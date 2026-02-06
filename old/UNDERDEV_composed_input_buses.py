from dataclasses import dataclass, field, MISSING
from abc import ABC, abstractmethod
from pywerflow.buses.bus_types import BusTypes
from pywerflow.buses.input_buses import InputBus

# POR IMPLEMENTAR
@dataclass(slots=True, frozen=True)
class ComposedInputBus(InputBus, ABC):
    loads: list = field(default_factory=list)  # Para que en cada instanciacion se cree una lista nueva
    generators: list = field(default_factory=list)
    g_shunt: float = 0
    b_shunt: float = 0

    def to_primitive(self) -> InputBus:
        """
        Convierte este bus compuesto en uno simple (PV, PQ o Slack)
        sumando sus componentes internos.
        """
        pass

@dataclass(slots=True, frozen=True) 
class ComSlackBus(ComposedInputBus):
    type: BusTypes = BusTypes.SLACK
    """Internal identifier for the bus type. Defaults to SLACK."""

    def to_primitive(self) -> InputBus:
        pass

@dataclass(slots=True, frozen=True)
class ComPVBus(ComposedInputBus):
    type: BusTypes = BusTypes.PV
    """Internal identifier for the bus type. Defaults to PV."""

    def to_primitive(self) -> InputBus:
        pass

@dataclass(slots=True, frozen=True)
class ComPQBus(ComposedInputBus):
    type: BusTypes = BusTypes.PQ
    """Internal identifier for the bus type. Defaults to PQ."""

    def to_primitive(self) -> InputBus:
        pass