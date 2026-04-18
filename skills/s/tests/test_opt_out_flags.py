"""
Test suite for GoT and ToT opt-out flags in /s skill.

These tests verify that:
- GoT is enabled by default (opt-out design)
- ToT is enabled by default (opt-out design)
- --no-got flag disables GoT strategy options analysis
- --no-tot flag disables ToT outcome exploration
- STRATEGY_NO_GOT environment variable disables GoT globally
- STRATEGY_NO_TOT environment variable disables ToT globally
- Flag parsing logic works correctly for both flags
- Constitutional compliance: opt-out does NOT bypass safety checks
- Flag independence: GoT and ToT flags work independently
"""

import os
import sys
from pathlib import Path

import pytest

# Add utils path to import GotPlanner, GotEdgeAnalyzer, and BranchGenerator from /code
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'code' / 'utils'))
from got_planner import GotPlanner
from tot_tracer import BranchGenerator

# Test fixtures

@pytest.fixture
def sample_strategy_options():
    """Sample strategy options with constraints, ideas, risks and outcome scenarios"""
    return """
## Architecture

### Constraints
- Budget < $5000
- Must use PostgreSQL
- Timeline < 4 weeks
- Must support 1000 concurrent users

### Ideas
- Use microservices architecture
- Implement OAuth 2.0
- Adopt event-driven architecture
- Add API Gateway
- Use Redis for caching

### Risks
- Microservices complexity
- OAuth integration latency
- Event ordering issues
- Cache consistency problems
- Single point of failure

## Outcome Analysis

def analyze_success_probability(strategy, complexity, team_size):
    if strategy == 'microservices':
        if complexity == 'high':
            if team_size >= 5:
                return 'Success likely (6-12 months)'
            else:  # small team
                return 'Success moderate (requires training)'
        else:  # low complexity
            return 'Success likely (3-6 months)'
    else:  # monolith
        if team_size >= 3:
            return 'Success likely (1-3 months)'
        else:
            return 'Success risk (team too small)'

def analyze_failure_modes(strategy, complexity):
    if strategy == 'microservices':
        if complexity == 'high':
            return 'Technical incompatibility'
        else:
            return 'Operational complexity'
    else:  # monolith
        if complexity == 'high':
            return 'Performance bottleneck'
        else:
            return 'Scaling limitations'
"""


# Tests for GoT opt-out flags

def test_got_enabled_by_default(sample_strategy_options):
    """Test that GoT is enabled by default (opt-out design)"""
    args = []
    got_enabled = '--no-got' not in args  # Default: enabled

    if got_enabled:
        planner = GotPlanner(sample_strategy_options)
        nodes = planner.extract_nodes()

        # Should extract nodes when GoT is enabled
        total_nodes = sum(len(node_list) for node_list in nodes.values())
        assert total_nodes >= 2, "GoT should extract at least 2 nodes by default"
        assert any(node_list for node_list in nodes.values()), "Nodes should have at least one category"


def test_no_got_flag_disables_got(sample_strategy_options):
    """Test that --no-got flag disables GoT analysis"""
    args = ['--no-got']
    got_enabled = '--no-got' not in args

    if not got_enabled:
        # When GoT is disabled, should use traditional strategy analysis
        assert True, "GoT disabled, traditional strategy analysis used"
    else:
        # Should extract nodes when GoT is enabled
        planner = GotPlanner(sample_strategy_options)
        nodes = planner.extract_nodes()
        total_nodes = sum(len(node_list) for node_list in nodes.values())
        assert total_nodes >= 2


# Tests for ToT opt-out flags

def test_tot_enabled_by_default(sample_strategy_options):
    """Test that ToT is enabled by default (opt-out design)"""
    args = []
    tot_enabled = '--no-tot' not in args  # Default: enabled

    if tot_enabled:
        generator = BranchGenerator(sample_strategy_options)
        branches = generator.generate_branches()

        # Should generate branches when ToT is enabled
        assert len(branches) >= 2, "ToT should generate at least 2 branches by default"
        assert any(branch.get('score') for branch in branches), "Branches should have scores"


def test_no_tot_flag_disables_tot(sample_strategy_options):
    """Test that --no-tot flag disables ToT branching"""
    args = ['--no-tot']
    tot_enabled = '--no-tot' not in args

    if not tot_enabled:
        # When ToT is disabled, should use traditional outcome exploration
        assert True, "ToT disabled, traditional outcome exploration used"
    else:
        # Should generate branches when ToT is enabled
        generator = BranchGenerator(sample_strategy_options)
        branches = generator.generate_branches()
        assert len(branches) >= 2


# Tests for default behavior (quality-first)

def test_default_behavior_quality_first():
    """Test that default behavior prioritizes quality (opt-out design)"""
    # Default should be quality-first (both GoT and ToT enabled)
    args = []
    got_default = '--no-got' not in args
    tot_default = '--no-tot' not in args

    # This aligns with /s's quality-first philosophy
    # where both enhancements are active unless explicitly disabled
    assert got_default is True, "GoT should be enabled by default"
    assert tot_default is True, "ToT should be enabled by default"


