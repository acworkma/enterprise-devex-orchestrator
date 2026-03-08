"""Tests for Azure Well-Architected Framework (WAF) standards engine."""

from __future__ import annotations

from src.orchestrator.standards.waf import (
    ADR_TO_WAF,
    GOVERNANCE_TO_WAF,
    WAF_PRINCIPLES,
    WAFAlignmentReport,
    WAFAssessmentItem,
    WAFAssessor,
    WAFPillar,
    generate_waf_report_md,
)

# ═════════════════════════════════════════════════════════════════════
# WAFPillar Enum Tests
# ═════════════════════════════════════════════════════════════════════


class TestWAFPillarEnum:
    """Test WAFPillar has the canonical 5 pillars."""

    def test_five_pillars(self) -> None:
        assert len(WAFPillar) == 5

    def test_pillar_values(self) -> None:
        expected = {
            "Reliability",
            "Security",
            "Cost Optimization",
            "Operational Excellence",
            "Performance Efficiency",
        }
        assert {p.value for p in WAFPillar} == expected

    def test_pillar_is_string_enum(self) -> None:
        assert isinstance(WAFPillar.RELIABILITY, str)
        assert WAFPillar.SECURITY == "Security"

    def test_pillar_names(self) -> None:
        assert WAFPillar.RELIABILITY.name == "RELIABILITY"
        assert WAFPillar.COST_OPTIMIZATION.name == "COST_OPTIMIZATION"


# ═════════════════════════════════════════════════════════════════════
# WAFPrinciple Catalog Tests
# ═════════════════════════════════════════════════════════════════════


class TestWAFPrinciplesCatalog:
    """Test the 25-principle catalog."""

    def test_total_principles(self) -> None:
        assert len(WAF_PRINCIPLES) == 26

    def test_unique_ids(self) -> None:
        ids = [p.id for p in WAF_PRINCIPLES]
        assert len(ids) == len(set(ids))

    def test_reliability_principles(self) -> None:
        rel = [p for p in WAF_PRINCIPLES if p.pillar == WAFPillar.RELIABILITY]
        assert len(rel) == 5
        assert all(p.id.startswith("REL-") for p in rel)

    def test_security_principles(self) -> None:
        sec = [p for p in WAF_PRINCIPLES if p.pillar == WAFPillar.SECURITY]
        assert len(sec) == 8
        assert all(p.id.startswith("SEC-") for p in sec)

    def test_cost_optimization_principles(self) -> None:
        cost = [p for p in WAF_PRINCIPLES if p.pillar == WAFPillar.COST_OPTIMIZATION]
        assert len(cost) == 4
        assert all(p.id.startswith("COST-") for p in cost)

    def test_operational_excellence_principles(self) -> None:
        ops = [p for p in WAF_PRINCIPLES if p.pillar == WAFPillar.OPERATIONAL_EXCELLENCE]
        assert len(ops) == 5
        assert all(p.id.startswith("OPS-") for p in ops)

    def test_performance_efficiency_principles(self) -> None:
        perf = [p for p in WAF_PRINCIPLES if p.pillar == WAFPillar.PERFORMANCE_EFFICIENCY]
        assert len(perf) == 4
        assert all(p.id.startswith("PERF-") for p in perf)

    def test_all_principles_have_required_fields(self) -> None:
        for p in WAF_PRINCIPLES:
            assert p.id, "Principle missing id"
            assert p.pillar, f"{p.id} missing pillar"
            assert p.name, f"{p.id} missing name"
            assert p.description, f"{p.id} missing description"
            assert p.check, f"{p.id} missing check"

    def test_principle_is_frozen(self) -> None:
        p = WAF_PRINCIPLES[0]
        try:
            p.id = "SHOULD-FAIL"  # type: ignore[misc]
            raise AssertionError("WAFPrinciple should be frozen")
        except AttributeError:
            pass  # Expected — frozen dataclass


# ═════════════════════════════════════════════════════════════════════
# WAFAlignmentReport Tests
# ═════════════════════════════════════════════════════════════════════


