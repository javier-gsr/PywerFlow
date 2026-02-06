from dataclasses import dataclass
from dataclasses import dataclass, fields, MISSING
from math import pi
from numbers import Real, Integral

from pywerflow.utils.validation_utils import validator, validate_ranges, validate_types
from pywerflow.buses.input_buses import InputBus
from pywerflow.buses.bus_types import BusTypes



"""
La idea de este archivo era definir aqui las clases:
    - MixSlackBus
    - MixPVBus
    - MixPQBus

La idea era tener buses que "desde fuera" tengan los mismos atributos
    - P y Q serian atributos "property" en estas nuevas clases
    - Pload, Pgen, Qload y Qgen serían atributos "de verdad"

Luego SolvedBus podría devolverte las P y las Q "divididas" en generada y demandada


LA IDEA SE HA DESESTIMADO, QUIERO MANTENER LAS CLASES DE BUSES 
MATEMATICAMENTE PURAS

"""
