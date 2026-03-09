"""Persistent Planning -- resumable, checkpoint-based task execution.

Implements a Manus-style persistent planning system where:
- Complex work is decomposed into a task graph with dependencies
- Each task has a status (pending/running/done/failed/skipped)
- Progress is checkpointed to disk after each step
- Failed pipelines can resume from the last successful step
- Task history provides audit trail of all executions

State is persisted to .devex/plan_state.json alongside the existing
state.json for drift detection.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Status of a pipeline task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    """Priority level for tasks."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class PlanTask:
    """A single task in the execution plan."""

    task_id: str
    name: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: list[str] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: float = 0.0
    error: str | None = None
    output_summary: str = ""
    retry_count: int = 0
    max_retries: int = 2
    checkpoint_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to dict."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "dependencies": self.dependencies,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "output_summary": self.output_summary,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "checkpoint_data": self.checkpoint_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanTask:
        """Deserialize task from dict."""
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            description=data["description"],
            status=TaskStatus(data.get("status", "pending")),
            priority=TaskPriority(data.get("priority", "medium")),
            dependencies=data.get("dependencies", []),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            duration_ms=data.get("duration_ms", 0.0),
            error=data.get("error"),
            output_summary=data.get("output_summary", ""),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 2),
            checkpoint_data=data.get("checkpoint_data", {}),
        )


