"""Codebase-Aware Prompt Generator.

Scans the user's repository to detect:
- Languages and frameworks
- Project structure and conventions
- Configuration patterns (Docker, CI/CD, IaC)
- Security posture (secrets, auth patterns)

Then constructs per-agent prompts enriched with this context so each
agent in the pipeline can generate artifacts that match the existing
codebase style rather than producing generic boilerplate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Language / Framework Detection
# ---------------------------------------------------------------------------

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
}

FRAMEWORK_INDICATORS: dict[str, list[tuple[str, str]]] = {
    # (filename_or_pattern, framework_name)
    "python": [
        ("requirements.txt", "pip"),
        ("pyproject.toml", "modern-python"),
        ("setup.py", "setuptools"),
        ("Pipfile", "pipenv"),
        ("poetry.lock", "poetry"),
        ("manage.py", "django"),
        ("app.py", "flask-or-fastapi"),
        ("main.py", "fastapi-or-cli"),
    ],
    "javascript": [
        ("package.json", "node"),
        ("next.config.js", "nextjs"),
        ("nuxt.config.js", "nuxtjs"),
        ("angular.json", "angular"),
        ("vite.config.js", "vite"),
        ("webpack.config.js", "webpack"),
    ],
    "typescript": [
        ("tsconfig.json", "typescript"),
        ("next.config.ts", "nextjs"),
        ("angular.json", "angular"),
    ],
    "go": [
        ("go.mod", "go-modules"),
        ("go.sum", "go-modules"),
    ],
    "java": [
        ("pom.xml", "maven"),
        ("build.gradle", "gradle"),
        ("build.gradle.kts", "gradle-kotlin"),
    ],
    "csharp": [
        ("*.csproj", "dotnet"),
        ("*.sln", "dotnet"),
    ],
    "rust": [
        ("Cargo.toml", "cargo"),
    ],
}

CONFIG_PATTERNS: list[tuple[str, str]] = [
    ("Dockerfile", "docker"),
    ("docker-compose.yml", "docker-compose"),
    ("docker-compose.yaml", "docker-compose"),
    (".github/workflows", "github-actions"),
    (".azure-pipelines", "azure-pipelines"),
    ("azure-pipelines.yml", "azure-pipelines"),
    ("Jenkinsfile", "jenkins"),
    (".gitlab-ci.yml", "gitlab-ci"),
    ("bicep", "bicep-iac"),
    ("terraform", "terraform-iac"),
    ("pulumi", "pulumi-iac"),
    (".env", "dotenv"),
    (".env.example", "dotenv"),
    ("azure.yaml", "azd"),
    ("host.json", "azure-functions"),
    ("local.settings.json", "azure-functions"),
]

SECURITY_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, pattern_name, category)
    (r"DefaultAzureCredential", "managed-identity", "auth"),
    (r"ManagedIdentityCredential", "managed-identity", "auth"),
    (r"OIDC|openid", "oidc-auth", "auth"),
    (r"JWT|jsonwebtoken|jose", "jwt-auth", "auth"),
    (r"bcrypt|argon2|scrypt", "password-hashing", "auth"),
    (r"KEY_VAULT|keyvault|KeyVault", "key-vault", "secrets"),
    (r"AZURE_CLIENT_SECRET|client_secret", "client-secret", "secrets"),
    (r"os\.environ|getenv", "env-vars", "config"),
    (r"helmet|csp|Content-Security-Policy", "http-security", "transport"),
    (r"https://|TLS|SSL", "tls", "transport"),
    (r"CORS|cors|Access-Control", "cors", "transport"),
    (r"rate.?limit|throttl", "rate-limiting", "api"),
    (r"rbac|role.?based", "rbac", "authz"),
]


# ---------------------------------------------------------------------------
# Scan Result Models
# ---------------------------------------------------------------------------


@dataclass
class CodebaseScanResult:
    """Result of scanning a user's repository."""

    root_dir: str = ""
    languages: dict[str, int] = field(default_factory=dict)  # lang -> file count
    primary_language: str = ""
    frameworks: list[str] = field(default_factory=list)
    config_tools: list[str] = field(default_factory=list)
    security_patterns: dict[str, list[str]] = field(default_factory=dict)
    has_docker: bool = False
    has_cicd: bool = False
    has_iac: bool = False
    has_tests: bool = False
    test_framework: str = ""
    folder_structure: dict[str, list[str]] = field(default_factory=dict)
    total_files: int = 0
    project_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize scan result."""
        return {
            "root_dir": self.root_dir,
            "languages": self.languages,
            "primary_language": self.primary_language,
            "frameworks": self.frameworks,
            "config_tools": self.config_tools,
            "security_patterns": self.security_patterns,
            "has_docker": self.has_docker,
            "has_cicd": self.has_cicd,
            "has_iac": self.has_iac,
            "has_tests": self.has_tests,
            "test_framework": self.test_framework,
            "total_files": self.total_files,
        }

    def context_summary(self) -> str:
        """Generate a human-readable summary for prompt injection."""
        lines = [
            f"Primary language: {self.primary_language or 'unknown'}",
            f"Languages detected: {', '.join(f'{k}({v})' for k, v in sorted(self.languages.items(), key=lambda x: -x[1]))}",
            f"Frameworks: {', '.join(self.frameworks) or 'none detected'}",
        ]
        if self.has_docker:
            lines.append("Containerization: Docker detected")
        if self.has_cicd:
            ci_tools = [
                t for t in self.config_tools if t in ("github-actions", "azure-pipelines", "gitlab-ci", "jenkins")
            ]
            lines.append(f"CI/CD: {', '.join(ci_tools)}")
        if self.has_iac:
            iac_tools = [t for t in self.config_tools if t.endswith("-iac")]
            lines.append(f"IaC: {', '.join(iac_tools)}")
        if self.has_tests:
            lines.append(f"Test framework: {self.test_framework}")

        sec_cats = self.security_patterns
        if sec_cats:
            sec_items = []
            for cat, patterns in sec_cats.items():
                sec_items.append(f"{cat}: {', '.join(patterns)}")
            lines.append(f"Security patterns: {'; '.join(sec_items)}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


IGNORE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".devex",
}


class CodebaseScanner:
    """Scan a project directory and extract metadata."""

    def __init__(self, root: str | Path, max_files: int = 2000) -> None:
        self.root = Path(root)
        self.max_files = max_files

    def scan(self) -> CodebaseScanResult:
        """Run a full codebase scan."""
        result = CodebaseScanResult(root_dir=str(self.root))

        if not self.root.is_dir():
            logger.warning("scanner.not_a_directory", path=str(self.root))
            return result

        all_files = self._collect_files()
        result.total_files = len(all_files)
        result.project_files = [str(f.relative_to(self.root)) for f in all_files[:200]]

        self._detect_languages(all_files, result)
        self._detect_frameworks(result)
        self._detect_config(all_files, result)
        self._detect_security(all_files, result)
        self._detect_tests(all_files, result)
        self._build_folder_structure(all_files, result)

        logger.info(
            "scanner.complete",
            files=result.total_files,
            lang=result.primary_language,
            frameworks=result.frameworks,
        )
        return result

    def _collect_files(self) -> list[Path]:
        """Collect files, respecting ignore directories."""
        files: list[Path] = []
        for path in self.root.rglob("*"):
            if len(files) >= self.max_files:
                break
            if path.is_file() and not any(part in IGNORE_DIRS for part in path.parts):
                files.append(path)
        return files

    def _detect_languages(self, files: list[Path], result: CodebaseScanResult) -> None:
        """Count files per language by extension."""
        for f in files:
            ext = f.suffix.lower()
            lang = LANGUAGE_EXTENSIONS.get(ext)
            if lang:
                result.languages[lang] = result.languages.get(lang, 0) + 1

        if result.languages:
            result.primary_language = max(result.languages, key=result.languages.get)  # type: ignore[arg-type]

    def _detect_frameworks(self, result: CodebaseScanResult) -> None:
        """Detect frameworks based on known indicator files."""
        for lang in result.languages:
            indicators = FRAMEWORK_INDICATORS.get(lang, [])
            for filename, framework in indicators:
                if "*" in filename:
                    # Glob pattern
                    if list(self.root.glob(filename)):
                        result.frameworks.append(framework)
                elif (self.root / filename).exists():
                    result.frameworks.append(framework)

        # Deduplicate
        result.frameworks = list(dict.fromkeys(result.frameworks))

    def _detect_config(self, files: list[Path], result: CodebaseScanResult) -> None:
        """Detect configuration patterns (Docker, CI/CD, IaC)."""
        file_names = {f.name for f in files}
        rel_dirs = {str(f.relative_to(self.root)).split("\\")[0].split("/")[0] for f in files}

        for pattern, tool in CONFIG_PATTERNS:
            if pattern in file_names or pattern in rel_dirs:
                result.config_tools.append(tool)

        result.config_tools = list(dict.fromkeys(result.config_tools))
        result.has_docker = any(t.startswith("docker") for t in result.config_tools)
        result.has_cicd = any(
            t in result.config_tools for t in ["github-actions", "azure-pipelines", "gitlab-ci", "jenkins"]
        )
        result.has_iac = any(t.endswith("-iac") for t in result.config_tools)

    def _detect_security(self, files: list[Path], result: CodebaseScanResult) -> None:
        """Scan source files for security patterns."""
        source_exts = {".py", ".js", ".ts", ".go", ".java", ".cs", ".yaml", ".yml"}
        scanned = 0

        for f in files:
            if f.suffix.lower() not in source_exts:
                continue
            if scanned >= 100:  # Limit to avoid excessive scanning
                break
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            scanned += 1

            for pattern, name, category in SECURITY_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    if category not in result.security_patterns:
                        result.security_patterns[category] = []
                    if name not in result.security_patterns[category]:
                        result.security_patterns[category].append(name)

    def _detect_tests(self, files: list[Path], result: CodebaseScanResult) -> None:
        """Detect test framework and test files."""
        test_files = [
            f
            for f in files
            if "test" in f.name.lower()
            or "spec" in f.name.lower()
            or any(p in str(f) for p in ["tests/", "test/", "__tests__/", "spec/"])
        ]

        if test_files:
            result.has_tests = True
            # Determine framework
            exts = {f.suffix.lower() for f in test_files}
            if ".py" in exts:
                result.test_framework = "pytest"
            elif ".ts" in exts or ".js" in exts:
                result.test_framework = "jest-or-mocha"
            elif ".java" in exts:
                result.test_framework = "junit"
            elif ".cs" in exts:
                result.test_framework = "xunit-or-nunit"
            elif ".go" in exts:
                result.test_framework = "go-test"

    def _build_folder_structure(self, files: list[Path], result: CodebaseScanResult) -> None:
        """Build a simplified folder tree (depth 2)."""
        for f in files[:500]:
            rel = f.relative_to(self.root)
            parts = rel.parts
            if len(parts) >= 2:
                parent = parts[0]
                if parent not in result.folder_structure:
                    result.folder_structure[parent] = []
                child = parts[1]
                if child not in result.folder_structure[parent]:
                    result.folder_structure[parent].append(child)


# ---------------------------------------------------------------------------
# Prompt Generator
# ---------------------------------------------------------------------------


AGENT_PROMPT_TEMPLATES: dict[str, str] = {
    "intent_parser": """You are an enterprise architecture intent parser.
{codebase_context}

