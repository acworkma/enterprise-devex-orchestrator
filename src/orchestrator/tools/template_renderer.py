"""Template Renderer Tool -- renders structured templates from plan output.

Provides tools for the agent runtime to:
    - render_template: Render a named template with plan data
    - list_templates: List available templates
    - preview_output: Show a preview of what would be generated
"""

from __future__ import annotations

import json

from src.orchestrator.generators.app_generator import AppGenerator
from src.orchestrator.generators.bicep_generator import BicepGenerator
from src.orchestrator.generators.cicd_generator import CICDGenerator
from src.orchestrator.generators.docs_generator import DocsGenerator
from src.orchestrator.intent_schema import IntentSpec, PlanOutput
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


def render_template(
    template_name: str,
    spec_json: str,
    plan_json: str,
) -> str:
    """Render a specific template using plan data.

    Args:
        template_name: Name of the template to render (bicep, cicd, app, docs).
        spec_json: JSON string of the IntentSpec.
        plan_json: JSON string of the PlanOutput.

    Returns:
        JSON string with rendered file contents.
    """
    logger.info("tool.render_template", template=template_name)

    try:
        spec = IntentSpec.model_validate_json(spec_json)
        plan = PlanOutput.model_validate_json(plan_json)
    except Exception as e:
        return json.dumps({"error": f"Invalid input data: {e}"})

    generators = {
        "bicep": BicepGenerator,
        "cicd": CICDGenerator,
        "app": AppGenerator,
        "docs": DocsGenerator,
    }

    gen_class = generators.get(template_name.lower())
    if not gen_class:
        return json.dumps({"error": f"Unknown template: {template_name}. Available: {list(generators.keys())}"})

    try:
        gen = gen_class()
        if template_name == "docs" or template_name == "bicep":
            files = gen.generate(spec, plan)
        elif template_name == "cicd" or template_name == "app":
            files = gen.generate(spec)
        else:
            files = {}

        return json.dumps(
            {
                "template": template_name,
                "files": {k: v[:500] + "..." if len(v) > 500 else v for k, v in files.items()},
                "file_count": len(files),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"error": f"Generation failed: {e}"})


def list_templates() -> str:
    """List all available templates.

    Returns:
        JSON string with template catalog.
    """
    templates = [
        {
            "name": "bicep",
            "description": "Azure Bicep infrastructure-as-code templates (main.bicep + modules)",
            "outputs": [
                "infra/bicep/main.bicep",
                "infra/bicep/modules/log-analytics.bicep",
                "infra/bicep/modules/managed-identity.bicep",
                "infra/bicep/modules/keyvault.bicep",
                "infra/bicep/modules/container-registry.bicep",
                "infra/bicep/modules/storage.bicep",
                "infra/bicep/modules/container-app.bicep",
                "infra/bicep/parameters/dev.parameters.json",
            ],
        },
        {
            "name": "cicd",
            "description": "GitHub Actions CI/CD workflows with OIDC authentication",
            "outputs": [
                ".github/workflows/validate.yml",
                ".github/workflows/deploy.yml",
                ".github/dependabot.yml",
                ".github/workflows/codeql.yml",
            ],
        },
        {
            "name": "app",
            "description": "FastAPI application scaffold with Docker support",
            "outputs": [
                "src/app/main.py",
                "src/app/requirements.txt",
                "src/app/Dockerfile",
                "src/app/__init__.py",
            ],
        },
        {
            "name": "docs",
            "description": "Project documentation including plan, security, deployment, and demo script",
            "outputs": [
                "docs/plan.md",
                "docs/security.md",
                "docs/deployment.md",
                "docs/rai-notes.md",
                "docs/demo-script.md",
                "docs/scorecard.md",
                "docs/governance-report.md",
            ],
        },
    ]

    return json.dumps({"templates": templates}, indent=2)


def preview_output(spec_json: str, plan_json: str) -> str:
    """Preview all files that would be generated without writing to disk.

    Args:
        spec_json: JSON string of the IntentSpec.
        plan_json: JSON string of the PlanOutput.

    Returns:
        JSON string with file manifest and sizes.
    """
    logger.info("tool.preview_output")

    try:
        spec = IntentSpec.model_validate_json(spec_json)
        plan = PlanOutput.model_validate_json(plan_json)
    except Exception as e:
        return json.dumps({"error": f"Invalid input data: {e}"})

    all_files: dict[str, int] = {}

    try:
        for gen_class, gen_args in [
            (BicepGenerator, (spec, plan)),
            (CICDGenerator, (spec,)),
            (AppGenerator, (spec,)),
            (DocsGenerator, (spec, plan)),
        ]:
            gen = gen_class()
            files = gen.generate(*gen_args)
            for path, content in files.items():
                all_files[path] = len(content.encode("utf-8"))
    except Exception as e:
        return json.dumps({"error": f"Preview failed: {e}"})

    total_bytes = sum(all_files.values())

    return json.dumps(
        {
            "file_count": len(all_files),
            "total_bytes": total_bytes,
            "total_kb": round(total_bytes / 1024, 1),
            "files": [{"path": path, "bytes": size} for path, size in sorted(all_files.items())],
        },
        indent=2,
    )


# Tool definitions for agent registration
TEMPLATE_RENDERER_TOOLS = [
    {
        "name": "render_template",
        "description": "Render a specific template (bicep, cicd, app, docs) using plan data.",
        "parameters": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Template to render: 'bicep', 'cicd', 'app', or 'docs'.",
                    "enum": ["bicep", "cicd", "app", "docs"],
                },
                "spec_json": {
                    "type": "string",
                    "description": "JSON string of the IntentSpec.",
                },
                "plan_json": {
                    "type": "string",
                    "description": "JSON string of the PlanOutput.",
                },
            },
            "required": ["template_name", "spec_json", "plan_json"],
        },
        "function": render_template,
    },
    {
        "name": "list_templates",
        "description": "List all available infrastructure and documentation templates.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "function": list_templates,
    },
    {
        "name": "preview_output",
        "description": "Preview all files that would be generated, with sizes, without writing to disk.",
        "parameters": {
            "type": "object",
            "properties": {
                "spec_json": {
                    "type": "string",
                    "description": "JSON string of the IntentSpec.",
                },
                "plan_json": {
                    "type": "string",
                    "description": "JSON string of the PlanOutput.",
                },
            },
            "required": ["spec_json", "plan_json"],
        },
        "function": preview_output,
    },
]
