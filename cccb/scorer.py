"""Score calculation for benchmark results."""
from __future__ import annotations


DEFAULT_WEIGHTS = (0.4, 0.4, 0.2)


def calculate_check_score(checks_passed: int, checks_total: int) -> float:
    """
    Calculate check score on 0-10 scale.

    Args:
        checks_passed: Number of checks that passed
        checks_total: Total number of checks

    Returns:
        Score from 0.0 to 10.0, or 0.0 if checks_total is 0
    """
    if checks_total == 0:
        return 0.0
    return (checks_passed / checks_total) * 10


def calculate_efficiency(
    cost_rank: int,
    time_rank: int,
    n_configs: int,
    timeout: bool = False
) -> float:
    """
    Calculate efficiency score on 1-10 scale.

    Ranks are 1-indexed (1 is best, n_configs is worst).

    Args:
        cost_rank: Rank by cost (1 = cheapest)
        time_rank: Rank by time (1 = fastest)
        n_configs: Total number of configurations
        timeout: Whether the run timed out (returns 1.0 if True)

    Returns:
        Score from 1.0 to 10.0
    """
    if timeout:
        return 1.0

    if n_configs <= 1:
        return 5.0

    return 10 - ((cost_rank + time_rank - 2) / (2 * (n_configs - 1))) * 9


def calculate_total_score(
    check_score: float,
    judge_score: float,
    efficiency: float,
    weights: tuple[float, float, float] = DEFAULT_WEIGHTS
) -> float:
    """
    Calculate total score as weighted combination.

    Args:
        check_score: Check score (0-10)
        judge_score: Judge score (typically 1-10)
        efficiency: Efficiency score (1-10)
        weights: Tuple of (check_weight, judge_weight, efficiency_weight)

    Returns:
        Weighted total score
    """
    w_check, w_judge, w_eff = weights
    return (check_score * w_check) + (judge_score * w_judge) + (efficiency * w_eff)


def calculate_config_average(scores: list[float]) -> float:
    """
    Calculate average score for a configuration across all tasks.

    Args:
        scores: List of scores

    Returns:
        Average score, or 0.0 if list is empty
    """
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
