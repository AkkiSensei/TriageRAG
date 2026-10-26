"""Deterministic YAML loader parsing all floating-point numerics to Decimal via string.

Safety Property (Rule R8):
Python floats suffer from binary representation errors (e.g., 84.7 -> 84.7000000000000028...).
This custom loader intercepts YAML float tokens and loads them via Decimal(node.value)
directly from raw text, completely preventing float representation drift.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


class DecimalSafeLoader(yaml.SafeLoader):
    """Custom YAML SafeLoader parsing all numeric floats directly as Decimal."""

    pass


def _decimal_constructor(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> Decimal:
    """Construct Decimal directly from the unparsed scalar string."""
    value_str = loader.construct_scalar(node)
    return Decimal(value_str)


# Intercept standard YAML float tag
DecimalSafeLoader.add_constructor(
    "tag:yaml.org,2002:float",
    _decimal_constructor,
)


def load_yaml_decimal(source: str | Path) -> Any:
    """Load YAML content ensuring all floating-point numbers are exact Decimals.

    Accepts file path or raw YAML string.
    """
    if isinstance(source, Path):
        with source.open("r", encoding="utf-8") as f:
            return yaml.load(f, Loader=DecimalSafeLoader)
    # Check if string is an existing file path
    path = Path(source)
    if path.exists() and path.is_file():
        with path.open("r", encoding="utf-8") as f:
            return yaml.load(f, Loader=DecimalSafeLoader)
    # Otherwise treat as raw YAML string
    return yaml.load(source, Loader=DecimalSafeLoader)
