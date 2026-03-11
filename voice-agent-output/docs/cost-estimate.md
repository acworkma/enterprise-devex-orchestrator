# Estimated Monthly Cost

> These are **approximate baseline** costs for a dev-tier workload.
> Actual costs vary with usage, region, and reserved pricing.

| Resource | SKU / Tier | Est. Monthly (USD) | Notes |
|----------|-----------|--------------------:|-------|
| Container App | 0.5 vCPU / 1 GiB | $30.00 | Always-on min replica |
| Container Registry | Standard | $5.00 |  |
| Log Analytics | Pay-per-GB | $2.76 | ~1 GB/mo ingest |
| Managed Identity | Free | $0.00 |  |
| Key Vault | Standard | $0.03 | Low operation volume |
| Cosmos DB | Serverless | $0.25 | Low RU usage |
| Azure Cache for Redis | Basic C0 | $16.00 | 250 MB |
| **Total** | | **$54.04** | |

*Prices are approximate USD baseline for East US. Use the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) for detailed estimates.*