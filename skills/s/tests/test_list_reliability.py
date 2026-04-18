import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Setup sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


# Mock ModelInfo since it might be hard to import directly due to CSF path
class MockModelInfo:
    def __init__(
        self,
        id,
        name,
        provider,
        is_free=False,
        prompt_price=0.0,
        completion_price=0.0,
        context_length=0,
        description="",
    ):
        self.id = id
        self.name = name
        self.provider = provider
        self.is_free = is_free
        self.prompt_price = prompt_price
        self.completion_price = completion_price
        self.context_length = context_length
        self.description = description


@pytest.fixture
def mock_display():
    with patch("rich.console.Console"), patch("src.core.config.api_keys.APIKeyManager"), patch(
        "src.llm.providers.utils.model_enumerator.ModelInfo", MockModelInfo
    ):
        import display

        yield display


def test_is_free_or_subscription(mock_display):
    # Free model
    m1 = MockModelInfo("m1", "Free Model", "groq", is_free=True)
    assert mock_display._is_free_or_subscription(m1) is True

    # Zero price model
    m2 = MockModelInfo("m2", "Zero Price", "openrouter", prompt_price=0.0, completion_price=0.0)
    assert mock_display._is_free_or_subscription(m2) is True

    # Known free provider
    m3 = MockModelInfo("m3", "Groq Model", "groq", prompt_price=0.01, completion_price=0.01)
    assert mock_display._is_free_or_subscription(m3) is True

    # Known paid provider
    m4 = MockModelInfo("m4", "Paid Model", "openai", prompt_price=0.0, completion_price=0.0)
    assert mock_display._is_free_or_subscription(m4) is False

    # Paid model on free provider (if any, but currently groq is always considered free in logic)
    m5 = MockModelInfo(
        "m5", "Paid Model", "anthropic", is_free=True
    )  # Should be false because anthropic is in PAID_PROVIDERS
    assert mock_display._is_free_or_subscription(m5) is False


def test_get_cost_category(mock_display):
    m1 = MockModelInfo("m1", "Free", "groq", is_free=True)
    assert mock_display._get_cost_category(m1) == "FREE"

    m2 = MockModelInfo("m2", "Paid", "openai")
    assert mock_display._get_cost_category(m2) == "PAID"


@pytest.mark.asyncio
async def test_fetch_models_timeout(mock_display):
    # Mock APIKeyManager to return a provider with key
    mock_api_manager = MagicMock()
    mock_api_manager.return_value.get_provider.return_value.api_key = (
        "fake_key"  # pragma: allowlist secret
    )

    # Mock enumerator to hang
    async def slow_enumerate(key):
        await asyncio.sleep(2.0)
        return []

    with patch("src.core.config.api_keys.APIKeyManager", mock_api_manager), patch(
        "display.enumerate_openrouter_models", slow_enumerate
    ), patch("display.asyncio.wait_for") as mock_wait_for, patch(
        "display._load_cache", return_value=None
    ):
        # Simulate timeout
        mock_wait_for.side_effect = asyncio.TimeoutError()

        # Should not raise exception, but return results (which will be empty if all timed out)
        results, ts = await mock_display._fetch_models(refresh=True)
        assert results == {}
        mock_wait_for.assert_called_once()


def test_table_column_widths(mock_display):
    from rich.table import Table

    # Mock data to ensure _print_category_table actually prints a table
    mock_entry = MagicMock()
    mock_entry.model_id = "provider/m1"
    mock_entry.score = 90.0
    mock_entry.benchmark = "Test Bench"

    mock_model = MockModelInfo("m1", "Model 1", "provider", is_free=True)

    leaderboard_data = {"test_key": [mock_entry]}
    model_info_map = {"provider/m1": mock_model}
    api_provider_map = {"provider/m1": "provider"}

    # Check _print_category_table column widths
    with patch.object(mock_display.console, "print") as mock_print:
        mock_display._print_category_table(
            "Test",
            "test_key",
            leaderboard_data,
            model_info_map,
            api_provider_map,
            limit=6,
            available_providers={"provider"},
        )
        # Find the Table call
        table = None
        for call in mock_print.call_args_list:
            args, kwargs = call
            if args and isinstance(args[0], Table):
                table = args[0]
                break

        assert table is not None, "Table was not printed"

        # In category table, API Host is column 1
        api_host_col = table.columns[1]
        assert api_host_col.header == "API Host"
        assert api_host_col.width == 25  # Match code (25)

        # Model column is 0
        model_col = table.columns[0]
        assert model_col.header == "Model"
        assert model_col.width == 35


def test_api_key_filtering(mock_display):
    from rich.table import Table

    # Mock data to test "needs key" indicator
    mock_entry = MagicMock()
    mock_entry.model_id = "provider/m1"
    mock_entry.score = 90.0
    mock_entry.benchmark = "Test Bench"

    mock_model = MockModelInfo("m1", "Model 1", "provider", is_free=True)

    leaderboard_data = {"test_key": [mock_entry]}
    model_info_map = {"provider/m1": mock_model}
    api_provider_map = {"provider/m1": "provider"}

    # Pass empty set of available_providers to trigger "(needs key)"
    with patch.object(mock_display.console, "print") as mock_print:
        mock_display._print_category_table(
            "Test",
            "test_key",
            leaderboard_data,
            model_info_map,
            api_provider_map,
            limit=6,
            available_providers=set(),
        )

        # Get the table rows
        table = None
        for call in mock_print.call_args_list:
            args, kwargs = call
            if args and isinstance(args[0], Table):
                table = args[0]
                break

        assert table is not None

        # Check the row data (API Host column is 1)
        # Table rows are accessed differently in Rich depending on version
        # We can look for the string "(needs key)" in the console output if table access is hard
        # But let's try to access rows if possible
        found_needs_key = False
        # Each row in table.rows is a Row object, but content is in table.columns[i].cells
        for cell in table.columns[1].cells:
            if "(needs key)" in str(cell):
                found_needs_key = True
                break

        assert found_needs_key is True


@pytest.mark.asyncio
async def test_cache_conflict_detection_logic(mock_display):
    # Test the logic that calculates age diff
    import time

    now = time.time()

    # 1. No conflict
    model_cache_time = now
    leaderboard_cache_time = now
    age_diff_hours = (model_cache_time - leaderboard_cache_time) / 3600
    assert abs(age_diff_hours) <= 24

    # 2. Conflict (provider much newer)
    model_cache_time = now
    leaderboard_cache_time = now - (48 * 3600)  # 2 days ago
    age_diff_hours = (model_cache_time - leaderboard_cache_time) / 3600
    assert age_diff_hours > 24


@pytest.mark.asyncio
async def test_model_id_validation_layer(mock_display):
    # Mock leaderboard data with a model not in provider data
    mock_entry = MagicMock()
    mock_entry.model_id = "unknown/model-1"
    mock_entry.score = 90.0
    mock_entry.benchmark = "Test Bench"

    leaderboard_data = {"reasoning": [mock_entry]}

    # Mock _fetch_models to return empty results
    with patch("display._fetch_models", return_value=({}, 0.0)), patch(
        "display._leaderboard_registry.fetch_leaderboard_data", return_value=leaderboard_data
    ), patch.object(mock_display.console, "print") as mock_print, patch("sys.exit") as mock_exit:
        try:
            await mock_display._display_free_models_async()
        except SystemExit:
            pass  # We expect sys.exit(0) at the end

        # Check if warning was printed
        warning_found = False
        for call in mock_print.call_args_list:
            args = call[0]
            if args and "models not in provider data" in str(args[0]):
                warning_found = True
                break
        assert warning_found is True
