
from dataclasses import dataclass
from abc import ABC, abstractmethod
from math import pi
from numbers import Real, Integral, Number
from pywerflow.validation_utils import auto_validate, validator, validate_ranges, validate_types

@dataclass(slots=True, frozen=True, kw_only=True)
class BaseBranch:
    """
    Base class for any branch connecting two buses.
    """
    id: int
    """Unique identifier for the branch."""

    bus1: int
    """ID of the origin bus (From)."""

    bus2: int
    """ID of the destination bus (To)."""


    def __post_init__(self):
        auto_validate(self)

    @validator
    def _validate_base_types(self):
        validate_types(self, {
            "id": Integral, 
            "bus1": Integral, 
            "bus2": Integral})

    @validator
    def _validate_base_ranges(self):
        validate_ranges(self, {
            "id": (0, None, "[)"),
            "bus1": (0, None, "[)"),
            "bus2": (0, None, "[)")
        })

    @validator
    def _validate_topology(self):
        if self.bus1 == self.bus2:
            raise ValueError(f"Topology Error: Branch {self.id} connects Bus {self.bus1} to itself (Self-loop).")



@dataclass(slots=True, frozen=True, kw_only=True)
class InputBranch(BaseBranch, ABC):
    """
    Base class for all input branches.
    Contains operational limits and status.
    """
    
    S_max: float = float("inf")
    """
    Apparent Power Limit (or thermal rating) .
    Used to calculate loading %.
    """

    @validator
    def _validate_input_limits(self):
        validate_types(self, {
            "S_max": Real,
        })
        
        validate_ranges(self, {
            "S_max": (0, None, "(]"), # Smax debe ser > 0 
        })
        
        


@dataclass(slots=True, frozen=True, kw_only=True)
class SolvedBranch(BaseBranch):
    """
    Represents the power flow results across a branch.
    """
    
    # --- Powers at bus1 end ---
    P1: float
    """
    Active Power injected from 'bus1' INTO the branch 
    Positive value means power flows away from bus1 towards the branch.
    """
    
    Q1: float
    """
    Reactive Power injected from 'bus1' INTO the branch 
    Positive value means reactive power flows away from bus1 towards the branch.
    """
    
    S1: float
    """
    Apparent Power Magnitude at 'bus1' 
    Calculated as sqrt(P1^2 + Q1^2).
    """

    # --- Powers at bus2 end ---
    P2: float
    """
    Active Power injected from 'bus2' INTO the branch 
    Positive value means power flows away from bus2 towards the branch.
    """
    
    Q2: float
    """
    Reactive Power injected from 'bus2' INTO the branch 
    Positive value means reactive power flows away from bus2 towards the branch.
    """

    S2: float
    """
    Apparent Power Magnitude at 'bus2' 
    Calculated as sqrt(P2^2 + Q2^2).
    """

    # --- Corrientes Inyectadas ---
    I1: float
    """Current Magnitude flowing from 'bus1' into the branch (p.u.)."""

    phi1: float
    """Current Angle (Phase) at 'bus1' (RADIANS)."""

    I2: float
    """Current Magnitude flowing from 'bus2' into the branch (p.u.)."""

    phi2: float
    """Current Angle (Phase) at 'bus2' (RADIANS)."""

    # --- Losses ---
    P_loss: float
    """Active power losses in the branch  Calculated as P1 + P2."""
    
    Q_loss: float
    """Reactive power losses in the branch  Calculated as Q1 + Q2."""
    
    loading_percent: float
    """
    Loading percentage relative to S limit.
    Range: 0.0 to 100.0 (or higher if overloaded).
    Returns 0.0 if Rate A is infinite.
    """









# @dataclass(slots=True, frozen=True, kw_only=True)
# class PhysicalTransformer(InputBranch): 
#     """
#     Representation of a physical transformer.
#     """

#     Rcc: float
#     """Short-circuit Resistance (ohms)."""

#     Xcc: float
#     """Short-circuit Reactance (ohms)."""

#     nominal_ratio: float
#     """
#     Nominal Ratio (V_nom_1 / V_nom_2).
    
#     This value is obtained from the rated voltages at the terminals.
#     It inherently accounts for the winding configuration (Y-Y, D-D, Y-D, etc.)
#     and is NOT necessarily equal to the physical winding turns ratio (N1/N2).
#     Example: For a 220kV/110kV transformer, this value is 2.0, regardless of 
#     whether it is Y-Y or Y-D connected. 
#     """

#     tap_ratio: float
#     """Current Tap Multiplier Factor (e.g., 1.05)."""

#     shift: float
#     """
#     Phase Shift Angle in RADIANS. 
    
#     It represents the angle of the complex transformation ratio 'a_T'.  
#     a_T = V1 / V2 = |a_T| * e^(j*shift).
    
#     Mathematically: shift = theta_1 - theta_2.
#     """


#     @validator
#     def _validate_types(self):
#         validate_types(self,
#                         {"Rcc": Real,
#                          "Xcc": Real,
#                          "nominal_ratio": Real,
#                          "tap_ratio": Real,
#                          "shift": Real})
    
#     @validator
#     def _validate_ranges(self):
#         validate_ranges(self, 
#                         {"Rcc": (0, None, "[)"),
#                          "nominal_ratio": (0, None, "()"),
#                          "tap_ratio": (0, None, "()"),
#                          "shift": (-pi, pi, "(]"), })


