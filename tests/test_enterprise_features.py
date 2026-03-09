"""Tests for enterprise intent features.

Covers:
- IntentFileResult enterprise section parsing
- Enterprise sections filled tracking
- Completeness percentage calculation
- _parse_enterprise_sections with alias headings
- _strip_comments helper
- full_intent property with enterprise sections
- generate_improvement_suggestions method
- _improvement_suggestions_md output
- generate_intent_template enterprise sections
- generate_upgrade_template with improvement suggestions
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from src.orchestrator.intent_file import (
    IntentFileParser,
    IntentFileResult,
    generate_intent_template,
    generate_upgrade_template,
)


# -- IntentFileResult dataclass tests --------------------------


class TestIntentFileResultEnterpriseSections(unittest.TestCase):
    """Test the IntentFileResult enterprise section properties."""

    def test_enterprise_sections_filled_empty(self) -> None:
        """All sections should be False when no content is set."""
        result = IntentFileResult()
        filled = result.enterprise_sections_filled
        assert len(filled) == 9
        assert all(v is False for v in filled.values())

    def test_enterprise_sections_filled_all(self) -> None:
        """All sections should be True when all have content."""
        result = IntentFileResult(
            problem_statement="Problem here",
            business_goals="Goals here",
            target_users="Users here",
            functional_requirements="Features here",
            scalability_requirements="Scale here",
            security_compliance="Security here",
            performance_requirements="Perf here",
            integration_requirements="Integrations here",
            acceptance_criteria="Criteria here",
        )
        filled = result.enterprise_sections_filled
        assert all(v is True for v in filled.values())

    def test_enterprise_sections_filled_partial(self) -> None:
        """Only filled sections should be True."""
        result = IntentFileResult(
            problem_statement="Problem here",
            business_goals="Goals here",
        )
        filled = result.enterprise_sections_filled
        assert filled["problem_statement"] is True
        assert filled["business_goals"] is True
        assert filled["target_users"] is False
        assert filled["functional_requirements"] is False

    def test_completeness_pct_zero(self) -> None:
        """Completeness should be 0% when nothing is filled."""
        result = IntentFileResult()
        assert result.completeness_pct == 0.0

    def test_completeness_pct_full(self) -> None:
        """Completeness should be 100% when all 9 sections are filled."""
        result = IntentFileResult(
            problem_statement="P",
            business_goals="G",
            target_users="U",
            functional_requirements="F",
            scalability_requirements="S",
            security_compliance="SC",
            performance_requirements="PR",
            integration_requirements="IR",
            acceptance_criteria="AC",
        )
        assert result.completeness_pct == 100.0

    def test_completeness_pct_partial(self) -> None:
        """Completeness should reflect the fraction of filled sections."""
        result = IntentFileResult(
            problem_statement="P",
            business_goals="G",
            target_users="U",
        )
        # 3 of 9 = 33.33...%
        pct = result.completeness_pct
        assert 33.0 < pct < 34.0

    def test_full_intent_includes_enterprise_sections(self) -> None:
        """full_intent should include all enterprise sections."""
        result = IntentFileResult(
            intent="Executive summary.",
            problem_statement="Problem text",
            business_goals="Goal text",
            target_users="User text",
            functional_requirements="Feature text",
            acceptance_criteria="Criteria text",
        )
        full = result.full_intent
        assert "Executive summary." in full
        assert "Problem Statement: Problem text" in full
        assert "Business Goals: Goal text" in full
        assert "Target Users: User text" in full
        assert "Functional Requirements: Feature text" in full
        assert "Acceptance Criteria: Criteria text" in full

    def test_full_intent_skips_empty_sections(self) -> None:
        """full_intent should not include labels for empty sections."""
        result = IntentFileResult(
            intent="Summary",
            problem_statement="Problem",
        )
        full = result.full_intent
        assert "Problem Statement:" in full
        assert "Business Goals:" not in full
        assert "Target Users:" not in full

    def test_full_intent_includes_config(self) -> None:
        """full_intent should append configuration as natural language."""
        result = IntentFileResult(
            intent="Summary",
            config={"app_type": "api", "region": "eastus2"},
        )
        full = result.full_intent
        assert "Application type: api" in full
        assert "Azure region: eastus2" in full


# -- IntentFileParser enterprise section parsing ---------------


class TestParseEnterpriseSections(unittest.TestCase):
    """Test parsing enterprise sections from markdown."""

    def setUp(self) -> None:
        self.parser = IntentFileParser()

    def test_parse_all_enterprise_sections(self) -> None:
        """Parser should extract all 9 enterprise sections."""
        md = """# Test Project
