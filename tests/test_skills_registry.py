"""Tests for Skills Registry -- discovery, registration, routing, execution."""

from __future__ import annotations

from typing import Any

from src.orchestrator.skills.registry import (
    SkillCategory,
    SkillMetadata,
    SkillRegistry,
    SkillResult,
    create_default_registry,
)

# ----------------- Test Helpers -----------------


class _DummySkill:
    """Minimal skill for testing."""

    def __init__(
        self,
        name: str = "dummy",
        capabilities: tuple[str, ...] = ("test_capability",),
        category: SkillCategory = SkillCategory.TESTING,
        priority: int = 100,
    ) -> None:
        self._meta = SkillMetadata(
            name=name,
            version="1.0.0",
            description=f"Test skill {name}",
            category=category,
            capabilities=capabilities,
            priority=priority,
        )

    @property
    def metadata(self) -> SkillMetadata:
        return self._meta

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"executed": True, "name": self._meta.name, **context}

    def can_handle(self, capability: str) -> bool:
        return capability.lower() in {c.lower() for c in self._meta.capabilities}


class _FailingSkill(_DummySkill):
    """Skill that always raises on execute."""

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("Intentional failure")


# ----------------- Registration -----------------


class TestSkillRegistration:
    def test_register_skill(self) -> None:
        reg = SkillRegistry()
        skill = _DummySkill("reg-test")
        reg.register(skill)
        assert reg.count == 1

    def test_register_duplicate_overwrites(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("dup"))
        reg.register(_DummySkill("dup"))
        assert reg.count == 1

    def test_unregister_removes_skill(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("to-remove"))
        assert reg.unregister("to-remove") is True
        assert reg.count == 0

    def test_unregister_nonexistent_returns_false(self) -> None:
        reg = SkillRegistry()
        assert reg.unregister("nope") is False

    def test_get_returns_registered_skill(self) -> None:
        reg = SkillRegistry()
        skill = _DummySkill("getter")
        reg.register(skill)
        assert reg.get("getter") is skill

    def test_get_returns_none_for_missing(self) -> None:
        reg = SkillRegistry()
        assert reg.get("missing") is None


# ----------------- Routing -----------------


class TestSkillRouting:
    def test_route_exact_match(self) -> None:
        reg = SkillRegistry()
        skill = _DummySkill("router", capabilities=("exact_cap",))
        reg.register(skill)
        found = reg.route("exact_cap")
        assert found is not None
        assert found.metadata.name == "router"

    def test_route_case_insensitive(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("ci", capabilities=("GovernanceCheck",)))
        assert reg.route("governancecheck") is not None

    def test_route_fuzzy_match(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("fuzzy", capabilities=("policy_evaluation",)))
        assert reg.route("policy") is not None

    def test_route_no_match_returns_none(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("x"))
        assert reg.route("nonexistent_capability_xyz") is None

    def test_route_priority_resolution(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("low", capabilities=("shared",), priority=200))
        reg.register(_DummySkill("high", capabilities=("shared",), priority=10))
        found = reg.route("shared")
        assert found is not None
        assert found.metadata.name == "high"

    def test_route_all_returns_sorted(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("a", capabilities=("multi",), priority=50))
        reg.register(_DummySkill("b", capabilities=("multi",), priority=10))
        reg.register(_DummySkill("c", capabilities=("multi",), priority=200))
        results = reg.route_all("multi")
        assert len(results) == 3
        assert results[0].metadata.name == "b"
        assert results[-1].metadata.name == "c"


# ----------------- Execution -----------------


class TestSkillExecution:
    def test_execute_success(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("exec"))
        result = reg.execute("exec", {"key": "val"})
        assert isinstance(result, SkillResult)
        assert result.success is True
        assert result.output["executed"] is True
        assert result.output["key"] == "val"
        assert result.duration_ms > 0

    def test_execute_missing_skill(self) -> None:
        reg = SkillRegistry()
        result = reg.execute("missing", {})
        assert result.success is False
        assert "not found" in result.error

    def test_execute_failure_captured(self) -> None:
        reg = SkillRegistry()
        reg.register(_FailingSkill("fail-me"))
        result = reg.execute("fail-me", {})
        assert result.success is False
        assert "Intentional failure" in result.error
        assert result.duration_ms >= 0


# ----------------- Listing -----------------


class TestSkillListing:
    def test_list_skills(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("a"))
        reg.register(_DummySkill("b"))
        skills = reg.list_skills()
        assert len(skills) == 2

    def test_list_by_category(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("t1", category=SkillCategory.TESTING))
        reg.register(_DummySkill("g1", category=SkillCategory.GOVERNANCE))
        reg.register(_DummySkill("t2", category=SkillCategory.TESTING))
        testing = reg.list_by_category(SkillCategory.TESTING)
        assert len(testing) == 2

    def test_list_capabilities(self) -> None:
        reg = SkillRegistry()
        reg.register(_DummySkill("x", capabilities=("cap_a", "cap_b")))
        caps = reg.list_capabilities()
        assert "cap_a" in caps
        assert "cap_b" in caps

    def test_count_property(self) -> None:
        reg = SkillRegistry()
        assert reg.count == 0
        reg.register(_DummySkill("one"))
        assert reg.count == 1


# ----------------- Default Registry -----------------


class TestDefaultRegistry:
    def test_creates_with_builtin_skills(self) -> None:
        reg = create_default_registry()
        assert reg.count >= 9  # 9 built-in skills

    def test_builtin_skills_have_metadata(self) -> None:
        reg = create_default_registry()
        for meta in reg.list_skills():
            assert meta.name
            assert meta.version
            assert meta.description
            assert meta.category
            assert len(meta.capabilities) > 0

    def test_routes_governance(self) -> None:
        reg = create_default_registry()
        skill = reg.route("governance_check")
        assert skill is not None

    def test_routes_bicep_generation(self) -> None:
        reg = create_default_registry()
        skill = reg.route("bicep_generation")
        assert skill is not None

    def test_routes_threat_modeling(self) -> None:
        reg = create_default_registry()
        skill = reg.route("threat_modeling")
        assert skill is not None

    def test_routes_naming(self) -> None:
        reg = create_default_registry()
        skill = reg.route("naming")
        assert skill is not None

    def test_routes_documentation(self) -> None:
        reg = create_default_registry()
        skill = reg.route("doc")
        assert skill is not None
