import json
import dataclasses
import warnings
from enum import Enum
from typing import Any

# Importamos para verificar tipos, pero usamos strings en el output para limpieza
from pywerflow.buses.bus_types import BusTypes

# --- 1. REGLAS DE TRADUCCIÓN (CLAVE INTERNA -> CLAVE BUILDER) ---
# Estas reglas definen cómo transformar un objeto guardado (InputBus) 
# en un diccionario que el PFNetworkBuilder entienda.
BUS_ATTR_MAP = {
    # DataClass Attr -> Builder Input Key
    'P': 'p_pu', 
    'Q': 'q_pu',
    'V': 'v_pu', 
    'V_guess': 'v_pu', # Si es un PQ, V_guess es la tensión inicial
    'theta': 'theta_rad', 
    'theta_guess': 'theta_rad',
    'G_shunt': 'g_pu', 
    'B_shunt': 'b_pu',
    'V_base': 'base_kv',
    'type': 'type',
    'id': 'id'
}

BRANCH_ATTR_MAP = {
    # DataClass Attr -> Builder Input Key
    'id': 'id',
    'bus1': 'bus1',
    'bus2': 'bus2',
    'R': 'r', 
    'X': 'x', 
    'G': 'g', 
    'B': 'b',
    # Para transformadores
    'Rcc': 'r', 
    'Xcc': 'x',
    'tap_ratio': 'tap',
    'shift': 'shift',
    'S_max': 's_max'
}

# --- 2. ENCODER PERSONALIZADO ---

class PywerJSONEncoder(json.JSONEncoder):
    """
    Serializador maestro. Convierte Dataclasses, Enums y Complejos a formato JSON nativo.
    """
    def default(self, obj):
        # A) Dataclasses (InputBus, SolvedBus, Branch, etc.)
        if dataclasses.is_dataclass(obj):
            data = dataclasses.asdict(obj)
            # Inyectamos una marca de clase para saber qué era originalmente
            data['__meta_class__'] = obj.__class__.__name__
            return data
        
        # B) Enums (BusTypes.PQ -> "PQ")
        if isinstance(obj, Enum):
            return obj.name
        
        # C) Números Complejos (1+2j -> {"real": 1, "imag": 2})
        if isinstance(obj, complex):
            return {"real": obj.real, "imag": obj.imag}
        
        # D) Sets (convertir a lista)
        if isinstance(obj, set):
            return list(obj)
            
        return super().default(obj)

# --- 3. FUNCIONES PÚBLICAS DE IO ---

def save_to_json(obj: Any, filepath: str, indent: int = 4):
    """
    Guarda cualquier objeto Pywerflow (Network, Results, Listas) en un archivo JSON.
    
    Estructura el archivo envolviendo los datos en un contenedor con metadatos.
    """
    # Determinamos qué tipo de objeto es para ponerle etiqueta
    obj_type = "unknown"
    s_base = None
    
    # Duck typing para detectar si es una Network o un Result
    if hasattr(obj, '_buses') and hasattr(obj, '_s_base'): # PowerFlowNetwork
        obj_type = "network"
        data_content = {
            "s_base": obj._s_base,
            # Extraemos las listas de los diccionarios internos
            "buses": list(obj._buses.values()),
            "branches": list(obj._branches.values())
        }
    elif hasattr(obj, 'buses') and hasattr(obj, 'meta'): # PowerFlowResults
        obj_type = "results"
        data_content = obj # El encoder se encargará de descomponer el dataclass
    else:
        # Fallback genérico
        data_content = obj

    envelope = {
        "pywerflow_version": "1.0",
        "file_type": obj_type,
        "content": data_content
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(envelope, f, cls=PywerJSONEncoder, indent=indent)


def load_data_for_builder(filepath: str) -> dict:
    """
    Lee un JSON, detecta su estructura y prepara los datos normalizados
    listos para ser consumidos por PFNetworkBuilder.add_..._from_data().

    Retorna un diccionario con:
        {
            's_base': float | None,
            'buses': list[dict],    # Claves ya mapeadas (p_pu, etc.)
            'branches': list[dict]  # Claves ya mapeadas (r, x, tap...)
        }
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    # 1. Desempaquetar (Soporta formato 'envelope' o formato crudo antiguo)
    if "file_type" in raw and "content" in raw:
        content = raw["content"]
    else:
        content = raw # Asumimos que es formato crudo

    # 2. Extraer datos base
    # Buscamos 'network' si viene de un snapshot completo, o usamos la raíz
    root = content.get("network", content) 
    
    s_base = root.get("s_base")
    # A veces s_base está suelto si guardamos results
    if s_base is None and "s_base" in content: 
        s_base = content["s_base"]

    # 3. Procesar Listas y Aplicar Mapeos
    raw_buses = root.get("buses", [])
    raw_branches = root.get("branches", [])

    # Helper de adaptación
    def adapt(record_list, mapping):
        adapted_list = []
        for item in record_list:
            new_item = {}
            for original_key, val in item.items():
                # Si la clave está en el mapa, la traducimos. Si no, la ignoramos o la pasamos igual
                # (Preferimos pasarla igual por si acaso es un campo extra)
                target_key = mapping.get(original_key, original_key)
                
                # Tratamiento especial para 'type' (Enum -> String ya lo hace json.load)
                # pero nos aseguramos de que el Builder lo reciba limpio.
                new_item[target_key] = val
            adapted_list.append(new_item)
        return adapted_list

    return {
        "s_base": s_base,
        "buses": adapt(raw_buses, BUS_ATTR_MAP),
        "branches": adapt(raw_branches, BRANCH_ATTR_MAP)
    }