"""Cost Estimator -- provides Azure monthly cost estimates.

Produces a rough cost breakdown for each Azure resource in the architecture plan.
Uses published Azure pricing baselines (not live API) so estimates are directional,
not exact. Useful for budget planning and comparing compute targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.orchestrator.intent_schema import ComputeTarget, DataStore, IntentSpec, PlanOutput
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


# -- Baseline monthly pricing (USD, lowest tier, dev workload) -------
# These are approximate starting prices; actual cost depends on usage.
_BASELINE_PRICES: dict[str, dict[str, float]] = {
    "container_apps": {
        "compute": 30.0,         # ~0.5 vCPU, 1 GiB, always-on
        "environment": 0.0,      # included
    },
    "app_service": {
        "B1_plan": 13.14,        # Basic B1
        "B2_plan": 26.28,        # Basic B2
        "S1_plan": 69.35,        # Standard S1
    },
    "functions": {
        "consumption": 0.0,      # free tier: 1M executions, 400K GB-s
        "premium_EP1": 146.00,   # Elastic Premium EP1
    },
    "log_analytics": {
        "workspace": 2.76,       # first 5 GB/month free; ~$2.76/GB
    },
    "managed_identity": {
        "identity": 0.0,         # free
    },
    "keyvault": {
        "standard": 0.03,        # per 10K operations
    },
    "container_registry": {
        "standard": 5.00,        # Standard SKU
    },
    "blob_storage": {
        "hot_lrs": 2.08,         # per 100 GB hot LRS
    },
    "cosmos_db": {
        "serverless": 0.25,      # per 1M RUs
    },
    "sql": {
        "basic": 4.90,           # Basic DTU
    },
    "redis": {
        "basic_C0": 16.00,       # Basic C0 250 MB
    },
}


@dataclass
class CostLineItem:
    """A single line item in the cost estimate."""

    resource: str
    sku: str
    monthly_usd: float
    notes: str = ""


@dataclass
class CostEstimate:
    """Aggregate cost estimate for the full architecture."""

    items: list[CostLineItem] = field(default_factory=list)

    @property
    def total_monthly(self) -> float:
        return sum(item.monthly_usd for item in self.items)

    def to_markdown(self) -> str:
        lines = [
            "# Estimated Monthly Cost",
            "",
            "> These are **approximate baseline** costs for a dev-tier workload.",
            "> Actual costs vary with usage, region, and reserved pricing.",
            "",
            "| Resource | SKU / Tier | Est. Monthly (USD) | Notes |",
            "|----------|-----------|--------------------:|-------|",
        ]
        for item in self.items:
            lines.append(
                f"| {item.resource} | {item.sku} | ${item.monthly_usd:,.2f} | {item.notes} |"
            )
        lines.append(f"| **Total** | | **${self.total_monthly:,.2f}** | |")
        lines.append("")
        lines.append("*Prices are approximate USD baseline for East US. "
                      "Use the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) "
                      "for detailed estimates.*")
        return "\n".join(lines)


class CostEstimator:
    """Estimates monthly Azure cost for a given IntentSpec and PlanOutput."""

    def estimate(self, spec: IntentSpec, plan: PlanOutput) -> CostEstimate:
        logger.info("cost_estimator.start", project=spec.project_name)
        items: list[CostLineItem] = []

        # Compute target
        compute = getattr(spec, "compute_target", ComputeTarget.CONTAINER_APPS)
        if compute == ComputeTarget.APP_SERVICE:
            items.append(CostLineItem("App Service Plan", "B1 Linux", 13.14, "Basic tier"))
        elif compute == ComputeTarget.FUNCTIONS:
            items.append(CostLineItem("Function App", "Consumption", 0.00, "1M free executions/mo"))
        else:
            items.append(CostLineItem("Container App", "0.5 vCPU / 1 GiB", 30.00, "Always-on min replica"))
            items.append(CostLineItem("Container Registry", "Standard", 5.00, ""))

        # Core infra (always present)
        items.append(CostLineItem("Log Analytics", "Pay-per-GB", 2.76, "~1 GB/mo ingest"))
        items.append(CostLineItem("Managed Identity", "Free", 0.00, ""))
        items.append(CostLineItem("Key Vault", "Standard", 0.03, "Low operation volume"))

        # Data stores
        for ds in spec.data_stores:
            if ds == DataStore.BLOB_STORAGE:
                items.append(CostLineItem("Blob Storage", "Hot LRS", 2.08, "~100 GB"))
            elif ds == DataStore.COSMOS_DB:
                items.append(CostLineItem("Cosmos DB", "Serverless", 0.25, "Low RU usage"))
            elif ds == DataStore.SQL:
                items.append(CostLineItem("Azure SQL", "Basic DTU", 4.90, "5 DTU"))
            elif ds == DataStore.REDIS:
                items.append(CostLineItem("Azure Cache for Redis", "Basic C0", 16.00, "250 MB"))

        logger.info("cost_estimator.complete", total=sum(i.monthly_usd for i in items))
        return CostEstimate(items=items)
