"""
Resource Allocation Optimization Tool

optimize_allocation: Optimize allocation of limited resources across competing items.

Use cases:
- Marketing budget across channels
- Production capacity across products
- Project selection with resource limits
- Ingredient formulation for beverages/foods
"""

from typing import Dict, List, Any, Optional
import pulp as pl

from ..solvers.pulp_solver import PuLPSolver
from ..solvers.base_solver import ObjectiveSense
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_allocation(
    objective: Dict[str, Any],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    constraints: Optional[List[Dict[str, Any]]] = None,
    monte_carlo_integration: Optional[Dict[str, Any]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Optimize resource allocation across items to maximize/minimize objective.

    Args:
        objective: Dict with:
                  - "items": List of {"name": str, "value": float}
                  - "sense": "maximize" or "minimize"
        resources: Dict of resource limits:
                  - {"budget": {"total": 100000}, "time": {"total": 480}}
        item_requirements: List of resource requirements per item:
                          - [{"name": "project_a", "budget": 25000, "time": 120}, ...]
        constraints: Optional additional constraints:
                    - [{"description": str, "items": [str], "limit": float, "type": "min|max"}, ...]
        monte_carlo_integration: Optional MC integration:
                                - {"mode": "percentile|expected|scenarios",
                                   "percentile": "p50",  # if mode=percentile
                                   "mc_output": {...}}    # MC simulation result
        solver_options: Optional solver settings:
                       - {"time_limit": 300, "verbose": False}

    Returns:
        Dict with:
        - status: "optimal", "infeasible", "unbounded", etc.
        - objective_value: Optimal objective value
        - allocation: Dict of selected quantities per item
        - resource_usage: Dict of resource utilization
        - shadow_prices: Marginal value of each resource
        - monte_carlo_compatible: MC validation-ready output

    Example:
        result = optimize_allocation(
            objective={
                "items": [
                    {"name": "google_ads", "value": 125000},  # Expected return
                    {"name": "linkedin", "value": 87000}
                ],
                "sense": "maximize"
            },
            resources={
                "budget": {"total": 100000}
            },
            item_requirements=[
                {"name": "google_ads", "budget": 25000},
                {"name": "linkedin", "budget": 18000}
            ]
        )
    """
    # Validate inputs
    DataConverter.validate_multi_objective_spec(objective)
    DataConverter.validate_resources_spec(resources)
    DataConverter.validate_item_requirements(item_requirements, resources)

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)

    # Process Monte Carlo integration if provided (single objective only)
    # For multi-objective, values are processed in _process_multi_objective()
    if "functions" not in objective:
        item_values = _process_objective_values(
            objective,
            monte_carlo_integration
        )
    else:
        # Multi-objective: create empty dict, values processed later
        item_values = {}

    # Create solver
    solver = PuLPSolver(problem_name="resource_allocation")

    # Create binary decision variables (select item or not)
    item_names = [item["name"] for item in item_requirements]
    variables = solver.create_variables(
        names=item_names,
        var_type="binary",  # 0 or 1 selection
        bounds=None
    )

    # Build objective function (supports multi-objective)
    obj_expr, objective_breakdown = _process_multi_objective(
        objective,
        variables,
        item_values,
        monte_carlo_integration
    )

    sense = (
        ObjectiveSense.MAXIMIZE if objective["sense"] == "maximize"
        else ObjectiveSense.MINIMIZE
    )
    solver.set_objective(obj_expr, sense)

    # Add resource constraints
    for resource_name, resource_spec in resources.items():
        total_available = resource_spec["total"]

        # Sum of resource usage across selected items <= available
        resource_expr = pl.lpSum([
            item.get(resource_name, 0) * variables[item["name"]]
            for item in item_requirements
        ])

        solver.add_constraint(
            resource_expr <= total_available,
            name=f"resource_{resource_name}"
        )

    # Add custom constraints if provided
    if constraints:
        _add_custom_constraints(solver, variables, constraints)

    # Solve
    try:
        status = solver.solve(time_limit=time_limit, verbose=verbose)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Solver encountered an error during optimization"
        }

    # Build result
    result = _build_allocation_result(
        solver,
        item_names,
        resources,
        item_requirements,
        item_values,
        objective["sense"],
        objective_breakdown
    )

    # Add Monte Carlo compatible output for validation
    if solver.is_feasible():
        mc_output = _create_mc_compatible_output(
            result["allocation"],
            item_values,
            result["objective_value"],
            objective["sense"]
        )
        result["monte_carlo_compatible"] = mc_output

    return result


def _process_objective_values(
    objective: Dict[str, Any],
    mc_integration: Optional[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Process objective values, incorporating Monte Carlo data if provided.

    Args:
        objective: Objective specification
        mc_integration: Optional MC integration settings

    Returns:
        Dict mapping item names to their objective values
    """
    # Start with base values from objective
    item_values = {
        item["name"]: item["value"]
        for item in objective["items"]
    }

    # Override with MC values if integration is specified
    if mc_integration:
        mode = mc_integration.get("mode", "percentile")
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
            # Update item values with MC percentile values
            for name in item_values.keys():
                if name in mc_values:
                    item_values[name] = mc_values[name]

        elif mode == "expected":
            mc_values = MonteCarloIntegration.extract_expected_values(mc_output)
            for name in item_values.keys():
                if name in mc_values:
                    item_values[name] = mc_values[name]

        elif mode == "scenarios":
            # For scenario mode, we just use expected values as base
            # (robust optimization across scenarios is handled by optimize_robust tool)
            mc_values = MonteCarloIntegration.extract_expected_values(mc_output)
            for name in item_values.keys():
                if name in mc_values:
                    item_values[name] = mc_values[name]

    return item_values


def _process_multi_objective(
    objective: Dict[str, Any],
    variables: Dict[str, Any],
    item_values: Dict[str, float],
    monte_carlo_integration: Optional[Dict[str, Any]] = None
) -> tuple[Any, Optional[Dict[str, float]]]:
    """
    Convert multi-objective to weighted single objective expression.

    Args:
        objective: Objective specification (single or multi)
        variables: PuLP decision variables
        item_values: Base item values (for single objective)
        monte_carlo_integration: Optional MC integration

    Returns:
        Tuple of (objective_expression, objective_breakdown_dict)
        - objective_expression: PuLP linear expression
        - objective_breakdown_dict: Dict mapping function names to values (multi-obj only)
    """
    if "functions" not in objective:
        # Single objective - use existing item_values
        obj_expr = pl.lpSum([
            item_values[name] * variables[name]
            for name in variables.keys()
        ])
        return obj_expr, None

    # Multi-objective: weighted scalarization
    weighted_expr = 0
    objective_breakdown = {}

    for func in objective["functions"]:
        func_name = func["name"]
        weight = func["weight"]

        # Get item values for this function
        func_item_values = {}
        for item in func["items"]:
            func_item_values[item["name"]] = item["value"]

        # Override with MC values if provided
        if monte_carlo_integration:
            mode = monte_carlo_integration.get("mode", "percentile")
            mc_output = monte_carlo_integration.get("mc_output")

            if mc_output is not None:
                if mode == "percentile":
                    percentile = monte_carlo_integration.get("percentile", "p50")
                    mc_values = MonteCarloIntegration.extract_percentile_values(
                        mc_output,
                        percentile
                    )
                    for name in func_item_values.keys():
                        if name in mc_values:
                            func_item_values[name] = mc_values[name]

                elif mode == "expected":
                    mc_values = MonteCarloIntegration.extract_expected_values(mc_output)
                    for name in func_item_values.keys():
                        if name in mc_values:
                            func_item_values[name] = mc_values[name]

        # Build expression for this function
        func_expr = pl.lpSum([
            func_item_values.get(name, 0) * variables[name]
            for name in variables.keys()
            if name in func_item_values
        ])

        # Add to weighted sum
        weighted_expr += weight * func_expr

        # Store for breakdown (will be calculated after solve)
        objective_breakdown[func_name] = {
            "weight": weight,
            "item_values": func_item_values
        }

    return weighted_expr, objective_breakdown


def _add_custom_constraints(
    solver: PuLPSolver,
    variables: Dict[str, Any],
    constraints: List[Dict[str, Any]]
):
    """
    Add custom user-defined constraints.

    Supports constraint types:
    - min/max: Basic linear constraints
    - conditional: If-then logic (if A selected, then B must be selected)
    - disjunctive: OR logic (at least N of M items must be selected)
    - mutex: Mutual exclusivity (exactly N items selected)

    Args:
        solver: PuLP solver instance
        variables: Decision variables
        constraints: List of constraint specifications
    """
    for i, constraint in enumerate(constraints):
        constraint_type = constraint.get("type", "max")
        description = constraint.get("description", f"constraint_{i}")

        if constraint_type == "max" or constraint_type == "min":
            # Linear constraint: sum(items) <= or >= limit
            items = constraint.get("items", [])
            limit = constraint.get("limit", 0)

            expr = pl.lpSum([variables[item] for item in items if item in variables])

            if constraint_type == "max":
                solver.add_constraint(
                    expr <= limit,
                    name=f"custom_{description}_{i}"
                )
            else:  # min
                solver.add_constraint(
                    expr >= limit,
                    name=f"custom_{description}_{i}"
                )

        elif constraint_type == "conditional":
            # If-then logic: if condition_item selected, then then_item must be selected
            # Formulation: x_then >= x_condition
            condition_item = constraint.get("condition_item")
            then_item = constraint.get("then_item")

            if condition_item not in variables:
                raise ValueError(
                    f"Conditional constraint: condition_item '{condition_item}' not in variables"
                )
            if then_item not in variables:
                raise ValueError(
                    f"Conditional constraint: then_item '{then_item}' not in variables"
                )

            solver.add_constraint(
                variables[then_item] >= variables[condition_item],
                name=f"conditional_{description}_{i}"
            )

        elif constraint_type == "disjunctive":
            # OR logic: at least min_selected of items must be selected
            # Formulation: sum(x_i) >= min_selected
            items = constraint.get("items", [])
            min_selected = constraint.get("min_selected", 1)

            if not items:
                raise ValueError("Disjunctive constraint requires 'items' list")

            expr = pl.lpSum([variables[item] for item in items if item in variables])
            solver.add_constraint(
                expr >= min_selected,
                name=f"disjunctive_{description}_{i}"
            )

        elif constraint_type == "mutex":
            # Mutual exclusivity: exactly N items must be selected
            # Formulation: sum(x_i) = exactly
            items = constraint.get("items", [])
            exactly = constraint.get("exactly", 1)

            if not items:
                raise ValueError("Mutex constraint requires 'items' list")

            expr = pl.lpSum([variables[item] for item in items if item in variables])
            solver.add_constraint(
                expr == exactly,
                name=f"mutex_{description}_{i}"
            )

        else:
            raise ValueError(
                f"Invalid constraint type '{constraint_type}'. "
                f"Must be one of: 'min', 'max', 'conditional', 'disjunctive', 'mutex'"
            )


def _build_allocation_result(
    solver: PuLPSolver,
    item_names: List[str],
    resources: Dict[str, Dict[str, float]],
    item_requirements: List[Dict[str, Any]],
    item_values: Dict[str, float],
    objective_sense: str,
    objective_breakdown: Optional[Dict[str, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Build comprehensive result dictionary.

    Args:
        solver: Solved PuLP solver
        item_names: List of item names
        resources: Resource specifications
        item_requirements: Item requirements
        item_values: Item objective values
        objective_sense: "maximize" or "minimize"
        objective_breakdown: Multi-objective breakdown info (if multi-objective)

    Returns:
        Result dictionary
    """
    result = {
        "solver": "pulp",
        "status": solver.status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if not solver.is_feasible():
        result["message"] = _generate_infeasibility_message(
            solver.status.value,
            resources,
            item_requirements
        )
        return result

    # Get solution
    solution = solver.get_solution()
    result["objective_value"] = solver.get_objective_value()

    # Format allocation (which items were selected)
    allocation = {
        name: int(solution[name])  # Binary variables: 0 or 1
        for name in item_names
    }
    result["allocation"] = allocation

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
    result["resource_usage"] = resource_usage

    # Add shadow prices (marginal value of resources)
    shadow_prices = solver.get_shadow_prices()
    result["shadow_prices"] = {
        name.replace("resource_", ""): price
        for name, price in shadow_prices.items()
        if name.startswith("resource_")
    }

    # Add selected items summary (for single objective)
    # For multi-objective, this info is in objective_breakdown
    if len(item_values) > 0:
        selected_items = [
            {
                "name": name,
                "value": item_values.get(name, 0),
                "selected": allocation[name] == 1
            }
            for name in item_names
        ]
        result["items"] = selected_items

    # Add multi-objective breakdown if applicable
    if objective_breakdown is not None:
        breakdown_values = {}
        for func_name, func_info in objective_breakdown.items():
            # Calculate value for this function given the allocation
            func_value = sum(
                func_info["item_values"].get(name, 0) * allocation[name]
                for name in item_names
            )
            breakdown_values[func_name] = {
                "value": func_value,
                "weight": func_info["weight"],
                "weighted_value": func_value * func_info["weight"]
            }
        result["objective_breakdown"] = breakdown_values

    return result


def _generate_infeasibility_message(
    status: str,
    resources: Dict[str, Any],
    item_requirements: List[Dict[str, Any]]
) -> str:
    """
    Generate helpful error message for infeasible/unbounded problems.

    Args:
        status: Solver status
        resources: Resource specifications
        item_requirements: Item requirements

    Returns:
        Helpful error message
    """
    if status == "infeasible":
        # Check if any single item exceeds resources
        infeasible_items = []
        for item in item_requirements:
            for resource_name, amount in item.items():
                if resource_name == "name":
                    continue
                if resource_name in resources:
                    if amount > resources[resource_name]["total"]:
                        infeasible_items.append(
                            f"Item '{item['name']}' requires {amount} {resource_name} "
                            f"but only {resources[resource_name]['total']} available"
                        )

        if infeasible_items:
            return (
                "Problem is infeasible. Some items require more resources than available:\n"
                + "\n".join(f"  - {msg}" for msg in infeasible_items)
            )
        else:
            return "Problem is infeasible. No feasible solution exists given the constraints."

    elif status == "unbounded":
        return (
            "Problem is unbounded. The objective can be improved infinitely. "
            "Check that all variables have appropriate bounds."
        )
    else:
        return f"Optimization failed with status: {status}"


def _create_mc_compatible_output(
    allocation: Dict[str, int],
    item_values: Dict[str, float],
    objective_value: float,
    objective_sense: str
) -> Dict[str, Any]:
    """
    Create Monte Carlo compatible output for validation.

    Args:
        allocation: Item allocation (0 or 1 for each item)
        item_values: Value/return for each item
        objective_value: Optimal objective value
        objective_sense: "maximize" or "minimize"

    Returns:
        MC compatible output dict
    """
    # Identify selected items
    selected_items = [name for name, selected in allocation.items() if selected == 1]

    # Create assumptions (treat item values as uncertain)
    assumptions = []
    for name, value in item_values.items():
        assumptions.append({
            "name": f"{name}_value",
            "value": value,
            "distribution": {
                "type": "normal",
                "params": {
                    "mean": value,
                    "std": value * 0.15  # Assume 15% standard deviation
                }
            }
        })

    # Create outcome function description
    outcome_function = (
        f"sum([{', '.join(f'{name}_value' for name in selected_items)}]) "
        f"for selected items: {selected_items}"
    )

    return {
        "decision_variables": allocation,
        "selected_items": selected_items,
        "assumptions": assumptions,
        "outcome_function": outcome_function,
        "recommended_next_tool": "validate_reasoning_confidence",
        "recommended_params": {
            "decision_context": f"Resource allocation optimizing {objective_sense} with {len(selected_items)} items selected",
            "assumptions": {
                a["name"]: {
                    "distribution": a["distribution"]["type"],
                    "params": a["distribution"]["params"]
                }
                for a in assumptions
            },
            "success_criteria": {
                "threshold": objective_value * 0.9,  # 90% of optimal
                "comparison": ">=" if objective_sense == "maximize" else "<="
            },
            "num_simulations": 10000
        }
    }
