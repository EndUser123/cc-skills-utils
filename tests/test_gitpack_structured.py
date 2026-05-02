"""Tests for gitpack_structured — appendix code fence fix."""

import sys
from pathlib import Path

import pytest

# Add scripts dir to path for import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "gitpack" / "scripts"))
from gitpack_structured import _build_appendix, _lang_for


class TestLangFor:
    def test_python(self) -> None:
        assert _lang_for("foo.py") == "python"

    def test_typescript(self) -> None:
        assert _lang_for("foo.ts") == "typescript"

    def test_unknown_defaults_to_text(self) -> None:
        assert _lang_for("foo.rs") == "text"

    def test_case_insensitive(self) -> None:
        assert _lang_for("foo.PY") == "python"


class TestBuildAppendix:
    def test_appendix_wraps_code_in_fences(self, tmp_path: Path) -> None:
        src = tmp_path / "example.py"
        src.write_text("def hello():\n    pass\n")
        files = [str(src)]
        result = _build_appendix(files, {})
        joined = "\n".join(result)

        assert "### " in joined
        assert "```python" in joined
        assert "def hello():" in joined
        assert joined.count("```") >= 2  # open and close fence

    def test_appendix_fences_for_missing_file(self) -> None:
        files = ["/nonexistent/path.py"]
        result = _build_appendix(files, {})
        joined = "\n".join(result)

        assert "```python" in joined
        assert "```" in result  # close fence present
        assert "(not found)" in joined

    def test_appendix_uses_correct_lang_label(self, tmp_path: Path) -> None:
        src = tmp_path / "styles.css"
        src.write_text("body { margin: 0; }\n")
        files = [str(src)]
        result = _build_appendix(files, {})

        assert "```css" in result

    def test_appendix_multiple_files_all_fenced(self, tmp_path: Path) -> None:
        py_file = tmp_path / "a.py"
        ts_file = tmp_path / "b.ts"
        py_file.write_text("x = 1\n")
        ts_file.write_text("const y = 2;\n")
        files = [str(py_file), str(ts_file)]
        result = _build_appendix(files, {})

        assert result.count("```python") == 1
        assert result.count("```typescript") == 1
        # Each file gets open + close fence = 4 total backtick lines
        fence_lines = [l for l in result if l.startswith("```")]
        assert len(fence_lines) == 4
