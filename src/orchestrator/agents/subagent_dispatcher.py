r"""Subagent Dispatcher -- dynamic spawning and orchestration of specialized micro-agents.

Enables the orchestrator to decompose complex tasks and dispatch them to
specialized subagents that run in parallel, with result aggregation.

Architecture:
    SubagentDispatcher
      |-- register_subagent(spec)       -- register a subagent type
      |-- spawn(task)                   -- spawn subagent for a task
      |-- fan_out(tasks)                -- spawn N subagents in parallel
      |-- aggregate(results)            -- merge subagent outputs
      \-- execute_plan(plan)            -- run a multi-step subagent plan

Subagent Specializations:
    - BicepModuleAgent       -- generates a single Bicep module
    - ThreatAnalysisAgent    -- analyzes one STRIDE category
    - ComplianceCheckAgent   -- checks one compliance domain
    - CostEstimationAgent    -- estimates cost for one component
    - SecurityScanAgent      -- scans one artifact type
    - DocWriterAgent         -- writes one documentation file
    - TestWriterAgent        -- generates tests for one module
    - AlertRuleAgent         -- creates alert rules for one resource
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class SubagentStatus(str, Enum):
    """Status of a subagent execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentTask:
    """A task to be executed by a subagent."""

    task_id: str
    task_type: str  # Maps to a subagent specialization
    description: str
    input_data: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)  # task_ids this depends on
    priority: int = 100  # Lower = higher priority
    timeout_ms: int = 30000


@dataclass
class SubagentResult:
    """Result from a subagent execution."""

    task_id: str
    task_type: str
    status: SubagentStatus
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    subagent_name: str = ""


@runtime_checkable
class Subagent(Protocol):
    """Protocol for subagent implementations."""

    @property
    def name(self) -> str: ...

    @property
    def specialization(self) -> str: ...

    def execute(self, task: SubagentTask) -> SubagentResult: ...


