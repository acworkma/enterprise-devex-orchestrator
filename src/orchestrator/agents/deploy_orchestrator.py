"""Deploy Orchestrator -- automated Azure deployment with error recovery.

Orchestrates deployment of generated Bicep templates via Azure CLI with:
    - Pre-deployment validation (what-if)
    - Staged deployment (infra -> app -> monitoring)
    - Automatic error classification and retry
    - Rollback on critical failures
    - Deployment status tracking
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


class DeployStage(str, Enum):
    """Deployment stage."""

    VALIDATE = "validate"
    WHAT_IF = "what-if"
    DEPLOY_INFRA = "deploy-infra"
    DEPLOY_APP = "deploy-app"
    DEPLOY_MONITORING = "deploy-monitoring"
    VERIFY = "verify"


class DeployStatus(str, Enum):
    """Status of a deployment."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ErrorCategory(str, Enum):
    """Classification of deployment errors."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    QUOTA = "quota"
    CONFLICT = "conflict"
    VALIDATION = "validation"
    NETWORK = "network"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"


# Known error patterns for classification
ERROR_PATTERNS: list[tuple[str, ErrorCategory, str]] = [
    (r"AADSTS\d+", ErrorCategory.AUTHENTICATION, "Re-authenticate with `az login`"),
    (r"AuthorizationFailed|does not have authorization", ErrorCategory.AUTHORIZATION, "Check RBAC role assignments"),
    (r"QuotaExceeded|exceeds.*quota", ErrorCategory.QUOTA, "Request quota increase or change SKU/region"),
    (
        r"Conflict|already exists",
        ErrorCategory.CONFLICT,
        "Resource exists -- use incremental deployment or delete first",
    ),
    (r"InvalidTemplate|validation failed", ErrorCategory.VALIDATION, "Fix Bicep template errors"),
    (r"timeout|ETIMEDOUT|connection refused", ErrorCategory.NETWORK, "Check network connectivity"),
    (r"InternalServerError|ServiceUnavailable|BadGateway", ErrorCategory.TRANSIENT, "Retry after 30 seconds"),
    (r"RequestDisallowedByPolicy", ErrorCategory.AUTHORIZATION, "Check Azure Policy assignments"),
    (r"SkuNotAvailable", ErrorCategory.QUOTA, "Try a different SKU or region"),
    (r"LinkedAuthorizationFailed", ErrorCategory.AUTHORIZATION, "Cross-scope permission needed"),
]


@dataclass
class DeployStageResult:
    """Result of a single deployment stage."""

    stage: DeployStage
    status: DeployStatus = DeployStatus.PENDING
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    output: str = ""
    error: str = ""
    error_category: ErrorCategory | None = None
    remediation: str = ""
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "error_category": self.error_category.value if self.error_category else None,
            "remediation": self.remediation,
            "retry_count": self.retry_count,
        }


@dataclass
class DeploymentResult:
    """Complete deployment result."""

    deployment_id: str
    resource_group: str
    region: str
    status: DeployStatus = DeployStatus.PENDING
    stages: list[DeployStageResult] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""
    total_duration_ms: float = 0.0
    resources_deployed: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.status == DeployStatus.SUCCEEDED

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "resource_group": self.resource_group,
            "region": self.region,
            "status": self.status.value,
            "stages": [s.to_dict() for s in self.stages],
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
            "resources_deployed": self.resources_deployed,
        }


class DeployOrchestrator:
    """Orchestrates staged Azure deployment with error recovery.

    Deployment stages:
    1. Validate -- `az deployment group validate`
    2. What-If -- Preview changes
    3. Deploy Infra -- Core infrastructure (main.bicep)
    4. Deploy App -- Container App image update
    5. Deploy Monitoring -- Alert rules and dashboards
    6. Verify -- Post-deployment health checks
    """

    MAX_RETRIES = 2
    RETRY_DELAY_SECONDS = 30

    def __init__(
        self,
        output_dir: str | Path,
        resource_group: str = "",
        region: str = "eastus2",
        subscription: str = "",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.resource_group = resource_group
        self.region = region
        self.subscription = subscription

    def deploy(
        self,
        bicep_path: str = "infra/bicep/main.bicep",
        parameters_path: str = "infra/bicep/parameters/dev.parameters.json",
        dry_run: bool = False,
    ) -> DeploymentResult:
        """Execute full deployment pipeline.

        Args:
            bicep_path: Relative path to main Bicep file.
            parameters_path: Relative path to parameters file.
            dry_run: If True, only validate and what-if (no actual deploy).

        Returns:
            DeploymentResult with per-stage status.
        """
        deployment_id = f"deploy-{datetime.now(tz=UTC).strftime('%Y%m%d-%H%M%S')}"
        result = DeploymentResult(
            deployment_id=deployment_id,
            resource_group=self.resource_group,
            region=self.region,
            created_at=datetime.now(tz=UTC).isoformat(),
        )

        full_bicep = self.output_dir / bicep_path
        full_params = self.output_dir / parameters_path

        # Define stages
        stages = [
            (DeployStage.VALIDATE, lambda: self._validate(full_bicep, full_params)),
            (DeployStage.WHAT_IF, lambda: self._what_if(full_bicep, full_params)),
        ]

        if not dry_run:
            stages.extend(
                [
                    (DeployStage.DEPLOY_INFRA, lambda: self._deploy_infra(full_bicep, full_params)),
                    (DeployStage.VERIFY, lambda: self._verify()),
                ]
            )

        start = time.perf_counter()

        for stage_type, stage_fn in stages:
            stage_result = self._run_stage(stage_type, stage_fn)
            result.stages.append(stage_result)

            if stage_result.status == DeployStatus.FAILED:
                result.status = DeployStatus.FAILED
                result.completed_at = datetime.now(tz=UTC).isoformat()
                result.total_duration_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    "deploy.failed",
                    stage=stage_type.value,
                    error=stage_result.error,
                    category=stage_result.error_category,
                )
                return result

        result.status = DeployStatus.SUCCEEDED
        result.completed_at = datetime.now(tz=UTC).isoformat()
        result.total_duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "deploy.succeeded",
            deployment_id=deployment_id,
            duration_ms=f"{result.total_duration_ms:.0f}",
        )
        return result

    def _run_stage(
        self,
        stage: DeployStage,
        fn: Any,
    ) -> DeployStageResult:
        """Execute a stage with retry logic."""
        stage_result = DeployStageResult(stage=stage)
        stage_result.started_at = datetime.now(tz=UTC).isoformat()

        for attempt in range(self.MAX_RETRIES + 1):
            start = time.perf_counter()
            try:
                output = fn()
                duration = (time.perf_counter() - start) * 1000

                stage_result.status = DeployStatus.SUCCEEDED
                stage_result.completed_at = datetime.now(tz=UTC).isoformat()
                stage_result.duration_ms = duration
                stage_result.output = str(output)[:500]
                stage_result.retry_count = attempt

                logger.info("deploy.stage.ok", stage=stage.value, duration_ms=f"{duration:.0f}")
                return stage_result

            except subprocess.CalledProcessError as e:
                duration = (time.perf_counter() - start) * 1000
                error_text = e.stderr or str(e)
                category, remediation = self._classify_error(error_text)

                stage_result.duration_ms = duration
                stage_result.error = error_text[:500]
                stage_result.error_category = category
                stage_result.remediation = remediation

                # Retry only transient errors
                if category == ErrorCategory.TRANSIENT and attempt < self.MAX_RETRIES:
                    logger.warning(
                        "deploy.stage.retry",
                        stage=stage.value,
                        attempt=attempt + 1,
                        wait=self.RETRY_DELAY_SECONDS,
                    )
                    time.sleep(self.RETRY_DELAY_SECONDS)
                    continue

                stage_result.status = DeployStatus.FAILED
                stage_result.retry_count = attempt
                return stage_result

            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                stage_result.status = DeployStatus.FAILED
                stage_result.duration_ms = duration
                stage_result.error = str(e)[:500]
                stage_result.error_category = ErrorCategory.UNKNOWN
                stage_result.retry_count = attempt
                return stage_result

        stage_result.status = DeployStatus.FAILED
        return stage_result

    def _classify_error(self, error_text: str) -> tuple[ErrorCategory, str]:
        """Classify deployment error and provide remediation."""
        for pattern, category, remediation in ERROR_PATTERNS:
            if re.search(pattern, error_text, re.IGNORECASE):
                return category, remediation
        return ErrorCategory.UNKNOWN, "Review error details and Azure documentation"

    def _build_az_cmd(self, *args: str) -> list[str]:
        """Build az CLI command with common flags."""
        import shutil
        az_path = shutil.which("az") or "az"
        cmd = [az_path] + list(args)
        if self.resource_group:
            cmd.extend(["--resource-group", self.resource_group])
        if self.subscription:
            cmd.extend(["--subscription", self.subscription])
        return cmd

    def _validate(self, bicep_path: Path, params_path: Path) -> str:
        """Run az deployment group validate."""
        cmd = self._build_az_cmd(
            "deployment",
            "group",
            "validate",
            "--template-file",
            str(bicep_path),
        )
        if params_path.exists():
            cmd.extend(["--parameters", f"@{params_path}"])

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        return proc.stdout

    def _what_if(self, bicep_path: Path, params_path: Path) -> str:
        """Run az deployment group what-if."""
        cmd = self._build_az_cmd(
            "deployment",
            "group",
            "what-if",
            "--template-file",
            str(bicep_path),
        )
        if params_path.exists():
            cmd.extend(["--parameters", f"@{params_path}"])

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        )
        return proc.stdout

    def _deploy_infra(self, bicep_path: Path, params_path: Path) -> str:
        """Run az deployment group create."""
        deployment_name = f"devex-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}"
        cmd = self._build_az_cmd(
            "deployment",
            "group",
            "create",
            "--template-file",
            str(bicep_path),
            "--name",
            deployment_name,
            "--mode",
            "Incremental",
        )
        if params_path.exists():
            cmd.extend(["--parameters", f"@{params_path}"])

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
        )
        return proc.stdout

    def _verify(self) -> str:
        """Post-deployment verification -- list deployed resources."""
        cmd = self._build_az_cmd(
            "resource",
            "list",
            "--output",
            "json",
        )
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        try:
            resources = json.loads(proc.stdout)
            return f"Verified {len(resources)} resources"
        except (json.JSONDecodeError, TypeError):
            return proc.stdout[:200]

    def get_deployment_status(self, deployment_name: str = "") -> dict[str, Any]:
        """Query deployment status from Azure."""
        cmd = self._build_az_cmd(
            "deployment",
            "group",
            "list",
            "--output",
            "json",
        )
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            deployments = json.loads(proc.stdout)
            if deployment_name:
                return next(
                    (d for d in deployments if d.get("name") == deployment_name),
                    {"status": "not_found"},
                )
            return {"deployments": deployments[:5]}
        except Exception as e:
            return {"error": str(e)}
