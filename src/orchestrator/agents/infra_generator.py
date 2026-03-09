"""Infrastructure Generator Agent.

Takes an IntentSpec and PlanOutput and produces a complete, deployable
infrastructure scaffold including:
    - Bicep modules for all Azure resources (CAF naming + enterprise tags)
    - GitHub Actions CI/CD workflows
    - Application code scaffold
    - Documentation (including naming & tagging standards)

This is the final production agent in the chain after governance approval.
"""

from __future__ import annotations

from pathlib import Path

from src.orchestrator.config import AppConfig
from src.orchestrator.intent_schema import IntentSpec, PlanOutput
from src.orchestrator.logging import get_logger
from src.orchestrator.standards.config import EnterpriseStandardsConfig

logger = get_logger(__name__)


class InfrastructureGeneratorAgent:
    """Generates complete infrastructure scaffold from plan.

    This agent coordinates all sub-generators (Bicep, CI/CD, app, docs)
    to produce a coherent, deployable output. Enterprise standards
    (naming, tagging, governance) are applied via EnterpriseStandardsConfig.
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        # Load enterprise standards from standards.yaml if available
        standards_path = Path("standards.yaml")
        self.standards = EnterpriseStandardsConfig.load(standards_path)

    def generate(
        self,
        spec: IntentSpec,
        plan: PlanOutput,
        gov_report: object | None = None,
        waf_report: object | None = None,
    ) -> dict[str, str]:
        """Generate all scaffold files.

        Args:
            spec: The validated intent specification.
            plan: The approved architecture plan.
            gov_report: Optional governance report.
            waf_report: Optional WAF alignment report.

        Returns:
            Dictionary mapping file paths (relative) to file contents.
        """
        logger.info("infrastructure_generator.start", project=spec.project_name)

        files: dict[str, str] = {}

        # Import generators
        from src.orchestrator.generators.alert_generator import AlertGenerator
        from src.orchestrator.generators.app_generator import AppGenerator
        from src.orchestrator.generators.bicep_generator import BicepGenerator
        from src.orchestrator.generators.cicd_generator import CICDGenerator
        from src.orchestrator.generators.cost_estimator import CostEstimator
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.generators.test_generator import TestGenerator

        # Generate all artifacts with enterprise standards
        bicep_gen = BicepGenerator(standards=self.standards)
        cicd_gen = CICDGenerator()
        app_gen = AppGenerator()
        docs_gen = DocsGenerator()
        test_gen = TestGenerator()
        alert_gen = AlertGenerator()
        cost_est = CostEstimator()

        files.update(bicep_gen.generate(spec, plan))
        files.update(cicd_gen.generate(spec))
        files.update(app_gen.generate(spec))
        files.update(docs_gen.generate(spec, plan, governance=gov_report, waf_report=waf_report))
        files.update(test_gen.generate(spec))
        files.update(alert_gen.generate(spec))

        # Cost estimate report
        estimate = cost_est.estimate(spec, plan)
        files["docs/cost-estimate.md"] = estimate.to_markdown()

        logger.info("infrastructure_generator.complete", file_count=len(files))
        return files
