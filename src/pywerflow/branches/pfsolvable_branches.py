from dataclasses import dataclass
from abc import ABC, abstractmethod
from math import pi
from cmath import rect, exp
import numpy as np
from numbers import Real, Integral, Number
from pywerflow.validation_utils import auto_validate, validator, validate_ranges, validate_types
from pywerflow.branches.base_branches import BaseBranch, InputBranch

@dataclass(slots=True, frozen=True, kw_only=True)
class PFSolvableBranch(InputBranch, ABC):
    """
    Abstract class for branches that can directly provide an Admittance Matrix (Ybus).
    """
    @abstractmethod
    def get_admittance_matrix(self) -> np.ndarray:
        """
        Returns the 2x2 admittance matrix of the branch.
        Format: np.array([[Y11, Y12], [Y21, Y22]], dtype=complex)
        """
        pass


@dataclass(slots=True, frozen=True, kw_only=True)
class PiLine(PFSolvableBranch):
    """
    Representation of a transmission line modeled using the Pi (π) equivalent circuit.
    """
    R: float
    """Series Resistance."""

    X: float
    """Series Reactance."""

    G: float
    """
    Total Shunt Conductance (G).
    
    NOTE: Input the TOTAL value for the entire line. 
    The solver will automatically apply G/2 at each end of the Pi model.
    """

    B: float
    """
    Total Shunt Susceptance (B).
    
    NOTE: Input the TOTAL value for the entire line. 
    The solver will automatically apply B/2 at each end of the Pi model.
    """

    @validator
    def _validate_piline_data(self):
        # 1. Tipos
        validate_types(self, {"R": Real, "X": Real, "G": Real, "B": Real})
        
        # 2. Rangos (La resistencia suele ser no-negativa, aunque hay excepciones raras)
        validate_ranges(self, {
            "R": (0, None, "[)"), 
            "G": (0, None, "[)") # G shunt >= 0 (pérdidas)
        })
        
        # 3. Física: Una línea no puede tener impedancia 0 (Z=0 -> Y=infinito)
        if abs(self.R) < 1e-9 and abs(self.X) < 1e-9:
            raise ValueError(f"PiLine {self.id}: Series impedance (R+jX) cannot be zero.")

    def get_admittance_matrix(self) -> np.ndarray:
        series_admittance = 1 / (self.R + 1j*self.X)
        shunt_half_admittance = (self.G + 1j*self.B) / 2
        return np.array([
                    [series_admittance + shunt_half_admittance, -series_admittance],
                    [-series_admittance, series_admittance + shunt_half_admittance]
                ], dtype=complex)


@dataclass(slots=True, frozen=True, kw_only=True)
class SimpleTransformer(PFSolvableBranch): 
    """
    Representation of a transformer with Per Unit parameters.
    """
    
    Rcc: float
    """Short-circuit Resistance (p.u.)"""

    Xcc: float
    """Short-circuit Reactance (p.u.)"""

    tap_ratio: float
    """Current Tap Multiplier Factor (e.g., 1.05)."""

    shift: float
    """
    Phase Shift Angle in RADIANS. 
    
    It represents the angle of the complex transformation ratio 'a_T'.  
    a_T = V1 / V2 = |a_T| * e^(j*shift).
    
    Mathematically: shift = theta_1 - theta_2.
    """
    @validator
    def _validate_stransf_data(self):
        validate_types(self,
                        {"Rcc": Real,
                         "Xcc": Real,
                         "tap_ratio": Real,
                         "shift": Real})

        validate_ranges(self,
                        {"Rcc": (0, None, "[)"),
                         "tap_ratio": (0, None, "()"),
                         "shift": (-pi, pi, "(]"), })
        
        # Validación de cortocircuito
        if abs(self.Rcc) < 1e-9 and abs(self.Xcc) < 1e-9:
             raise ValueError(f"SimpleTransformer {self.id}: Short-circuit impedance cannot be zero.")
    
    def get_admittance_matrix(self) -> np.ndarray:
        Ycc = 1/(self.Rcc + 1j*self.Xcc)
        complex_ratio = rect(self.tap_ratio, self.shift)
        return np.array([
                [   Ycc/self.tap_ratio**2,     -Ycc/complex_ratio.conjugate()],
                [  -Ycc/complex_ratio,          Ycc                         ]
            ], dtype=complex)


