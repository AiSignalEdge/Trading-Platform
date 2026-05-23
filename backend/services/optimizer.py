"""
Bayesian Parameter Optimizer for trading strategy parameters.

Uses Gaussian Process-based Expected Improvement to find optimal parameters
for trading strategies by running backtests and maximizing a target metric.
"""

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from services.backtest.engine import BacktestConfig, BacktestEngine

logger = logging.getLogger(__name__)


@dataclass
class SearchSpace:
    """Defines the search space for a parameter."""
    min_value: float
    max_value: float
    default: float = None

    def __post_init__(self):
        if self.default is None:
            self.default = (self.min_value + self.max_value) / 2


def _rbf_kernel(X: np.ndarray, X_prime: np.ndarray, gamma: float = 1.0) -> np.ndarray:
    """RBF kernel: k(x, x') = exp(-gamma * ||x - x'||^2)"""
    X_flat = X.reshape(X.shape[0], -1)
    X_prime_flat = X_prime.reshape(X_prime.shape[0], -1)
    sq_dists = np.sum((X_flat[:, np.newaxis, :] - X_prime_flat[np.newaxis, :, :]) ** 2, axis=2)
    return np.exp(-gamma * sq_dists)


def _norm_cdf(x):
    """Cumulative distribution function for standard normal."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x):
    """Probability density function for standard normal."""
    return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)


class BayesianOptimizer:
    """
    Bayesian optimizer using Gaussian Process with Expected Improvement acquisition.
    """

    def __init__(self, search_space: dict[str, dict[str, float]]):
        """
        Initialize optimizer with parameter search space.

        Args:
            search_space: Dict mapping parameter names to {min, max, default}
        """
        self.search_space = search_space
        self.param_names = list(search_space.keys())
        self.X_observed: list[dict] = []
        self.y_observed: list[float] = []

    def _sample_random_parameters(self) -> dict[str, float]:
        """Sample a random point from the search space uniformly."""
        params = {}
        for name, space in self.search_space.items():
            params[name] = np.random.uniform(space["min"], space["max"])
        return params

    def _params_to_vector(self, params: dict[str, float]) -> np.ndarray:
        """Convert parameter dict to numpy vector."""
        return np.array([params[name] for name in self.param_names])

    def _vector_to_params(self, vec: np.ndarray) -> dict[str, float]:
        """Convert numpy vector back to parameter dict."""
        return {name: float(vec[i]) for i, name in enumerate(self.param_names)}

    async def _fit_gp(self) -> tuple[np.ndarray, np.ndarray, float]:
        """Fit GP on observed data. Returns (X, y_normalized, gamma)."""
        if len(self.X_observed) == 0:
            raise ValueError("No observations yet")

        X = np.array([self._params_to_vector(p) for p in self.X_observed])
        y = np.array(self.y_observed)

        # Normalize y for numerical stability
        y_mean, y_std = y.mean(), y.std() + 1e-8
        y_norm = (y - y_mean) / y_std

        # Estimate gamma from data spread using median pairwise distance
        if len(X) > 1:
            X_flat = X.reshape(X.shape[0], -1)
            med_dist = np.median(np.sqrt(np.sum((X_flat[:, np.newaxis, :] - X_flat[np.newaxis, :, :]) ** 2, axis=2)))
            gamma = 1.0 / (2 * med_dist ** 2 + 1e-8)
        else:
            gamma = 1.0

        return X, y_norm, y_mean, y_std, gamma

    async def _predict_gp(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        y_mean: float,
        y_std: float,
        gamma: float,
        X_cand: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """GP prediction at candidate points. Returns (mu, sigma)."""
        K = _rbf_kernel(X_train, X_train, gamma) + 1e-6 * np.eye(len(X_train))
        K_star = _rbf_kernel(X_train, X_cand, gamma)
        K_star_star = _rbf_kernel(X_cand, X_cand, gamma) + 1e-6 * np.eye(len(X_cand))

        try:
            K_inv = np.linalg.inv(K)
        except np.linalg.LinAlgError:
            return np.zeros(len(X_cand)), np.ones(len(X_cand))

        # Predicted mean (normalized)
        mu_norm = K_star.T @ K_inv @ y_train

        # Predicted covariance
        cov = K_star_star - K_star.T @ K_inv @ K_star
        var = np.maximum(np.diag(cov), 1e-8)
        sigma = np.sqrt(var)

        # Denormalize mean
        mu = mu_norm * y_std + y_mean

        return mu, sigma

    def _expected_improvement(
        self,
        mu: np.ndarray,
        sigma: np.ndarray,
        y_best: float,
        xi: float = 0.01,
    ) -> np.ndarray:
        """
        Compute Expected Improvement acquisition function.

        Args:
            mu: Predicted means for candidate points
            sigma: Predicted standard deviations
            y_best: Best observed y value
            xi: Exploration bonus (higher = more exploration)

        Returns:
            EI values for each candidate point
        """
        sigma = np.maximum(sigma, 1e-8)
        z = (mu - y_best - xi) / sigma
        ei = (mu - y_best - xi) * _norm_cdf(z) + sigma * _norm_pdf(z)
        ei[sigma < 1e-8] = 0.0
        return ei

    def _generate_candidate_points(self, n_candidates: int = 1000) -> np.ndarray:
        """Generate random candidate points for EI evaluation."""
        candidates = []
        for _ in range(n_candidates):
            params = self._sample_random_parameters()
            candidates.append(self._params_to_vector(params))
        return np.array(candidates)

    async def _suggest_next_parameters_ei(self) -> dict[str, float]:
        """Suggest next parameters using Expected Improvement."""
        if len(self.X_observed) < 2:
            # Not enough data for GP, use random sampling
            return self._sample_random_parameters()

        X_train, y_train, y_mean, y_std, gamma = await self._fit_gp()
        y_best = max(self.y_observed)

        # Generate candidate points
        candidates = self._generate_candidate_points(200)

        # Get GP predictions for all candidates
        mu, sigma = await self._predict_gp(X_train, y_train, y_mean, y_std, gamma, candidates)

        # Compute EI
        ei = self._expected_improvement(mu, sigma, y_best)

        # Pick the point with highest EI
        best_idx = int(np.argmax(ei))
        return self._vector_to_params(candidates[best_idx])

    def suggest_next_random(self) -> dict[str, float]:
        """Get a random parameter set (for initial exploration)."""
        return self._sample_random_parameters()


async def _run_backtest(
    strategy_name: str,
    symbols: list[str],
    timeframe: str,
    start_date: str,
    end_date: str,
    params: dict[str, float],
    capital: float,
) -> dict[str, Any]:
    """
    Run a backtest with given parameters and return metrics.

    Args:
        strategy_name: Name of the strategy to test
        symbols: List of trading symbols
        timeframe: Timeframe (e.g., "4h", "1d")
        start_date: Start date string
        end_date: End date string
        params: Strategy parameters to test
        capital: Initial capital

    Returns:
        Dict with backtest metrics including target metric
    """
    from datetime import datetime

    config = BacktestConfig(
        strategy_name=strategy_name,
        symbols=symbols,
        timeframe=timeframe,
        initial_cash=capital,
        start_date=datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date,
        end_date=datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date,
        extra_data={"strategy_params": params},
        commission=0.001,
        slippage=0.0005,
    )

    engine = BacktestEngine(config)
    results = await engine.run()

    if not results:
        return {
            "total_return": -999.0,
            "sharpe_ratio": -999.0,
            "trades": 0,
            "win_rate": 0.0,
        }

    # Aggregate metrics across symbols (use first result for now)
    result = results[0]
    return {
        "total_return": result.total_return,
        "total_return_pct": result.total_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "calmar_ratio": result.calmar_ratio,
        "max_drawdown_pct": result.max_drawdown_pct,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "trades": result.total_trades,
        "expectancy": result.expectancy,
    }


async def _evaluate_parameters(
    strategy_name: str,
    symbols: list[str],
    timeframe: str,
    start_date: str,
    end_date: str,
    params: dict[str, float],
    capital: float,
    target_metric: str,
) -> float:
    """
    Evaluate a parameter set and return the target metric score.

    Args:
        strategy_name: Name of the strategy
        symbols: Trading symbols
        timeframe: Timeframe
        start_date: Start date
        end_date: End date
        params: Strategy parameters to evaluate
        capital: Initial capital
        target_metric: Metric to optimize ("sharpe_ratio", "total_return", etc.)

    Returns:
        Score for the parameter set
    """
    metrics = await _run_backtest(
        strategy_name=strategy_name,
        symbols=symbols,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        params=params,
        capital=capital,
    )

    # Get the target metric value
    score = metrics.get(target_metric, 0.0)

    # Handle edge case where score is invalid
    if score == -999.0 or math.isnan(score):
        return -1000.0

    return float(score)


async def optimize_strategy_parameters(
    strategy_name: str,
    symbols: list[str],
    timeframe: str,
    start_date: str,
    end_date: str,
    search_space: dict[str, dict[str, float]],
    n_initial: int = 5,
    n_iterations: int = 20,
    target_metric: str = "sharpe_ratio",
    capital: float = 10000,
) -> dict:
    """
    Optimize strategy parameters using Bayesian optimization with GP.

    Args:
        strategy_name: Name of the strategy to optimize
        symbols: Trading symbols to test on
        timeframe: Timeframe (e.g., "4h", "1d")
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        search_space: Parameter search space dict
        n_initial: Number of random initial evaluations
        n_iterations: Number of Bayesian optimization iterations
        target_metric: Metric to optimize
        capital: Initial capital for backtesting

    Returns:
        Dict with best parameters, score, and optimization history
    """
    logger.info(f"Starting Bayesian optimization for {strategy_name}")
    logger.info(f"Search space: {search_space}")
    logger.info(f"Target metric: {target_metric}, n_initial={n_initial}, n_iterations={n_iterations}")

    optimizer = BayesianOptimizer(search_space)

    evaluations: list[dict] = []
    convergence: list[dict] = []
    best_score = float('-inf')
    best_params = None

    # Phase 1: Random initial evaluations
    logger.info(f"Running {n_initial} initial random evaluations...")
    for i in range(n_initial):
        params = optimizer.suggest_next_random()
        logger.info(f"  Initial eval {i+1}/{n_initial}: {params}")

        score = await _evaluate_parameters(
            strategy_name=strategy_name,
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            params=params,
            capital=capital,
            target_metric=target_metric,
        )

        metrics = await _run_backtest(
            strategy_name=strategy_name,
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            params=params,
            capital=capital,
        )

        optimizer.X_observed.append(params)
        optimizer.y_observed.append(score)

        evaluations.append({
            "parameters": params,
            "score": score,
            "metrics": metrics,
        })

        if score > best_score:
            best_score = score
            best_params = params.copy()
            logger.info(f"  New best: {best_score:.4f} with {best_params}")

        convergence.append({
            "iteration": i,
            "best_score": best_score,
        })

    # Phase 2: Bayesian optimization iterations
    logger.info(f"Running {n_iterations} Bayesian optimization iterations...")
    for i in range(n_iterations):
        # Suggest next parameters using EI
        params = await optimizer._suggest_next_parameters_ei()
        logger.info(f"  BO eval {i+1}/{n_iterations}: {params}")

        score = await _evaluate_parameters(
            strategy_name=strategy_name,
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            params=params,
            capital=capital,
            target_metric=target_metric,
        )

        metrics = await _run_backtest(
            strategy_name=strategy_name,
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            params=params,
            capital=capital,
        )

        optimizer.X_observed.append(params)
        optimizer.y_observed.append(score)

        evaluations.append({
            "parameters": params,
            "score": score,
            "metrics": metrics,
        })

        if score > best_score:
            best_score = score
            best_params = params.copy()
            logger.info(f"  New best: {best_score:.4f} with {best_params}")

        convergence.append({
            "iteration": n_initial + i,
            "best_score": best_score,
        })

    logger.info(f"Optimization complete. Best score: {best_score:.4f}")
    logger.info(f"Best parameters: {best_params}")

    return {
        "best_parameters": best_params,
        "best_score": best_score,
        "evaluations": evaluations,
        "total_evaluations": len(evaluations),
        "convergence": convergence,
    }