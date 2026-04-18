"""Unit tests for ProgressReporter class.

Tests cover:
- phase_start(), persona_complete(), phase_complete() methods
- reset() method for state clearing between runs
- Elapsed time display
- --quiet flag behavior (verbose=False)
"""

# Import the module under test (will fail until we create it)
import sys
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts directory to path for imports
scripts_dir = Path(__file__).parent.parent / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from progress_reporter import ProgressReporter  # noqa: E402


class TestProgressReporterInit:
    """Tests for ProgressReporter initialization."""

    def test_default_initialization(self) -> None:
        """ProgressReporter initializes with default values."""
        reporter = ProgressReporter()
        assert reporter.verbose is True
        assert reporter.current_phase == "init"
        assert len(reporter.personas_complete) == 0
        assert reporter.start_time is None

    def test_verbose_false_initialization(self) -> None:
        """ProgressReporter can be initialized with verbose=False."""
        reporter = ProgressReporter(verbose=False)
        assert reporter.verbose is False

    def test_custom_output_stream(self) -> None:
        """ProgressReporter accepts custom output stream."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        assert reporter.output is output


class TestProgressReporterReset:
    """Tests for reset() method."""

    def test_reset_clears_phase(self) -> None:
        """reset() clears current_phase to 'init'."""
        reporter = ProgressReporter()
        reporter.current_phase = "diverge"
        reporter.reset()
        assert reporter.current_phase == "init"

    def test_reset_clears_personas(self) -> None:
        """reset() clears personas_complete set."""
        reporter = ProgressReporter()
        reporter.personas_complete.add("innovator")
        reporter.personas_complete.add("critic")
        reporter.reset()
        assert len(reporter.personas_complete) == 0

    def test_reset_sets_start_time(self) -> None:
        """reset() sets start_time to current time."""
        reporter = ProgressReporter()
        assert reporter.start_time is None
        reporter.reset()
        assert reporter.start_time is not None
        # Verify start_time is recent (within 1 second)
        now = datetime.now()
        assert abs((now - reporter.start_time).total_seconds()) < 1

    def test_reset_allows_reuse(self) -> None:
        """reset() allows reporter to be reused for new session."""
        output = StringIO()
        reporter = ProgressReporter(output=output)

        # First session
        reporter.reset()
        reporter.phase_start("diverge")
        reporter.persona_complete("innovator", 5)

        # Reset for second session
        reporter.reset()
        assert reporter.current_phase == "init"
        assert len(reporter.personas_complete) == 0


class TestPhaseStart:
    """Tests for phase_start() method."""

    def test_phase_start_outputs_phase_name(self) -> None:
        """phase_start() outputs phase name to output stream."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.phase_start("diverge")
        output_text = output.getvalue()

        assert "DIVERGE" in output_text
        assert "▶" in output_text

    def test_phase_start_shows_item_count(self) -> None:
        """phase_start() shows item count when total_items > 0."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.phase_start("diverge", total_items=5)
        output_text = output.getvalue()

        assert "5 items" in output_text

    def test_phase_start_quiet_mode_no_output(self) -> None:
        """phase_start() produces no output when verbose=False."""
        output = StringIO()
        reporter = ProgressReporter(verbose=False, output=output)
        reporter.reset()

        reporter.phase_start("diverge")
        output_text = output.getvalue()

        assert output_text == ""

    def test_phase_start_shows_elapsed_time(self) -> None:
        """phase_start() shows elapsed time since reset()."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.phase_start("diverge")
        output_text = output.getvalue()

        # Should contain elapsed time in [MM:SS] format
        assert "[00:00]" in output_text


