"""Intent File Parser -- reads structured intent from Markdown files.

Allows users to describe enterprise requirements in a comprehensive
``intent.md`` file and have the orchestrator parse it into a
pipeline-ready intent string and version metadata.

Enterprise intent files force the user to clearly define every stage of
the solution -- problem, goals, users, scalability, security, performance,
integrations, and acceptance criteria -- so the orchestrator can analyse,
design, implement, test, and suggest improvements in a single run.

Supported format::

    # My Project Name
    > One-paragraph executive summary of the solution.

    ## Problem Statement
    What business problem does this solve?

    ## Business Goals
    Measurable outcomes this project must achieve.

    ## Target Users
    Who will use this system and how?

    ## Functional Requirements
    What the system must do -- features and capabilities.

    ## Scalability Requirements
    Load expectations, growth targets, scaling strategy.

    ## Security & Compliance
    Auth, data classification, compliance frameworks, threat concerns.

    ## Performance Requirements
    Latency, throughput, availability SLA targets.

    ## Integration Requirements
    External systems, APIs, data sources this must connect to.

    ## Configuration
    - **App Type**: api
    - **Data Stores**: blob, cosmos
    - **Region**: eastus2
    - **Environment**: dev
    - **Auth**: managed-identity
    - **Compliance**: SOC2

    ## Acceptance Criteria
    Conditions that must be true for the solution to be considered complete.

    ## Version
    - **Version**: 1
    - **Based On**: (none for v1)
    - **Changes**: Initial scaffold

    ## Notes
    Free-form notes or additional context.
"""

from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)

# --- Section heading patterns ----------------------------------

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
_FIELD_RE = re.compile(
    r"[-*]\s+\*\*(.+?)\*\*\s*:\s*(.+)",
    re.IGNORECASE,
)
_BLOCKQUOTE_RE = re.compile(r"^>\s*(.+)$", re.MULTILINE)

# Fields we recognise in the Configuration section
_CONFIG_KEYS = {
    "app type": "app_type",
    "data stores": "data_stores",
    "region": "region",
    "environment": "environment",
    "auth": "auth",
    "compliance": "compliance",
    "observability": "observability",
}

_VERSION_KEYS = {
    "version": "version",
    "based on": "based_on",
    "changes": "changes",
    "change summary": "changes",
}


@dataclass
class IntentFileVersion:
    """Version metadata extracted from the intent file."""

    version: int = 1
    based_on: int | None = None
    changes: str = ""

    @property
    def is_upgrade(self) -> bool:
        """Whether this version builds on a previous one."""
        return self.based_on is not None and self.based_on >= 1


