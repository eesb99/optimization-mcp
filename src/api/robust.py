"""
Robust Optimization Tool

optimize_robust: Find robust solutions that perform well across multiple scenarios.

Optimizes allocation considering uncertainty by testing across Monte Carlo scenarios.
"""

from typing import Dict, List, Any, Optional
import pulp as pl
import numpy as np

from ..solvers.pulp_solver import PuLPSolver
from ..solvers.base_solver import ObjectiveSense
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_robust(
    objective: Dict[str, Any],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    monte_carlo_scenarios: Dict[str, Any],
    robustness_criterion: str = "best_average",
    risk_tolerance: float = 0.85,
    constraints: Optional[List[Dict[str, Any]]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Find robust allocation that performs well across Monte Carlo scenarios.

    Instead of optimizing for a single expected value, this finds solutions
    that work well in 85%+ of scenarios (configurable via risk_tolerance).

    Args:
        objective: Dict with:
                  - "items": List of {"name": str}
                  - "sense": "maximize" or "minimize"
        resources: Resource limits (same as optimize_allocation)
        item_requirements: Item requirements (same as optimize_allocation)
        monte_carlo_scenarios: Dict with:
                              - "scenarios": List of scenario dicts from MC output
                                Each scenario has item values
        robustness_criterion: How to aggregate across scenarios:
                             - "best_average": Maximize expected value
                             - "worst_case": Optimize for worst scenario
                             - "percentile": Optimize for Pth percentile
        risk_tolerance: For percentile criterion, optimize for this percentile
                       (e.g., 0.85 = solution works in 85% of scenarios)
        constraints: Optional additional constraints
        solver_options: Optional solver settings

    Returns:
        Dict with:
        - allocation: Robust allocation decision
        - robustness_metrics: Performance across scenarios
        - outcome_distribution: List of outcomes for each scenario
        - monte_carlo_compatible: MC validation-ready output

    Example:
        # After running Monte Carlo simulation
        mc_result = run_business_scenario(...)

        # Find robust allocation
        result = optimize_robust(
            objective={
                "items": [{"name": "project_a"}, {"name": "project_b"}],
                "sense": "maximize"
            },
            resources={"budget": {"total": 100000}},
            item_requirements=[...],
            monte_carlo_scenarios={
                "scenarios": mc_result["scenarios"]  # All 10K scenarios
            },
            robustness_criterion="best_average",
            risk_tolerance=0.85
        )
    """
    # Validate inputs
    # Note: require_values=False because robust optimization gets values from scenarios, not objective
    DataConverter.validate_objective_spec({
        "items": objective.get("items", []),
        "sense": objective.get("sense", "maximize")
    }, require_values=False)
    DataConverter.validate_resources_spec(resources)

    # Extract scenarios
    scenarios = monte_carlo_scenarios.get("scenarios")
    if scenarios is None:
        raise ValueError(
            "monte_carlo_scenarios must include 'scenarios' field with MC output"
        )

    if len(scenarios) == 0:
        raise ValueError("No scenarios provided")

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)

    # Item names
    item_names = [item["name"] for item in objective["items"]]

    # Try different candidate allocations and evaluate robustness
    # Strategy: Sample multiple allocations, evaluate each across scenarios
    candidate_allocations = _generate_candidate_allocations(
        item_names,
        resources,
        item_requirements,
        constraints,
        time_limit,
        verbose
    )

    # Evaluate each candidate across all scenarios
    best_allocation = None
    best_score = float('-inf') if objective["sense"] == "maximize" else float('inf')
    best_outcomes = None

    for allocation in candidate_allocations:
        # Evaluate this allocation across all scenarios
        outcomes = _evaluate_allocation_across_scenarios(
            allocation,
            item_names,
            scenarios,
            objective["sense"]
        )

        # Score based on robustness criterion
        score = _calculate_robustness_score(
            outcomes,
            robustness_criterion,
            risk_tolerance,
            objective["sense"]
        )

        # Update best if this is better
        is_better = (
            score > best_score if objective["sense"] == "maximize"
            else score < best_score
        )

        if is_better:
            best_score = score
            best_allocation = allocation
            best_outcomes = outcomes

    # Build result
    result = _build_robust_result(
        best_allocation,
        best_outcomes,
        item_names,
        resources,
        item_requirements,
        objective["sense"],
        robustness_criterion,
        risk_tolerance
    )

    # Add MC compatible output
    if best_allocation:
        mc_output = _create_mc_compatible_output_robust(
            best_allocation,
            best_outcomes,
            objective["sense"]
        )
        result["monte_carlo_compatible"] = mc_output

    return result


def _generate_candidate_allocations(
    item_names: List[str],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    constraints: Optional[List[Dict[str, Any]]],
    time_limit: Optional[float],
    verbose: bool
) -> List[Dict[str, int]]:
    """
    Generate candidate allocations to test for robustness.

    Strategy: Use PuLP to find several good allocations with different
    objective functions (best case, worst case, random).

    Args:
        item_names: List of item names
        resources: Resource specifications
        item_requirements: Item requirements
        constraints: Optional constraints
        time_limit: Solver time limit
        verbose: Verbose output

    Returns:
        List of candidate allocations (each is a dict of item -> 0/1)
    """
    candidates = []

    # Candidate 1: Optimize assuming all items have equal value
    allocation = _solve_allocation_problem(
        item_names,
        {name: 1.0 for name in item_names},
        resources,
        item_requirements,
        constraints,
        "maximize",
        time_limit,
        verbose
    )
    if allocation:
        candidates.append(allocation)

    # Candidate 2: Optimize for maximum resource utilization
    allocation = _solve_allocation_problem(
        item_names,
        {name: sum(item.get(res, 0) for res in resources.keys())
         for name, item in zip(item_names, item_requirements)},
        resources,
        item_requirements,
        constraints,
        "maximize",
        time_limit,
        verbose
    )
    if allocation:
        candidates.append(allocation)

    # Candidate 3-5: Try optimizing with random objective weights
    for _ in range(3):
        random_values = {name: np.random.uniform(0.5, 1.5) for name in item_names}
        allocation = _solve_allocation_problem(
            item_names,
            random_values,
            resources,
            item_requirements,
            constraints,
            "maximize",
            time_limit,
            verbose
        )
        if allocation and allocation not in candidates:
            candidates.append(allocation)

    return candidates


def _solve_allocation_problem(
    item_names: List[str],
    item_values: Dict[str, float],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    constraints: Optional[List[Dict[str, Any]]],
    sense: str,
    time_limit: Optional[float],
    verbose: bool
) -> Optional[Dict[str, int]]:
    """
    Solve a single allocation problem.

    Args:
        item_names: Item names
        item_values: Objective values for each item
        resources: Resource limits
        item_requirements: Item requirements
        constraints: Optional constraints
        sense: "maximize" or "minimize"
        time_limit: Solver time limit
        verbose: Verbose output

    Returns:
        Allocation dict or None if infeasible
    """
    solver = PuLPSolver(problem_name="candidate_allocation")

    # Create variables
    variables = solver.create_variables(
        names=item_names,
        var_type="binary"
    )

    # Objective
    obj_expr = pl.lpSum([
        item_values[name] * variables[name]
        for name in item_names
    ])
    objective_sense = (
        ObjectiveSense.MAXIMIZE if sense == "maximize"
        else ObjectiveSense.MINIMIZE
    )
    solver.set_objective(obj_expr, objective_sense)

    # Resource constraints
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

    # Additional constraints
    if constraints:
        for i, constraint in enumerate(constraints):
            items = constraint.get("items", [])
            limit = constraint.get("limit", 0)
            constraint_type = constraint.get("type", "max")

            expr = pl.lpSum([variables[item] for item in items if item in variables])

            if constraint_type == "max":
                solver.add_constraint(expr <= limit, name=f"constraint_{i}")
            elif constraint_type == "min":
                solver.add_constraint(expr >= limit, name=f"constraint_{i}")

    # Solve
    try:
        status = solver.solve(time_limit=time_limit, verbose=False)
        if solver.is_feasible():
            solution = solver.get_solution()
            return {name: int(solution[name]) for name in item_names}
    except:
        pass

    return None


def _evaluate_allocation_across_scenarios(
    allocation: Dict[str, int],
    item_names: List[str],
    scenarios: List[Dict[str, float]],
    objective_sense: str
) -> List[float]:
    """
    Evaluate allocation performance across all scenarios.

    Args:
        allocation: Allocation decision (item -> 0/1)
        item_names: List of item names
        scenarios: List of scenario dicts with item values
        objective_sense: "maximize" or "minimize"

    Returns:
        List of outcomes (one per scenario)
    """
    outcomes = []

    for scenario in scenarios:
        # Calculate outcome for this allocation in this scenario
        # Extract values from scenario (supports both {name: value} and {"values": {name: value}} formats)
        scenario_values = scenario.get("values", scenario)
        outcome = sum(
            allocation.get(name, 0) * scenario_values.get(name, 0)
            for name in item_names
        )
        outcomes.append(outcome)

    return outcomes


def _calculate_robustness_score(
    outcomes: List[float],
    criterion: str,
    risk_tolerance: float,
    objective_sense: str
) -> float:
    """
    Calculate robustness score for an allocation.

    Args:
        outcomes: List of outcomes across scenarios
        criterion: Robustness criterion
        risk_tolerance: Risk tolerance for percentile criterion
        objective_sense: "maximize" or "minimize"

    Returns:
        Robustness score
    """
    if criterion == "best_average":
        return np.mean(outcomes)

    elif criterion == "worst_case":
        return min(outcomes) if objective_sense == "maximize" else max(outcomes)

    elif criterion == "percentile":
        # For maximize: use risk_tolerance percentile (conservative)
        # For minimize: use (1 - risk_tolerance) percentile
        percentile = risk_tolerance * 100 if objective_sense == "maximize" else (1 - risk_tolerance) * 100
        return np.percentile(outcomes, percentile)

    else:
        raise ValueError(
            f"Invalid robustness criterion '{criterion}'. "
            f"Must be: best_average, worst_case, percentile"
        )


def _build_robust_result(
    allocation: Dict[str, int],
    outcomes: List[float],
    item_names: List[str],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    objective_sense: str,
    robustness_criterion: str,
    risk_tolerance: float
) -> Dict[str, Any]:
    """
    Build comprehensive robust optimization result.

    Args:
        allocation: Best robust allocation
        outcomes: Outcomes across scenarios
        item_names: Item names
        resources: Resource specifications
        item_requirements: Item requirements
        objective_sense: "maximize" or "minimize"
        robustness_criterion: Robustness criterion used
        risk_tolerance: Risk tolerance

    Returns:
        Result dictionary
    """
    # Calculate resource usage
    resource_usage = {}
    for resource_name in resources.keys():
        used = sum(
            item.get(resource_name, 0) * allocation[item["name"]]
            for item in item_requirements
        )
        total = resources[resource_name]["total"]
        resource_usage[resource_name] = {
            "used": used,
            "available": total,
            "remaining": total - used,
            "utilization_pct": (used / total * 100) if total > 0 else 0
        }

    # Calculate robustness metrics
    expected_outcome = np.mean(outcomes)
    worst_case = min(outcomes) if objective_sense == "maximize" else max(outcomes)
    best_case = max(outcomes) if objective_sense == "maximize" else min(outcomes)

    # Calculate percentage of scenarios meeting threshold
    threshold = expected_outcome * 0.9  # 90% of expected
    if objective_sense == "maximize":
        scenarios_meeting_threshold = sum(1 for o in outcomes if o >= threshold) / len(outcomes)
    else:
        scenarios_meeting_threshold = sum(1 for o in outcomes if o <= threshold) / len(outcomes)

    return {
        "status": "optimal",
        "allocation": allocation,
        "selected_items": [name for name, val in allocation.items() if val == 1],
        "resource_usage": resource_usage,
        "robustness_metrics": {
            "criterion_used": robustness_criterion,
            "risk_tolerance": risk_tolerance,
            "expected_outcome": expected_outcome,
            "worst_case_outcome": worst_case,
            "best_case_outcome": best_case,
            "scenarios_meeting_threshold": scenarios_meeting_threshold,
            "outcome_std_dev": np.std(outcomes),
            "outcome_percentiles": {
                "p10": np.percentile(outcomes, 10),
                "p25": np.percentile(outcomes, 25),
                "p50": np.percentile(outcomes, 50),
                "p75": np.percentile(outcomes, 75),
                "p90": np.percentile(outcomes, 90)
            }
        },
        "outcome_distribution": outcomes,
        "num_scenarios_evaluated": len(outcomes)
    }


def _create_mc_compatible_output_robust(
    allocation: Dict[str, int],
    outcomes: List[float],
    objective_sense: str
) -> Dict[str, Any]:
    """
    Create MC compatible output for robust optimization.

    Args:
        allocation: Robust allocation
        outcomes: Outcomes across scenarios
        objective_sense: "maximize" or "minimize"

    Returns:
        MC compatible output
    """
    selected_items = [name for name, val in allocation.items() if val == 1]

    return {
        "decision_variables": allocation,
        "selected_items": selected_items,
        "outcome_distribution": outcomes,
        "expected_outcome": np.mean(outcomes),
        "recommended_next_tool": "run_sensitivity_analysis",
        "recommended_params": {
            "base_simulation_id": "robust_optimization",
            "variables_to_test": selected_items,
            "outcome_data": {
                "outcomes": outcomes,
                "expected": np.mean(outcomes)
            }
        }
    }
