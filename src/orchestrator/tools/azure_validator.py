"""Azure Validator Tool — validates Bicep templates and Azure resource availability.

Provides tools for the agent runtime to call during plan/scaffold operations:
    - validate_bicep: Run `az bicep build` on generated templates
    - validate_deployment: Run `az deployment group validate`
    - check_region_availability: Verify service availability in target region
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ValidationResult:
    """Result of a validation operation."""

    success: bool
    message: str
    details: dict | None = None


def validate_bicep(template_path: str) -> str:
    """Validate a Bicep template by running `az bicep build`.

    Args:
        template_path: Path to the .bicep file.

    Returns:
        JSON string with validation result.
    """
    logger.info("tool.validate_bicep", path=template_path)
    path = Path(template_path)

    if not path.exists():
        result = ValidationResult(
            success=False,
            message=f"File not found: {template_path}",
        )
        return json.dumps({"success": result.success, "message": result.message})

    if not path.suffix == ".bicep":
        result = ValidationResult(
            success=False,
            message=f"Not a Bicep file: {template_path}",
        )
        return json.dumps({"success": result.success, "message": result.message})

    try:
        proc = subprocess.run(
            ["az", "bicep", "build", "--file", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0:
            result = ValidationResult(
                success=True,
                message=f"Bicep template is valid: {template_path}",
            )
        else:
            result = ValidationResult(
                success=False,
                message=f"Bicep validation failed: {proc.stderr.strip()}",
                details={"stdout": proc.stdout, "stderr": proc.stderr},
            )

    except FileNotFoundError:
        result = ValidationResult(
            success=False,
            message="Azure CLI not found. Install az CLI and bicep extension.",
        )
    except subprocess.TimeoutExpired:
        result = ValidationResult(
            success=False,
            message="Bicep validation timed out after 60s.",
        )

    return json.dumps({"success": result.success, "message": result.message, "details": result.details})


def validate_deployment(
    resource_group: str,
    template_path: str,
    parameters_path: str | None = None,
) -> str:
    """Run `az deployment group validate` to check deployment feasibility.

    Args:
        resource_group: Azure resource group name.
        template_path: Path to the main Bicep template.
        parameters_path: Path to parameters file (optional).

    Returns:
        JSON string with validation result.
    """
    logger.info(
        "tool.validate_deployment",
        rg=resource_group,
        template=template_path,
    )

    cmd = [
        "az",
        "deployment",
        "group",
        "validate",
        "--resource-group",
        resource_group,
        "--template-file",
        template_path,
    ]
    if parameters_path:
        cmd.extend(["--parameters", parameters_path])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            return json.dumps(
                {
                    "success": True,
                    "message": "Deployment validation passed.",
                }
            )
        else:
            error_msg = proc.stderr.strip()
            # Try to parse structured error
            try:
                err_json = json.loads(proc.stdout)
                error_msg = err_json.get("error", {}).get("message", error_msg)
            except (json.JSONDecodeError, KeyError):
                pass

            return json.dumps(
                {
                    "success": False,
                    "message": f"Deployment validation failed: {error_msg}",
                }
            )

    except FileNotFoundError:
        return json.dumps(
            {
                "success": False,
                "message": "Azure CLI not found.",
            }
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "success": False,
                "message": "Deployment validation timed out after 120s.",
            }
        )


def check_region_availability(region: str, provider: str, resource_type: str) -> str:
    """Check if a resource type is available in the specified Azure region.

    Args:
        region: Azure region (e.g., 'eastus2').
        provider: Resource provider (e.g., 'Microsoft.App').
        resource_type: Resource type (e.g., 'containerApps').

    Returns:
        JSON string with availability result.
    """
    logger.info(
        "tool.check_region",
        region=region,
        provider=provider,
        resource_type=resource_type,
    )

    try:
        proc = subprocess.run(
            [
                "az",
                "provider",
                "show",
                "--namespace",
                provider,
                "--query",
                f"resourceTypes[?resourceType=='{resource_type}'].locations[]",
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if proc.returncode == 0:
            locations = json.loads(proc.stdout)
            # Normalize region names for comparison
            normalized = [loc.lower().replace(" ", "") for loc in locations]
            is_available = region.lower().replace(" ", "") in normalized

            return json.dumps(
                {
                    "available": is_available,
                    "region": region,
                    "provider": provider,
                    "resource_type": resource_type,
                    "available_regions_count": len(locations),
                }
            )
        else:
            return json.dumps(
                {
                    "available": False,
                    "message": f"Failed to query provider: {proc.stderr.strip()}",
                }
            )

    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return json.dumps(
            {
                "available": False,
                "message": str(e),
            }
        )


# Tool definitions for agent registration
AZURE_VALIDATOR_TOOLS = [
    {
        "name": "validate_bicep",
        "description": "Validate a Bicep infrastructure-as-code template for syntax and semantic errors.",
        "parameters": {
            "type": "object",
            "properties": {
                "template_path": {
                    "type": "string",
                    "description": "Path to the .bicep file to validate.",
                }
            },
            "required": ["template_path"],
        },
        "function": validate_bicep,
    },
    {
        "name": "validate_deployment",
        "description": "Validate an Azure deployment using az deployment group validate.",
        "parameters": {
            "type": "object",
            "properties": {
                "resource_group": {
                    "type": "string",
                    "description": "Azure resource group name.",
                },
                "template_path": {
                    "type": "string",
                    "description": "Path to the main Bicep template.",
                },
                "parameters_path": {
                    "type": "string",
                    "description": "Path to parameters file (optional).",
                },
            },
            "required": ["resource_group", "template_path"],
        },
        "function": validate_deployment,
    },
    {
        "name": "check_region_availability",
        "description": "Check if an Azure resource type is available in a specific region.",
        "parameters": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Azure region, e.g. 'eastus2'.",
                },
                "provider": {
                    "type": "string",
                    "description": "Resource provider namespace, e.g. 'Microsoft.App'.",
                },
                "resource_type": {
                    "type": "string",
                    "description": "Resource type, e.g. 'containerApps'.",
                },
            },
            "required": ["region", "provider", "resource_type"],
        },
        "function": check_region_availability,
    },
]
