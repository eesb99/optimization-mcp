"""
NetworkX Solver Implementation

Specialized solver for network flow problems using NetworkX graph algorithms.
Provides 10-100x speedup for pure network flow problems compared to general LP solvers.

Supported problem types:
- Min-cost flow (supply chain, distribution)
- Max-flow (throughput, capacity)
- Assignment problems
- Shortest path routing
"""

import time
from typing import Dict, List, Any, Optional, Tuple
import networkx as nx

from .base_solver import BaseSolver, OptimizationStatus, ObjectiveSense


class NetworkXSolver(BaseSolver):
    """
    Network flow solver using NetworkX graph algorithms.

    10-100x faster than general LP for pure network problems with:
    - Pure flow conservation constraints
    - Integer capacities/demands
    - <5000 edges

    Automatically selects optimal algorithm based on problem type:
    - nx.min_cost_flow() for capacitated min-cost flow
    - nx.maximum_flow() for max-flow problems
    - nx.shortest_path() for uncapacitated routing
    """

    def __init__(self):
        super().__init__(solver_name="networkx")
        self.graph: Optional[nx.DiGraph] = None
        self.problem_type: Optional[str] = None  # 'min_cost_flow', 'max_flow', 'shortest_path'
        self.node_demands: Dict[str, float] = {}
        self.solution_flows: Dict[Tuple[str, str], float] = {}
        self.edge_names: Dict[Tuple[str, str], str] = {}  # Map (u,v) -> variable name
        self.objective_sense: ObjectiveSense = ObjectiveSense.MINIMIZE

    def create_variables(
        self,
        names: List[str],
        var_type: str = "continuous",
        bounds: Optional[Dict[str, tuple]] = None
    ) -> Dict[str, Any]:
        """
        Create network flow variables as edges in a directed graph.

        Variable names should encode edge structure, or provide edge info via bounds dict.
        Expected formats:
        - "flow_A_B" or "route_A_B" → edge from A to B
        - Or provide edge_info in bounds: {'edge_A_B': ('A', 'B', capacity, cost)}

        Args:
            names: List of edge flow variable names
            var_type: Should be "continuous" for network flow
            bounds: Dict with (lower_bound, upper_bound) for each variable,
                   or extended format with edge metadata

        Returns:
            Dict mapping variable names to edge tuples
        """
        if var_type != "continuous":
            raise ValueError(
                f"NetworkXSolver only supports continuous variables for flows. "
                f"Got var_type='{var_type}'"
            )

        # Initialize graph
        self.graph = nx.DiGraph()
        bounds = bounds or {}

        variables = {}
        for name in names:
            # Try to extract edge endpoints from variable name
            # Format: "flow_A_B" or "route_X_Y" etc.
            parts = name.replace("flow_", "").replace("route_", "").split("_")

            if len(parts) >= 2:
                # Standard naming convention
                from_node = parts[0]
                to_node = "_".join(parts[1:])  # Handle multi-word node names
            else:
                raise ValueError(
                    f"Cannot parse edge from variable name '{name}'. "
                    f"Expected format: 'flow_A_B' or provide edge_info in bounds"
                )

            # Get capacity from bounds (upper bound)
            capacity = float('inf')
            cost = 0.0

            if name in bounds:
                bound_info = bounds[name]
                if isinstance(bound_info, tuple) and len(bound_info) == 2:
                    lower, upper = bound_info
                    capacity = upper if upper is not None else float('inf')
                elif isinstance(bound_info, dict):
                    # Extended format with metadata
                    capacity = bound_info.get('capacity', float('inf'))
                    cost = bound_info.get('cost', 0.0)

            # Add edge to graph
            self.graph.add_edge(
                from_node,
                to_node,
                capacity=capacity,
                weight=cost,  # NetworkX uses 'weight' for edge costs
                var_name=name
            )

            # Store mapping
            edge_tuple = (from_node, to_node)
            variables[name] = edge_tuple
            self.edge_names[edge_tuple] = name

        return variables

    def set_objective(
        self,
        expression: Any,
        sense: ObjectiveSense = ObjectiveSense.MINIMIZE
    ):
        """
        Set objective and determine problem type.

        Args:
            expression: Dict with 'type' key indicating problem type:
                       - 'min_cost': minimize total cost
                       - 'max_flow': maximize total flow
                       Or dict with edge costs: {edge_name: cost}
            sense: MINIMIZE or MAXIMIZE
        """
        self.objective_sense = sense

        if isinstance(expression, dict):
            if 'type' in expression:
                # Explicit problem type specification
                problem_type = expression['type']
                if problem_type in ['min_cost', 'min_cost_flow']:
                    self.problem_type = 'min_cost_flow'
                elif problem_type in ['max_flow', 'maximum_flow']:
                    self.problem_type = 'max_flow'
                elif problem_type in ['shortest_path']:
                    self.problem_type = 'shortest_path'
                else:
                    raise ValueError(f"Unknown problem type: {problem_type}")
            else:
                # Assume it's a cost dictionary
                # Update edge weights with provided costs
                for var_name, cost in expression.items():
                    # Find edge for this variable
                    for u, v, data in self.graph.edges(data=True):
                        if data.get('var_name') == var_name:
                            self.graph[u][v]['weight'] = cost
                            break

                # Infer problem type from sense
                if sense == ObjectiveSense.MINIMIZE:
                    self.problem_type = 'min_cost_flow'
                else:
                    self.problem_type = 'max_flow'
        else:
            # Default to min cost flow
            self.problem_type = 'min_cost_flow'

    def add_constraint(
        self,
        constraint: Any,
        name: Optional[str] = None
    ):
        """
        Add flow conservation constraint (node balance).

        Args:
            constraint: Dict with node balance information:
                       {'node': 'A', 'demand': 50} or {'node': 'A', 'supply': -50}
                       Positive demand = consumption, Negative demand/supply = production
            name: Optional constraint name (not used, for interface compatibility)
        """
        if isinstance(constraint, dict):
            node = constraint.get('node')
            demand = constraint.get('demand', 0.0)
            supply = constraint.get('supply', 0.0)

            if node is None:
                raise ValueError("Constraint must specify 'node' field")

            # Store net demand (demand - supply)
            # Negative demand = net supply
            net_demand = demand - supply
            self.node_demands[node] = net_demand

            # Ensure node exists in graph
            if node not in self.graph.nodes():
                self.graph.add_node(node)
        else:
            raise TypeError(
                f"NetworkXSolver expects constraint as dict with node balance info. "
                f"Got: {type(constraint)}"
            )

    def solve(
        self,
        time_limit: Optional[float] = None,
        verbose: bool = False
    ) -> OptimizationStatus:
        """
        Solve network flow problem using appropriate NetworkX algorithm.

        Args:
            time_limit: Maximum solving time in seconds (not enforced by NetworkX)
            verbose: Print solver output

        Returns:
            Optimization status
        """
        start_time = time.time()

        try:
            if self.graph is None or self.graph.number_of_edges() == 0:
                self.status = OptimizationStatus.ERROR
                raise ValueError("No graph defined. Call create_variables first.")

            if verbose:
                print(f"NetworkX Solver: {self.problem_type}")
                print(f"  Nodes: {self.graph.number_of_nodes()}")
                print(f"  Edges: {self.graph.number_of_edges()}")

            # Solve based on problem type
            if self.problem_type == 'min_cost_flow':
                self._solve_min_cost_flow(verbose)

            elif self.problem_type == 'max_flow':
                self._solve_max_flow(verbose)

            elif self.problem_type == 'shortest_path':
                self._solve_shortest_path(verbose)

            else:
                raise ValueError(f"Unknown problem type: {self.problem_type}")

            self.solve_time = time.time() - start_time

            if verbose:
                print(f"  Status: {self.status.value}")
                print(f"  Solve time: {self.solve_time:.3f}s")

            return self.status

        except nx.NetworkXUnfeasible:
            self.status = OptimizationStatus.INFEASIBLE
            self.solve_time = time.time() - start_time
            return self.status

        except nx.NetworkXError as e:
            if 'unbounded' in str(e).lower():
                self.status = OptimizationStatus.UNBOUNDED
            else:
                self.status = OptimizationStatus.ERROR
            self.solve_time = time.time() - start_time
            return self.status

        except Exception as e:
            self.status = OptimizationStatus.ERROR
            self.solve_time = time.time() - start_time
            if verbose:
                print(f"  Error: {str(e)}")
            return self.status

    def _solve_min_cost_flow(self, verbose: bool = False):
        """Solve minimum cost flow problem using network simplex."""
        # NetworkX expects integer demands and uses 'demand' attribute on nodes
        # Negative demand = supply
        demand_dict = {}
        for node in self.graph.nodes():
            demand_dict[node] = -int(self.node_demands.get(node, 0))  # Flip sign for NetworkX

        if verbose:
            print(f"  Demand balance: {sum(demand_dict.values())}")

        # Check if problem is balanced
        total_demand = sum(demand_dict.values())
        if abs(total_demand) > 1e-6:
            raise nx.NetworkXUnfeasible(
                f"Flow conservation violated: total demand = {total_demand} != 0"
            )

        # Solve min-cost flow
        flow_dict = nx.min_cost_flow(self.graph, demand=demand_dict, weight='weight')

        # Calculate objective value
        total_cost = sum(
            flow_dict[u][v] * self.graph[u][v]['weight']
            for u in flow_dict
            for v in flow_dict[u]
            if flow_dict[u][v] > 0
        )

        # Store solution
        self.solution_flows = {
            (u, v): flow_dict[u][v]
            for u in flow_dict
            for v in flow_dict[u]
        }
        self.objective_value = total_cost
        self.status = OptimizationStatus.OPTIMAL

    def _solve_max_flow(self, verbose: bool = False):
        """Solve maximum flow problem using Edmonds-Karp or Dinic algorithm."""
        # Identify source (supply) and sink (demand) nodes
        sources = [node for node, demand in self.node_demands.items() if demand < 0]
        sinks = [node for node, demand in self.node_demands.items() if demand > 0]

        if len(sources) == 0 or len(sinks) == 0:
            raise nx.NetworkXError("Max flow requires at least one source and one sink")

        if len(sources) > 1 or len(sinks) > 1:
            # Multi-source/sink: add super source and sink
            super_source = "__super_source__"
            super_sink = "__super_sink__"

            # Create temporary graph with super nodes
            G = self.graph.copy()
            for source in sources:
                supply = -self.node_demands[source]
                G.add_edge(super_source, source, capacity=supply)
            for sink in sinks:
                demand = self.node_demands[sink]
                G.add_edge(sink, super_sink, capacity=demand)

            source_node = super_source
            sink_node = super_sink
        else:
            G = self.graph
            source_node = sources[0]
            sink_node = sinks[0]

        # Solve max flow
        flow_value, flow_dict = nx.maximum_flow(G, source_node, sink_node, capacity='capacity')

        # Store solution (exclude super nodes if added)
        self.solution_flows = {
            (u, v): flow_dict[u][v]
            for u in flow_dict
            for v in flow_dict[u]
            if u not in ['__super_source__', '__super_sink__']
            and v not in ['__super_source__', '__super_sink__']
        }
        self.objective_value = flow_value
        self.status = OptimizationStatus.OPTIMAL

    def _solve_shortest_path(self, verbose: bool = False):
        """Solve shortest path problem using Dijkstra or Bellman-Ford."""
        # Identify source and target
        sources = [node for node, demand in self.node_demands.items() if demand < 0]
        targets = [node for node, demand in self.node_demands.items() if demand > 0]

        if len(sources) != 1 or len(targets) != 1:
            raise nx.NetworkXError(
                "Shortest path requires exactly one source and one target"
            )

        source = sources[0]
        target = targets[0]

        # Solve shortest path
        try:
            path = nx.shortest_path(
                self.graph,
                source=source,
                target=target,
                weight='weight'
            )
            path_cost = nx.shortest_path_length(
                self.graph,
                source=source,
                target=target,
                weight='weight'
            )
        except nx.NetworkXNoPath:
            raise nx.NetworkXUnfeasible(f"No path from {source} to {target}")

        # Convert path to flows
        self.solution_flows = {}
        flow_amount = abs(self.node_demands[source])

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            self.solution_flows[(u, v)] = flow_amount

        self.objective_value = path_cost
        self.status = OptimizationStatus.OPTIMAL

    def get_solution(self) -> Dict[str, float]:
        """
        Extract solution as variable name -> flow value mapping.

        Returns:
            Dict mapping variable names to flow values
        """
        if not self.is_feasible():
            raise ValueError("No feasible solution available")

        solution = {}
        for (u, v), flow in self.solution_flows.items():
            var_name = self.edge_names.get((u, v), f"flow_{u}_{v}")
            solution[var_name] = flow

        return solution

    def get_objective_value(self) -> float:
        """
        Get optimal objective value (total cost or total flow).

        Returns:
            Objective value at optimal solution
        """
        if not self.is_feasible():
            raise ValueError("No feasible solution available")

        return self.objective_value

    def get_bottlenecks(self, tolerance: float = 0.01) -> List[Dict[str, Any]]:
        """
        Identify bottleneck edges (at or near capacity).

        Args:
            tolerance: Utilization threshold (default: 99% capacity)

        Returns:
            List of bottleneck edge information
        """
        if not self.is_feasible():
            return []

        bottlenecks = []
        for (u, v), flow in self.solution_flows.items():
            if flow > 0:
                capacity = self.graph[u][v].get('capacity', float('inf'))
                if capacity < float('inf'):
                    utilization = flow / capacity
                    if utilization >= (1.0 - tolerance):
                        bottlenecks.append({
                            'edge': self.edge_names.get((u, v), f"{u}->{v}"),
                            'from': u,
                            'to': v,
                            'capacity': capacity,
                            'flow': flow,
                            'utilization': utilization
                        })

        return sorted(bottlenecks, key=lambda x: x['utilization'], reverse=True)

    def get_node_balance(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate flow balance at each node.

        Returns:
            Dict with node -> {inflow, outflow, net} information
        """
        if not self.is_feasible():
            return {}

        balance = {}
        for node in self.graph.nodes():
            inflow = sum(
                self.solution_flows.get((u, node), 0)
                for u in self.graph.predecessors(node)
            )
            outflow = sum(
                self.solution_flows.get((node, v), 0)
                for v in self.graph.successors(node)
            )
            balance[node] = {
                'inflow': inflow,
                'outflow': outflow,
                'net': inflow - outflow
            }

        return balance
