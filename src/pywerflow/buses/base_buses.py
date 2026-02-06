from dataclasses import dataclass, fields, MISSING
from abc import ABC, abstractmethod

from math import pi
from numbers import Real, Integral
from pywerflow.validation_utils import auto_validate, validator, validate_ranges, validate_types



@dataclass(slots=True, frozen=True)
class BaseBus:
    """
    Base class for all bus types.
    """
    id: int
    """Unique identifier for the bus (integer)."""

    def __post_init__(self):
        auto_validate(self)

    @validator
    def _validate_base_types(self):
        validate_types(self, {"id": Integral})

    @validator
    def _validate_base_ranges(self):
        # IDs no negativos
        validate_ranges(self, {"id": (0, None, "[)")})
