"""Skill Registry — dynamic discovery, registration, and routing of domain skills.

A Skill is a self-contained unit of expertise that an agent can invoke.
Skills declare their capabilities, version, input/output types, and
dependencies so the orchestrator can route work to the right specialist.

Architecture:
    SkillRegistry
      ├── register(skill)         — add skill to catalog
      ├── discover(directory)     — auto-load skills from a folder
      ├── route(capability)       — find best skill for a task
      ├── list_skills()           — catalog introspection
      └── execute(name, context)  — run a skill and return result
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class SkillCategory(str, Enum):
    """Broad skill categories for routing."""

    PARSING = "parsing"
    ARCHITECTURE = "architecture"
    GOVERNANCE = "governance"
    SECURITY = "security"
    GENERATION = "generation"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    COMPLIANCE = "compliance"
    DOCUMENTATION = "documentation"
    COST = "cost"
    NETWORKING = "networking"


@dataclass(frozen=True)
class SkillMetadata:
    """Metadata describing a skill's capabilities and requirements."""

    name: str
    version: str
    description: str
    category: SkillCategory
    capabilities: tuple[str, ...]  # What this skill can do
    input_types: tuple[str, ...] = ()  # Expected input type names
    output_types: tuple[str, ...] = ()  # Expected output type names
    dependencies: tuple[str, ...] = ()  # Other skills this depends on
    priority: int = 100  # Lower = higher priority (for routing conflicts)


