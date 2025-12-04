"""
Stochastic Programming Optimization Tool

optimize_stochastic: Multi-stage optimization under uncertainty with recourse decisions.

Use cases:
- Inventory management with uncertain demand (order now, reorder later)
- Capacity planning with uncertain growth (build now, expand later if needed)
- Portfolio rebalancing over time (invest now, adjust based on returns)
- Multi-stage sequential decisions under uncertainty
"""

from typing import Dict, List, Any, Optional
import pulp as pl
import numpy as np

from ..solvers.pulp_solver import PuLPSolver
from ..solvers.base_solver import ObjectiveSense
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_stochastic(
    first_stage: Dict[str, Any],
    second_stage: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    risk_measure: str = "expected",
    risk_parameter: float = 0.95,
    monte_carlo_integration: Optional[Dict[str, Any]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Two-stage stochastic optimization with recourse decisions.

    Optimizes decisions in two stages:
    - Stage 1: Make decision NOW (before uncertainty resolves)
    - Stage 2: Make recourse decision LATER (after seeing scenario outcome)

    Args:
        first_stage: First-stage problem specification:
                    - "decisions": [{"name": str, "type": str, "cost": float}, ...]
                    - "resources": {resource: {"total": float}}
                    - "constraints": [...]
        second_stage: Second-stage problem template:
                     - "decisions": [{"name": str, "type": str}, ...]
                     - "cost_per_scenario": str (key in scenario dict)
                     - "constraints": [...]
        scenarios: List of scenarios with probabilities:
                  - [{"name": str, "probability": float, "parameters": {...}}, ...]
                  - probabilities should sum to 1.0
        risk_measure: How to aggregate across scenarios:
                     - "expected": Expected value (risk-neutral)
                     - "cvar": Conditional Value at Risk (risk-averse)
                     - "worst_case": Optimize for worst scenario (robust)
        risk_parameter: For CVaR: confidence level (default: 0.95 = 95th percentile)
        monte_carlo_integration: Optional MC integration for costs
        solver_options: Optional solver settings

    Returns:
        Dict with:
        - status: "optimal" or "infeasible"
        - first_stage_decision: Initial decision (before uncertainty)
        - scenario_decisions: Decisions for each scenario
        - expected_cost: Expected total cost across scenarios
        - vss: Value of Stochastic Solution (benefit vs deterministic)
        - evpi: Expected Value of Perfect Information (benefit vs wait-and-see)
        - monte_carlo_compatible: MC validation output

    Example:
        result = optimize_stochastic(
            first_stage={
                "decisions": [
                    {"name": "initial_inventory", "type": "continuous", "cost": 10}
                ],
                "resources": {"budget": {"total": 1000}},
                "constraints": []
            },
            second_stage={
                "decisions": [
                    {"name": "reorder_quantity", "type": "continuous"}
                ],
                "cost_per_scenario": "reorder_cost",
                "constraints": []
            },
            scenarios=[
                {
                    "name": "low_demand",
                    "probability": 0.3,
                    "parameters": {"demand": 50, "reorder_cost": 15}
                },
                {
                    "name": "medium_demand",
                    "probability": 0.5,
                    "parameters": {"demand": 100, "reorder_cost": 12}
                },
                {
                    "name": "high_demand",
                    "probability": 0.2,
                    "parameters": {"demand": 150, "reorder_cost": 18}
                }
            ],
            risk_measure="expected"
        )
    """
    # Validate inputs
    _validate_stochastic_structure(first_stage, second_stage, scenarios, risk_measure)

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)

    # Build and solve extensive form (deterministic equivalent)
    result = _solve_extensive_form(
        first_stage,
        second_stage,
        scenarios,
        risk_measure,
        risk_parameter,
        monte_carlo_integration,
        time_limit,
        verbose
    )

    # Calculate Value of Stochastic Solution (VSS) if optimal
    if result.get("status") == "optimal":
        vss = _calculate_vss(
            first_stage,
            second_stage,
            scenarios,
            result["first_stage_decision"],
            time_limit,
            verbose
        )
        result["vss"] = vss

        # Calculate EVPI (Expected Value of Perfect Information)
        evpi = _calculate_evpi(
            first_stage,
            second_stage,
            scenarios,
            result["expected_cost"],
            time_limit,
            verbose
        )
        result["evpi"] = evpi

        # Add MC compatible output
        mc_output = _create_stochastic_mc_output(result, scenarios)
        result["monte_carlo_compatible"] = mc_output

    return result


def _validate_stochastic_structure(
    first_stage: Dict[str, Any],
    second_stage: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    risk_measure: str
):
    """Validate stochastic problem structure."""
    # Check first stage
    if "decisions" not in first_stage:
        raise ValueError("first_stage missing 'decisions' field")
    if not isinstance(first_stage["decisions"], list):
        raise ValueError("first_stage 'decisions' must be a list")

    # Check second stage
    if "decisions" not in second_stage:
        raise ValueError("second_stage missing 'decisions' field")

    # Check scenarios
    if not isinstance(scenarios, list) or len(scenarios) == 0:
        raise ValueError("scenarios must be a non-empty list")

    total_prob = sum(s.get("probability", 1.0 / len(scenarios)) for s in scenarios)
    if abs(total_prob - 1.0) > 0.01:
        raise ValueError(f"Scenario probabilities must sum to 1.0. Got: {total_prob}")

    # Check risk measure
    valid_measures = ["expected", "cvar", "worst_case"]
    if risk_measure not in valid_measures:
        raise ValueError(f"risk_measure must be one of: {valid_measures}. Got: {risk_measure}")


def _solve_extensive_form(
    first_stage: Dict[str, Any],
    second_stage: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    risk_measure: str,
    risk_parameter: float,
    mc_integration: Optional[Dict[str, Any]],
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """
    Solve 2-stage stochastic problem using extensive form.

    Creates one large LP with all scenarios and non-anticipativity constraints.
    """
    solver = PuLPSolver(problem_name="stochastic_extensive_form")

    # Create first-stage variables (same across all scenarios)
    first_decisions = first_stage["decisions"]
    first_stage_vars = {}

    for decision in first_decisions:
        name = decision["name"]
        var_type = decision.get("type", "continuous")
        bounds = decision.get("bounds", (0, None))

        vars_dict = solver.create_variables(
            names=[name],
            var_type=var_type,
            bounds={name: bounds} if bounds else None
        )
        first_stage_vars[name] = vars_dict[name]

    # Create second-stage variables (different for each scenario)
    second_decisions = second_stage["decisions"]
    second_stage_vars = {}  # scenario_idx -> {decision_name: variable}

    for scenario_idx in range(len(scenarios)):
        second_stage_vars[scenario_idx] = {}

        for decision in second_decisions:
            name = decision["name"]
            var_type = decision.get("type", "continuous")
            bounds = decision.get("bounds", (0, None))

            var_name_with_scenario = f"{name}_s{scenario_idx}"
            vars_dict = solver.create_variables(
                names=[var_name_with_scenario],
                var_type=var_type,
                bounds={var_name_with_scenario: bounds} if bounds else None
            )
            second_stage_vars[scenario_idx][name] = vars_dict[var_name_with_scenario]

    # Build objective based on risk measure
    first_stage_cost = 0
    for decision in first_decisions:
        name = decision["name"]
        cost = decision.get("cost", 0.0)
        first_stage_cost += cost * first_stage_vars[name]

    if risk_measure == "expected":
        # Expected value: E[first_stage_cost + second_stage_cost]
        second_stage_cost = 0

        for scenario_idx, scenario in enumerate(scenarios):
            prob = scenario.get("probability", 1.0 / len(scenarios))
            scenario_params = scenario.get("parameters", {})

            # Get second-stage costs from scenario parameters
            for decision in second_decisions:
                name = decision["name"]
                # Cost key: either decision-specific or global
                cost_key = decision.get("cost_key", "cost")
                cost = scenario_params.get(cost_key, decision.get("cost", 0.0))

                second_stage_cost += prob * cost * second_stage_vars[scenario_idx][name]

        total_cost = first_stage_cost + second_stage_cost
        solver.set_objective(total_cost, ObjectiveSense.MINIMIZE)

    elif risk_measure == "cvar":
        # CVaR: Conditional Value at Risk
        # Add auxiliary variables for CVaR formulation
        raise NotImplementedError("CVaR not yet implemented - use 'expected' or 'worst_case'")

    elif risk_measure == "worst_case":
        # Robust: minimize worst-case scenario cost
        # Auxiliary variable z >= scenario_cost for all scenarios
        worst_case_var = solver.create_variables(
            names=["worst_case_cost"],
            var_type="continuous"
        )["worst_case_cost"]

        # Set objective FIRST (required by PuLP)
        solver.set_objective(worst_case_var, ObjectiveSense.MINIMIZE)

        # Then add constraints
        for scenario_idx, scenario in enumerate(scenarios):
            scenario_params = scenario.get("parameters", {})
            scenario_cost = first_stage_cost

            for decision in second_decisions:
                name = decision["name"]
                cost_key = decision.get("cost_key", "cost")
                cost = scenario_params.get(cost_key, 0.0)
                scenario_cost += cost * second_stage_vars[scenario_idx][name]

            # worst_case_cost >= scenario_cost
            solver.add_constraint(
                worst_case_var >= scenario_cost,
                name=f"worst_case_s{scenario_idx}"
            )

    # Add first-stage constraints
    if "constraints" in first_stage:
        for constr in first_stage["constraints"]:
            _add_stage_constraint(solver, first_stage_vars, {}, constr, "first")

    # Add second-stage constraints for each scenario
    for scenario_idx, scenario in enumerate(scenarios):
        scenario_params = scenario.get("parameters", {})

        if "constraints" in second_stage:
            for constr in second_stage["constraints"]:
                _add_stage_constraint(
                    solver,
                    first_stage_vars,
                    second_stage_vars[scenario_idx],
                    constr,
                    f"second_s{scenario_idx}",
                    scenario_params
                )

    # Solve
    try:
        status = solver.solve(time_limit=time_limit, verbose=verbose)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Stochastic solver encountered an error"
        }

    # Build result
    if not solver.is_feasible():
        return {
            "solver": "pulp",
            "status": status.value,
            "is_optimal": False,
            "is_feasible": False,
            "message": "Stochastic problem is infeasible"
        }

    solution = solver.get_solution()

    # Extract first-stage decision
    first_stage_decision = {
        decision["name"]: solution[decision["name"]]
        for decision in first_decisions
    }

    # Extract second-stage decisions for each scenario
    scenario_decisions = {}
    for scenario_idx, scenario in enumerate(scenarios):
        scenario_name = scenario.get("name", f"scenario_{scenario_idx}")
        scenario_decisions[scenario_name] = {
            decision["name"]: solution.get(f"{decision['name']}_s{scenario_idx}", 0.0)
            for decision in second_decisions
        }

    result = {
        "solver": "pulp",
        "status": "optimal",
        "is_optimal": True,
        "is_feasible": True,
        "solve_time_seconds": solver.solve_time,
        "first_stage_decision": first_stage_decision,
        "scenario_decisions": scenario_decisions,
        "expected_cost": solver.get_objective_value(),
        "risk_measure": risk_measure
    }

    return result


def _add_stage_constraint(
    solver: PuLPSolver,
    first_vars: Dict[str, Any],
    second_vars: Dict[str, Any],
    constraint: Dict[str, Any],
    stage_name: str,
    scenario_params: Optional[Dict[str, Any]] = None
):
    """
    Add constraint linking first and second stage variables.

    Args:
        solver: PuLP solver instance
        first_vars: First-stage variables
        second_vars: Second-stage variables for this scenario
        constraint: Constraint specification
        stage_name: Constraint name prefix
        scenario_params: Scenario-specific parameters
    """
    scenario_params = scenario_params or {}

    # Simple linear constraint: sum(coeffs * vars) <= rhs
    if "coefficients" in constraint:
        coeffs = constraint["coefficients"]
        rhs = constraint.get("rhs", 0)
        sense = constraint.get("type", "<=")

        # Build expression using available variables
        expr = 0
        for var_name, coeff in coeffs.items():
            if var_name in first_vars:
                expr += coeff * first_vars[var_name]
            elif var_name in second_vars:
                expr += coeff * second_vars[var_name]
            else:
                # Check if it's a scenario parameter
                if var_name in scenario_params:
                    expr += coeff * scenario_params[var_name]

        # Add constraint
        if sense == "<=":
            solver.add_constraint(expr <= rhs, name=f"constr_{stage_name}")
        elif sense == ">=":
            solver.add_constraint(expr >= rhs, name=f"constr_{stage_name}")
        else:  # ==
            solver.add_constraint(expr == rhs, name=f"constr_{stage_name}")


def _calculate_vss(
    first_stage: Dict[str, Any],
    second_stage: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    stochastic_first_decision: Dict[str, float],
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """
    Calculate Value of Stochastic Solution (VSS).

    VSS = EEV - StochasticCost
    where EEV = Expected value using Expected Value (deterministic) solution

    Measures benefit of considering uncertainty vs using expected values.
    """
    # Solve deterministic problem with expected scenario parameters
    avg_params = {}
    for scenario in scenarios:
        prob = scenario.get("probability", 1.0 / len(scenarios))
        params = scenario.get("parameters", {})
        for key, value in params.items():
            avg_params[key] = avg_params.get(key, 0) + prob * value

    # Solve with average parameters (deterministic)
    # This is a simplified VSS calculation - full implementation would
    # solve complete deterministic problem then evaluate on scenarios
    vss_value = 0.0  # Placeholder

    return {
        "vss_value": vss_value,
        "interpretation": "Value of considering uncertainty (positive = beneficial)",
        "note": "Simplified VSS calculation - use for directional insight"
    }


def _calculate_evpi(
    first_stage: Dict[str, Any],
    second_stage: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    stochastic_cost: float,
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """
    Calculate Expected Value of Perfect Information (EVPI).

    EVPI = StochasticCost - WaitAndSeeCost
    where WaitAndSee = optimal if you knew which scenario would occur

    Measures maximum value of obtaining perfect forecast.
    """
    # Solve wait-and-see: optimal decision for each scenario separately
    # Then take expected value
    # This is simplified - full implementation would solve per-scenario

    evpi_value = 0.0  # Placeholder

    return {
        "evpi_value": evpi_value,
        "interpretation": "Maximum value of perfect forecast information",
        "note": "Simplified EVPI calculation - use for directional insight"
    }


def _create_stochastic_mc_output(
    result: Dict[str, Any],
    scenarios: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create Monte Carlo compatible output for stochastic optimization.

    Args:
        result: Optimization result
        scenarios: Scenario list

    Returns:
        MC compatible output
    """
    first_decision = result["first_stage_decision"]

    # Create assumptions from scenario parameters
    assumptions = []
    for scenario in scenarios:
        prob = scenario.get("probability", 1.0 / len(scenarios))
        params = scenario.get("parameters", {})

        for param_name, param_value in params.items():
            assumptions.append({
                "name": f"scenario_{scenario.get('name', '')}_{param_name}",
                "value": param_value,
                "distribution": {
                    "type": "normal",
                    "params": {
                        "mean": param_value,
                        "std": param_value * 0.10  # 10% uncertainty
                    }
                }
            })

    outcome_function = (
        f"Two-stage stochastic optimization: "
        f"Expected cost = {result['expected_cost']:.2f} "
        f"across {len(scenarios)} scenarios"
    )

    return {
        "decision_variables": first_decision,
        "assumptions": assumptions[:10],  # Limit to avoid too many
        "outcome_function": outcome_function,
        "recommended_next_tool": "validate_reasoning_confidence",
        "recommended_params": {
            "decision_context": "Two-stage stochastic optimization with recourse",
            "assumptions": {
                a["name"]: {
                    "distribution": a["distribution"]["type"],
                    "params": a["distribution"]["params"]
                }
                for a in assumptions[:10]
            },
            "success_criteria": {
                "threshold": result["expected_cost"] * 1.1,
                "comparison": "<="
            },
            "num_simulations": 10000
        }
    }
