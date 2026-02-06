import json
import dataclasses
import warnings
from enum import Enum
from typing import Any, Dict, List, Union, Tuple
import numpy as np
from math import isinf

from pywerflow.networks.pf_network import PowerFlowNetwork
from pywerflow.buses.input_buses import InputBus, SlackBus, PVBus, PQBus
from pywerflow.buses.bus_types import BusTypes
from pywerflow.branches.pfsolvable_branches import (
    PFSolvableBranch, 
    PiLine, 
    SimpleTransformer, 
    PiTransformer, 
    RawBranch
)

# Versión del formato JSON para compatibilidad futura
JSON_FORMAT_VERSION = "1.0"

# Registro de clases permitidas para la deserialización
CLASS_REGISTRY = {
    "SlackBus": SlackBus,
    "PVBus": PVBus,
    "PQBus": PQBus,
    "PiLine": PiLine,
    "SimpleTransformer": SimpleTransformer,
    "PiTransformer": PiTransformer,
    "RawBranch": RawBranch
}

class PywerFlowJSONEncoder(json.JSONEncoder):
    """
    Custom JSON Encoder for PywerFlow objects.

    Handles the serialization of specialized types such as Dataclasses, Enums,
    Complex numbers, Numpy types, and Infinity values.
    """
    def default(self, obj: Any) -> Any:
        if dataclasses.is_dataclass(obj):
            # Convertir dataclass a diccionario
            data = dataclasses.asdict(obj)
            # Inyectar el nombre de la clase para la reconstrucción
            data["__class__"] = obj.__class__.__name__
            return data
        
        if isinstance(obj, Enum):
            return obj.name  # Serializar como el nombre en string (ej: "PV")
        
        if isinstance(obj, complex):
            return str(obj)  # Serializar como string "(r+ij)"
        
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        
        if isinstance(obj, np.ndarray):
            return obj.tolist()
            
        return super().default(obj)


def _decode_value(value: Any) -> Any:
    """
    Helper to decode specific values (complex, inf, nan) from strings.
    """
    if isinstance(value, str):
        # Manejo de números complejos
        if ("(" in value and ")" in value and ("j" in value or "i" in value)):
            try:
                # Manejar la notación 'i' si está presente
                return complex(value.replace("i", "j"))
            except ValueError:
                pass 
        
        # Manejo de Infinito/NaN
        if value == "Infinity": return float("inf")
        if value == "-Infinity": return float("-inf")
        if value == "NaN": return float("nan")
        
    return value

def _instantiate_object(data: Dict[str, Any]) -> Any:
    """
    Reconstructs a PywerFlow object from a dictionary containing a '__class__' key.
    """
    class_name = data.pop("__class__", None)
    
    # Decodificar recursivamente los valores en el diccionario (ej: complejos en campos)
    decoded_data = {k: _decode_value(v) for k, v in data.items()}

    if not class_name:
        return decoded_data

    if class_name not in CLASS_REGISTRY:
        warnings.warn(f"Unknown class '{class_name}' encountered in JSON. Returning as dict.", UserWarning)
        return decoded_data

    cls = CLASS_REGISTRY[class_name]
    
    # Manejo especial para el Enum BusTypes
    if "type" in decoded_data and isinstance(decoded_data["type"], str):
        try:
            decoded_data["type"] = BusTypes[decoded_data["type"]]
        except KeyError:
            pass # Dejar que el validador lo gestione o falle más tarde

    # Instanciar la dataclass
    try:
        return cls(**decoded_data)
    except TypeError as e:
        raise TypeError(f"Failed to instantiate {class_name}: {e}") from e


def network_to_json(network: PowerFlowNetwork, filepath: str, indent: int = 4) -> None:
    """
    Serializes a PowerFlowNetwork state directly to a JSON file.

    It handles disabled buses by retrieving their original definition from 
    memory instead of saving the active 'dummy' bus.

    Args:
        network (PowerFlowNetwork): The network instance to export.
        filepath (str): The destination file path.
        indent (int, optional): Indentation level. Defaults to 4.
    """
    
    # 1. Gestionar Nudos Deshabilitados
    buses_to_save = []
    
    # Recuperar todos los nudos activos actualmente
    # Accedemos al diccionario interno directamente o vía el getter público
    current_buses = network.get_all_buses()
    
    # Comprobar nudos deshabilitados
    disabled_map = {}
    if network.get_disabled_buses():
         disabled_map = {b.id: b for b in network.get_disabled_buses()}

    for bus in current_buses:
        # Comprobar si el ID de este nudo corresponde a uno deshabilitado
        if bus.id in disabled_map:
            # Intercambiar dummy por original
            original_bus = disabled_map[bus.id]
            buses_to_save.append(original_bus)
            warnings.warn(
                f"Bus {bus.id} is disabled. Saving ORIGINAL definition from memory.",
                UserWarning
            )
        else:
            buses_to_save.append(bus)
            
    # Ordenar por consistencia
    buses_to_save.sort(key=lambda b: b.id)
    
    # 2. Recolectar Ramas
    all_branches = list(network.get_all_branches())
    all_branches.sort(key=lambda b: b.id)

    # 3. Construir Estructura Raíz
    data = {
        "meta": {
            "format": "PywerFlow Network",
            "version": JSON_FORMAT_VERSION,
        },
        "s_base": network.s_base,
        "buses": buses_to_save,     # Lista de Objetos
        "branches": all_branches,   # Lista de Objetos
    }

    # 4. Escribir a Archivo
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, cls=PywerFlowJSONEncoder, indent=indent)


def load_network_from_json(filepath: str) -> Tuple[List[InputBus], List[PFSolvableBranch], float]:
    """
    Reads a PywerFlow JSON file and reconstructs the native objects directly.

    Args:
        filepath (str): The path to the source .json file.

    Returns:
        Tuple[List[InputBus], List[PFSolvableBranch], float]: 
            - List of instantiated InputBus objects.
            - List of instantiated PFSolvableBranch objects.
            - System base power (S_base).

    Raises:
        ValueError: If the JSON structure is invalid.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    if "buses" not in raw_data or "branches" not in raw_data:
        raise ValueError("Invalid JSON format: Missing 'buses' or 'branches' keys.")

    s_base = raw_data.get("s_base")
    if s_base is None:
        raise ValueError("Invalid JSON format: Missing 's_base'.")

    # Reconstruir Nudos
    buses = []
    for bus_data in raw_data["buses"]:
        # Decodificar e Instanciar
        if isinstance(bus_data, dict):
             buses.append(_instantiate_object(bus_data))
    
    # Reconstruir Ramas
    branches = []
    for branch_data in raw_data["branches"]:
        # Decodificar e Instanciar
        if isinstance(branch_data, dict):
            branches.append(_instantiate_object(branch_data))

    return buses, branches, float(s_base)