@runtime_checkable
class Skill(Protocol):
    """Protocol that all skills must implement."""

    @property
    def metadata(self) -> SkillMetadata: ...

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the skill with the given context.

        Args:
            context: Input data for the skill.

        Returns:
            Output data from skill execution.
        """
        ...

    def can_handle(self, capability: str) -> bool:
        """Check if this skill can handle the requested capability."""
        ...


@dataclass
class SkillResult:
    """Result of a skill execution."""

    skill_name: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class SkillRegistry:
    """Central registry for discovering, registering, and routing skills.

    The registry supports:
    - Manual registration via register()
    - Auto-discovery from a directory via discover()
    - Capability-based routing via route()
    - Priority-based conflict resolution
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._capability_index: dict[str, list[str]] = {}  # capability → [skill_names]

    def register(self, skill: Skill) -> None:
        """Register a skill in the catalog."""
        meta = skill.metadata
        if meta.name in self._skills:
            logger.warning("skill.duplicate", name=meta.name, action="overwrite")

        self._skills[meta.name] = skill
        # Index capabilities for fast routing
        for cap in meta.capabilities:
            cap_lower = cap.lower()
            if cap_lower not in self._capability_index:
                self._capability_index[cap_lower] = []
            if meta.name not in self._capability_index[cap_lower]:
                self._capability_index[cap_lower].append(meta.name)

        logger.info(
            "skill.registered",
            name=meta.name,
            version=meta.version,
            category=meta.category.value,
            capabilities=len(meta.capabilities),
        )

    def unregister(self, name: str) -> bool:
        """Remove a skill from the registry."""
        if name not in self._skills:
            return False
        skill = self._skills.pop(name)
        # Clean up capability index
        for cap in skill.metadata.capabilities:
            cap_lower = cap.lower()
            if cap_lower in self._capability_index:
                self._capability_index[cap_lower] = [
                    n for n in self._capability_index[cap_lower] if n != name
                ]
        logger.info("skill.unregistered", name=name)
        return True

    def get(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def route(self, capability: str) -> Skill | None:
        """Find the best skill for a given capability.

        Routes by matching capability strings and resolving conflicts
        by priority (lower number = higher priority).
        """
        cap_lower = capability.lower()

        # Exact match
        if cap_lower in self._capability_index:
            candidates = self._capability_index[cap_lower]
        else:
            # Fuzzy match — find skills whose capabilities contain the query
            candidates = []
            for indexed_cap, skill_names in self._capability_index.items():
                if cap_lower in indexed_cap or indexed_cap in cap_lower:
                    candidates.extend(skill_names)
            candidates = list(dict.fromkeys(candidates))  # dedupe, preserve order

        if not candidates:
            logger.debug("skill.route.no_match", capability=capability)
            return None

        # Sort by priority (lower = higher priority)
        candidates_with_priority = [
            (self._skills[name].metadata.priority, name)
            for name in candidates
            if name in self._skills
        ]
        candidates_with_priority.sort()

        best_name = candidates_with_priority[0][1]
        logger.info("skill.route.matched", capability=capability, skill=best_name)
        return self._skills[best_name]

    def route_all(self, capability: str) -> list[Skill]:
        """Find all skills that can handle a capability, sorted by priority."""
        cap_lower = capability.lower()
        candidates = []

        for indexed_cap, skill_names in self._capability_index.items():
            if cap_lower in indexed_cap or indexed_cap in cap_lower:
                candidates.extend(skill_names)

        candidates = list(dict.fromkeys(candidates))
        skills = [
            self._skills[name]
            for name in candidates
            if name in self._skills
        ]
        skills.sort(key=lambda s: s.metadata.priority)
        return skills

    def execute(self, name: str, context: dict[str, Any]) -> SkillResult:
        """Execute a skill by name with the given context."""
        import time

        skill = self._skills.get(name)
        if not skill:
            return SkillResult(
                skill_name=name,
                success=False,
                error=f"Skill '{name}' not found in registry",
            )

        start = time.perf_counter()
        try:
            output = skill.execute(context)
            duration = (time.perf_counter() - start) * 1000
            logger.info("skill.executed", name=name, duration_ms=f"{duration:.1f}")
            return SkillResult(
                skill_name=name,
                success=True,
                output=output,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            logger.error("skill.execute_error", name=name, error=str(e))
            return SkillResult(
                skill_name=name,
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def list_skills(self) -> list[SkillMetadata]:
        """Return metadata for all registered skills."""
        return [s.metadata for s in self._skills.values()]

    def list_by_category(self, category: SkillCategory) -> list[SkillMetadata]:
        """Return skills filtered by category."""
        return [
            s.metadata
            for s in self._skills.values()
            if s.metadata.category == category
        ]

    def list_capabilities(self) -> list[str]:
        """Return all registered capabilities."""
        return sorted(self._capability_index.keys())

    @property
    def count(self) -> int:
        """Number of registered skills."""
        return len(self._skills)

    def discover(self, directory: Path) -> int:
        """Auto-discover and register skills from a directory.

        Scans Python modules in the directory for classes implementing
        the Skill protocol and registers them.

        Returns:
            Number of skills discovered and registered.
        """
        if not directory.exists():
            logger.warning("skill.discover.dir_missing", path=str(directory))
            return 0

        registered = 0
        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            try:
                # Build importable module path
                rel_parts = py_file.relative_to(Path.cwd()).with_suffix("").parts
                module_path = ".".join(rel_parts)
                module = importlib.import_module(module_path)

                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    if isinstance(obj, type) and issubclass(obj, Skill) and obj is not Skill:
                        try:
                            instance = obj()
                            if isinstance(instance, Skill):
                                self.register(instance)
                                registered += 1
                        except Exception as e:
                            logger.warning(
                                "skill.discover.instantiate_failed",
                                cls=_name,
                                error=str(e),
                            )
            except Exception as e:
                logger.warning(
                    "skill.discover.import_failed",
                    module=module_name,
                    error=str(e),
                )

        logger.info("skill.discover.complete", directory=str(directory), registered=registered)
        return registered


# ───────────────── Built-in Skills ─────────────────


class GovernanceSkill:
    """Built-in skill for governance policy evaluation."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="governance-policy",
            version="1.0.0",
            description="Evaluates architecture plans against 20 enterprise governance policies",
            category=SkillCategory.GOVERNANCE,
            capabilities=(
                "governance_check",
                "policy_evaluation",
                "compliance_validation",
                "security_review",
                "naming_validation",
                "tagging_validation",
            ),
            input_types=("IntentSpec", "PlanOutput"),
            output_types=("GovernanceReport",),
            priority=10,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent

        spec = context.get("spec")
        plan = context.get("plan")
        config = context.get("config")

        if not spec or not plan:
            return {"error": "Missing spec or plan in context"}

        reviewer = GovernanceReviewerAgent(config)
        report = reviewer.validate_plan(spec, plan)
        return {"report": report, "status": report.status}


class WAFSkill:
    """Built-in skill for Azure Well-Architected Framework assessment."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="waf-assessment",
            version="1.0.0",
            description="Azure Well-Architected Framework 5-pillar assessment with 26 principles",
            category=SkillCategory.COMPLIANCE,
            capabilities=(
                "waf_assessment",
                "well_architected",
                "reliability_check",
                "security_pillar",
                "cost_optimization",
                "operational_excellence",
                "performance_efficiency",
            ),
            input_types=("IntentSpec", "PlanOutput", "GovernanceReport"),
            output_types=("WAFAlignmentReport",),
            dependencies=("governance-policy",),
            priority=20,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent

        spec = context.get("spec")
        plan = context.get("plan")
        gov_report = context.get("governance_report")
        config = context.get("config")

        if not all([spec, plan, gov_report]):
            return {"error": "Missing spec, plan, or governance_report"}

        reviewer = GovernanceReviewerAgent(config)
        waf_report = reviewer.assess_waf(spec, plan, gov_report)
        return {"waf_report": waf_report, "coverage_pct": waf_report.coverage_pct}


class ThreatModelSkill:
    """Built-in skill for STRIDE threat modeling."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="threat-modeling",
            version="1.0.0",
            description="STRIDE threat modeling for Azure architectures",
            category=SkillCategory.SECURITY,
            capabilities=(
                "threat_modeling",
                "stride_analysis",
                "security_assessment",
                "risk_analysis",
            ),
            input_types=("IntentSpec",),
            output_types=("list[ThreatEntry]",),
            priority=30,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.agents.architecture_planner import ArchitecturePlannerAgent

        spec = context.get("spec")
        config = context.get("config")

        if not spec:
            return {"error": "Missing spec in context"}

        planner = ArchitecturePlannerAgent(config)
        plan = planner.plan(spec)
        return {"threats": plan.threat_model, "count": len(plan.threat_model)}


class NamingSkill:
    """Built-in skill for Azure CAF naming conventions."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="naming-conventions",
            version="1.0.0",
            description="Azure Cloud Adoption Framework naming conventions (20 resource types, 34 regions)",
            category=SkillCategory.GOVERNANCE,
            capabilities=(
                "naming_convention",
                "caf_naming",
                "resource_naming",
            ),
            input_types=("IntentSpec",),
            output_types=("dict",),
            priority=50,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.standards.naming import NamingEngine, ResourceType

        spec = context.get("spec")
        if not spec:
            return {"error": "Missing spec in context"}

        engine = NamingEngine(
            workload=spec.project_name,
            environment=spec.environment or "dev",
            region=spec.azure_region or "eastus2",
        )
        names = {
            rt.value: engine.name(rt) for rt in ResourceType
        }
        return {"names": names, "count": len(names)}


class TaggingSkill:
    """Built-in skill for enterprise tagging standards."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="tagging-standards",
            version="1.0.0",
            description="Enterprise tagging standard (7 required + 5 optional tags)",
            category=SkillCategory.GOVERNANCE,
            capabilities=(
                "tagging_standard",
                "resource_tagging",
                "tag_validation",
            ),
            input_types=("IntentSpec",),
            output_types=("dict",),
            priority=50,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.standards.tagging import TaggingEngine

        spec = context.get("spec")
        if not spec:
            return {"error": "Missing spec in context"}

        engine = TaggingEngine(
            project_name=spec.project_name,
            environment=spec.environment or "dev",
            owner="platform-team",
        )
        tags = engine.required_tags()
        return {"tags": tags, "required_count": len(tags)}


class BicepGenerationSkill:
    """Built-in skill for Bicep IaC generation."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="bicep-generation",
            version="1.0.0",
            description="Generate Azure Bicep infrastructure-as-code (7 modules + parameters)",
            category=SkillCategory.GENERATION,
            capabilities=(
                "bicep_generation",
                "infrastructure_code",
                "iac_generation",
                "azure_bicep",
            ),
            input_types=("IntentSpec", "PlanOutput"),
            output_types=("dict[str, str]",),
            priority=10,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.generators.bicep_generator import BicepGenerator

        spec = context.get("spec")
        plan = context.get("plan")
        if not spec or not plan:
            return {"error": "Missing spec or plan"}

        generator = BicepGenerator()
        files = generator.generate(spec, plan)
        return {"files": files, "file_count": len(files)}


class CICDSkill:
    """Built-in skill for CI/CD workflow generation."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="cicd-generation",
            version="1.0.0",
            description="Generate GitHub Actions CI/CD workflows with OIDC auth",
            category=SkillCategory.GENERATION,
            capabilities=(
                "cicd_generation",
                "github_actions",
                "pipeline_generation",
                "workflow_generation",
            ),
            input_types=("IntentSpec",),
            output_types=("dict[str, str]",),
            priority=20,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.generators.cicd_generator import CICDGenerator

        spec = context.get("spec")
        if not spec:
            return {"error": "Missing spec"}

        generator = CICDGenerator()
        files = generator.generate(spec)
        return {"files": files, "file_count": len(files)}


class AppScaffoldSkill:
    """Built-in skill for application code generation."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="app-scaffold",
            version="1.0.0",
            description="Generate FastAPI application scaffold with Docker and managed identity",
            category=SkillCategory.GENERATION,
            capabilities=(
                "app_generation",
                "fastapi_scaffold",
                "dockerfile_generation",
                "application_code",
            ),
            input_types=("IntentSpec",),
            output_types=("dict[str, str]",),
            priority=20,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.generators.app_generator import AppGenerator

        spec = context.get("spec")
        if not spec:
            return {"error": "Missing spec"}

        generator = AppGenerator()
        files = generator.generate(spec)
        return {"files": files, "file_count": len(files)}


class DocumentationSkill:
    """Built-in skill for documentation generation."""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="documentation",
            version="1.0.0",
            description="Generate project documentation (plan, security, deployment, RAI, WAF report)",
            category=SkillCategory.DOCUMENTATION,
            capabilities=(
                "doc_generation",
                "documentation",
                "plan_docs",
                "security_docs",
                "rai_notes",
            ),
            input_types=("IntentSpec", "PlanOutput", "GovernanceReport", "WAFAlignmentReport"),
            output_types=("dict[str, str]",),
            priority=30,
        )

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self.metadata.capabilities}

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.orchestrator.generators.docs_generator import DocsGenerator

        spec = context.get("spec")
        plan = context.get("plan")
        gov_report = context.get("governance_report")
        waf_report = context.get("waf_report")

        if not spec or not plan:
            return {"error": "Missing spec or plan"}

        generator = DocsGenerator()
        files = generator.generate(spec, plan, governance=gov_report, waf_report=waf_report)
        return {"files": files, "file_count": len(files)}


def create_default_registry() -> SkillRegistry:
    """Create a skill registry with all built-in skills pre-registered.

    Returns:
        A fully populated SkillRegistry ready for use.
    """
    registry = SkillRegistry()

    # Register all built-in skills
    built_ins: list[Skill] = [
        GovernanceSkill(),  # type: ignore[list-item]
        WAFSkill(),  # type: ignore[list-item]
        ThreatModelSkill(),  # type: ignore[list-item]
        NamingSkill(),  # type: ignore[list-item]
        TaggingSkill(),  # type: ignore[list-item]
        BicepGenerationSkill(),  # type: ignore[list-item]
        CICDSkill(),  # type: ignore[list-item]
        AppScaffoldSkill(),  # type: ignore[list-item]
        DocumentationSkill(),  # type: ignore[list-item]
    ]

    for skill in built_ins:
        registry.register(skill)

    logger.info("skill.registry.initialized", skill_count=registry.count)
    return registry
