import re
import warnings
import math
from typing import Any

# --- CONSTANTES DE COLUMNAS MATPOWER (Índices basados en 0) ---
# Referencia: documentación de caseformat.m

# Columnas de Datos de BUS
_BUS_I       = 0
_BUS_TYPE    = 1
_PD          = 2
_QD          = 3
_GS          = 4
_BS          = 5
_VM          = 7
_VA          = 8
_BASE_KV     = 9  # Col 10 en doc
_VMAX        = 11 # Col 12 en doc
_VMIN        = 12 # Col 13 en doc

# Columnas de Datos de GENERADOR (GEN)
_GEN_BUS     = 0
_PG          = 1
_QG          = 2
_QMAX        = 3
_QMIN        = 4
_GEN_STATUS  = 7  # Col 8 en doc

# Columnas de Datos de RAMA (BRANCH)
_F_BUS       = 0
_T_BUS       = 1
_BR_R        = 2
_BR_X        = 3
_BR_B        = 4
_RATE_A      = 5
_TAP         = 8  # Col 9 en doc
_SHIFT       = 9  # Col 10 en doc
_BR_STATUS   = 10 # Col 11 en doc


def _parse_matpower_raw(filepath: str) -> dict[str, Any]:
    """
    Parses a raw .m Matpower file into a dictionary of lists using Regex.
    Handles MATLAB M-file syntax quirks:
    - Scientific notation (e.g., 1.0e-2).
    - Comma or space separators.
    - Loose matrix closing brackets.
    """
    data = {"baseMVA": 100.0, "bus": [], "gen": [], "branch": []}
    current_block = None
    
    # Regex para detectar inicio de bloque: mpc.bus = [
    block_start_re = re.compile(r"mpc\.(bus|gen|branch)\s*=\s*\[")
    
    # Regex para detectar baseMVA: mpc.baseMVA = 100;
    # Robusto: Soporta enteros, floats y notación científica (ej: 1e2, 1.0E+2)
    scalar_re = re.compile(r"mpc\.baseMVA\s*=\s*([-\d\.\+eE]+)")

    # Regex para detección de versión y detección de V1
    version_field_re = re.compile(r"mpc\.version\s*=\s*['\"](\d+)['\"]")
    v1_legacy_re = re.compile(r"^\s*(bus|gen|branch|baseMVA)\s*=\s*\[?")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            # 1. Limpieza: Quitar comentarios (%) y espacios en blanco
            line = line.split('%')[0].strip()
            
            if not line: 
                continue

            # Comprobar campo de versión explícito
            m_version = version_field_re.search(line)
            if m_version and m_version.group(1) == "1":
                raise ValueError(f"Incompatible Matpower Format: Version 1 detected on line {line_num}. "
                                 "Only MATPOWER Case Format Version 2 (mpc struct) is supported.")

            # Comprobar estilo legado Versión 1 (variables sin prefijo 'mpc.')
            if v1_legacy_re.match(line) and not line.startswith("mpc."):
                 raise ValueError(f"Incompatible Matpower Format: Legacy Version 1 syntax detected on line {line_num}. "
                                  "Please use Version 2 format (mpc.bus, mpc.gen, etc.).")
                
            # 2. Lógica de Bloques (Dentro de una matriz)
            if current_block:
                # Las matrices de MATLAB terminan con ]; (o solo ] en algunos casos)
                # Dividimos por ']' para separar los datos del corchete de cierre
                if "]" in line:
                    content_part = line.split("]")[0]
                    is_end_of_block = True
                else:
                    content_part = line
                    is_end_of_block = False
                
                # Sanear:
                # - Reemplazar comas por espacios (MATLAB permite ambos como separadores)
                # - Quitar puntos y coma (fin de fila/instrucción)
                content_part = content_part.replace(",", " ").replace(";", "")
                
                # Parsear números si hay contenido
                if content_part.strip():
                    try:
                        row_values = [float(x) for x in content_part.split()]
                        data[current_block].append(row_values)
                    except ValueError as e:
                        # Avisos para líneas malformadas dentro de un bloque
                        warnings.warn(f"Line {line_num}: Could not parse numerical data in block '{current_block}'. Skipped. Error: {e}", UserWarning)

                if is_end_of_block:
                    current_block = None
                
                continue

            # 3. Búsqueda de Base MVA
            m_scalar = scalar_re.search(line)
            if m_scalar:
                try:
                    data["baseMVA"] = float(m_scalar.group(1))
                except ValueError:
                    warnings.warn(f"Line {line_num}: Invalid baseMVA format '{m_scalar.group(1)}'. Defaulting to 100.0.", UserWarning)
                continue
            
            # 4. Búsqueda de Inicio de Bloque
            m_block = block_start_re.search(line)
            if m_block:
                current_block = m_block.group(1)
                # Comprobar si el bloque se cierra en la misma línea (ej: mpc.bus = [ ... ];)
                if "]" in line:
                    # Parsear el contenido entre [ y ]
                    start_idx = line.find("[") + 1
                    end_idx = line.find("]")
                    content_part = line[start_idx:end_idx]
                    
                    content_part = content_part.replace(",", " ").replace(";", "")
                    if content_part.strip():
                        try:
                            row_values = [float(x) for x in content_part.split()]
                            data[current_block].append(row_values)
                        except ValueError:
                             warnings.warn(f"Line {line_num}: Could not parse inline data in block '{current_block}'.", UserWarning)
                    current_block = None # Bloque cerrado inmediatamente
                continue
                
    return data


