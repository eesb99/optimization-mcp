"""
Monte Carlo Integration Layer

Provides deep integration with Monte Carlo MCP by:
1. Processing MC outputs for use in optimization
2. Formatting optimization outputs for MC validation
3. Supporting three integration modes: percentile, expected, scenarios
"""

from typing import Dict, List, Any, Optional
import numpy as np


class MonteCarloIntegration:
    """
    Handles integration between optimization and Monte Carlo MCPs.

    Enables three integration modes:
    - Percentile: Use P10/P50/P90 values from MC simulations
    - Expected: Use mean values across all scenarios
    - Scenarios: Optimize across all MC scenarios for robustness
    """

    @staticmethod
    def extract_percentile_values(
        mc_output: Dict[str, Any],
        percentile: str = "p50",
        variable_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Extract percentile values from Monte Carlo output.

        Args:
            mc_output: Output from Monte Carlo MCP tool (e.g., run_business_scenario)
            percentile: Which percentile to extract ("p10", "p50", "p90")
            variable_names: Optional list of variables to extract (None = all)

        Returns:
            Dict mapping variable names to their percentile values

        Example:
            mc_result = run_business_scenario(...)
            values = extract_percentile_values(mc_result, "p50")
            # values = {"project_a_return": 48500, "project_b_return": 62000}
        """
        # Check if percentiles exist in MC output
        if "percentiles" not in mc_output:
            raise ValueError(
                "Monte Carlo output missing 'percentiles' field. "
                "Ensure MC tool was called correctly."
            )

        percentiles = mc_output["percentiles"]

        # Validate percentile choice
        valid_percentiles = ["p10", "p25", "p50", "p75", "p90"]
        percentile_lower = percentile.lower()
        if percentile_lower not in [p.lower() for p in valid_percentiles]:
            raise ValueError(
                f"Invalid percentile '{percentile}'. "
                f"Must be one of: {valid_percentiles}"
            )

        # Extract values
        extracted_values = {}

        # Try exact case match first
        if percentile in percentiles:
            percentile_data = percentiles[percentile]
        else:
            # Try case-insensitive match
            for key in percentiles.keys():
                if key.lower() == percentile_lower:
                    percentile_data = percentiles[key]
                    break
            else:
                raise ValueError(
                    f"Percentile '{percentile}' not found in MC output. "
                    f"Available: {list(percentiles.keys())}"
                )

        # Extract requested variables
        if variable_names is None:
            extracted_values = percentile_data
        else:
            for var in variable_names:
                if var in percentile_data:
                    extracted_values[var] = percentile_data[var]
                else:
                    raise ValueError(
                        f"Variable '{var}' not found in percentile data. "
                        f"Available: {list(percentile_data.keys())}"
                    )

        return extracted_values

    @staticmethod
    def extract_expected_values(
        mc_output: Dict[str, Any],
        variable_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Extract expected (mean) values from Monte Carlo output.

        Args:
            mc_output: Output from Monte Carlo MCP tool
            variable_names: Optional list of variables to extract

        Returns:
            Dict mapping variable names to their expected values
        """
        # Try to get expected values directly
        if "expected_outcome" in mc_output:
            expected = mc_output["expected_outcome"]
            if isinstance(expected, dict):
                if variable_names is None:
                    return expected
                else:
                    return {
                        var: expected[var]
                        for var in variable_names
                        if var in expected
                    }

        # Fallback: Use P50 as proxy for expected value
        return MonteCarloIntegration.extract_percentile_values(
            mc_output, "p50", variable_names
        )

    @staticmethod
    def extract_all_scenarios(
        mc_output: Dict[str, Any],
        variable_names: Optional[List[str]] = None
    ) -> List[Dict[str, float]]:
        """
        Extract all scenarios from Monte Carlo output for robust optimization.

        Args:
            mc_output: Output from Monte Carlo MCP tool
            variable_names: Optional list of variables to extract

        Returns:
            List of dicts, each representing one scenario with variable values

        Example:
            scenarios = extract_all_scenarios(mc_output, ["revenue", "cost"])
            # scenarios = [
            #     {"revenue": 95000, "cost": 32000},
            #     {"revenue": 102000, "cost": 29000},
            #     ...  (10,000 scenarios)
            # ]
        """
        if "scenarios" not in mc_output:
            raise ValueError(
                "Monte Carlo output missing 'scenarios' field. "
                "Use run_business_scenario with return_scenarios=True."
            )

        scenarios = mc_output["scenarios"]

        if variable_names is None:
            return scenarios
        else:
            # Filter to requested variables
            return [
                {var: scenario[var] for var in variable_names if var in scenario}
                for scenario in scenarios
            ]

    @staticmethod
    def create_assumptions_from_distributions(
        distributions: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert distribution specifications to MC-compatible assumptions format.

        Args:
            distributions: Dict mapping variable names to distribution specs
                          e.g., {"revenue": {"type": "normal", "mean": 100000, "std": 15000}}

        Returns:
            List of assumption dicts for Monte Carlo validation

        Example:
            distributions = {
                "project_a_return": {"type": "normal", "mean": 50000, "std": 10000},
                "project_b_return": {"type": "normal", "mean": 35000, "std": 8000}
            }
            assumptions = create_assumptions_from_distributions(distributions)
        """
        assumptions = []

        for var_name, dist_spec in distributions.items():
            assumption = {
                "name": var_name,
                "value": dist_spec.get("mean", dist_spec.get("most_likely", 0)),
                "distribution": {
                    "type": dist_spec.get("type", "normal"),
                    "params": {
                        k: v for k, v in dist_spec.items()
                        if k not in ["type", "name"]
                    }
                }
            }
            assumptions.append(assumption)

        return assumptions

    @staticmethod
    def format_for_robustness_testing(
        decision_variables: Dict[str, float],
        assumptions: List[Dict[str, Any]],
        outcome_function: str,
        objective_value: float
    ) -> Dict[str, Any]:
        """
        Format optimization results for Monte Carlo robustness testing.

        Prepares data for test_assumption_robustness tool.

        Args:
            decision_variables: Optimal variable values
            assumptions: Uncertainty assumptions
            outcome_function: Description of how outcome is calculated
            objective_value: Optimal objective value

        Returns:
            Dict ready for test_assumption_robustness
        """
        # Generate stress test ranges (±50% from mean)
        stress_ranges = {}
        for assumption in assumptions:
            name = assumption["name"]
            value = assumption["value"]
            stress_ranges[name] = {
                "low": value * 0.5,
                "high": value * 1.5
            }

        return {
            "base_answer": (
                f"Optimal allocation: {decision_variables}, "
                f"Objective value: {objective_value:.2f}"
            ),
            "critical_assumptions": assumptions,
            "stress_test_ranges": stress_ranges,
            "outcome_function_str": outcome_function,
            "num_scenarios": 1000
        }

    @staticmethod
    def format_for_confidence_validation(
        decision_context: str,
        assumptions: List[Dict[str, Any]],
        objective_value: float,
        success_threshold_pct: float = 0.9
    ) -> Dict[str, Any]:
        """
        Format optimization results for Monte Carlo confidence validation.

        Prepares data for validate_reasoning_confidence tool.

        Args:
            decision_context: Description of the decision
            assumptions: Uncertainty assumptions
            objective_value: Target objective value
            success_threshold_pct: Success defined as >= this % of optimal

        Returns:
            Dict ready for validate_reasoning_confidence
        """
        # Convert assumptions list to dict format
        assumptions_dict = {}
        for assumption in assumptions:
            assumptions_dict[assumption["name"]] = {
                "distribution": assumption["distribution"]["type"],
                "params": assumption["distribution"]["params"]
            }

        return {
            "decision_context": decision_context,
            "assumptions": assumptions_dict,
            "success_criteria": {
                "threshold": objective_value * success_threshold_pct,
                "comparison": ">="
            },
            "num_simulations": 10000
        }

    @staticmethod
    def calculate_scenario_probabilities(
        scenarios: List[Dict[str, float]],
        equal_weight: bool = True
    ) -> List[float]:
        """
        Calculate probability weights for scenarios.

        Args:
            scenarios: List of scenario dicts
            equal_weight: If True, equal probability for all scenarios

        Returns:
            List of probabilities (sum to 1.0)
        """
        n = len(scenarios)
        if equal_weight:
            return [1.0 / n] * n
        else:
            # Future: Could implement importance sampling
            return [1.0 / n] * n

    @staticmethod
    def aggregate_scenario_outcomes(
        scenario_outcomes: List[float],
        probabilities: Optional[List[float]] = None,
        aggregation: str = "expected"
    ) -> float:
        """
        Aggregate outcomes across scenarios.

        Args:
            scenario_outcomes: List of outcome values for each scenario
            probabilities: Optional probability weights
            aggregation: "expected", "worst_case", "best_case"

        Returns:
            Aggregated outcome value
        """
        if probabilities is None:
            probabilities = [1.0 / len(scenario_outcomes)] * len(scenario_outcomes)

        if aggregation == "expected":
            return np.average(scenario_outcomes, weights=probabilities)
        elif aggregation == "worst_case":
            return min(scenario_outcomes)
        elif aggregation == "best_case":
            return max(scenario_outcomes)
        else:
            raise ValueError(
                f"Invalid aggregation '{aggregation}'. "
                f"Must be: expected, worst_case, best_case"
            )

    @staticmethod
    def validate_mc_output(mc_output: Dict[str, Any]) -> bool:
        """
        Validate that MC output has required structure.

        Args:
            mc_output: Output from Monte Carlo MCP tool

        Returns:
            True if valid, raises ValueError if invalid
        """
        required_fields = ["percentiles"]

        for field in required_fields:
            if field not in mc_output:
                raise ValueError(
                    f"Invalid Monte Carlo output: missing '{field}' field. "
                    f"Available fields: {list(mc_output.keys())}"
                )

        # Validate percentiles structure
        percentiles = mc_output["percentiles"]
        if not isinstance(percentiles, dict):
            raise ValueError(
                "Monte Carlo 'percentiles' must be a dictionary"
            )

        return True


# Convenience functions for common integration patterns

def integrate_mc_percentile(
    mc_output: Dict[str, Any],
    percentile: str = "p50"
) -> Dict[str, float]:
    """
    Quick helper: Extract percentile values from MC output.

    Args:
        mc_output: Monte Carlo MCP output
        percentile: "p10", "p50", or "p90"

    Returns:
        Dict of variable values at specified percentile
    """
    return MonteCarloIntegration.extract_percentile_values(mc_output, percentile)


def integrate_mc_expected(mc_output: Dict[str, Any]) -> Dict[str, float]:
    """
    Quick helper: Extract expected values from MC output.

    Args:
        mc_output: Monte Carlo MCP output

    Returns:
        Dict of expected variable values
    """
    return MonteCarloIntegration.extract_expected_values(mc_output)


def integrate_mc_scenarios(mc_output: Dict[str, Any]) -> List[Dict[str, float]]:
    """
    Quick helper: Extract all scenarios from MC output.

    Args:
        mc_output: Monte Carlo MCP output

    Returns:
        List of scenario dicts
    """
    return MonteCarloIntegration.extract_all_scenarios(mc_output)
