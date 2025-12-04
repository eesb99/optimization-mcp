"""
Tests for optimize_portfolio tool
"""

import sys
sys.path.insert(0, '/Users/thianseongyee/.claude/mcp-servers/optimization-mcp')

try:
    from src.api.portfolio import optimize_portfolio
    CVXPY_AVAILABLE = True
except ImportError:
    CVXPY_AVAILABLE = False
    print("CVXPY not available - skipping portfolio tests")


def test_sharpe_ratio_optimization():
    """Test Sharpe ratio maximization"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    result = optimize_portfolio(
        assets=[
            {"name": "stock_a", "expected_return": 0.12},
            {"name": "stock_b", "expected_return": 0.08},
            {"name": "bond", "expected_return": 0.04}
        ],
        covariance_matrix=[
            [0.04, 0.01, 0.002],  # stock_a variance and covariances
            [0.01, 0.02, 0.001],  # stock_b
            [0.002, 0.001, 0.005]  # bond
        ],
        optimization_objective="sharpe",
        risk_free_rate=0.02
    )

    print("Test: Sharpe Ratio Optimization")
    print(f"Status: {result['status']}")
    print(f"Expected Return: {result.get('expected_return', 'N/A'):.4f}")
    print(f"Portfolio Std: {result.get('portfolio_std', 'N/A'):.4f}")
    print(f"Sharpe Ratio: {result.get('sharpe_ratio', 'N/A'):.4f}")
    print(f"Weights: {result.get('weights', {})}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["is_optimal"] == True
    assert "weights" in result
    assert "sharpe_ratio" in result
    assert "monte_carlo_compatible" in result

    # Weights should sum to 1
    weights_sum = sum(result["weights"].values())
    assert abs(weights_sum - 1.0) < 0.01

    print("✓ Test passed\n")
    return result


def test_min_variance_portfolio():
    """Test variance minimization with target return"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    result = optimize_portfolio(
        assets=[
            {"name": "equity", "expected_return": 0.10},
            {"name": "bonds", "expected_return": 0.05},
            {"name": "cash", "expected_return": 0.02}
        ],
        covariance_matrix=[
            [0.04, 0.01, 0.0],  # equity
            [0.01, 0.01, 0.0],  # bonds
            [0.0, 0.0, 0.0001]  # cash (very low risk)
        ],
        constraints={
            "target_return": 0.06  # Target 6% return
        },
        optimization_objective="min_variance"
    )

    print("Test: Minimum Variance Portfolio")
    print(f"Status: {result['status']}")
    print(f"Expected Return: {result.get('expected_return', 'N/A'):.4f}")
    print(f"Portfolio Variance: {result.get('portfolio_variance', 'N/A'):.6f}")
    print(f"Portfolio Std: {result.get('portfolio_std', 'N/A'):.4f}")
    print(f"Weights: {result.get('weights', {})}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["expected_return"] >= 0.0599  # Meets target (with tolerance)

    # Weights sum to 1
    weights_sum = sum(result["weights"].values())
    assert abs(weights_sum - 1.0) < 0.01

    print("✓ Test passed\n")
    return result


def test_max_return_portfolio():
    """Test return maximization with risk constraint"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    result = optimize_portfolio(
        assets=[
            {"name": "aggressive", "expected_return": 0.15},
            {"name": "moderate", "expected_return": 0.08},
            {"name": "conservative", "expected_return": 0.03}
        ],
        covariance_matrix=[
            [0.09, 0.02, 0.001],  # aggressive (high risk)
            [0.02, 0.02, 0.001],  # moderate
            [0.001, 0.001, 0.001]  # conservative (low risk)
        ],
        constraints={
            "target_risk": 0.03  # Max variance = 0.03
        },
        optimization_objective="max_return"
    )

    print("Test: Maximum Return Portfolio")
    print(f"Status: {result['status']}")
    if result['status'] == 'optimal':
        print(f"Expected Return: {result.get('expected_return'):.4f}")
        print(f"Portfolio Variance: {result.get('portfolio_variance'):.4f}")
        print(f"Weights: {result.get('weights', {})}")
    else:
        print(f"Error: {result.get('error', 'Unknown')}")
        print(f"Message: {result.get('message', 'No message')}")

    # Assertions
    assert result["status"] == "optimal"
    assert result["portfolio_variance"] <= 0.0301  # Within risk limit (with tolerance)

    # Weights sum to 1
    weights_sum = sum(result["weights"].values())
    assert abs(weights_sum - 1.0) < 0.01

    print("✓ Test passed\n")
    return result


def test_portfolio_weight_constraints():
    """Test portfolio with weight limits"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    result = optimize_portfolio(
        assets=[
            {"name": "asset_a", "expected_return": 0.12},
            {"name": "asset_b", "expected_return": 0.09},
            {"name": "asset_c", "expected_return": 0.06}
        ],
        covariance_matrix=[
            [0.04, 0.01, 0.005],
            [0.01, 0.02, 0.003],
            [0.005, 0.003, 0.01]
        ],
        constraints={
            "max_weight": 0.5,  # No asset > 50%
            "min_weight": 0.1,  # No asset < 10%
            "long_only": True   # No short selling
        },
        optimization_objective="sharpe",
        risk_free_rate=0.03
    )

    print("Test: Portfolio with Weight Constraints")
    print(f"Status: {result['status']}")
    print(f"Weights: {result.get('weights', {})}")

    # Assertions
    assert result["status"] == "optimal"

    # Check weight constraints
    for name, weight in result["weights"].items():
        assert weight >= 0.099  # Min weight (with tolerance)
        assert weight <= 0.501  # Max weight (with tolerance)
        assert weight >= 0  # Long only

    # Weights sum to 1
    weights_sum = sum(result["weights"].values())
    assert abs(weights_sum - 1.0) < 0.01

    print("✓ Test passed\n")
    return result


