"""Tests for plugin-audit-and-fix.py — drift sync, stale cleanup, and bump cache logic."""

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import importlib.util

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "plugin-audit-and-fix.py"
_spec = importlib.util.spec_from_file_location("plugin_audit", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

audit_source_cache_drift = _mod.audit_source_cache_drift
bump_version = _mod.bump_version
bidir_sync = _mod.bidir_sync
main = _mod.main


def _make_plugin(packages_dir: Path, name: str = "test-pkg", version: str = "1.0.0") -> Path:
    """Create a minimal plugin structure under packages_dir/<name>."""
    pkg = packages_dir / name
    manifest_dir = pkg / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(json.dumps({"name": name, "version": version}))
    skills = pkg / "skills" / "myskill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# myskill\n")
    return pkg


def _make_cache(cache_root: Path, name: str, version: str, content: str = "# myskill\n") -> Path:
    """Create a cache dir at cache_root/<name>/<version>."""
    cache = cache_root / name / version
    cache.mkdir(parents=True)
    skills = cache / "skills" / "myskill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(content)
    return cache


def _patch_expanduser(cache_root: Path, installed_path: Path | None = None, settings_path: Path | None = None):
    """Patch os.path.expanduser to redirect plugin cache paths to test fixtures.

    Redirects:
      ~/.claude/plugins/cache/local  → cache_root
      ~/.claude/plugins/installed_plugins.json → installed_path (if provided)
      ~/.claude/settings.json → settings_path (if provided)
    """
    original = os.path.expanduser

    def _expanduser(path: str) -> str:
        if path == "~/.claude/plugins/cache/local":
            return str(cache_root)
        if installed_path is not None and path == "~/.claude/plugins/installed_plugins.json":
            return str(installed_path)
        if settings_path is not None and path == "~/.claude/settings.json":
            return str(settings_path)
        return original(path)

    # Patch on the module's bound os reference so the module's import picks it up
    return patch.object(_mod.os.path, "expanduser", _expanduser)