@dataclass
class IntentFileResult:
    """Result of parsing an intent.md file."""

    # Core intent (the blockquote description or full text)
    intent: str = ""

    # Project name (from H1 heading)
    project_name: str = ""

    # -- Enterprise requirement sections ---------------------------
    problem_statement: str = ""
    business_goals: str = ""
    target_users: str = ""
    functional_requirements: str = ""
    scalability_requirements: str = ""
    security_compliance: str = ""
    performance_requirements: str = ""
    integration_requirements: str = ""
    acceptance_criteria: str = ""

    # Structured configuration overrides
    config: dict[str, str] = field(default_factory=dict)

    # Version info
    version_info: IntentFileVersion = field(default_factory=IntentFileVersion)

    # Free-form notes
    notes: str = ""

    # Source file path
    source_path: str = ""

    # -- Enterprise section name -> attribute mapping ---------------
    _ENTERPRISE_SECTIONS: dict[str, str] = field(
        default=None,  # type: ignore[assignment]
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        # Map recognised H2 heading names to dataclass attributes
        self._ENTERPRISE_SECTIONS = {
            "problem statement": "problem_statement",
            "problem": "problem_statement",
            "business goals": "business_goals",
            "goals": "business_goals",
            "target users": "target_users",
            "users": "target_users",
            "personas": "target_users",
            "functional requirements": "functional_requirements",
            "features": "functional_requirements",
            "scalability requirements": "scalability_requirements",
            "scalability": "scalability_requirements",
            "scaling": "scalability_requirements",
            "security & compliance": "security_compliance",
            "security and compliance": "security_compliance",
            "security": "security_compliance",
            "compliance": "security_compliance",
            "performance requirements": "performance_requirements",
            "performance": "performance_requirements",
            "integration requirements": "integration_requirements",
            "integrations": "integration_requirements",
            "acceptance criteria": "acceptance_criteria",
            "acceptance": "acceptance_criteria",
            "definition of done": "acceptance_criteria",
        }

    @property
    def full_intent(self) -> str:
        """Build a complete intent string from file contents.

        Combines the executive summary, enterprise requirement sections,
        and configuration so the intent parser agent gets comprehensive
        context for analysing, designing, and generating the solution.
        """
        parts = []

        if self.intent:
            parts.append(self.intent)

        # -- Enterprise requirement sections (in logical order) ----
        if self.problem_statement:
            parts.append(f"Problem Statement: {self.problem_statement}")
        if self.business_goals:
            parts.append(f"Business Goals: {self.business_goals}")
        if self.target_users:
            parts.append(f"Target Users: {self.target_users}")
        if self.functional_requirements:
            parts.append(f"Functional Requirements: {self.functional_requirements}")
        if self.scalability_requirements:
            parts.append(f"Scalability Requirements: {self.scalability_requirements}")
        if self.security_compliance:
            parts.append(f"Security & Compliance: {self.security_compliance}")
        if self.performance_requirements:
            parts.append(f"Performance Requirements: {self.performance_requirements}")
        if self.integration_requirements:
            parts.append(f"Integration Requirements: {self.integration_requirements}")
        if self.acceptance_criteria:
            parts.append(f"Acceptance Criteria: {self.acceptance_criteria}")

        # -- Structured configuration as natural language ----------
        config_parts = []
        if self.config.get("app_type"):
            config_parts.append(f"Application type: {self.config['app_type']}")
        if self.config.get("data_stores"):
            config_parts.append(f"Data stores: {self.config['data_stores']}")
        if self.config.get("region"):
            config_parts.append(f"Azure region: {self.config['region']}")
        if self.config.get("environment"):
            config_parts.append(f"Environment: {self.config['environment']}")
        if self.config.get("auth"):
            config_parts.append(f"Authentication: {self.config['auth']}")
        if self.config.get("compliance"):
            config_parts.append(f"Compliance framework: {self.config['compliance']}")
        if self.config.get("observability"):
            config_parts.append(f"Observability: {self.config['observability']}")

        if config_parts:
            parts.append(". ".join(config_parts) + ".")

        if self.notes:
            parts.append(self.notes.strip())

        return " ".join(parts) if parts else ""

    @property
    def enterprise_sections_filled(self) -> dict[str, bool]:
        """Return which enterprise sections have content."""
        return {
            "problem_statement": bool(self.problem_statement),
            "business_goals": bool(self.business_goals),
            "target_users": bool(self.target_users),
            "functional_requirements": bool(self.functional_requirements),
            "scalability_requirements": bool(self.scalability_requirements),
            "security_compliance": bool(self.security_compliance),
            "performance_requirements": bool(self.performance_requirements),
            "integration_requirements": bool(self.integration_requirements),
            "acceptance_criteria": bool(self.acceptance_criteria),
        }

    @property
    def completeness_pct(self) -> float:
        """Percentage of enterprise sections that have content."""
        filled = self.enterprise_sections_filled
        if not filled:
            return 0.0
        return sum(1 for v in filled.values() if v) / len(filled) * 100


class IntentFileParser:
    """Parses structured intent from Markdown files.

    Usage:
        parser = IntentFileParser()
        result = parser.parse("intent.md")
        intent_string = result.full_intent
    """

    def parse(self, path: str | Path) -> IntentFileResult:
        """Parse an intent markdown file.

        Args:
            path: Path to the intent .md file.

        Returns:
            IntentFileResult with parsed intent, config, and version info.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is empty or has no recognizable intent.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Intent file not found: {path}")

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Intent file is empty: {path}")

        logger.info("intent_file.parsing", path=str(path), size=len(content))

        result = IntentFileResult(source_path=str(path))

        # Parse sections
        sections = self._split_sections(content)

        # Extract project name from H1
        result.project_name = sections.get("_title", "")

        # Extract blockquote (primary intent description)
        result.intent = self._extract_blockquote(content)

        # If no blockquote, use the text under the title as intent
        if not result.intent and "_body" in sections:
            result.intent = sections["_body"].strip()

        # Parse Configuration section
        for section_name in ("configuration", "config", "settings"):
            if section_name in sections:
                result.config = self._parse_config_fields(sections[section_name])
                break

        # Parse enterprise requirement sections
        self._parse_enterprise_sections(result, sections)

        # Parse Version section
        for section_name in ("version", "versioning"):
            if section_name in sections:
                result.version_info = self._parse_version_fields(sections[section_name])
                break

        # Parse Notes section
        for section_name in ("notes", "requirements", "context", "details"):
            if section_name in sections:
                result.notes = sections[section_name].strip()
                break

        # Validation
        if not result.intent and not result.config:
            # Fall back: treat the entire file as a plain intent description
            result.intent = content
            logger.info("intent_file.fallback_plain_text")

        logger.info(
            "intent_file.parsed",
            project=result.project_name,
            has_config=bool(result.config),
            version=result.version_info.version,
            is_upgrade=result.version_info.is_upgrade,
            completeness=f"{result.completeness_pct:.0f}%",
        )

        return result

    def parse_string(self, content: str) -> IntentFileResult:
        """Parse intent from a markdown string (for testing).

        Args:
            content: Markdown content as a string.

        Returns:
            IntentFileResult with parsed data.
        """
        if not content.strip():
            raise ValueError("Intent content is empty")

        result = IntentFileResult()
        sections = self._split_sections(content)

        result.project_name = sections.get("_title", "")
        result.intent = self._extract_blockquote(content)

        if not result.intent and "_body" in sections:
            result.intent = sections["_body"].strip()

        for section_name in ("configuration", "config", "settings"):
            if section_name in sections:
                result.config = self._parse_config_fields(sections[section_name])
                break

        # Parse enterprise requirement sections
        self._parse_enterprise_sections(result, sections)

        for section_name in ("version", "versioning"):
            if section_name in sections:
                result.version_info = self._parse_version_fields(sections[section_name])
                break

        for section_name in ("notes", "requirements", "context", "details"):
            if section_name in sections:
                result.notes = sections[section_name].strip()
                break

        if not result.intent and not result.config:
            result.intent = content.strip()

        return result

    # -- Internal helpers ----------------------------------------

    def _split_sections(self, content: str) -> dict[str, str]:
        """Split markdown into named sections by headings.

        Returns a dict with lowercase heading names -> section content.
        Special keys:
            _title: The H1 heading text
            _body: Text between H1 and first H2/H3
        """
        sections: dict[str, str] = {}
        lines = content.split("\n")

        current_section: str | None = None
        current_lines: list[str] = []
        found_title = False

        for line in lines:
            heading_match = _HEADING_RE.match(line)
            if heading_match:
                # Save previous section
                if current_section is not None:
                    sections[current_section] = "\n".join(current_lines).strip()

                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                if level == 1 and not found_title:
                    sections["_title"] = heading_text
                    current_section = "_body"
                    found_title = True
                else:
                    current_section = heading_text.lower()

                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        if current_section is not None:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections

    def _extract_blockquote(self, content: str) -> str:
        """Extract blockquote text as the primary intent description."""
        quotes = _BLOCKQUOTE_RE.findall(content)
        return " ".join(q.strip() for q in quotes) if quotes else ""

    def _parse_enterprise_sections(
        self,
        result: IntentFileResult,
        sections: dict[str, str],
    ) -> None:
        """Populate enterprise requirement fields from parsed sections.

        Iterates over the section dict looking for heading names that
        match known enterprise section aliases and strips HTML comments
        (template placeholders) before storing content.
        """
        mapping = result._ENTERPRISE_SECTIONS
        for section_key, section_text in sections.items():
            attr = mapping.get(section_key)
            if attr is not None:
                cleaned = self._strip_comments(section_text).strip()
                if cleaned:
                    setattr(result, attr, cleaned)

    @staticmethod
    def _strip_comments(text: str) -> str:
        """Remove HTML / markdown comments from section text."""
        return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()

    def _parse_config_fields(self, section_text: str) -> dict[str, str]:
        """Parse **Key**: Value fields from a configuration section."""
        config: dict[str, str] = {}
        for match in _FIELD_RE.finditer(section_text):
            key = match.group(1).strip().lower()
            value = match.group(2).strip()
            if key in _CONFIG_KEYS:
                config[_CONFIG_KEYS[key]] = value
        return config

    def _parse_version_fields(self, section_text: str) -> IntentFileVersion:
        """Parse version metadata from the Version section."""
        version_info = IntentFileVersion()
        for match in _FIELD_RE.finditer(section_text):
            key = match.group(1).strip().lower()
            value = match.group(2).strip()

            mapped = _VERSION_KEYS.get(key)
            if mapped == "version":
                try:
                    version_info.version = int(value)
                except ValueError:
                    version_info.version = 1
            elif mapped == "based_on":
                if value.lower() not in ("none", "n/a", "-", ""):
                    with suppress(ValueError):
                        version_info.based_on = int(value)
            elif mapped == "changes":
                version_info.changes = value

        return version_info


# --- Template generation --------------------------------------


def generate_intent_template(
    project_name: str = "my-secure-api",
    version: int = 1,
    based_on: int | None = None,
) -> str:
    """Generate a comprehensive enterprise intent.md template.

    Forces the user to define every stage of enterprise solution delivery:
    problem, goals, users, requirements, scalability, security, performance,
    integrations, and acceptance criteria.

    Args:
        project_name: Default project name (kebab-case).
        version: Version number.
        based_on: Previous version this builds on (None for v1).

    Returns:
        Markdown string ready to write to a file.
    """
    based_on_str = str(based_on) if based_on else "none"
    changes_str = "Initial scaffold" if version == 1 else "Describe your changes here"

    template = f"""# {project_name}

> Provide a one-paragraph executive summary of the solution you are building.
> Describe the system, its purpose, and the key business outcome it delivers.

---

## Problem Statement

<!--
Define the business problem this project solves. Be specific:
  - What pain point exists today?
  - Who is affected and how?
  - What is the cost of not solving this problem?
  - What has been tried before (if anything)?
-->

## Business Goals

<!--
List measurable business outcomes this project must achieve:
  - Revenue impact or cost savings expected
  - Time-to-market targets
  - Operational efficiency improvements
  - Key success metrics (KPIs) and how they will be measured
-->

## Target Users

<!--
Define who will use this system. For each user type, describe:
  - Role or persona name
  - What they need from the system
  - Usage frequency (daily, weekly, on-demand)
  - Technical proficiency level
  - Example user journey or workflow

Example:
  - **API Consumer (Internal Team)**: Calls the API from internal microservices
    to retrieve and store documents. Daily use. High technical proficiency.
  - **Operations Engineer**: Monitors system health, deploys updates, and
    manages infrastructure. Weekly use. Expert-level Azure knowledge.
-->

## Functional Requirements

<!--
Describe what the system must do -- its features and capabilities:
  - Core features (must-have for v1)
  - API endpoints or user-facing functionality
  - Data processing or business logic
  - Background jobs or scheduled tasks
  - Error handling and retry behaviour

Example:
  - Upload, download, and search documents via REST API
  - Role-based access control for document operations
  - Full audit logging for all data access
  - Automated document classification on upload
-->

## Scalability Requirements

<!--
Define load expectations and growth targets:
  - Expected concurrent users (current and projected)
  - Requests per second (peak and average)
  - Data volume (current and 12-month projection)
  - Geographic distribution of users
  - Scaling strategy (horizontal, vertical, auto-scale triggers)
  - Cost ceiling or budget constraints for scaling

Example:
  - 500 concurrent users at launch, growing to 5,000 in 12 months
  - Peak: 200 requests/second; Average: 50 requests/second
  - 10 TB initial data, growing 2 TB/month
  - Users primarily in US East and EU West
-->

## Security & Compliance

<!--
Define security and compliance requirements:
  - Authentication model (managed-identity, entra-id, api-key)
  - Authorization model (RBAC roles, resource-level permissions)
  - Data classification (public, internal, confidential, restricted)
  - Compliance frameworks (SOC2, HIPAA, PCI-DSS, FedRAMP, ISO 27001)
  - Encryption requirements (at-rest, in-transit, key management)
  - Network security (private endpoints, VNet integration, WAF)
  - Threat concerns specific to your domain
  - Data residency or sovereignty requirements
-->

## Performance Requirements

<!--
Define latency, throughput, and availability targets:
  - API response time targets (p50, p95, p99)
  - Availability SLA (99.9%, 99.95%, 99.99%)
  - Recovery Time Objective (RTO) and Recovery Point Objective (RPO)
  - Cold start tolerance (for serverless workloads)
  - Batch processing time windows

Example:
  - API p95 latency < 200ms for read operations
  - 99.95% availability SLA
  - RTO: 1 hour, RPO: 15 minutes
-->

## Integration Requirements

<!--
List external systems, APIs, and data sources this must connect to:
  - Upstream services (what sends data to this system)
  - Downstream services (what this system sends data to)
  - Third-party APIs or SaaS integrations
  - Data migration or import requirements
  - Event-driven integrations (Kafka, Service Bus, Event Grid)

Example:
  - Ingest documents from SharePoint via Microsoft Graph API
  - Publish document events to Azure Service Bus for downstream analytics
  - Integrate with Azure AD for SSO
-->

## Configuration

- **App Type**: api
- **Data Stores**: blob
- **Region**: eastus2
- **Environment**: dev
- **Auth**: managed-identity
- **Compliance**: SOC2

## Acceptance Criteria

<!--
Define the conditions that must be true for this solution to be
considered complete and ready for production:
  - Functional acceptance tests that must pass
  - Performance benchmarks that must be met
  - Security controls that must be verified
  - Documentation that must exist
  - Operational readiness checks

Example:
  - All CRUD API endpoints return correct responses
  - p95 latency < 200ms under 100 concurrent users
  - Zero critical findings in security scan
  - Deployment runbook reviewed and approved
  - Monitoring dashboards and alerts configured
-->

## Version

- **Version**: {version}
- **Based On**: {based_on_str}
- **Changes**: {changes_str}

## Notes

<!--
Additional context, constraints, or assumptions not captured above.
The orchestrator uses every section to analyse requirements, design
architecture, generate infrastructure, produce tests, and suggest
improvements. Each re-run with updated content brings the solution
closer to production readiness.
-->
"""
    return template


def generate_upgrade_template(
    project_name: str,
    current_version: int,
    current_intent: str,
    improvement_suggestions: list[str] | None = None,
) -> str:
    """Generate an intent file for a version upgrade.

    Pre-fills from the current version's data and optionally includes
    improvement suggestions from the previous run so users can review
    and incorporate them.

    Args:
        project_name: Existing project name.
        current_version: The version being upgraded from.
        current_intent: The current intent description.
        improvement_suggestions: Suggestions from the previous run's analysis.

    Returns:
        Markdown string for the upgrade intent file.
    """
    new_version = current_version + 1

    suggestions_block = ""
    if improvement_suggestions:
        items = "\n".join(f"  - {s}" for s in improvement_suggestions)
        suggestions_block = f"""
## Improvement Suggestions from v{current_version}

<!--
The orchestrator identified these improvement opportunities from the
previous run. Review them and incorporate any you want into the
sections above or into the changes description below.

{items}
-->
"""

    return f"""# {project_name}

> {current_intent}

---

## Problem Statement

<!-- Carry forward or refine the problem statement from v{current_version}. -->

## Business Goals

<!-- Update goals based on progress from v{current_version}. -->

## Target Users

<!-- Add new user types or refine existing personas. -->

## Functional Requirements

<!-- List new features and keep existing requirements that still apply. -->

## Scalability Requirements

<!-- Update load expectations based on production data from v{current_version}. -->

## Security & Compliance

<!-- Add new security requirements or address findings from v{current_version}. -->

## Performance Requirements

<!-- Refine targets based on observed v{current_version} performance. -->

## Integration Requirements

<!-- Add new integrations or update existing ones. -->

## Configuration

- **App Type**: api
- **Data Stores**: blob
- **Region**: eastus2
- **Environment**: dev
- **Auth**: managed-identity
- **Compliance**: SOC2

## Acceptance Criteria

<!-- Updated acceptance criteria for v{new_version}. -->
{suggestions_block}
## Version

- **Version**: {new_version}
- **Based On**: {current_version}
- **Changes**: Describe what you are adding or changing in v{new_version}

## Notes

<!--
UPGRADE from v{current_version} -> v{new_version}

The orchestrator will:
  1. Analyse your updated requirements against v{current_version}
  2. Re-design architecture to accommodate changes
  3. Generate updated infrastructure, tests, and CI/CD
  4. Deploy v{new_version} safely alongside v{current_version} (revision-based)
  5. Provide new improvement suggestions for the next iteration

Each run brings the solution closer to production readiness.
-->
"""