# EXPERIMENTAL!!!
@dataclass(slots=True, frozen=True, kw_only=True)
class PiTransformer(PFSolvableBranch): 
    """
    General model representing a Pi-Line in series with an Ideal Transformer 
    located at the 'from' bus side.
    
    This model supports:
    - Series Impedance (R + jX)
    - Shunt Admittance (G + jB) -> Applied as G/2, B/2 in the Pi Line after the ideal transformer.
    - Off-nominal Tap Ratio (tau)
    - Phase Shift (shift)
    """
    
    R: float
    X: float
    G: float
    B: float
    
    tap_ratio: float
    """Magnitude of the transformation ratio (tau)."""

    shift: float
    """Phase shift angle in RADIANS."""


    @validator
    def _validate_pitransf_data(self):
        validate_types(self,
                        {"R": Real,
                         "X": Real,
                         "G": Real,
                         "B": Real,
                         "tap_ratio": Real,
                         "shift": Real})
                
        validate_ranges(self, 
                        {"R": (0, None, "[)"),
                         "G": (0, None, "[)"),
                         "tap_ratio": (0, None, "()"),
                         "shift": (-pi, pi, "(]"), })
        
        # Validación de cortocircuito
        if abs(self.R) < 1e-9 and abs(self.X) < 1e-9:
             raise ValueError(f"PiTransformer {self.id}: Short-circuit impedance cannot be zero.")
        

    def get_admittance_matrix(self) -> np.ndarray:
        # 1. Admitancias básicas de la línea Pi
        # Serie: y_s = 1 / (R + jX)
        denom = self.R + 1j * self.X
        if abs(denom) < 1e-12:
            raise ValueError(f"Branch {self.id}: Z series is close to 0.")
        
        y_s = 1.0 / denom
        
        # Shunt (Media admitancia en cada extremo de la parte Pi)
        y_sh_half = (self.G + 1j * self.B) / 2.0

        # 2. Relación de transformación compleja
        # a = tap * e^(j * shift)
        # Usamos cmath o numpy para la exponencial compleja
        a = self.tap_ratio * exp(1j * self.shift)
        
        # 3. Construcción de la matriz Y primitiva (Generalizada)
        # El trafo ideal está en el lado 1 (From).
        
        # Y11 = (ys + y_sh_half) / |a|^2
        Y11 = (y_s + y_sh_half) / (abs(a)**2)
        
        # Y12 = -ys / conj(a)
        Y12 = -y_s / a.conjugate()
        
        # Y21 = -ys / a
        Y21 = -y_s / a
        
        # Y22 = ys + y_sh_half (El lado 'to' no ve el tap directamente)
        Y22 = y_s + y_sh_half
        
        return np.array([
            [Y11, Y12],
            [Y21, Y22]
        ], dtype=complex)



@dataclass(slots=True, frozen=True, kw_only=True)
class RawBranch(PFSolvableBranch):
    """
    Branch defined directly by its primitive nodal admittance matrix elements (2x2).
    
    The relationship is defined as:  
    ```
    [ I_1 ]     [ Y_11  Y_12 ]     [ V_1 ]
    [ I_2 ]  =  [ Y_21  Y_22 ]  *  [ V_2 ]
    ```
    NOTE: I_1 and I_2 represent currents flowing INTO the branch from bus 1 
    and bus 2 respectively (Injections).  
    """
    
    Y_11: complex
    """Self-admittance at the 'bus1' node."""
    
    Y_12: complex
    """Transfer admittance from 'bus1' to 'bus2'."""
    
    Y_21: complex
    """Transfer admittance from 'bus2' to 'bus1'."""
    
    Y_22: complex
    """Self-admittance at the 'bus2' node."""


    def get_admittance_matrix(self) -> np.ndarray:
        # Devuelve la matriz NumPy construida con los elementos raw
        return np.array([
            [self.Y_11, self.Y_12],
            [self.Y_21, self.Y_22]
        ], dtype=complex)


    @classmethod
    def from_numpy_matrix(cls, id: int, bus1: int, bus2: int, Y_matrix: np.ndarray, S_max: float = float("inf")):
        """
        Helper method to create a RawBranch instance from a 2x2 NumPy matrix.
        
        Args:
            id (int): Branch ID.
            bus1 (int): ID of bus 1.
            bus2 (int): ID of bus 2.
            Y_matrix (np.ndarray): A complex 2x2 numpy matrix.
        """
        # Verificamos dimensiones
        if Y_matrix.shape != (2, 2):
            raise ValueError("Admittance Matrix must be 2x2")
        
        # Extraemos valores usando indexación estándar de matriz
        return cls(
            id=id, bus1=bus1, bus2=bus2, S_max=S_max,
            Y_11=complex(Y_matrix[0, 0]),
            Y_12=complex(Y_matrix[0, 1]),
            Y_21=complex(Y_matrix[1, 0]),
            Y_22=complex(Y_matrix[1, 1])
        )
    
