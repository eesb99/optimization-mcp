"""
Network Flow Optimization Tool

optimize_network_flow: Optimize network flow problems using specialized algorithms.

Use cases:
- Supply chain routing (min-cost flow)
- Transportation logistics
- Assignment problems (workers to tasks)
- Maximum throughput/capacity problems
"""

from typing import Dict, List, Any, Optional
import time

from ..solvers.networkx_solver import NetworkXSolver
from ..solvers.pulp_solver import PuLPSolver
from ..solvers.base_solver import ObjectiveSense, OptimizationStatus
from ..integration.monte_carlo import MonteCarloIntegration
from ..integration.data_converters import DataConverter


def optimize_network_flow(
    network: Dict[str, Any],
    flow_type: str = "min_cost",
    constraints: Optional[List[Dict[str, Any]]] = None,
    monte_carlo_integration: Optional[Dict[str, Any]] = None,
    solver_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Optimize network flow problems: min-cost flow, max-flow, assignment.

    Uses specialized NetworkX algorithms (10-100x faster than general LP) for
    pure network flow problems, with automatic fallback to PuLP for complex cases.

    Args:
        network: Network specification with:
                - "nodes": List of [{"id": str, "supply": float, "demand": float}, ...]
                          (supply/demand optional, default 0)
                - "edges": List of [{"from": str, "to": str, "capacity": float, "cost": float, "name": str}, ...]
                          (capacity, cost, name optional)
        flow_type: Problem type:
                  - "min_cost": Minimize total cost of flow
                  - "max_flow": Maximize total flow
                  - "assignment": Assignment problem (bipartite matching)
        constraints: Optional additional constraints (triggers PuLP fallback):
                    - [{"type": str, ...}, ...]
        monte_carlo_integration: Optional MC integration:
                                - {"mode": "percentile|expected|scenarios",
                                   "percentile": "p50",  # if mode=percentile
                                   "mc_output": {...}}    # MC simulation result
        solver_options: Optional solver settings:
                       - {"time_limit": 300, "verbose": False, "solver": "networkx|pulp"}

    Returns:
        Dict with:
        - status: "optimal", "infeasible", "error"
        - solver: "networkx" or "pulp"
        - solve_time_seconds: Execution time
        - flow_solution: Dict of {edge_name: flow_amount}
        - total_cost: Total cost (for min_cost)
        - total_flow: Total flow (for max_flow)
        - bottlenecks: List of edges at capacity
        - node_balance: Flow balance at each node
        - monte_carlo_compatible: MC validation-ready output

    Example:
        result = optimize_network_flow(
            network={
                "nodes": [
                    {"id": "warehouse_A", "supply": 100},
                    {"id": "customer_1", "demand": 40},
                    {"id": "customer_2", "demand": 60}
                ],
                "edges": [
                    {"from": "warehouse_A", "to": "customer_1", "capacity": 50, "cost": 5.0},
                    {"from": "warehouse_A", "to": "customer_2", "capacity": 80, "cost": 3.0}
                ]
            },
            flow_type="min_cost"
        )
    """
    # Validate inputs
    DataConverter.validate_network_structure(network)

    if flow_type not in ["min_cost", "max_flow", "assignment"]:
        raise ValueError(
            f"Invalid flow_type: '{flow_type}'. "
            f"Must be one of: 'min_cost', 'max_flow', 'assignment'"
        )

    # Extract solver options
    solver_opts = solver_options or {}
    time_limit = solver_opts.get("time_limit", None)
    verbose = solver_opts.get("verbose", False)
    solver_preference = solver_opts.get("solver", None)  # "networkx" or "pulp"

    # Process Monte Carlo integration (extract values from MC output)
    costs_data = network.get("edges", [])
    if monte_carlo_integration:
        costs_data = _process_mc_integration(
            network,
            monte_carlo_integration,
            verbose
        )

    # Check if we should use NetworkX or PuLP
    use_networkx = _should_use_networkx(network, constraints, solver_preference, verbose)

    if use_networkx:
        result = _solve_with_networkx(
            network,
            costs_data,
            flow_type,
            time_limit,
            verbose
        )
    else:
        result = _solve_with_pulp_fallback(
            network,
            costs_data,
            flow_type,
            time_limit,
            verbose
        )

    # Add Monte Carlo compatible output
    if result.get("is_feasible", False):
        mc_output = _create_mc_compatible_output(
            result,
            flow_type,
            network
        )
        result["monte_carlo_compatible"] = mc_output

    return result


def _should_use_networkx(
    network: Dict[str, Any],
    constraints: Optional[List[Dict[str, Any]]],
    solver_preference: Optional[str],
    verbose: bool = False
) -> bool:
    """
    Determine whether to use NetworkX or fall back to PuLP.

    NetworkX is preferred when:
    - No side constraints beyond flow conservation
    - Pure network structure
    - No solver preference for PuLP

    Args:
        network: Network specification
        constraints: Additional constraints
        solver_preference: User's solver preference
        verbose: Print decision reasoning

    Returns:
        True if NetworkX should be used, False for PuLP fallback
    """
    # Explicit solver preference
    if solver_preference == "pulp":
        if verbose:
            print("Using PuLP solver (user preference)")
        return False
    if solver_preference == "networkx":
        if verbose:
            print("Using NetworkX solver (user preference)")
        return True

    # Check for side constraints (require PuLP)
    if constraints and len(constraints) > 0:
        if verbose:
            print("Using PuLP solver (side constraints present)")
        return False

    # Check network size (NetworkX best for <5000 edges)
    num_edges = len(network.get("edges", []))
    if num_edges > 5000:
        if verbose:
            print(f"Using PuLP solver (large network: {num_edges} edges)")
        return False

    # Default: use NetworkX for pure network flow
    if verbose:
        print("Using NetworkX solver (pure network flow)")
    return True


def _process_mc_integration(
    network: Dict[str, Any],
    mc_integration: Dict[str, Any],
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Process Monte Carlo integration to extract edge costs from MC output.

    Args:
        network: Original network specification
        mc_integration: MC integration settings
        verbose: Print processing info

    Returns:
        Updated edge list with costs from MC output
    """
    mode = mc_integration.get("mode", "percentile")
    mc_output = mc_integration.get("mc_output", {})

    edges = network.get("edges", [])[:]  # Copy

    if mode == "percentile":
        percentile = mc_integration.get("percentile", "p50")
        costs = MonteCarloIntegration.extract_percentile_values(
            mc_output,
            percentile=percentile
        )
        if verbose:
            print(f"Using MC {percentile} cost values")

    elif mode == "expected":
        costs = MonteCarloIntegration.extract_expected_values(mc_output)
        if verbose:
            print("Using MC expected cost values")

    elif mode == "scenarios":
        # For scenarios mode, use expected values as default
        costs = MonteCarloIntegration.extract_expected_values(mc_output)
        if verbose:
            print("Using MC expected values from scenarios")

    else:
        raise ValueError(f"Unknown MC integration mode: '{mode}'")

    # Update edge costs with MC values
    for edge in edges:
        edge_name = edge.get("name", f"flow_{edge['from']}_{edge['to']}")
        if edge_name in costs:
            edge["cost"] = costs[edge_name]

    return edges


def _solve_with_networkx(
    network: Dict[str, Any],
    costs_data: List[Dict[str, Any]],
    flow_type: str,
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """
    Solve network flow problem using NetworkX algorithms.

    Args:
        network: Network specification
        costs_data: Edge list (possibly updated with MC costs)
        flow_type: "min_cost", "max_flow", or "assignment"
        time_limit: Solver time limit
        verbose: Print solver output

    Returns:
        Result dictionary
    """
    solver = NetworkXSolver()

    # Create variables (edges)
    edges = costs_data if costs_data else network.get("edges", [])
    edge_names = []
    edge_bounds = {}

    for edge in edges:
        from_node = edge["from"]
        to_node = edge["to"]
        capacity = edge.get("capacity", None)
        cost = edge.get("cost", 0.0)
        name = edge.get("name", f"flow_{from_node}_{to_node}")

        edge_names.append(name)
        edge_bounds[name] = {
            'from': from_node,  # Explicit edge endpoints
            'to': to_node,
            'capacity': capacity if capacity is not None else float('inf'),
            'cost': cost
        }

    solver.create_variables(
        names=edge_names,
        var_type="continuous",
        bounds=edge_bounds
    )

    # Set objective
    solver.set_objective(
        expression={'type': flow_type},
        sense=ObjectiveSense.MINIMIZE if flow_type != "max_flow" else ObjectiveSense.MAXIMIZE
    )

    # Add node balance constraints
    for node in network.get("nodes", []):
        node_id = node["id"]
        supply = node.get("supply", 0.0)
        demand = node.get("demand", 0.0)

        solver.add_constraint({
            'node': node_id,
            'supply': supply,
            'demand': demand
        })

    # Solve
    status = solver.solve(time_limit=time_limit, verbose=verbose)

    # Build result
    result = {
        "solver": "networkx",
        "status": status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if solver.is_feasible():
        solution = solver.get_solution()
        objective_value = solver.get_objective_value()

        result["flow_solution"] = solution

        if flow_type in ["min_cost", "assignment"]:
            result["total_cost"] = objective_value
        elif flow_type == "max_flow":
            result["total_flow"] = objective_value
        else:
            # Fallback
            result["objective_value"] = objective_value

        # Add bottleneck analysis
        bottlenecks = solver.get_bottlenecks(tolerance=0.01)
        result["bottlenecks"] = bottlenecks

        # Add node balance
        node_balance = solver.get_node_balance()
        result["node_balance"] = node_balance

    else:
        # Infeasible/error case
        result["message"] = _generate_network_infeasibility_message(
            status.value,
            network
        )

    return result


def _solve_with_pulp_fallback(
    network: Dict[str, Any],
    costs_data: List[Dict[str, Any]],
    flow_type: str,
    time_limit: Optional[float],
    verbose: bool
) -> Dict[str, Any]:
    """
    Solve network flow using PuLP as general LP.

    Used when problem has side constraints or other features
    not supported by pure network flow algorithms.

    Args:
        network: Network specification
        costs_data: Edge list
        flow_type: Problem type
        time_limit: Solver time limit
        verbose: Print solver output

    Returns:
        Result dictionary
    """
    import pulp as pl

    solver = PuLPSolver(problem_name=f"network_flow_{flow_type}")

    # Create variables for edge flows
    edges = costs_data if costs_data else network.get("edges", [])
    edge_vars = {}

    for edge in edges:
        from_node = edge["from"]
        to_node = edge["to"]
        capacity = edge.get("capacity", None)
        name = edge.get("name", f"flow_{from_node}_{to_node}")

        upper_bound = capacity if capacity is not None else None
        edge_vars[name] = (0, upper_bound)

    variables = solver.create_variables(
        names=list(edge_vars.keys()),
        var_type="continuous",
        bounds=edge_vars
    )

    # Set objective
    if flow_type == "min_cost":
        # Minimize total cost
        coefficients = {
            edge.get("name", f"flow_{edge['from']}_{edge['to']}"): edge.get("cost", 0.0)
            for edge in edges
        }
        obj_expr = pl.lpSum([
            coefficients[name] * variables[name]
            for name in variables
        ])
        solver.set_objective(obj_expr, ObjectiveSense.MINIMIZE)

    elif flow_type == "max_flow":
        # Maximize total flow from sources
        # Find source nodes (supply > 0)
        sources = [node for node in network.get("nodes", []) if node.get("supply", 0) > 0]
        source_ids = {node["id"] for node in sources}

        # Sum of outflow from sources
        flow_expr = pl.lpSum([
            variables[name]
            for edge in edges
            if edge["from"] in source_ids
            for name in [edge.get("name", f"flow_{edge['from']}_{edge['to']}")]
            if name in variables
        ])
        solver.set_objective(flow_expr, ObjectiveSense.MAXIMIZE)

    # Add flow conservation constraints
    nodes = network.get("nodes", [])
    for node in nodes:
        node_id = node["id"]
        supply = node.get("supply", 0.0)
        demand = node.get("demand", 0.0)

        # Inflow
        inflow = pl.lpSum([
            variables[edge.get("name", f"flow_{edge['from']}_{edge['to']}")]
            for edge in edges
            if edge["to"] == node_id
            and edge.get("name", f"flow_{edge['from']}_{edge['to']}") in variables
        ])

        # Outflow
        outflow = pl.lpSum([
            variables[edge.get("name", f"flow_{edge['from']}_{edge['to']}")]
            for edge in edges
            if edge["from"] == node_id
            and edge.get("name", f"flow_{edge['from']}_{edge['to']}") in variables
        ])

        # Flow conservation: inflow - outflow = demand - supply
        net_demand = demand - supply
        solver.add_constraint(
            inflow - outflow == net_demand,
            name=f"flow_conservation_{node_id}"
        )

    # Solve
    status = solver.solve(time_limit=time_limit, verbose=verbose)

    # Build result
    result = {
        "solver": "pulp",
        "status": status.value,
        "is_optimal": solver.is_optimal(),
        "is_feasible": solver.is_feasible(),
        "solve_time_seconds": solver.solve_time
    }

    if solver.is_feasible():
        solution = solver.get_solution()
        objective_value = solver.get_objective_value()

        result["flow_solution"] = solution

        if flow_type in ["min_cost", "assignment"]:
            result["total_cost"] = objective_value
        elif flow_type == "max_flow":
            result["total_flow"] = objective_value
        else:
            # Fallback
            result["objective_value"] = objective_value

        # Calculate bottlenecks
        bottlenecks = []
        for edge in edges:
            name = edge.get("name", f"flow_{edge['from']}_{edge['to']}")
            if name in solution:
                flow = solution[name]
                capacity = edge.get("capacity")
                if capacity is not None and flow > 0:
                    utilization = flow / capacity
                    if utilization >= 0.99:
                        bottlenecks.append({
                            'edge': name,
                            'from': edge['from'],
                            'to': edge['to'],
                            'capacity': capacity,
                            'flow': flow,
                            'utilization': utilization
                        })
        result["bottlenecks"] = sorted(bottlenecks, key=lambda x: x['utilization'], reverse=True)

        # Calculate node balance
        node_balance = {}
        for node in nodes:
            node_id = node["id"]
            inflow = sum(
                solution.get(edge.get("name", f"flow_{edge['from']}_{edge['to']}"), 0)
                for edge in edges
                if edge["to"] == node_id
            )
            outflow = sum(
                solution.get(edge.get("name", f"flow_{edge['from']}_{edge['to']}"), 0)
                for edge in edges
                if edge["from"] == node_id
            )
            node_balance[node_id] = {
                'inflow': inflow,
                'outflow': outflow,
                'net': inflow - outflow
            }
        result["node_balance"] = node_balance

    else:
        result["message"] = _generate_network_infeasibility_message(
            status.value,
            network
        )

    return result


def _generate_network_infeasibility_message(
    status: str,
    network: Dict[str, Any]
) -> str:
    """Generate helpful infeasibility message."""
    if status == "infeasible":
        total_supply = sum(node.get("supply", 0) for node in network.get("nodes", []))
        total_demand = sum(node.get("demand", 0) for node in network.get("nodes", []))

        return (
            f"Network flow problem is infeasible. "
            f"Total supply: {total_supply}, Total demand: {total_demand}. "
            f"Check: (1) Supply equals demand, (2) Network connectivity, "
            f"(3) Edge capacities sufficient."
        )
    elif status == "unbounded":
        return "Network flow problem is unbounded (infinite cost reduction possible)."
    else:
        return f"Solver error: {status}"


def _create_mc_compatible_output(
    result: Dict[str, Any],
    flow_type: str,
    network: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create Monte Carlo compatible output for validation.

    Args:
        result: Optimization result
        flow_type: Problem type
        network: Original network

    Returns:
        MC compatible output dictionary
    """
    flow_solution = result.get("flow_solution", {})

    # Create uncertainty assumptions (treat costs as uncertain)
    assumptions = []
    edges = network.get("edges", [])

    for edge in edges:
        edge_name = edge.get("name", f"flow_{edge['from']}_{edge['to']}")
        cost = edge.get("cost", 0.0)

        if cost > 0:  # Only include edges with costs
            assumptions.append({
                "name": f"{edge_name}_cost",
                "value": cost,
                "distribution": {
                    "type": "normal",
                    "params": {
                        "mean": cost,
                        "std": cost * 0.10  # 10% standard deviation
                    }
                }
            })

    # Describe outcome function
    total_cost = result.get("total_cost", result.get("total_flow", 0))

    outcome_function = (
        f"Total {'cost' if flow_type == 'min_cost' else 'flow'}: "
        f"{total_cost:.2f} based on network flow optimization"
    )

    return {
        "decision_variables": flow_solution,
        "assumptions": assumptions,
        "outcome_function": outcome_function,
        "recommended_next_tool": "validate_reasoning_confidence",
        "recommended_params": {
            "decision_context": f"Network flow optimization ({flow_type})",
            "assumptions": {
                a["name"]: {
                    "distribution": a["distribution"]["type"],
                    "params": a["distribution"]["params"]
                }
                for a in assumptions
            },
            "success_criteria": {
                "threshold": total_cost * (0.9 if flow_type == "min_cost" else 1.1),
                "comparison": "<=" if flow_type == "min_cost" else ">="
            },
            "num_simulations": 10000
        }
    }
