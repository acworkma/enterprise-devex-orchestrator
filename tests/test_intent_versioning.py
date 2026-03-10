"""Tests for the Intent File Parser and Version Manager.

Validates the complete describe -> run -> iterate workflow:
  - Parsing intent.md files into structured data
  - Generating intent templates
  - Version tracking and upgrade planning
  - Rollback support
"""

from __future__ import annotations

import json
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from src.orchestrator.intent_file import (
    IntentFileParser,
    IntentFileResult,
    IntentFileVersion,
    generate_intent_template,
    generate_upgrade_template,
)
from src.orchestrator.versioning import (
    UpgradePlan,
    VersionManager,
    VersionRecord,
    VersionState,
)

# ===============================================
# Intent File Parser Tests
# ===============================================


class TestIntentFileParser:
    """Test parsing of intent.md files."""

    def test_parse_full_intent_file(self) -> None:
        """Parse a complete intent.md with all sections."""
        parser = IntentFileParser()
        content = textwrap.dedent("""\
            # my-cool-api

            > Build a secure REST API with blob storage for document management.

            ## Configuration

            - **App Type**: api
            - **Data Stores**: blob, cosmos
            - **Region**: eastus2
            - **Environment**: dev
            - **Auth**: managed-identity
            - **Compliance**: SOC2

            ## Version

            - **Version**: 1
            - **Based On**: none
            - **Changes**: Initial scaffold

            ## Notes

            Must support 10,000 concurrent users.
        """)
        result = parser.parse_string(content)

        assert result.project_name == "my-cool-api"
        assert "secure REST API" in result.intent
        assert result.config["app_type"] == "api"
        assert result.config["data_stores"] == "blob, cosmos"
        assert result.config["region"] == "eastus2"
        assert result.config["environment"] == "dev"
        assert result.config["auth"] == "managed-identity"
        assert result.config["compliance"] == "SOC2"
        assert result.version_info.version == 1
        assert result.version_info.based_on is None
        assert result.version_info.changes == "Initial scaffold"
        assert "10,000 concurrent users" in result.notes

    def test_parse_minimal_intent(self) -> None:
        """Parse an intent file with just a title and description."""
        parser = IntentFileParser()
        content = textwrap.dedent("""\
            # simple-api

            > Build a REST API with blob storage.
        """)
        result = parser.parse_string(content)

        assert result.project_name == "simple-api"
        assert "REST API" in result.intent
        assert result.version_info.version == 1

    def test_parse_plain_text_fallback(self) -> None:
        """When no markdown structure, treat entire content as intent."""
        parser = IntentFileParser()
        content = "Build a secure API with blob storage and Redis cache."
        result = parser.parse_string(content)

        assert "secure API" in result.intent
        assert "Redis" in result.intent

    def test_parse_upgrade_intent(self) -> None:
        """Parse a v2 upgrade intent file."""
        parser = IntentFileParser()
        content = textwrap.dedent("""\
            # my-cool-api

            > Build a secure REST API with blob storage and Redis cache.

            ## Configuration

            - **App Type**: api
            - **Data Stores**: blob, cosmos, redis
            - **Region**: eastus2
            - **Environment**: dev

            ## Version

            - **Version**: 2
            - **Based On**: 1
            - **Changes**: Add Redis cache for session management
        """)
        result = parser.parse_string(content)

        assert result.version_info.version == 2
        assert result.version_info.based_on == 1
        assert result.version_info.is_upgrade is True
        assert "Redis" in result.version_info.changes

    def test_full_intent_builds_complete_string(self) -> None:
        """full_intent combines blockquote + config + notes."""
        parser = IntentFileParser()
        content = textwrap.dedent("""\
            # test-project

            > Build a secure API.

            ## Configuration

            - **App Type**: api
            - **Region**: westus2

            ## Notes

            Needs high availability.
        """)
        result = parser.parse_string(content)
        full = result.full_intent

        assert "secure API" in full
        assert "Application type: api" in full
        assert "Azure region: westus2" in full
        assert "high availability" in full

    def test_parse_empty_raises(self) -> None:
        """Empty content raises ValueError."""
        parser = IntentFileParser()
        with pytest.raises(ValueError, match="empty"):
            parser.parse_string("")

    def test_parse_file_not_found(self, tmp_path: Path) -> None:
        """Missing file raises FileNotFoundError."""
        parser = IntentFileParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(tmp_path / "nonexistent.md")

    def test_parse_from_file(self, tmp_path: Path) -> None:
        """Parse from an actual file on disk."""
        content = textwrap.dedent("""\
            # file-project

            > Build an event-driven worker with Cosmos DB.

            ## Configuration

            - **App Type**: worker
            - **Data Stores**: cosmos
        """)
        intent_path = tmp_path / "intent.md"
        intent_path.write_text(content, encoding="utf-8")

        parser = IntentFileParser()
        result = parser.parse(intent_path)

        assert result.project_name == "file-project"
        assert "event-driven" in result.intent
        assert result.config["app_type"] == "worker"
        assert result.source_path == str(intent_path)

    def test_version_not_upgrade_when_v1(self) -> None:
        """v1 is not an upgrade."""
        v = IntentFileVersion(version=1, based_on=None)
        assert v.is_upgrade is False

    def test_version_is_upgrade_when_based_on(self) -> None:
        """v2 based on v1 is an upgrade."""
        v = IntentFileVersion(version=2, based_on=1)
        assert v.is_upgrade is True

    def test_parse_alternative_section_names(self) -> None:
        """Parser handles 'Settings' instead of 'Configuration'."""
        parser = IntentFileParser()
        content = textwrap.dedent("""\
            # alt-project

            > Build an API.

            ## Settings

            - **App Type**: web
            - **Region**: northeurope
        """)
        result = parser.parse_string(content)
        assert result.config["app_type"] == "web"
        assert result.config["region"] == "northeurope"

    def test_parse_no_blockquote_uses_body(self) -> None:
        """When there's no blockquote, use the body text as intent."""
        parser = IntentFileParser()
        content = textwrap.dedent("""\
            # body-intent-project

            Build a secure worker service for batch processing.

            ## Configuration

            - **App Type**: worker
        """)
        result = parser.parse_string(content)
        assert "batch processing" in result.intent


