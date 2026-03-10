"""Tests for Persistent Planning -- plan creation, execution, checkpointing, resume."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.orchestrator.planning import (
    ExecutionPlan,
    PersistentPlanner,
    PlanTask,
    TaskPriority,
    TaskStatus,
)


@pytest.fixture()
def tmp_out(tmp_path: Path) -> Path:
    """Provide a temporary output directory."""
    return tmp_path / "out"


# ----------------- PlanTask -----------------


class TestPlanTask:
    def test_defaults(self) -> None:
        t = PlanTask(task_id="t1", name="Test", description="desc")
        assert t.status == TaskStatus.PENDING
        assert t.priority == TaskPriority.MEDIUM
        assert t.retry_count == 0
        assert t.max_retries == 2

    def test_serialization_roundtrip(self) -> None:
        t = PlanTask(
            task_id="t2",
            name="Round",
            description="trip",
            status=TaskStatus.COMPLETED,
            priority=TaskPriority.HIGH,
            dependencies=["t1"],
        )
        data = t.to_dict()
        restored = PlanTask.from_dict(data)
        assert restored.task_id == "t2"
        assert restored.status == TaskStatus.COMPLETED
        assert restored.priority == TaskPriority.HIGH
        assert restored.dependencies == ["t1"]


# ----------------- ExecutionPlan -----------------


class TestExecutionPlan:
    def _make_plan(self, statuses: list[TaskStatus]) -> ExecutionPlan:
        return ExecutionPlan(
            plan_id="test",
            tasks=[
                PlanTask(task_id=f"t{i}", name=f"Task {i}", description="", status=s)
                for i, s in enumerate(statuses)
            ],
        )

    def test_is_complete_all_done(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.SKIPPED])
        assert plan.is_complete is True

    def test_is_complete_with_pending(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.PENDING])
        assert plan.is_complete is False

    def test_has_failures(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.FAILED])
        assert plan.has_failures is True

    def test_no_failures(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.COMPLETED])
        assert plan.has_failures is False

    def test_current_task(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS, TaskStatus.PENDING])
        current = plan.current_task
        assert current is not None
        assert current.task_id == "t1"

    def test_current_task_none_when_no_in_progress(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.PENDING])
        assert plan.current_task is None

    def test_next_task_with_deps(self) -> None:
        plan = ExecutionPlan(
            plan_id="deps",
            tasks=[
                PlanTask(task_id="a", name="A", description="", status=TaskStatus.COMPLETED),
                PlanTask(task_id="b", name="B", description="", dependencies=["a"]),
                PlanTask(task_id="c", name="C", description="", dependencies=["b"]),
            ],
        )
        nxt = plan.next_task
        assert nxt is not None
        assert nxt.task_id == "b"

    def test_progress_pct(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.PENDING, TaskStatus.PENDING])
        assert plan.progress_pct == 25.0

    def test_progress_pct_empty(self) -> None:
        plan = ExecutionPlan(plan_id="empty")
        assert plan.progress_pct == 0.0

    def test_summary_counts(self) -> None:
        plan = self._make_plan([TaskStatus.COMPLETED, TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.FAILED])
        s = plan.summary()
        assert s["completed"] == 2
        assert s["pending"] == 1
        assert s["failed"] == 1

    def test_serialization_roundtrip(self) -> None:
        plan = ExecutionPlan(
            plan_id="rt",
            version=2,
            intent_hash="abc123",
            created_at="2024-01-01",
            tasks=[PlanTask(task_id="t", name="T", description="D")],
            metadata={"key": "val"},
        )
        data = plan.to_dict()
        restored = ExecutionPlan.from_dict(data)
        assert restored.plan_id == "rt"
        assert restored.version == 2
        assert restored.intent_hash == "abc123"
        assert len(restored.tasks) == 1
        assert restored.metadata["key"] == "val"


# ----------------- PersistentPlanner -----------------


class TestPersistentPlanner:
    def test_create_pipeline_plan(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        plan = planner.create_pipeline_plan("Build a test API")
        assert plan is not None
        assert len(plan.tasks) == 13
        assert plan.plan_id.startswith("plan-")

    def test_plan_persisted_to_disk(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Build a test API")
        plan_file = tmp_out / ".devex" / "plan_state.json"
        assert plan_file.exists()
        data = json.loads(plan_file.read_text())
        assert data["plan_id"].startswith("plan-")

    def test_resume_existing_plan(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        plan1 = planner.create_pipeline_plan("Build a test API")
        plan_id = plan1.plan_id

        # Create a new planner that should load from disk
        planner2 = PersistentPlanner(tmp_out)
        plan2 = planner2.create_pipeline_plan("Build a test API")
        assert plan2.plan_id == plan_id  # Same plan resumed

    def test_new_intent_creates_new_plan(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        plan1 = planner.create_pipeline_plan("Build API A")

        # Different intent -> new plan
        plan2 = planner.create_pipeline_plan("Build API B")
        assert plan2.plan_id != plan1.plan_id

    def test_execute_task(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test intent")
        task = planner.execute_task("parse-intent", handler=lambda: {"summary": "parsed"})
        assert task.status == TaskStatus.COMPLETED
        assert task.duration_ms > 0
        assert task.output_summary == "parsed"

    def test_execute_task_failure_and_retry(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test intent")

        call_count = 0

        def _flaky() -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Flaky error")
            return {"summary": "ok"}

        # First call: fails but becomes PENDING (retry available)
        task1 = planner.execute_task("parse-intent", handler=_flaky)
        assert task1.status == TaskStatus.PENDING  # retryable
        assert task1.retry_count == 1

        # Second call: succeeds
        task2 = planner.execute_task("parse-intent", handler=_flaky)
        assert task2.status == TaskStatus.COMPLETED

    def test_execute_task_no_handler_raises(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test")
        with pytest.raises(ValueError, match="No handler"):
            planner.execute_task("parse-intent")

    def test_execute_task_unknown_raises(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test")
        with pytest.raises(ValueError, match="not found"):
            planner.execute_task("nonexistent-task", handler=lambda: {})

    def test_execute_task_no_plan_raises(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        with pytest.raises(RuntimeError, match="No plan"):
            planner.execute_task("parse-intent", handler=lambda: {})

    def test_get_resumable_tasks(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test")
        resumable = planner.get_resumable_tasks()
        # parse-intent has no deps, so it should be resumable
        ids = [t.task_id for t in resumable]
        assert "parse-intent" in ids

    def test_reset_failed_tasks(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test")

        # Force a task to FAILED
        for t in planner.plan.tasks:
            if t.task_id == "parse-intent":
                t.status = TaskStatus.FAILED
                t.retry_count = 99
                break

        count = planner.reset_failed_tasks()
        assert count == 1
        task = next(t for t in planner.plan.tasks if t.task_id == "parse-intent")
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0

    def test_get_plan_summary(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test")
        summary = planner.get_plan_summary()
        assert summary["plan_id"].startswith("plan-")
        assert summary["progress_pct"] == 0.0
        assert summary["is_complete"] is False
        assert "task_counts" in summary

    def test_get_plan_summary_no_plan(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        summary = planner.get_plan_summary()
        assert summary["status"] == "no_plan"

    def test_register_handler(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        planner.create_pipeline_plan("Test")
        planner.register_handler("parse-intent", lambda: {"summary": "handled"})
        task = planner.execute_task("parse-intent")
        assert task.status == TaskStatus.COMPLETED

    def test_history_saved_on_completion(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        plan = planner.create_pipeline_plan("Test")

        # Complete all tasks
        for t in plan.tasks:
            planner.execute_task(t.task_id, handler=lambda: {"summary": "done"})

        history = planner.get_execution_history()
        assert len(history) >= 1

    def test_pipeline_plan_has_correct_dependencies(self, tmp_out: Path) -> None:
        planner = PersistentPlanner(tmp_out)
        plan = planner.create_pipeline_plan("Test")

        task_map = {t.task_id: t for t in plan.tasks}
        # parse-intent has no deps
        assert task_map["parse-intent"].dependencies == []
        # plan-architecture depends on parse-intent
        assert "parse-intent" in task_map["plan-architecture"].dependencies
        # validate-governance depends on plan-architecture
        assert "plan-architecture" in task_map["validate-governance"].dependencies
        # generate-bicep depends on validate-governance
        assert "validate-governance" in task_map["generate-bicep"].dependencies
