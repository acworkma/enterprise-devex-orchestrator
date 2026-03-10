"""Intent Parser Agent.

Takes raw natural-language business intent and normalizes it into a strict
IntentSpec schema. This is the first agent in the chain.

Responsibilities:
    - Extract project name, description, app type, data stores
    - Identify security requirements (compliance, auth, networking)
    - Determine observability and CI/CD needs
    - Record assumptions and confidence level
"""

from __future__ import annotations

import json
import re

from src.orchestrator.agent import AgentRuntime
from src.orchestrator.config import AppConfig
from src.orchestrator.intent_schema import (
    LANGUAGE_FRAMEWORKS,
    AppType,
    AuthModel,
    CICDRequirements,
    ComplianceFramework,
    ComputeTarget,
    DataStore,
    IntentSpec,
    NetworkingModel,
    ObservabilityRequirements,
    SecurityRequirements,
)
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)

INTENT_PARSER_SYSTEM_PROMPT = """\
You are an Enterprise Intent Parser. Your job is to take a natural-language
business requirement and produce a strict JSON object conforming to the
IntentSpec schema.

## Rules
1. Extract a kebab-case project name from the description (3-39 chars, lowercase, alphanumeric + hyphens).
2. Identify the application type: api, web, worker, or function.
3. Determine data stores needed: blob_storage, cosmos_db, sql, table_storage, or none.
4. Assess security requirements:
   - Auth model: managed_identity (default), entra_id, api_key
   - Compliance: general (default), hipaa_guidance, soc2_guidance, fedramp_guidance
   - Networking: private (default), internal, public_restricted
   - Data classification: confidential (default), internal, public
5. Always enable: encryption_at_rest, encryption_in_transit, secret_management, log_analytics, diagnostic_settings, health_endpoint.
6. Record assumptions you made in the 'assumptions' array.
7. Set confidence between 0.0 and 1.0.
8. If the intent mentions AI/ML, set uses_ai to true.

## Output Format
Return ONLY a JSON object matching the IntentSpec schema. No markdown, no explanation.

## IntentSpec Schema Fields
{
  "project_name": "string (kebab-case)",
  "description": "string (max 200 chars)",
  "raw_intent": "string (original input)",
  "app_type": "api|web|worker|function",
  "language": "python",
  "framework": "fastapi",
  "data_stores": ["blob_storage"],
  "uses_ai": false,
  "security": {
    "auth_model": "managed_identity",
    "compliance_framework": "general",
    "networking": "private",
    "data_classification": "confidential",
    "encryption_at_rest": true,
    "encryption_in_transit": true,
    "secret_management": true,
    "enable_waf": false
  },
  "observability": {
    "log_analytics": true,
    "diagnostic_settings": true,
    "health_endpoint": true,
    "alerts": false,
    "dashboard": false
  },
  "cicd": {
    "validate_on_pr": true,
    "deploy_on_merge": false,
    "manual_deploy": true,
    "oidc_auth": true,
    "artifact_upload": true
  },
  "azure_region": "eastus2",
  "environment": "dev",
  "assumptions": [],
  "decisions": [],
  "open_risks": [],
  "confidence": 0.85
}
"""


