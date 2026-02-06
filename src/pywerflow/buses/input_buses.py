from dataclasses import dataclass, fields, MISSING
from abc import ABC, abstractmethod

from math import pi
from numbers import Real, Integral
from pywerflow.validation_utils import auto_validate, validator, validate_ranges, validate_types
from pywerflow.buses.base_buses import BaseBus
from pywerflow.buses.bus_types import BusTypes


@dataclass(slots=True, frozen=True, kw_only=True)
class InputBus(BaseBus, ABC):
    """
    Base class for defining bus data for power flow calculations.
    """  
    type: BusTypes

    V_base: None|float = None
    """The base voltage of the bus in kV. Optional"""


    @validator
    def validate_bustypes(self):
        """
        Verify that the value of the type attribute is the one specified by default.

        It inspects the class definition to check if the 'type' field has a 
        specific default value (e.g., BusTypes.SLACK in SlackBus). 
        If a default exists, it enforces that the instance's 'type' matches it.

        Raises:
            TypeError: If the instantiated type does not match the class's required default type.
        """
        # 1. Obtenemos los metadatos de los campos de ESTA clase (self)
        cls_fields = fields(self)
        
        # 2. Buscamos el campo llamado "type"
        # (Usamos next con default None por si acaso alguna clase hija no tuviera 'type')
        type_field = next((f for f in cls_fields if f.name == 'type'), None)

        # 3. Si existe el campo 'type' Y tiene un valor por defecto definido...
        if type_field and type_field.default is not MISSING:

            expected_type = type_field.default
            
            # 4. Comparamos el valor real (self.type) con el esperado (default)
            if self.type != expected_type:
                raise TypeError(
                    f"Integrity Error: {self.__class__.__name__} must be of type "
                    f"'{expected_type}', but got '{self.type}'."
                )

    @abstractmethod
    def get_shunt_admittance(self) -> complex:
        """
        Returns the complex shunt admittance of the bus.
        """
        pass
    
    @validator
    def _validate_pv_data(self):

        if self.V_base is None: # Si es None se omite la comprobación
            return
        
        validate_types(self, {
            "V_base": Real,
        })
    
        validate_ranges(self, {
            "V_base": (0, None, "[)"),
        })

        
@dataclass(slots=True, frozen=True, kw_only=True)
class SlackBus(InputBus):
    """
    Represents a Slack (Swing) bus.
    Acts as the angular reference for the system.
    """
    
    V: float
    """
    Fixed Voltage Magnitude.
    Units: p.u.
    """

    theta: float
    """
    Fixed Voltage Angle.
    Units: RADIANS.
    """

    G_shunt: float = 0

    B_shunt: float = 0

    # Pmin: float = float("-inf")

    # Pmax: float = float("inf")

    # Qmin: float = float("-inf")

    # Qmax: float = float("inf")

    type: BusTypes = BusTypes.SLACK
    """Internal identifier for the bus type. Must be SLACK."""

    @validator
    def _validate_slack_data(self):
        validate_types(self, {
            "V": Real, "theta": Real, "type": BusTypes,
            "G_shunt": Real, "B_shunt": Real,
            # "Pmin": Real, "Pmax": Real,
            # "Qmin": Real, "Qmax": Real
        })
        
        validate_ranges(self, {
            "V": (0, None, "[)"),         # V >= 0
            "theta": (-pi, pi, "(]"),     # -pi < theta <= pi
            "G_shunt": (0, None, "[)"),   # Conductancia física >= 0 (Consumo)
        })

        # # Consistencia de limites
        # if self.Pmin > self.Pmax:
        #     raise ValueError(f"Range Error in SlackBus {self.id}: Pmin ({self.Pmin}) cannot be greater than Pmax ({self.Pmax}).")
        
        # if self.Qmin > self.Qmax:
        #     raise ValueError(f"Range Error in SlackBus {self.id}: Qmin ({self.Qmin}) cannot be greater than Qmax ({self.Qmax}).")

    def get_shunt_admittance(self) -> complex:
        """
        Returns the complex shunt admittance of the bus.
        """
        return (self.G_shunt + 1j*self.B_shunt)


