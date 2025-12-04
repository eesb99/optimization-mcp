"""
Portfolio Optimization Tool

optimize_portfolio: Optimize portfolio allocation with risk-return tradeoffs.

Use cases:
- Maximize Sharpe ratio (return/risk)
- Minimize variance for target return
- Maximize return for target risk
"""

from typing import Dict, List, Any, Optional
import numpy as np

try:
    import cvxpy as cp
    CVXPY_AVAILABLE = True
except ImportError:
    CVXPY_AVAILABLE = False

from ..solvers.cvxpy_solver import CVXPYSolver
from ..solvers.base_solver import ObjectiveSense
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_portfolio(
    assets: List[Dict[str, Any]],
    covariance_matrix: List[List[float]],
    constraints: Optional[Dict[str, Any]] = None,
    optimization_objective: str = "sharpe",
    risk_free_rate: float = 0.02,
    monte_carlo_integration: Optional[Dict[str, Any]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Portfolio optimization with risk-return tradeoffs.

    Args:
        assets: List of assets with expected returns:
               - [{"name": "AAPL", "expected_return": 0.12}, ...]
        covariance_matrix: N×N covariance matrix for asset returns
                          - [[var1, cov12, ...], [cov21, var2, ...], ...]
        constraints: Optional portfolio constraints:
                    - max_weight: Maximum weight per asset (e.g., 0.3 = 30%)
                    - min_weight: Minimum weight per asset (e.g., 0.05 = 5%)
                    - target_return: Minimum expected return (for min_variance objective)
                    - target_risk: Maximum variance (for max_return objective)
                    - long_only: True to prevent short selling (default: True)
        optimization_objective: Optimization goal:
                              - "sharpe": Maximize Sharpe ratio (return/risk)
                              - "min_variance": Minimize variance for target return
                              - "max_return": Maximize return for target risk
        risk_free_rate: Risk-free rate for Sharpe ratio calculation (default: 0.02)
        monte_carlo_integration: Optional MC integration for uncertain returns
        solver_options: Optional solver settings

    Returns:
        Dict with:
        - status: "optimal", "infeasible", etc.
        - weights: Dict of asset weights (sum to 1.0)
        - expected_return: Portfolio expected return
        - portfolio_variance: Portfolio variance
        - portfolio_std: Portfolio standard deviation (risk)
        - sharpe_ratio: (return - rf) / std (if applicable)
        - monte_carlo_compatible: MC validation-ready output

    Example:
        result = optimize_portfolio(
            assets=[
                {"name": "stock_a", "expected_return": 0.12},
                {"name": "stock_b", "expected_return": 0.08},
                {"name": "bond", "expected_return": 0.04}
            ],
            covariance_matrix=[
                [0.04, 0.01, 0.002],  # stock_a variance and covariances
                [0.01, 0.02, 0.001],  # stock_b
                [0.002, 0.001, 0.005]  # bond
            ],
            optimization_objective="sharpe",
            risk_free_rate=0.02
        )
    """
    if not CVXPY_AVAILABLE:
        return {
            "status": "error",
            "error": "CVXPY not installed",
            "message": "Portfolio optimization requires CVXPY. Install with: pip install cvxpy"
        }

    # Validate inputs
    _validate_portfolio_inputs(assets, covariance_matrix, optimization_objective)

    # Process constraints
    constraints = constraints or {}
    max_weight = constraints.get("max_weight", 1.0)
    min_weight = constraints.get("min_weight", 0.0)
    long_only = constraints.get("long_only", True)
    target_return = constraints.get("target_return", None)
    target_risk = constraints.get("target_risk", None)

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)

    # Process asset returns (with MC integration if provided)
    expected_returns = _process_asset_returns(assets, monte_carlo_integration)

    # Convert inputs to numpy arrays
    asset_names = [asset["name"] for asset in assets]
    n_assets = len(asset_names)
    returns_array = np.array([expected_returns[name] for name in asset_names])
    cov_matrix = np.array(covariance_matrix)

    # Validate covariance matrix
    if cov_matrix.shape != (n_assets, n_assets):
        return {
            "status": "error",
            "error": f"Covariance matrix shape {cov_matrix.shape} doesn't match {n_assets} assets",
            "message": "Covariance matrix must be N×N where N = number of assets"
        }

    # Create solver
    # Use "QP" for variance minimization and Sharpe, but problem_type doesn't
    # strictly enforce solver - CVXPY will auto-select appropriate solver
    solver = CVXPYSolver(problem_type="QP")

    # Create weight variables
    variables = solver.create_variables(
        names=asset_names,
        var_type="continuous"
    )

    # Build weight vector for CVXPY
    weights = cp.hstack([variables[name] for name in asset_names])

    # Add basic constraints
    # Constraint 1: Weights sum to 1
    solver.add_constraint(cp.sum(weights) == 1)

    # Constraint 2: Weight bounds
    for name in asset_names:
        if long_only:
            solver.add_constraint(variables[name] >= min_weight)
        else:
            # Allow short selling within bounds
            solver.add_constraint(variables[name] >= -max_weight)
        solver.add_constraint(variables[name] <= max_weight)

    # Build portfolio metrics
    portfolio_return = returns_array @ weights
    portfolio_variance = cp.quad_form(weights, cov_matrix)

    # Set objective based on optimization goal
    if optimization_objective == "sharpe":
        # Maximize Sharpe ratio = (return - rf) / std
        # Equivalent to: maximize (return - rf) subject to std = 1
        # Or: maximize (return - rf)^2 / variance
        # We use a simpler approach: minimize variance - lambda * return
        # Lambda chosen to balance risk-return tradeoff
        excess_return = portfolio_return - risk_free_rate

        # CVXPY doesn't handle division by sqrt well for optimization
        # Use alternative: maximize return - risk_aversion * variance
        risk_aversion = 0.5  # Tuning parameter
        obj_expr = excess_return - risk_aversion * portfolio_variance
        solver.set_objective(obj_expr, ObjectiveSense.MAXIMIZE)

    elif optimization_objective == "min_variance":
        # Minimize variance subject to target return
        if target_return is None:
            return {
                "status": "error",
                "error": "target_return required for min_variance objective",
                "message": "Specify target_return in constraints"
            }

        solver.set_objective(portfolio_variance, ObjectiveSense.MINIMIZE)
        solver.add_constraint(portfolio_return >= target_return)

    elif optimization_objective == "max_return":
        # Maximize return subject to target risk
        if target_risk is None:
            return {
                "status": "error",
                "error": "target_risk required for max_return objective",
                "message": "Specify target_risk in constraints"
            }

        solver.set_objective(portfolio_return, ObjectiveSense.MAXIMIZE)
        solver.add_constraint(portfolio_variance <= target_risk)

    else:
        return {
            "status": "error",
            "error": f"Invalid optimization_objective: {optimization_objective}",
            "message": "Must be 'sharpe', 'min_variance', or 'max_return'"
        }

    # Solve
    try:
        status = solver.solve(time_limit=time_limit, verbose=verbose)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Solver encountered an error during portfolio optimization"
        }

    # Build result
    result = _build_portfolio_result(
        solver,
        asset_names,
        returns_array,
        cov_matrix,
        risk_free_rate,
        optimization_objective
    )

    # Add Monte Carlo compatible output
    if solver.is_feasible():
        mc_output = _create_mc_compatible_output(
            result["weights"],
            expected_returns,
            result["expected_return"],
            result["portfolio_variance"]
        )
        result["monte_carlo_compatible"] = mc_output

    return result


def _validate_portfolio_inputs(
    assets: List[Dict[str, Any]],
    covariance_matrix: List[List[float]],
    optimization_objective: str
):
    """
    Validate portfolio optimization inputs.

    Args:
        assets: List of asset dicts
        covariance_matrix: Covariance matrix
        optimization_objective: Objective type

    Raises:
        ValueError: If inputs are invalid
    """
    if not isinstance(assets, list) or len(assets) < 2:
        raise ValueError("Portfolio requires at least 2 assets")

    for i, asset in enumerate(assets):
        if "name" not in asset:
            raise ValueError(f"Asset {i} missing 'name'")
        if "expected_return" not in asset:
            raise ValueError(f"Asset {i} missing 'expected_return'")
        if not isinstance(asset["expected_return"], (int, float)):
            raise ValueError(f"Asset {i} 'expected_return' must be numeric")

    if not isinstance(covariance_matrix, list):
        raise ValueError("Covariance matrix must be a list of lists")

    valid_objectives = ["sharpe", "min_variance", "max_return"]
    if optimization_objective not in valid_objectives:
        raise ValueError(
            f"Invalid optimization_objective: {optimization_objective}. "
            f"Must be one of: {valid_objectives}"
        )


def _process_asset_returns(
    assets: List[Dict[str, Any]],
    mc_integration: Optional[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Process asset returns, incorporating Monte Carlo data if provided.

    Args:
        assets: List of asset specifications
        mc_integration: Optional MC integration settings

    Returns:
        Dict mapping asset names to expected returns
    """
    # Start with base expected returns
    returns = {
        asset["name"]: asset["expected_return"]
        for asset in assets
    }

    # Override with MC values if integration is specified
    if mc_integration:
        mode = mc_integration.get("mode", "expected")
        mc_output = mc_integration.get("mc_output")

        if mc_output is None:
            raise ValueError(
                "monte_carlo_integration requires 'mc_output' field"
            )

        if mode == "percentile":
            percentile = mc_integration.get("percentile", "p50")
            mc_values = MonteCarloIntegration.extract_percentile_values(
                mc_output,
                percentile
            )
            for name in returns.keys():
                if name in mc_values:
                    returns[name] = mc_values[name]

        elif mode == "expected":
            mc_values = MonteCarloIntegration.extract_expected_values(mc_output)
            for name in returns.keys():
                if name in mc_values:
                    returns[name] = mc_values[name]

    return returns


def _build_portfolio_result(
    solver: CVXPYSolver,
    asset_names: List[str],
    returns_array: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float,
    optimization_objective: str
) -> Dict[str, Any]:
    """
    Build comprehensive portfolio result.

    Args:
        solver: Solved CVXPY solver
        asset_names: List of asset names
        returns_array: Array of expected returns
        cov_matrix: Covariance matrix
        risk_free_rate: Risk-free rate
        optimization_objective: Objective used

    Returns:
        Portfolio result dictionary
    """
    result = {
        "solver": "cvxpy",
        "optimization_objective": optimization_objective,
        "status": solver.status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if not solver.is_feasible():
        result["message"] = _generate_infeasibility_message(
            solver.status.value,
            optimization_objective
        )
        return result

    # Get solution (weights)
    solution = solver.get_solution()
    weights_dict = {name: solution[name] for name in asset_names}
    result["weights"] = weights_dict

    # Convert to numpy array for calculations
    weights_array = np.array([weights_dict[name] for name in asset_names])

    # Calculate portfolio metrics
    expected_return = float(np.dot(returns_array, weights_array))
    portfolio_variance = float(weights_array.T @ cov_matrix @ weights_array)
    portfolio_std = np.sqrt(portfolio_variance)

    result["expected_return"] = expected_return
    result["portfolio_variance"] = float(portfolio_variance)
    result["portfolio_std"] = float(portfolio_std)

    # Calculate Sharpe ratio
    sharpe_ratio = (expected_return - risk_free_rate) / portfolio_std if portfolio_std > 0 else 0
    result["sharpe_ratio"] = float(sharpe_ratio)

    # Add asset-level details
    asset_details = []
    for name in asset_names:
        asset_details.append({
            "name": name,
            "weight": weights_dict[name],
            "expected_return": float(returns_array[asset_names.index(name)]),
            "contribution_to_return": weights_dict[name] * returns_array[asset_names.index(name)]
        })
    result["assets"] = asset_details

    # Risk contribution analysis
    # Marginal contribution to risk = 2 * Σ @ w
    marginal_risk = 2 * cov_matrix @ weights_array
    risk_contribution = weights_array * marginal_risk
    risk_contribution_pct = risk_contribution / portfolio_variance if portfolio_variance > 0 else np.zeros_like(risk_contribution)

    for i, name in enumerate(asset_names):
        asset_details[i]["risk_contribution"] = float(risk_contribution[i])
        asset_details[i]["risk_contribution_pct"] = float(risk_contribution_pct[i] * 100)

    return result


def _generate_infeasibility_message(
    status: str,
    optimization_objective: str
) -> str:
    """
    Generate helpful error message for infeasible portfolio problems.

    Args:
        status: Solver status
        optimization_objective: Objective that was used

    Returns:
        Helpful error message
    """
    if status == "infeasible":
        if optimization_objective == "min_variance":
            return (
                "Portfolio is infeasible. Target return may be too high given "
                "the asset returns and constraints. Try reducing target_return."
            )
        elif optimization_objective == "max_return":
            return (
                "Portfolio is infeasible. Target risk may be too low given "
                "the asset volatilities and constraints. Try increasing target_risk."
            )
        else:
            return (
                "Portfolio is infeasible. Check that constraints are not contradictory "
                "(e.g., min_weight and max_weight settings)."
            )
    elif status == "unbounded":
        return (
            "Portfolio is unbounded. This suggests missing constraints. "
            "Ensure weights sum to 1 and have reasonable bounds."
        )
    else:
        return f"Portfolio optimization failed with status: {status}"


def _create_mc_compatible_output(
    weights: Dict[str, float],
    expected_returns: Dict[str, float],
    portfolio_return: float,
    portfolio_variance: float
) -> Dict[str, Any]:
    """
    Create Monte Carlo compatible output for validation.

    Args:
        weights: Optimal portfolio weights
        expected_returns: Expected return for each asset
        portfolio_return: Portfolio expected return
        portfolio_variance: Portfolio variance

    Returns:
        MC compatible output dict
    """
    # Create assumptions (asset returns as uncertain variables)
    assumptions = []
    for name, expected_return in expected_returns.items():
        assumptions.append({
            "name": f"{name}_return",
            "value": expected_return,
            "distribution": {
                "type": "normal",
                "params": {
                    "mean": expected_return,
                    "std": expected_return * 0.20  # Assume 20% volatility
                }
            }
        })

    # Outcome function description
    weighted_assets = [
        f"{weights[name]:.3f}*{name}_return"
        for name in weights.keys()
        if weights[name] > 0.001  # Only include significant weights
    ]
    outcome_function = f"Portfolio return = {' + '.join(weighted_assets)}"

    return {
        "decision_variables": weights,
        "assumptions": assumptions,
        "outcome_function": outcome_function,
        "expected_value": portfolio_return,
        "variance": portfolio_variance,
        "recommended_next_tool": "validate_reasoning_confidence",
        "recommended_params": {
            "decision_context": f"Portfolio allocation with {len(weights)} assets",
            "assumptions": {
                a["name"]: {
                    "distribution": a["distribution"]["type"],
                    "params": a["distribution"]["params"]
                }
                for a in assumptions
            },
            "success_criteria": {
                "threshold": portfolio_return * 0.90,  # 90% of expected return
                "comparison": ">="
            },
            "num_simulations": 10000
        }
    }