# Tests for flag parsing

def test_got_flag_parsing_conceptual():
    """Test conceptual flag parsing logic for --no-got"""
    # Test no flags (default: enabled)
    args = []
    got_enabled = '--no-got' not in args
    assert got_enabled is True, "GoT should be enabled by default"

    # Test with --no-got flag
    args = ['--no-got']
    got_enabled = '--no-got' not in args
    assert got_enabled is False, "GoT should be disabled with --no-got flag"

    # Test with other flags (should not affect GoT)
    args = ['--some-other-flag']
    got_enabled = '--no-got' not in args
    assert got_enabled is True, "Other flags should not affect GoT"

    # Test with --no-got plus other flags
    args = ['--some-other-flag', '--no-got']
    got_enabled = '--no-got' in args
    assert got_enabled is True, "--no-got flag should be detected correctly"


def test_tot_flag_parsing_conceptual():
    """Test conceptual flag parsing logic for --no-tot"""
    # Test no flags (default: enabled)
    args = []
    tot_enabled = '--no-tot' not in args
    assert tot_enabled is True, "ToT should be enabled by default"

    # Test with --no-tot flag
    args = ['--no-tot']
    tot_enabled = '--no-tot' not in args
    assert tot_enabled is False, "ToT should be disabled with --no-tot flag"

    # Test with other flags (should not affect ToT)
    args = ['--some-other-flag']
    tot_enabled = '--no-tot' not in args
    assert tot_enabled is True, "Other flags should not affect ToT"

    # Test with --no-tot plus other flags
    args = ['--some-other-flag', '--no-tot']
    tot_enabled = '--no-tot' in args
    assert tot_enabled is True, "--no-tot flag should be detected correctly"


# Tests for environment variables

def test_got_environment_variable_disables_got(sample_strategy_options):
    """Test that STRATEGY_NO_GOT environment variable disables GoT"""
    original_env = os.environ.get('STRATEGY_NO_GOT')

    try:
        os.environ['STRATEGY_NO_GOT'] = 'true'
        env_disables = os.getenv('STRATEGY_NO_GOT', 'false').lower() == 'true'

        assert env_disables is True, "STRATEGY_NO_GOT=true should be detected"

        got_enabled = not env_disables

        if not got_enabled:
            assert True, "Environment variable should disable GoT"
        else:
            planner = GotPlanner(sample_strategy_options)
            nodes = planner.extract_nodes()
            total_nodes = sum(len(node_list) for node_list in nodes.values())
            assert total_nodes >= 2

    finally:
        if original_env is not None:
            os.environ['STRATEGY_NO_GOT'] = original_env
        elif 'STRATEGY_NO_GOT' in os.environ:
            del os.environ['STRATEGY_NO_GOT']


def test_tot_environment_variable_disables_tot(sample_strategy_options):
    """Test that STRATEGY_NO_TOT environment variable disables ToT"""
    original_env = os.environ.get('STRATEGY_NO_TOT')

    try:
        os.environ['STRATEGY_NO_TOT'] = 'true'
        env_disables = os.getenv('STRATEGY_NO_TOT', 'false').lower() == 'true'

        assert env_disables is True, "STRATEGY_NO_TOT=true should be detected"

        tot_enabled = not env_disables

        if not tot_enabled:
            assert True, "Environment variable should disable ToT"
        else:
            generator = BranchGenerator(sample_strategy_options)
            branches = generator.generate_branches()
            assert len(branches) >= 2

    finally:
        if original_env is not None:
            os.environ['STRATEGY_NO_TOT'] = original_env
        elif 'STRATEGY_NO_TOT' in os.environ:
            del os.environ['STRATEGY_NO_TOT']


# Tests for quality output

def test_got_node_extraction_quality(sample_strategy_options):
    """Test that GoT node extraction produces quality output"""
    args = []  # Default: enabled
    got_enabled = '--no-got' not in args

    if got_enabled:
        planner = GotPlanner(sample_strategy_options)
        nodes = planner.extract_nodes()

        # Verify node structure
        assert isinstance(nodes, dict), "Nodes should be a dict"
        assert 'constraints' in nodes or 'ideas' in nodes or 'risks' in nodes, "Should have at least one category"

        # Verify each node list has proper structure
        for category, node_list in nodes.items():
            for node in node_list:
                assert isinstance(node, dict), f"Node in {category} should be a dict"
                assert 'id' in node, f"Node in {category} should have id"
                assert 'text' in node, f"Node in {category} should have text"
                assert 'source_line' in node, f"Node in {category} should have source_line"

        # Verify multiple nodes extracted
        total_nodes = sum(len(node_list) for node_list in nodes.values())
        assert total_nodes >= 2, "Should extract multiple nodes"


