# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for v2.6.0
- Monte Carlo integration patterns documentation
- Schema Grammar reference section
- Quick Start in 60 seconds guide
- Example JSON payloads in docs/examples/

## [2.5.1] - 2025-12-06

### Fixed
- Cross-platform path handling using pathlib (Windows + Unix compatible)
- Item universe consistency validation (prevents typo bugs in item names)
- Removed misleading test claims from README (no public test directory)

### Changed
- Logging now configurable via `OPT_MCP_LOG_PATH` environment variable
- Logging includes StreamHandler for stdout visibility
- Requirements pinned to ranges (>=X,<Y) for better reproducibility

### Added
- Comprehensive scalability guidelines for all 9 tools
- Performance characteristics documentation
- "When You Hit Scale Limits" guidance section

### Documentation
- Removed test badge and test count claims from README
- Added scale limits for all tools (items, resources, time horizons)
- Changed "Battle-Tested: 51/51 passing" to "Production Ready: Internally tested"

## [2.5.0] - 2025-12-04

### Added
- `optimize_network_flow` tool - Network flow optimization with NetworkX (5000x speedup)
- `optimize_pareto` tool - Pareto frontier generation for multi-objective
- `optimize_stochastic` tool - 2-stage stochastic programming
- `optimize_column_gen` tool - Column generation framework
- NetworkXSolver backend - Specialized network flow algorithms
- Network validation in DataConverter
- Pareto frontier visualization and sketchnote

### Performance
- Network flow: 5000x faster than general LP for pure network problems
- All tools handle 1K-10K variable scale efficiently
- Pareto frontier: 20-100 points in 10-30 seconds

### Testing
- 17 new tests added (8 network flow + 6 Pareto + 3 stochastic)
- Total: 51/51 tests passing (internal)

## [2.4.0] - 2025-12-04

### Added
- `optimize_stochastic` tool - 2-stage stochastic programming
- Extensive form implementation for scenario-based decisions
- Expected value and worst-case risk measures
- VSS (Value of Stochastic Solution) calculations
- 3 comprehensive tests

### Features
- Sequential decision modeling (order now, adjust later)
- Scenario-based uncertainty representation
- Recourse decisions after information revelation

## [2.3.0] - 2025-12-04

### Added
- `optimize_pareto` tool - Pareto frontier generation
- Weighted sum scalarization for multi-objective
- Knee point recommendation algorithm
- Trade-off analysis between objectives
- Mixed sense support (maximize + minimize simultaneously)
- Dominated solution filtering
- 6 comprehensive tests

### Features
- Generate 20-100 non-dominated solutions
- Explore full trade-off space
- Identify best-balanced solution automatically

## [2.2.0] - 2025-12-04

### Added
- `optimize_network_flow` tool - Network flow optimization
- NetworkXSolver class - Specialized network flow backend
- Network structure validation in DataConverter
- Support for min-cost flow, max-flow, assignment problems
- Bottleneck analysis for capacity-constrained edges
- 8 comprehensive tests
- networkx>=3.0 dependency

### Performance
- 5000x+ speedup for network flow problems vs general LP
- Small networks (<100 nodes): <0.1 seconds
- Large networks (1000-10000 nodes): <10 seconds

### Technical
- Exploits network structure (incidence matrix)
- Network simplex algorithm for min-cost flow
- Edmonds-Karp algorithm for max-flow

## [2.1.0] - 2025-12-02

### Added
- `optimize_execute` tool - Custom optimization with auto-solver selection
- Flexible dict-based problem specification
- Auto-detection of problem type (LP/MIP/QP/nonlinear)
- Solver override capability
- 5 comprehensive tests

### Features
- Power user tool for custom formulations
- Escape hatch for problems not fitting standard templates
- Auto-selects best solver (PuLP/SciPy/CVXPY)
- Flexible variable types (continuous, integer, binary)

## [2.0.0] - 2025-12-02

### Added
- Multi-objective optimization (weighted scalarization)
- CVXPYSolver for quadratic programming
- `optimize_portfolio` tool (Sharpe, variance, return objectives)
- `optimize_schedule` tool (dependencies, makespan, critical path)
- Enhanced constraints (conditional, disjunctive, mutex)
- Risk contribution analysis for portfolios
- Critical path detection for schedules
- 26 new tests
- Comprehensive documentation

### Changed
- `optimize_allocation` now supports multi-objective via "functions" key
- CVXPY solver selection uses SCS for robustness
- README reorganized with 4 tool sections

### Features
- Balance multiple competing objectives
- Portfolio risk-return optimization
- Project scheduling with resource constraints
- If-then, OR, XOR constraint logic

## [1.0.0] - 2025-12-01

### Added
- Initial release
- `optimize_allocation` tool - Resource allocation
- `optimize_robust` tool - Robust optimization
- PuLP and SciPy solvers
- Monte Carlo integration (3 modes: percentile, expected, scenarios)
- Basic test suite
- Installation and usage documentation

### Features
- Resource allocation under constraints
- Robust optimization across scenarios
- Multi-resource support
- Shadow price analysis

---

## Version Numbering

- **Major (X.0.0)**: Breaking API changes
- **Minor (0.X.0)**: New features, backward compatible
- **Patch (0.0.X)**: Bug fixes, documentation

## Links

- [Full Documentation](README.md)
- [Installation Guide](docs/INSTALLATION.md)
- [GitHub Repository](https://github.com/eesb99/optimization-mcp)