> A test project summary.

## Problem Statement
Users cannot manage documents securely.

## Business Goals
Reduce manual processing by 60%.

## Target Users
Internal compliance officers.

## Functional Requirements
Upload, download, and search documents.

## Scalability Requirements
500 concurrent users, 200 RPS.

## Security & Compliance
OAuth 2.0, SOC2 compliance, AES-256 encryption.

## Performance Requirements
p95 latency < 200ms, 99.9% SLA.

## Integration Requirements
Azure AD, legacy CRM via REST.

## Acceptance Criteria
All endpoints return < 300ms under load.

## Configuration
- **App Type**: api
- **Data Stores**: blob, cosmos
"""
        result = self.parser.parse_string(md)

        assert result.problem_statement == "Users cannot manage documents securely."
        assert "60%" in result.business_goals
        assert "compliance officers" in result.target_users
        assert "Upload" in result.functional_requirements
        assert "500 concurrent" in result.scalability_requirements
        assert "SOC2" in result.security_compliance
        assert "200ms" in result.performance_requirements
        assert "legacy CRM" in result.integration_requirements
        assert "300ms" in result.acceptance_criteria
        assert result.completeness_pct == 100.0

    def test_parse_alias_headings(self) -> None:
        """Parser should recognise heading aliases like 'Goals', 'Features'."""
        md = """# Alias Test
> Summary.

## Problem
The core issue.

## Goals
Hit 10K users.

## Personas
Platform engineers.

## Features
Auto-scaling, monitoring.

## Scaling
Horizontal pod autoscaler.

## Security
OAuth2 + RBAC.

## Performance
< 100ms p99.

## Integrations
Datadog, PagerDuty.

## Definition of Done
All smoke tests pass in CI.
"""
        result = self.parser.parse_string(md)

        assert result.problem_statement == "The core issue."
        assert "10K users" in result.business_goals
        assert "Platform engineers" in result.target_users
        assert "Auto-scaling" in result.functional_requirements
        assert "Horizontal" in result.scalability_requirements
        assert "OAuth2" in result.security_compliance
        assert "100ms" in result.performance_requirements
        assert "Datadog" in result.integration_requirements
        assert "smoke tests" in result.acceptance_criteria
        assert result.completeness_pct == 100.0

    def test_strip_comments(self) -> None:
        """Parser should strip HTML comments from section content."""
        md = """# Comment Test
> Summary.

## Problem Statement
<!-- Describe the business problem here -->
Real problem description.

## Business Goals
<!-- List measurable goals -->
Increase revenue by 20%.
"""
        result = self.parser.parse_string(md)

        assert "<!--" not in result.problem_statement
        assert "Real problem description." in result.problem_statement
        assert "<!--" not in result.business_goals
        assert "20%" in result.business_goals

    def test_empty_sections_ignored(self) -> None:
        """Sections with only comments should result in empty fields."""
        md = """# Empty Sections
> Summary.

## Problem Statement
<!-- Fill this in -->

## Business Goals
Real goals here.
"""
        result = self.parser.parse_string(md)

        assert result.problem_statement == ""
        assert result.business_goals == "Real goals here."
        filled = result.enterprise_sections_filled
        assert filled["problem_statement"] is False
        assert filled["business_goals"] is True

    def test_partial_completeness(self) -> None:
        """Completeness should be correct for partially-filled files."""
        md = """# Partial
> Summary.

## Problem Statement
A real problem.

## Functional Requirements
Feature list.

