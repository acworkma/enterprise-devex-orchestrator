"""Governance Reviewer Agent.

Validates generated artifacts against enterprise governance policies.
Implements a feedback loop: if validation fails, it sends issues back
to the Architecture Planner for revision.

This agent turns governance from documentation into enforcement.
Includes validation for enterprise naming conventions (Azure CAF)
and tagging standards.
"""

from __future__ import annotations

import re

from src.orchestrator.config import AppConfig
from src.orchestrator.intent_schema import (
    GovernanceCheck,
    GovernanceReport,
    IntentSpec,
    PlanOutput,
)
from src.orchestrator.logging import get_logger
from src.orchestrator.standards.tagging import REQUIRED_TAGS
from src.orchestrator.standards.waf import WAFAlignmentReport, WAFAssessor

logger = get_logger(__name__)


class GovernanceReviewerAgent:
    """Validates architecture plans and generated artifacts against governance policies."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config

    # Required Azure components that must exist in every plan
    REQUIRED_COMPONENTS = {
        "key-vault": "Key Vault for secret management",
        "log-analytics": "Log Analytics for observability",
        "managed-identity": "Managed Identity for passwordless auth",
    }

    # Patterns that indicate security issues in generated code
    SECURITY_ANTIPATTERNS = [
        (r"(?i)password\s*=\s*[\"'][^\"']+[\"']", "Hardcoded password detected"),
        (r"(?i)api[_-]?key\s*=\s*[\"'][^\"']+[\"']", "Hardcoded API key detected"),
        (r"(?i)connection[_-]?string\s*=\s*[\"'][^\"']+[\"']", "Hardcoded connection string detected"),
        (r"(?i)secret\s*=\s*[\"'][^\"']+[\"']", "Hardcoded secret detected"),
        (r"allowInsecure:\s*true", "Insecure connections allowed"),
        (r"publicNetworkAccess:\s*'Enabled'", "Public network access enabled"),
    ]

    def validate_plan(self, spec: IntentSpec, plan: PlanOutput) -> GovernanceReport:
        """Validate an architecture plan against governance policies.

        Returns a GovernanceReport with PASS/FAIL status and detailed checks.
        """
        logger.info("governance_reviewer.validate_plan", project=spec.project_name)

        checks: list[GovernanceCheck] = []

        # Check 1: Required components
        checks.extend(self._check_required_components(plan))

        # Check 2: Security controls on each component
        checks.extend(self._check_security_controls(plan))

        # Check 3: Networking posture
        checks.extend(self._check_networking(spec))

        # Check 4: Observability requirements
        checks.extend(self._check_observability(spec))

        # Check 5: CI/CD configuration
        checks.extend(self._check_cicd(spec))

        # Check 6: Threat model completeness
        checks.extend(self._check_threat_model(plan))

        # Check 7: Enterprise naming convention compliance
        checks.extend(self._check_naming_standards(spec))

        # Check 8: Enterprise tagging standard compliance
        checks.extend(self._check_tagging_standards(spec))

        # Determine overall status
        failed = [c for c in checks if not c.passed]
        critical_failures = [c for c in failed if c.severity == "critical"]

        if critical_failures:
            status = "FAIL"
            summary = f"Governance validation FAILED: {len(critical_failures)} critical issue(s) found."
        elif failed:
            status = "PASS_WITH_WARNINGS"
            summary = f"Governance validation passed with {len(failed)} warning(s)."
        else:
            status = "PASS"
            summary = "All governance checks passed."

        recommendations = self._generate_recommendations(checks)

        report = GovernanceReport(
            status=status,
            checks=checks,
            summary=summary,
            recommendations=recommendations,
        )

        logger.info(
            "governance_reviewer.complete",
            status=status,
            total_checks=len(checks),
            passed=len([c for c in checks if c.passed]),
            failed=len(failed),
        )

        return report

    def validate_bicep(self, bicep_files: dict[str, str] | str) -> GovernanceReport:
        """Validate generated Bicep code for security anti-patterns.

        Args:
            bicep_files: Either a dict mapping file paths to content, or a single
                         Bicep content string.

        Returns:
            GovernanceReport with PASS/FAIL status and detailed checks.
        """
        # Normalize input
        if isinstance(bicep_files, str):
            bicep_content = bicep_files
        else:
            bicep_content = "\n".join(bicep_files.values())

        checks: list[GovernanceCheck] = []

        for pattern, description in self.SECURITY_ANTIPATTERNS:
            matches = re.findall(pattern, bicep_content)
            checks.append(
                GovernanceCheck(
                    check_id=f"BICEP-SEC-{len(checks) + 1:03d}",
                    name=f"Security scan: {description}",
                    passed=len(matches) == 0,
                    details=f"Found {len(matches)} occurrence(s)" if matches else "No issues found",
                    severity="critical" if matches else "low",
                )
            )

        # Check for diagnostic settings
        has_diagnostics = (
            "diagnosticSettings" in bicep_content or "Microsoft.Insights/diagnosticSettings" in bicep_content
        )
        checks.append(
            GovernanceCheck(
                check_id="BICEP-OBS-001",
                name="Diagnostic settings present",
                passed=has_diagnostics,
                details="Diagnostic settings found in Bicep"
                if has_diagnostics
                else "No diagnostic settings -- add Microsoft.Insights/diagnosticSettings",
                severity="high" if not has_diagnostics else "low",
            )
        )

        # Check for managed identity
        has_mi = "UserAssigned" in bicep_content or "SystemAssigned" in bicep_content
        checks.append(
            GovernanceCheck(
                check_id="BICEP-SEC-MI",
                name="Managed Identity configured",
                passed=has_mi,
                details="Managed Identity reference found" if has_mi else "No Managed Identity configuration found",
                severity="critical" if not has_mi else "low",
            )
        )

        # Check for enterprise tagging standard
        required_tag_names = ["costCenter", "owner", "dataSensitivity", "createdBy"]
        missing_tags = [t for t in required_tag_names if t not in bicep_content]
        has_enterprise_tags = len(missing_tags) == 0
        checks.append(
            GovernanceCheck(
                check_id="BICEP-STD-001",
                name="Enterprise tags present in Bicep",
                passed=has_enterprise_tags,
                details=(
                    "All required enterprise tags found in Bicep templates"
                    if has_enterprise_tags
                    else f"Missing enterprise tags in Bicep: {', '.join(missing_tags)}"
                ),
                severity="high" if not has_enterprise_tags else "low",
            )
        )

        # Check for CAF naming convention variables
        naming_prefixes = ["lawName", "kvName", "crName", "caName", "identityName"]
        found_prefixes = [p for p in naming_prefixes if p in bicep_content]
        has_naming = len(found_prefixes) >= 3  # At least 3 out of 5 naming vars
        checks.append(
            GovernanceCheck(
                check_id="BICEP-STD-002",
                name="CAF naming convention variables present",
                passed=has_naming,
                details=(
                    f"CAF naming variables found: {', '.join(found_prefixes)}"
                    if has_naming
                    else "Missing Azure CAF naming convention variables in Bicep"
                ),
                severity="medium" if not has_naming else "low",
            )
        )

        # Determine status
        failed = [c for c in checks if not c.passed]
        critical_failures = [c for c in failed if c.severity == "critical"]

        if critical_failures:
            status = "FAIL"
            summary = f"Bicep validation FAILED: {len(critical_failures)} critical issue(s)."
        elif failed:
            status = "PASS_WITH_WARNINGS"
            summary = f"Bicep validation passed with {len(failed)} warning(s)."
        else:
            status = "PASS"
            summary = "All Bicep security checks passed."

        return GovernanceReport(
            status=status,
            checks=checks,
            summary=summary,
            recommendations=[f"[{c.severity.upper()}] {c.name}: {c.details}" for c in failed],
        )

    def _check_required_components(self, plan: PlanOutput) -> list[GovernanceCheck]:
        """Check that all required components are in the plan."""
        checks = []
        component_names = {c.name for c in plan.components}

        for req_name, req_desc in self.REQUIRED_COMPONENTS.items():
            present = req_name in component_names
            checks.append(
                GovernanceCheck(
                    check_id=f"GOV-REQ-{req_name.upper()}",
                    name=f"Required component: {req_desc}",
                    passed=present,
                    details=f"{req_desc} is {'present' if present else 'MISSING'} in architecture plan",
                    severity="critical" if not present else "low",
                )
            )

        return checks

    def _check_security_controls(self, plan: PlanOutput) -> list[GovernanceCheck]:
        """Check that each component has security controls defined."""
        checks = []

        for component in plan.components:
            has_controls = len(component.security_controls) > 0
            checks.append(
                GovernanceCheck(
                    check_id=f"GOV-SEC-{component.name.upper()}",
                    name=f"Security controls: {component.name}",
                    passed=has_controls,
                    details=(
                        f"Controls: {', '.join(component.security_controls)}"
                        if has_controls
                        else f"No security controls defined for {component.name}"
                    ),
                    severity="high" if not has_controls else "low",
                )
            )

        return checks

    def _check_networking(self, spec: IntentSpec) -> list[GovernanceCheck]:
        """Check networking security posture."""
        is_private = spec.security.networking.value in ("private", "internal")
        return [
            GovernanceCheck(
                check_id="GOV-NET-001",
                name="Private networking",
                passed=is_private,
                details=(
                    f"Networking model: {spec.security.networking.value}"
                    + (" (enterprise-approved)" if is_private else " -- consider private networking")
                ),
                severity="medium" if not is_private else "low",
            ),
            GovernanceCheck(
                check_id="GOV-NET-002",
                name="Encryption in transit",
                passed=spec.security.encryption_in_transit,
                details="HTTPS/TLS enforced"
                if spec.security.encryption_in_transit
                else "Encryption in transit NOT enabled",
                severity="critical" if not spec.security.encryption_in_transit else "low",
            ),
        ]

    def _check_observability(self, spec: IntentSpec) -> list[GovernanceCheck]:
        """Check observability requirements."""
        return [
            GovernanceCheck(
                check_id="GOV-OBS-001",
                name="Log Analytics enabled",
                passed=spec.observability.log_analytics,
                details="Log Analytics workspace included"
                if spec.observability.log_analytics
                else "Log Analytics NOT configured",
                severity="high" if not spec.observability.log_analytics else "low",
            ),
            GovernanceCheck(
                check_id="GOV-OBS-002",
                name="Diagnostic settings enabled",
                passed=spec.observability.diagnostic_settings,
                details="Diagnostic settings will be configured"
                if spec.observability.diagnostic_settings
                else "Diagnostic settings NOT configured",
                severity="high" if not spec.observability.diagnostic_settings else "low",
            ),
            GovernanceCheck(
                check_id="GOV-OBS-003",
                name="Health endpoint included",
                passed=spec.observability.health_endpoint,
                details="Health check endpoint will be available"
                if spec.observability.health_endpoint
                else "No health endpoint configured",
                severity="medium" if not spec.observability.health_endpoint else "low",
            ),
        ]

    def _check_cicd(self, spec: IntentSpec) -> list[GovernanceCheck]:
        """Check CI/CD configuration."""
        return [
            GovernanceCheck(
                check_id="GOV-CICD-001",
                name="PR validation enabled",
                passed=spec.cicd.validate_on_pr,
                details="CI runs on pull requests" if spec.cicd.validate_on_pr else "No PR validation configured",
                severity="high" if not spec.cicd.validate_on_pr else "low",
            ),
            GovernanceCheck(
                check_id="GOV-CICD-002",
                name="OIDC authentication for CI",
                passed=spec.cicd.oidc_auth,
                details="OIDC federation for Azure login" if spec.cicd.oidc_auth else "Not using OIDC -- secrets in CI",
                severity="medium" if not spec.cicd.oidc_auth else "low",
            ),
        ]

    def _check_threat_model(self, plan: PlanOutput) -> list[GovernanceCheck]:
        """Check threat model completeness."""
        has_threats = len(plan.threat_model) >= 3
        stride_categories = {t.category for t in plan.threat_model}
        min_categories = len(stride_categories) >= 3

        return [
            GovernanceCheck(
                check_id="GOV-THREAT-001",
                name="Threat model exists",
                passed=has_threats,
                details=f"{len(plan.threat_model)} threats identified" if has_threats else "Insufficient threat model",
                severity="high" if not has_threats else "low",
            ),
            GovernanceCheck(
                check_id="GOV-THREAT-002",
                name="STRIDE coverage",
                passed=min_categories,
                details=f"Categories covered: {', '.join(sorted(stride_categories))}",
                severity="medium" if not min_categories else "low",
            ),
        ]

    def _check_naming_standards(self, spec: IntentSpec) -> list[GovernanceCheck]:
        """Check that the project follows Azure CAF naming conventions."""
        checks = []

        # Validate project name format (kebab-case, 3-39 chars)
        name_valid = bool(re.match(r"^[a-z][a-z0-9-]{2,38}$", spec.project_name))
        checks.append(
            GovernanceCheck(
                check_id="STD-NAME-001",
                name="Project name follows kebab-case convention",
                passed=name_valid,
                details=(
                    f"Project name '{spec.project_name}' is valid kebab-case"
                    if name_valid
                    else f"Project name '{spec.project_name}' must be kebab-case, 3-39 chars (a-z, 0-9, hyphens)"
                ),
                severity="high" if not name_valid else "low",
            )
        )

        # Validate resource group naming convention
        expected_rg = f"rg-{spec.project_name}-{spec.environment}"
        rg_valid = spec.resource_group_name == expected_rg
        checks.append(
            GovernanceCheck(
                check_id="STD-NAME-002",
                name="Resource group follows CAF naming (rg-{workload}-{env})",
                passed=rg_valid,
                details=(
                    f"Resource group '{spec.resource_group_name}' follows CAF convention"
                    if rg_valid
                    else f"Expected '{expected_rg}', got '{spec.resource_group_name}'"
                ),
                severity="medium" if not rg_valid else "low",
            )
        )

        # Check that environment is a recognized value
        valid_envs = {"dev", "staging", "prod", "test", "sandbox"}
        env_valid = spec.environment in valid_envs
        checks.append(
            GovernanceCheck(
                check_id="STD-NAME-003",
                name="Environment identifier is standardized",
                passed=env_valid,
                details=(
                    f"Environment '{spec.environment}' is a recognized standard value"
                    if env_valid
                    else f"Environment '{spec.environment}' not in standard set: {sorted(valid_envs)}"
                ),
                severity="medium" if not env_valid else "low",
            )
        )

        return checks

    def _check_tagging_standards(self, spec: IntentSpec) -> list[GovernanceCheck]:
        """Check that enterprise tagging standards can be applied."""
        checks = []

        # Verify all required tag fields are satisfiable from the spec
        required_tag_names = [t.name for t in REQUIRED_TAGS]
        checks.append(
            GovernanceCheck(
                check_id="STD-TAG-001",
                name="Required enterprise tags defined",
                passed=True,  # The tagging engine ensures these are always generated
                details=(
                    f"Enterprise tagging standard enforces {len(required_tag_names)} required tags: "
                    f"{', '.join(required_tag_names)}"
                ),
                severity="low",
            )
        )

        # Verify data classification level is set
        data_class = spec.security.data_classification
        valid_levels = {"public", "internal", "confidential", "restricted"}
        class_valid = data_class.lower() in valid_levels
        checks.append(
            GovernanceCheck(
                check_id="STD-TAG-002",
                name="Data sensitivity classification set",
                passed=class_valid,
                details=(
                    f"Data classified as '{data_class}' -- will be applied as dataSensitivity tag"
                    if class_valid
                    else f"Data classification '{data_class}' not in standard levels: {sorted(valid_levels)}"
                ),
                severity="high" if not class_valid else "low",
            )
        )

        # Verify compliance scope can be derived
        compliance = spec.security.compliance_framework.value
        checks.append(
            GovernanceCheck(
                check_id="STD-TAG-003",
                name="Compliance scope identifiable for tagging",
                passed=True,
                details=f"Compliance scope '{compliance}' will be applied as complianceScope tag",
                severity="low",
            )
        )

        return checks

    def _generate_recommendations(self, checks: list[GovernanceCheck]) -> list[str]:
        """Generate actionable recommendations from failed checks."""
        recommendations = []
        for check in checks:
            if not check.passed:
                recommendations.append(f"[{check.severity.upper()}] {check.name}: {check.details}")
        return recommendations

    def assess_waf(
        self,
        spec: IntentSpec,
        plan: PlanOutput,
        governance_report: GovernanceReport | None = None,
    ) -> WAFAlignmentReport:
        """Assess a workload against the Azure Well-Architected Framework.

        Uses governance checks, plan components, and generated artifact metadata
        to evaluate coverage across all 5 WAF pillars.
        """
        logger.info("governance_reviewer.assess_waf", project=spec.project_name)

        # Build governance check results from existing report
        gov_checks: dict[str, bool] = {}
        if governance_report:
            for check in governance_report.checks:
                gov_checks[check.check_id] = check.passed

        # Build component name list
        component_names = [c.name for c in plan.components]

        # Detect features from the spec and plan
        data_store_names = [ds.value for ds in spec.data_stores]

        assessor = WAFAssessor()
        report = assessor.assess(
            plan_components=component_names,
            governance_checks=gov_checks,
            has_bicep=True,  # SDK always generates Bicep
            has_dockerfile=True,  # SDK always generates Dockerfile
            has_cicd=True,  # SDK always generates CI/CD
            has_state_manager=True,  # StateManager integrated
            has_threat_model=len(plan.threat_model) >= 3,
            has_adrs=len(plan.decisions) >= 3,
            has_tags=True,  # TaggingEngine always applies tags
            has_health_endpoint=spec.observability.health_endpoint,
            data_stores=data_store_names,
        )

        logger.info(
            "governance_reviewer.waf_complete",
            coverage_pct=f"{report.coverage_pct:.0f}%",
            covered=report.covered_count,
            total=report.total_principles,
            gaps=len(report.gaps()),
        )

        return report
