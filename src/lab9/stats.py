"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for h, j in zip(human, judge):
        human_fail, judge_fail = h == POS, j == POS
        if human_fail and judge_fail:
            counts["tp"] += 1
        elif judge_fail:
            counts["fp"] += 1
        elif human_fail:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    n = len(human)
    if n == 0 or n != len(judge):
        raise ValueError("kappa is undefined without a paired sample")
    cm = confusion(human, judge)
    p_o = (cm["tp"] + cm["tn"]) / n
    p_human_fail = (cm["tp"] + cm["fn"]) / n
    p_judge_fail = (cm["tp"] + cm["fp"]) / n
    p_e = p_human_fail * p_judge_fail + (1 - p_human_fail) * (1 - p_judge_fail)
    if p_e == 1:
        raise ValueError("kappa is undefined when chance agreement is 1")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1
    if denom == 0:
        return 0.0
    corrected = (observed_rate + specificity - 1) / denom
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    left, right = list(a), list(b)
    if len(left) == len(right) and all(x == y for x, y in zip(left, right)):
        return (0.0, 0.0, 0.0)
    xs = np.asarray(left, dtype=float)
    ys = np.asarray(right, dtype=float)

    def difference(x, y, axis=-1):
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    result = bootstrap(
        (xs, ys),
        difference,
        n_resamples=n_resamples,
        paired=True,
        method="percentile",
        confidence_level=confidence,
        rng=np.random.default_rng(rng),
    )
    return (float(difference(xs, ys)), float(result.confidence_interval.low), float(result.confidence_interval.high))


def _check_pass_k(n: int, c: int, k: int) -> None:
    if n < 0 or c < 0 or c > n or k <= 0 or k > n:
        raise ValueError("pass@k is undefined unless 0 <= c <= n and 1 <= k <= n")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    import math
    _check_pass_k(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    import math
    _check_pass_k(n, c, k)
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)
