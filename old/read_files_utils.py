import pandas as pd
import math
import logging

LOGGER = logging.getLogger(__name__)
# ======================================
#           Helper functions
# ======================================

def find_column(df_cols, aliases):
    df_cols_lower = [c.strip().lower() for c in df_cols]
    for name in aliases:
        if name.lower() in df_cols_lower:
            return df_cols[df_cols_lower.index(name.lower())]
    raise ValueError(f"None of the expected column names {aliases} were found.")

def convert_value(value, dtype, null_indicators):
    if pd.isna(value):  
        return None
    # Verificar si el valor es un indicador de nulo
    value_str = str(value).strip()
    if value_str in null_indicators:
        return None
    # Verificar si contiene 'nan' (para casos como 'nan', '(nan+0j)', etc.)
    if 'nan' in value_str.lower():
        return None
    
    if dtype == complex:
        s = str(value).replace(" ", "")
        if "∠" in s:
            try:
                r_str, theta_str = s.split("∠")
                r = float(r_str)
                theta = float(theta_str)
                return complex(r * math.cos(theta), r * math.sin(theta))
            except Exception:
                raise ValueError(f"Cannot parse polar complex number from '{value}'")
        try:
            return complex(s)
        except Exception:
            raise ValueError(f"Cannot parse complex number from '{value}'")
    else:
        return dtype(value)

# ======================================
#           Reading function
# ======================================

def read_power_network_excel(file_path):
    """
    Reads an Excel file containing 'buses' and 'lines' sheets,
    with flexible, case-insensitive column names and expected dtypes.
    """

    # Lista de caracteres/strings que se interpretan como None
    NULL_INDICATORS = ["-", "—", "–", "N/A", "n/a", "NA", "na", "", "None", "none", "NULL", "null"]

    COLUMN_DEFINITIONS = {
        "buses": {
            "id": {"aliases": ["id"], "dtype": int},
            "type": {"aliases": ["type"], "dtype": str},
            "P": {"aliases": ["p"], "dtype": float},
            "Q": {"aliases": ["q"], "dtype": float},
            "V": {"aliases": ["V"], "dtype": float},
            "theta": {"aliases": ["θ", "theta"], "dtype": float},
        },
        "lines": {
            "id": {"aliases": ["id"], "dtype": int},
            "bus1": {"aliases": ["id bus 1"], "dtype": int},
            "bus2": {"aliases": ["id bus 2"], "dtype": int},
            "Z": {"aliases": ["z"], "dtype": complex},
            "Y": {"aliases": ["y"], "dtype": complex},
            "T-rt": {"aliases": ["trafo-rt"], "dtype": complex},
            "T-Zcc": {"aliases": ["trafo-zcc"], "dtype": complex},
        },
    }


    # --- DEFINICIONES OPCIONALES (NUEVO DICCIONARIO) ---
    OPTIONAL_COLUMN_DEFINITIONS = {
        "buses": {
            "V0": {"aliases": ["v0", "v_start", "v_init", "initial_v"], "dtype": float},
            "theta0": {"aliases": ["theta0", "θ0", "theta_start", "theta_init"], "dtype": float},
        }
        # Se puede expandir para "lines" en el futuro si hiciera falta
    }

    # ==============================
    # Read buses sheet
    # ==============================
    df_buses_raw = pd.read_excel(file_path, sheet_name="buses")
    df_buses_raw.columns = df_buses_raw.columns.str.strip()

    bus_cols_found = {
        k: find_column(df_buses_raw.columns, v["aliases"])
        for k, v in COLUMN_DEFINITIONS["buses"].items()
    }

    # Cutoff at first empty 'type'
    empty_mask = df_buses_raw[bus_cols_found["type"]].isna()
    cutoff_index = empty_mask[empty_mask].index.min()
    if pd.notna(cutoff_index):
        df_buses_raw = df_buses_raw.iloc[:cutoff_index]

    # Keep only needed columns and rename (corregido el mapeo inverso)
    df_buses = df_buses_raw[list(bus_cols_found.values())].rename(
        columns={v: k for k, v in bus_cols_found.items()}
    )

    # --- NUEVO BLOQUE: PROCESAMIENTO DE COLUMNAS OPCIONALES ---
    # Buscamos en el df_raw original si existen las opcionales y las añadimos a df_buses
    for k, v in OPTIONAL_COLUMN_DEFINITIONS["buses"].items():
        try:
            # Intentamos encontrarla en el raw
            found_col_name = find_column(df_buses_raw.columns, v["aliases"])
            # Si existe, la copiamos al df limpio con el nombre estandarizado
            df_buses[k] = df_buses_raw[found_col_name]
        except ValueError:
            # Si no existe, creamos la columna llena de None
            df_buses[k] = None
    # ----------------------------------------------------------

    # Convertir a lista de diccionarios PRIMERO para librarnos de pandas
    bus_list = df_buses.to_dict(orient="records")

    # AHORA sí, convertir tipos en los diccionarios de Python
    for bus in bus_list:
        for k, v in COLUMN_DEFINITIONS["buses"].items():
            if k in bus:
                dtype = v["dtype"]
                bus[k] = convert_value(bus[k], dtype, NULL_INDICATORS)

    # --- NUEVO BLOQUE: CONVERSIÓN DE TIPOS (Para Opcionales) ---
    for bus in bus_list:
        for k, v in OPTIONAL_COLUMN_DEFINITIONS["buses"].items():
            # Aquí no chequeamos 'if k in bus' porque ya garantizamos arriba que existen (o son None)
            dtype = v["dtype"]
            bus[k] = convert_value(bus[k], dtype, NULL_INDICATORS)
    # -----------------------------------------------------------

    # Adjust buses by type
    for bus in bus_list:
        match bus["type"].upper():
            case "SLACK":
                bus.pop("P", None)
                bus.pop("Q", None)
                bus.pop("V0", None)
                bus.pop("theta0", None)
            case "PQ":
                bus.pop("V", None)
                bus.pop("theta", None)
            case "PV":
                bus.pop("Q", None)
                bus.pop("theta", None)
                bus.pop("V0", None)

    # ==============================
    # Read lines sheet
    # ==============================
    df_lines = pd.read_excel(file_path, sheet_name="lines")
    df_lines.columns = df_lines.columns.str.strip()

    line_cols_found = {
        k: find_column(df_lines.columns, v["aliases"])
        for k, v in COLUMN_DEFINITIONS["lines"].items()
    }

    # Cutoff at first empty 'id' (añadido para lines)
    empty_mask = df_lines[line_cols_found["id"]].isna()
    cutoff_index = empty_mask[empty_mask].index.min()
    if pd.notna(cutoff_index):
        df_lines = df_lines.iloc[:cutoff_index]

    # Keep only needed columns and rename (corregido el mapeo inverso)
    df_lines = df_lines[list(line_cols_found.values())].rename(
        columns={v: k for k, v in line_cols_found.items()}
    )

    # Convertir a lista de diccionarios PRIMERO para librarnos de pandas
    lines_list = df_lines.to_dict(orient="records")

    # AHORA sí, convertir tipos en los diccionarios de Python
    for bus in lines_list:
        for k, v in COLUMN_DEFINITIONS["lines"].items():
            if k in bus:
                dtype = v["dtype"]
                bus[k] = convert_value(bus[k], dtype, NULL_INDICATORS)







    # # Convert types
    # for k, v in COLUMN_DEFINITIONS["lines"].items():
    #     dtype = v["dtype"]
    #     df_lines[k] = df_lines[k].apply(lambda val: convert_value(val, dtype, NULL_INDICATORS))

    # line_list = df_lines.to_dict(orient="records")

    return {"buses": bus_list, "lines": lines_list}