@dataclass(slots=True, frozen=True, kw_only=True)
class PVBus(InputBus):
    """
    Represents a PV bus where Active Power and Voltage are controlled.
    """
    
    P: float
    """
    Fixed Active Power Injection.
    Units: p.u.
    Sign convention: Generation is positive (+), Consumption is negative (-).
    """

    V: float
    """
    Fixed Voltage Magnitude setpoint.
    Units: p.u..
    """

    G_shunt: float = 0

    B_shunt: float = 0

    Qmin: float = float("-inf")

    Qmax: float = float("inf")
    
    theta_guess: float = 0

    type: BusTypes = BusTypes.PV
    """Internal identifier for the bus type. Defaults to PV."""

    @validator
    def _validate_pv_data(self):
        validate_types(self, {
            "P": Real, "V": Real, "type": BusTypes,
            "G_shunt": Real, "B_shunt": Real,
            "Qmin": Real, "Qmax": Real,
            "theta_guess": Real
        })
        
        validate_ranges(self, {
            "V": (0, None, "[)"),
            "G_shunt": (0, None, "[)"), 
            "theta_guess": (-pi, pi, "(]"),
        })

        # Consistencia de limites
        if self.Qmin > self.Qmax:
            raise ValueError(f"Range Error in PVBus {self.id}: Qmin ({self.Qmin}) cannot be greater than Qmax ({self.Qmax}).")

    def get_shunt_admittance(self) -> complex:
        """
        Returns the complex shunt admittance of the bus.
        """
        return (self.G_shunt + 1j*self.B_shunt)


@dataclass(slots=True, frozen=True, kw_only=True)
class PQBus(InputBus):
    """
    Represents a PQ bus where Active and Reactive power are fixed.
    """
    
    P: float
    """
    Active Power Injection.
    Units: p.u.
    Sign convention: Generation is positive (+), Load/Consumption is negative (-).
    """

    Q: float
    """
    Reactive Power Injection.
    Units: p.u.
    Sign convention: Injection/Capacitive (+), Consumption/Inductive (-).
    """
    G_shunt: float = 0

    B_shunt: float = 0

    Vmin: float = 0

    Vmax: float = float("inf")

    V_guess: float = 1

    theta_guess: float = 0

    type: BusTypes = BusTypes.PQ
    """Internal identifier for the bus type. Defaults to PQ."""


    @validator
    def _validate_pq_data(self):
        validate_types(self, {
            "P": Real, "Q": Real, "type": BusTypes,
            "G_shunt": Real, "B_shunt": Real,
            "Vmin": Real, "Vmax": Real,
            "theta_guess": Real,
            "V_guess": Real
            
        })

        validate_ranges(self, {
            "G_shunt": (0, None, "[)"),
            "Vmin": (0, None, "[)"), 
            "Vmax": (0, None, "[)"),
            "theta_guess": (-pi, pi, "(]"),
            "V_guess": (0, None, "[)"),
        })

        # Consistencia de limites
        if self.Vmin > self.Vmax:
            raise ValueError(f"Range Error in PQBus {self.id}: Vmin ({self.Vmin}) cannot be greater than Vmax ({self.Vmax}).")

    def get_shunt_admittance(self) -> complex:
        """
        Returns the complex shunt admittance of the bus.
        """
        return (self.G_shunt + 1j*self.B_shunt)

   
   
   
   
   
   
   
"""
   
   
   
    def from_physical_powers()
        

import numpy as np

def bus_from_mix_data(
    id: int,
    type: BusTypes,
    P_MW: float|None = None,
    Q_MVAr: float|None = None,
    V_KV: float|None = None,
    theta_abs: float|None = None,
    G_ohms: float|None = None,
    B_ohms: float|None = None,
    S_base_MVA: float|None = None,
    V_base_KV: float|None = None,
    P_pu: float|None = None,
    theta_pu: float|None = None,
    Q_pu: float|None = None,
    V_pu: float|None = None,
    G_pu: float|None = None,
    B_pu: float|None = None,
    ):
    # Esta funcion permite definir un objeto Bus usando datos "mixtos"
    pass


def buses_from_mix_data( bus_data: np.ndarray | list[list], 
                        S_base: float,
                        cols = None 
                        ):
    # V y theta se interpretan como initial guess salvo en PV (solo V) y Slack (Solo V o Q
    # Solo hay ciertas "palabras" permitidas en cols y algunas son OBLIGATORIAS, otras OPCIONALES
    # Pueden meterse como ndarray 

    # La S base me la das por separado y luego yo te permito construir una "red" con esa Sbase
    pass

#Ejemplo:
buses_from_mix_data(
    bus_data = np.array(),
    cols = ["id", "type", "V", "Q", "theta", "Pgen", "Pload"],
)

# Keys permitidas


bus_from_mix_data(
    id=1,
    type=BusTypes.PQBus,
    Q_MVAr=1,
    P_MW=1,
    theta_abs=1,   
)
"""