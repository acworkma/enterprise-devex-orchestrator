"""Tests for Deploy Orchestrator -- staged deployment, error classification."""

from __future__ import annotations

from src.orchestrator.agents.deploy_orchestrator import (
    ERROR_PATTERNS,
    DeploymentResult,
    DeployOrchestrator,
    DeployStage,
    DeployStageResult,
    DeployStatus,
    ErrorCategory,
)

# ----------------- Data Classes -----------------


class TestDeployStageResult:
    def test_defaults(self) -> None:
        r = DeployStageResult(stage=DeployStage.VALIDATE)
        assert r.status == DeployStatus.PENDING
        assert r.error == ""
        assert r.retry_count == 0

    def test_to_dict(self) -> None:
        r = DeployStageResult(
            stage=DeployStage.VALIDATE,
            status=DeployStatus.SUCCEEDED,
            duration_ms=123.4,
        )
        d = r.to_dict()
        assert d["stage"] == "validate"
        assert d["status"] == "succeeded"
        assert d["duration_ms"] == 123.4


class TestDeploymentResult:
    def test_is_success(self) -> None:
        r = DeploymentResult(
            deployment_id="test",
            resource_group="rg",
            region="eastus2",
            status=DeployStatus.SUCCEEDED,
        )
        assert r.is_success is True

    def test_is_not_success(self) -> None:
        r = DeploymentResult(
            deployment_id="test",
            resource_group="rg",
            region="eastus2",
            status=DeployStatus.FAILED,
        )
        assert r.is_success is False

    def test_to_dict(self) -> None:
        r = DeploymentResult(
            deployment_id="dep1",
            resource_group="rg",
            region="eastus2",
            status=DeployStatus.SUCCEEDED,
            resources_deployed=["rg/kv", "rg/app"],
        )
        d = r.to_dict()
        assert d["deployment_id"] == "dep1"
        assert d["status"] == "succeeded"
        assert len(d["resources_deployed"]) == 2


# ----------------- Error Classification -----------------


class TestErrorClassification:
    def test_classify_auth_error(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("AADSTS50012: invalid token")
        assert cat == ErrorCategory.AUTHENTICATION
        assert "login" in rem.lower()

    def test_classify_authorization_error(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("AuthorizationFailed for scope xyz")
        assert cat == ErrorCategory.AUTHORIZATION

    def test_classify_quota_error(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("QuotaExceeded for resource")
        assert cat == ErrorCategory.QUOTA

    def test_classify_conflict_error(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("Resource already exists in rg")
        assert cat == ErrorCategory.CONFLICT

    def test_classify_transient_error(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("InternalServerError received")
        assert cat == ErrorCategory.TRANSIENT

    def test_classify_unknown_error(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("something completely random")
        assert cat == ErrorCategory.UNKNOWN

    def test_classify_sku_not_available(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("SkuNotAvailable in region")
        assert cat == ErrorCategory.QUOTA

    def test_classify_policy_error(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        cat, rem = orch._classify_error("RequestDisallowedByPolicy")
        assert cat == ErrorCategory.AUTHORIZATION


# ----------------- Enums -----------------


class TestDeployEnums:
    def test_deploy_stages(self) -> None:
        assert DeployStage.VALIDATE.value == "validate"
        assert DeployStage.WHAT_IF.value == "what-if"
        assert DeployStage.DEPLOY_INFRA.value == "deploy-infra"
        assert DeployStage.VERIFY.value == "verify"

    def test_deploy_status(self) -> None:
        assert DeployStatus.PENDING.value == "pending"
        assert DeployStatus.SUCCEEDED.value == "succeeded"
        assert DeployStatus.FAILED.value == "failed"

    def test_error_category_values(self) -> None:
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.QUOTA.value == "quota"
        assert ErrorCategory.TRANSIENT.value == "transient"

    def test_error_patterns_not_empty(self) -> None:
        assert len(ERROR_PATTERNS) >= 8


# ----------------- Orchestrator Init -----------------


class TestDeployOrchestratorInit:
    def test_default_region(self) -> None:
        orch = DeployOrchestrator(output_dir=".", resource_group="rg")
        assert orch.region == "eastus2"

    def test_custom_params(self) -> None:
        orch = DeployOrchestrator(
            output_dir="/tmp/out",
            resource_group="my-rg",
            region="westus2",
            subscription="sub-123",
        )
        assert orch.resource_group == "my-rg"
        assert orch.region == "westus2"
        assert orch.subscription == "sub-123"
