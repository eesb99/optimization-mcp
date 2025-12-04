"""
Test Pareto Multi-Objective Optimization

Tests for optimize_pareto tool generating Pareto frontiers.
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

from src.api.pareto import optimize_pareto


def test_simple_two_objective_pareto():
    """Test basic 2-objective Pareto frontier (profit vs sustainability)."""
    print("Test: Simple 2-Objective Pareto Frontier")

    objectives = [
        {
            "name": "profit",
            "items": [
                {"name": "project_a", "value": 100},
                {"name": "project_b", "value": 60},
                {"name": "project_c", "value": 80}
            ],
            "sense": "maximize"
        },
        {
            "name": "sustainability",
            "items": [
                {"name": "project_a", "value": 40},
                {"name": "project_b", "value": 90},
                {"name": "project_c", "value": 70}
            ],
            "sense": "maximize"
        }
    ]

    resources = {"budget": {"total": 100}}

    item_requirements = [
        {"name": "project_a", "budget": 60},
        {"name": "project_b", "budget": 45},
        {"name": "project_c", "budget": 55}
    ]

    result = optimize_pareto(
        objectives=objectives,
        resources=resources,
        item_requirements=item_requirements,
        num_points=10
    )

    print(f"  Status: {result['status']}")
    print(f"  Frontier points: {result['num_frontier_points']}")

    # Assertions
    assert result["status"] == "optimal"
    assert "pareto_frontier" in result
    assert result["num_frontier_points"] > 0

    # Check frontier structure
    frontier = result["pareto_frontier"]
    assert len(frontier) > 0

    # Each point should have allocation and objective values
    for point in frontier:
        assert "allocation" in point
        assert "objective_values" in point
        assert "profit" in point["objective_values"]
        assert "sustainability" in point["objective_values"]

    # Check recommended point exists
    assert "recommended_point" in result
    assert "index" in result["recommended_point"]

    print(f"  Sample point: {frontier[0]['objective_values']}")
    print(f"  Recommended: {result['recommended_point']['objective_values']}")
    print("✓ Test passed\n")
    return result


def test_pareto_tradeoff_analysis():
    """Test trade-off analysis between objectives."""
    print("Test: Pareto Trade-Off Analysis")

    objectives = [
        {
            "name": "revenue",
            "items": [
                {"name": "premium", "value": 200},
                {"name": "standard", "value": 100}
            ],
            "sense": "maximize"
        },
        {
            "name": "customer_satisfaction",
            "items": [
                {"name": "premium", "value": 95},
                {"name": "standard", "value": 70}
            ],
            "sense": "maximize"
        }
    ]

    resources = {"capacity": {"total": 1}}
    item_requirements = [
        {"name": "premium", "capacity": 1},
        {"name": "standard", "capacity": 1}
    ]

    result = optimize_pareto(
        objectives=objectives,
        resources=resources,
        item_requirements=item_requirements,
        num_points=15
    )

    print(f"  Status: {result['status']}")
    print(f"  Frontier points: {result['num_frontier_points']}")

    # Check tradeoff analysis
    assert "tradeoff_analysis" in result
    analysis = result["tradeoff_analysis"]

    assert "objective_ranges" in analysis
    assert "revenue" in analysis["objective_ranges"]
    assert "customer_satisfaction" in analysis["objective_ranges"]

    # Check if trade-off rates calculated (for 2 objectives)
    if "tradeoff_rates" in analysis and len(analysis["tradeoff_rates"]) > 0:
        print(f"  Trade-off rates: {list(analysis['tradeoff_rates'].keys())}")

    print("✓ Test passed\n")
    return result


def test_pareto_three_objectives():
    """Test 3-objective Pareto frontier."""
    print("Test: 3-Objective Pareto Frontier")

    objectives = [
        {"name": "cost", "items": [{"name": "option_a", "value": 100}, {"name": "option_b", "value": 80}], "sense": "minimize"},
        {"name": "time", "items": [{"name": "option_a", "value": 10}, {"name": "option_b", "value": 15}], "sense": "minimize"},
        {"name": "quality", "items": [{"name": "option_a", "value": 90}, {"name": "option_b", "value": 85}], "sense": "maximize"}
    ]

    resources = {"budget": {"total": 150}}
    item_requirements = [
        {"name": "option_a", "budget": 100},
        {"name": "option_b", "budget": 80}
    ]

    result = optimize_pareto(
        objectives=objectives,
        resources=resources,
        item_requirements=item_requirements,
        num_points=12,
        solver_options={"verbose": False}
    )

    print(f"  Status: {result['status']}")
    print(f"  Frontier points: {result['num_frontier_points']}")

    assert result["status"] == "optimal"
    assert result["num_frontier_points"] > 0

    # Check all 3 objectives present
    first_point = result["pareto_frontier"][0]
    assert "cost" in first_point["objective_values"]
    assert "time" in first_point["objective_values"]
    assert "quality" in first_point["objective_values"]

    print("✓ Test passed\n")
    return result


def test_pareto_with_constraints():
    """Test Pareto with additional constraints."""
    print("Test: Pareto with Additional Constraints")

    objectives = [
        {"name": "profit", "items": [{"name": "A", "value": 50}, {"name": "B", "value": 40}, {"name": "C", "value": 60}], "sense": "maximize"},
        {"name": "risk", "items": [{"name": "A", "value": 20}, {"name": "B", "value": 10}, {"name": "C", "value": 30}], "sense": "minimize"}
    ]

    resources = {"budget": {"total": 100}}
    item_requirements = [
        {"name": "A", "budget": 40},
        {"name": "B", "budget": 30},
        {"name": "C", "budget": 50}
    ]

    # Add constraint: must select at least 1 item
    constraints = [
        {"type": "disjunctive", "items": ["A", "B", "C"], "min_selected": 1}
    ]

    result = optimize_pareto(
        objectives=objectives,
        resources=resources,
        item_requirements=item_requirements,
        constraints=constraints,
        num_points=8
    )

    print(f"  Status: {result['status']}")
    print(f"  Frontier points: {result['num_frontier_points']}")

    assert result["status"] == "optimal"

    # Verify constraint satisfaction
    for point in result["pareto_frontier"]:
        selected = sum(point["allocation"].values())
        assert selected >= 1  # At least one selected

    print("✓ Test passed\n")
    return result


def test_pareto_dominated_solutions_removed():
    """Test that dominated solutions are filtered out."""
    print("Test: Dominated Solutions Filtering")

    objectives = [
        {"name": "obj1", "items": [{"name": "X", "value": 100}, {"name": "Y", "value": 50}], "sense": "maximize"},
        {"name": "obj2", "items": [{"name": "X", "value": 80}, {"name": "Y", "value": 90}], "sense": "maximize"}
    ]

    resources = {"limit": {"total": 1}}
    item_requirements = [
        {"name": "X", "limit": 1},
        {"name": "Y", "limit": 1}
    ]

    result = optimize_pareto(
        objectives=objectives,
        resources=resources,
        item_requirements=item_requirements,
        num_points=20
    )

    print(f"  Status: {result['status']}")
    print(f"  Frontier points: {result['num_frontier_points']}")

    # Should find 2 non-dominated solutions (select X or select Y)
    # Plus possibly empty solution
    assert result["status"] == "optimal"
    assert result["num_frontier_points"] >= 2

    # Verify no dominated solutions
    frontier = result["pareto_frontier"]
    for i, point_a in enumerate(frontier):
        for j, point_b in enumerate(frontier):
            if i != j:
                # Check that A doesn't dominate B
                obj1_a = point_a["objective_values"]["obj1"]
                obj1_b = point_b["objective_values"]["obj1"]
                obj2_a = point_a["objective_values"]["obj2"]
                obj2_b = point_b["objective_values"]["obj2"]

                # If A better on both, B is dominated (should not happen)
                if obj1_a > obj1_b and obj2_a > obj2_b:
                    assert False, f"Point {j} dominated by point {i}"

    print("✓ Test passed (no dominated solutions)\n")
    return result


def test_pareto_mc_compatible_output():
    """Test Monte Carlo compatible output generation."""
    print("Test: Pareto MC Compatible Output")

    objectives = [
        {"name": "return", "items": [{"name": "stock_a", "value": 100}], "sense": "maximize"},
        {"name": "risk", "items": [{"name": "stock_a", "value": 20}], "sense": "minimize"}
    ]

    resources = {"capital": {"total": 100}}
    item_requirements = [{"name": "stock_a", "capital": 100}]

    result = optimize_pareto(
        objectives=objectives,
        resources=resources,
        item_requirements=item_requirements,
        num_points=5
    )

    print(f"  Status: {result['status']}")

    # Check MC output
    assert "monte_carlo_compatible" in result
    mc_output = result["monte_carlo_compatible"]

    assert "decision_variables" in mc_output
    assert "assumptions" in mc_output
    assert "outcome_function" in mc_output
    assert "recommended_next_tool" in mc_output

    print(f"  MC assumptions: {len(mc_output['assumptions'])}")
    print("✓ Test passed\n")
    return result


# Main test runner
if __name__ == "__main__":
    print("=" * 60)
    print("Running Pareto Multi-Objective Optimization Tests")
    print("=" * 60 + "\n")

    test_simple_two_objective_pareto()
    test_pareto_tradeoff_analysis()
    test_pareto_three_objectives()
    test_pareto_with_constraints()
    test_pareto_dominated_solutions_removed()
    test_pareto_mc_compatible_output()

    print("=" * 60)
    print("All Pareto tests passed!")
    print("=" * 60)
