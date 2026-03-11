// ===================================================================
// Azure Monitor Dashboard Module
// Auto-generated observability dashboard with KQL tiles.
// Project: enterprise-grade-real-time
// ===================================================================

@description('Azure region')
param location string

@description('Dashboard display name')
param dashboardName string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Resource tags')
param tags object = {}

resource dashboard 'Microsoft.Portal/dashboards@2020-09-01-preview' = {
  name: dashboardName
  location: location
  tags: tags
  properties: {
    lenses: [
      {
        order: 0
        parts: [
          // -- Request throughput tile --
          {
            position: { x: 0, y: 0, colSpan: 6, rowSpan: 4 }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              inputs: [
                { name: 'resourceTypeMode', value: 'workspace' }
                { name: 'ComponentId', value: logAnalyticsWorkspaceId }
                { name: 'Query', value: 'ContainerAppConsoleLogs_CL | where TimeGenerated > ago(1h) | summarize RequestCount=count() by bin(TimeGenerated, 5m) | render timechart' }
                { name: 'TimeRange', value: 'PT1H' }
                { name: 'PartTitle', value: 'Request Throughput (5m bins)' }
              ]
            }
          }
          // -- P95 latency tile --
          {
            position: { x: 6, y: 0, colSpan: 6, rowSpan: 4 }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              inputs: [
                { name: 'resourceTypeMode', value: 'workspace' }
                { name: 'ComponentId', value: logAnalyticsWorkspaceId }
                { name: 'Query', value: 'ContainerAppConsoleLogs_CL | where TimeGenerated > ago(1h) | extend duration_ms = todouble(extract("duration_ms=([\\d.]+)", 1, Log_s)) | summarize p50=percentile(duration_ms, 50), p95=percentile(duration_ms, 95), p99=percentile(duration_ms, 99) by bin(TimeGenerated, 5m) | render timechart' }
                { name: 'TimeRange', value: 'PT1H' }
                { name: 'PartTitle', value: 'Response Latency Percentiles' }
              ]
            }
          }
          // -- Error rate tile --
          {
            position: { x: 0, y: 4, colSpan: 6, rowSpan: 4 }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              inputs: [
                { name: 'resourceTypeMode', value: 'workspace' }
                { name: 'ComponentId', value: logAnalyticsWorkspaceId }
                { name: 'Query', value: 'ContainerAppConsoleLogs_CL | where TimeGenerated > ago(24h) | extend statusCode = toint(extract("status_code=([\\d]+)", 1, Log_s)) | summarize Total=count(), Errors=countif(statusCode >= 400) by bin(TimeGenerated, 15m) | extend ErrorRate = round(100.0 * Errors / Total, 2) | render timechart' }
                { name: 'TimeRange', value: 'P1D' }
                { name: 'PartTitle', value: 'Error Rate % (24h)' }
              ]
            }
          }
          // -- Container replica count tile --
          {
            position: { x: 6, y: 4, colSpan: 6, rowSpan: 4 }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              inputs: [
                { name: 'resourceTypeMode', value: 'workspace' }
                { name: 'ComponentId', value: logAnalyticsWorkspaceId }
                { name: 'Query', value: 'ContainerAppSystemLogs_CL | where TimeGenerated > ago(1h) | where RevisionName_s != "" | summarize ReplicaCount=dcount(ContainerName_s) by bin(TimeGenerated, 5m) | render timechart' }
                { name: 'TimeRange', value: 'PT1H' }
                { name: 'PartTitle', value: 'Active Replicas' }
              ]
            }
          }
        ]
      }
    ]
  }
}

output dashboardId string = dashboard.id
output dashboardName string = dashboard.name
