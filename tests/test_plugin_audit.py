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


def _patch_expanduser(cache_root: Path):
    """Patch os.path.expanduser to redirect ~/.claude/plugins/cache/local to cache_root."""
    original = os.path.expanduser

    def _expanduser(path: str) -> str:
        if path == "~/.claude/plugins/cache/local":
            return str(cache_root)
        return original(path)

    # Patch in the module under test AND in os.path globally (module caches os.path)
    return patch.object(os.path, "expanduser", side_effect=_expanduser)


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
        assert stats["cache_to_src"] == 0

    def test_newer_source_syncs_to_cache(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "f.txt").write_text("old")
        time.sleep(0.05)
        (src / "f.txt").write_text("new")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 1
        assert stats["cache_to_src"] == 0
        assert (cache / "f.txt").read_text() == "new"

    def test_newer_cache_syncs_to_source(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (src / "f.txt").write_text("old")
        time.sleep(0.05)
        (cache / "f.txt").write_text("cache-edit")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 0
        assert stats["cache_to_src"] == 1
        assert (src / "f.txt").read_text() == "cache-edit"

    def test_source_only_copies_to_cache(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (src / "new.txt").write_text("new file")
        stats = bidir_sync(src, cache)
        assert stats["src_to_cache"] == 1
        assert (cache / "new.txt").read_text() == "new file"

    def test_cache_only_copies_to_source(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        (cache / "rescue.txt").write_text("cache-only work")
        stats = bidir_sync(src, cache)
        assert stats["cache_to_src"] == 1
        assert (src / "rescue.txt").read_text() == "cache-only work"

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

    def test_cache_to_source_rescue(self, tmp_path):
        """Cache edits (newer mtime) should be synced back to source."""
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

        src_skill = pkg / "skills" / "myskill" / "SKILL.md"
        assert "cache-edit" in src_skill.read_text()


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