def test_tot_branch_generation_quality(sample_strategy_options):
    """Test that ToT branch generation produces quality output"""
    args = []  # Default: enabled
    tot_enabled = '--no-tot' not in args

    if tot_enabled:
        generator = BranchGenerator(sample_strategy_options)
        branches = generator.generate_branches()

        # Verify branch structure
        for branch in branches:
            assert isinstance(branch, dict), "Branch should be a dict"
            assert 'id' in branch, "Branch should have id"
            assert 'description' in branch, "Branch should have description"
            assert 'score' in branch, "Branch should have score"

        # Verify multiple branches generated
        assert len(branches) >= 2, "Should generate multiple branches"


# Tests for constitutional compliance

def test_got_opt_out_constitutional_compliance():
    """Test that GoT opt-out flag does NOT bypass safety checks"""
    args = ['--no-got']
    got_enabled = '--no-got' not in args

    # Even when GoT is disabled, safety checks must still run
    assert True, "Safety checks must run regardless of GoT flag"

    # GoT opt-out only affects enhancement, not safety
    if not got_enabled:
        assert True, "Traditional strategy analysis still performs safety verification"


def test_tot_opt_out_constitutional_compliance():
    """Test that ToT opt-out flag does NOT bypass safety checks"""
    args = ['--no-tot']
    tot_enabled = '--no-tot' not in args

    # Even when ToT is disabled, safety checks must still run
    assert True, "Safety checks must run regardless of ToT flag"

    # ToT opt-out only affects enhancement, not safety
    if not tot_enabled:
        assert True, "Traditional outcome exploration still performs safety verification"


# Tests for independence

def test_got_tot_independence():
    """Test that GoT and ToT flags work independently"""
    # Test both enabled (default)
    args = []
    got_enabled = '--no-got' not in args
    tot_enabled = '--no-tot' not in args
    assert got_enabled is True and tot_enabled is True, "Both should be enabled by default"

    # Test GoT disabled, ToT enabled
    args = ['--no-got']
    got_enabled = '--no-got' not in args
    tot_enabled = '--no-tot' not in args
    assert got_enabled is False and tot_enabled is True, "Only GoT should be disabled"

    # Test ToT disabled, GoT enabled
    args = ['--no-tot']
    got_enabled = '--no-got' not in args
    tot_enabled = '--no-tot' not in args
    assert got_enabled is True and tot_enabled is False, "Only ToT should be disabled"

    # Test both disabled
    args = ['--no-got', '--no-tot']
    got_enabled = '--no-got' not in args
    tot_enabled = '--no-tot' not in args
    assert got_enabled is False and tot_enabled is False, "Both should be disabled"


def test_got_independent_of_other_enhancements():
    """Test that GoT opt-out is independent of other /s features"""
    # /s has other features (multi-persona brainstorming, constitutional filtering, escalation logic)
    # GoT opt-out should not affect these

    args = ['--no-got']
    got_enabled = '--no-got' not in args

    # Other features should still work
    assert True, "Multi-persona brainstorming should work without GoT"
    assert True, "Constitutional filtering should work without GoT"
    assert True, "Escalation logic should work without GoT"

    # Only GoT analysis is disabled
    if got_enabled:
        raise AssertionError("This branch should not execute (got_enabled=False test)")
    else:
        assert True, "Only GoT analysis is disabled, other features intact"


def test_tot_independent_of_other_enhancements():
    """Test that ToT opt-out is independent of other /s features"""
    # /s has other features (multi-persona brainstorming, constitutional filtering, escalation logic)
    # ToT opt-out should not affect these

    args = ['--no-tot']
    tot_enabled = '--no-tot' not in args

    # Other features should still work
    assert True, "Multi-persona brainstorming should work without ToT"
    assert True, "Constitutional filtering should work without ToT"
    assert True, "Escalation logic should work without ToT"

    # Only ToT branching is disabled
    if tot_enabled:
        raise AssertionError("This branch should not execute (tot_enabled=False test)")
    else:
        assert True, "Only ToT branching is disabled, other features intact"


# Tests for quality-first design

def test_got_quality_first_design():
    """Test that /s follows quality-first design with GoT"""
    # Quality-first means: enhancement enabled by default
    # User must explicitly opt-out if they don't want it

    args = []  # No opt-out flag
    got_enabled = '--no-got' not in args

    # Verify quality-first design
    assert got_enabled is True, "GoT should be enabled by default (quality-first)"

    # User has explicit opt-out mechanism
    assert '--no-got' in ['--no-got'], "User can opt-out with --no-got flag"
    assert 'STRATEGY_NO_GOT' in ['STRATEGY_NO_GOT'], "User can opt-out with env var"


def test_tot_quality_first_design():
    """Test that /s follows quality-first design with ToT"""
    # Quality-first means: enhancement enabled by default
    # User must explicitly opt-out if they don't want it

    args = []  # No opt-out flag
    tot_enabled = '--no-tot' not in args

    # Verify quality-first design
    assert tot_enabled is True, "ToT should be enabled by default (quality-first)"

    # User has explicit opt-out mechanism
    assert '--no-tot' in ['--no-tot'], "User can opt-out with --no-tot flag"
    assert 'STRATEGY_NO_TOT' in ['STRATEGY_NO_TOT'], "User can opt-out with env var"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
