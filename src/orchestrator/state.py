"""State Management -- tracks generated artifacts and detects drift.

Provides persistent state tracking for the orchestrator, enabling:
  - Recording what was generated (intent, plan, files)
  - Detecting drift between current spec and previously generated artifacts
  - Supporting incremental updates when intent changes
  - Audit trail of all generation events

State is stored in .devex/state.json within the output directory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.orchestrator.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FileRecord:
    """Record of a generated file."""

    path: str
    content_hash: str
    size_bytes: int
    generated_at: str


@dataclass
class GenerationEvent:
    """Record of a single generation run."""

    timestamp: str
    intent: str
    project_name: str
    environment: str
    azure_region: str
    file_count: int
    governance_status: str
    standards_version: str = "1.0.0"


@dataclass
class DriftResult:
    """Result of drift detection analysis."""

    has_drift: bool
    changed_fields: list[str] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ProjectState:
    """Persistent state for a scaffolded project.

    Stored in .devex/state.json and tracks the complete
    generation history and current file manifest.
    """

    version: str = "1.0.0"
    project_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    intent_hash: str = ""
    plan_hash: str = ""
    last_intent: str = ""
    last_environment: str = ""
    last_region: str = ""
    last_governance_status: str = ""
    files: dict[str, FileRecord] = field(default_factory=dict)
    history: list[GenerationEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to a JSON-compatible dict."""
        return {
            "version": self.version,
            "project_name": self.project_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "intent_hash": self.intent_hash,
            "plan_hash": self.plan_hash,
            "last_intent": self.last_intent,
            "last_environment": self.last_environment,
            "last_region": self.last_region,
            "last_governance_status": self.last_governance_status,
            "files": {
                path: {
                    "path": rec.path,
                    "content_hash": rec.content_hash,
                    "size_bytes": rec.size_bytes,
                    "generated_at": rec.generated_at,
                }
                for path, rec in self.files.items()
            },
            "history": [
                {
                    "timestamp": event.timestamp,
                    "intent": event.intent,
                    "project_name": event.project_name,
                    "environment": event.environment,
                    "azure_region": event.azure_region,
                    "file_count": event.file_count,
                    "governance_status": event.governance_status,
                    "standards_version": event.standards_version,
                }
                for event in self.history
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectState:
        """Deserialize state from a dict."""
        files = {}
        for path, rec_data in data.get("files", {}).items():
            files[path] = FileRecord(
                path=rec_data["path"],
                content_hash=rec_data["content_hash"],
                size_bytes=rec_data["size_bytes"],
                generated_at=rec_data["generated_at"],
            )

        history = []
        for event_data in data.get("history", []):
            history.append(
                GenerationEvent(
                    timestamp=event_data["timestamp"],
                    intent=event_data["intent"],
                    project_name=event_data["project_name"],
                    environment=event_data["environment"],
                    azure_region=event_data["azure_region"],
                    file_count=event_data["file_count"],
                    governance_status=event_data["governance_status"],
                    standards_version=event_data.get("standards_version", "1.0.0"),
                )
            )

        return cls(
            version=data.get("version", "1.0.0"),
            project_name=data.get("project_name", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            intent_hash=data.get("intent_hash", ""),
            plan_hash=data.get("plan_hash", ""),
            last_intent=data.get("last_intent", ""),
            last_environment=data.get("last_environment", ""),
            last_region=data.get("last_region", ""),
            last_governance_status=data.get("last_governance_status", ""),
            files=files,
            history=history,
        )


class StateManager:
    """Manages persistent project state for the orchestrator.

    Usage:
        manager = StateManager(output_dir)
        manager.record_generation(spec, plan, report, files)
        drift = manager.detect_drift(new_spec)
    """

    STATE_FILE = ".devex/state.json"

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.state_path = self.output_dir / self.STATE_FILE
        self.state = self._load_state()

    def _load_state(self) -> ProjectState:
        """Load existing state or create new."""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                logger.info("state.loaded", path=str(self.state_path))
                return ProjectState.from_dict(data)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("state.load_failed", error=str(exc))
                return ProjectState()
        return ProjectState()

    def save(self) -> None:
        """Persist current state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.state.to_dict(), indent=2),
            encoding="utf-8",
        )
        logger.info("state.saved", path=str(self.state_path))

    def record_generation(
        self,
        intent: str,
        project_name: str,
        environment: str,
        region: str,
        governance_status: str,
        files: dict[str, str],
    ) -> None:
        """Record a generation event and update the file manifest.

        Args:
            intent: Raw natural-language intent.
            project_name: Parsed project name.
            environment: Target environment.
            region: Azure region.
            governance_status: PASS/FAIL/PASS_WITH_WARNINGS.
            files: Generated file path -> content mapping.
        """
        now = datetime.now(tz=UTC).isoformat()

        # Update state metadata
        if not self.state.created_at:
            self.state.created_at = now
        self.state.updated_at = now
        self.state.project_name = project_name
        self.state.intent_hash = self._hash(intent)
        self.state.last_intent = intent
        self.state.last_environment = environment
        self.state.last_region = region
        self.state.last_governance_status = governance_status

        # Update file manifest
        self.state.files = {}
        for path, content in files.items():
            self.state.files[path] = FileRecord(
                path=path,
                content_hash=self._hash(content),
                size_bytes=len(content.encode("utf-8")),
                generated_at=now,
            )

        # Record event in history
        event = GenerationEvent(
            timestamp=now,
            intent=intent,
            project_name=project_name,
            environment=environment,
            azure_region=region,
            file_count=len(files),
            governance_status=governance_status,
        )
        self.state.history.append(event)

        # Keep history manageable (last 20 events)
        if len(self.state.history) > 20:
            self.state.history = self.state.history[-20:]

        self.save()
        logger.info(
            "state.recorded",
            project=project_name,
            files=len(files),
            history_count=len(self.state.history),
        )

    def detect_drift(
        self,
        intent: str,
        environment: str = "",
        region: str = "",
    ) -> DriftResult:
        """Detect drift between current intent and previously generated state.

        Args:
            intent: New intent string to compare against last generation.
            environment: New environment (optional).
            region: New region (optional).

        Returns:
            DriftResult describing what has changed.
        """
        if not self.state.last_intent:
            return DriftResult(
                has_drift=True,
                summary="No previous generation found -- initial scaffold.",
            )

        changed: list[str] = []

        # Compare intent
        if self._hash(intent) != self.state.intent_hash:
            changed.append("intent")

        # Compare environment
        if environment and environment != self.state.last_environment:
            changed.append("environment")

        # Compare region
        if region and region != self.state.last_region:
            changed.append("region")

        # Check files on disk against manifest
        added: list[str] = []
        removed: list[str] = []
        modified: list[str] = []

        for path, record in self.state.files.items():
            disk_path = self.output_dir / path
            if not disk_path.exists():
                removed.append(path)
            else:
                content = disk_path.read_text(encoding="utf-8")
                if self._hash(content) != record.content_hash:
                    modified.append(path)

        # Check for files on disk not in manifest
        if self.output_dir.exists():
            for disk_file in self.output_dir.rglob("*"):
                if disk_file.is_file() and not str(disk_file.name).startswith("."):
                    rel = str(disk_file.relative_to(self.output_dir)).replace("\\", "/")
                    if rel not in self.state.files and not rel.startswith(".devex"):
                        added.append(rel)

        has_drift = bool(changed or added or removed or modified)

        parts: list[str] = []
        if changed:
            parts.append(f"Changed fields: {', '.join(changed)}")
        if added:
            parts.append(f"New files on disk: {len(added)}")
        if removed:
            parts.append(f"Deleted files: {len(removed)}")
        if modified:
            parts.append(f"Modified files: {len(modified)}")

        summary = "; ".join(parts) if parts else "No drift detected."

        return DriftResult(
            has_drift=has_drift,
            changed_fields=changed,
            added_files=added,
            removed_files=removed,
            modified_files=modified,
            summary=summary,
        )

    def get_generation_count(self) -> int:
        """Return the number of generation events recorded."""
        return len(self.state.history)

    def get_last_event(self) -> GenerationEvent | None:
        """Return the most recent generation event."""
        return self.state.history[-1] if self.state.history else None

    def get_file_manifest(self) -> dict[str, str]:
        """Return file path -> content hash mapping."""
        return {path: rec.content_hash for path, rec in self.state.files.items()}

    @staticmethod
    def _hash(content: str) -> str:
        """Create a content hash for drift detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
