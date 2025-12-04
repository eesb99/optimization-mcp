"""
Pareto Multi-Objective Optimization Tool

optimize_pareto: Generate Pareto frontier for multi-objective problems.

Use cases:
- Profit vs sustainability trade-off exploration
- Cost vs quality optimization
- Risk vs return analysis
- Multi-criteria decision support
"""

from typing import Dict, List, Any, Optional
import pulp as pl
import numpy as np

from ..solvers.pulp_solver import PuLPSolver
from ..solvers.base_solver import ObjectiveSense
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_pareto(
    objectives: List[Dict[str, Any]],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    constraints: Optional[List[Dict[str, Any]]] = None,
    num_points: int = 20,
    monte_carlo_integration: Optional[Dict[str, Any]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate Pareto frontier exploring trade-offs between multiple objectives.

    Finds set of non-dominated solutions showing how improving one objective
    requires sacrificing another. Uses weighted sum scalarization with systematic
    weight variation.

    Args:
        objectives: List of objective specifications:
                   - [{"name": str, "items": [{"name": str, "value": float}], "sense": str}, ...]
                   - Each objective has its own value function
                   - All objectives should have same sense (maximize or minimize)
        resources: Resource constraints (same as optimize_allocation)
        item_requirements: Item resource requirements (same as optimize_allocation)
        constraints: Optional additional constraints
        num_points: Number of Pareto frontier points to generate (default: 20)
                   Higher values give finer resolution but take longer
        monte_carlo_integration: Optional MC integration for objective values
        solver_options: Optional solver settings

    Returns:
        Dict with:
        - status: "optimal" if frontier found, "infeasible" otherwise
        - pareto_frontier: List of frontier points with allocations and objective values
        - num_frontier_points: Number of points on frontier
        - trade off_analysis: Sensitivity metrics showing trade-offs
        - recommended_point: Suggested balanced solution (knee point)
        - monte_carlo_compatible: MC validation-ready output

    Example:
        result = optimize_pareto(
            objectives=[
                {
                    "name": "profit",
                    "items": [
                        {"name": "project_a", "value": 125000},
                        {"name": "project_b", "value": 87000}
                    ],
                    "sense": "maximize"
                },
                {
                    "name": "sustainability",
                    "items": [
                        {"name": "project_a", "value": 75},
                        {"name": "project_b", "value": 92}
                    ],
                    "sense": "maximize"
                }
            ],
            resources={"budget": {"total": 100000}},
            item_requirements=[
                {"name": "project_a", "budget": 60000},
                {"name": "project_b", "budget": 45000}
            ],
            num_points=20
        )
    """
    # Validate inputs
    if len(objectives) < 2:
        raise ValueError("Pareto optimization requires at least 2 objectives")

    for i, obj in enumerate(objectives):
        if "name" not in obj:
            raise ValueError(f"Objective {i} missing 'name' field")
        DataConverter.validate_objective_spec(obj)

    DataConverter.validate_resources_spec(resources)
    DataConverter.validate_item_requirements(item_requirements, resources)

    # Note: Objectives can have mixed senses (maximize/minimize)
    # We'll normalize all to maximization by negating minimize objectives

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)

    # Process MC integration for all objectives
    objective_values = {}
    for obj in objectives:
        obj_name = obj["name"]
        objective_values[obj_name] = _extract_objective_values(
            obj,
            monte_carlo_integration
        )

    # Generate Pareto frontier
    frontier_points = _generate_pareto_frontier(
        objectives,
        objective_values,
        resources,
        item_requirements,
        constraints,
        num_points,
        time_limit,
        verbose
    )

    # Build result
    result = {
        "solver": "pulp",  # Currently uses PuLP for weighted sum
        "status": "optimal" if len(frontier_points) > 0 else "infeasible",
        "pareto_frontier": frontier_points,
        "num_frontier_points": len(frontier_points),
    }

    if len(frontier_points) > 0:
        # Analyze trade-offs
        tradeoff_analysis = _analyze_tradeoffs(frontier_points, objectives)
        result["tradeoff_analysis"] = tradeoff_analysis

        # Find recommended point (knee point - best balanced solution)
        recommended_idx = _find_knee_point(frontier_points, objectives)
        result["recommended_point"] = {
            "index": recommended_idx,
            "allocation": frontier_points[recommended_idx]["allocation"],
            "objective_values": frontier_points[recommended_idx]["objective_values"],
            "weights": frontier_points[recommended_idx]["weights"]
        }

        # Add MC compatible output using recommended point
        mc_output = _create_pareto_mc_output(
            result["recommended_point"],
            objectives,
            objective_values
        )
        result["monte_carlo_compatible"] = mc_output

    else:
        result["message"] = "No feasible Pareto frontier found. Check constraints."

    return result


def _extract_objective_values(
    objective: Dict[str, Any],
    mc_integration: Optional[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Extract objective values from specification or MC output.

    Args:
        objective: Objective specification
        mc_integration: Optional MC data

    Returns:
        Dict mapping item names to objective values
    """
    item_values = {}

    for item in objective["items"]:
        item_name = item["name"]
        base_value = item["value"]

        # Check if MC integration provides updated value
        if mc_integration:
            mode = mc_integration.get("mode", "percentile")
            mc_output = mc_integration.get("mc_output", {})

            if mode == "percentile":
                percentile = mc_integration.get("percentile", "p50")
                mc_values = MonteCarloIntegration.extract_percentile_values(
                    mc_output,
                    percentile=percentile
                )
                item_values[item_name] = mc_values.get(item_name, base_value)

            elif mode == "expected":
                mc_values = MonteCarloIntegration.extract_expected_values(mc_output)
                item_values[item_name] = mc_values.get(item_name, base_value)

            else:
                # Scenarios mode: use expected
                item_values[item_name] = base_value
        else:
            item_values[item_name] = base_value

    return item_values


def _generate_pareto_frontier(
    objectives: List[Dict[str, Any]],
    objective_values: Dict[str, Dict[str, float]],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    constraints: Optional[List[Dict[str, Any]]],
    num_points: int,
    time_limit: Optional[float],
    verbose: bool
) -> List[Dict[str, Any]]:
    """
    Generate Pareto frontier by solving weighted sum scalarizations.

    Args:
        objectives: List of objectives
        objective_values: Extracted values for each objective
        resources: Resource constraints
        item_requirements: Item requirements
        constraints: Additional constraints
        num_points: Number of frontier points
        time_limit: Solver time limit
        verbose: Print progress

    Returns:
        List of Pareto frontier points
    """
    num_objectives = len(objectives)
    frontier_points = []

    # Generate weight combinations
    if num_objectives == 2:
        # For 2 objectives: linear interpolation from (1,0) to (0,1)
        weight_combinations = [
            [1 - i/(num_points - 1), i/(num_points - 1)]
            for i in range(num_points)
        ]
    else:
        # For 3+ objectives: use systematic simplex lattice design
        weight_combinations = _generate_simplex_lattice_weights(num_objectives, num_points)

    if verbose:
        print(f"\nGenerating Pareto frontier with {len(weight_combinations)} points...")

    # Solve for each weight combination
    for weight_idx, weights in enumerate(weight_combinations):
        if verbose and weight_idx % 5 == 0:
            print(f"  Solving point {weight_idx + 1}/{len(weight_combinations)}...")

        # Create weighted objective
        result_point = _solve_weighted_scalarization(
            objectives,
            weights,
            objective_values,
            resources,
            item_requirements,
            constraints,
            time_limit,
            verbose=False  # Don't print for each point
        )

        if result_point["status"] == "optimal":
            frontier_points.append(result_point)

    # Remove dominated solutions (keep only non-dominated)
    if len(frontier_points) > 1:
        frontier_points = _filter_dominated_solutions(frontier_points, objectives)

    if verbose:
        print(f"  Found {len(frontier_points)} non-dominated solutions\n")

    return frontier_points


def _solve_weighted_scalarization(
    objectives: List[Dict[str, Any]],
    weights: List[float],
    objective_values: Dict[str, Dict[str, float]],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    constraints: Optional[List[Dict[str, Any]]],
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """
    Solve single weighted sum scalarization.

    Returns:
        Dict with status, allocation, objective_values, weights
    """
    solver = PuLPSolver(problem_name="pareto_scalarization")

    # Create variables
    item_names = [item["name"] for item in item_requirements]
    variables = solver.create_variables(names=item_names, var_type="binary")

    # Build weighted objective
    # Normalize all objectives to MAXIMIZATION by negating minimize objectives
    weighted_expr = 0

    for obj_idx, objective in enumerate(objectives):
        obj_name = objective["name"]
        weight = weights[obj_idx]
        values = objective_values[obj_name]
        obj_sense = objective["sense"]

        # For minimize objectives, negate the values (so we can maximize all)
        multiplier = 1.0 if obj_sense == "maximize" else -1.0

        # Add weighted contribution
        weighted_expr += weight * multiplier * pl.lpSum([
            values.get(item_name, 0) * variables[item_name]
            for item_name in item_names
        ])

    # Always maximize the weighted sum (since we normalized)
    solver.set_objective(weighted_expr, ObjectiveSense.MAXIMIZE)

    # Add resource constraints
    for resource_name, resource_spec in resources.items():
        total_available = resource_spec["total"]
        resource_expr = pl.lpSum([
            item.get(resource_name, 0) * variables[item["name"]]
            for item in item_requirements
        ])
        solver.add_constraint(
            resource_expr <= total_available,
            name=f"resource_{resource_name}"
        )

    # Add custom constraints
    if constraints:
        from .allocation import _add_custom_constraints
        _add_custom_constraints(solver, variables, constraints)

    # Solve
    try:
        status = solver.solve(time_limit=time_limit, verbose=verbose)
    except Exception:
        return {"status": "error"}

    if not solver.is_feasible():
        return {"status": status.value}

    # Extract solution
    solution = solver.get_solution()
    allocation = {name: int(solution[name]) for name in item_names}

    # Calculate objective values for this solution
    obj_values = {}
    for objective in objectives:
        obj_name = objective["name"]
        values = objective_values[obj_name]
        obj_value = sum(values.get(name, 0) * allocation[name] for name in item_names)
        obj_values[obj_name] = obj_value

    return {
        "status": "optimal",
        "weights": {objectives[i]["name"]: weights[i] for i in range(len(objectives))},
        "allocation": allocation,
        "objective_values": obj_values,
        "weighted_objective": solver.get_objective_value()
    }


def _generate_simplex_lattice_weights(num_objectives: int, target_points: int) -> List[List[float]]:
    """
    Generate weight combinations using simplex lattice design.

    For N objectives, creates systematic coverage of weight space.

    Args:
        num_objectives: Number of objectives
        target_points: Desired number of points

    Returns:
        List of weight vectors (each sums to 1.0)
    """
    # Calculate lattice resolution
    # For N objectives with resolution h, points = C(N+h-1, N-1)
    # Use heuristic: h ≈ target_points^(1/N)
    h = max(2, int(target_points ** (1.0 / num_objectives)))

    weights = []
    _generate_simplex_recursive(num_objectives, h, [], weights)

    # If we generated too many or too few, subsample or extend
    if len(weights) > target_points * 1.5:
        # Subsample uniformly
        indices = np.linspace(0, len(weights) - 1, target_points, dtype=int)
        weights = [weights[i] for i in indices]
    elif len(weights) < target_points // 2:
        # Add random points to reach target
        while len(weights) < target_points:
            random_weights = np.random.dirichlet([1] * num_objectives)
            weights.append(list(random_weights))

    return weights


def _generate_simplex_recursive(
    num_dims: int,
    h: int,
    current: List[int],
    results: List[List[float]]
):
    """Recursively generate simplex lattice points."""
    if len(current) == num_dims - 1:
        # Last dimension determined by others (sum to h)
        last_val = h - sum(current)
        if last_val >= 0:
            full_point = current + [last_val]
            # Convert to weights (divide by h)
            weights = [val / h for val in full_point]
            results.append(weights)
        return

    # Try all values for current dimension
    remaining = h - sum(current)
    for val in range(remaining + 1):
        _generate_simplex_recursive(num_dims, h, current + [val], results)


def _filter_dominated_solutions(
    frontier_points: List[Dict[str, Any]],
    objectives: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Remove dominated solutions from frontier.

    Solution A dominates B if A is better or equal on all objectives
    and strictly better on at least one.

    Args:
        frontier_points: Candidate frontier points
        objectives: Objective specifications

    Returns:
        Non-dominated points only
    """
    non_dominated = []
    obj_names = [obj["name"] for obj in objectives]
    sense = objectives[0]["sense"]  # All same sense

    for i, point_a in enumerate(frontier_points):
        is_dominated = False

        for j, point_b in enumerate(frontier_points):
            if i == j:
                continue

            # Check if point_b dominates point_a
            better_count = 0
            worse_count = 0

            for obj_name in obj_names:
                val_a = point_a["objective_values"][obj_name]
                val_b = point_b["objective_values"][obj_name]

                if sense == "maximize":
                    if val_b > val_a:
                        better_count += 1
                    elif val_b < val_a:
                        worse_count += 1
                else:  # minimize
                    if val_b < val_a:
                        better_count += 1
                    elif val_b > val_a:
                        worse_count += 1

            # Point B dominates A if better on ≥1 objective and not worse on any
            if better_count > 0 and worse_count == 0:
                is_dominated = True
                break

        if not is_dominated:
            non_dominated.append(point_a)

    return non_dominated


def _analyze_tradeoffs(
    frontier_points: List[Dict[str, Any]],
    objectives: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze trade-offs between objectives on the frontier.

    Args:
        frontier_points: Pareto frontier points
        objectives: Objective specifications

    Returns:
        Dict with trade-off metrics
    """
    obj_names = [obj["name"] for obj in objectives]
    sense = objectives[0]["sense"]

    # Calculate range for each objective
    ranges = {}
    for obj_name in obj_names:
        values = [p["objective_values"][obj_name] for p in frontier_points]
        ranges[obj_name] = {
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values)
        }

    # For 2 objectives, calculate marginal rate of substitution
    trade_off_rates = {}
    if len(obj_names) == 2:
        obj1, obj2 = obj_names[0], obj_names[1]

        # Sort frontier by first objective
        sorted_frontier = sorted(
            frontier_points,
            key=lambda p: p["objective_values"][obj1]
        )

        # Calculate slopes between consecutive points
        slopes = []
        for i in range(len(sorted_frontier) - 1):
            delta_obj1 = sorted_frontier[i+1]["objective_values"][obj1] - sorted_frontier[i]["objective_values"][obj1]
            delta_obj2 = sorted_frontier[i+1]["objective_values"][obj2] - sorted_frontier[i]["objective_values"][obj2]

            if abs(delta_obj1) > 1e-6:
                slope = delta_obj2 / delta_obj1
                slopes.append(slope)

        if slopes:
            trade_off_rates[f"{obj2}_per_{obj1}"] = {
                "mean": np.mean(slopes),
                "min": np.min(slopes),
                "max": np.max(slopes),
                "interpretation": f"On average, gaining 1 unit of {obj1} costs {abs(np.mean(slopes)):.2f} units of {obj2}"
            }

    return {
        "objective_ranges": ranges,
        "tradeoff_rates": trade_off_rates,
        "num_unique_solutions": len(set(str(p["allocation"]) for p in frontier_points))
    }


def _find_knee_point(
    frontier_points: List[Dict[str, Any]],
    objectives: List[Dict[str, Any]]
) -> int:
    """
    Find knee point (best balanced solution) on Pareto frontier.

    Uses distance from ideal point (best on all objectives).

    Args:
        frontier_points: Pareto frontier points
        objectives: Objective specifications

    Returns:
        Index of recommended point
    """
    obj_names = [obj["name"] for obj in objectives]
    sense = objectives[0]["sense"]

    # Find ideal point (best value for each objective)
    ideal = {}
    for obj_name in obj_names:
        values = [p["objective_values"][obj_name] for p in frontier_points]
        if sense == "maximize":
            ideal[obj_name] = max(values)
        else:
            ideal[obj_name] = min(values)

    # Normalize objectives to [0, 1] scale
    normalized_points = []
    for point in frontier_points:
        normalized = {}
        for obj_name in obj_names:
            values = [p["objective_values"][obj_name] for p in frontier_points]
            value_range = max(values) - min(values)

            if value_range > 1e-6:
                normalized[obj_name] = (
                    (point["objective_values"][obj_name] - min(values)) / value_range
                )
            else:
                normalized[obj_name] = 0.5  # All same, arbitrary

        normalized_points.append(normalized)

    # Find point closest to ideal (all 1.0 for maximize, all 0.0 for minimize)
    ideal_normalized = 1.0 if sense == "maximize" else 0.0

    distances = []
    for norm_point in normalized_points:
        # Euclidean distance from ideal
        dist = sum((norm_point[obj] - ideal_normalized) ** 2 for obj in obj_names) ** 0.5
        distances.append(dist)

    # Return index of point with minimum distance
    return int(np.argmin(distances))


def _create_pareto_mc_output(
    recommended_point: Dict[str, Any],
    objectives: List[Dict[str, Any]],
    objective_values: Dict[str, Dict[str, float]]
) -> Dict[str, Any]:
    """
    Create Monte Carlo compatible output for Pareto optimization.

    Args:
        recommended_point: Recommended solution (knee point)
        objectives: Objective specifications
        objective_values: Value mappings for each objective

    Returns:
        MC compatible output
    """
    allocation = recommended_point["allocation"]
    selected_items = [name for name, qty in allocation.items() if qty > 0]

    # Create assumptions for each objective's values
    assumptions = []
    for objective in objectives:
        obj_name = objective["name"]
        values = objective_values[obj_name]

        for item_name in selected_items:
            if item_name in values:
                value = values[item_name]
                assumptions.append({
                    "name": f"{item_name}_{obj_name}",
                    "value": value,
                    "distribution": {
                        "type": "normal",
                        "params": {
                            "mean": value,
                            "std": value * 0.15  # 15% uncertainty
                        }
                    }
                })

    # Describe outcome (multi-objective weighted sum)
    obj_values_str = ", ".join([
        f"{obj['name']}={recommended_point['objective_values'][obj['name']]:.1f}"
        for obj in objectives
    ])

    outcome_function = (
        f"Multi-objective optimization: {obj_values_str} "
        f"for selected items: {selected_items}"
    )

    return {
        "decision_variables": allocation,
        "selected_items": selected_items,
        "assumptions": assumptions,
        "outcome_function": outcome_function,
        "recommended_next_tool": "validate_reasoning_confidence",
        "recommended_params": {
            "decision_context": "Pareto multi-objective optimization (balanced solution)",
            "assumptions": {
                a["name"]: {
                    "distribution": a["distribution"]["type"],
                    "params": a["distribution"]["params"]
                }
                for a in assumptions
            },
            "success_criteria": {
                "threshold": sum(recommended_point["objective_values"].values()) * 0.9,
                "comparison": ">="
            },
            "num_simulations": 10000
        }
    }