Given this context about the user's existing project, extract the IntentSpec.
Pay attention to:
- The primary language ({primary_language}) for appropriate app scaffolding
- Existing frameworks ({frameworks}) to maintain consistency
- Current security patterns to preserve and enhance
- Existing CI/CD setup to extend rather than replace

{base_instructions}""",
    "architecture_planner": """You are an Azure Solutions Architect.
{codebase_context}

Given the user's existing project context:
- The project uses {primary_language} with {frameworks}
- {"Docker is already configured" if has_docker else "No Docker setup detected -- include Dockerfile generation"}
- {"CI/CD is configured" if has_cicd else "No CI/CD detected -- include full workflow generation"}
- {"IaC exists" if has_iac else "No IaC detected -- generate complete Bicep templates"}
- Security patterns found: {security_summary}

Design the architecture to complement existing infrastructure.

{base_instructions}""",
    "governance_reviewer": """You are an enterprise governance reviewer.
{codebase_context}

The project's existing security posture includes: {security_summary}
Test coverage: {"Tests detected using " + test_framework if has_tests else "No tests detected -- flag as governance finding"}

Evaluate the architecture plan against enterprise policies, considering
what the project already has in place.

{base_instructions}""",
    "infra_generator": """You are an infrastructure code generator.
{codebase_context}

