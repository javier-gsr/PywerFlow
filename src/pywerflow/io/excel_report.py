from typing import Literal
import pandas as pd
import warnings

# Importamos solo para Type Hinting (evitar ciclos en tiempo de ejecución si fuera necesario)
from pywerflow.networks.pf_network import PowerFlowNetwork
from pywerflow.networks.pfresults import PowerFlowResults

def generate_excel_report(
    filepath: str,
    network: PowerFlowNetwork,
    results: PowerFlowResults,
    
    # --- Interruptores de Secciones ---
    include_inputs: bool = True,
    include_results: bool = True,
    include_meta: bool = True,
    
    # --- Selección de Columnas (Entradas) ---
    in_bus_columns: list[str] | None = None,
    in_branch_columns: list[str] | None = None,
    
    # --- Selección de Columnas (Resultados) ---
    res_bus_columns: list[str] | None = None,
    res_branch_columns: list[str] | None = None,
    
    # --- Configuración Visual ---
    sheet_names: dict[str, str] | None = None
):
    """
    Generates a comprehensive Excel report merging Network Definition (Inputs) and 
    Simulation Results (Outputs) into a single workbook.

    This function acts as a centralized reporter. It validates consistency between 
    the network and the results before delegating data extraction to the respective 
    objects.

    **Available Column Keys:**
    
    * **Input Buses (`in_bus_columns`):**
        'id', 'type', 'base_kv', 'v_pu', 'v_kv', 'theta_rad', 'theta_deg', 
        'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'g_pu', 'b_pu'.
        *(Note: Returns setpoints or initial guesses depending on bus type)*

    * **Input Branches (`in_branch_columns`):**
        'id', 'type', 'bus1', 'bus2', 'r', 'x', 'g', 'b', 'tap', 'shift', 's_max'.

    * **Result Buses (`res_bus_columns`):**
        'id', 'type', 'v_pu', 'v_kv', 'theta_rad', 'theta_deg', 
        'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'p_mis', 'q_mis'.
        *(Note: Returns the final calculated state)*

    * **Result Branches (`res_branch_columns`):**
        'id', 'bus1', 'bus2', 'loading', 
        'p1_mw', 'q1_mvar', 'p2_mw', 'q2_mvar', 'ploss_mw', 'qloss_mvar',
        'i1_ka', 'i2_ka'.

    Args:
        filepath (str): Destination path (.xlsx).
        network (PowerFlowNetwork): The source topology object.
        results (PowerFlowResults): The simulation output object.
        
        include_inputs (bool): If True, adds sheets for Input Buses/Branches.
        include_results (bool): If True, adds sheets for Solved Buses/Branches.
        include_meta (bool): If True, adds a sheet with Solver convergence info.
        
        in_bus_columns (list[str]): Columns for Input Bus sheet. Defaults to standard definition.
        in_branch_columns (list[str]): Columns for Input Branch sheet. Defaults to standard parameters.
        res_bus_columns (list[str]): Columns for Result Bus sheet. Defaults to standard state + mismatches.
        res_branch_columns (list[str]): Columns for Result Branch sheet. Defaults to flows + losses.
        
        sheet_names (dict[str, str]): Override default sheet names. 
            Keys: 'meta', 'in_buses', 'in_branches', 'in_general', 'res_buses', 'res_branches'.

    Raises:
        ValueError: If physical units are requested but S_base/V_base is missing.
        UserWarning: If inconsistencies (e.g., S_base mismatch) are detected between Network and Results.
    """

    # --- 1. VALIDACIÓN DE CONSISTENCIA (CRUCE DE DATOS) ---
    # Verificamos si la base de potencia coincide. Si no, los MW de entrada y salida serán incomparables.
    if network.s_base is not None and results.s_base is not None:
        if abs(network.s_base - results.s_base) > 1e-6:
            warnings.warn(
                f"Report Consistency Warning: Network S_base ({network.s_base} MVA) "
                f"differs from Results S_base ({results.s_base} MVA). "
                "The report will be generated using the respective base for each section, "
                "but direct comparison of MW/MVar columns may be invalid.",
                UserWarning
            )

    # --- 2. CONFIGURACIÓN DE VALORES POR DEFECTO ---
    
    # Nombres de Hojas
    sheets = {
        'meta': 'Solver Info',
        'in_general': 'Input - General',
        'in_buses': 'Input - Buses',
        'in_branches': 'Input - Branches',
        'res_buses': 'Result - Buses',
        'res_branches': 'Result - Branches',
    }
    if sheet_names:
        sheets.update(sheet_names)

    # Columnas por Defecto (Si son None)
    if in_bus_columns is None:
        in_bus_columns = ['id', 'type', 'base_kv', 'v_pu', 'v_guess', 'p_mw', 'q_mvar', 'g_pu', 'b_pu']
    if in_branch_columns is None:
        in_branch_columns = ['id', 'type', 'bus1', 'bus2', 'r', 'x', 'b', 'tap', 'shift', 's_max']
        
    if res_bus_columns is None:
        res_bus_columns = ['id', 'type', 'v_pu', 'v_kv', 'theta_deg', 'p_mw', 'q_mvar', 'p_mis', 'q_mis']
    if res_branch_columns is None:
        res_branch_columns = ['id', 'bus1', 'bus2', 'loading', 'p1_mw', 'q1_mvar', 'ploss_mw', 'qloss_mvar']

    # --- 3. GENERACIÓN DE DATAFRAMES ---
    dfs_to_write = []

    # A) Metadatos y General
    if include_meta:
        # Combinamos info de la red y del solver en una tabla resumen
        meta_data = {
            "Report Type": "Full Power Flow Report",
            "Network S_base (MVA)": network.s_base,
            "Result S_base (MVA)": results.s_base,
            "Solver Method": results.meta.method_name,
            "Converged": results.meta.success,
            "Iterations": results.meta.iterations,
            "Final Max Error": results.meta.final_error,
            "Buses Count": len(network.get_all_buses()),
            "Branches Count": len(network.get_all_branches())
        }
        df_meta = pd.DataFrame(list(meta_data.items()), columns=["Parameter", "Value"])
        dfs_to_write.append((sheets['meta'], df_meta))

    # B) Entradas (Definición)
    if include_inputs:
        # Exportamos usando los métodos del objeto Network
        df_in_bus = network.export_buses(columns=in_bus_columns, out_format='dataframe')
        dfs_to_write.append((sheets['in_buses'], df_in_bus))

        df_in_br = network.export_branches(columns=in_branch_columns, out_format='dataframe')
        dfs_to_write.append((sheets['in_branches'], df_in_br))

    # C) Resultados (Simulación)
    if include_results:
        # Exportamos usando los métodos del objeto Results
        df_res_bus = results.export_buses(columns=res_bus_columns, out_format='dataframe')
        dfs_to_write.append((sheets['res_buses'], df_res_bus))

        df_res_br = results.export_branches(columns=res_branch_columns, out_format='dataframe')
        dfs_to_write.append((sheets['res_branches'], df_res_br))

    # --- 4. ESCRITURA A DISCO ---
    try:
        with pd.ExcelWriter(filepath) as writer:
            for sheet_name, df in dfs_to_write:
                # Escribimos solo si el DF es válido
                if df is not None and not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # (Opcional) Ajuste de ancho de columnas básico si se usara xlsxwriter
                    # pero mantenemos esto limpio.
    except IOError as e:
        raise IOError(f"Failed to write report to '{filepath}'. Check if the file is open or permissions are denied.") from e