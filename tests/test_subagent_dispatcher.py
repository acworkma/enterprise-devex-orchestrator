"""Tests for Subagent Dispatcher -- spawning, fan-out, aggregation."""

from __future__ import annotations

from src.orchestrator.agents.subagent_dispatcher import (
    SubagentDispatcher,
    SubagentResult,
    SubagentStatus,
    SubagentTask,
    create_default_dispatcher,
)

# ----------------- Test Helpers -----------------


class _EchoSubagent:
    """Subagent that echoes its input."""

    def __init__(self, spec: str = "echo") -> None:
        self._spec = spec

    @property
    def name(self) -> str:
        return f"echo-{self._spec}"

    @property
    def specialization(self) -> str:
        return self._spec

    def execute(self, task: SubagentTask) -> SubagentResult:
        return SubagentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            status=SubagentStatus.COMPLETED,
            output={"echoed": task.input_data, "files": {f"{task.task_id}.txt": "content"}},
            subagent_name=self.name,
        )


class _FailSubagent:
    """Subagent that always fails."""

    @property
    def name(self) -> str:
        return "fail-agent"

    @property
    def specialization(self) -> str:
        return "fail"

    def execute(self, task: SubagentTask) -> SubagentResult:
        raise RuntimeError("Subagent crash")


# ----------------- Registration -----------------


class TestSubagentRegistration:
    def test_register_subagent(self) -> None:
        d = SubagentDispatcher()
        d.register(_EchoSubagent("test"))
        assert "test" in d.registered_types

    def test_registered_types(self) -> None:
        d = SubagentDispatcher()
        d.register(_EchoSubagent("alpha"))
        d.register(_EchoSubagent("beta"))
        assert set(d.registered_types) == {"alpha", "beta"}


# ----------------- Spawn -----------------


class TestSubagentSpawn:
    def test_spawn_success(self) -> None:
        d = SubagentDispatcher()
        d.register(_EchoSubagent("echo"))
        task = SubagentTask(task_id="t1", task_type="echo", description="test")
        result = d.spawn(task)
        assert result.status == SubagentStatus.COMPLETED
        assert result.task_id == "t1"
        assert result.duration_ms >= 0

    def test_spawn_unknown_type(self) -> None:
        d = SubagentDispatcher()
        task = SubagentTask(task_id="t2", task_type="unknown", description="x")
        result = d.spawn(task)
        assert result.status == SubagentStatus.FAILED
        assert "No subagent registered" in result.error

    def test_spawn_failure_captured(self) -> None:
        d = SubagentDispatcher()
        d.register(_FailSubagent())
        task = SubagentTask(task_id="t3", task_type="fail", description="crash")
        result = d.spawn(task)
        assert result.status == SubagentStatus.FAILED
        assert "Subagent crash" in result.error

    def test_execution_history(self) -> None:
        d = SubagentDispatcher()
        d.register(_EchoSubagent("echo"))
        d.spawn(SubagentTask(task_id="h1", task_type="echo", description="x"))
        d.spawn(SubagentTask(task_id="h2", task_type="echo", description="x"))
        assert len(d.execution_history) == 2


# ----------------- Fan-Out -----------------


class TestSubagentFanOut:
    def test_fan_out_parallel(self) -> None:
        d = SubagentDispatcher(max_workers=2)
        d.register(_EchoSubagent("echo"))
        tasks = [SubagentTask(task_id=f"p{i}", task_type="echo", description=f"task {i}") for i in range(4)]
        results = d.fan_out(tasks)
        assert len(results) == 4
        assert all(r.status == SubagentStatus.COMPLETED for r in results)

    def test_fan_out_empty_list(self) -> None:
        d = SubagentDispatcher()
        assert d.fan_out([]) == []

    def test_fan_out_with_dependencies(self) -> None:
        d = SubagentDispatcher()
        d.register(_EchoSubagent("echo"))
        tasks = [
            SubagentTask(task_id="ind1", task_type="echo", description="independent"),
            SubagentTask(
                task_id="dep1",
                task_type="echo",
                description="depends on ind1",
                dependencies=["ind1"],
            ),
        ]
        results = d.fan_out(tasks)
        assert len(results) == 2
        assert results[0].status == SubagentStatus.COMPLETED
        assert results[1].status == SubagentStatus.COMPLETED

    def test_fan_out_cancelled_on_unmet_deps(self) -> None:
        d = SubagentDispatcher()
        d.register(_FailSubagent())
        tasks = [
            SubagentTask(task_id="f1", task_type="fail", description="will fail"),
            SubagentTask(
                task_id="d1",
                task_type="fail",
                description="depends on f1",
                dependencies=["f1"],
            ),
        ]
        results = d.fan_out(tasks)
        dep_result = next(r for r in results if r.task_id == "d1")
        assert dep_result.status == SubagentStatus.CANCELLED


# ----------------- Aggregation -----------------


class TestSubagentAggregation:
    def test_aggregate_merges_files(self) -> None:
        d = SubagentDispatcher()
        results = [
            SubagentResult(
                task_id="a1",
                task_type="echo",
                status=SubagentStatus.COMPLETED,
                output={"files": {"a.bicep": "aaa"}},
            ),
            SubagentResult(
                task_id="a2",
                task_type="echo",
                status=SubagentStatus.COMPLETED,
                output={"files": {"b.bicep": "bbb"}},
            ),
        ]
        agg = d.aggregate(results)
        assert "a.bicep" in agg["files"]
        assert "b.bicep" in agg["files"]

    def test_aggregate_counts_status(self) -> None:
        d = SubagentDispatcher()
        results = [
            SubagentResult("ok", "t", SubagentStatus.COMPLETED, output={}),
            SubagentResult("fail", "t", SubagentStatus.FAILED, error="e"),
            SubagentResult("cancel", "t", SubagentStatus.CANCELLED),
        ]
        agg = d.aggregate(results)
        assert agg["stats"]["completed"] == 1
        assert agg["stats"]["failed"] == 1
        assert agg["stats"]["cancelled"] == 1
        assert agg["stats"]["total"] == 3

    def test_aggregate_collects_errors(self) -> None:
        d = SubagentDispatcher()
        results = [
            SubagentResult("f1", "t", SubagentStatus.FAILED, error="err1"),
        ]
        agg = d.aggregate(results)
        assert len(agg["errors"]) == 1
        assert agg["errors"][0]["error"] == "err1"


# ----------------- Default Dispatcher -----------------


class TestDefaultDispatcher:
    def test_creates_with_builtin_subagents(self) -> None:
        d = create_default_dispatcher()
        assert len(d.registered_types) >= 6  # 6 built-in subagents

    def test_has_bicep_module_subagent(self) -> None:
        d = create_default_dispatcher()
        assert "bicep_module" in d.registered_types

    def test_has_compliance_check_subagent(self) -> None:
        d = create_default_dispatcher()
        assert "compliance_check" in d.registered_types

    def test_has_security_scan_subagent(self) -> None:
        d = create_default_dispatcher()
        assert "security_scan" in d.registered_types

    def test_has_doc_writer_subagent(self) -> None:
        d = create_default_dispatcher()
        assert "doc_writer" in d.registered_types