# ===============================================
# Template Generation Tests
# ===============================================


class TestTemplateGeneration:
    """Test intent.md template generation."""

    def test_generate_v1_template(self) -> None:
        """Generate a v1 template."""
        template = generate_intent_template(project_name="test-api")
        assert "# test-api" in template
        assert "**Version**: 1" in template
        assert "**Based On**: none" in template
        assert "## Problem Statement" in template
        assert "## Business Goals" in template
        assert "## Acceptance Criteria" in template

    def test_generate_v2_template(self) -> None:
        """Generate a v2 template."""
        template = generate_intent_template(
            project_name="test-api", version=2, based_on=1
        )
        assert "**Version**: 2" in template
        assert "**Based On**: 1" in template
        assert "Describe your changes" in template

    def test_generate_upgrade_template(self) -> None:
        """Generate upgrade template from existing project data."""
        template = generate_upgrade_template(
            project_name="my-api",
            current_version=1,
            current_intent="Build a secure API with blob storage.",
        )
        assert "# my-api" in template
        assert "**Version**: 2" in template
        assert "**Based On**: 1" in template
        assert "UPGRADE from v1" in template

    def test_template_is_parseable(self) -> None:
        """Generated template can be parsed back by the parser."""
        template = generate_intent_template(project_name="roundtrip-test")
        parser = IntentFileParser()
        result = parser.parse_string(template)

        assert result.project_name == "roundtrip-test"
        assert result.version_info.version == 1
        assert result.config.get("app_type") == "api"