class SubagentDispatcher:
    """Dispatches tasks to specialized subagents with parallel execution.

    Supports:
    - Fan-out: spawn N subagents simultaneously
    - Dependency resolution: tasks run in topological order
    - Result aggregation: merge outputs from multiple subagents
    - Error isolation: one subagent failure doesn't crash others
    """

    def __init__(self, max_workers: int = 4) -> None:
        self._subagents: dict[str, Subagent] = {}
        self._max_workers = max_workers
        self._execution_history: list[SubagentResult] = []

    def register(self, subagent: Subagent) -> None:
        """Register a subagent specialization."""
        self._subagents[subagent.specialization] = subagent
        logger.info(
            "subagent.registered",
            name=subagent.name,
            specialization=subagent.specialization,
        )

    def spawn(self, task: SubagentTask) -> SubagentResult:
        """Spawn a single subagent to execute a task."""
        subagent = self._subagents.get(task.task_type)
        if not subagent:
            return SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                status=SubagentStatus.FAILED,
                error=f"No subagent registered for type: {task.task_type}",
            )

        start = time.perf_counter()
        try:
            logger.info(
                "subagent.spawn",
                task_id=task.task_id,
                type=task.task_type,
                agent=subagent.name,
            )
            result = subagent.execute(task)
            result.duration_ms = (time.perf_counter() - start) * 1000
            self._execution_history.append(result)
            logger.info(
                "subagent.complete",
                task_id=task.task_id,
                status=result.status.value,
                duration_ms=f"{result.duration_ms:.1f}",
            )
            return result
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            result = SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                status=SubagentStatus.FAILED,
                error=str(e),
                duration_ms=duration,
                subagent_name=subagent.name,
            )
            self._execution_history.append(result)
            logger.error("subagent.failed", task_id=task.task_id, error=str(e))
            return result

    def fan_out(self, tasks: list[SubagentTask]) -> list[SubagentResult]:
        """Execute multiple tasks in parallel using a thread pool.

        Tasks without dependencies run concurrently. Tasks with
        dependencies wait for their prerequisites to complete.
        """
        if not tasks:
            return []

        # Separate independent tasks from dependent ones
        independent = [t for t in tasks if not t.dependencies]
        dependent = [t for t in tasks if t.dependencies]

        results: dict[str, SubagentResult] = {}

        # Execute independent tasks in parallel
        if independent:
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                futures = {executor.submit(self.spawn, task): task for task in independent}
                for future in as_completed(futures):
                    task = futures[future]
                    result = future.result()
                    results[task.task_id] = result

        # Execute dependent tasks in order
        for task in dependent:
            # Check if dependencies are met
            deps_met = all(
                dep_id in results and results[dep_id].status == SubagentStatus.COMPLETED for dep_id in task.dependencies
            )
            if deps_met:
                # Inject dependency outputs into task input
                for dep_id in task.dependencies:
                    if dep_id in results:
                        task.input_data[f"dep_{dep_id}"] = results[dep_id].output
                result = self.spawn(task)
            else:
                result = SubagentResult(
                    task_id=task.task_id,
                    task_type=task.task_type,
                    status=SubagentStatus.CANCELLED,
                    error="Dependencies not met",
                )
            results[task.task_id] = result

        # Return in original task order
        return [results[t.task_id] for t in tasks if t.task_id in results]

    def aggregate(self, results: list[SubagentResult]) -> dict[str, Any]:
        """Aggregate outputs from multiple subagent results.

        Merges file dictionaries, collects errors, computes stats.
        """
        aggregated: dict[str, Any] = {
            "files": {},
            "errors": [],
            "stats": {
                "total": len(results),
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "total_duration_ms": 0.0,
            },
        }

        for result in results:
            aggregated["stats"]["total_duration_ms"] += result.duration_ms

            if result.status == SubagentStatus.COMPLETED:
                aggregated["stats"]["completed"] += 1
                # Merge file outputs
                if "files" in result.output:
                    aggregated["files"].update(result.output["files"])
                # Collect other outputs
                for key, value in result.output.items():
                    if key != "files":
                        if key not in aggregated:
                            aggregated[key] = []
                        if isinstance(aggregated[key], list):
                            aggregated[key].append(value)
            elif result.status == SubagentStatus.FAILED:
                aggregated["stats"]["failed"] += 1
                aggregated["errors"].append({"task_id": result.task_id, "error": result.error})
            elif result.status == SubagentStatus.CANCELLED:
                aggregated["stats"]["cancelled"] += 1

        return aggregated

    @property
    def registered_types(self) -> list[str]:
        """List all registered subagent specializations."""
        return list(self._subagents.keys())

    @property
    def execution_history(self) -> list[SubagentResult]:
        """Get execution history."""
        return list(self._execution_history)

    @property
    def agent_count(self) -> int:
        """Number of registered subagents."""
        return len(self._subagents)


# ----------------- Built-in Subagents -----------------


class BicepModuleSubagent:
    """Generates a single Bicep module for a specific resource type."""

    @property
    def name(self) -> str:
        return "bicep-module-agent"

    @property
    def specialization(self) -> str:
        return "bicep_module"

    def execute(self, task: SubagentTask) -> SubagentResult:
        from src.orchestrator.generators.bicep_generator import BicepGenerator

        module_name = task.input_data.get("module_name", "")
        spec = task.input_data.get("spec")
        plan = task.input_data.get("plan")

        if not spec or not plan:
            return SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                status=SubagentStatus.FAILED,
                error="Missing spec or plan",
                subagent_name=self.name,
            )

        generator = BicepGenerator()
        all_files = generator.generate(spec, plan)
        # Filter to just the requested module
        module_files = {k: v for k, v in all_files.items() if module_name in k or not module_name}

        return SubagentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            status=SubagentStatus.COMPLETED,
            output={"files": module_files, "module": module_name},
            subagent_name=self.name,
        )


