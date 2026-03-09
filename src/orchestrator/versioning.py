"""Version Manager -- safe, incremental version upgrades for scaffolded projects.

Tracks version history, enables v1 -> v2 -> v3 upgrades without breaking
existing deployments, and generates version-aware CI/CD artifacts.

Version state is stored in `.devex/versions.json`.

Upgrade strategy:
  - v1: Full scaffold (Container Apps, infra, CI/CD, app)
  - v2+: Incremental -- only regenerate changed components.
         CI/CD gets a promotion workflow with revision-based deployment
         so the previous version stays live while the new one is validated.

Container Apps revision model:
  - Each version deploys as a new revision
  - Traffic is split 0/100 until the new revision is verified
  - Promotion shifts traffic 100% to the new revision
  - Rollback re-enables the previous revision
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.orchestrator.intent_file import IntentFileResult
from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VersionRecord:
    """Record of a single version of the project."""

    version: int
    intent: str
    intent_hash: str
    changes: str
    created_at: str
    status: str = "active"  # active | superseded | rolled-back
    file_count: int = 0
    governance_status: str = ""
    based_on: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "intent": self.intent,
            "intent_hash": self.intent_hash,
            "changes": self.changes,
            "created_at": self.created_at,
            "status": self.status,
            "file_count": self.file_count,
            "governance_status": self.governance_status,
            "based_on": self.based_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VersionRecord:
        return cls(
            version=data["version"],
            intent=data.get("intent", ""),
            intent_hash=data.get("intent_hash", ""),
            changes=data.get("changes", ""),
            created_at=data.get("created_at", ""),
            status=data.get("status", "active"),
            file_count=data.get("file_count", 0),
            governance_status=data.get("governance_status", ""),
            based_on=data.get("based_on"),
        )


@dataclass
class VersionState:
    """Persistent version tracking for a project."""

    project_name: str = ""
    current_version: int = 0
    versions: dict[int, VersionRecord] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "current_version": self.current_version,
            "versions": {
                str(v): rec.to_dict() for v, rec in self.versions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VersionState:
        versions = {}
        for v_str, rec_data in data.get("versions", {}).items():
            v = int(v_str)
            versions[v] = VersionRecord.from_dict(rec_data)
        return cls(
            project_name=data.get("project_name", ""),
            current_version=data.get("current_version", 0),
            versions=versions,
        )


@dataclass
class UpgradePlan:
    """Plan for upgrading from one version to another."""

    from_version: int
    to_version: int
    changes: str
    new_intent: str
    previous_intent: str
    regenerate_infra: bool = True
    regenerate_cicd: bool = True
    regenerate_app: bool = True
    regenerate_docs: bool = True
    add_promotion_workflow: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts = [f"Upgrade v{self.from_version} -> v{self.to_version}"]
        if self.changes:
            parts.append(f"Changes: {self.changes}")
        regen = []
        if self.regenerate_infra:
            regen.append("infra")
        if self.regenerate_cicd:
            regen.append("CI/CD")
        if self.regenerate_app:
            regen.append("app")
        if self.regenerate_docs:
            regen.append("docs")
        parts.append(f"Regenerate: {', '.join(regen)}")
        return " | ".join(parts)


class VersionManager:
    """Manages versioned project iterations.

    Usage:
        vm = VersionManager(output_dir)
        vm.record_version(intent_result, file_count, governance_status)

        # Later, for an upgrade:
        plan = vm.plan_upgrade(new_intent_result)
        # ... execute the upgrade ...
        vm.record_version(new_intent_result, new_file_count, status)
    """

    VERSION_FILE = ".devex/versions.json"

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.version_path = self.output_dir / self.VERSION_FILE
        self.state = self._load()

    def _load(self) -> VersionState:
        """Load version state from disk."""
        if self.version_path.exists():
            try:
                data = json.loads(self.version_path.read_text(encoding="utf-8"))
                logger.info("version.loaded", path=str(self.version_path))
                return VersionState.from_dict(data)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("version.load_failed", error=str(exc))
        return VersionState()

    def save(self) -> None:
        """Persist version state to disk."""
        self.version_path.parent.mkdir(parents=True, exist_ok=True)
        self.version_path.write_text(
            json.dumps(self.state.to_dict(), indent=2),
            encoding="utf-8",
        )
        logger.info("version.saved", path=str(self.version_path))

    @property
    def current_version(self) -> int:
        return self.state.current_version

    @property
    def has_versions(self) -> bool:
        return len(self.state.versions) > 0

    def get_version(self, version: int) -> VersionRecord | None:
        """Get a specific version record."""
        return self.state.versions.get(version)

    def get_current(self) -> VersionRecord | None:
        """Get the current active version record."""
        return self.state.versions.get(self.state.current_version)

    def record_version(
        self,
        intent_result: IntentFileResult,
        file_count: int = 0,
        governance_status: str = "",
    ) -> VersionRecord:
        """Record a new version after generation.

        Args:
            intent_result: Parsed intent file result.
            file_count: Number of generated files.
            governance_status: PASS/FAIL/PASS_WITH_WARNINGS.

        Returns:
            The new VersionRecord.
        """
        version = intent_result.version_info.version
        now = datetime.now(tz=UTC).isoformat()

        # Mark previous version as superseded
        if self.state.current_version > 0 and self.state.current_version != version:
            prev = self.state.versions.get(self.state.current_version)
            if prev:
                prev.status = "superseded"

        record = VersionRecord(
            version=version,
            intent=intent_result.full_intent,
            intent_hash=self._hash(intent_result.full_intent),
            changes=intent_result.version_info.changes,
            created_at=now,
            status="active",
            file_count=file_count,
            governance_status=governance_status,
            based_on=intent_result.version_info.based_on,
        )

        self.state.versions[version] = record
        self.state.current_version = version
        self.state.project_name = intent_result.project_name or self.state.project_name

        self.save()
        logger.info(
            "version.recorded",
            version=version,
            files=file_count,
            based_on=record.based_on,
        )
        return record

    def plan_upgrade(self, new_intent: IntentFileResult) -> UpgradePlan:
        """Create an upgrade plan from current version to the new one.

        Args:
            new_intent: The parsed intent file for the new version.

        Returns:
            UpgradePlan describing what needs to change.
        """
        from_version = self.state.current_version
        to_version = new_intent.version_info.version

        prev = self.state.versions.get(from_version)
        previous_intent = prev.intent if prev else ""

        plan = UpgradePlan(
            from_version=from_version,
            to_version=to_version,
            changes=new_intent.version_info.changes,
            new_intent=new_intent.full_intent,
            previous_intent=previous_intent,
        )

        # Determine what needs regeneration based on what changed
        new_config = new_intent.config
        plan.notes.append(f"Upgrading from v{from_version} to v{to_version}")

        if new_config.get("data_stores") or new_config.get("app_type"):
            plan.regenerate_infra = True
            plan.notes.append("Infrastructure changes detected -- regenerating Bicep")
        if new_config.get("region") or new_config.get("environment"):
            plan.regenerate_infra = True
            plan.notes.append("Region/environment change -- updating parameters")

        # Always add promotion workflow for upgrades
        if from_version > 0:
            plan.add_promotion_workflow = True
            plan.notes.append(
                "Adding revision-based promotion workflow for safe deployment"
            )

        logger.info(
            "version.upgrade_planned",
            from_v=from_version,
            to_v=to_version,
            notes=len(plan.notes),
        )
        return plan

    def rollback(self, to_version: int) -> bool:
        """Roll back to a previous version.

        Marks the current version as rolled-back and reactivates
        the target version. Does NOT regenerate files.

        Args:
            to_version: The version to roll back to.

        Returns:
            True if rollback succeeded, False if target version not found.
        """
        if to_version not in self.state.versions:
            logger.warning("version.rollback_failed", target=to_version)
            return False

        # Mark current as rolled-back
        current = self.state.versions.get(self.state.current_version)
        if current:
            current.status = "rolled-back"

        # Reactivate target
        target = self.state.versions[to_version]
        target.status = "active"
        self.state.current_version = to_version

        self.save()
        logger.info("version.rolled_back", to=to_version)
        return True

    def get_history(self) -> list[dict[str, Any]]:
        """Get version history as a list of dicts (for display)."""
        result = []
        for v in sorted(self.state.versions.keys()):
            rec = self.state.versions[v]
            result.append({
                "version": rec.version,
                "status": rec.status,
                "changes": rec.changes,
                "created_at": rec.created_at,
                "files": rec.file_count,
                "governance": rec.governance_status,
                "based_on": rec.based_on,
            })
        return result

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
