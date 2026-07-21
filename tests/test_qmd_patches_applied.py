"""Verify QMD semantic-search patches are present in the installed qmd package.

Each test asserts that a specific marker substring is present in the source
of a patched function. Fast (<1s). Run with::

    pytest tests/test_qmd_patches_applied.py -v

If a marker is missing, the corresponding `.patch` file at::

    P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/

needs to be re-applied. See the wiki CLAUDE.md "Wiki Search Contract" section
for the reinstall protocol.

Source: /design run 10d616f8 (2026-07-20).
See P:/.data/wiki/concepts/qmd-patch-durability-strategy.md.
"""
import importlib
import inspect

import pytest


PATCHES = [
    {
        "id": "qmd_cli_main.patch (patch 1: cmd_search passes llm_backend)",
        "module": "qmd.cli.main",
        "function": "cmd_search",
        "must_appear": ["llm_backend", "create_llm_backend"],
        "extra_dep": None,
    },
    {
        "id": "qmd_llm_sentence_tf.patch (patch 2: default model = all-mpnet-base-v2)",
        "module": "qmd.llm.sentence_tf",
        "function": "SentenceTransformerBackend.__init__",
        "must_appear": ["all-mpnet-base-v2"],
        "extra_dep": "sentence_transformers",
    },
    {
        "id": "qmd_fts5_patch.patch (existing: FTS5 operator escaping)",
        "module": "qmd.core.retrieval",
        "function": "build_fts5_query",
        "must_appear": ["re.sub"],
        "extra_dep": None,
    },
]


@pytest.mark.parametrize("patch", PATCHES, ids=[p["id"] for p in PATCHES])
def test_patch_present(patch):
    """Each patch's marker substrings must be present in the patched function's source."""
    try:
        mod = importlib.import_module(patch["module"])
    except ImportError as e:
        if patch["extra_dep"] and patch["extra_dep"].replace("-", "_") in str(e).replace("-", "_"):
            pytest.skip(
                f"optional dependency not installed: {patch['extra_dep']} "
                f"(needed to import {patch['module']})"
            )
        raise

    # Walk to the function (supports "Class.method" via split on ".")
    obj = mod
    for part in patch["function"].split("."):
        obj = getattr(obj, part)

    try:
        src = inspect.getsource(obj)
    except (TypeError, OSError) as e:
        pytest.fail(
            f"could not get source for {patch['module']}.{patch['function']}: {e}. "
            f"This usually means qmd is installed as bytecode-only; reinstall with source."
        )

    missing = [s for s in patch["must_appear"] if s not in src]
    assert not missing, (
        f"Patch marker(s) missing from {patch['module']}.{patch['function']}: {missing}. "
        f"Re-apply the .patch file from "
        f"P:/packages/.claude-marketplace/plugins/cc-skills-utils/__lib/ "
        f"and re-run pytest tests/test_qmd_patches_applied.py. "
        f"See wiki CLAUDE.md 'Wiki Search Contract' for the reinstall protocol."
    )
