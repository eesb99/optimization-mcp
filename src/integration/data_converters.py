"""
Data Converters

Utilities for converting between different data formats:
- JSON/dict validation
- Type conversions
- Format standardization
"""

from typing import Dict, List, Any, Optional, Union
import numpy as np


class DataConverter:
    """
    Handles data format conversions and validation.

    Ensures data passed between tools is properly formatted and typed.
    """

    @staticmethod
    def validate_objective_spec(objective: Dict[str, Any], require_values: bool = True) -> bool:
        """
        Validate objective function specification.

        Args:
            objective: Dict with 'items', 'sense' keys
            require_values: If True, require 'value' for each item (default: True)
                          If False, only require 'name' (for robust optimization where values come from scenarios)

        Returns:
            True if valid

        Raises:
            ValueError: If specification is invalid
        """
        required_keys = ["items", "sense"]
        for key in required_keys:
            if key not in objective:
                raise ValueError(f"Objective missing required key: '{key}'")

        if not isinstance(objective["items"], list):
            raise ValueError("Objective 'items' must be a list")

        valid_senses = ["minimize", "maximize"]
        if objective["sense"] not in valid_senses:
            raise ValueError(
                f"Objective 'sense' must be one of: {valid_senses}"
            )

        # Validate each item
        for i, item in enumerate(objective["items"]):
            if not isinstance(item, dict):
                raise ValueError(f"Item {i} must be a dict")

            if "name" not in item:
                raise ValueError(f"Item {i} must have 'name'")

            if require_values and "value" not in item:
                raise ValueError(f"Item {i} must have 'value'")

        return True

    @staticmethod
    def validate_multi_objective_spec(objective: Dict[str, Any]) -> bool:
        """
        Validate multi-objective specification.

        Supports two formats:
        1. Single objective (backward compatible):
           {"items": [...], "sense": "maximize"}

        2. Multi-objective (new):
           {"sense": "maximize",
            "functions": [
              {"name": "profit", "items": [...], "weight": 0.7},
              {"name": "sustainability", "items": [...], "weight": 0.3}
            ]}

        Args:
            objective: Objective specification

        Returns:
            True if valid

        Raises:
            ValueError: If specification is invalid
        """
        # Check if multi-objective format
        if "functions" in objective:
            # Multi-objective validation
            if "sense" not in objective:
                raise ValueError("Multi-objective missing required key: 'sense'")

            valid_senses = ["minimize", "maximize"]
            if objective["sense"] not in valid_senses:
                raise ValueError(
                    f"Objective 'sense' must be one of: {valid_senses}"
                )

            if not isinstance(objective["functions"], list):
                raise ValueError("Multi-objective 'functions' must be a list")

            if len(objective["functions"]) < 2:
                raise ValueError(
                    "Multi-objective requires at least 2 functions. "
                    f"Got {len(objective['functions'])}. "
                    "For single objective, use standard format."
                )

            # Validate weights sum to 1.0
            total_weight = sum(func.get("weight", 0) for func in objective["functions"])
            if abs(total_weight - 1.0) > 0.01:
                raise ValueError(
                    f"Multi-objective function weights must sum to 1.0. "
                    f"Got {total_weight:.4f}"
                )

            # Validate each function
            for i, func in enumerate(objective["functions"]):
                if not isinstance(func, dict):
                    raise ValueError(f"Function {i} must be a dict")

                # Check required keys
                required_func_keys = ["name", "items", "weight"]
                for key in required_func_keys:
                    if key not in func:
                        raise ValueError(
                            f"Function {i} missing required key: '{key}'"
                        )

                # Validate name
                if not isinstance(func["name"], str):
                    raise ValueError(f"Function {i} 'name' must be a string")

                # Validate weight
                if not isinstance(func["weight"], (int, float)):
                    raise ValueError(
                        f"Function {i} 'weight' must be a number"
                    )

                if func["weight"] < 0 or func["weight"] > 1:
                    raise ValueError(
                        f"Function {i} 'weight' must be between 0 and 1. "
                        f"Got {func['weight']}"
                    )

                # Validate items
                if not isinstance(func["items"], list):
                    raise ValueError(f"Function {i} 'items' must be a list")

                for j, item in enumerate(func["items"]):
                    if not isinstance(item, dict):
                        raise ValueError(
                            f"Function {i}, item {j} must be a dict"
                        )
                    if "name" not in item or "value" not in item:
                        raise ValueError(
                            f"Function {i}, item {j} must have 'name' and 'value'"
                        )
                    if not isinstance(item["value"], (int, float)):
                        raise ValueError(
                            f"Function {i}, item {j} 'value' must be a number"
                        )

        else:
            # Single objective - use existing validation
            DataConverter.validate_objective_spec(objective)

        return True

    @staticmethod
    def validate_resources_spec(resources: Dict[str, Dict[str, float]]) -> bool:
        """
        Validate resources specification.

        Args:
            resources: Dict mapping resource names to {'total': float}

        Returns:
            True if valid

        Raises:
            ValueError: If specification is invalid
        """
        if not isinstance(resources, dict):
            raise ValueError("Resources must be a dict")

        for resource_name, resource_spec in resources.items():
            if not isinstance(resource_spec, dict):
                raise ValueError(f"Resource '{resource_name}' spec must be a dict")

            if "total" not in resource_spec:
                raise ValueError(f"Resource '{resource_name}' missing 'total'")

            if not isinstance(resource_spec["total"], (int, float)):
                raise ValueError(
                    f"Resource '{resource_name}' total must be a number"
                )

            if resource_spec["total"] < 0:
                raise ValueError(
                    f"Resource '{resource_name}' total must be non-negative"
                )

        return True

    @staticmethod
    def validate_item_requirements(
        items: List[Dict[str, Any]],
        resources: Dict[str, Any]
    ) -> bool:
        """
        Validate item requirements against resources.

        Args:
            items: List of item requirement dicts
            resources: Resource availability dict

        Returns:
            True if valid

        Raises:
            ValueError: If specification is invalid
        """
        resource_names = set(resources.keys())

        for i, item in enumerate(items):
            if "name" not in item:
                raise ValueError(f"Item {i} missing 'name'")

            # Check that item requirements reference valid resources
            for resource_name, amount in item.items():
                if resource_name == "name":
                    continue

                if resource_name not in resource_names:
                    raise ValueError(
                        f"Item '{item['name']}' references unknown resource '{resource_name}'. "
                        f"Available resources: {resource_names}"
                    )

                if not isinstance(amount, (int, float)):
                    raise ValueError(
                        f"Item '{item['name']}' requirement for '{resource_name}' "
                        f"must be a number"
                    )

                if amount < 0:
                    raise ValueError(
                        f"Item '{item['name']}' requirement for '{resource_name}' "
                        f"must be non-negative"
                    )

        return True

    @staticmethod
    def normalize_variable_names(names: List[str]) -> List[str]:
        """
        Normalize variable names for solver compatibility.

        Replaces spaces, special characters with underscores.

        Args:
            names: List of variable names

        Returns:
            List of normalized names
        """
        normalized = []
        for name in names:
            # Replace spaces and special chars with underscore
            normalized_name = "".join(
                c if c.isalnum() else "_"
                for c in str(name)
            )
            # Remove leading/trailing underscores
            normalized_name = normalized_name.strip("_")
            # Ensure doesn't start with a digit
            if normalized_name and normalized_name[0].isdigit():
                normalized_name = "var_" + normalized_name

            normalized.append(normalized_name)

        return normalized

    @staticmethod
    def convert_to_float(value: Any) -> float:
        """
        Safely convert value to float.

        Args:
            value: Value to convert

        Returns:
            Float value

        Raises:
            ValueError: If conversion fails
        """
        try:
            return float(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Cannot convert '{value}' to float: {e}")

    @staticmethod
    def convert_solution_to_dict(
        variable_names: List[str],
        values: Union[np.ndarray, List[float]]
    ) -> Dict[str, float]:
        """
        Convert array of values to dict mapping names to values.

        Args:
            variable_names: List of variable names
            values: Array or list of values

        Returns:
            Dict mapping names to values
        """
        if len(variable_names) != len(values):
            raise ValueError(
                f"Length mismatch: {len(variable_names)} names, {len(values)} values"
            )

        return {
            name: float(value)
            for name, value in zip(variable_names, values)
        }

    @staticmethod
    def merge_dicts_safely(
        base: Dict[str, Any],
        overlay: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two dicts, ensuring no key conflicts.

        Args:
            base: Base dictionary
            overlay: Dictionary to merge in

        Returns:
            Merged dictionary

        Raises:
            ValueError: If keys conflict
        """
        conflicts = set(base.keys()) & set(overlay.keys())
        if conflicts:
            raise ValueError(
                f"Key conflicts when merging dicts: {conflicts}"
            )

        return {**base, **overlay}

    @staticmethod
    def extract_numeric_fields(
        data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract only numeric fields from a dict.

        Args:
            data: Input dictionary

        Returns:
            Dict with only numeric key-value pairs
        """
        return {
            k: v for k, v in data.items()
            if isinstance(v, (int, float, np.number))
        }

    @staticmethod
    def validate_percentile_string(percentile: str) -> str:
        """
        Validate and normalize percentile string.

        Args:
            percentile: Percentile string (e.g., "p50", "P90")

        Returns:
            Normalized percentile string (lowercase)

        Raises:
            ValueError: If invalid percentile
        """
        valid = ["p10", "p25", "p50", "p75", "p90"]
        normalized = percentile.lower()

        if normalized not in valid:
            raise ValueError(
                f"Invalid percentile '{percentile}'. Must be one of: {valid}"
            )

        return normalized

    @staticmethod
    def validate_mc_integration_mode(mode: str) -> str:
        """
        Validate Monte Carlo integration mode.

        Args:
            mode: Integration mode string

        Returns:
            Validated mode string (lowercase)

        Raises:
            ValueError: If invalid mode
        """
        valid_modes = ["percentile", "expected", "scenarios"]
        normalized = mode.lower()

        if normalized not in valid_modes:
            raise ValueError(
                f"Invalid MC integration mode '{mode}'. "
                f"Must be one of: {valid_modes}"
            )

        return normalized

    @staticmethod
    def validate_bounds(
        bounds: Dict[str, tuple],
        variable_names: List[str]
    ) -> bool:
        """
        Validate variable bounds specification.

        Args:
            bounds: Dict mapping variable names to (lower, upper) tuples
            variable_names: List of all variable names

        Returns:
            True if valid

        Raises:
            ValueError: If bounds are invalid
        """
        for var_name, (lb, ub) in bounds.items():
            if var_name not in variable_names:
                raise ValueError(
                    f"Bounds specified for unknown variable '{var_name}'. "
                    f"Known variables: {variable_names}"
                )

            if lb is not None and ub is not None:
                if lb > ub:
                    raise ValueError(
                        f"Variable '{var_name}': lower bound ({lb}) > upper bound ({ub})"
                    )

            if lb is not None and not isinstance(lb, (int, float)):
                raise ValueError(
                    f"Variable '{var_name}': lower bound must be numeric"
                )

            if ub is not None and not isinstance(ub, (int, float)):
                raise ValueError(
                    f"Variable '{var_name}': upper bound must be numeric"
                )

        return True

    @staticmethod
    def validate_network_structure(network: Dict[str, Any]) -> bool:
        """
        Validate network flow problem specification.

        Args:
            network: Dict with 'nodes' and 'edges' keys

        Returns:
            True if valid

        Raises:
            ValueError: If specification is invalid
        """
        # Check required keys
        if 'nodes' not in network:
            raise ValueError("Network missing required key: 'nodes'")
        if 'edges' not in network:
            raise ValueError("Network missing required key: 'edges'")

        nodes = network['nodes']
        edges = network['edges']

        if not isinstance(nodes, list):
            raise ValueError("Network 'nodes' must be a list")
        if not isinstance(edges, list):
            raise ValueError("Network 'edges' must be a list")

        # Validate nodes
        node_ids = set()
        total_supply = 0.0
        total_demand = 0.0

        for i, node in enumerate(nodes):
            if not isinstance(node, dict):
                raise ValueError(f"Node {i} must be a dict")
            if 'id' not in node:
                raise ValueError(f"Node {i} missing required key: 'id'")

            node_id = node['id']
            if node_id in node_ids:
                raise ValueError(f"Duplicate node ID: '{node_id}'")
            node_ids.add(node_id)

            # Track supply/demand balance
            supply = node.get('supply', 0.0)
            demand = node.get('demand', 0.0)
            total_supply += supply
            total_demand += demand

        # Check flow conservation (supply should equal demand)
        net_balance = total_supply - total_demand
        if abs(net_balance) > 1e-6:
            raise ValueError(
                f"Flow conservation violated: "
                f"total_supply ({total_supply}) != total_demand ({total_demand}), "
                f"net_balance = {net_balance}"
            )

        # Validate edges
        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                raise ValueError(f"Edge {i} must be a dict")

            required_edge_keys = ['from', 'to']
            for key in required_edge_keys:
                if key not in edge:
                    raise ValueError(f"Edge {i} missing required key: '{key}'")

            from_node = edge['from']
            to_node = edge['to']

            # Check that nodes exist
            if from_node not in node_ids:
                raise ValueError(
                    f"Edge {i} references unknown 'from' node: '{from_node}'"
                )
            if to_node not in node_ids:
                raise ValueError(
                    f"Edge {i} references unknown 'to' node: '{to_node}'"
                )

            # Validate optional numeric fields
            if 'capacity' in edge and not isinstance(edge['capacity'], (int, float)):
                raise ValueError(f"Edge {i} 'capacity' must be numeric")
            if 'cost' in edge and not isinstance(edge['cost'], (int, float)):
                raise ValueError(f"Edge {i} 'cost' must be numeric")

        return True


# Convenience functions

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert to float with fallback.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def dict_to_list(d: Dict[str, float], keys: List[str]) -> List[float]:
    """
    Convert dict to list in specified key order.

    Args:
        d: Dictionary
        keys: Ordered list of keys

    Returns:
        List of values in key order
    """
    return [d[key] for key in keys]


def list_to_dict(lst: List[float], keys: List[str]) -> Dict[str, float]:
    """
    Convert list to dict with specified keys.

    Args:
        lst: List of values
        keys: List of keys

    Returns:
        Dictionary mapping keys to values
    """
    if len(lst) != len(keys):
        raise ValueError(
            f"Length mismatch: {len(lst)} values, {len(keys)} keys"
        )
    return dict(zip(keys, lst))