# ======================================
#     Verification function
# ======================================

# AÑADIR O CORREGIR:
# Ninguna Z serie puede ser 0 en un modelo PI


def verify_power_network(network_data):
    """
    Verifies the integrity and consistency of the power network data.
    Raises exceptions if any validation fails.
    
    Args:
        network_data: Dictionary with 'buses' and 'lines' keys
    """
    buses = network_data["buses"]
    lines = network_data["lines"]
    
    # ==============================
    # Verificar buses
    # ==============================
    
    # Verificar IDs únicas y no negativas
    bus_ids = [bus["id"] for bus in buses]
    if len(bus_ids) != len(set(bus_ids)):
        duplicates = [bid for bid in bus_ids if bus_ids.count(bid) > 1]
        raise ValueError(f"Duplicate bus IDs found: {set(duplicates)}")
    
    if any(bid < 0 for bid in bus_ids):
        negative = [bid for bid in bus_ids if bid < 0]
        raise ValueError(f"Negative bus IDs found: {negative}")
    
    # Contar buses Slack
    slack_buses = [bus for bus in buses if bus["type"].upper() == "SLACK"]
    if len(slack_buses) == 0:
        raise ValueError("No SLACK bus found. Exactly one SLACK bus is required.")
    if len(slack_buses) > 1:
        slack_ids = [bus["id"] for bus in slack_buses]
        raise ValueError(f"Multiple SLACK buses found (IDs: {slack_ids}). Only one SLACK bus is allowed.")
    
    # Verificar bus SLACK
    slack = slack_buses[0]
    if "V" not in slack or slack["V"] is None or not isinstance(slack["V"], float):
        raise ValueError(f"SLACK bus (ID: {slack['id']}) must have V defined as float.")
    if "theta" not in slack or slack["theta"] is None or not isinstance(slack["theta"], float):
        raise ValueError(f"SLACK bus (ID: {slack['id']}) must have theta defined as float.")
    
    # Verificar buses PV
    for bus in buses:
        if bus["type"].upper() == "PV":
            if "P" not in bus or bus["P"] is None or not isinstance(bus["P"], float):
                raise ValueError(f"PV bus (ID: {bus['id']}) must have P defined as float.")
            if "V" not in bus or bus["V"] is None or not isinstance(bus["V"], float):
                raise ValueError(f"PV bus (ID: {bus['id']}) must have V defined as float.")
    
    # Verificar buses PQ
    for bus in buses:
        if bus["type"].upper() == "PQ":
            if "P" not in bus or bus["P"] is None or not isinstance(bus["P"], float):
                raise ValueError(f"PQ bus (ID: {bus['id']}) must have P defined as float.")
            if "Q" not in bus or bus["Q"] is None or not isinstance(bus["Q"], float):
                raise ValueError(f"PQ bus (ID: {bus['id']}) must have Q defined as float.")
    
    # ==============================
    # Verificar líneas
    # ==============================
    
    # Verificar IDs únicas y no negativas
    line_ids = [line["id"] for line in lines]
    if len(line_ids) != len(set(line_ids)):
        duplicates = [lid for lid in line_ids if line_ids.count(lid) > 1]
        raise ValueError(f"Duplicate line IDs found: {set(duplicates)}")
    
    if any(lid < 0 for lid in line_ids):
        negative = [lid for lid in line_ids if lid < 0]
        raise ValueError(f"Negative line IDs found: {negative}")
    
    # Verificar campos obligatorios de líneas
    required_fields = ["id", "bus1", "bus2", "Z", "Y"]
    required_types = {"id": int, "bus1": int, "bus2": int, "Z": complex, "Y": complex}
    
    for line in lines:
        for field in required_fields:
            if field not in line or line[field] is None:
                raise ValueError(f"Line (ID: {line.get('id', 'unknown')}) missing required field '{field}'.")
            if not isinstance(line[field], required_types[field]):
                raise ValueError(
                    f"Line (ID: {line['id']}) field '{field}' must be of type {required_types[field].__name__}, "
                    f"got {type(line[field]).__name__}."
                )
    
    # Verificar que bus1 y bus2 existen
    bus_id_set = set(bus_ids)
    for line in lines:
        if line["bus1"] not in bus_id_set:
            raise ValueError(f"Line (ID: {line['id']}) references non-existent bus1 (ID: {line['bus1']}).")
        if line["bus2"] not in bus_id_set:
            raise ValueError(f"Line (ID: {line['id']}) references non-existent bus2 (ID: {line['bus2']}).")
    
    # Verificar transformadores y añadir atributo "has_T"
    for line in lines:
        has_trt = "T-rt" in line and line["T-rt"] is not None and isinstance(line["T-rt"], complex)
        has_tzcc = "T-Zcc" in line and line["T-Zcc"] is not None and isinstance(line["T-Zcc"], complex)
        
        # Verificar que si hay uno, hay ambos
        if has_trt and not has_tzcc:
            raise ValueError(
                f"Line (ID: {line['id']}) has T-rt defined but T-Zcc is missing. "
                f"Both must be specified for transformers."
            )
        if has_tzcc and not has_trt:
            raise ValueError(
                f"Line (ID: {line['id']}) has T-Zcc defined but T-rt is missing. "
                f"Both must be specified for transformers."
            )
        
        # Añadir atributo has_T
        line["has_T"] = has_trt and has_tzcc
    
    return True  # Si llegamos aquí, todo está correcto