## Acceptance Criteria
Tests pass.
"""
        result = self.parser.parse_string(md)

        assert result.completeness_pct == pytest.approx(33.33, abs=0.1)


# -- _strip_comments unit test --------------------------------


class TestStripComments(unittest.TestCase):
    """Test the _strip_comments static method."""

    def test_single_comment(self) -> None:
        text = "Hello <!-- comment --> world"
        assert IntentFileParser._strip_comments(text) == "Hello  world"

    def test_multiline_comment(self) -> None:
        text = "Before\n<!-- multi\nline\ncomment -->\nAfter"
        result = IntentFileParser._strip_comments(text)
        assert "Before" in result
        assert "After" in result
        assert "<!--" not in result

    def test_no_comments(self) -> None:
        text = "No comments here"
        assert IntentFileParser._strip_comments(text) == "No comments here"

    def test_comment_only(self) -> None:
        text = "<!-- just a comment -->"
        assert IntentFileParser._strip_comments(text) == ""


# -- Template generation tests --------------------------------


class TestEnterpriseTemplate(unittest.TestCase):
    """Test enterprise template generation."""

    def test_template_has_all_enterprise_sections(self) -> None:
        """Generated template should include all 9 enterprise sections."""
        template = generate_intent_template("test-project")

        sections = [
            "## Problem Statement",
            "## Business Goals",
            "## Target Users",
            "## Functional Requirements",
            "## Scalability Requirements",
            "## Security & Compliance",
            "## Performance Requirements",
            "## Integration Requirements",
            "## Acceptance Criteria",
        ]
        for section in sections:
            assert section in template, f"Missing section: {section}"

    def test_template_has_configuration(self) -> None:
        template = generate_intent_template("test-project")
        assert "## Configuration" in template
        assert "App Type" in template
        assert "Data Stores" in template

    def test_template_has_version(self) -> None:
        template = generate_intent_template("test-project")
        assert "## Version" in template
        assert "**Version**: 1" in template

    def test_template_project_name(self) -> None:
        template = generate_intent_template("my-cool-api")
        assert "# my-cool-api" in template

    def test_template_has_guidance_comments(self) -> None:
        """Template should include HTML comment guidance for users."""
        template = generate_intent_template("test-project")
        assert "<!--" in template


class TestUpgradeTemplate(unittest.TestCase):
    """Test upgrade template with improvement suggestions."""

    def test_upgrade_template_version_2(self) -> None:
        template = generate_upgrade_template("test-project", current_version=1, current_intent="Build API")
        assert "**Version**: 2" in template
        assert "**Based On**: 1" in template

    def test_upgrade_template_with_suggestions(self) -> None:
        """Upgrade template should embed improvement suggestions."""
        suggestions = [
            "[Security] Enable WAF",
            "[Performance] Add Redis cache",
            "[WAF/Security] Coverage 60% -- add coverage for: Zero Trust",
        ]
        template = generate_upgrade_template(
            "test-project",
            current_version=1,
            current_intent="Build API",
            improvement_suggestions=suggestions,
        )
        assert "Improvement Suggestions from v1" in template
        assert "Enable WAF" in template
        assert "Add Redis cache" in template
        assert "Zero Trust" in template

    def test_upgrade_template_without_suggestions(self) -> None:
        """Upgrade template without suggestions should still work."""
        template = generate_upgrade_template("test-project", current_version=2, current_intent="Build API v2")
        assert "**Version**: 3" in template
        assert "**Based On**: 2" in template

    def test_upgrade_template_has_enterprise_sections(self) -> None:
        """Upgrade template should still have all enterprise sections."""
        template = generate_upgrade_template("test-project", current_version=1, current_intent="Build API")
        assert "## Problem Statement" in template
        assert "## Business Goals" in template
        assert "## Acceptance Criteria" in template


# -- Improvement Suggestions Engine tests ----------------------


class TestImprovementSuggestions(unittest.TestCase):
    """Test the DocsGenerator improvement suggestions engine."""

    def _make_spec(self, **overrides):
        """Create a minimal IntentSpec for testing."""
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            ComplianceFramework,
            IntentSpec,
            ObservabilityRequirements,
            SecurityRequirements,
        )

        defaults = dict(
            project_name="test-project",
            description="Test project",
            raw_intent="Build a test project",
            app_type=AppType.API,
            data_stores=[],
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=ComplianceFramework.SOC2_GUIDANCE,
            ),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
        )
        defaults.update(overrides)
        return IntentSpec(**defaults)

    def _make_plan(self, components=None, threat_model=None):
        """Create a minimal PlanOutput."""
        from src.orchestrator.intent_schema import PlanOutput

        return PlanOutput(
            title="Test Plan",
            summary="Test summary",
            components=components or [],
            decisions=[],
            threat_model=threat_model or [],
            diagram_mermaid="graph LR; A-->B",
        )

    def test_suggestions_with_no_inputs(self) -> None:
        """Should produce suggestions even with minimal inputs."""
        from src.orchestrator.generators.docs_generator import DocsGenerator

        gen = DocsGenerator()
        suggestions = gen.generate_improvement_suggestions(
            self._make_spec(),
            self._make_plan(),
        )
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0  # Should always find something to suggest

    def test_security_suggestions_waf_disabled(self) -> None:
        """Should suggest enabling WAF when it's disabled."""
        from src.orchestrator.generators.docs_generator import DocsGenerator

        gen = DocsGenerator()
        suggestions = gen.generate_improvement_suggestions(
            self._make_spec(),
            self._make_plan(),
        )
        waf_suggestions = [s for s in suggestions if "WAF" in s and "Security" in s]
        assert len(waf_suggestions) >= 1

    def test_observability_suggestions(self) -> None:
        """Should suggest alerts and dashboards when they're missing."""
        from src.orchestrator.generators.docs_generator import DocsGenerator

        gen = DocsGenerator()
        suggestions = gen.generate_improvement_suggestions(
            self._make_spec(),
            self._make_plan(),
        )
        obs_suggestions = [s for s in suggestions if "Observability" in s]
        assert len(obs_suggestions) >= 1

    def test_threat_model_suggestions(self) -> None:
        """Should suggest expanding threat model when < 4 categories."""
        from src.orchestrator.generators.docs_generator import DocsGenerator

        gen = DocsGenerator()
        suggestions = gen.generate_improvement_suggestions(
            self._make_spec(),
            self._make_plan(threat_model=[]),
        )
        threat_suggestions = [s for s in suggestions if "threat model" in s.lower()]
        assert len(threat_suggestions) >= 1

    def test_waf_gap_suggestions(self) -> None:
        """Should generate WAF gap suggestions when WAF report has low coverage."""
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.standards.waf import WAFAssessor

        gen = DocsGenerator()
        assessor = WAFAssessor()
        waf_report = assessor.assess(plan_components=[], governance_checks={})

        suggestions = gen.generate_improvement_suggestions(
            self._make_spec(),
            self._make_plan(),
            waf_report=waf_report,
        )
        waf_gap_suggestions = [s for s in suggestions if s.startswith("[WAF/")]
        # With empty components, coverage should be low -> should have WAF gaps
        assert len(waf_gap_suggestions) >= 1

    def test_governance_suggestions(self) -> None:
        """Should include governance findings as suggestions."""
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.intent_schema import GovernanceCheck, GovernanceReport

        gov = GovernanceReport(
            status="FAIL",
            summary="Governance validation failed",
            checks=[
                GovernanceCheck(
                    check_id="GOV-001",
                    name="key-vault-required",
                    passed=False,
                    details="Missing Key Vault component",
                ),
            ],
            recommendations=["Add Key Vault for secrets management"],
        )
        gen = DocsGenerator()
        suggestions = gen.generate_improvement_suggestions(
            self._make_spec(),
            self._make_plan(),
            governance=gov,
        )
        gov_suggestions = [s for s in suggestions if "[Governance]" in s]
        assert len(gov_suggestions) >= 2  # One from check, one from recommendation


