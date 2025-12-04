"""
PuLP Solver Wrapper

Wrapper for PuLP library providing linear and mixed-integer programming.
Uses CBC solver backend (bundled with PuLP).
"""

import time
from typing import Dict, List, Any, Optional
import pulp as pl

from .base_solver import BaseSolver, OptimizationStatus, ObjectiveSense


class PuLPSolver(BaseSolver):
    """
    PuLP solver wrapper for Linear Programming (LP) and Mixed-Integer Programming (MIP).

    Capabilities:
    - Linear objective functions
    - Linear constraints
    - Continuous, integer, and binary variables
    - Shadow prices (dual values) for constraints
    - Supports problems up to 10,000+ variables
    """

    def __init__(self, problem_name: str = "optimization"):
        """
        Initialize PuLP solver.

        Args:
            problem_name: Name for the optimization problem
        """
        super().__init__(solver_name="pulp")
        self.problem_name = problem_name
        self.problem = None
        self.variables = {}
        self.constraints = {}
        self.constraint_counter = 0

    def create_variables(
        self,
        names: List[str],
        var_type: str = "continuous",
        bounds: Optional[Dict[str, tuple]] = None
    ) -> Dict[str, Any]:
        """
        Create PuLP decision variables.

        Args:
            names: List of variable names
            var_type: "continuous", "integer", or "binary"
            bounds: Dict mapping variable names to (lower, upper) bounds

        Returns:
            Dict mapping variable names to PuLP LpVariable objects
        """
        # Map var_type to PuLP categories
        pulp_cat_map = {
            "continuous": pl.LpContinuous,
            "integer": pl.LpInteger,
            "binary": pl.LpBinary
        }

        if var_type not in pulp_cat_map:
            raise ValueError(
                f"Invalid var_type '{var_type}'. "
                f"Must be one of: {list(pulp_cat_map.keys())}"
            )

        cat = pulp_cat_map[var_type]
        bounds = bounds or {}

        for name in names:
            lb, ub = bounds.get(name, (None, None))
            self.variables[name] = pl.LpVariable(
                name=name,
                lowBound=lb,
                upBound=ub,
                cat=cat
            )

        return self.variables

    def set_objective(
        self,
        expression: Any,
        sense: ObjectiveSense = ObjectiveSense.MINIMIZE
    ):
        """
        Set the objective function.

        Args:
            expression: PuLP linear expression
            sense: MINIMIZE or MAXIMIZE

        Raises:
            ValueError: If problem doesn't exist (call create_variables first)
        """
        # Create problem if it doesn't exist
        pulp_sense = (
            pl.LpMinimize if sense == ObjectiveSense.MINIMIZE else pl.LpMaximize
        )

        self.problem = pl.LpProblem(
            name=self.problem_name,
            sense=pulp_sense
        )

        # Set objective
        self.problem += expression

    def add_constraint(
        self,
        constraint: Any,
        name: Optional[str] = None
    ):
        """
        Add a constraint to the problem.

        Args:
            constraint: PuLP constraint expression (e.g., x + y <= 10)
            name: Optional constraint name

        Raises:
            ValueError: If problem doesn't exist (set objective first)
        """
        if self.problem is None:
            raise ValueError(
                "Problem not initialized. Call set_objective first."
            )

        if name is None:
            name = f"constraint_{self.constraint_counter}"
            self.constraint_counter += 1

        self.problem += constraint, name
        self.constraints[name] = constraint

    def solve(
        self,
        time_limit: Optional[float] = None,
        verbose: bool = False
    ) -> OptimizationStatus:
        """
        Solve the optimization problem using CBC solver.

        Args:
            time_limit: Maximum solving time in seconds
            verbose: Print solver output (0 = silent, 1 = normal)

        Returns:
            Optimization status

        Raises:
            ValueError: If problem not properly set up
        """
        if self.problem is None:
            raise ValueError("Problem not initialized. Set objective first.")

        # Configure solver
        solver_options = []
        if time_limit is not None:
            solver_options.append(f"sec {time_limit}")

        msg = 1 if verbose else 0

        # Solve
        start_time = time.time()
        try:
            status_code = self.problem.solve(
                pl.PULP_CBC_CMD(msg=msg, timeLimit=time_limit)
            )
            self.solve_time = time.time() - start_time

            # Map PuLP status to our standard status
            self.status = self._map_pulp_status(status_code)

            # Store solution if feasible
            if self.is_feasible():
                self.solution = self.get_solution()
                self.objective_value = self.get_objective_value()

            return self.status

        except Exception as e:
            self.solve_time = time.time() - start_time
            self.status = OptimizationStatus.ERROR
            raise RuntimeError(f"Solver error: {str(e)}")

    def _map_pulp_status(self, pulp_status: int) -> OptimizationStatus:
        """
        Map PuLP status codes to standard status.

        Args:
            pulp_status: PuLP status code

        Returns:
            Standard OptimizationStatus
        """
        status_map = {
            pl.LpStatusOptimal: OptimizationStatus.OPTIMAL,
            pl.LpStatusNotSolved: OptimizationStatus.UNKNOWN,
            pl.LpStatusInfeasible: OptimizationStatus.INFEASIBLE,
            pl.LpStatusUnbounded: OptimizationStatus.UNBOUNDED,
            pl.LpStatusUndefined: OptimizationStatus.ERROR
        }

        return status_map.get(pulp_status, OptimizationStatus.UNKNOWN)

    def get_solution(self) -> Dict[str, float]:
        """
        Extract solution values for all variables.

        Returns:
            Dict mapping variable names to optimal values

        Raises:
            ValueError: If no solution available
        """
        if not self.is_feasible():
            raise ValueError(
                f"No solution available. Status: {self.status.value}"
            )

        return {
            name: var.varValue
            for name, var in self.variables.items()
            if var.varValue is not None
        }

    def get_objective_value(self) -> float:
        """
        Get the optimal objective function value.

        Returns:
            Objective value at optimal solution

        Raises:
            ValueError: If no solution available
        """
        if not self.is_feasible():
            raise ValueError(
                f"No solution available. Status: {self.status.value}"
            )

        return pl.value(self.problem.objective)

    def get_shadow_prices(self) -> Dict[str, float]:
        """
        Get shadow prices (dual values) for constraints.

        Shadow price = marginal value of relaxing a constraint by 1 unit.

        Returns:
            Dict mapping constraint names to shadow prices

        Note:
            Only available for LP problems (not MIP)
            Only available for optimal solutions
        """
        if not self.is_optimal():
            return {}

        shadow_prices = {}
        for name, constraint in self.problem.constraints.items():
            pi = constraint.pi
            if pi is not None:
                shadow_prices[name] = pi

        return shadow_prices

    def get_reduced_costs(self) -> Dict[str, float]:
        """
        Get reduced costs for variables.

        Reduced cost = amount objective would improve if variable forced to enter basis.

        Returns:
            Dict mapping variable names to reduced costs

        Note:
            Only available for LP problems (not MIP)
            Only available for optimal solutions
        """
        if not self.is_optimal():
            return {}

        reduced_costs = {}
        for name, var in self.variables.items():
            rc = var.dj
            if rc is not None:
                reduced_costs[name] = rc

        return reduced_costs

    def get_slack_values(self) -> Dict[str, float]:
        """
        Get slack values for constraints.

        Slack = how much constraint is "relaxed" from its bound.

        Returns:
            Dict mapping constraint names to slack values
        """
        if not self.is_feasible():
            return {}

        slack_values = {}
        for name, constraint in self.problem.constraints.items():
            slack = constraint.slack
            if slack is not None:
                slack_values[name] = slack

        return slack_values

    def format_solution(
        self,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format solution with PuLP-specific information.

        Adds shadow prices, reduced costs, and slack values if available.

        Args:
            additional_info: Additional information to include

        Returns:
            Comprehensive solution dictionary
        """
        result = super().format_solution(additional_info)

        if self.is_feasible():
            # Add PuLP-specific info
            result["shadow_prices"] = self.get_shadow_prices()
            result["reduced_costs"] = self.get_reduced_costs()
            result["slack_values"] = self.get_slack_values()

            # Categorize variables by type
            result["variable_types"] = {
                name: self._get_variable_type(var)
                for name, var in self.variables.items()
            }

        return result

    def _get_variable_type(self, var: pl.LpVariable) -> str:
        """Get human-readable variable type"""
        if var.cat == pl.LpContinuous:
            return "continuous"
        elif var.cat == pl.LpInteger:
            return "integer"
        elif var.cat == pl.LpBinary:
            return "binary"
        else:
            return "unknown"

    def reset(self):
        """Reset solver for a new problem"""
        super().reset()
        self.problem = None
        self.variables = {}
        self.constraints = {}
        self.constraint_counter = 0

    def get_problem_info(self) -> Dict[str, Any]:
        """
        Get information about the problem structure.

        Returns:
            Dict with problem statistics
        """
        if self.problem is None:
            return {"error": "No problem defined"}

        num_vars = len(self.variables)
        num_constraints = len(self.constraints)

        var_types = {}
        for var in self.variables.values():
            vtype = self._get_variable_type(var)
            var_types[vtype] = var_types.get(vtype, 0) + 1

        return {
            "problem_name": self.problem_name,
            "num_variables": num_vars,
            "num_constraints": num_constraints,
            "variable_types": var_types,
            "sense": "minimize" if self.problem.sense == pl.LpMinimize else "maximize"
        }