class IntentParserAgent:
    """Parses raw business intent into a strict IntentSpec."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.runtime = AgentRuntime(config)

    def parse(self, raw_intent: str) -> IntentSpec:
        """Parse natural-language intent into IntentSpec.

        Uses the Copilot SDK agent to extract structured data. Falls back
        to rule-based parsing if the API is unavailable.
        """
        logger.info("intent_parser.start", intent_length=len(raw_intent))

        try:
            response = self.runtime.run_sync(
                system_prompt=INTENT_PARSER_SYSTEM_PROMPT,
                user_message=raw_intent,
                max_iterations=3,
            )
            spec = self._parse_response(response, raw_intent)
        except Exception as e:
            logger.warning("intent_parser.llm_fallback", error=str(e))
            spec = self._rule_based_parse(raw_intent)

        logger.info(
            "intent_parser.complete",
            project=spec.project_name,
            app_type=spec.app_type.value,
            confidence=spec.confidence,
        )
        return spec

    def _parse_response(self, response: str, raw_intent: str) -> IntentSpec:
        """Parse the LLM response into an IntentSpec."""
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to parse the entire response as JSON
            json_str = response.strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("intent_parser.json_parse_failed")
            return self._rule_based_parse(raw_intent)

        # Ensure raw_intent is preserved
        data["raw_intent"] = raw_intent

        return IntentSpec(**data)

    def _rule_based_parse(self, raw_intent: str) -> IntentSpec:
        """Deterministic rule-based fallback parser.

        Extracts key signals from the intent text using pattern matching.
        Ensures the system always produces valid output, even without LLM.
        """
        logger.info("intent_parser.rule_based")
        intent_lower = raw_intent.lower()

        # Extract project name
        project_name = self._extract_project_name(intent_lower)

        # Detect app type
        app_type = self._detect_app_type(intent_lower)

        # Detect data stores
        data_stores = self._detect_data_stores(intent_lower)

        # Detect compliance
        compliance = self._detect_compliance(intent_lower)

        # Detect AI usage
        uses_ai = any(kw in intent_lower for kw in ["ai ", "ml ", "machine learning", "model", "llm", "gpt", "openai"])

        # Detect programming language
        language = self._detect_language(intent_lower)
        framework = LANGUAGE_FRAMEWORKS.get(language, "fastapi")

        # Detect compute target
        compute_target = self._detect_compute_target(intent_lower)

        # Detect networking
        networking = NetworkingModel.PRIVATE
        if "public" in intent_lower:
            networking = NetworkingModel.PUBLIC_RESTRICTED
        elif "internal" in intent_lower:
            networking = NetworkingModel.INTERNAL

        return IntentSpec(
            project_name=project_name,
            description=raw_intent[:200],
            raw_intent=raw_intent,
            app_type=app_type,
            language=language,
            framework=framework,
            compute_target=compute_target,
            data_stores=data_stores,
            uses_ai=uses_ai,
            security=SecurityRequirements(
                auth_model=AuthModel.MANAGED_IDENTITY,
                compliance_framework=compliance,
                networking=networking,
            ),
            observability=ObservabilityRequirements(),
            cicd=CICDRequirements(),
            azure_region=self.config.azure.location,
            resource_group_name=self.config.azure.resource_group,
            assumptions=[
                f"Using {language.capitalize()} + {framework} as application stack",
                f"Azure {compute_target.value.replace('_', ' ').title()} as compute target",
                "Managed Identity for authentication",
                "Key Vault for secret management",
                "Log Analytics for observability",
            ],
            decisions=[
                f"Selected {compute_target.value.replace('_', ' ').title()} based on intent signals",
                "Private networking by default for security posture",
                "Bicep for infrastructure as code (Azure-native)",
            ],
            open_risks=[
                "Intent may require clarification for complex architectures",
            ],
            confidence=0.75,
        )

    @staticmethod
    def _extract_project_name(intent: str) -> str:
        """Extract a kebab-case project name from intent text."""
        # Try to find "build a <name>" or "create a <name>"
        match = re.search(
            r"(?:build|create|deploy|make)\s+(?:a\s+)?(\w[\w\s-]{2,30}?)(?:\s+(?:that|which|with|for|to))", intent
        )
        if match:
            name = match.group(1).strip()
            name = re.sub(r"[^a-z0-9\s-]", "", name.lower())
            name = re.sub(r"\s+", "-", name.strip())
            name = name[:39]
            if re.match(r"^[a-z][a-z0-9-]{2,38}$", name):
                return name

        # Fallback: generate from first meaningful words
        words = re.findall(r"[a-z]+", intent)
        meaningful = [
            w
            for w in words
            if w
            not in {
                "a",
                "an",
                "the",
                "that",
                "which",
                "with",
                "for",
                "to",
                "and",
                "or",
                "build",
                "create",
                "deploy",
                "make",
                "please",
                "i",
                "want",
                "need",
            }
        ]
        name = "-".join(meaningful[:4])
        if len(name) < 3:
            name = "enterprise-workload"
        return name[:39]

    @staticmethod
    def _detect_app_type(intent: str) -> AppType:
        """Detect application type from intent text using word-boundary matching."""

        def _has_word(keyword: str) -> bool:
            return bool(re.search(rf"\b{re.escape(keyword)}\b", intent))

        if any(_has_word(kw) for kw in ["api", "rest", "endpoint", "microservice"]):
            return AppType.API
        if any(_has_word(kw) for kw in ["web", "frontend", "ui", "dashboard"]):
            return AppType.WEB
        if any(_has_word(kw) for kw in ["worker", "background", "queue", "batch", "process"]):
            return AppType.WORKER
        if any(_has_word(kw) for kw in ["function", "serverless", "trigger", "event-driven"]):
            return AppType.FUNCTION
        return AppType.API

    @staticmethod
    def _detect_data_stores(intent: str) -> list[DataStore]:
        """Detect required data stores from intent text."""
        stores: list[DataStore] = []
        if any(kw in intent for kw in ["blob", "file", "document", "upload", "storage"]):
            stores.append(DataStore.BLOB_STORAGE)
        if any(kw in intent for kw in ["cosmos", "nosql", "json store"]):
            stores.append(DataStore.COSMOS_DB)
        if any(kw in intent for kw in ["sql", "database", "relational", "postgres"]):
            stores.append(DataStore.SQL)
        if any(kw in intent for kw in ["redis", "cache", "session"]):
            stores.append(DataStore.REDIS)
        if not stores:
            stores.append(DataStore.BLOB_STORAGE)
        return stores

    @staticmethod
    def _detect_compliance(intent: str) -> ComplianceFramework:
        """Detect compliance framework from intent text."""
        if "hipaa" in intent:
            return ComplianceFramework.HIPAA_GUIDANCE
        if "soc2" in intent or "soc 2" in intent:
            return ComplianceFramework.SOC2_GUIDANCE
        if "fedramp" in intent:
            return ComplianceFramework.FEDRAMP_GUIDANCE
        return ComplianceFramework.GENERAL

    @staticmethod
    def _detect_language(intent: str) -> str:
        """Detect programming language from intent text."""

        def _has(keyword: str) -> bool:
            return bool(re.search(rf"\b{re.escape(keyword)}\b", intent))

        if any(_has(kw) for kw in ["node", "nodejs", "javascript", "typescript", "express"]):
            return "node"
        if any(_has(kw) for kw in ["dotnet", ".net", "csharp", "c#", "aspnet", "asp.net"]):
            return "dotnet"
        return "python"

    @staticmethod
    def _detect_compute_target(intent: str) -> ComputeTarget:
        """Detect Azure compute target from intent text."""

        def _has(keyword: str) -> bool:
            return bool(re.search(rf"\b{re.escape(keyword)}\b", intent))

        if any(_has(kw) for kw in ["app service", "webapp", "web app"]):
            return ComputeTarget.APP_SERVICE
        if any(_has(kw) for kw in ["function", "functions", "serverless", "consumption"]):
            return ComputeTarget.FUNCTIONS
        return ComputeTarget.CONTAINER_APPS
