# Dashboard KQL Queries -- enterprise-grade-real-time

> Copy these into **Log Analytics > Logs** for ad-hoc analysis.

## Request Throughput (5-minute bins)

```kql
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(1h)
| summarize RequestCount=count() by bin(TimeGenerated, 5m)
| render timechart
```

## Response Latency Percentiles

```kql
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(1h)
| extend duration_ms = todouble(extract("duration_ms=([\\d.]+)", 1, Log_s))
| summarize
    p50=percentile(duration_ms, 50),
    p95=percentile(duration_ms, 95),
    p99=percentile(duration_ms, 99)
  by bin(TimeGenerated, 5m)
| render timechart
```

## Error Rate (24h)

```kql
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(24h)
| extend statusCode = toint(extract("status_code=([\\d]+)", 1, Log_s))
| summarize Total=count(), Errors=countif(statusCode >= 400) by bin(TimeGenerated, 15m)
| extend ErrorRate = round(100.0 * Errors / Total, 2)
| render timechart
```

## Active Container Replicas

```kql
ContainerAppSystemLogs_CL
| where TimeGenerated > ago(1h)
| where RevisionName_s != ""
| summarize ReplicaCount=dcount(ContainerName_s) by bin(TimeGenerated, 5m)
| render timechart
```
