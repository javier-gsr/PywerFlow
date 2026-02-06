from pywerflow.buses.input_buses import InputBus, SlackBus
from pywerflow.branches.base_branches import InputBranch
from pywerflow.buses.bus_types import BusTypes
from pywerflow.validation_utils import auto_validate, validator

class BaseNetwork:

    def __init__(self, buses: list[InputBus], branches: list[InputBranch]):
        self._buses: dict[int, InputBus] = {}
        self._branches: dict[int, InputBranch] = {}
        for bus in buses:
            if bus.id in self._buses:
                raise ValueError(f"Duplicate Bus ID detected: {bus.id}")
            self._buses[bus.id] = bus
        for branch in branches:
            if branch.id in self._branches:
                raise ValueError(f"Duplicate Branch ID detected: {branch.id}")
            self._branches[branch.id] = branch

        # Validaciones post inicializacion
        auto_validate(self)


    @validator
    def _validate_types(self):
        # Validar que los tipos de lineas y buses son los permitidos
        for id, bus in self._buses.items():
            if not isinstance(bus, InputBus):
                raise TypeError(f"Invalid object found in buses. Bus ID '{id}' is of type '{type(bus).__name__}', expected instance of 'InputBus'.")

            if not isinstance(bus.type, BusTypes):
                raise ValueError(f"Unknown or Invalid Bus Type for Bus ID {bus.id}: {bus.type}. Attribute 'type' must be a valid 'BusTypes' Enum member.")

        for id, branch in self._branches.items():
            if not isinstance(branch, InputBranch): # La fisica no permite trafos pu, la pu no permite trafos phisical (extienden el metodo)
                raise TypeError(f"Invalid object found in branches. Branch ID '{id}' is of type '{type(branch).__name__}', expected instance of 'BaseBranch'.")

    @validator
    def _validate_slack(self):
        # Validar que existe UN slack y solo UN slack
        slack_num = sum( isinstance(bus, SlackBus) for bus in self._buses.values() )
        if slack_num != 1:
            raise ValueError(f"Topology Error: The network must have exactly ONE Slack bus. Found {slack_num} Slack buses.")

    @validator
    def _validate_topology(self):
        # validar que todas las lineas unen buses existentes y que todos los buses pertenecen a alguna linea.
        included_buses = set()  
        for branch in self._branches.values():
            if not branch.bus1 in self._buses:
                raise ValueError(f"Integrity Error: Branch {branch.id} connects to Bus {branch.bus1}, which does not exist in the network.")
            if not branch.bus2 in self._buses:
                raise ValueError(f"Integrity Error: Branch {branch.id} connects to Bus {branch.bus2}, which does not exist in the network.")
            
            included_buses.add(branch.bus1)
            included_buses.add(branch.bus2)
        
        if len(included_buses)!=len(self._buses):
            raise ValueError(
                f"Topology Error: The following buses are isolated (not connected to any branch): {
                    [bus_id for bus_id in self._buses if bus_id not in included_buses]}.")
    
    @validator
    def _validate_connectivity(self):
        # Validar que NO existen "islas" en la (es ya demasiada validacion)
        pass