class ComplianceCheckSubagent:
    """Checks compliance for a specific domain (security, networking, etc.)."""

    @property
    def name(self) -> str:
        return "compliance-check-agent"

    @property
    def specialization(self) -> str:
        return "compliance_check"

    def execute(self, task: SubagentTask) -> SubagentResult:
        domain = task.input_data.get("domain", "security")
        spec = task.input_data.get("spec")
        plan = task.input_data.get("plan")

        if not spec or not plan:
            return SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                status=SubagentStatus.FAILED,
                error="Missing spec or plan",
                subagent_name=self.name,
            )

        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent

        reviewer = GovernanceReviewerAgent()
        report = reviewer.validate_plan(spec, plan)

        # Filter checks by domain
        domain_checks = [
            c for c in report.checks if domain.lower() in c.check_id.lower() or domain.lower() in c.name.lower()
        ]

        return SubagentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            status=SubagentStatus.COMPLETED,
            output={
                "domain": domain,
                "checks": [{"id": c.check_id, "name": c.name, "passed": c.passed} for c in domain_checks],
                "passed_count": sum(1 for c in domain_checks if c.passed),
                "total_count": len(domain_checks),
            },
            subagent_name=self.name,
        )


class CostEstimationSubagent:
    """Estimates Azure costs for a component based on SKU and region."""

    @property
    def name(self) -> str:
        return "cost-estimation-agent"

    @property
    def specialization(self) -> str:
        return "cost_estimation"

    def execute(self, task: SubagentTask) -> SubagentResult:
        component = task.input_data.get("component_name", "")
        azure_service = task.input_data.get("azure_service", "")
        region = task.input_data.get("region", "eastus2")

        # Estimated monthly costs by service type (conservative estimates)
        cost_estimates: dict[str, dict[str, float]] = {
            "Azure Container Apps": {
                "base": 0.0,
                "per_vcpu_hr": 0.0876,
                "per_gb_hr": 0.0109,
                "estimated_monthly": 45.0,
            },
            "Azure Key Vault": {"base": 0.0, "per_10k_ops": 0.03, "estimated_monthly": 5.0},
            "Azure Log Analytics": {"per_gb_ingested": 2.76, "estimated_monthly": 25.0},
            "Azure Container Registry": {"basic_monthly": 5.0, "standard_monthly": 20.0, "estimated_monthly": 20.0},
            "Azure Storage Account": {"per_gb_hot": 0.018, "per_10k_write": 0.05, "estimated_monthly": 10.0},
            "Managed Identity": {"estimated_monthly": 0.0},
        }

        est = cost_estimates.get(azure_service, {"estimated_monthly": 15.0})

        return SubagentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            status=SubagentStatus.COMPLETED,
            output={
                "component": component,
                "azure_service": azure_service,
                "region": region,
                "estimated_monthly_usd": est.get("estimated_monthly", 15.0),
                "pricing_details": est,
            },
            subagent_name=self.name,
        )


class SecurityScanSubagent:
    """Scans generated artifacts for security anti-patterns."""

    @property
    def name(self) -> str:
        return "security-scan-agent"

    @property
    def specialization(self) -> str:
        return "security_scan"

    def execute(self, task: SubagentTask) -> SubagentResult:
        files = task.input_data.get("files", {})

        if not files:
            return SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                status=SubagentStatus.FAILED,
                error="No files to scan",
                subagent_name=self.name,
            )

        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent

        reviewer = GovernanceReviewerAgent()
        report = reviewer.validate_bicep(files)

        return SubagentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            status=SubagentStatus.COMPLETED,
            output={
                "files_scanned": len(files),
                "issues_found": len([c for c in report.checks if not c.passed]),
                "status": report.status,
                "checks": [
                    {"id": c.check_id, "name": c.name, "passed": c.passed, "details": c.details} for c in report.checks
                ],
            },
            subagent_name=self.name,
        )