@dataclass
class ExecutionPlan:
    """A complete execution plan with ordered tasks.

    Plans are versioned and checkpointed. Each version represents
    a distinct intent -> scaffold run.
    """

    plan_id: str
    version: int = 1
    intent_hash: str = ""
    created_at: str = ""
    updated_at: str = ""
    tasks: list[PlanTask] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are done or skipped."""
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
            for t in self.tasks
        )

    @property
    def has_failures(self) -> bool:
        """Check if any tasks failed."""
        return any(t.status == TaskStatus.FAILED for t in self.tasks)

    @property
    def current_task(self) -> PlanTask | None:
        """Get the currently in-progress task."""
        for t in self.tasks:
            if t.status == TaskStatus.IN_PROGRESS:
                return t
        return None

    @property
    def next_task(self) -> PlanTask | None:
        """Get the next pending task whose dependencies are met."""
        completed_ids = {
            t.task_id for t in self.tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
        }
        for t in self.tasks:
            if t.status == TaskStatus.PENDING and all(
                dep in completed_ids for dep in t.dependencies
            ):
                return t
        return None

    @property
    def progress_pct(self) -> float:
        """Completion percentage."""
        if not self.tasks:
            return 0.0
        done = sum(
            1 for t in self.tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
        )
        return (done / len(self.tasks)) * 100

    def summary(self) -> dict[str, int]:
        """Return task count by status."""
        counts: dict[str, int] = {}
        for t in self.tasks:
            key = t.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Serialize plan to dict."""
        return {
            "plan_id": self.plan_id,
            "version": self.version,
            "intent_hash": self.intent_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tasks": [t.to_dict() for t in self.tasks],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionPlan:
        """Deserialize plan from dict."""
        return cls(
            plan_id=data.get("plan_id", ""),
            version=data.get("version", 1),
            intent_hash=data.get("intent_hash", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            tasks=[PlanTask.from_dict(t) for t in data.get("tasks", [])],
            metadata=data.get("metadata", {}),
        )


class PersistentPlanner:
    """Manages persistent, resumable execution plans.

    Features:
    - Creates task graphs from pipeline stages
    - Checkpoints after each task
    - Resumes from last successful step on failure
    - Tracks execution history across sessions
    - Supports plan versioning for intent changes
    """

    PLAN_FILE = ".devex/plan_state.json"
    HISTORY_FILE = ".devex/plan_history.json"

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.plan_path = self.output_dir / self.PLAN_FILE
        self.history_path = self.output_dir / self.HISTORY_FILE
        self._task_handlers: dict[str, Callable[..., dict[str, Any]]] = {}
        self.plan: ExecutionPlan | None = self._load_plan()

    def _load_plan(self) -> ExecutionPlan | None:
        """Load existing plan from disk."""
        if self.plan_path.exists():
            try:
                data = json.loads(self.plan_path.read_text(encoding="utf-8"))
                plan = ExecutionPlan.from_dict(data)
                logger.info("planner.loaded", plan_id=plan.plan_id, progress=f"{plan.progress_pct:.0f}%")
                return plan
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("planner.load_failed", error=str(exc))
        return None

    def _save_plan(self) -> None:
        """Persist current plan to disk."""
        if not self.plan:
            return
        self.plan.updated_at = datetime.now(tz=UTC).isoformat()
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(
            json.dumps(self.plan.to_dict(), indent=2),
            encoding="utf-8",
        )
        logger.debug("planner.saved", plan_id=self.plan.plan_id)

    def _save_history(self, plan: ExecutionPlan) -> None:
        """Append completed plan to history."""
        history: list[dict[str, Any]] = []
        if self.history_path.exists():
            try:
                history = json.loads(self.history_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                history = []

        history.append(plan.to_dict())
        # Keep last 10 runs
        if len(history) > 10:
            history = history[-10:]

        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(
            json.dumps(history, indent=2),
            encoding="utf-8",
        )

    def register_handler(self, task_id: str, handler: Callable[..., dict[str, Any]]) -> None:
        """Register a handler function for a task type."""
        self._task_handlers[task_id] = handler

    def create_pipeline_plan(self, intent: str, project_name: str = "") -> ExecutionPlan:
        """Create a standard 4-agent pipeline plan.

        This decomposes the orchestration into resumable steps.
        """
        intent_hash = hashlib.sha256(intent.encode()).hexdigest()[:16]

        # Check if we can resume an existing plan
        if self.plan and self.plan.intent_hash == intent_hash and not self.plan.is_complete:
            logger.info("planner.resume", plan_id=self.plan.plan_id, progress=f"{self.plan.progress_pct:.0f}%")
            return self.plan

        plan = ExecutionPlan(
            plan_id=f"plan-{intent_hash[:8]}",
            intent_hash=intent_hash,
            created_at=datetime.now(tz=UTC).isoformat(),
            metadata={"intent": intent, "project_name": project_name},
            tasks=[
                PlanTask(
                    task_id="parse-intent",
                    name="Parse Business Intent",
                    description="Extract structured IntentSpec from natural language",
                    priority=TaskPriority.CRITICAL,
                ),
                PlanTask(
                    task_id="analyze-codebase",
                    name="Analyze Existing Codebase",
                    description="Scan project for language, framework, and patterns",
                    priority=TaskPriority.HIGH,
                    dependencies=["parse-intent"],
                ),
                PlanTask(
                    task_id="plan-architecture",
                    name="Plan Architecture",
                    description="Design Azure components, ADRs, and threat model",
                    priority=TaskPriority.CRITICAL,
                    dependencies=["parse-intent"],
                ),
                PlanTask(
                    task_id="validate-governance",
                    name="Validate Governance",
                    description="Check plan against 20 enterprise governance policies",
                    priority=TaskPriority.CRITICAL,
                    dependencies=["plan-architecture"],
                ),
                PlanTask(
                    task_id="assess-waf",
                    name="WAF Assessment",
                    description="Evaluate against 26 Well-Architected Framework principles",
                    priority=TaskPriority.HIGH,
                    dependencies=["validate-governance"],
                ),
                PlanTask(
                    task_id="generate-bicep",
                    name="Generate Bicep IaC",
                    description="Generate Bicep templates (7 modules + parameters)",
                    priority=TaskPriority.CRITICAL,
                    dependencies=["validate-governance"],
                ),
                PlanTask(
                    task_id="generate-cicd",
                    name="Generate CI/CD",
                    description="Generate GitHub Actions workflows with OIDC",
                    priority=TaskPriority.HIGH,
                    dependencies=["parse-intent"],
                ),
                PlanTask(
                    task_id="generate-app",
                    name="Generate Application",
                    description="Generate FastAPI application scaffold",
                    priority=TaskPriority.HIGH,
                    dependencies=["parse-intent"],
                ),
                PlanTask(
                    task_id="generate-tests",
                    name="Generate Tests",
                    description="Generate pytest tests for the application",
                    priority=TaskPriority.MEDIUM,
                    dependencies=["generate-app"],
                ),
                PlanTask(
                    task_id="generate-alerts",
                    name="Generate Alert Rules",
                    description="Generate Azure Monitor alert rules in Bicep",
                    priority=TaskPriority.MEDIUM,
                    dependencies=["generate-bicep"],
                ),
                PlanTask(
                    task_id="generate-docs",
                    name="Generate Documentation",
                    description="Generate 9 documentation files",
                    priority=TaskPriority.MEDIUM,
                    dependencies=["validate-governance", "assess-waf"],
                ),
                PlanTask(
                    task_id="security-scan",
                    name="Security Scan",
                    description="Scan generated artifacts for security anti-patterns",
                    priority=TaskPriority.HIGH,
                    dependencies=["generate-bicep", "generate-app"],
                ),
                PlanTask(
                    task_id="cost-estimation",
                    name="Cost Estimation",
                    description="Estimate monthly Azure costs for all components",
                    priority=TaskPriority.LOW,
                    dependencies=["plan-architecture"],
                ),
            ],
        )

        self.plan = plan
        self._save_plan()
        logger.info("planner.created", plan_id=plan.plan_id, tasks=len(plan.tasks))
        return plan

    def execute_task(self, task_id: str, handler: Callable[..., dict[str, Any]] | None = None, **kwargs: Any) -> PlanTask:
        """Execute a single task with checkpointing.

        Args:
            task_id: ID of the task to execute.
            handler: Optional handler function. Falls back to registered handlers.
            **kwargs: Arguments passed to the handler.

        Returns:
            The updated PlanTask after execution.
        """
        if not self.plan:
            raise RuntimeError("No plan loaded. Call create_pipeline_plan() first.")

        task = next((t for t in self.plan.tasks if t.task_id == task_id), None)
        if not task:
            raise ValueError(f"Task '{task_id}' not found in plan")

        # Use provided handler or registered handler
        fn = handler or self._task_handlers.get(task_id)
        if not fn:
            raise ValueError(f"No handler for task '{task_id}'")

        # Mark as in-progress
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(tz=UTC).isoformat()
        self._save_plan()

        start = time.perf_counter()
        try:
            result = fn(**kwargs)
            duration = (time.perf_counter() - start) * 1000

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(tz=UTC).isoformat()
            task.duration_ms = duration
            task.output_summary = str(result.get("summary", ""))[:200] if isinstance(result, dict) else ""
            task.checkpoint_data = {
                k: v for k, v in (result if isinstance(result, dict) else {}).items()
                if k != "summary" and _is_serializable(v)
            }

            logger.info(
                "planner.task.completed",
                task_id=task_id,
                duration_ms=f"{duration:.1f}",
            )

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            task.duration_ms = duration
            task.retry_count += 1

            if task.retry_count <= task.max_retries:
                task.status = TaskStatus.PENDING
                task.error = f"Retry {task.retry_count}/{task.max_retries}: {e}"
                logger.warning(
                    "planner.task.retry",
                    task_id=task_id,
                    attempt=task.retry_count,
                    error=str(e),
                )
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                logger.error("planner.task.failed", task_id=task_id, error=str(e))

        self._save_plan()

        # If plan is complete, save to history
        if self.plan.is_complete:
            self._save_history(self.plan)
            logger.info("planner.complete", plan_id=self.plan.plan_id)

        return task

    def get_resumable_tasks(self) -> list[PlanTask]:
        """Get tasks that can be resumed (pending with met dependencies)."""
        if not self.plan:
            return []

        completed_ids = {
            t.task_id for t in self.plan.tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
        }

        resumable = []
        for t in self.plan.tasks:
            if t.status in (TaskStatus.PENDING, TaskStatus.FAILED) and all(
                dep in completed_ids for dep in t.dependencies
            ):
                resumable.append(t)

        return resumable

    def reset_failed_tasks(self) -> int:
        """Reset all failed tasks to pending for retry."""
        if not self.plan:
            return 0

        count = 0
        for t in self.plan.tasks:
            if t.status == TaskStatus.FAILED:
                t.status = TaskStatus.PENDING
                t.error = None
                t.retry_count = 0
                count += 1

        if count:
            self._save_plan()
        return count

    def get_plan_summary(self) -> dict[str, Any]:
        """Get a summary of the current plan state."""
        if not self.plan:
            return {"status": "no_plan"}

        return {
            "plan_id": self.plan.plan_id,
            "progress_pct": self.plan.progress_pct,
            "is_complete": self.plan.is_complete,
            "has_failures": self.plan.has_failures,
            "task_counts": self.plan.summary(),
            "current_task": self.plan.current_task.name if self.plan.current_task else None,
            "next_task": self.plan.next_task.name if self.plan.next_task else None,
            "total_duration_ms": sum(t.duration_ms for t in self.plan.tasks),
        }

    def get_execution_history(self) -> list[dict[str, Any]]:
        """Load execution history from disk."""
        if not self.history_path.exists():
            return []
        try:
            return json.loads(self.history_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            return []


def _is_serializable(value: Any) -> bool:
    """Check if a value is JSON-serializable."""
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False