class TestWAFAlignmentReport:
    """Test report aggregation properties."""

    def _make_items(self, covered_flags: list[tuple[WAFPillar, bool]]) -> list[WAFAssessmentItem]:
        items = []
        for i, (pillar, covered) in enumerate(covered_flags):
            items.append(
                WAFAssessmentItem(
                    principle_id=f"TST-{i:02d}",
                    pillar=pillar,
                    name=f"Test principle {i}",
                    covered=covered,
                    evidence="Test evidence" if covered else "Not covered",
                    recommendation="" if covered else "Fix it",
                )
            )
        return items

    def test_empty_report(self) -> None:
        report = WAFAlignmentReport(items=[])
        assert report.total_principles == 0
        assert report.covered_count == 0
        assert report.coverage_pct == 0.0
        assert report.gaps() == []

    def test_all_covered(self) -> None:
        items = self._make_items([
            (WAFPillar.SECURITY, True),
            (WAFPillar.RELIABILITY, True),
        ])
        report = WAFAlignmentReport(items=items)
        assert report.total_principles == 2
        assert report.covered_count == 2
        assert report.coverage_pct == 100.0
        assert report.gaps() == []

    def test_partial_coverage(self) -> None:
        items = self._make_items([
            (WAFPillar.SECURITY, True),
            (WAFPillar.SECURITY, False),
            (WAFPillar.RELIABILITY, True),
            (WAFPillar.RELIABILITY, False),
        ])
        report = WAFAlignmentReport(items=items)
        assert report.total_principles == 4
        assert report.covered_count == 2
        assert report.coverage_pct == 50.0
        assert len(report.gaps()) == 2

    def test_pillar_scores(self) -> None:
        items = self._make_items([
            (WAFPillar.SECURITY, True),
            (WAFPillar.SECURITY, True),
            (WAFPillar.SECURITY, False),
            (WAFPillar.RELIABILITY, True),
        ])
        report = WAFAlignmentReport(items=items)
        scores = report.pillar_scores()
        assert scores[WAFPillar.SECURITY]["covered"] == 2
        assert scores[WAFPillar.SECURITY]["total"] == 3
        pct = scores[WAFPillar.SECURITY]["pct"]
        assert abs(pct - 66.66666) < 1  # ~66.7%
        assert scores[WAFPillar.RELIABILITY]["covered"] == 1
        assert scores[WAFPillar.RELIABILITY]["total"] == 1
        assert scores[WAFPillar.RELIABILITY]["pct"] == 100.0

    def test_pillar_scores_all_five_pillars_present(self) -> None:
        """Even pillars with no items should appear in scores."""
        report = WAFAlignmentReport(items=[])
        scores = report.pillar_scores()
        assert len(scores) == 5
        for pillar in WAFPillar:
            assert pillar in scores
            assert scores[pillar]["total"] == 0
            assert scores[pillar]["pct"] == 0.0

    def test_gaps_returns_uncovered_only(self) -> None:
        items = self._make_items([
            (WAFPillar.COST_OPTIMIZATION, True),
            (WAFPillar.COST_OPTIMIZATION, False),
        ])
        report = WAFAlignmentReport(items=items)
        gaps = report.gaps()
        assert len(gaps) == 1
        assert gaps[0].covered is False


# ═════════════════════════════════════════════════════════════════════
# WAFAssessor Tests
# ═════════════════════════════════════════════════════════════════════