class TestBidirSync:
    """Unit tests for bidir_sync function."""

    def test_identical_files_no_op(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (src / "f.txt").write_text("hello")
        (cache / "f.txt").write_text("hello")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 0
        assert stats["skipped"] == 0

    def test_source_wins_over_older_cache(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "f.txt").write_text("old")
        time.sleep(0.05)
        (src / "f.txt").write_text("new")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 1
        assert (cache / "f.txt").read_text() == "new"
        assert "f.txt" in stats["conflicts"]

    def test_source_wins_even_when_cache_newer(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (src / "f.txt").write_text("old-src")
        time.sleep(0.05)
        (cache / "f.txt").write_text("cache-edit")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 1
        assert (cache / "f.txt").read_text() == "old-src"
        assert "f.txt" in stats["conflicts"]

    def test_source_only_copies_to_cache(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (src / "new.txt").write_text("new file")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 1
        assert (cache / "new.txt").read_text() == "new file"

    def test_cache_only_skipped(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        # Cache-only files with quality issues are skipped (not restored)
        (cache / "cache_rescue.txt").write_text("")  # empty file → quality issue
        stats = bidir_sync(src, cache)
        assert stats["skipped"] == 1
        assert not (src / "cache_rescue.txt").exists()

    def test_skips_excluded_dirs(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (src / "__pycache__" / "mod.pyc").parent.mkdir()
        (src / "__pycache__" / "mod.pyc").write_text("bytecode")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 0
        assert not (cache / "__pycache__").exists()


class TestDriftDetection:
    """Test audit_source_cache_drift detects stale and modified cache dirs."""

    def test_no_drift_when_identical(self, tmp_path):
        packages = tmp_path / "packages"
        _make_plugin(packages, version="1.0.0")
        cache_root = tmp_path / "cache"
        _make_cache(cache_root, "test-pkg", "1.0.0", content="# myskill\n")
        with _patch_expanduser(cache_root):
            findings = audit_source_cache_drift(packages)
        assert len(findings) == 0

    def test_detects_stale_version_dir(self, tmp_path):
        packages = tmp_path / "packages"
        _make_plugin(packages, version="1.0.1")
        cache_root = tmp_path / "cache"
        _make_cache(cache_root, "test-pkg", "1.0.1")
        _make_cache(cache_root, "test-pkg", "1.0.0")  # stale
        with _patch_expanduser(cache_root):
            findings = audit_source_cache_drift(packages)
        stale = [f for f in findings if f["type"] == "stale_version_dirs"]
        assert len(stale) == 1
        assert "1.0.0" in stale[0]["stale_versions"]

    def test_detects_source_modified_drift(self, tmp_path):
        packages = tmp_path / "packages"
        pkg = _make_plugin(packages, version="1.0.0")
        (pkg / "skills" / "myskill" / "SKILL.md").write_text("# myskill\nnew content\n")
        cache_root = tmp_path / "cache"
        _make_cache(cache_root, "test-pkg", "1.0.0", content="# myskill\nold content\n")
        with _patch_expanduser(cache_root):
            findings = audit_source_cache_drift(packages)
        modified = [f for f in findings if f["type"] == "source_modified"]
        assert len(modified) == 1
        assert modified[0]["drift_count"] >= 1


class TestBumpVersion:
    """Test bump_version bumps patch in all three files."""

    def test_bumps_patch_version(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        pkg = plugins_dir / "test-pkg"
        manifest_dir = pkg / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        manifest = manifest_dir / "plugin.json"
        manifest.write_text(json.dumps({"name": "test-pkg", "version": "1.2.3"}))

        mp = tmp_path / "marketplace"
        mp.mkdir()
        (mp / "marketplace.json").write_text(json.dumps({"plugins": [{"name": "test-pkg", "version": "1.2.3"}]}))
        sub_mp = mp / ".claude-plugin" / "marketplace.json"
        sub_mp.parent.mkdir(parents=True)
        sub_mp.write_text(json.dumps({"plugins": [{"name": "test-pkg", "version": "1.2.3"}]}))

        result = bump_version(plugins_dir, str(mp), "test-pkg")
        assert result["old_version"] == "1.2.3"
        assert result["new_version"] == "1.2.4"
        assert not result["errors"]

        updated = json.loads(manifest.read_text())
        assert updated["version"] == "1.2.4"

    def test_fails_on_missing_manifest(self, tmp_path):
        result = bump_version(tmp_path / "plugins", str(tmp_path), "nonexistent")
        assert result["errors"]

    def test_fails_on_bad_version_format(self, tmp_path):
        pkg = tmp_path / "plugins" / "test-pkg"
        manifest_dir = pkg / ".claude-plugin"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "plugin.json").write_text(json.dumps({"name": "test-pkg", "version": "v1"}))
        result = bump_version(tmp_path / "plugins", str(tmp_path), "test-pkg")
        assert any("Unexpected version" in e for e in result["errors"])


class TestPackagesRootAutoFix:
    """Test that --packages-root --auto-fix handles drift sync and stale cleanup."""

    def _setup(self, tmp_path, version="1.0.1"):
        """Create packages dir with marketplace structure so auto-fix triggers."""
        packages = tmp_path / "packages"
        _make_plugin(packages, version=version)
        # Marketplace structure required for mp_root detection:
        # _detect_marketplace_root checks packages_dir / ".claude-marketplace"
        mp = packages / ".claude-marketplace"
        mp.mkdir(exist_ok=True)
        (mp / "plugins").mkdir(exist_ok=True)
        cache_root = tmp_path / "cache"
        return packages, mp, cache_root

    def test_stale_cleanup_on_packages_root(self, tmp_path):
        """Stale version dirs should be deleted when --auto-fix runs."""
        packages, mp, cache_root = self._setup(tmp_path, version="1.0.1")
        _make_cache(cache_root, "test-pkg", "1.0.1")
        stale = _make_cache(cache_root, "test-pkg", "1.0.0")

        with _patch_expanduser(cache_root):
            ret = main([
                "prog", "--packages-root", str(packages),
                "--auto-fix", "--no-fix-paths",
            ])

        assert not stale.exists()
        assert (cache_root / "test-pkg" / "1.0.1").exists()

    def test_drift_sync_on_packages_root(self, tmp_path):
        """Newer source files should be synced to cache."""
        packages, mp, cache_root = self._setup(tmp_path, version="1.0.0")
        cache_dir = _make_cache(cache_root, "test-pkg", "1.0.0", content="# myskill\nold\n")
        # Write source AFTER cache so source mtime is newer
        pkg = packages / "test-pkg"
        time.sleep(0.05)  # ensure mtime difference on fast filesystems
        (pkg / "skills" / "myskill" / "SKILL.md").write_text("# myskill\nupdated\n")

        with _patch_expanduser(cache_root):
            ret = main([
                "prog", "--packages-root", str(packages),
                "--auto-fix", "--no-fix-paths",
            ])

        cached_skill = cache_dir / "skills" / "myskill" / "SKILL.md"
        assert "updated" in cached_skill.read_text()

    def test_source_overwrites_newer_cache(self, tmp_path):
        """Source wins even when cache has newer mtime — no cache-to-source rescue."""
        packages, mp, cache_root = self._setup(tmp_path, version="1.0.0")
        pkg = packages / "test-pkg"
        # Create cache AFTER source with different content — cache is newer
        time.sleep(0.05)
        cache_dir = _make_cache(cache_root, "test-pkg", "1.0.0", content="# myskill\ncache-edit\n")

        with _patch_expanduser(cache_root):
            ret = main([
                "prog", "--packages-root", str(packages),
                "--auto-fix", "--no-fix-paths",
            ])

        # Source is canonical — must remain unchanged
        src_skill = pkg / "skills" / "myskill" / "SKILL.md"
        assert "# myskill\n" == src_skill.read_text()
        # Cache should be overwritten with source content
        cache_skill = cache_dir / "skills" / "myskill" / "SKILL.md"
        assert "# myskill\n" == cache_skill.read_text()


class TestBumpCacheManagement:
    """Test that --bump creates new cache dir and removes old one."""

    def _setup_marketplace(self, tmp_path, version="1.0.0"):
        """Create a marketplace dir with plugins subdir containing the plugin."""
        mp = tmp_path / "marketplace"
        mp.mkdir()
        # Marketplace needs plugins/ subdir
        plugins_dir = mp / "plugins"
        _make_plugin(plugins_dir, version=version)
        (mp / "marketplace.json").write_text(
            json.dumps({"plugins": [{"name": "test-pkg", "version": version}]})
        )
        sub_mp = mp / ".claude-plugin" / "marketplace.json"
        sub_mp.parent.mkdir(parents=True)
        sub_mp.write_text(
            json.dumps({"plugins": [{"name": "test-pkg", "version": version}]})
        )
        cache_root = tmp_path / "cache"
        return mp, cache_root

    def test_bump_creates_new_cache_and_removes_old(self, tmp_path):
        """After bump, new version dir exists, old one is gone."""
        mp, cache_root = self._setup_marketplace(tmp_path, version="1.0.0")
        old_cache = _make_cache(cache_root, "test-pkg", "1.0.0")

        with _patch_expanduser(cache_root):
            ret = main([
                "prog", "--marketplace-root", str(mp),
                "--bump", "test-pkg",
            ])

        assert ret == 0
        assert not old_cache.exists()
        new_cache = cache_root / "test-pkg" / "1.0.1"
        assert new_cache.exists()

    def test_bump_without_existing_cache(self, tmp_path):
        """Bump should succeed even when no cache exists yet."""
        mp, cache_root = self._setup_marketplace(tmp_path, version="2.0.0")

        with _patch_expanduser(cache_root):
            ret = main([
                "prog", "--marketplace-root", str(mp),
                "--bump", "test-pkg",
            ])

        assert ret == 0
        manifest_dir = mp / "plugins" / "test-pkg" / ".claude-plugin"
        updated = json.loads((manifest_dir / "plugin.json").read_text())
        assert updated["version"] == "2.0.1"

    def test_bump_updates_installPath_in_installed_plugins_json(self, tmp_path):
        """After bump, installPath in installed_plugins.json must point to new version dir."""
        mp, cache_root = self._setup_marketplace(tmp_path, version="1.0.0")
        _make_cache(cache_root, "test-pkg", "1.0.0")

        # Pre-populate installed_plugins.json with old installPath
        installed_path = tmp_path / "installed_plugins.json"
        installed_path.write_text(json.dumps({
            "version": 2,
            "plugins": {
                "test-pkg@local": [{
                    "scope": "user",
                    "installPath": str(cache_root / "test-pkg" / "1.0.0"),
                    "version": "1.0.0",
                    "installedAt": "2026-01-01T00:00:00.000Z",
                    "lastUpdated": "2026-01-01T00:00:00.000Z",
                    "gitCommitSha": "abc123"
                }]
            }
        }))

        with _patch_expanduser(cache_root, installed_path):
            ret = main([
                "prog", "--marketplace-root", str(mp),
                "--bump", "test-pkg",
            ])

        assert ret == 0

        # Verify installPath was updated to new version
        installed = json.loads(installed_path.read_text())
        entry = installed["plugins"]["test-pkg@local"][0]
        assert entry["version"] == "1.0.1", f"version should be 1.0.1, got {entry['version']}"
        assert str(cache_root / "test-pkg" / "1.0.1") in entry["installPath"], \
            f"installPath should point to 1.0.1, got {entry['installPath']}"



class TestAuditSkillFrontmatter:
    """Test audit_skill_frontmatter detects missing and mismatched frontmatter fields."""

    def test_detects_missing_frontmatter(self, tmp_path):
        """Skill with no YAML frontmatter should be flagged."""
        audit_skill_frontmatter = _mod.audit_skill_frontmatter
        plugins = tmp_path / "plugins"
        pkg = plugins / "test-pkg"
        skills = pkg / "skills" / "nofm"
        skills.mkdir(parents=True)
        # No frontmatter at all
        (skills / "SKILL.md").write_text("# Just a heading\n")

        findings = audit_skill_frontmatter(plugins)

        missing_fm = [f for f in findings if f["type"] == "missing_frontmatter"]
        assert len(missing_fm) == 1
        assert missing_fm[0]["skill"] == "nofm"
        assert "no YAML frontmatter" in missing_fm[0]["issue"]

    def test_detects_missing_name_field(self, tmp_path):
        """Skill with frontmatter but no 'name' field should be flagged."""
        audit_skill_frontmatter = _mod.audit_skill_frontmatter
        plugins = tmp_path / "plugins"
        pkg = plugins / "test-pkg"
        skills = pkg / "skills" / "noname"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\ndescription: A skill\n---\n# Content\n")

        findings = audit_skill_frontmatter(plugins)

        missing_name = [f for f in findings if f["type"] == "missing_name_field"]
        assert len(missing_name) == 1
        assert missing_name[0]["skill"] == "noname"
        assert "no 'name'" in missing_name[0]["issue"]

    def test_detects_missing_description_field(self, tmp_path):
        """Skill with frontmatter but no 'description' field should be flagged."""
        audit_skill_frontmatter = _mod.audit_skill_frontmatter
        plugins = tmp_path / "plugins"
        pkg = plugins / "test-pkg"
        skills = pkg / "skills" / "nodesc"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: nodesc\n---\n# Content\n")

        findings = audit_skill_frontmatter(plugins)

        missing_desc = [f for f in findings if f["type"] == "missing_description_field"]
        assert len(missing_desc) == 1
        assert missing_desc[0]["skill"] == "nodesc"
        assert "no 'description'" in missing_desc[0]["issue"]

    def test_skips_lib_directories(self, tmp_path):
        """__lib and __lib__ directories should be skipped."""
        audit_skill_frontmatter = _mod.audit_skill_frontmatter
        plugins = tmp_path / "plugins"
        pkg = plugins / "test-pkg"
        skills = pkg / "skills"
        skills.mkdir(parents=True)
        # Create __lib with no frontmatter
        (skills / "__lib" / "module.py").parent.mkdir()
        (skills / "__lib" / "module.py").write_text("# no frontmatter\n")

        findings = audit_skill_frontmatter(plugins)

        # Should not report __lib as missing frontmatter
        assert len(findings) == 0

    def test_valid_frontmatter_no_findings(self, tmp_path):
        """Skill with proper name and description should not be flagged."""
        audit_skill_frontmatter = _mod.audit_skill_frontmatter
        plugins = tmp_path / "plugins"
        pkg = plugins / "test-pkg"
        skills = pkg / "skills" / "valid"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: valid\ndescription: A valid skill\n---\n# Content\n")

        findings = audit_skill_frontmatter(plugins)

        assert len(findings) == 0


class TestAuditIntraSourceDuplication:
    """Tests for audit_intra_source_duplication — duplicate sibling lib dir detection."""

    def _make_plugins_dir(self, tmp_path: Path, plugin_name: str = "myplugin"):
        """Return (plugins_dir, plugin_dir)."""
        plugins = tmp_path / "plugins"
        plugin = plugins / plugin_name
        plugin.mkdir(parents=True)
        return plugins, plugin

    # (a) Identical content -> flagged, diverged: False
    def test_duplication_identical_flagged_not_diverged(self, tmp_path):
        """__lib/ and __lib__/ with identical m.py -> finding with diverged=False."""
        audit = _mod.audit_intra_source_duplication
        plugins, plugin = self._make_plugins_dir(tmp_path)

        lib1 = plugin / "__lib"
        lib2 = plugin / "__lib__"
        lib1.mkdir()
        lib2.mkdir()
        content = "def foo(): pass\n"
        (lib1 / "m.py").write_text(content)
        (lib2 / "m.py").write_text(content)

        findings = audit(plugins)

        dup = [f for f in findings if f["type"] == "intra_source_duplication"]
        assert len(dup) == 1, f"Expected 1 finding, got: {dup}"
        f = dup[0]
        assert f["plugin"] == "myplugin"
        assert f["overlap_count"] == 1
        assert f["diverged"] is False
        assert "diverged_paths" not in f

    # (b) Divergent content -> flagged, diverged: True, lists m.py
    def test_duplication_divergent_flagged_with_paths(self, tmp_path):
        """__lib/ and __lib__/ with different m.py -> finding with diverged=True, diverged_paths=[m.py]."""
        audit = _mod.audit_intra_source_duplication
        plugins, plugin = self._make_plugins_dir(tmp_path)

        lib1 = plugin / "__lib"
        lib2 = plugin / "__lib__"
        lib1.mkdir()
        lib2.mkdir()
        (lib1 / "m.py").write_text("def foo(): return 1\n")
        (lib2 / "m.py").write_text("def foo(): return 2\n")  # diverged!

        findings = audit(plugins)

        dup = [f for f in findings if f["type"] == "intra_source_duplication"]
        assert len(dup) == 1
        f = dup[0]
        assert f["diverged"] is True
        assert "m.py" in f["diverged_paths"]

    # (c) Only __lib/ present -> NOT flagged
    def test_only_one_lib_dir_not_flagged(self, tmp_path):
        """Plugin with only __lib/ (no sibling) -> no findings."""
        audit = _mod.audit_intra_source_duplication
        plugins, plugin = self._make_plugins_dir(tmp_path)

        lib1 = plugin / "__lib"
        lib1.mkdir()
        (lib1 / "m.py").write_text("def foo(): pass\n")

        findings = audit(plugins)

        dup = [f for f in findings if f["type"] == "intra_source_duplication"]
        assert len(dup) == 0

    # (d) Junction/realpath dedup
    def test_realpath_dedup_skips_already_visited(self, tmp_path):
        """The visited_realpaths set prevents scanning the same physical dir twice.

        We cannot create real NTFS junctions in a tmp_path without admin rights.
        Instead, we verify the dedup logic directly: two plugin entries whose
        os.path.realpath resolves to the same path should yield findings from
        only ONE scan, not two.  We do this by creating a single physical plugin
        dir and symlinking it as a second entry (symlinks work without elevation).
        If symlink creation fails (Windows policy), we skip rather than assert a
        fabricated pass.
        """
        audit = _mod.audit_intra_source_duplication
        plugins = tmp_path / "plugins"
        plugins.mkdir()

        # Create physical plugin with dup lib dirs
        physical = plugins / "real-plugin"
        physical.mkdir()
        lib1 = physical / "__lib"
        lib2 = physical / "__lib__"
        lib1.mkdir()
        lib2.mkdir()
        (lib1 / "m.py").write_text("def foo(): pass\n")
        (lib2 / "m.py").write_text("def foo(): pass\n")

        symlink = plugins / "sym-plugin"
        try:
            os.symlink(str(physical), str(symlink))
        except (OSError, NotImplementedError):
            # Symlinks require elevated permissions or Developer Mode on Windows.
            # Skip rather than fabricate an assertion.
            pytest.skip("Symlink creation not available; dedup logic covered by code inspection")

        findings = audit(plugins)

        dup = [f for f in findings if f["type"] == "intra_source_duplication"]
        # Without dedup: 2 findings (one for real-plugin, one for sym-plugin).
        # With dedup: 1 finding — realpath of sym-plugin matches real-plugin, skipped.
        assert len(dup) == 1, (
            f"Expected 1 finding (dedup prevented double-scan), got {len(dup)}: {dup}"
        )


class TestAuditSettingsHooks:
    """Tests for settings.json hook-command validation."""

    def test_detects_missing_router_entrypoint_before_event_argument(self, tmp_path):
        """A settings hook like 'python .../router.py Stop' should validate router.py, not Stop."""
        audit_settings_hooks = _mod.audit_settings_hooks

        settings_path = tmp_path / "settings.json"
        router_path = tmp_path / "plugins" / "cc-model-router" / "__lib" / "router.py"
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "matcher": ".*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": f'python "{router_path}" Stop',
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )

        findings = audit_settings_hooks(settings_path)

        assert len(findings) == 1
        assert findings[0]["file"] == "settings.json"
        assert "router.py" in findings[0]["error"]

    def test_main_packages_root_flags_missing_settings_router(self, tmp_path):
        """The installer audit should fail when live settings.json points at a missing router."""
        packages = tmp_path / "packages"
        pkg = _make_plugin(packages, name="cc-model-router", version="0.1.1")
        (pkg / "hooks").mkdir()
        (pkg / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {}}))
        marketplace = packages / ".claude-marketplace"
        (marketplace / "plugins").mkdir(parents=True)
        (marketplace / "marketplace.json").write_text(json.dumps({"plugins": []}))
        (marketplace / ".claude-plugin").mkdir(parents=True)
        (marketplace / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"plugins": []}))

        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "matcher": ".*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": f'python "{packages / "cc-model-router" / "__lib" / "router.py"}" Stop',
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )

        with _patch_expanduser(tmp_path / "cache", settings_path=settings_path):
            exit_code = main(["prog", "--packages-root", str(packages)])

        assert exit_code == 1
