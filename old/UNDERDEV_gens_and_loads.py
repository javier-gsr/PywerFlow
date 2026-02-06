from dataclasses import dataclass, field, MISSING
from abc import ABC, abstractmethod
from pywerflow.buses.bus_types import BusTypes
from pywerflow.buses.input_buses import InputBus




"""
Implementar esto no sé si será util en algun momento para alguien, asi que de momento lo dejaré sin implementar

Para que quiero detallar tanto lo que hay dentro de un bus? Y bajo que condiciones? 
Si sobre tiempo pensaré de qué manera puede ser util y que tipos de componentes podrian haber

Esto es problematico ya que no es "intuitivo" como se va a comportar el bus final (PQ, PV, Slack) 
en relacion con su "lista de componentes". 

¿Como encajar la V, la P y la Q de cada generador o carga en el nudo final?
"""

class BusComponent:
    pass


class Generator(BusComponent):
    
    P: float

    Q: float
    
    V: float

    Qmin: float = float("-inf")

    Qmax: float = float("inf")

    Vmin: float = float("-inf")

    Vmax: float = float("inf")

    Vmin: float = float("-inf")

    Vmax: float = float("inf")


class Load(BusComponent):

    P: float

    Q: float

    V: float

    Qmin: float = float("-inf")

    Qmax: float = float("inf")

    Vmin: float = float("-inf")

    Vmax: float = float("inf")