class TestWAFAssessor:
    """Test the WAF assessment engine."""

    def setup_method(self) -> None:
        self.assessor = WAFAssessor()

    def test_full_coverage_scenario(self) -> None:
        """Test assessment with all features enabled — high coverage expected."""
        report = self.assessor.assess(
            plan_components=[
                "container-app",
                "key-vault",
                "log-analytics",
                "managed-identity",
                "container-registry",
            ],
            governance_checks={
                "GOV-REQ-KEY-VAULT": True,
                "GOV-REQ-LOG-ANALYTICS": True,
                "GOV-REQ-MANAGED-IDENTITY": True,
                "GOV-NET-001": True,
                "GOV-NET-002": True,
            },
            has_bicep=True,
            has_dockerfile=True,
            has_cicd=True,
            has_state_manager=True,
            has_threat_model=True,
            has_adrs=True,
            has_tags=True,
            has_health_endpoint=True,
            data_stores=["blob"],
        )

        assert report.total_principles == 26
        assert report.coverage_pct >= 90.0, f"Expected >=90% but got {report.coverage_pct}%"

    def test_minimal_coverage_scenario(self) -> None:
        """Test assessment with minimal features — low coverage expected."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_bicep=False,
            has_dockerfile=False,
            has_cicd=False,
            has_state_manager=False,
            has_threat_model=False,
            has_adrs=False,
            has_tags=False,
            has_health_endpoint=False,
        )

        assert report.total_principles == 26
        assert report.coverage_pct <= 20.0, f"Expected <=20% but got {report.coverage_pct}%"
        assert len(report.gaps()) >= 18

    def test_always_returns_25_items(self) -> None:
        """Assessor should evaluate all 25 principles regardless of inputs."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
        )
        assert len(report.items) == 26

    def test_reliability_health_endpoint(self) -> None:
        """REL-01: Health endpoint should map to health_endpoint flag."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_health_endpoint=True,
        )
        rel01 = next(i for i in report.items if i.principle_id == "REL-01")
        assert rel01.covered is True

        report_no = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_health_endpoint=False,
        )
        rel01_no = next(i for i in report_no.items if i.principle_id == "REL-01")
        assert rel01_no.covered is False

    def test_security_managed_identity(self) -> None:
        """SEC-01: Managed Identity depends on governance check."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={"GOV-REQ-MANAGED-IDENTITY": True},
        )
        sec01 = next(i for i in report.items if i.principle_id == "SEC-01")
        assert sec01.covered is True

    def test_security_key_vault(self) -> None:
        """SEC-02: Key Vault depends on governance check."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={"GOV-REQ-KEY-VAULT": True},
        )
        sec02 = next(i for i in report.items if i.principle_id == "SEC-02")
        assert sec02.covered is True

    def test_security_threat_model(self) -> None:
        """SEC-05: Threat model coverage."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_threat_model=True,
        )
        sec05 = next(i for i in report.items if i.principle_id == "SEC-05")
        assert sec05.covered is True

    def test_cost_optimization_tags(self) -> None:
        """COST-01: Tags for cost tracking."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_tags=True,
        )
        cost01 = next(i for i in report.items if i.principle_id == "COST-01")
        assert cost01.covered is True

    def test_cost_cosmos_serverless(self) -> None:
        """COST-04: Cosmos DB serverless for dev."""
        # With cosmos in data stores
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            data_stores=["cosmos"],
        )
        cost04 = next(i for i in report.items if i.principle_id == "COST-04")
        assert cost04.covered is True

        # Without cosmos — N/A, should still be "covered"
        report_no = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            data_stores=["blob"],
        )
        cost04_no = next(i for i in report_no.items if i.principle_id == "COST-04")
        assert cost04_no.covered is True  # N/A counts as covered

    def test_ops_centralized_logging(self) -> None:
        """OPS-01: Log Analytics depends on governance check."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={"GOV-REQ-LOG-ANALYTICS": True},
        )
        ops01 = next(i for i in report.items if i.principle_id == "OPS-01")
        assert ops01.covered is True

    def test_ops_cicd_oidc(self) -> None:
        """OPS-02: CI/CD with OIDC."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_cicd=True,
        )
        ops02 = next(i for i in report.items if i.principle_id == "OPS-02")
        assert ops02.covered is True

    def test_ops_state_manager(self) -> None:
        """OPS-05: State management and drift detection."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_state_manager=True,
        )
        ops05 = next(i for i in report.items if i.principle_id == "OPS-05")
        assert ops05.covered is True

    def test_perf_container_registry(self) -> None:
        """PERF-03: Private container registry."""
        report = self.assessor.assess(
            plan_components=["container-registry"],
            governance_checks={},
        )
        perf03 = next(i for i in report.items if i.principle_id == "PERF-03")
        assert perf03.covered is True

    def test_ops04_always_covered(self) -> None:
        """OPS-04: Automated governance validation is always true (by design)."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_bicep=False,
            has_cicd=False,
        )
        ops04 = next(i for i in report.items if i.principle_id == "OPS-04")
        assert ops04.covered is True

    def test_uncovered_principles_have_recommendations(self) -> None:
        """All uncovered principles should have non-empty recommendations."""
        report = self.assessor.assess(
            plan_components=[],
            governance_checks={},
            has_bicep=False,
            has_dockerfile=False,
            has_cicd=False,
            has_state_manager=False,
            has_threat_model=False,
            has_adrs=False,
            has_tags=False,
            has_health_endpoint=False,
        )
        for item in report.items:
            if not item.covered:
                assert item.recommendation, f"{item.principle_id} is uncovered but has no recommendation"


# ═════════════════════════════════════════════════════════════════════
# Mapping Tests
# ═════════════════════════════════════════════════════════════════════


class TestGovernanceToWAFMapping:
    """Test the GOVERNANCE_TO_WAF mapping table."""

    def test_mapping_not_empty(self) -> None:
        assert len(GOVERNANCE_TO_WAF) >= 15

    def test_all_values_are_valid_pillars(self) -> None:
        for check_id, pillars in GOVERNANCE_TO_WAF.items():
            assert isinstance(pillars, list), f"{check_id} value should be a list"
            for p in pillars:
                assert isinstance(p, WAFPillar), f"{check_id} has invalid pillar: {p}"

    def test_key_vault_maps_to_security(self) -> None:
        assert WAFPillar.SECURITY in GOVERNANCE_TO_WAF["GOV-REQ-KEY-VAULT"]

    def test_log_analytics_maps_to_ops(self) -> None:
        assert WAFPillar.OPERATIONAL_EXCELLENCE in GOVERNANCE_TO_WAF["GOV-REQ-LOG-ANALYTICS"]

    def test_tagging_maps_to_cost(self) -> None:
        assert WAFPillar.COST_OPTIMIZATION in GOVERNANCE_TO_WAF["STD-TAG-001"]


class TestADRToWAFMapping:
    """Test the ADR_TO_WAF mapping table."""

    def test_mapping_has_entries(self) -> None:
        assert len(ADR_TO_WAF) >= 5

    def test_adr001_maps_to_reliability(self) -> None:
        assert WAFPillar.RELIABILITY in ADR_TO_WAF["ADR-001"]

    def test_adr002_maps_to_security(self) -> None:
        assert WAFPillar.SECURITY in ADR_TO_WAF["ADR-002"]

    def test_adr003_maps_to_iac(self) -> None:
        assert WAFPillar.RELIABILITY in ADR_TO_WAF["ADR-003"]
        assert WAFPillar.OPERATIONAL_EXCELLENCE in ADR_TO_WAF["ADR-003"]


# ═════════════════════════════════════════════════════════════════════
# WAF Report Generation Tests
# ═════════════════════════════════════════════════════════════════════


class TestGenerateWAFReportMd:
    """Test Markdown WAF report generation."""

    def _make_report(self) -> WAFAlignmentReport:
        assessor = WAFAssessor()
        return assessor.assess(
            plan_components=["container-app", "key-vault", "managed-identity", "container-registry"],
            governance_checks={
                "GOV-REQ-KEY-VAULT": True,
                "GOV-REQ-LOG-ANALYTICS": True,
                "GOV-REQ-MANAGED-IDENTITY": True,
                "GOV-NET-001": True,
            },
            has_bicep=True,
            has_dockerfile=True,
            has_cicd=True,
            has_state_manager=True,
            has_threat_model=True,
            has_adrs=True,
            has_tags=True,
            has_health_endpoint=True,
        )

    def test_report_starts_with_title(self) -> None:
        md = generate_waf_report_md(self._make_report())
        assert md.startswith("# Well-Architected Framework Alignment Report")

    def test_report_has_overall_coverage(self) -> None:
        md = generate_waf_report_md(self._make_report())
        assert "Overall Coverage:" in md

    def test_report_has_pillar_scores_table(self) -> None:
        md = generate_waf_report_md(self._make_report())
        assert "## Pillar Scores" in md
        assert "| Pillar |" in md

    def test_report_has_detailed_assessment(self) -> None:
        md = generate_waf_report_md(self._make_report())
        assert "## Detailed Assessment" in md

    def test_report_has_all_five_pillar_sections(self) -> None:
        md = generate_waf_report_md(self._make_report())
        for pillar in WAFPillar:
            assert f"### {pillar.value}" in md

    def test_report_has_reference_links(self) -> None:
        md = generate_waf_report_md(self._make_report())
        assert "learn.microsoft.com/en-us/azure/well-architected/" in md

    def test_report_has_status_icons(self) -> None:
        md = generate_waf_report_md(self._make_report())
        assert "✅" in md  # At least some should pass

    def test_report_generated_by_footer(self) -> None:
        md = generate_waf_report_md(self._make_report())
        assert "Enterprise DevEx Orchestrator Agent" in md

    def test_empty_report_still_generates(self) -> None:
        md = generate_waf_report_md(WAFAlignmentReport(items=[]))
        assert "# Well-Architected Framework Alignment Report" in md
        assert "0/0" in md


# ═════════════════════════════════════════════════════════════════════
# Integration Tests
# ═════════════════════════════════════════════════════════════════════


class TestWAFIntegration:
    """Test WAF integration with governance reviewer."""

    def test_assess_waf_method_exists(self) -> None:
        """GovernanceReviewerAgent should have assess_waf method."""
        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent

        reviewer = GovernanceReviewerAgent(config=None)
        assert hasattr(reviewer, "assess_waf")
        assert callable(reviewer.assess_waf)

    def test_assess_waf_returns_report(self) -> None:
        """assess_waf should return WAFAlignmentReport."""
        from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            ComplianceFramework,
            GovernanceReport,
            IntentSpec,
            ObservabilityRequirements,
            PlanOutput,
            SecurityRequirements,
        )

        spec = IntentSpec(
            project_name="test-waf-project",
            description="Test WAF project",
            raw_intent="Test intent for WAF",
            app_type=AppType.API,
            data_stores=[],
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=ComplianceFramework.SOC2_GUIDANCE,
            ),
            observability=ObservabilityRequirements(health_endpoint=True),
            cicd=CICDRequirements(),
        )

        plan = PlanOutput(
            title="Test Plan",
            summary="Test summary",
            components=[],
            decisions=[],
            threat_model=[],
            diagram_mermaid="graph LR; A-->B",
        )

        gov_report = GovernanceReport(
            status="PASS",
            summary="All checks passed.",
            checks=[],
            recommendations=[],
        )

        reviewer = GovernanceReviewerAgent(config=None)
        waf_report = reviewer.assess_waf(spec, plan, gov_report)

        assert isinstance(waf_report, WAFAlignmentReport)
        assert waf_report.total_principles == 26
        assert 0 <= waf_report.coverage_pct <= 100

    def test_waf_report_in_docs_generator(self) -> None:
        """DocsGenerator should include waf-report.md when WAF report is provided."""
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            ComplianceFramework,
            IntentSpec,
            ObservabilityRequirements,
            PlanOutput,
            SecurityRequirements,
        )

        spec = IntentSpec(
            project_name="test-docs",
            description="Test docs project",
            raw_intent="Test intent for docs",
            app_type=AppType.API,
            data_stores=[],
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=ComplianceFramework.SOC2_GUIDANCE,
            ),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
        )

        plan = PlanOutput(
            title="Test Plan",
            summary="Test summary",
            components=[],
            decisions=[],
            threat_model=[],
            diagram_mermaid="graph LR; A-->B",
        )

        assessor = WAFAssessor()
        waf_report = assessor.assess(plan_components=[], governance_checks={})

        docs_gen = DocsGenerator()
        files = docs_gen.generate(spec, plan, waf_report=waf_report)

        assert "docs/waf-report.md" in files
        assert "Well-Architected Framework" in files["docs/waf-report.md"]

    def test_docs_generator_without_waf_report(self) -> None:
        """DocsGenerator should work without WAF report."""
        from src.orchestrator.generators.docs_generator import DocsGenerator
        from src.orchestrator.intent_schema import (
            AppType,
            AuthModel,
            CICDRequirements,
            ComplianceFramework,
            IntentSpec,
            ObservabilityRequirements,
            PlanOutput,
            SecurityRequirements,
        )

        spec = IntentSpec(
            project_name="test-no-waf",
            description="Test no WAF",
            raw_intent="Test intent no WAF",
            app_type=AppType.API,
            data_stores=[],
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=ComplianceFramework.SOC2_GUIDANCE,
            ),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
        )

        plan = PlanOutput(
            title="Test Plan",
            summary="Test summary",
            components=[],
            decisions=[],
            threat_model=[],
            diagram_mermaid="graph LR; A-->B",
        )

        docs_gen = DocsGenerator()
        files = docs_gen.generate(spec, plan)

        assert "docs/waf-report.md" not in files
        assert "docs/plan.md" in files  # Other docs still generated


# ═════════════════════════════════════════════════════════════════════
# Policy Engine WAF Policy Tests
# ═════════════════════════════════════════════════════════════════════


class TestWAFPolicies:
    """Test WAF policies are present in the policy engine."""

    def test_waf_policies_exist(self) -> None:
        from src.orchestrator.tools.policy_engine import POLICY_CATALOG

        waf_policies = [p for p in POLICY_CATALOG if p.id.startswith("WAF-")]
        assert len(waf_policies) == 5

    def test_waf_policy_ids(self) -> None:
        from src.orchestrator.tools.policy_engine import POLICY_CATALOG

        waf_ids = {p.id for p in POLICY_CATALOG if p.id.startswith("WAF-")}
        assert waf_ids == {"WAF-001", "WAF-002", "WAF-003", "WAF-004", "WAF-005"}

    def test_waf_policies_category(self) -> None:
        from src.orchestrator.tools.policy_engine import POLICY_CATALOG

        for p in POLICY_CATALOG:
            if p.id.startswith("WAF-"):
                assert p.category == "Well-Architected"

    def test_waf002_is_error_severity(self) -> None:
        """WAF-002 Security should be an ERROR (not just WARNING)."""
        from src.orchestrator.tools.policy_engine import POLICY_CATALOG

        waf002 = next(p for p in POLICY_CATALOG if p.id == "WAF-002")
        assert waf002.severity.value == "error"

    def test_total_policy_count(self) -> None:
        """Verify total policy count increased after WAF addition."""
        from src.orchestrator.tools.policy_engine import POLICY_CATALOG

        assert len(POLICY_CATALOG) == 20  # 15 original + 5 WAF
