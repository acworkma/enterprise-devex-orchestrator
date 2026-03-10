"""Enterprise DevEx Orchestrator -- CLI Entrypoint.

Usage:
    devex init                          # Create intent.md template
    devex scaffold --file intent.md     # Generate from intent file
    devex scaffold "Build a secure ..." # Generate from inline intent
    devex upgrade --file intent.v2.md   # Safe versioned upgrade
    devex validate --path ./out
    devex history ./out                 # Show version history
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.orchestrator.agents.architecture_planner import ArchitecturePlannerAgent
from src.orchestrator.agents.governance_reviewer import GovernanceReviewerAgent
from src.orchestrator.agents.infra_generator import InfrastructureGeneratorAgent
from src.orchestrator.agents.intent_parser import IntentParserAgent
from src.orchestrator.config import AppConfig, get_config
from src.orchestrator.intent_file import IntentFileParser, generate_intent_template, generate_upgrade_template
from src.orchestrator.intent_schema import GovernanceReport, IntentSpec, PlanOutput
from src.orchestrator.logging import get_logger, setup_logging
from src.orchestrator.planning import PersistentPlanner
from src.orchestrator.prompts.generator import PromptGenerator
from src.orchestrator.skills.registry import create_default_registry
from src.orchestrator.standards.waf import WAFAlignmentReport
from src.orchestrator.state import StateManager
from src.orchestrator.versioning import VersionManager

if TYPE_CHECKING:
    from src.orchestrator.intent_file import IntentFileResult

console = Console()
logger = get_logger(__name__)


def _banner() -> None:
    """Print startup banner."""
    console.print(
        Panel.fit(
            "[bold cyan]Enterprise DevEx Orchestrator Agent[/]\n[dim]Powered by GitHub Copilot SDK[/]",
            border_style="cyan",
        )
    )


def _load_config() -> AppConfig:
    """Load configuration from environment."""
    try:
        return get_config()
    except Exception as exc:
        console.print(f"[red]Configuration error:[/] {exc}")
        console.print("[dim]Ensure .env is configured. See .env.example[/]")
        sys.exit(1)


def _run_pipeline(
    intent: str,
    config: AppConfig,
    output_dir: Path | None = None,
    plan_only: bool = False,
) -> tuple[IntentSpec, PlanOutput, GovernanceReport, WAFAlignmentReport]:
    """Execute the full agent pipeline."""
    setup_logging(level=config.log_level)

    # -- Initialize advanced subsystems ------------------------------
    # Prompt Generator: scan codebase for context-aware prompts
    prompt_gen = PromptGenerator()
    if output_dir and output_dir.exists():
        try:
            prompt_gen.scan(output_dir)
            logger.info(
                "pipeline.codebase_scanned", files=prompt_gen.scan_result.total_files if prompt_gen.scan_result else 0
            )
        except Exception:
            logger.debug("pipeline.codebase_scan_skipped")

    # Skills Registry: pluggable capability routing
    skill_registry = create_default_registry()
    logger.info("pipeline.skills_loaded", count=len(skill_registry.list_skills()))

    # Persistent Planner: resumable checkpointed execution
    planner_mgr: PersistentPlanner | None = None
    if output_dir:
        planner_mgr = PersistentPlanner(output_dir)
        plan_state = planner_mgr.create_pipeline_plan(intent, project_name="")
        logger.info("pipeline.plan_created", tasks=len(plan_state.tasks), progress=f"{plan_state.progress_pct:.0f}%")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Phase 1: Parse Intent
        task = progress.add_task("[cyan]Parsing business intent...", total=None)
        parser = IntentParserAgent(config)
        spec = parser.parse(intent)
        if planner_mgr:
            planner_mgr.execute_task("parse-intent", handler=lambda: {"summary": f"Parsed: {spec.project_name}"})
        progress.update(task, completed=True, description="[green][ok] Intent parsed")

        _show_intent_summary(spec)

        # Phase 2: Architecture Planning
        task = progress.add_task("[cyan]Planning architecture...", total=None)
        planner = ArchitecturePlannerAgent(config)
        plan = planner.plan(spec)
        if planner_mgr:
            planner_mgr.execute_task(
                "plan-architecture", handler=lambda: {"summary": f"{len(plan.components)} components"}
            )
        progress.update(task, completed=True, description="[green][ok] Architecture planned")

        _show_plan_summary(plan)

        # Phase 3: Governance Review
        task = progress.add_task("[cyan]Validating governance...", total=None)
        reviewer = GovernanceReviewerAgent(config)
        gov_report = reviewer.validate_plan(spec, plan)
        if planner_mgr:
            planner_mgr.execute_task("validate-governance", handler=lambda: {"summary": gov_report.status})
        progress.update(task, completed=True, description="[green][ok] Governance validated")

        _show_governance_summary(gov_report)

        # Phase 3b: WAF Assessment
        task = progress.add_task("[cyan]Assessing WAF alignment...", total=None)
        waf_report = reviewer.assess_waf(spec, plan, gov_report)
        if planner_mgr:
            planner_mgr.execute_task(
                "assess-waf", handler=lambda: {"summary": f"{waf_report.coverage_pct:.0f}% coverage"}
            )
        progress.update(
            task,
            completed=True,
            description=f"[green][ok] WAF assessed ({waf_report.coverage_pct:.0f}% coverage)",
        )

        _show_waf_summary(waf_report)

        # Phase 4: Generate Infrastructure (if not plan-only)
        if not plan_only and output_dir:
            task = progress.add_task("[cyan]Generating infrastructure...", total=None)
            generator = InfrastructureGeneratorAgent(config)
            files = generator.generate(spec, plan, gov_report, waf_report)

            # Checkpoint generation tasks
            if planner_mgr:
                for task_id in (
                    "generate-bicep",
                    "generate-cicd",
                    "generate-app",
                    "generate-tests",
                    "generate-alerts",
                    "generate-docs",
                ):
                    planner_mgr.execute_task(task_id, handler=lambda: {"summary": "generated"})

            # Write .devex metadata so `validate` can re-load later
            meta_dir = output_dir / ".devex"
            meta_dir.mkdir(parents=True, exist_ok=True)
            (meta_dir / "spec.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")
            (meta_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
            (meta_dir / "governance.json").write_text(gov_report.model_dump_json(indent=2), encoding="utf-8")

            # Write files to disk
            written = _write_files(files, output_dir)

            # Record generation state for drift detection
            state_mgr = StateManager(output_dir)
            state_mgr.record_generation(
                intent=intent,
                project_name=spec.project_name,
                environment=spec.environment or "dev",
                region=spec.azure_region or config.azure.location,
                governance_status=gov_report.status,
                files=files,
            )

            progress.update(
                task,
                completed=True,
                description=f"[green][ok] Generated {written} files",
            )

            _show_file_tree(output_dir)

    return spec, plan, gov_report, waf_report


def _show_intent_summary(spec: IntentSpec) -> None:
    """Display parsed intent summary."""
    table = Table(title="Parsed Intent", border_style="cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Project", spec.project_name)
    table.add_row("App Type", spec.app_type.value)
    table.add_row("Data Stores", ", ".join(d.value for d in spec.data_stores))
    table.add_row("Auth", spec.security.auth_model.value)
    table.add_row("Compliance", spec.security.compliance_framework.value)
    table.add_row("Region", spec.azure_region)
    table.add_row("Environment", spec.environment)
    table.add_row("Confidence", f"{spec.confidence:.0%}")

    console.print()
    console.print(table)


def _show_plan_summary(plan: PlanOutput) -> None:
    """Display architecture plan summary."""
    table = Table(title="Architecture Plan", border_style="green")
    table.add_column("Component", style="bold")
    table.add_column("Azure Service")
    table.add_column("Purpose")

    for c in plan.components:
        table.add_row(c.name, c.azure_service, c.purpose)

    console.print()
    console.print(table)
    console.print(f"  [dim]{len(plan.decisions)} ADRs | {len(plan.threat_model)} threats modeled[/]")


def _show_governance_summary(report: GovernanceReport) -> None:
    """Display governance validation summary."""
    status_color = {
        "PASS": "green",
        "FAIL": "red",
        "PASS_WITH_WARNINGS": "yellow",
    }
    color = status_color.get(report.status, "white")

    console.print()
    console.print(
        Panel(
            f"[bold {color}]{report.status}[/]\n\n"
            f"{report.summary}\n\n"
            f"Checks: [green]{len([c for c in report.checks if c.passed])} passed[/] | "
            f"[red]{len([c for c in report.checks if not c.passed])} failed[/]",
            title="Governance Report",
            border_style=color,
        )
    )

    if report.recommendations:
        for r in report.recommendations:
            console.print(f"  [yellow]->[/] {r}")


def _show_waf_summary(waf_report: WAFAlignmentReport) -> None:
    """Display WAF alignment summary with pillar scores."""
    table = Table(title="WAF Alignment", border_style="blue")
    table.add_column("Pillar", style="bold")
    table.add_column("Covered", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Score", justify="right")

    for pillar, scores in waf_report.pillar_scores().items():
        pct = scores["pct"]
        if pct >= 80:
            color = "green"
        elif pct >= 50:
            color = "yellow"
        else:
            color = "red"
        table.add_row(
            pillar.value,
            str(scores["covered"]),
            str(scores["total"]),
            f"[{color}]{pct:.0f}%[/]",
        )

    console.print()
    console.print(table)
    console.print(
        f"  [bold]Overall:[/] {waf_report.covered_count}/{waf_report.total_principles} "
        f"principles ({waf_report.coverage_pct:.0f}%)"
    )

    gaps = waf_report.gaps()
    if gaps:
        console.print(f"  [dim]{len(gaps)} gap(s) -- see docs/waf-report.md for details[/]")


def _write_files(files: dict[str, str], output_dir: Path) -> int:
    """Write generated files to disk."""
    written = 0
    for rel_path, content in files.items():
        full_path = output_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        written += 1
        logger.info("file.written", path=str(full_path))
    return written


def _show_file_tree(output_dir: Path) -> None:
    """Display generated file tree."""
    console.print()
    console.print(f"[bold]Generated files in [cyan]{output_dir}[/cyan]:[/]")

    for root, _dirs, filenames in os.walk(output_dir):
        root_path = Path(root)
        level = len(root_path.relative_to(output_dir).parts)
        indent = "  " * level
        console.print(f"  {indent}[bold]{root_path.name}/[/]")
        sub_indent = "  " * (level + 1)
        for f in sorted(filenames):
            console.print(f"  {sub_indent}[dim]{f}[/]")


def _show_improvement_suggestions(
    spec: IntentSpec,
    plan: PlanOutput,
    gov_report: GovernanceReport,
    waf_report: WAFAlignmentReport,
) -> None:
    """Display a summary of improvement suggestions after generation."""
    from src.orchestrator.generators.docs_generator import DocsGenerator

    docs_gen = DocsGenerator()
    suggestions = docs_gen.generate_improvement_suggestions(spec, plan, gov_report, waf_report)

    if not suggestions:
        console.print("\n  [green]No improvements identified -- architecture is well-defined.[/]")
        return

    console.print(
        Panel.fit(
            f"[bold yellow]Improvement Suggestions ({len(suggestions)})[/]\n\n"
            + "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(suggestions[:8]))
            + (
                f"\n  [dim]... and {len(suggestions) - 8} more (see docs/improvement-suggestions.md)[/]"
                if len(suggestions) > 8
                else ""
            )
            + "\n\n[dim]Review docs/improvement-suggestions.md, update intent.md, and re-run.[/]",
            border_style="yellow",
            title="Next Iteration",
        )
    )


def _resolve_intent(intent: str | None, intent_file: str | None) -> str:
    """Resolve intent string from CLI arg or --file flag."""
    if intent_file:
        parser = IntentFileParser()
        result = parser.parse(intent_file)
        console.print(f"  [dim]Read intent from {intent_file}[/]")
        if result.project_name:
            console.print(f"  [dim]Project: {result.project_name}[/]")
        if result.version_info.version > 1:
            console.print(
                f"  [dim]Version: {result.version_info.version} (based on v{result.version_info.based_on})[/]"
            )
        return result.full_intent
    if intent:
        return intent
    console.print("[red]Error:[/] Provide INTENT as an argument or use --file intent.md")
    sys.exit(1)


def _resolve_intent_with_meta(intent: str | None, intent_file: str | None) -> tuple[str, IntentFileResult | None]:
    """Resolve intent and also return parsed file metadata (if from file)."""
    if intent_file:
        parser = IntentFileParser()
        result = parser.parse(intent_file)
        console.print(f"  [dim]Read intent from {intent_file}[/]")
        if result.project_name:
            console.print(f"  [dim]Project: {result.project_name}[/]")
        if result.version_info.version > 1:
            console.print(
                f"  [dim]Version: v{result.version_info.version} (upgrade from v{result.version_info.based_on})[/]"
            )

        # Show enterprise requirements completeness
        completeness = result.completeness_pct
        filled = result.enterprise_sections_filled
        filled_count = sum(1 for v in filled.values() if v)
        total_count = len(filled)
        colour = "green" if completeness >= 80 else "yellow" if completeness >= 50 else "red"
        console.print(
            f"  [{colour}]Requirements completeness: {completeness:.0f}% "
            f"({filled_count}/{total_count} sections)[/{colour}]"
        )
        if completeness < 100:
            missing = [k.replace("_", " ").title() for k, v in filled.items() if not v]
            console.print(f"  [dim]Missing: {', '.join(missing)}[/]")

        return result.full_intent, result
    if intent:
        return intent, None
    console.print("[red]Error:[/] Provide INTENT as an argument or use --file intent.md")
    sys.exit(1)


# ----------------- CLI Commands -----------------


@click.group()
@click.version_option(version="1.1.0", prog_name="Enterprise DevEx Orchestrator")
def cli() -> None:
    """Enterprise DevEx Orchestrator Agent.

    Transform business intent into production-ready, secure, deployable
    Azure workloads -- powered by GitHub Copilot SDK.
    """
    pass


@cli.command()
@click.argument("intent", required=False, default=None)
@click.option(
    "--file",
    "-f",
    "intent_file",
    type=click.Path(),
    default=None,
    help="Path to an intent .md file (e.g., intent.md). Overrides INTENT argument.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output directory for docs only. Defaults to ./out",
)
@click.option(
    "--format",
    "-F",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def plan(intent: str | None, intent_file: str | None, output: str | None, output_format: str) -> None:
    """Parse intent and generate architecture plan (no infrastructure).

    INTENT is the business requirement in plain English (quoted string).
    Alternatively, use --file to read from an intent.md file.

    Example:
        devex plan "Build a secure REST API with blob storage"
        devex plan --file intent.md
    """
    _banner()
    config = _load_config()
    out_dir = Path(output) if output else Path("out")

    # Resolve intent from file or argument
    intent_str = _resolve_intent(intent, intent_file)

    spec, architecture_plan, gov_report, waf_report = _run_pipeline(
        intent=intent_str,
        config=config,
        output_dir=out_dir,
        plan_only=True,
    )

    if output_format == "json":
        result = {
            "spec": spec.model_dump(mode="json"),
            "plan": architecture_plan.model_dump(mode="json"),
            "governance": gov_report.model_dump(mode="json"),
            "waf": {
                "coverage_pct": waf_report.coverage_pct,
                "covered": waf_report.covered_count,
                "total": waf_report.total_principles,
                "pillar_scores": {p.value: s for p, s in waf_report.pillar_scores().items()},
            },
        }
        console.print_json(json.dumps(result, indent=2))

    console.print("\n[green bold][ok] Plan complete.[/] Run `devex scaffold` to generate full infrastructure.\n")


@cli.command()
@click.argument("intent", required=False, default=None)
@click.option(
    "--file",
    "-f",
    "intent_file",
    type=click.Path(),
    default=None,
    help="Path to an intent .md file. Overrides INTENT argument.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="out",
    help="Output directory for all generated artifacts. Default: ./out",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be generated without writing files.",
)
def scaffold(intent: str | None, intent_file: str | None, output: str, dry_run: bool) -> None:
    """Generate full production scaffold from business intent.

    INTENT is the business requirement in plain English (quoted string).
    Alternatively, use --file to read from an intent.md file.

    Runs the complete pipeline: parse -> plan -> govern -> generate.

    Example:
        devex scaffold "Build a secure REST API with blob storage" -o ./my-project
        devex scaffold --file intent.md -o ./my-project
    """
    _banner()
    config = _load_config()
    out_dir = Path(output)

    if dry_run:
        console.print("[yellow]Dry run mode -- no files will be written.[/]\n")

    start = time.time()

    # Resolve intent from file or argument
    intent_str, parsed_intent = _resolve_intent_with_meta(intent, intent_file)

    spec, architecture_plan, gov_report, waf_report = _run_pipeline(
        intent=intent_str,
        config=config,
        output_dir=None if dry_run else out_dir,
        plan_only=dry_run,
    )

    elapsed = time.time() - start

    if not dry_run:
        # Also write the plan data as JSON for programmatic use
        meta_dir = out_dir / ".devex"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "spec.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        (meta_dir / "plan.json").write_text(architecture_plan.model_dump_json(indent=2), encoding="utf-8")
        (meta_dir / "governance.json").write_text(gov_report.model_dump_json(indent=2), encoding="utf-8")

        # Record version if using file-based intent
        if parsed_intent:
            vm = VersionManager(out_dir)
            file_count = len(list(out_dir.rglob("*")))
            vm.record_version(parsed_intent, file_count, gov_report.status)
            console.print(f"  [cyan]Version {parsed_intent.version_info.version} recorded[/]")

    console.print(f"\n[green bold][ok] Scaffold complete[/] in {elapsed:.1f}s")
    if not dry_run:
        console.print(f"  Output: [cyan]{out_dir.resolve()}[/]")

        # Show persistent planner summary
        planner_mgr = PersistentPlanner(out_dir)
        summary = planner_mgr.get_plan_summary()
        if summary.get("status") != "no_plan":
            console.print(
                f"  Plan progress: {summary.get('progress_pct', 0):.0f}% | "
                f"Tasks: {json.dumps(summary.get('task_counts', {}))}"
            )

        console.print(
            "\n  Next steps:\n"
            f"    cd {out_dir}\n"
            "    az deployment group validate \\\n"
            "      --resource-group <rg> \\\n"
            "      --template-file infra/bicep/main.bicep \\\n"
            "      --parameters infra/bicep/parameters/dev.parameters.json\n"
        )

        # Show improvement suggestions summary
        _show_improvement_suggestions(spec, architecture_plan, gov_report, waf_report)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def validate(path: str) -> None:
    """Validate a previously generated scaffold against governance policies.

    PATH is the directory of a generated scaffold.

    Example:
        devex validate ./out
    """
    _banner()
    config = _load_config()
    out_dir = Path(path)

    # Load spec and plan from metadata
    meta_dir = out_dir / ".devex"
    if not meta_dir.exists():
        console.print("[red]Error:[/] No .devex metadata found. Was this scaffold generated by devex?")
        sys.exit(1)

    spec = IntentSpec.model_validate_json((meta_dir / "spec.json").read_text(encoding="utf-8"))
    plan = PlanOutput.model_validate_json((meta_dir / "plan.json").read_text(encoding="utf-8"))

    # Read Bicep files for validation
    bicep_dir = out_dir / "infra" / "bicep"
    bicep_files: dict[str, str] = {}
    if bicep_dir.exists():
        for f in bicep_dir.rglob("*.bicep"):
            bicep_files[str(f.relative_to(out_dir))] = f.read_text(encoding="utf-8")

    reviewer = GovernanceReviewerAgent(config)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Running governance validation...", total=None)

        plan_report = reviewer.validate_plan(spec, plan)
        bicep_report = reviewer.validate_bicep(bicep_files)

        progress.update(task, completed=True, description="[green][ok] Validation complete")

    _show_governance_summary(plan_report)

    if bicep_report.checks:
        console.print()
        console.print("[bold]Bicep Security Scan:[/]")
        for c in bicep_report.checks:
            icon = "[PASS]" if c.passed else "[FAIL]"
            console.print(f"  {icon} [{c.severity}] {c.name}: {c.details}")

    # Drift detection
    state_mgr = StateManager(out_dir)
    if state_mgr.get_generation_count() > 0:
        drift = state_mgr.detect_drift(
            intent="",  # no new intent during validate
            environment=spec.environment or "dev",
            region=spec.azure_region or config.azure.location,
        )
        if drift.has_drift:
            console.print()
            console.print("[bold yellow]Drift Detection:[/]")
            console.print(f"  {drift.summary}")
            if drift.modified_files:
                for f in drift.modified_files:
                    console.print(f"  [yellow]~ {f}[/]")
            if drift.added_files:
                for f in drift.added_files:
                    console.print(f"  [green]+ {f}[/]")
            if drift.removed_files:
                for f in drift.removed_files:
                    console.print(f"  [red]- {f}[/]")
        else:
            console.print("\n[green][ok] No file drift detected.[/]")

        last = state_mgr.get_last_event()
        if last:
            console.print(f"  Last generated: {last.timestamp}")
            console.print(f"  Generation count: {state_mgr.get_generation_count()}")

    # Combined status
    all_passed = plan_report.status != "FAIL" and bicep_report.status != "FAIL"
    if all_passed:
        console.print("\n[green bold][ok] All governance checks passed.[/]\n")
    else:
        console.print("\n[red bold][x] Governance validation failed. Fix issues above.[/]\n")
        sys.exit(1)


@cli.command()
def version() -> None:
    """Show version and environment info."""
    console.print("[bold]Enterprise DevEx Orchestrator Agent[/]")
    console.print("  Version:  1.0.0")
    console.print(f"  Python:   {sys.version.split()[0]}")
    console.print(f"  Platform: {sys.platform}")

    try:
        config = get_config()
        console.print(
            "  LLM:      azure_openai"
            if config.llm.azure_openai_endpoint
            else "  LLM:      copilot_sdk"
            if config.copilot.github_token
            else "  LLM:      template-only"
        )
        console.print(f"  Model:    {config.llm.azure_openai_deployment}")
        console.print(f"  Region:   {config.azure.location}")
    except Exception:
        console.print("  [dim]Config not loaded (.env missing)[/]")


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--resource-group", "-g", required=True, help="Azure resource group name.")
@click.option("--region", "-r", default="eastus2", help="Azure region. Default: eastus2")
@click.option("--subscription", "-s", default="", help="Azure subscription ID.")
@click.option("--dry-run", is_flag=True, default=False, help="Validate and what-if only (no deploy).")
def deploy(path: str, resource_group: str, region: str, subscription: str, dry_run: bool) -> None:
    """Deploy generated infrastructure to Azure.

    PATH is the directory of a generated scaffold.

    Runs staged deployment: validate -> what-if -> deploy -> verify.
    Uses automatic error classification and retry for transient failures.

    Example:
        devex deploy ./out -g my-resource-group -r eastus2
    """
    from src.orchestrator.agents.deploy_orchestrator import (
        DeployOrchestrator,
        DeployStatus,
    )

    _banner()
    out_dir = Path(path)

    # Verify scaffold exists
    meta_dir = out_dir / ".devex"
    if not meta_dir.exists():
        console.print("[red]Error:[/] No .devex metadata found. Run `devex scaffold` first.")
        sys.exit(1)

    deployer = DeployOrchestrator(
        output_dir=out_dir,
        resource_group=resource_group,
        region=region,
        subscription=subscription,
    )

    mode = "dry-run" if dry_run else "full"
    console.print(f"[cyan]Deploying infrastructure ({mode})...[/]\n")
    console.print(f"  Resource Group: {resource_group}")
    console.print(f"  Region:         {region}")
    if subscription:
        console.print(f"  Subscription:   {subscription}")
    console.print()

    result = deployer.deploy(dry_run=dry_run)

    # Show stage results
    table = Table(title="Deployment Stages", border_style="cyan")
    table.add_column("Stage", style="bold")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Details")

    for stage in result.stages:
        status_color = "green" if stage.status == DeployStatus.SUCCEEDED else "red"
        details = stage.remediation if stage.error else "OK"
        table.add_row(
            stage.stage.value,
            f"[{status_color}]{stage.status.value}[/]",
            f"{stage.duration_ms:.0f}ms",
            details[:60],
        )

    console.print(table)

    if result.is_success:
        console.print(f"\n[green bold][ok] Deployment succeeded[/] in {result.total_duration_ms:.0f}ms")
    else:
        failed = [s for s in result.stages if s.status == DeployStatus.FAILED]
        for s in failed:
            console.print(f"\n[red]Error ({s.error_category}):[/] {s.error[:200]}")
            if s.remediation:
                console.print(f"  [yellow]Remediation:[/] {s.remediation}")
        console.print("\n[red bold][x] Deployment failed.[/]")
        sys.exit(1)


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=".",
    help="Directory to create intent.md in. Default: current directory.",
)
@click.option(
    "--project",
    "-p",
    default="my-secure-api",
    help="Default project name.",
)
def init(output: str, project: str) -> None:
    """Create an intent.md template to describe your project.

    Generates a starter intent.md file that you can fill in.
    Then run `devex scaffold --file intent.md -o ./my-project` to generate.

    Example:
        devex init
        devex init -o ./my-project -p my-cool-api
    """
    _banner()
    out_dir = Path(output)
    intent_path = out_dir / "intent.md"

    if intent_path.exists():
        console.print(f"[yellow]Warning:[/] {intent_path} already exists.")
        if not click.confirm("Overwrite?"):
            console.print("[dim]Cancelled.[/]")
            return

    out_dir.mkdir(parents=True, exist_ok=True)
    content = generate_intent_template(project_name=project)
    intent_path.write_text(content, encoding="utf-8")

    console.print(f"\n[green bold][ok] Created {intent_path}[/]\n")
    console.print("  Next steps:")
    console.print(f"  1. Edit [cyan]{intent_path}[/] -- describe what you want to build")
    console.print(f"  2. Run: [bold]devex scaffold --file {intent_path} -o ./my-project[/]")
    console.print("  3. Your entire infrastructure is generated and ready!\n")


@cli.command()
@click.option(
    "--file",
    "-f",
    "intent_file",
    type=click.Path(exists=True),
    required=True,
    help="Path to the upgrade intent .md file (e.g., intent.v2.md).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="out",
    help="Output directory of the existing scaffold. Default: ./out",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show upgrade plan without executing.",
)
def upgrade(intent_file: str, output: str, dry_run: bool) -> None:
    """Safely upgrade an existing scaffold with a new version.

    Reads the upgrade intent file, diff's against the existing version,
    and regenerates only what changed. Adds a CI/CD promotion workflow
    for safe, revision-based deployment.

    Example:
        devex upgrade --file intent.v2.md -o ./my-project
    """
    _banner()
    config = _load_config()
    out_dir = Path(output)

    # Verify existing scaffold
    meta_dir = out_dir / ".devex"
    if not meta_dir.exists():
        console.print("[red]Error:[/] No existing scaffold found. Run `devex scaffold` first.")
        sys.exit(1)

    # Parse the upgrade intent file
    parser = IntentFileParser()
    parsed = parser.parse(intent_file)

    if not parsed.version_info.is_upgrade:
        console.print(
            "[yellow]Warning:[/] No 'Based On' version specified in the intent file. "
            "This will be treated as a full regeneration, not an incremental upgrade."
        )

    # Load version manager and create upgrade plan
    vm = VersionManager(out_dir)

    if vm.has_versions:
        plan = vm.plan_upgrade(parsed)

        console.print()
        console.print(
            Panel(
                f"[bold]{plan.summary}[/]\n\n" + "\n".join(f"  * {n}" for n in plan.notes),
                title="Upgrade Plan",
                border_style="cyan",
            )
        )
    else:
        console.print("[dim]No previous version found -- full scaffold will be generated.[/]")

    if dry_run:
        console.print("\n[yellow]Dry run -- no changes applied.[/]")
        return

    # Execute the pipeline with the upgrade intent
    start = time.time()
    intent_str = parsed.full_intent

    spec, architecture_plan, gov_report, waf_report = _run_pipeline(
        intent=intent_str,
        config=config,
        output_dir=out_dir,
        plan_only=False,
    )

    elapsed = time.time() - start

    # Record the new version
    file_count = len(list(out_dir.rglob("*")))
    vm.record_version(parsed, file_count, gov_report.status)

    console.print(f"\n[green bold][ok] Upgrade to v{parsed.version_info.version} complete[/] in {elapsed:.1f}s")
    console.print(f"  Version {parsed.version_info.version} recorded and active")

    # Show version history
    _show_version_history(vm)

    console.print(
        "\n  Next steps:\n"
        "    1. Review the changes in your scaffold\n"
        "    2. Commit and push to trigger CI/CD\n"
        "    3. The promotion workflow deploys as a new Container Apps revision\n"
        "    4. Traffic stays on the previous version until you promote\n"
    )


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def history(path: str) -> None:
    """Show version history for a scaffold.

    PATH is the directory of a generated scaffold.

    Example:
        devex history ./my-project
    """
    _banner()
    out_dir = Path(path)
    vm = VersionManager(out_dir)

    if not vm.has_versions:
        console.print("[dim]No version history found.[/]")
        return

    _show_version_history(vm)


@cli.command(name="new-version")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Where to write the new intent file. Default: <path>/intent.v<N>.md",
)
def new_version(path: str, output: str | None) -> None:
    """Generate a new version intent file based on the current scaffold.

    Pre-fills the upgrade template from the current version's data,
    so you only need to describe what's changing.

    Example:
        devex new-version ./my-project
    """
    _banner()
    out_dir = Path(path)
    vm = VersionManager(out_dir)

    if not vm.has_versions:
        console.print("[red]Error:[/] No version history. Run `devex scaffold` first.")
        sys.exit(1)

    current = vm.get_current()
    if not current:
        console.print("[red]Error:[/] No active version found.")
        sys.exit(1)

    new_v = current.version + 1
    template = generate_upgrade_template(
        project_name=vm.state.project_name or "my-project",
        current_version=current.version,
        current_intent=current.intent,
    )

    if output:
        out_path = Path(output)
    else:
        out_path = out_dir / f"intent.v{new_v}.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template, encoding="utf-8")

    console.print(f"\n[green bold][ok] Created {out_path}[/]\n")
    console.print(f"  Current version: v{current.version}")
    console.print(f"  New version:     v{new_v}\n")
    console.print("  Next steps:")
    console.print(f"  1. Edit [cyan]{out_path}[/] -- describe your changes")
    console.print(f"  2. Run: [bold]devex upgrade --file {out_path} -o {out_dir}[/]")
    console.print("  3. CI/CD promotion workflow keeps v1 safe while v2 deploys\n")


def _show_version_history(vm: VersionManager) -> None:
    """Display version history table."""
    table = Table(title="Version History", border_style="cyan")
    table.add_column("Version", style="bold", justify="right")
    table.add_column("Status")
    table.add_column("Changes")
    table.add_column("Files", justify="right")
    table.add_column("Governance")
    table.add_column("Created")

    for entry in vm.get_history():
        status_color = {
            "active": "green",
            "superseded": "dim",
            "rolled-back": "red",
        }.get(entry["status"], "white")

        table.add_row(
            f"v{entry['version']}",
            f"[{status_color}]{entry['status']}[/]",
            (entry["changes"] or "-")[:40],
            str(entry["files"]),
            entry["governance"] or "-",
            (entry["created_at"] or "-")[:19],
        )

    console.print()
    console.print(table)


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="out",
    help="Output directory. Default: ./out",
)
def interactive(output: str) -> None:
    """Interactively build a project intent through guided questions.

    Walks you through each decision (project name, language, compute target,
    data stores, security, etc.) and generates the scaffold at the end.

    Example:
        devex interactive
        devex interactive -o ./my-project
    """
    _banner()
    console.print(
        "[bold]Interactive mode[/] -- answer a few questions and we'll generate your full production scaffold.\n"
    )

    # -- Project basics ----------------------------------------------
    project_name = click.prompt(
        "Project name (kebab-case, e.g. my-secure-api)",
        default="my-secure-api",
    )
    description = click.prompt(
        "One-sentence description of what you're building",
        default="A secure REST API for enterprise data processing",
    )

    # -- Language ----------------------------------------------------
    language = click.prompt(
        "Programming language",
        type=click.Choice(["python", "node", "dotnet"], case_sensitive=False),
        default="python",
    )

    # -- App Type ----------------------------------------------------
    app_type = click.prompt(
        "Application type",
        type=click.Choice(["api", "web", "worker", "function"], case_sensitive=False),
        default="api",
    )

    # -- Compute Target ----------------------------------------------
    compute = click.prompt(
        "Azure compute target",
        type=click.Choice(["container_apps", "app_service", "functions"], case_sensitive=False),
        default="container_apps",
    )

    # -- Data Stores -------------------------------------------------
    ds_choices = click.prompt(
        "Data stores (comma-separated: blob, cosmos, sql, redis, none)",
        default="blob",
    )
    data_stores_raw = [s.strip().lower() for s in ds_choices.split(",")]
    # -- Security ----------------------------------------------------
    auth = click.prompt(
        "Authentication model",
        type=click.Choice(["managed-identity", "entra-id", "api-key"], case_sensitive=False),
        default="managed-identity",
    )
    compliance = click.prompt(
        "Compliance guidance",
        type=click.Choice(["general", "hipaa", "soc2", "fedramp"], case_sensitive=False),
        default="general",
    )

    # -- Region ------------------------------------------------------
    region = click.prompt("Azure region", default="eastus2")
    environment = click.prompt(
        "Environment",
        type=click.Choice(["dev", "staging", "prod"], case_sensitive=False),
        default="dev",
    )

    # -- Confirmation ------------------------------------------------
    console.print()
    summary = Table(title="Your Configuration", border_style="cyan")
    summary.add_column("Setting", style="bold")
    summary.add_column("Value")
    summary.add_row("Project", project_name)
    summary.add_row("Language", language)
    summary.add_row("App Type", app_type)
    summary.add_row("Compute", compute)
    summary.add_row("Data Stores", ", ".join(data_stores_raw))
    summary.add_row("Auth", auth)
    summary.add_row("Compliance", compliance)
    summary.add_row("Region", region)
    summary.add_row("Environment", environment)
    console.print(summary)
    console.print()

    if not click.confirm("Generate scaffold with these settings?", default=True):
        console.print("[dim]Cancelled.[/]")
        return

    # -- Build intent string -----------------------------------------
    auth_clean = auth.replace("-", " ")
    intent = (
        f"Build a {app_type} called {project_name}: {description}. "
        f"Use {language} with {compute.replace('_', ' ')} compute. "
        f"Data stores: {', '.join(data_stores_raw)}. "
        f"Auth: {auth_clean}. Compliance: {compliance}. "
        f"Region: {region}, environment: {environment}."
    )

    config = _load_config()
    out_dir = Path(output)
    start = time.time()

    spec, plan, gov_report, waf_report = _run_pipeline(
        intent=intent,
        config=config,
        output_dir=out_dir,
    )

    elapsed = time.time() - start
    console.print(f"\n[green bold][ok] Scaffold complete[/] in {elapsed:.1f}s")
    console.print(f"  Output: [cyan]{out_dir.resolve()}[/]\n")
    _show_improvement_suggestions(spec, plan, gov_report, waf_report)


if __name__ == "__main__":
    cli()
