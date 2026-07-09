"""Live tests for bidir_sync direction modes (release vs recovery vs dry-run).

Uses real temp directories — no mocks — so the source-mutation prohibition is
proven at the filesystem level, not via a patched stub.
"""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "plugin-audit-and-fix.py"
_spec = importlib.util.spec_from_file_location("plugin_audit_direction", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

bidir_sync = _mod.bidir_sync


def _tree(root: Path) -> dict[str, bytes]:
    out = {}
    for f in root.rglob("*"):
        if f.is_file():
            out[str(f.relative_to(root)).replace("\\", "/")] = f.read_bytes()
    return out


def test_release_bump_cache_only_file_not_created_in_source(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cache = tmp_path / "cache"; cache.mkdir()
    (src / "plugin.json").write_text('{"name":"x"}')
    (cache / "plugin.json").write_text('{"name":"x"}')  # identical
    (cache / "cache_only.txt").write_text("only in cache")  # would mutate source in legacy bidir
    s = bidir_sync(src, cache, direction="source_to_cache_only")
    assert not (src / "cache_only.txt").exists(), "FAIL: cache-only file leaked into source on release bump"
    assert s["cache_to_src"] == 0
    assert s["source_mutated"] is False
    assert s["direction"] == "source_to_cache_only"


def test_release_bump_divergent_cache_receives_source_source_unchanged(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cache = tmp_path / "cache"; cache.mkdir()
    (src / "f.py").write_text("SOURCE\n")
    (cache / "f.py").write_text("CACHE\n")
    before = (src / "f.py").read_bytes()
    s = bidir_sync(src, cache, direction="source_to_cache_only")
    assert (cache / "f.py").read_text() == "SOURCE\n", "FAIL: cache did not receive source content"
    assert (src / "f.py").read_bytes() == before, "FAIL: source was mutated on divergent file"
    assert s["src_to_cache"] == 1
    assert s["source_mutated"] is False


def test_explicit_recovery_copies_cache_to_source_no_version_bump(tmp_path):
    # Recovery is a pure sync primitive test here; the CLI handler adds the
    # "no version bump" guarantee (it never calls bump_version). Verify the
    # primitive copies cache->source and flags source_mutated.
    src = tmp_path / "src"; src.mkdir()
    cache = tmp_path / "cache"; cache.mkdir()
    (src / "plugin.json").write_text('{"name":"x","version":"1.0.0"}')
    (cache / "plugin.json").write_text('{"name":"x","version":"1.0.0"}')
    (cache / "recovered.py").write_text("print('from cache')\n")  # absent from source
    s = bidir_sync(src, cache, direction="cache_to_source_only")
    assert (src / "recovered.py").exists(), "FAIL: recovery did not copy cache->source"
    assert (src / "recovered.py").read_text() == "print('from cache')\n"
    assert s["cache_to_src"] >= 1
    assert s["source_mutated"] is True
    # version file untouched by the primitive (CLI handler guarantees no bump_version call)
    assert (src / "plugin.json").read_text() == '{"name":"x","version":"1.0.0"}'


def test_recovery_cache_wins_divergent(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cache = tmp_path / "cache"; cache.mkdir()
    (src / "d.py").write_text("SRC\n")
    (cache / "d.py").write_text("CACHE\n")
    s = bidir_sync(src, cache, direction="cache_to_source_only")
    assert (src / "d.py").read_text() == "CACHE\n", "FAIL: cache did not win divergent in recovery"
    assert s["source_mutated"] is True


def test_dry_run_writes_nothing_and_classifies(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    cache = tmp_path / "cache"; cache.mkdir()
    (src / "only_src.txt").write_text("s")
    (cache / "only_cache.txt").write_text("c")
    (src / "same.txt").write_text("same"); (cache / "same.txt").write_text("same")
    (src / "diff.txt").write_text("a"); (cache / "diff.txt").write_text("b")
    src_before = _tree(src); cache_before = _tree(cache)
    s = bidir_sync(src, cache, direction="dry_run")
    assert _tree(src) == src_before, "FAIL: dry-run wrote to source"
    assert _tree(cache) == cache_before, "FAIL: dry-run wrote to cache"
    assert set(s["source_only"]) == {"only_src.txt"}
    assert set(s["cache_only"]) == {"only_cache.txt"}
    assert set(s["divergent"]) == {"diff.txt"}
    assert s["identical"] == 1
    assert s["src_to_cache"] == 0 and s["cache_to_src"] == 0


def test_bidirectional_legacy_preserved(tmp_path):
    """Regression: default direction must match legacy behavior (src wins divergent,
    cache-only copied to source when quality passes)."""
    src = tmp_path / "src"; src.mkdir()
    cache = tmp_path / "cache"; cache.mkdir()
    (src / "d.py").write_text("SRC\n")
    (cache / "d.py").write_text("CACHE\n")
    (cache / "extra.py").write_text("x = 1\n")
    s = bidir_sync(src, cache)  # default bidirectional
    assert (cache / "d.py").read_text() == "SRC\n", "legacy: source wins divergent"
    assert (src / "extra.py").exists(), "legacy: cache-only copied to source (quality-gated)"
    assert s["source_mutated"] is True
