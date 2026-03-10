"""Tests for the State Management module.

Covers StateManager, ProjectState, FileRecord, GenerationEvent,
DriftResult -- including persistence, drift detection, and history capping.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.orchestrator.state import (
    DriftResult,
    FileRecord,
    GenerationEvent,
    ProjectState,
    StateManager,
)

# ---------------------------------------------------------------------------
# FileRecord
# ---------------------------------------------------------------------------


class TestFileRecord:
    """Tests for the FileRecord dataclass."""

    def test_create(self) -> None:
        rec = FileRecord(
            path="infra/bicep/main.bicep",
            content_hash="abc123",
            size_bytes=1024,
            generated_at="2025-01-01T00:00:00+00:00",
        )
        assert rec.path == "infra/bicep/main.bicep"
        assert rec.content_hash == "abc123"
        assert rec.size_bytes == 1024

    def test_generated_at(self) -> None:
        rec = FileRecord(path="f.txt", content_hash="x", size_bytes=0, generated_at="ts")
        assert rec.generated_at == "ts"


# ---------------------------------------------------------------------------
# GenerationEvent
# ---------------------------------------------------------------------------


class TestGenerationEvent:
    """Tests for the GenerationEvent dataclass."""

    def test_create(self) -> None:
        event = GenerationEvent(
            timestamp="2025-01-01T00:00:00+00:00",
            intent="Build API",
            project_name="my-api",
            environment="dev",
            azure_region="eastus2",
            file_count=22,
            governance_status="PASS",
        )
        assert event.project_name == "my-api"
        assert event.file_count == 22
        assert event.standards_version == "1.0.0"

    def test_custom_standards_version(self) -> None:
        event = GenerationEvent(
            timestamp="ts",
            intent="x",
            project_name="p",
            environment="dev",
            azure_region="eastus2",
            file_count=1,
            governance_status="PASS",
            standards_version="2.0.0",
        )
        assert event.standards_version == "2.0.0"


# ---------------------------------------------------------------------------
# DriftResult
# ---------------------------------------------------------------------------


class TestDriftResult:
    """Tests for the DriftResult dataclass."""

    def test_no_drift(self) -> None:
        result = DriftResult(has_drift=False, summary="No drift detected.")
        assert not result.has_drift
        assert result.changed_fields == []

    def test_with_drift(self) -> None:
        result = DriftResult(
            has_drift=True,
            changed_fields=["intent", "environment"],
            modified_files=["main.bicep"],
            summary="Changed fields: intent, environment",
        )
        assert result.has_drift
        assert len(result.changed_fields) == 2
        assert "main.bicep" in result.modified_files

    def test_defaults(self) -> None:
        result = DriftResult(has_drift=False)
        assert result.added_files == []
        assert result.removed_files == []
        assert result.modified_files == []
        assert result.summary == ""


# ---------------------------------------------------------------------------
# ProjectState serialization
# ---------------------------------------------------------------------------


class TestProjectState:
    """Tests for ProjectState serialisation round-trip."""

    def test_empty_state_roundtrip(self) -> None:
        state = ProjectState()
        data = state.to_dict()
        restored = ProjectState.from_dict(data)
        assert restored.version == "1.0.0"
        assert restored.files == {}
        assert restored.history == []

    def test_full_state_roundtrip(self) -> None:
        state = ProjectState(
            version="1.0.0",
            project_name="my-api",
            created_at="2025-01-01T00:00:00+00:00",
            updated_at="2025-01-02T00:00:00+00:00",
            intent_hash="abc123",
            plan_hash="def456",
            last_intent="Build an API",
            last_environment="dev",
            last_region="eastus2",
            last_governance_status="PASS",
            files={
                "main.bicep": FileRecord(
                    path="main.bicep",
                    content_hash="hash1",
                    size_bytes=500,
                    generated_at="2025-01-01T00:00:00+00:00",
                )
            },
            history=[
                GenerationEvent(
                    timestamp="2025-01-01T00:00:00+00:00",
                    intent="Build an API",
                    project_name="my-api",
                    environment="dev",
                    azure_region="eastus2",
                    file_count=1,
                    governance_status="PASS",
                )
            ],
        )
        data = state.to_dict()
        restored = ProjectState.from_dict(data)
        assert restored.project_name == "my-api"
        assert "main.bicep" in restored.files
        assert restored.files["main.bicep"].content_hash == "hash1"
        assert len(restored.history) == 1
        assert restored.history[0].project_name == "my-api"

    def test_json_serialization(self) -> None:
        state = ProjectState(project_name="test")
        text = json.dumps(state.to_dict(), indent=2)
        data = json.loads(text)
        restored = ProjectState.from_dict(data)
        assert restored.project_name == "test"

    def test_from_dict_missing_keys(self) -> None:
        """Handles missing keys gracefully with defaults."""
        restored = ProjectState.from_dict({})
        assert restored.version == "1.0.0"
        assert restored.project_name == ""


# ---------------------------------------------------------------------------
# StateManager -- core functionality
# ---------------------------------------------------------------------------


class TestStateManagerBasics:
    """Tests for StateManager initialization and persistence."""

    def test_creates_new_state(self, tmp_path: Path) -> None:
        mgr = StateManager(tmp_path)
        assert mgr.state.version == "1.0.0"
        assert mgr.get_generation_count() == 0

    def test_save_and_reload(self, tmp_path: Path) -> None:
        mgr = StateManager(tmp_path)
        mgr.state.project_name = "test-project"
        mgr.save()
        assert (tmp_path / ".devex" / "state.json").exists()

        mgr2 = StateManager(tmp_path)
        assert mgr2.state.project_name == "test-project"

    def test_invalid_json_resets(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".devex"
        state_dir.mkdir(parents=True)
        (state_dir / "state.json").write_text("{bad json", encoding="utf-8")

        mgr = StateManager(tmp_path)
        assert mgr.state.version == "1.0.0"
        assert mgr.state.project_name == ""

    def test_get_last_event_none(self, tmp_path: Path) -> None:
        mgr = StateManager(tmp_path)
        assert mgr.get_last_event() is None


# ---------------------------------------------------------------------------
# StateManager -- record_generation
# ---------------------------------------------------------------------------


class TestStateManagerRecordGeneration:
    """Tests for StateManager.record_generation()."""

    @pytest.fixture()
    def sample_files(self) -> dict[str, str]:
        return {
            "infra/bicep/main.bicep": "param location string",
            "src/app/main.py": "print('hello')",
            "README.md": "# My Project",
        }

    def test_records_event(self, tmp_path: Path, sample_files: dict[str, str]) -> None:
        mgr = StateManager(tmp_path)
        mgr.record_generation(
            intent="Build an API",
            project_name="my-api",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=sample_files,
        )
        assert mgr.get_generation_count() == 1
        assert mgr.state.project_name == "my-api"
        assert mgr.state.last_environment == "dev"
        assert mgr.state.last_region == "eastus2"

    def test_creates_file_manifest(self, tmp_path: Path, sample_files: dict[str, str]) -> None:
        mgr = StateManager(tmp_path)
        mgr.record_generation(
            intent="Build API",
            project_name="api",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=sample_files,
        )
        assert len(mgr.state.files) == 3
        assert "infra/bicep/main.bicep" in mgr.state.files
        rec = mgr.state.files["infra/bicep/main.bicep"]
        assert rec.content_hash != ""
        assert rec.size_bytes == len(b"param location string")

    def test_records_intent_hash(self, tmp_path: Path, sample_files: dict[str, str]) -> None:
        mgr = StateManager(tmp_path)
        mgr.record_generation(
            intent="Build an API",
            project_name="api",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=sample_files,
        )
        assert mgr.state.intent_hash != ""
        assert len(mgr.state.intent_hash) == 16

    def test_persists_state(self, tmp_path: Path, sample_files: dict[str, str]) -> None:
        mgr = StateManager(tmp_path)
        mgr.record_generation(
            intent="Build API",
            project_name="api",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=sample_files,
        )
        # Reload from disk
        mgr2 = StateManager(tmp_path)
        assert mgr2.get_generation_count() == 1
        assert mgr2.state.project_name == "api"

    def test_multiple_generations(self, tmp_path: Path, sample_files: dict[str, str]) -> None:
        mgr = StateManager(tmp_path)
        for i in range(3):
            mgr.record_generation(
                intent=f"Intent {i}",
                project_name=f"project-{i}",
                environment="dev",
                region="eastus2",
                governance_status="PASS",
                files=sample_files,
            )
        assert mgr.get_generation_count() == 3
        last = mgr.get_last_event()
        assert last is not None
        assert last.project_name == "project-2"

    def test_history_capped_at_20(self, tmp_path: Path) -> None:
        mgr = StateManager(tmp_path)
        files = {"f.txt": "content"}
        for i in range(25):
            mgr.record_generation(
                intent=f"Intent {i}",
                project_name="proj",
                environment="dev",
                region="eastus2",
                governance_status="PASS",
                files=files,
            )
        assert mgr.get_generation_count() == 20
        assert mgr.state.history[0].intent == "Intent 5"
        assert mgr.state.history[-1].intent == "Intent 24"

    def test_created_at_set_once(self, tmp_path: Path, sample_files: dict[str, str]) -> None:
        mgr = StateManager(tmp_path)
        mgr.record_generation(
            intent="First",
            project_name="p",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=sample_files,
        )
        first_created = mgr.state.created_at

        mgr.record_generation(
            intent="Second",
            project_name="p",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=sample_files,
        )
        assert mgr.state.created_at == first_created
        assert mgr.state.updated_at != first_created

    def test_get_file_manifest(self, tmp_path: Path, sample_files: dict[str, str]) -> None:
        mgr = StateManager(tmp_path)
        mgr.record_generation(
            intent="Intent",
            project_name="p",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=sample_files,
        )
        manifest = mgr.get_file_manifest()
        assert len(manifest) == 3
        assert all(isinstance(v, str) for v in manifest.values())


# ---------------------------------------------------------------------------
# StateManager -- drift detection
# ---------------------------------------------------------------------------


class TestStateManagerDriftDetection:
    """Tests for StateManager.detect_drift()."""

    @pytest.fixture()
    def _populated(self, tmp_path: Path) -> StateManager:
        """Fixture that creates a StateManager with a recorded generation."""
        files = {
            "main.bicep": "param location string",
            "app.py": "print('hello')",
        }
        mgr = StateManager(tmp_path)
        mgr.record_generation(
            intent="Build an API",
            project_name="my-api",
            environment="dev",
            region="eastus2",
            governance_status="PASS",
            files=files,
        )
        # Write the actual files to disk for drift comparison
        for path, content in files.items():
            (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / path).write_text(content, encoding="utf-8")
        return mgr

    def test_no_drift_same_intent(self, _populated: StateManager, tmp_path: Path) -> None:
        drift = _populated.detect_drift(
            intent="Build an API",
            environment="dev",
            region="eastus2",
        )
        assert not drift.has_drift

    def test_detects_intent_change(self, _populated: StateManager) -> None:
        drift = _populated.detect_drift(intent="Build a completely different thing")
        assert drift.has_drift
        assert "intent" in drift.changed_fields

    def test_detects_environment_change(self, _populated: StateManager) -> None:
        drift = _populated.detect_drift(
            intent="Build an API",
            environment="prod",
        )
        assert drift.has_drift
        assert "environment" in drift.changed_fields

    def test_detects_region_change(self, _populated: StateManager) -> None:
        drift = _populated.detect_drift(
            intent="Build an API",
            region="westus2",
        )
        assert drift.has_drift
        assert "region" in drift.changed_fields

    def test_detects_modified_file(self, _populated: StateManager, tmp_path: Path) -> None:
        # Modify a file on disk
        (tmp_path / "main.bicep").write_text("CHANGED CONTENT", encoding="utf-8")
        drift = _populated.detect_drift(
            intent="Build an API",
            environment="dev",
            region="eastus2",
        )
        assert drift.has_drift
        assert "main.bicep" in drift.modified_files

    def test_detects_removed_file(self, _populated: StateManager, tmp_path: Path) -> None:
        (tmp_path / "app.py").unlink()
        drift = _populated.detect_drift(
            intent="Build an API",
            environment="dev",
            region="eastus2",
        )
        assert drift.has_drift
        assert "app.py" in drift.removed_files

    def test_detects_added_file(self, _populated: StateManager, tmp_path: Path) -> None:
        (tmp_path / "extra.txt").write_text("bonus", encoding="utf-8")
        drift = _populated.detect_drift(
            intent="Build an API",
            environment="dev",
            region="eastus2",
        )
        assert drift.has_drift
        assert "extra.txt" in drift.added_files

    def test_initial_scaffold_drift(self, tmp_path: Path) -> None:
        """First-time generation shows drift (no previous)."""
        mgr = StateManager(tmp_path)
        drift = mgr.detect_drift(intent="Build API")
        assert drift.has_drift
        assert "initial scaffold" in drift.summary.lower()

    def test_drift_summary_format(self, _populated: StateManager) -> None:
        drift = _populated.detect_drift(
            intent="Different intent",
            environment="staging",
        )
        assert drift.has_drift
        assert "Changed fields" in drift.summary

    def test_no_drift_empty_env_region(self, _populated: StateManager, tmp_path: Path) -> None:
        """Empty env/region strings skip comparison (not considered drift)."""
        drift = _populated.detect_drift(
            intent="Build an API",
            environment="",
            region="",
        )
        assert not drift.has_drift


# ---------------------------------------------------------------------------
# StateManager -- hash function
# ---------------------------------------------------------------------------


class TestStateManagerHash:
    """Tests for the _hash static method."""

    def test_deterministic(self) -> None:
        h1 = StateManager._hash("hello world")
        h2 = StateManager._hash("hello world")
        assert h1 == h2

    def test_different_inputs(self) -> None:
        h1 = StateManager._hash("hello")
        h2 = StateManager._hash("world")
        assert h1 != h2

    def test_hash_length(self) -> None:
        h = StateManager._hash("test content")
        assert len(h) == 16

    def test_hex_characters(self) -> None:
        h = StateManager._hash("content")
        assert all(c in "0123456789abcdef" for c in h)
