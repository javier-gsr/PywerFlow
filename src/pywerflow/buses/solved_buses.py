from dataclasses import dataclass, fields, MISSING
from enum import Enum
from abc import ABC, abstractmethod

from math import pi
from numbers import Real, Integral
from pywerflow.validation_utils import auto_validate, validator, validate_ranges, validate_types
from pywerflow.buses.base_buses import BaseBus
from pywerflow.buses.bus_types import BusTypes

@dataclass(slots=True, frozen=True)
class SolvedBus(BaseBus):
    """
    Represents a bus with a complete, solved state (Results).
    """
    
    # --- 1. ESTADO FUNDAMENTAL (lo que sale de resolver el sistema de ecuaciones no lineal) ---
    V: float
    """Solved Voltage Magnitude (p.u. or V)."""

    theta: float
    """Solved Voltage Angle (RADIANS)."""

    # --- 2. INYECCIONES NETAS (Lo que sale del nudo hacia la red, calculado tras resolver el sistema de ecuaciones) ---
    P_net: float
    """Net Active Power Injection into the grid (Gen - Load)."""

    Q_net: float
    """Net Reactive Power Injection into the grid (Gen - Load)."""
    
    I: float
    """Magnitude of the net current injection at this bus."""

    phi: float
    """Angle of the net current injection (RADIANS)."""


    # --- 3. DATOS DE SHUNTS (Lo que "se come" el nudo internamente) ---
    P_shunt: float
    """Active Power consumed by the shunt conductance G (V^2 * G)."""
    
    Q_shunt: float
    """Reactive Power consumed (if positive) or inyected (if negative) by the shunt susceptance B (-V^2 * B)."""
    

    # --- 4. ESTADO DEL ALGORITMO (La "Historia" de la resolución) ---
    original_type: BusTypes
    """The type the user requested (e.g., PV)."""
    
    final_type: BusTypes
    """The actual type used in the final iteration."""
    

    # --- 5. BANDERAS DE ALERTA (Límites) ---
    is_v_limited: bool
    """True if a PQ bus hit Vmin or Vmax and lost reactive power control."""
    
    is_q_limited: bool
    """True if a PV bus hit Qmin or Qmax and lost voltage control."""


    # --- 6. RESIDUALES (Calidad matemática) ---
    P_mismatch: float
    """Remaining P error at this node (should be close to 0, < tolerance)."""
    
    Q_mismatch: float
    """Remaining Q error at this node (should be close to 0, < tolerance)."""

    V_mismatch: float
    """Remaining V error at this node (should be close to 0, < tolerance)."""
    
    V_base: None|float = None
    """The original Vbase voltage of the bus in kV. Optional"""


    @validator
    def _validate_results(self):
        # Validamos que los resultados tengan sentido físico básico
        validate_types(self, {
            "V": Real, "theta": Real,
            "I": Real, "phi": Real,
            "P_net": Real, "Q_net": Real
        })

        validate_ranges(self, {
            "V": (0, None, "[)"),      # Voltaje > 0
            "I": (0, None, "[)"),      # Corriente >= 0 (Magnitud)
            # theta y phi deberían normalizarse, pero matemáticamente pueden ser cualquier cosa
        })










# @dataclass(slots=True, frozen=True)
# class ComposedSolvedBus(SolvedBus):
#     pass