# ===============================================
# Version Manager Tests
# ===============================================


class TestVersionManager:
    """Test versioned project iterations."""

    def _make_intent_result(
        self, version: int = 1, based_on: int | None = None, changes: str = ""
    ) -> IntentFileResult:
        """Create a mock IntentFileResult for testing."""
        return IntentFileResult(
            intent="Build a secure API",
            project_name="test-project",
            config={"app_type": "api", "region": "eastus2"},
            version_info=IntentFileVersion(
                version=version, based_on=based_on, changes=changes
            ),
        )

    def test_initial_state_empty(self, tmp_path: Path) -> None:
        """New VersionManager has no versions."""
        vm = VersionManager(tmp_path)
        assert vm.current_version == 0
        assert vm.has_versions is False
        assert vm.get_current() is None

    def test_record_v1(self, tmp_path: Path) -> None:
        """Record a v1 version."""
        vm = VersionManager(tmp_path)
        intent = self._make_intent_result(version=1, changes="Initial scaffold")

        record = vm.record_version(intent, file_count=42, governance_status="PASS")

        assert record.version == 1
        assert record.status == "active"
        assert record.file_count == 42
        assert record.governance_status == "PASS"
        assert vm.current_version == 1
        assert vm.has_versions is True

    def test_record_v2_supersedes_v1(self, tmp_path: Path) -> None:
        """Recording v2 marks v1 as superseded."""
        vm = VersionManager(tmp_path)

        v1_intent = self._make_intent_result(version=1, changes="Initial")
        vm.record_version(v1_intent, file_count=40)

        v2_intent = self._make_intent_result(
            version=2, based_on=1, changes="Add Redis"
        )
        vm.record_version(v2_intent, file_count=45)

        assert vm.current_version == 2
        assert vm.get_version(1).status == "superseded"
        assert vm.get_version(2).status == "active"

    def test_persistence(self, tmp_path: Path) -> None:
        """Version state is persisted and reloaded."""
        vm1 = VersionManager(tmp_path)
        intent = self._make_intent_result(version=1, changes="Initial")
        vm1.record_version(intent, file_count=30)

        # Reload from disk
        vm2 = VersionManager(tmp_path)
        assert vm2.current_version == 1
        assert vm2.has_versions is True
        assert vm2.get_version(1).changes == "Initial"

    def test_plan_upgrade(self, tmp_path: Path) -> None:
        """Create an upgrade plan from v1 to v2."""
        vm = VersionManager(tmp_path)
        v1 = self._make_intent_result(version=1, changes="Initial")
        vm.record_version(v1, file_count=40)

        v2 = self._make_intent_result(
            version=2, based_on=1, changes="Add Redis cache"
        )
        plan = vm.plan_upgrade(v2)

        assert plan.from_version == 1
        assert plan.to_version == 2
        assert "Redis" in plan.changes
        assert plan.add_promotion_workflow is True
        assert len(plan.notes) > 0

    def test_rollback(self, tmp_path: Path) -> None:
        """Rollback from v2 to v1."""
        vm = VersionManager(tmp_path)

        v1 = self._make_intent_result(version=1)
        vm.record_version(v1, file_count=40)

        v2 = self._make_intent_result(version=2, based_on=1)
        vm.record_version(v2, file_count=45)

        assert vm.current_version == 2

        success = vm.rollback(to_version=1)
        assert success is True
        assert vm.current_version == 1
        assert vm.get_version(1).status == "active"
        assert vm.get_version(2).status == "rolled-back"

    def test_rollback_nonexistent_fails(self, tmp_path: Path) -> None:
        """Can't roll back to a version that doesn't exist."""
        vm = VersionManager(tmp_path)
        v1 = self._make_intent_result(version=1)
        vm.record_version(v1)

        assert vm.rollback(to_version=99) is False

    def test_history(self, tmp_path: Path) -> None:
        """Get version history as list."""
        vm = VersionManager(tmp_path)

        for i in range(1, 4):
            intent = self._make_intent_result(
                version=i,
                based_on=i - 1 if i > 1 else None,
                changes=f"Version {i}",
            )
            vm.record_version(intent, file_count=40 + i)

        history = vm.get_history()
        assert len(history) == 3
        assert history[0]["version"] == 1
        assert history[2]["version"] == 3
        assert history[2]["status"] == "active"

    def test_version_state_serialization(self) -> None:
        """VersionState round-trips through dict."""
        state = VersionState(
            project_name="test",
            current_version=2,
            versions={
                1: VersionRecord(
                    version=1,
                    intent="Build API",
                    intent_hash="abc123",
                    changes="Initial",
                    created_at="2025-01-01T00:00:00Z",
                    status="superseded",
                ),
                2: VersionRecord(
                    version=2,
                    intent="Build API v2",
                    intent_hash="def456",
                    changes="Add Redis",
                    created_at="2025-01-02T00:00:00Z",
                    based_on=1,
                ),
            },
        )

        data = state.to_dict()
        restored = VersionState.from_dict(data)

        assert restored.current_version == 2
        assert restored.versions[1].status == "superseded"
        assert restored.versions[2].based_on == 1

    def test_upgrade_plan_summary(self) -> None:
        """UpgradePlan produces readable summary."""
        plan = UpgradePlan(
            from_version=1,
            to_version=2,
            changes="Add Redis",
            new_intent="Build API with Redis",
            previous_intent="Build API",
        )
        summary = plan.summary
        assert "v1" in summary
        assert "v2" in summary
        assert "Redis" in summary

    def test_versions_json_file_created(self, tmp_path: Path) -> None:
        """Recording a version creates .devex/versions.json."""
        vm = VersionManager(tmp_path)
        intent = self._make_intent_result(version=1)
        vm.record_version(intent, file_count=10)

        version_file = tmp_path / ".devex" / "versions.json"
        assert version_file.exists()

        data = json.loads(version_file.read_text(encoding="utf-8"))
        assert data["current_version"] == 1
        assert "1" in data["versions"]