class TestPersonaComplete:
    """Tests for persona_complete() method."""

    def test_persona_complete_outputs_persona_name(self) -> None:
        """persona_complete() outputs persona name and idea count."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.persona_complete("innovator", 7)
        output_text = output.getvalue()

        assert "innovator" in output_text
        assert "7 ideas" in output_text
        assert "✓" in output_text

    def test_persona_complete_tracks_completed_personas(self) -> None:
        """persona_complete() adds persona to personas_complete set."""
        reporter = ProgressReporter()
        reporter.reset()

        reporter.persona_complete("innovator", 5)
        assert "innovator" in reporter.personas_complete

        reporter.persona_complete("critic", 3)
        assert "critic" in reporter.personas_complete
        assert len(reporter.personas_complete) == 2

    def test_persona_complete_quiet_mode_no_output(self) -> None:
        """persona_complete() produces no output when verbose=False."""
        output = StringIO()
        reporter = ProgressReporter(verbose=False, output=output)
        reporter.reset()

        reporter.persona_complete("innovator", 5)
        output_text = output.getvalue()

        assert output_text == ""

    def test_persona_complete_shows_elapsed_time(self) -> None:
        """persona_complete() shows elapsed time since reset()."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.persona_complete("innovator", 5)
        output_text = output.getvalue()

        # Should contain elapsed time in [MM:SS] format
        assert "[00:00]" in output_text


class TestPhaseComplete:
    """Tests for phase_complete() method."""

    def test_phase_complete_outputs_result_count(self) -> None:
        """phase_complete() outputs result count."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.phase_complete("diverge", result_count=15)
        output_text = output.getvalue()

        assert "15 results" in output_text
        assert "✓" in output_text

    def test_phase_complete_quiet_mode_no_output(self) -> None:
        """phase_complete() produces no output when verbose=False."""
        output = StringIO()
        reporter = ProgressReporter(verbose=False, output=output)
        reporter.reset()

        reporter.phase_complete("diverge", result_count=10)
        output_text = output.getvalue()

        assert output_text == ""

    def test_phase_complete_shows_elapsed_time(self) -> None:
        """phase_complete() shows elapsed time since reset()."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.phase_complete("diverge", result_count=10)
        output_text = output.getvalue()

        # Should contain elapsed time in [MM:SS] format
        assert "[00:00]" in output_text


class TestElapsedTime:
    """Tests for elapsed time display."""

    def test_elapsed_time_increases(self) -> None:
        """Elapsed time increases as time passes."""
        output = StringIO()
        reporter = ProgressReporter(output=output)
        reporter.reset()

        reporter.phase_start("diverge")

        # Simulate time passing (mock datetime)
        with patch("progress_reporter.datetime") as mock_dt:
            # Set now() to 2 minutes after start_time
            mock_dt.now.return_value = reporter.start_time + timedelta(minutes=2)
            reporter.phase_complete("diverge", result_count=10)

        second_output = output.getvalue()

        # Second output should show [02:00] instead of [00:00]
        assert "[02:00]" in second_output

    def test_elapsed_time_zero_before_reset(self) -> None:
        """Elapsed time shows 00:00 before reset() is called."""
        output = StringIO()
        reporter = ProgressReporter(output=output)

        # Don't call reset(), start_time is None
        reporter.phase_start("diverge")
        output_text = output.getvalue()

        # Should still show [00:00] as fallback
        assert "[00:00]" in output_text


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow_output(self) -> None:
        """Test complete workflow produces expected output."""
        output = StringIO()
        reporter = ProgressReporter(output=output)

        # Reset for new session
        reporter.reset()

        # Phase 1: Diverge
        reporter.phase_start("diverge", total_items=5)
        reporter.persona_complete("innovator", 8)
        reporter.persona_complete("critic", 5)
        reporter.phase_complete("diverge", result_count=13)

        # Phase 2: Converge
        reporter.phase_start("converge")
        reporter.phase_complete("converge", result_count=3)

        output_text = output.getvalue()

        # Verify all phases and personas appear
        assert "DIVERGE" in output_text
        assert "CONVERGE" in output_text
        assert "innovator" in output_text
        assert "critic" in output_text
        assert "5 items" in output_text
        assert "8 ideas" in output_text
        assert "5 ideas" in output_text
        assert "13 results" in output_text
        assert "3 results" in output_text

    def test_stderr_output_by_default(self) -> None:
        """By default, output goes to stderr."""
        import sys

        reporter = ProgressReporter()
        assert reporter.output is sys.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
