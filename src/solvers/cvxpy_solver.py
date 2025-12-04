"""
CVXPY Solver Wrapper

Wrapper for CVXPY library providing convex optimization (LP, QP, SOCP).
"""

import time
from typing import Dict, List, Any, Optional
import numpy as np

try:
    import cvxpy as cp
except ImportError:
    cp = None

from .base_solver import BaseSolver, OptimizationStatus, ObjectiveSense


class CVXPYSolver(BaseSolver):
    """
    CVXPY solver wrapper for convex optimization (LP, QP, SOCP).

    Capabilities:
    - Linear and quadratic objectives
    - Quadratic constraints
    - Convex optimization problems
    - Scale: 100-5000 variables

    Use cases:
    - Portfolio optimization (quadratic variance)
    - Least squares problems
    - Convex regression
    """

    def __init__(self, problem_type: str = "LP"):
        """
        Initialize CVXPY solver.

        Args:
            problem_type: Type of problem ("LP", "QP", "SOCP")
        """
        if cp is None:
            raise ImportError(
                "CVXPY not installed. Install with: pip install cvxpy"
            )

        super().__init__(solver_name="cvxpy")
        self.problem_type = problem_type
        self.cvxpy_variables = {}
        self.cvxpy_constraints = []
        self.cvxpy_objective = None
        self.cvxpy_problem = None

    def create_variables(
        self,
        names: List[str],
        var_type: str = "continuous",
        bounds: Optional[Dict[str, tuple]] = None
    ) -> Dict[str, Any]:
        """
        Create CVXPY decision variables.

        Args:
            names: List of variable names
            var_type: "continuous", "integer", or "binary"
            bounds: Dict mapping variable names to (lower, upper) bounds

        Returns:
            Dict mapping variable names to CVXPY Variable objects
        """
        bounds = bounds or {}

        for name in names:
            # Create variable based on type
            if var_type == "continuous":
                var = cp.Variable(name=name)
            elif var_type == "binary":
                var = cp.Variable(name=name, boolean=True)
            elif var_type == "integer":
                var = cp.Variable(name=name, integer=True)
            else:
                raise ValueError(
                    f"Invalid var_type '{var_type}'. "
                    f"Must be 'continuous', 'integer', or 'binary'"
                )

            self.cvxpy_variables[name] = var

            # Add bounds as constraints
            if name in bounds:
                lb, ub = bounds[name]
                if lb is not None:
                    self.cvxpy_constraints.append(var >= lb)
                if ub is not None:
                    self.cvxpy_constraints.append(var <= ub)

        return self.cvxpy_variables

    def set_objective(
        self,
        expression: Any,
        sense: ObjectiveSense = ObjectiveSense.MINIMIZE
    ):
        """
        Set the objective function.

        Args:
            expression: CVXPY expression
            sense: MINIMIZE or MAXIMIZE

        Raises:
            ValueError: If expression is invalid
        """
        if sense == ObjectiveSense.MINIMIZE:
            self.cvxpy_objective = cp.Minimize(expression)
        elif sense == ObjectiveSense.MAXIMIZE:
            self.cvxpy_objective = cp.Maximize(expression)
        else:
            raise ValueError(f"Invalid sense: {sense}")

    def add_constraint(
        self,
        constraint: Any,
        name: Optional[str] = None
    ):
        """
        Add a constraint to the problem.

        Args:
            constraint: CVXPY constraint expression
            name: Optional constraint name (for reference)

        Note:
            CVXPY doesn't support named constraints in the same way as PuLP.
            The name parameter is accepted for API compatibility but not used.
        """
        self.cvxpy_constraints.append(constraint)

    def solve(
        self,
        time_limit: Optional[float] = None,
        verbose: bool = False
    ) -> OptimizationStatus:
        """
        Solve the optimization problem with CVXPY.

        Args:
            time_limit: Maximum solving time in seconds
            verbose: Print solver output

        Returns:
            Optimization status

        Raises:
            ValueError: If problem not properly set up
            RuntimeError: If solver encounters an error
        """
        if self.cvxpy_objective is None:
            raise ValueError("Objective not set. Call set_objective first.")

        # Create problem
        self.cvxpy_problem = cp.Problem(
            self.cvxpy_objective,
            self.cvxpy_constraints
        )

        # Choose solver based on problem type
        solver = self._select_solver()

        # Build solver options
        solver_kwargs = {"verbose": verbose}
        if time_limit is not None:
            # Note: Not all CVXPY solvers support time limits
            solver_kwargs["max_iters"] = 100000  # Fallback

        # Solve
        start_time = time.time()
        try:
            self.cvxpy_problem.solve(solver=solver, **solver_kwargs)
            self.solve_time = time.time() - start_time

            # Map CVXPY status to our standard status
            self.status = self._map_cvxpy_status(self.cvxpy_problem.status)

            # Store results if feasible
            if self.is_feasible():
                self.objective_value = self.cvxpy_problem.value

            return self.status

        except Exception as e:
            self.solve_time = time.time() - start_time
            self.status = OptimizationStatus.ERROR
            raise RuntimeError(f"CVXPY solver error: {str(e)}")

    def _select_solver(self):
        """
        Select appropriate CVXPY solver based on problem type.

        Returns:
            CVXPY solver constant or None (auto-select)
        """
        # Try to detect if problem has integer variables
        has_integer = any(
            var.attributes.get('boolean', False) or
            var.attributes.get('integer', False)
            for var in self.cvxpy_variables.values()
        )

        if has_integer:
            # Mixed-integer solver - let CVXPY auto-select
            # Common MIP solvers: GLPK_MI, CBC, SCIP
            return None  # Auto-select

        else:
            # Continuous optimization
            # Use SCS - it's more general and handles QP, SOCP, SDP
            # SCS is bundled and robust for various convex problems
            return cp.SCS

    def _map_cvxpy_status(self, cvxpy_status: str) -> OptimizationStatus:
        """
        Map CVXPY status to standard status.

        Args:
            cvxpy_status: CVXPY status string

        Returns:
            Standard OptimizationStatus
        """
        status_map = {
            "optimal": OptimizationStatus.OPTIMAL,
            "optimal_inaccurate": OptimizationStatus.FEASIBLE,
            "infeasible": OptimizationStatus.INFEASIBLE,
            "infeasible_inaccurate": OptimizationStatus.INFEASIBLE,
            "unbounded": OptimizationStatus.UNBOUNDED,
            "unbounded_inaccurate": OptimizationStatus.UNBOUNDED,
        }

        return status_map.get(cvxpy_status, OptimizationStatus.UNKNOWN)

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

        solution = {}
        for name, var in self.cvxpy_variables.items():
            if var.value is not None:
                # Convert numpy types to Python float
                if isinstance(var.value, np.ndarray):
                    solution[name] = float(var.value.item())
                else:
                    solution[name] = float(var.value)

        return solution

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

        if self.cvxpy_problem is None or self.cvxpy_problem.value is None:
            raise ValueError("Problem not solved or no value available")

        return float(self.cvxpy_problem.value)

    def reset(self):
        """Reset solver for a new problem"""
        super().reset()
        self.cvxpy_variables = {}
        self.cvxpy_constraints = []
        self.cvxpy_objective = None
        self.cvxpy_problem = None

    def get_problem_info(self) -> Dict[str, Any]:
        """
        Get information about the problem structure.

        Returns:
            Dict with problem statistics
        """
        if self.cvxpy_problem is None:
            return {
                "problem_type": self.problem_type,
                "num_variables": len(self.cvxpy_variables),
                "num_constraints": len(self.cvxpy_constraints),
                "status": "not_solved"
            }

        # Get variable types
        var_types = {"continuous": 0, "integer": 0, "binary": 0}
        for var in self.cvxpy_variables.values():
            if var.attributes.get('boolean', False):
                var_types["binary"] += 1
            elif var.attributes.get('integer', False):
                var_types["integer"] += 1
            else:
                var_types["continuous"] += 1

        return {
            "problem_type": self.problem_type,
            "num_variables": len(self.cvxpy_variables),
            "num_constraints": len(self.cvxpy_constraints),
            "variable_types": var_types,
            "status": self.status.value if self.status else "unknown",
            "is_dcp": self.cvxpy_problem.is_dcp() if self.cvxpy_problem else None,
            "is_dgp": self.cvxpy_problem.is_dgp() if self.cvxpy_problem else None,
        }

    def get_dual_values(self) -> Dict[str, float]:
        """
        Get dual values (shadow prices) for constraints.

        Returns:
            Dict mapping constraint indices to dual values

        Note:
            Only available for LP problems (not MIP).
            CVXPY constraints don't have names, so we use indices.
        """
        if not self.is_optimal():
            return {}

        dual_values = {}
        for i, constraint in enumerate(self.cvxpy_constraints):
            if hasattr(constraint, 'dual_value') and constraint.dual_value is not None:
                dual_values[f"constraint_{i}"] = float(constraint.dual_value)

        return dual_values