Generate artifacts that match the project's conventions:
- Language: {primary_language}
- Package manager: {package_manager}
- Test framework: {test_framework}
- Existing config tools: {config_tools}

Ensure generated code follows the same patterns as the existing codebase.

{base_instructions}""",
}


class PromptGenerator:
    """Generate context-enriched prompts for each pipeline agent.

    Workflow:
    1. Scan the user's codebase with CodebaseScanner
    2. Enrich each agent's system prompt with codebase context
    3. Return per-agent prompts for use in the pipeline
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else None
        self.scan_result: CodebaseScanResult | None = None

    def scan(self, root: str | Path | None = None) -> CodebaseScanResult:
        """Scan the codebase and cache the result."""
        scan_root = Path(root) if root else self.root
        if not scan_root:
            raise ValueError("No root directory provided for scanning")
        self.root = scan_root
        scanner = CodebaseScanner(scan_root)
        self.scan_result = scanner.scan()
        return self.scan_result

    def generate_prompt(self, agent_name: str, base_instructions: str = "") -> str:
        """Generate an enriched prompt for a specific agent.

        Args:
            agent_name: One of intent_parser, architecture_planner,
                       governance_reviewer, infra_generator.
            base_instructions: The agent's default system prompt.

        Returns:
            Enriched system prompt with codebase context.
        """
        if not self.scan_result:
            # Return base instructions if no scan was performed
            return base_instructions

        template = AGENT_PROMPT_TEMPLATES.get(agent_name)
        if not template:
            # Unknown agent -- just prepend context summary
            return f"Codebase context:\n{self.scan_result.context_summary()}\n\n{base_instructions}"

        ctx = self._build_context_vars(base_instructions)

        # Format template with available context
        try:
            return template.format(**ctx)
        except KeyError:
            # Fallback: prepend context summary
            return f"Codebase context:\n{self.scan_result.context_summary()}\n\n{base_instructions}"

    def generate_all_prompts(
        self,
        base_prompts: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Generate enriched prompts for all 4 agents.

        Args:
            base_prompts: Map of agent_name -> default system prompt.

        Returns:
            Map of agent_name -> enriched prompt.
        """
        base = base_prompts or {}
        return {name: self.generate_prompt(name, base.get(name, "")) for name in AGENT_PROMPT_TEMPLATES}

    def get_context_json(self) -> str:
        """Return scan result as JSON for debugging/logging."""
        if not self.scan_result:
            return "{}"
        return json.dumps(self.scan_result.to_dict(), indent=2)

    def _build_context_vars(self, base_instructions: str) -> dict[str, Any]:
        """Build template variables from scan result."""
        sr = self.scan_result or CodebaseScanResult()
        sec_items = []
        for cat, patterns in sr.security_patterns.items():
            sec_items.append(f"{cat}: {', '.join(patterns)}")
        security_summary = "; ".join(sec_items) if sec_items else "none detected"

        # Detect package manager
        pkg_manager = "unknown"
        if "pip" in sr.frameworks or "modern-python" in sr.frameworks:
            pkg_manager = "pip"
        elif "poetry" in sr.frameworks:
            pkg_manager = "poetry"
        elif "node" in sr.frameworks:
            pkg_manager = "npm"
        elif "go-modules" in sr.frameworks:
            pkg_manager = "go-modules"

        return {
            "codebase_context": sr.context_summary(),
            "primary_language": sr.primary_language or "unknown",
            "frameworks": ", ".join(sr.frameworks) or "none",
            "has_docker": sr.has_docker,
            "has_cicd": sr.has_cicd,
            "has_iac": sr.has_iac,
            "has_tests": sr.has_tests,
            "test_framework": sr.test_framework or "none",
            "security_summary": security_summary,
            "config_tools": ", ".join(sr.config_tools) or "none",
            "package_manager": pkg_manager,
            "base_instructions": base_instructions,
        }
