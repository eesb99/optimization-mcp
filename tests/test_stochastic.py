"""
Test Stochastic Programming Optimization

Tests for optimize_stochastic tool (2-stage with recourse).
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

from src.api.stochastic import optimize_stochastic


def test_simple_two_stage():
    """Test basic 2-stage stochastic problem."""
    print("Test: Simple 2-Stage Stochastic")

    result = optimize_stochastic(
        first_stage={
            "decisions": [{"name": "inventory", "type": "continuous", "cost": 10, "bounds": (0, 100)}]
        },
        second_stage={
            "decisions": [{"name": "reorder", "type": "continuous"}],
            "constraints": []
        },
        scenarios=[
            {"name": "low", "probability": 0.3, "parameters": {"cost": 5}},
            {"name": "medium", "probability": 0.5, "parameters": {"cost": 10}},
            {"name": "high", "probability": 0.2, "parameters": {"cost": 15}}
        ]
    )

    print(f"  Status: {result['status']}")
    print(f"  First-stage decision: {result.get('first_stage_decision')}")
    print(f"  Expected cost: {result.get('expected_cost')}")

    assert result["status"] == "optimal"
    assert "first_stage_decision" in result
    assert "scenario_decisions" in result
    assert "expected_cost" in result

    print("✓ Test passed\n")
    return result


def test_worst_case_risk_measure():
    """Test worst-case (robust) risk measure."""
    print("Test: Worst-Case Risk Measure")

    result = optimize_stochastic(
        first_stage={
            "decisions": [{"name": "capacity", "type": "continuous", "cost": 100}]
        },
        second_stage={
            "decisions": [{"name": "expansion", "type": "continuous"}]
        },
        scenarios=[
            {"name": "pessimistic", "probability": 0.2, "parameters": {"cost": 200}},
            {"name": "base", "probability": 0.6, "parameters": {"cost": 150}},
            {"name": "optimistic", "probability": 0.2, "parameters": {"cost": 100}}
        ],
        risk_measure="worst_case"
    )

    print(f"  Status: {result['status']}")
    print(f"  Risk measure: {result.get('risk_measure')}")

    assert result["status"] == "optimal"
    assert result["risk_measure"] == "worst_case"

    print("✓ Test passed\n")
    return result


def test_mc_compatible_output():
    """Test Monte Carlo compatible output generation."""
    print("Test: Stochastic MC Compatible Output")

    result = optimize_stochastic(
        first_stage={
            "decisions": [{"name": "invest", "type": "continuous", "cost": 1000}]
        },
        second_stage={
            "decisions": [{"name": "adjust", "type": "continuous"}]
        },
        scenarios=[
            {"name": "s1", "probability": 0.5, "parameters": {"return": 1.1}},
            {"name": "s2", "probability": 0.5, "parameters": {"return": 0.9}}
        ]
    )

    assert "monte_carlo_compatible" in result
    mc_output = result["monte_carlo_compatible"]

    assert "decision_variables" in mc_output
    assert "assumptions" in mc_output
    assert "recommended_next_tool" in mc_output

    print(f"  MC assumptions: {len(mc_output['assumptions'])}")
    print("✓ Test passed\n")
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Running Stochastic Programming Tests")
    print("=" * 60 + "\n")

    test_simple_two_stage()
    test_worst_case_risk_measure()
    test_mc_compatible_output()

    print("=" * 60)
    print("All Stochastic tests passed!")
    print("=" * 60)