# ===============================================
# CI/CD Promotion Tests
# ===============================================


class TestCICDPromotion:
    """Test CI/CD workflow generation with version promotion."""

    @staticmethod
    def _spec():
        from src.orchestrator.intent_schema import IntentSpec

        return IntentSpec(
            project_name="test-project",
            description="Test project",
            raw_intent="Build a test project",
        )

    def test_v1_no_promotion_workflow(self) -> None:
        """v1 doesn't get promotion/rollback workflows."""
        from src.orchestrator.generators.cicd_generator import CICDGenerator

        gen = CICDGenerator()
        files = gen.generate(self._spec(), version=1)

        assert ".github/workflows/validate.yml" in files
        assert ".github/workflows/deploy.yml" in files
        assert ".github/workflows/promote.yml" not in files
        assert ".github/workflows/rollback.yml" not in files

    def test_v2_gets_promotion_workflow(self) -> None:
        """v2+ gets promotion and rollback workflows."""
        from src.orchestrator.generators.cicd_generator import CICDGenerator

        gen = CICDGenerator()
        files = gen.generate(self._spec(), version=2)

        assert ".github/workflows/promote.yml" in files
        assert ".github/workflows/rollback.yml" in files

    def test_promote_workflow_has_health_check(self) -> None:
        """Promotion workflow includes health checking."""
        from src.orchestrator.generators.cicd_generator import CICDGenerator

        gen = CICDGenerator()
        files = gen.generate(self._spec(), version=2)

        promote = files[".github/workflows/promote.yml"]
        assert "health" in promote.lower()
        assert "revision" in promote.lower()
        assert "traffic" in promote.lower()

    def test_rollback_workflow_has_traffic_shift(self) -> None:
        """Rollback workflow shifts traffic back."""
        from src.orchestrator.generators.cicd_generator import CICDGenerator

        gen = CICDGenerator()
        files = gen.generate(self._spec(), version=2)

        rollback = files[".github/workflows/rollback.yml"]
        assert "rollback" in rollback.lower()
        assert "revision" in rollback.lower()