# ======================================
#     Writing files function
# ======================================

def export_ybus_to_csv(Ybus_matrix, bus_mapping, filename="ybus_export.csv"):
    """
    Exporta la matriz Y-bus a un CSV usando pandas, etiquetando
    filas y columnas con los IDs de los buses.

    Parameters:
        Ybus_matrix (np.ndarray): La matriz Y-bus (compleja).
        bus_mapping (dict): El diccionario que mapea {bus_id: matrix_index}.
                            (Debe venir de get_admitance_matrix)
        filename (str): Nombre del archivo CSV de salida.
    """
    
    # 1. Invertir el mapeo para obtener {index: bus_id}
    idx_to_bus = {i: bus_id for bus_id, i in bus_mapping.items()}
    
    # 2. Crear la lista de etiquetas ordenada por el índice (0, 1, 2...)
    #    Como el bus_mapping ya está ordenado, 'labels' también lo estará.
    labels = [idx_to_bus[i] for i in range(Ybus_matrix.shape[0])]
    
    # 3. Crear el DataFrame de pandas
    #    Aplica las MISMAS etiquetas a filas (index) y columnas (columns)
    df = pd.DataFrame(Ybus_matrix, index=labels, columns=labels)
    
    # 4. Exportar a CSV
    try:
        df.to_csv(filename)
        print(f"Éxito: Matriz Y-bus exportada a '{filename}'")
    except Exception as e:
        print(f"Error al exportar Y-bus: {e}")