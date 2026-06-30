"""Exploratory, non-promotable strategy search sandbox infrastructure."""

from .sandbox_evidence import run_sandbox_implementation
from .sandbox_variant_generator import generate_variant_plan

__all__ = ["generate_variant_plan", "run_sandbox_implementation"]