# ===============================================
# End-to-End Workflow Test
# ===============================================


class TestEndToEndWorkflow:
    """Test the full describe -> scaffold -> upgrade workflow."""

    def test_full_lifecycle(self, tmp_path: Path) -> None:
        """Simulate: create intent -> scaffold v1 -> create v2 -> upgrade."""
        # Step 1: Create intent.md
        template = generate_intent_template(project_name="lifecycle-test")
        intent_path = tmp_path / "intent.md"
        intent_path.write_text(template, encoding="utf-8")

        # Step 2: Parse it
        parser = IntentFileParser()
        v1_result = parser.parse(intent_path)
        assert v1_result.project_name == "lifecycle-test"
        assert v1_result.version_info.version == 1
        assert v1_result.version_info.is_upgrade is False

        # Step 3: Record v1 in version manager
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        vm = VersionManager(project_dir)
        vm.record_version(v1_result, file_count=42, governance_status="PASS")

        assert vm.current_version == 1

        # Step 4: Create upgrade template
        upgrade_template = generate_upgrade_template(
            project_name="lifecycle-test",
            current_version=1,
            current_intent=v1_result.full_intent,
        )
        v2_path = tmp_path / "intent.v2.md"
        v2_path.write_text(upgrade_template, encoding="utf-8")

        # Step 5: Parse upgrade intent
        v2_result = parser.parse(v2_path)
        assert v2_result.version_info.version == 2
        assert v2_result.version_info.based_on == 1
        assert v2_result.version_info.is_upgrade is True

        # Step 6: Plan upgrade
        plan = vm.plan_upgrade(v2_result)
        assert plan.from_version == 1
        assert plan.to_version == 2
        assert plan.add_promotion_workflow is True

        # Step 7: Record v2
        vm.record_version(v2_result, file_count=48, governance_status="PASS")
        assert vm.current_version == 2
        assert vm.get_version(1).status == "superseded"

        # Step 8: Rollback to v1
        assert vm.rollback(to_version=1) is True
        assert vm.current_version == 1

        # Step 9: History shows all versions
        history = vm.get_history()
        assert len(history) == 2

    def test_anyone_can_clone_and_scaffold(self, tmp_path: Path) -> None:
        """Simulate: clone repo -> edit intent.md -> scaffold."""
        # Simulate cloning: copy intent.md to a new directory
        clone_dir = tmp_path / "cloned-repo"
        clone_dir.mkdir()

        # Write custom intent
        custom_intent = textwrap.dedent("""\
            # my-custom-project

            > Build a real-time event processing system with Cosmos DB and Service Bus.

            ## Configuration

            - **App Type**: event-driven
            - **Data Stores**: cosmos
            - **Region**: westeurope
            - **Environment**: staging
            - **Auth**: managed-identity
            - **Compliance**: SOC2

            ## Version

            - **Version**: 1
            - **Based On**: none
            - **Changes**: Custom initial scaffold for event processing
        """)
        intent_path = clone_dir / "intent.md"
        intent_path.write_text(custom_intent, encoding="utf-8")

        # Parse it
        parser = IntentFileParser()
        result = parser.parse(intent_path)

        assert result.project_name == "my-custom-project"
        assert "event processing" in result.intent
        assert result.config["app_type"] == "event-driven"
        assert result.config["region"] == "westeurope"
        assert result.config["environment"] == "staging"
        assert result.version_info.version == 1

        # Full intent string is complete enough for the pipeline
        full = result.full_intent
        assert "event processing" in full
        assert "westeurope" in full