def test_portfolio_infeasible():
    """Test infeasible portfolio (target return too high)"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    result = optimize_portfolio(
        assets=[
            {"name": "asset_a", "expected_return": 0.05},
            {"name": "asset_b", "expected_return": 0.03}
        ],
        covariance_matrix=[
            [0.01, 0.002],
            [0.002, 0.008]
        ],
        constraints={
            "target_return": 0.20  # Impossible - max possible is 0.05
        },
        optimization_objective="min_variance"
    )

    print("Test: Infeasible Portfolio (Target Return Too High)")
    print(f"Status: {result['status']}")
    print(f"Message: {result.get('message', 'N/A')}")

    # Assertions
    assert not result["is_optimal"]
    assert not result["is_feasible"]

    print("✓ Test passed (correctly detected infeasibility)\n")
    return result


def test_portfolio_three_assets():
    """Test realistic 3-asset portfolio"""
    if not CVXPY_AVAILABLE:
        print("CVXPY not installed - skipping test")
        return

    # Realistic example: US Stocks, International Stocks, Bonds
    result = optimize_portfolio(
        assets=[
            {"name": "US_equity", "expected_return": 0.10},
            {"name": "intl_equity", "expected_return": 0.09},
            {"name": "bonds", "expected_return": 0.04}
        ],
        covariance_matrix=[
            [0.0225, 0.0100, 0.0020],  # US equity: 15% std
            [0.0100, 0.0256, 0.0015],  # Intl equity: 16% std
            [0.0020, 0.0015, 0.0036]   # Bonds: 6% std
        ],
        constraints={
            "max_weight": 0.70,  # No more than 70% in one asset
            "min_weight": 0.10,  # At least 10% in each
            "long_only": True
        },
        optimization_objective="sharpe",
        risk_free_rate=0.025
    )

    print("Test: Realistic 3-Asset Portfolio")
    print(f"Status: {result['status']}")
    print(f"Expected Return: {result['expected_return']:.2%}")
    print(f"Portfolio Std (Risk): {result['portfolio_std']:.2%}")
    print(f"Sharpe Ratio: {result['sharpe_ratio']:.3f}")
    print("\nAsset Allocation:")
    for asset in result.get("assets", []):
        print(f"  {asset['name']}: {asset['weight']:.1%} "
              f"(return contrib: {asset['contribution_to_return']:.2%}, "
              f"risk contrib: {asset['risk_contribution_pct']:.1f}%)")

    # Assertions
    assert result["status"] == "optimal"
    assert 0.04 <= result["expected_return"] <= 0.10  # Within asset return range
    assert result["portfolio_std"] > 0
    assert result["sharpe_ratio"] > 0

    # Check weight constraints
    for asset in result["assets"]:
        assert 0.099 <= asset["weight"] <= 0.701

    print("✓ Test passed\n")
    return result


if __name__ == "__main__":
    if not CVXPY_AVAILABLE:
        print("=" * 60)
        print("CVXPY not installed!")
        print("Install with: pip install cvxpy")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("Running Portfolio Optimization Tests")
    print("=" * 60 + "\n")

    test_sharpe_ratio_optimization()
    test_min_variance_portfolio()
    test_max_return_portfolio()
    test_portfolio_weight_constraints()
    test_portfolio_infeasible()
    test_portfolio_three_assets()

    print("=" * 60)
    print("All portfolio tests passed!")
    print("=" * 60)
