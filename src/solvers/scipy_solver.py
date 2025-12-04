"""
SciPy Solver Wrapper

Wrapper for SciPy's optimize.minimize providing nonlinear continuous optimization.
Supports bounds and constraints for smooth, differentiable problems.
"""

import time
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from scipy.optimize import minimize, OptimizeResult

from .base_solver import BaseSolver, OptimizationStatus, ObjectiveSense


class SciPySolver(BaseSolver):
    """
    SciPy solver wrapper for nonlinear continuous optimization.

    Capabilities:
    - Nonlinear objective functions
    - Bounds on variables
    - Equality and inequality constraints
    - Multiple algorithms (L-BFGS-B, SLSQP, trust-constr)
    - Best for: 10-1000 continuous variables
    """

    def __init__(self, method: str = "SLSQP"):
        """
        Initialize SciPy solver.

        Args:
            method: Optimization algorithm
                   - "L-BFGS-B": Bound-constrained, no constraints
                   - "SLSQP": Sequential Least Squares, supports constraints
                   - "trust-constr": Trust region, most general
        """
        super().__init__(solver_name="scipy")
        self.method = method
        self.variables = {}  # name -> index mapping
        self.var_names = []  # ordered list of variable names
        self.bounds = []     # [(lower, upper), ...] for each variable
        self.initial_guess = None
        self.objective_func = None
        self.objective_sense = ObjectiveSense.MINIMIZE
        self.constraints_list = []  # List of constraint dicts
        self.result: Optional[OptimizeResult] = None

    def create_variables(
        self,
        names: List[str],
        var_type: str = "continuous",
        bounds: Optional[Dict[str, tuple]] = None
    ) -> Dict[str, int]:
        """
        Create SciPy decision variables.

        Args:
            names: List of variable names
            var_type: Must be "continuous" (SciPy only supports continuous)
            bounds: Dict mapping variable names to (lower, upper) bounds

        Returns:
            Dict mapping variable names to their indices

        Raises:
            ValueError: If var_type is not "continuous"
        """
        if var_type != "continuous":
            raise ValueError(
                f"SciPy solver only supports continuous variables. "
                f"Use PuLP solver for {var_type} variables."
            )

        bounds = bounds or {}

        for i, name in enumerate(names):
            self.variables[name] = i
            self.var_names.append(name)

            # Get bounds or use (-inf, inf)
            lb, ub = bounds.get(name, (None, None))
            self.bounds.append((lb, ub))

        # Initialize guess to zeros (or bounds midpoint if bounded)
        self.initial_guess = self._generate_initial_guess()

        return self.variables

    def _generate_initial_guess(self) -> np.ndarray:
        """
        Generate initial guess for optimization.

        Returns:
            Initial values for all variables
        """
        guess = []
        for lb, ub in self.bounds:
            if lb is not None and ub is not None:
                # Midpoint of bounds
                guess.append((lb + ub) / 2.0)
            elif lb is not None:
                # Lower bound + 1
                guess.append(lb + 1.0)
            elif ub is not None:
                # Upper bound - 1
                guess.append(ub - 1.0)
            else:
                # No bounds, start at 0
                guess.append(0.0)

        return np.array(guess)

    def set_objective(
        self,
        expression: Callable[[np.ndarray], float],
        sense: ObjectiveSense = ObjectiveSense.MINIMIZE
    ):
        """
        Set the objective function.

        Args:
            expression: Callable that takes variable array and returns float
            sense: MINIMIZE or MAXIMIZE

        Example:
            def objective(x):
                return x[0]**2 + x[1]**2
            solver.set_objective(objective, ObjectiveSense.MINIMIZE)
        """
        self.objective_func = expression
        self.objective_sense = sense

    def add_constraint(
        self,
        constraint: Dict[str, Any],
        name: Optional[str] = None
    ):
        """
        Add a constraint to the problem.

        Args:
            constraint: Dict with keys:
                       - "type": "ineq" (>= 0) or "eq" (== 0)
                       - "fun": Callable taking variable array
                       - "jac": Optional Jacobian (gradient) function
            name: Optional constraint name

        Example:
            # x + y <= 10  -->  10 - x - y >= 0
            constraint = {
                "type": "ineq",
                "fun": lambda x: 10 - x[0] - x[1]
            }
            solver.add_constraint(constraint)
        """
        if name is None:
            name = f"constraint_{len(self.constraints_list)}"

        constraint["name"] = name
        self.constraints_list.append(constraint)

    def solve(
        self,
        time_limit: Optional[float] = None,
        verbose: bool = False
    ) -> OptimizationStatus:
        """
        Solve the optimization problem using SciPy minimize.

        Args:
            time_limit: Maximum solving time (not all methods support this)
            verbose: Print solver output

        Returns:
            Optimization status

        Raises:
            ValueError: If problem not properly set up
        """
        if self.objective_func is None:
            raise ValueError("Objective function not set")

        if len(self.variables) == 0:
            raise ValueError("No variables defined")

        # Prepare objective (negate if maximizing)
        if self.objective_sense == ObjectiveSense.MAXIMIZE:
            objective = lambda x: -self.objective_func(x)
        else:
            objective = self.objective_func

        # Prepare options
        options = {
            "disp": verbose
        }
        if time_limit is not None and self.method in ["trust-constr"]:
            options["maxiter"] = 10000  # Approximate time limiting

        # Solve
        start_time = time.time()
        try:
            self.result = minimize(
                fun=objective,
                x0=self.initial_guess,
                method=self.method,
                bounds=self.bounds if self.bounds else None,
                constraints=self.constraints_list if self.constraints_list else None,
                options=options
            )
            self.solve_time = time.time() - start_time

            # Map scipy status to our standard status
            self.status = self._map_scipy_status(self.result)

            # Store solution if feasible
            if self.is_feasible():
                self.solution = self.get_solution()
                # Negate back if we were maximizing
                if self.objective_sense == ObjectiveSense.MAXIMIZE:
                    self.objective_value = -self.result.fun
                else:
                    self.objective_value = self.result.fun

            return self.status

        except Exception as e:
            self.solve_time = time.time() - start_time
            self.status = OptimizationStatus.ERROR
            raise RuntimeError(f"Solver error: {str(e)}")

    def _map_scipy_status(self, result: OptimizeResult) -> OptimizationStatus:
        """
        Map SciPy result to standard status.

        Args:
            result: SciPy OptimizeResult

        Returns:
            Standard OptimizationStatus
        """
        if result.success:
            # Check if constraints are satisfied (for constrained problems)
            if self.constraints_list:
                max_violation = self._check_constraint_violations(result.x)
                if max_violation > 1e-6:
                    return OptimizationStatus.FEASIBLE
            return OptimizationStatus.OPTIMAL
        else:
            # Check result message for specific failure modes
            message = result.message.lower() if hasattr(result, "message") else ""

            if "infeasible" in message:
                return OptimizationStatus.INFEASIBLE
            elif "unbounded" in message:
                return OptimizationStatus.UNBOUNDED
            elif "iteration" in message or "limit" in message:
                return OptimizationStatus.TIMEOUT
            else:
                return OptimizationStatus.ERROR

    def _check_constraint_violations(self, x: np.ndarray) -> float:
        """
        Check maximum constraint violation.

        Args:
            x: Variable values

        Returns:
            Maximum violation amount
        """
        max_violation = 0.0

        for constraint in self.constraints_list:
            value = constraint["fun"](x)

            if constraint["type"] == "eq":
                violation = abs(value)
            elif constraint["type"] == "ineq":
                violation = max(0, -value)  # Should be >= 0
            else:
                violation = 0

            max_violation = max(max_violation, violation)

        return max_violation

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
            name: float(self.result.x[idx])
            for name, idx in self.variables.items()
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

        return self.objective_value

    def format_solution(
        self,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format solution with SciPy-specific information.

        Adds iterations, function evaluations, gradient evaluations.

        Args:
            additional_info: Additional information to include

        Returns:
            Comprehensive solution dictionary
        """
        result = super().format_solution(additional_info)

        if self.result is not None:
            # Add SciPy-specific info
            result["iterations"] = getattr(self.result, "nit", None)
            result["function_evaluations"] = getattr(self.result, "nfev", None)
            result["jacobian_evaluations"] = getattr(self.result, "njev", None)
            result["message"] = getattr(self.result, "message", None)

            if self.is_feasible():
                # Check constraint satisfaction
                max_violation = self._check_constraint_violations(self.result.x)
                result["max_constraint_violation"] = max_violation
                result["constraints_satisfied"] = max_violation < 1e-6

        return result

    def set_initial_guess(self, guess: Dict[str, float]):
        """
        Set custom initial guess for variables.

        Args:
            guess: Dict mapping variable names to initial values

        Raises:
            ValueError: If variable names don't match
        """
        if set(guess.keys()) != set(self.variables.keys()):
            raise ValueError(
                "Initial guess must include all variables"
            )

        self.initial_guess = np.array([
            guess[name] for name in self.var_names
        ])

    def reset(self):
        """Reset solver for a new problem"""
        super().reset()
        self.variables = {}
        self.var_names = []
        self.bounds = []
        self.initial_guess = None
        self.objective_func = None
        self.constraints_list = []
        self.result = None

    def get_problem_info(self) -> Dict[str, Any]:
        """
        Get information about the problem structure.

        Returns:
            Dict with problem statistics
        """
        return {
            "solver_method": self.method,
            "num_variables": len(self.variables),
            "num_constraints": len(self.constraints_list),
            "has_bounds": any(
                lb is not None or ub is not None
                for lb, ub in self.bounds
            ),
            "sense": self.objective_sense.value
        }