class DocWriterSubagent:
    """Generates a specific documentation file."""

    @property
    def name(self) -> str:
        return "doc-writer-agent"

    @property
    def specialization(self) -> str:
        return "doc_writer"

    def execute(self, task: SubagentTask) -> SubagentResult:
        doc_type = task.input_data.get("doc_type", "plan")
        spec = task.input_data.get("spec")
        plan = task.input_data.get("plan")

        if not spec or not plan:
            return SubagentResult(
                task_id=task.task_id,
                task_type=task.task_type,
                status=SubagentStatus.FAILED,
                error="Missing spec or plan",
                subagent_name=self.name,
            )

        from src.orchestrator.generators.docs_generator import DocsGenerator

        generator = DocsGenerator()
        all_docs = generator.generate(spec, plan)
        # Filter to requested doc type
        doc_files = {k: v for k, v in all_docs.items() if doc_type in k}

        return SubagentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            status=SubagentStatus.COMPLETED,
            output={"files": doc_files, "doc_type": doc_type},
            subagent_name=self.name,
        )


class AlertRuleSubagent:
    """Creates Azure Monitor alert rules for a specific resource."""

    @property
    def name(self) -> str:
        return "alert-rule-agent"

    @property
    def specialization(self) -> str:
        return "alert_rule"

    def execute(self, task: SubagentTask) -> SubagentResult:
        resource_type = task.input_data.get("resource_type", "container-app")
        project_name = task.input_data.get("project_name", "app")

        alert_templates: dict[str, list[dict[str, Any]]] = {
            "container-app": [
                {
                    "name": f"High CPU - {project_name}",
                    "metric": "UsageNanoCores",
                    "operator": "GreaterThan",
                    "threshold": 80,
                    "severity": 2,
                },
                {
                    "name": f"High Memory - {project_name}",
                    "metric": "UsageBytes",
                    "operator": "GreaterThan",
                    "threshold": 85,
                    "severity": 2,
                },
                {
                    "name": f"5xx Errors - {project_name}",
                    "metric": "Requests",
                    "operator": "GreaterThan",
                    "threshold": 10,
                    "severity": 1,
                },
                {
                    "name": f"Response Time - {project_name}",
                    "metric": "RequestDuration",
                    "operator": "GreaterThan",
                    "threshold": 5000,
                    "severity": 3,
                },
            ],
            "key-vault": [
                {
                    "name": f"KV Availability - {project_name}",
                    "metric": "Availability",
                    "operator": "LessThan",
                    "threshold": 99,
                    "severity": 1,
                },
                {
                    "name": f"KV Saturation - {project_name}",
                    "metric": "SaturationShoebox",
                    "operator": "GreaterThan",
                    "threshold": 75,
                    "severity": 2,
                },
            ],
            "storage": [
                {
                    "name": f"Storage Availability - {project_name}",
                    "metric": "Availability",
                    "operator": "LessThan",
                    "threshold": 99,
                    "severity": 1,
                },
                {
                    "name": f"Storage Latency - {project_name}",
                    "metric": "SuccessE2ELatency",
                    "operator": "GreaterThan",
                    "threshold": 1000,
                    "severity": 3,
                },
            ],
        }

        alerts = alert_templates.get(resource_type, [])

        return SubagentResult(
            task_id=task.task_id,
            task_type=task.task_type,
            status=SubagentStatus.COMPLETED,
            output={
                "resource_type": resource_type,
                "alerts": alerts,
                "alert_count": len(alerts),
            },
            subagent_name=self.name,
        )


def create_default_dispatcher() -> SubagentDispatcher:
    """Create a dispatcher with all built-in subagents registered.

    Returns:
        A fully populated SubagentDispatcher ready for use.
    """
    dispatcher = SubagentDispatcher()

    built_ins: list[Subagent] = [
        BicepModuleSubagent(),  # type: ignore[list-item]
        ComplianceCheckSubagent(),  # type: ignore[list-item]
        CostEstimationSubagent(),  # type: ignore[list-item]
        SecurityScanSubagent(),  # type: ignore[list-item]
        DocWriterSubagent(),  # type: ignore[list-item]
        AlertRuleSubagent(),  # type: ignore[list-item]
    ]

    for subagent in built_ins:
        dispatcher.register(subagent)

    logger.info("subagent.dispatcher.initialized", agent_count=dispatcher.agent_count)
    return dispatcher