def read_matpower_file(filepath: str) -> tuple[list[dict], list[dict], float]:
    """
    Reads a Matpower file and returns raw structured data.

    This function extracts the system base power, aggregates generators by bus,
    and maps the Matpower matrix columns to named dictionary keys compatible 
    with standard data processing pipelines.

    .. note::
        **Information Loss Warning:** The current implementation ignores several 
        Matpower features:
        *   **Reactive Power Limits:** Qmin and Qmax are detected but ignored.
        *   **Voltage Limits:** Vmin and Vmax for buses are detected but ignored.
        *   **Secondary Ratings:** Only Rate A is processed; Rate B and C are ignored.
        *   **Out-of-service elements:** Branches or buses with status <= 0 are skipped.

    Args:
        filepath: Path to the .m file.

    Returns:
        tuple: A tuple containing:
            - **bus_data** (list[dict]): List of dictionaries describing buses.
            - **branch_data** (list[dict]): List of dictionaries describing branches.
            - **base_mva** (float): The system base MVA.
    """
    # 1. Parsear texto crudo
    mpc = _parse_matpower_raw(filepath)
    
    base_mva = float(mpc['baseMVA'])
    
    # 2. Agregación de Generadores (Sumar P y Q por nudo)
    gen_agg = {}
    q_limits_found = False
    
    for row in mpc['gen']:
        # Comprobación de seguridad para acceso a índices de columna
        # Status es col 8 (idx 7). Si la fila es más corta, asumimos 1 (En Servicio)
        status = row[_GEN_STATUS] if len(row) > _GEN_STATUS else 1
        
        if status <= 0:
            gen_bus_id = int(row[_GEN_BUS]) if len(row) > _GEN_BUS else 'Unknown'
            warnings.warn(f"Generator at bus {gen_bus_id} is out of service (status <= 0) and will be skipped.", UserWarning)
            continue
        
        # Detectar presencia de límites Q (cols 4 y 5 -> índices 3 y 4)
        if len(row) > max(_QMAX, _QMIN):
            q_limits_found = True

        bus_id = int(row[_GEN_BUS])
        if bus_id not in gen_agg: gen_agg[bus_id] = {'p': 0.0, 'q': 0.0}
        
        # P y Q son las columnas 2 y 3 (índices 1 y 2)
        p_val = row[_PG] if len(row) > _PG else 0.0
        q_val = row[_QG] if len(row) > _QG else 0.0
        
        gen_agg[bus_id]['p'] += p_val
        gen_agg[bus_id]['q'] += q_val

    if q_limits_found:
        warnings.warn("Reactive power limits (Qmin/Qmax) were found in the Matpower file but will be ignored. "
                      "The current software version does not support reactive power limits.", UserWarning)

    # 3. Procesamiento de Buses
    bus_records = []
    v_limits_found = False
    
    for row in mpc['bus']:
        bus_id = int(row[_BUS_I])
        bus_type = int(row[_BUS_TYPE]) if len(row) > _BUS_TYPE else 1 # PQ por defecto
        
        # Detectar presencia de límites V (cols 12 y 13 -> índices 11 y 12)
        if len(row) > max(_VMAX, _VMIN):
            v_limits_found = True

        # Ignorar nudos aislados (Tipo 4)
        if bus_type == 4: 
            warnings.warn(f"Bus {bus_id} is isolated (Type 4) and will be skipped.", UserWarning)
            continue
            
        gen_data = gen_agg.get(bus_id, {'p': 0.0, 'q': 0.0})
        
        # Acceso seguro a columnas con valores por defecto si faltan
        gs = row[_GS] if len(row) > _GS else 0.0
        bs = row[_BS] if len(row) > _BS else 0.0
        base_kv = row[_BASE_KV] if len(row) > _BASE_KV else 1.0 
        vm = row[_VM] if len(row) > _VM else 1.0
        va = row[_VA] if len(row) > _VA else 0.0
        pd = row[_PD] if len(row) > _PD else 0.0
        qd = row[_QD] if len(row) > _QD else 0.0

        # Conversión Shunt MW -> p.u.
        g_pu = gs / base_mva
        b_pu = bs / base_mva

        bus_records.append({
            'id': bus_id,
            'type': bus_type,
            'base_kv': base_kv,
            'v_pu': vm,
            'theta_deg': va,
            'pload_mw': pd,
            'qload_mvar': qd,
            'pgen_mw': gen_data['p'],
            'qgen_mvar': gen_data['q'],
            'g_pu': g_pu,
            'b_pu': b_pu
        })

    if v_limits_found:
        warnings.warn("Voltage magnitude limits (Vmin/Vmax) were found in the Matpower file but will be ignored. "
                      "The current software version does not support voltage limits check during load import.", UserWarning)

    # 4. Procesamiento de Ramas (Branches)
    branch_records = []
    for i, row in enumerate(mpc['branch']):
        # Comprobación de estado
        status = row[_BR_STATUS] if len(row) > _BR_STATUS else 1
        if status <= 0:
            f_bus = int(row[_F_BUS]) if len(row) > _F_BUS else '?'
            t_bus = int(row[_T_BUS]) if len(row) > _T_BUS else '?'
            warnings.warn(f"Branch connecting bus {f_bus} to {t_bus} is out of service (status <= 0) and will be skipped.", UserWarning)
            continue
            
        # Manejo de Tap
        # Tap es col 9 (idx 8). 0 significa 1.0 por defecto
        tap_raw = row[_TAP] if len(row) > _TAP else 0.0
        tap = tap_raw if tap_raw != 0.0 else 1.0
        
        # Manejo de Shift (Desfase)
        # Shift es col 10 (idx 9). 0 por defecto.
        shift_deg = row[_SHIFT] if len(row) > _SHIFT else 0.0
        shift_rad = math.radians(shift_deg)
        
        # Manejo de Rate A
        rate_a = row[_RATE_A] if len(row) > _RATE_A else 0.0
        s_max = rate_a if rate_a > 0 else float('inf')

        # Impedancia
        r = row[_BR_R] if len(row) > _BR_R else 0.0
        x = row[_BR_X] if len(row) > _BR_X else 0.0
        b = row[_BR_B] if len(row) > _BR_B else 0.0

        branch_records.append({
            'id': i + 1, # ID autogenerado
            'from': int(row[_F_BUS]),
            'to': int(row[_T_BUS]),
            'r': r,
            'x': x,
            'b': b,
            'tap': tap,
            'shift': shift_rad,
            's_max': s_max
        })

    return bus_records, branch_records, base_mva