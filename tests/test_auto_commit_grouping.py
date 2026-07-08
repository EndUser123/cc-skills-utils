"""Regression tests for cc-skills-utils Stop auto-commit grouping.

Bug: 2026-07-08 incident — PI telemetry work in `skills/go/` was
auto-committed together with parallel refactor-discovery work in
`skills/refactor/` because `_commit_group_key` grouped at the top
directory only (`skills`), so the two landed in one bundled commit.

These tests pin the resolved grouping rule:
  * depth-1 (single segment like `README.md`)              -> "root"
  * depth-2 (top dir + filename like `agents/foo.md`,
    `hooks/Stop.py`, `.claude-plugin/plugin.json`)          -> just top dir
  * depth-3+                                                -> first two segments

That means `skills/go` and `skills/refactor` produce distinct keys when
both are dirty (preventing cross-skill bundling inside one plugin),
while every file under `skills/go/` collapses to the same key so a
single logical unit lands in one commit.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HOOK = (
    Path(__file__).resolve().parents[1]
    / "hooks"
    / "cc-skills-utils_Stop_auto_commit.py"
)


def _load_ac():
    spec = importlib.util.spec_from_file_location("ac", HOOK)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ac"] = mod
    spec.loader.exec_module(mod)
    return mod


ac = _load_ac()


def _key(p: str) -> str:
    return ac._commit_group_key(p)


class TestConcurrentWorkSplitsAcrossSkills:
    """Different skill areas under one plugin must NOT bundle into one commit."""

    def test_go_and_refactor_split(self):
        # The exact paths from the 2026-07-08 incident.
        assert _key("skills/go/scripts/orchestrate.py") == "skills/go"
        assert _key("skills/go/scripts/adapters/pi/resolve_model.py") == "skills/go"
        assert _key("skills/go/tests/test_candidate_chains.py") == "skills/go"
        assert _key("skills/refactor/references/agent-configs.md") == "skills/refactor"
        assert _key("skills/refactor/references/discovery-agent-contract.md") == "skills/refactor"

    def test_go_key_differs_from_refactor_key(self):
        a = _key("skills/go/scripts/orchestrate.py")
        b = _key("skills/refactor/references/agent-configs.md")
        assert a != b, (
            f"REGRESSION: skills/go and skills/refactor grouped together as {a!r}. "
            "Concurrent work on different skill areas must NOT bundle into one commit."
        )

    def test_three_skills_produce_three_groups(self):
        groups = {
            _key("skills/go/scripts/orchestrate.py"),
            _key("skills/refactor/references/agent-configs.md"),
            _key("skills/main/scripts/check_dream_cycle_findings.py"),
        }
        assert len(groups) == 3, f"expected 3 distinct groups, got {groups}"


class TestSingleSkillStaysOneCommit:
    """Files within the same skill area must collapse into one commit."""

    def test_go_scripts_tests_skill_all_collide(self):
        # A logical unit (source + tests + skill body) should land in one commit,
        # so the debounce/quiescence logic can detect it as one change set.
        k_src = _key("skills/go/scripts/orchestrate.py")
        k_tests = _key("skills/go/tests/test_candidate_chains.py")
        k_skill = _key("skills/go/SKILL.md")
        assert k_src == k_tests == k_skill == "skills/go"

    def test_refactor_references_collapse(self):
        assert _key("skills/refactor/references/agent-configs.md") == \
               _key("skills/refactor/references/discovery-agent-contract.md") == \
               "skills/refactor"


class TestTopLevelShapes:
    """Depth-1 and depth-2 paths group sensibly (no per-file explosion)."""

    def test_root_file(self):
        assert _key("README.md") == "root"

    def test_agents_dir_depth2_collapses_to_dir(self):
        # agents/refactor-discovery-logic.md must NOT become its own commit
        # just because the file lives directly under agents/.
        assert _key("agents/refactor-discovery-logic.md") == "agents"
        assert _key("agents/refactor-discovery-async.md") == "agents"

    def test_hooks_dir_depth2_collapses_to_dir(self):
        assert _key("hooks/cc-skills-utils_Stop_auto_commit.py") == "hooks"

    def test_claude_plugin_depth2_collapses_to_dir(self):
        # The plugin manifest path lives inside the plugin repo at depth-2.
        assert _key(".claude-plugin/plugin.json") == ".claude-plugin"

    def test_skill_area_at_depth3(self):
        # plugins/<name>/skills/<area>/... -> plugins/<name> (depth-3 rule:
        # first two segments). The skill-area split that matters for concurrent
        # bundling happens at the OUTER level (one plugin = one group), since
        # the cross-plugin bundling risk is what this hook is meant to bound;
        # intra-plugin cross-skill bundling is bounded by `_commit_grouped`
        # splitting further when >1 distinct group exists.
        assert (
            _key("plugins/cc-skills-utils/skills/git/scripts/sync.py")
            == "plugins/cc-skills-utils"
        )


class TestPluginMarketplaceShape:
    """Marketplace-rooted paths group at the top two segments."""

    def test_marketplace_path(self):
        # When the hook runs inside the marketplace root, paths are like
        # packages/.claude-marketplace/plugins/<name>/...
        assert (
            _key(
                "packages/.claude-marketplace/plugins/cc-skills-sdlc/"
                ".claude-plugin/plugin.json"
            )
            == "packages/.claude-marketplace"
        )