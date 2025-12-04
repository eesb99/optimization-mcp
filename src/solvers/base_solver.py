"""
Base Solver Interface

Abstract base class defining the common interface for all optimization solvers.
All concrete solvers (PuLP, SciPy, CVXPY) inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from enum import Enum


class OptimizationStatus(Enum):
    """Standard optimization status codes across all solvers"""
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    FEASIBLE = "feasible"  # Solution found but not proven optimal
    TIMEOUT = "timeout"
    ERROR = "error"
    UNKNOWN = "unknown"


class ObjectiveSense(Enum):
    """Optimization direction"""
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class BaseSolver(ABC):
    """
    Abstract base class for optimization solvers.

    Provides common interface and utilities for:
    - Problem formulation
    - Solving
    - Solution extraction
    - Monte Carlo integration
    """

    def __init__(self, solver_name: str):
        """
        Initialize solver.

        Args:
            solver_name: Name of the solver implementation (e.g., "pulp", "scipy")
        """
        self.solver_name = solver_name
        self.problem = None
        self.status = OptimizationStatus.UNKNOWN
        self.solution = None
        self.objective_value = None
        self.solve_time = None

    @abstractmethod
    def create_variables(
        self,
        names: List[str],
        var_type: str = "continuous",
        bounds: Optional[Dict[str, tuple]] = None
    ) -> Dict[str, Any]:
        """
        Create decision variables.

        Args:
            names: List of variable names
            var_type: "continuous", "integer", or "binary"
            bounds: Dict mapping variable names to (lower, upper) bounds

        Returns:
            Dict mapping variable names to solver-specific variable objects
        """
        pass

    @abstractmethod
    def set_objective(
        self,
        expression: Any,
        sense: ObjectiveSense = ObjectiveSense.MINIMIZE
    ):
        """
        Set the objective function.

        Args:
            expression: Solver-specific objective expression
            sense: MINIMIZE or MAXIMIZE
        """
        pass

    @abstractmethod
    def add_constraint(
        self,
        constraint: Any,
        name: Optional[str] = None
    ):
        """
        Add a constraint to the problem.

        Args:
            constraint: Solver-specific constraint expression
            name: Optional name for the constraint
        """
        pass

    @abstractmethod
    def solve(
        self,
        time_limit: Optional[float] = None,
        verbose: bool = False
    ) -> OptimizationStatus:
        """
        Solve the optimization problem.

        Args:
            time_limit: Maximum solving time in seconds
            verbose: Print solver output

        Returns:
            Optimization status
        """
        pass

    @abstractmethod
    def get_solution(self) -> Dict[str, float]:
        """
        Extract solution values for all variables.

        Returns:
            Dict mapping variable names to their optimal values
        """
        pass

    @abstractmethod
    def get_objective_value(self) -> float:
        """
        Get the optimal objective function value.

        Returns:
            Objective value at optimal solution
        """
        pass

    def get_status(self) -> OptimizationStatus:
        """Get the current optimization status"""
        return self.status

    def get_solve_time(self) -> Optional[float]:
        """Get the solver execution time in seconds"""
        return self.solve_time

    def is_optimal(self) -> bool:
        """Check if an optimal solution was found"""
        return self.status == OptimizationStatus.OPTIMAL

    def is_feasible(self) -> bool:
        """Check if a feasible solution exists"""
        return self.status in [
            OptimizationStatus.OPTIMAL,
            OptimizationStatus.FEASIBLE
        ]

    def format_solution(
        self,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format solution in standard output format.

        Args:
            additional_info: Solver-specific additional information

        Returns:
            Standardized solution dictionary
        """
        result = {
            "solver": self.solver_name,
            "status": self.status.value,
            "is_optimal": self.is_optimal(),
            "is_feasible": self.is_feasible(),
            "solve_time_seconds": self.solve_time
        }

        if self.is_feasible():
            result["objective_value"] = self.get_objective_value()
            result["solution"] = self.get_solution()

        if additional_info:
            result.update(additional_info)

        return result

    def create_monte_carlo_compatible_output(
        self,
        decision_variables: Dict[str, float],
        assumptions: List[Dict[str, Any]],
        outcome_function: str,
        recommended_next_tool: str = "validate_reasoning_confidence"
    ) -> Dict[str, Any]:
        """
        Create standardized output section for Monte Carlo integration.

        This enables zero-friction chaining with Monte Carlo MCP tools.

        Args:
            decision_variables: Dict of variable names and their values
            assumptions: List of assumption dicts with name, value, distribution
            outcome_function: String describing how outcome is calculated
            recommended_next_tool: Suggested next MC tool to call

        Returns:
            Monte Carlo compatible output dict
        """
        return {
            "decision_variables": decision_variables,
            "assumptions": assumptions,
            "outcome_function": outcome_function,
            "recommended_next_tool": recommended_next_tool,
            "recommended_params": self._generate_recommended_mc_params(
                decision_variables,
                assumptions
            )
        }

    def _generate_recommended_mc_params(
        self,
        decision_variables: Dict[str, float],
        assumptions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate recommended parameters for next Monte Carlo tool call.

        Args:
            decision_variables: Optimization decision variables
            assumptions: Uncertainty assumptions

        Returns:
            Suggested parameters for validate_reasoning_confidence
        """
        # Extract objective value for success criteria
        obj_value = self.get_objective_value() if self.is_feasible() else None

        params = {
            "decision_context": f"Optimization solution with {len(decision_variables)} variables",
            "assumptions": {
                a["name"]: {
                    "distribution": a.get("distribution", {}).get("type", "normal"),
                    "params": a.get("distribution", {}).get("params", {})
                }
                for a in assumptions
            }
        }

        if obj_value is not None:
            # Conservative success: 90% of optimal value
            params["success_criteria"] = {
                "threshold": obj_value * 0.9,
                "comparison": ">="
            }

        return params

    def reset(self):
        """Reset solver state for a new problem"""
        self.problem = None
        self.status = OptimizationStatus.UNKNOWN
        self.solution = None
        self.objective_value = None
        self.solve_time = None