class TestImprovementSuggestionsMd(unittest.TestCase):
    """Test the _improvement_suggestions_md rendering."""

    def test_renders_suggestions(self) -> None:
        """Should render numbered suggestions in markdown."""
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            IntentSpec,
            ObservabilityRequirements,
            SecurityRequirements,
        )

        spec = IntentSpec(
            project_name="md-test",
            description="Test",
            raw_intent="Test",
            app_type=AppType.API,
            data_stores=[],
            security=SecurityRequirements(auth_model=AuthModel.MANAGED_IDENTITY),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
        )
        gen = DocsGenerator()
        md = gen._improvement_suggestions_md(
            spec, ["Suggestion A", "Suggestion B"]
        )
        assert "# Improvement Suggestions -- md-test" in md
        assert "1. Suggestion A" in md
        assert "2. Suggestion B" in md
        assert "How to Use" in md

    def test_renders_empty_suggestions(self) -> None:
        """Should handle no suggestions gracefully."""
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            IntentSpec,
            ObservabilityRequirements,
            SecurityRequirements,
        )

        spec = IntentSpec(
            project_name="empty-test",
            description="Test",
            raw_intent="Test",
            app_type=AppType.API,
            data_stores=[],
            security=SecurityRequirements(auth_model=AuthModel.MANAGED_IDENTITY),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
        )
        gen = DocsGenerator()
        md = gen._improvement_suggestions_md(spec, [])
        assert "well-defined" in md.lower() or "no improvements" in md.lower()


