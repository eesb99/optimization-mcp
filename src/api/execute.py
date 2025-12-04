"""
Custom Optimization Execute Tool

optimize_execute: Flexible optimization with automatic solver selection.

Use cases:
- Power users with custom problem specifications
- Rapid prototyping of optimization problems
- When you know the mathematical form but want solver auto-selection
"""

from typing import Dict, List, Any, Optional
import pulp as pl
import numpy as np

try:
    import cvxpy as cp
    CVXPY_AVAILABLE = True
except ImportError:
    CVXPY_AVAILABLE = False

from ..solvers.pulp_solver import PuLPSolver
from ..solvers.scipy_solver import SciPySolver
from ..solvers.cvxpy_solver import CVXPYSolver
from ..solvers.base_solver import ObjectiveSense
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_execute(
    problem_definition: Dict[str, Any],
    auto_detect: bool = True,
    solver_preference: Optional[str] = None,
    monte_carlo_integration: Optional[Dict[str, Any]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute custom optimization with automatic solver selection.

    Flexible problem specification for power users who want control over
    the exact problem formulation while leveraging automatic solver selection.

    Args:
        problem_definition: Dict with:
                           - variables: [{name, type, bounds}]
                           - objective: {coefficients, sense} or {expression, sense}
                           - constraints: [{coefficients, type, rhs}] or [{expression, type}]
        auto_detect: Automatically detect best solver (default: True)
        solver_preference: Override auto-detection ("pulp", "scipy", "cvxpy")
        monte_carlo_integration: Optional MC integration
        solver_options: Optional solver settings

    Returns:
        Dict with:
        - status: "optimal", "infeasible", etc.
        - solver_used: Which solver was selected
        - objective_value: Optimal value
        - solution: Dict of variable values
        - problem_info: Problem statistics
        - monte_carlo_compatible: MC output

    Example (Dict-based):
        result = optimize_execute(
            problem_definition={
                "variables": [
                    {"name": "x", "type": "continuous", "bounds": (0, 10)},
                    {"name": "y", "type": "binary"}
                ],
                "objective": {
                    "coefficients": {"x": 3, "y": 2},
                    "sense": "maximize"
                },
                "constraints": [
                    {"coefficients": {"x": 1, "y": 1}, "type": "<=", "rhs": 10},
                    {"coefficients": {"x": 2, "y": -1}, "type": ">=", "rhs": 0}
                ]
            }
        )
    """
    # Validate problem definition
    try:
        _validate_problem_definition(problem_definition)
    except ValueError as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Invalid problem definition"
        }

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)

    # Detect problem type and select solver
    if solver_preference:
        solver_name = solver_preference.lower()
        if solver_name not in ["pulp", "scipy", "cvxpy"]:
            return {
                "status": "error",
                "error": f"Invalid solver_preference: {solver_preference}",
                "message": "Must be 'pulp', 'scipy', or 'cvxpy'"
            }
    elif auto_detect:
        solver_name = _detect_problem_type(problem_definition)
    else:
        solver_name = "pulp"  # Default

    # Check CVXPY availability
    if solver_name == "cvxpy" and not CVXPY_AVAILABLE:
        return {
            "status": "error",
            "error": "CVXPY not installed",
            "message": "Install with: pip install cvxpy"
        }

    # Build and solve problem
    try:
        if solver_name == "pulp":
            result = _solve_with_pulp(problem_definition, time_limit, verbose)
        elif solver_name == "scipy":
            result = _solve_with_scipy(problem_definition, time_limit, verbose)
        elif solver_name == "cvxpy":
            result = _solve_with_cvxpy(problem_definition, time_limit, verbose)
        else:
            return {
                "status": "error",
                "error": f"Unknown solver: {solver_name}"
            }

        # Add solver info
        result["solver_used"] = solver_name

        # Add MC compatible output if feasible
        if result.get("is_feasible", False):
            mc_output = _create_mc_compatible_output(
                result["solution"],
                result.get("objective_value", 0)
            )
            result["monte_carlo_compatible"] = mc_output

        return result

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "solver_used": solver_name,
            "message": f"Error during optimization with {solver_name}"
        }


def _validate_problem_definition(problem_def: Dict[str, Any]):
    """Validate problem definition format."""
    if not isinstance(problem_def, dict):
        raise ValueError("problem_definition must be a dict")

    if "variables" not in problem_def:
        raise ValueError("problem_definition must include 'variables'")

    if "objective" not in problem_def:
        raise ValueError("problem_definition must include 'objective'")

    variables = problem_def["variables"]
    if not isinstance(variables, list) or len(variables) == 0:
        raise ValueError("variables must be a non-empty list")

    for var in variables:
        if "name" not in var:
            raise ValueError("Each variable must have 'name'")
        if "type" not in var:
            raise ValueError(f"Variable '{var['name']}' must have 'type'")
        if var["type"] not in ["continuous", "integer", "binary"]:
            raise ValueError(
                f"Variable '{var['name']}' type must be 'continuous', 'integer', or 'binary'"
            )

    objective = problem_def["objective"]
    if "sense" not in objective:
        raise ValueError("objective must include 'sense' (maximize/minimize)")

    if objective["sense"] not in ["maximize", "minimize"]:
        raise ValueError("objective sense must be 'maximize' or 'minimize'")


def _detect_problem_type(problem_def: Dict[str, Any]) -> str:
    """
    Auto-detect appropriate solver based on problem characteristics.

    Args:
        problem_def: Problem definition

    Returns:
        Solver name: "pulp", "scipy", or "cvxpy"
    """
    variables = problem_def["variables"]
    objective = problem_def["objective"]

    # Check variable types
    has_binary = any(v["type"] == "binary" for v in variables)
    has_integer = any(v["type"] == "integer" for v in variables)

    # If integer/binary variables → PuLP
    if has_binary or has_integer:
        return "pulp"

    # Check for quadratic terms in objective
    if "coefficients" in objective:
        # Dict format - check for quadratic keys
        coeffs = objective["coefficients"]
        for key in coeffs.keys():
            if "*" in str(key) or "**2" in str(key):
                return "cvxpy"  # Quadratic detected

    # Check constraints for nonlinearity
    # For now, default to PuLP for linear continuous
    return "pulp"


def _solve_with_pulp(
    problem_def: Dict[str, Any],
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """Solve problem using PuLP."""
    solver = PuLPSolver(problem_name="custom_optimization")

    variables = problem_def["variables"]
    objective = problem_def["objective"]
    constraints = problem_def.get("constraints", [])

    # Create variables
    var_names = [v["name"] for v in variables]
    var_types = {v["name"]: v["type"] for v in variables}
    bounds = {v["name"]: v.get("bounds") for v in variables if "bounds" in v}

    # Group variables by type for solver.create_variables()
    continuous_vars = [v for v in variables if v["type"] == "continuous"]
    binary_vars = [v for v in variables if v["type"] == "binary"]
    integer_vars = [v for v in variables if v["type"] == "integer"]

    pulp_vars = {}

    # Create continuous variables
    if continuous_vars:
        cont_names = [v["name"] for v in continuous_vars]
        cont_bounds = {v["name"]: v.get("bounds") for v in continuous_vars if "bounds" in v}
        cont_created = solver.create_variables(cont_names, "continuous", cont_bounds)
        pulp_vars.update(cont_created)

    # Create binary variables
    if binary_vars:
        binary_names = [v["name"] for v in binary_vars]
        binary_created = solver.create_variables(binary_names, "binary", None)
        pulp_vars.update(binary_created)

    # Create integer variables
    if integer_vars:
        int_names = [v["name"] for v in integer_vars]
        int_bounds = {v["name"]: v.get("bounds") for v in integer_vars if "bounds" in v}
        int_created = solver.create_variables(int_names, "integer", int_bounds)
        pulp_vars.update(int_created)

    # Build objective
    obj_coeffs = objective.get("coefficients", {})
    obj_expr = pl.lpSum([obj_coeffs.get(name, 0) * pulp_vars[name] for name in var_names])

    sense = ObjectiveSense.MAXIMIZE if objective["sense"] == "maximize" else ObjectiveSense.MINIMIZE
    solver.set_objective(obj_expr, sense)

    # Add constraints
    for i, constraint in enumerate(constraints):
        coeffs = constraint.get("coefficients", {})
        con_expr = pl.lpSum([coeffs.get(name, 0) * pulp_vars[name] for name in var_names])
        rhs = constraint.get("rhs", 0)
        con_type = constraint.get("type", "<=")

        if con_type == "<=":
            solver.add_constraint(con_expr <= rhs, name=f"constraint_{i}")
        elif con_type == ">=":
            solver.add_constraint(con_expr >= rhs, name=f"constraint_{i}")
        elif con_type == "==":
            solver.add_constraint(con_expr == rhs, name=f"constraint_{i}")

    # Solve
    status = solver.solve(time_limit=time_limit, verbose=verbose)

    # Format result
    result = {
        "status": solver.status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if solver.is_feasible():
        result["objective_value"] = solver.get_objective_value()
        result["solution"] = solver.get_solution()
        result["shadow_prices"] = solver.get_shadow_prices()

    result["problem_info"] = solver.get_problem_info()

    return result


def _solve_with_scipy(
    problem_def: Dict[str, Any],
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """Solve problem using SciPy (continuous only)."""
    solver = SciPySolver(method="SLSQP")

    variables = problem_def["variables"]
    objective = problem_def["objective"]
    constraints = problem_def.get("constraints", [])

    # Check all variables are continuous
    for var in variables:
        if var["type"] != "continuous":
            return {
                "status": "error",
                "error": f"SciPy only supports continuous variables. Variable '{var['name']}' is {var['type']}",
                "message": "Use PuLP solver for integer/binary variables"
            }

    # Create variables
    var_names = [v["name"] for v in variables]
    bounds = {v["name"]: v.get("bounds", (None, None)) for v in variables}

    solver.create_variables(var_names, var_type="continuous", bounds=bounds)

    # Build objective function
    obj_coeffs = objective.get("coefficients", {})

    def objective_func(x_array):
        x_dict = {name: x_array[i] for i, name in enumerate(var_names)}
        return sum(obj_coeffs.get(name, 0) * x_dict[name] for name in var_names)

    sense = ObjectiveSense.MAXIMIZE if objective["sense"] == "maximize" else ObjectiveSense.MINIMIZE
    solver.set_objective(objective_func, sense)

    # Add constraints
    for i, constraint in enumerate(constraints):
        coeffs = constraint.get("coefficients", {})
        rhs = constraint.get("rhs", 0)
        con_type = constraint.get("type", "<=")

        def con_func(x_array, coeffs=coeffs, rhs=rhs):
            x_dict = {name: x_array[i] for i, name in enumerate(var_names)}
            lhs = sum(coeffs.get(name, 0) * x_dict[name] for name in var_names)
            return lhs - rhs

        if con_type == "<=":
            solver.add_constraint({"type": "ineq", "fun": lambda x: rhs - sum(coeffs.get(var_names[i], 0) * x[i] for i in range(len(var_names)))})
        elif con_type == ">=":
            solver.add_constraint({"type": "ineq", "fun": lambda x: sum(coeffs.get(var_names[i], 0) * x[i] for i in range(len(var_names))) - rhs})
        elif con_type == "==":
            solver.add_constraint({"type": "eq", "fun": con_func})

    # Solve
    status = solver.solve(time_limit=time_limit, verbose=verbose)

    # Format result
    result = {
        "status": solver.status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if solver.is_feasible():
        result["objective_value"] = solver.get_objective_value()
        result["solution"] = solver.get_solution()

    result["problem_info"] = solver.get_problem_info()

    return result


def _solve_with_cvxpy(
    problem_def: Dict[str, Any],
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """Solve problem using CVXPY."""
    solver = CVXPYSolver(problem_type="QP")

    variables = problem_def["variables"]
    objective = problem_def["objective"]
    constraints = problem_def.get("constraints", [])

    # Create variables
    var_names = [v["name"] for v in variables]
    var_types = {v["name"]: v["type"] for v in variables}
    bounds = {v["name"]: v.get("bounds") for v in variables if "bounds" in v}

    cvxpy_vars = solver.create_variables(
        names=var_names,
        var_type="continuous",  # CVXPY handles types differently
        bounds=bounds
    )

    # Build objective
    obj_coeffs = objective.get("coefficients", {})
    obj_expr = sum(obj_coeffs.get(name, 0) * cvxpy_vars[name] for name in var_names)

    sense = ObjectiveSense.MAXIMIZE if objective["sense"] == "maximize" else ObjectiveSense.MINIMIZE
    solver.set_objective(obj_expr, sense)

    # Add constraints
    for i, constraint in enumerate(constraints):
        coeffs = constraint.get("coefficients", {})
        rhs = constraint.get("rhs", 0)
        con_type = constraint.get("type", "<=")

        con_expr = sum(coeffs.get(name, 0) * cvxpy_vars[name] for name in var_names)

        if con_type == "<=":
            solver.add_constraint(con_expr <= rhs)
        elif con_type == ">=":
            solver.add_constraint(con_expr >= rhs)
        elif con_type == "==":
            solver.add_constraint(con_expr == rhs)

    # Solve
    status = solver.solve(time_limit=time_limit, verbose=verbose)

    # Format result
    result = {
        "status": solver.status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if solver.is_feasible():
        result["objective_value"] = solver.get_objective_value()
        result["solution"] = solver.get_solution()
        result["dual_values"] = solver.get_dual_values()

    result["problem_info"] = solver.get_problem_info()

    return result


def _create_mc_compatible_output(
    solution: Dict[str, float],
    objective_value: float
) -> Dict[str, Any]:
    """
    Create Monte Carlo compatible output.

    Args:
        solution: Optimal variable values
        objective_value: Optimal objective value

    Returns:
        MC compatible output dict
    """
    # Create assumptions for each variable
    assumptions = []
    for name, value in solution.items():
        assumptions.append({
            "name": f"{name}_coefficient",
            "value": value,
            "distribution": {
                "type": "normal",
                "params": {
                    "mean": value,
                    "std": abs(value) * 0.10  # 10% uncertainty
                }
            }
        })

    return {
        "decision_variables": solution,
        "assumptions": assumptions,
        "outcome_function": f"Custom optimization with {len(solution)} variables",
        "expected_value": objective_value,
        "recommended_next_tool": "validate_reasoning_confidence",
        "recommended_params": {
            "decision_context": "Custom optimization problem",
            "assumptions": {
                a["name"]: {
                    "distribution": a["distribution"]["type"],
                    "params": a["distribution"]["params"]
                }
                for a in assumptions
            },
            "success_criteria": {
                "threshold": objective_value * 0.90,
                "comparison": ">="
            },
            "num_simulations": 10000
        }
    }
