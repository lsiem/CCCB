"""Tests for score calculation."""
import pytest

from cccb.scorer import (
    calculate_check_score,
    calculate_efficiency,
    calculate_total_score,
    calculate_config_average,
    DEFAULT_WEIGHTS,
)


class TestCheckScore:
    """Tests for check_score calculation."""

    def test_all_checks_pass(self):
        """Test score when all checks pass."""
        score = calculate_check_score(5, 5)
        assert score == 10.0

    def test_no_checks_pass(self):
        """Test score when no checks pass."""
        score = calculate_check_score(0, 5)
        assert score == 0.0

    def test_partial_pass(self):
        """Test score with partial pass (3/5)."""
        score = calculate_check_score(3, 5)
        assert score == 6.0

    def test_zero_total_checks(self):
        """Test score when total checks is zero."""
        score = calculate_check_score(0, 0)
        assert score == 0.0

    def test_single_check_pass(self):
        """Test score with single passing check."""
        score = calculate_check_score(1, 1)
        assert score == 10.0

    def test_single_check_fail(self):
        """Test score with single failing check."""
        score = calculate_check_score(0, 1)
        assert score == 0.0

    def test_half_pass(self):
        """Test score with exactly half passing."""
        score = calculate_check_score(2, 4)
        assert score == 5.0


class TestEfficiency:
    """Tests for efficiency calculation."""

    def test_best_efficiency(self):
        """Test efficiency when ranked best (1st)."""
        score = calculate_efficiency(1, 1, 3)
        assert score == 10.0

    def test_worst_efficiency(self):
        """Test efficiency when ranked worst."""
        score = calculate_efficiency(3, 3, 3)
        assert score == 1.0

    def test_middle_efficiency(self):
        """Test efficiency in middle rank."""
        score = calculate_efficiency(2, 2, 3)
        assert score == 5.5

    def test_single_config(self):
        """Test efficiency with single configuration."""
        score = calculate_efficiency(1, 1, 1)
        assert score == 5.0

    def test_zero_configs(self):
        """Test efficiency with zero configurations."""
        score = calculate_efficiency(1, 1, 0)
        assert score == 5.0

    def test_timeout_returns_worst(self):
        """Test that timeout always returns 1.0."""
        score = calculate_efficiency(1, 1, 5, timeout=True)
        assert score == 1.0

    def test_timeout_ignores_ranks(self):
        """Test that timeout overrides ranks."""
        score1 = calculate_efficiency(1, 1, 5, timeout=True)
        score2 = calculate_efficiency(5, 5, 5, timeout=True)
        assert score1 == score2 == 1.0

    def test_two_configs_best(self):
        """Test efficiency with two configs, best rank."""
        score = calculate_efficiency(1, 1, 2)
        assert score == 10.0

    def test_two_configs_worst(self):
        """Test efficiency with two configs, worst rank."""
        score = calculate_efficiency(2, 2, 2)
        assert score == 1.0

    def test_large_config_set(self):
        """Test efficiency with many configurations."""
        # 10 configs, middle rank (5th and 5th)
        score = calculate_efficiency(5, 5, 10)
        # 10 - ((5 + 5 - 2) / (2 * (10 - 1))) * 9
        # = 10 - (8 / 18) * 9
        # = 10 - 4
        # = 6
        assert score == 6.0


class TestTotalScore:
    """Tests for total score calculation."""

    def test_all_perfect_scores(self):
        """Test total score when all components are 10."""
        score = calculate_total_score(10, 10, 10)
        assert score == 10.0

    def test_default_weights(self):
        """Test that default weights sum correctly."""
        w_check, w_judge, w_eff = DEFAULT_WEIGHTS
        assert w_check + w_judge + w_eff == 1.0

    def test_custom_weights(self):
        """Test total score with custom weights."""
        # Custom weights: 50% check, 30% judge, 20% efficiency
        weights = (0.5, 0.3, 0.2)
        score = calculate_total_score(10, 10, 10, weights)
        assert score == 10.0

    def test_mixed_scores_default_weights(self):
        """Test with mixed scores and default weights."""
        # check=8, judge=6, efficiency=4
        # (8 * 0.4) + (6 * 0.4) + (4 * 0.2) = 3.2 + 2.4 + 0.8 = 6.4
        score = calculate_total_score(8, 6, 4)
        assert score == 6.4

    def test_all_zero_scores(self):
        """Test total score with all zeros."""
        score = calculate_total_score(0, 0, 0)
        assert score == 0.0

    def test_check_only_weighting(self):
        """Test with only check score weighted."""
        weights = (1.0, 0.0, 0.0)
        score = calculate_total_score(8, 10, 10, weights)
        assert score == 8.0

    def test_judge_only_weighting(self):
        """Test with only judge score weighted."""
        weights = (0.0, 1.0, 0.0)
        score = calculate_total_score(10, 5, 10, weights)
        assert score == 5.0

    def test_efficiency_only_weighting(self):
        """Test with only efficiency score weighted."""
        weights = (0.0, 0.0, 1.0)
        score = calculate_total_score(10, 10, 7, weights)
        assert score == 7.0


class TestConfigAverage:
    """Tests for config average calculation."""

    def test_three_scores(self):
        """Test average with three scores."""
        scores = [7.0, 8.0, 9.0]
        avg = calculate_config_average(scores)
        assert avg == 8.0

    def test_single_score(self):
        """Test average with single score."""
        scores = [5.0]
        avg = calculate_config_average(scores)
        assert avg == 5.0

    def test_empty_list(self):
        """Test average with empty list."""
        scores = []
        avg = calculate_config_average(scores)
        assert avg == 0.0

    def test_identical_scores(self):
        """Test average with identical scores."""
        scores = [6.5, 6.5, 6.5, 6.5]
        avg = calculate_config_average(scores)
        assert avg == 6.5

    def test_mixed_scores_including_zero(self):
        """Test average including zero."""
        scores = [0.0, 5.0, 10.0]
        avg = calculate_config_average(scores)
        assert avg == 5.0

    def test_decimal_average(self):
        """Test average with decimal result."""
        scores = [7.0, 8.0, 9.0, 10.0]
        avg = calculate_config_average(scores)
        assert avg == 8.5