class TestDocsGeneratorOutputIncludesImprovements(unittest.TestCase):
    """Test that generate() includes improvement-suggestions.md."""

    def test_generate_includes_improvement_suggestions_file(self) -> None:
        """The generate method should always produce improvement-suggestions.md."""
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            IntentSpec,
            ObservabilityRequirements,
            PlanOutput,
            SecurityRequirements,
        )

        spec = IntentSpec(
            project_name="output-test",
            description="Test",
            raw_intent="Test",
            app_type=AppType.API,
            data_stores=[],
            security=SecurityRequirements(auth_model=AuthModel.MANAGED_IDENTITY),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
        )
        plan = PlanOutput(
            title="Plan",
            summary="Summary",
            components=[],
            decisions=[],
            threat_model=[],
            diagram_mermaid="graph LR; A-->B",
        )
        gen = DocsGenerator()
        files = gen.generate(spec, plan)

        assert "docs/improvement-suggestions.md" in files
        assert "Improvement Suggestions" in files["docs/improvement-suggestions.md"]


# -- Roundtrip test: template -> parse -> completeness ----------


class TestEnterpriseRoundtrip(unittest.TestCase):
    """Test that a filled-in template parses back with full completeness."""

    def test_filled_template_roundtrip(self) -> None:
        """A fully filled enterprise template should parse to 100% completeness."""
        parser = IntentFileParser()

        md = """# roundtrip-test
> A comprehensive enterprise API for document management.

## Problem Statement
Manual document processing costs $2M/year.

## Business Goals
Reduce processing time by 80%, achieve SOC2 certification.

## Target Users
Compliance officers, legal counsel, system administrators.

## Functional Requirements
Document upload, search, versioning, audit trail.

## Scalability Requirements
1000 concurrent users, 500 RPS peak, 10TB storage.

## Security & Compliance
OAuth2 + RBAC, AES-256, SOC2, HIPAA awareness.

## Performance Requirements
p95 < 200ms, p99 < 500ms, 99.95% SLA.

## Integration Requirements
Azure AD, legacy ERP via REST, email notifications.

## Acceptance Criteria
All endpoints < 300ms under load, zero critical CVEs, CI green.

## Configuration
- **App Type**: api
- **Data Stores**: blob, cosmos
- **Region**: eastus2
- **Environment**: dev
- **Auth**: managed-identity
- **Compliance**: SOC2

## Version
- **Version**: 1
- **Based On**: (none)
- **Changes**: Initial scaffold
"""
        result = parser.parse_string(md)

        assert result.project_name == "roundtrip-test"
        assert result.completeness_pct == 100.0
        assert all(result.enterprise_sections_filled.values())

        # full_intent should be non-empty and contain key content
        full = result.full_intent
        assert "$2M/year" in full
        assert "SOC2 certification" in full
        assert "Compliance officers" in full
        assert "Document upload" in full
        assert "1000 concurrent" in full
        assert "AES-256" in full
        assert "p95 < 200ms" in full
        assert "legacy ERP" in full
        assert "zero critical CVEs" in full
        assert "Application type: api" in full
        assert "Azure region: eastus2" in full


# -- Import guard ---------------------------------------------

import pytest  # noqa: E402 -- needed for approx


if __name__ == "__main__":
    unittest.main()
