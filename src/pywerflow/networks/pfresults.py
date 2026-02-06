from dataclasses import dataclass, asdict
from typing import Literal, Callable, Any
from math import sqrt, degrees
import warnings

import pandas as pd
import numpy as np

# Importamos solo para tipado
from pywerflow.solvers.results import SolverMetaResult
from pywerflow.buses.solved_buses import SolvedBus
from pywerflow.branches.base_branches import SolvedBranch

# Tipos para las salidas
OutputFormat = Literal['dataframe', 'dict', 'records']


# BUS GETTERS: Reciben (bus, s_base)
_BUS_GETTERS: dict[str, Callable[[SolvedBus, float|None], Any]] = {
    # --- Identificación ---
    'id':           lambda b, s: b.id,
    'type':         lambda b, s: b.final_type.name,
    'base_kv':      lambda b, s: b.V_base,
    
    # --- Voltaje ---
    'v_pu':         lambda b, s: b.V,
    'v_kv':         lambda b, s: _req_vb(b, b.V * b.V_base), 
    'theta_rad':    lambda b, s: b.theta,
    'theta_deg':    lambda b, s: degrees(b.theta),

    # --- Potencia Neta ---
    'p_pu':         lambda b, s: b.P_net,
    'p_mw':         lambda b, s: _req_sb(s) * b.P_net,
    'q_pu':         lambda b, s: b.Q_net,
    'q_mvar':       lambda b, s: _req_sb(s) * b.Q_net,

    # --- Shunts ---
    'pshunt_pu':    lambda b, s: b.P_shunt,
    'pshunt_mw':    lambda b, s: _req_sb(s) * b.P_shunt,
    'qshunt_pu':    lambda b, s: b.Q_shunt,
    'qshunt_mvar':  lambda b, s: _req_sb(s) * b.Q_shunt,

    # --- Desajustes ---
    'p_mis':        lambda b, s: b.P_mismatch,
    'q_mis':        lambda b, s: b.Q_mismatch,
}

# BRANCH GETTERS: Reciben (branch, s_base, vbase_map)
# vbase_map es un dict {bus_id: v_base} que pasaremos al llamar
_BRANCH_GETTERS: dict[str, Callable[[SolvedBranch, float|None, dict[int, float]], Any]] = {
    # --- Identificación ---
    'id':           lambda br, s, vm: br.id,
    'bus1':         lambda br, s, vm: br.bus1,
    'bus2':         lambda br, s, vm: br.bus2,
    'loading':      lambda br, s, vm: br.loading_percent,

    # --- Potencia Extremo 1 (From) ---
    'p1_pu':        lambda br, s, vm: br.P1,
    'p1_mw':        lambda br, s, vm: _req_sb(s) * br.P1,
    'q1_pu':        lambda br, s, vm: br.Q1,
    'q1_mvar':      lambda br, s, vm: _req_sb(s) * br.Q1,
    's1_mva':       lambda br, s, vm: _req_sb(s) * br.S1,

    # --- Potencia Extremo 2 (To) ---
    'p2_pu':        lambda br, s, vm: br.P2,
    'p2_mw':        lambda br, s, vm: _req_sb(s) * br.P2,
    'q2_pu':        lambda br, s, vm: br.Q2,
    'q2_mvar':      lambda br, s, vm: _req_sb(s) * br.Q2,
    's2_mva':       lambda br, s, vm: _req_sb(s) * br.S2,

    # --- Corrientes Físicas (Aquí usamos el vbase_map) ---
    'i1_pu':        lambda br, s, vm: br.I1,
    # Buscamos la V_base del nudo 'bus1' en el mapa
    'i1_ka':        lambda br, s, vm: _calc_ika(br.I1, s, vm.get(br.bus1), br.id, br.bus1),
    
    'i2_pu':        lambda br, s, vm: br.I2,
    # Buscamos la V_base del nudo 'bus2' en el mapa
    'i2_ka':        lambda br, s, vm: _calc_ika(br.I2, s, vm.get(br.bus2), br.id, br.bus2),

    # --- Pérdidas ---
    'ploss_pu':     lambda br, s, vm: br.P_loss,
    'ploss_mw':     lambda br, s, vm: _req_sb(s) * br.P_loss,
    'qloss_pu':     lambda br, s, vm: br.Q_loss,
    'qloss_mvar':   lambda br, s, vm: _req_sb(s) * br.Q_loss,
}


@dataclass(frozen=True)
class PowerFlowResults:
    """
    Smart container for Power Flow Analysis results.
    
    It aggregates the solver metadata, the list of solved buses, and the list of
    solved branches. It provides utility methods to export data to Pandas DataFrames,
    convert units to physical values, and print summaries.
    """
    
    meta: SolverMetaResult
    """Metadata regarding the solver execution (convergence, time, error)."""
    
    buses: list[SolvedBus]
    """List of fully solved bus states."""
    
    branches: list[SolvedBranch]
    """List of computed branch flows and losses."""
    
    s_base: float | None = None
    """System base power (MVA) used for physical unit conversion."""

    # =========================================================================
    #  2. MÉTODOS PÚBLICOS DE EXPORTACIÓN
    # =========================================================================

    def export_buses(
        self, 
        columns: list[str] | None = None, 
        ids: list[int] | None = None,
        out_format: OutputFormat = 'dataframe'
    ) -> pd.DataFrame | list[dict] | dict:
        """
        Extracts specific data from SolvedBuses, handling unit conversion dynamically.

        Args:
            columns (list[str] | None): List of keys to extract. If None, defaults to 
                standard p.u. columns ['id', 'type', 'v_pu', 'theta_rad', 'p_pu', 'q_pu'].
            ids (list[int] | None): Optional list of Bus IDs to filter results. 
                If None, all buses are returned.
            out_format (Literal['dataframe', 'dict', 'records']): Output format. 
                Defaults to 'dataframe'.

        Available Keys & Descriptions:
            * **Identification**
                * `id`: Unique identifier of the bus (int).
                * `type`: Final bus type string (e.g., 'PQ', 'PV', 'SLACK').
                * `base_kv`: Base voltage of the bus in kV (if provided).

            * **Voltage State**
                * `v_pu`: Voltage magnitude in per-unit.
                * `v_kv`: Voltage magnitude in kV. *(Requires 'V_base' on the bus)*.
                * `theta_rad`: Voltage angle in radians.
                * `theta_deg`: Voltage angle in degrees.

            * **Net Power Injection** (Generation - Load)
                * `p_pu`: Net Active Power in per-unit.
                * `p_mw`: Net Active Power in MW. *(Requires 's_base' on the network)*.
                * `q_pu`: Net Reactive Power in per-unit.
                * `q_mvar`: Net Reactive Power in MVAr. *(Requires 's_base' on the network)*.

            * **Shunt Consumption** (V^2 * Y_shunt)
                * `pshunt_pu`: Active Power consumed by G_shunt in p.u.
                * `pshunt_mw`: Active Power consumed by G_shunt in MW.
                * `qshunt_pu`: Reactive Power consumed by B_shunt in p.u. (Positive = Inductive load).
                * `qshunt_mvar`: Reactive Power consumed by B_shunt in MVAr.

            * **Solver Quality**
                * `p_mis`: Active power mismatch at this node (should be < tolerance).
                * `q_mis`: Reactive power mismatch at this node (should be < tolerance).

        Returns:
            pd.DataFrame | list[dict] | dict: The extracted data in the requested format.
        
        Raises:
            ValueError: If a requested key is unknown.
            ValueError: If a physical unit key (e.g., 'p_mw') is requested but `s_base` is missing.
            ValueError: If 'v_kv' is requested but the bus has no `V_base`.
        """
        # Defaults
        if columns is None: 
            columns = ['id', 'type', 'v_pu', 'theta_rad', 'p_pu', 'q_pu']
        
        source_data = self.buses
        if ids is not None:
            id_set = set(ids)
            source_data = [b for b in source_data if b.id in id_set]

        # Para export_buses NO necesitamos el mapa de voltajes extra, 
        # ya que cada bus se conoce a sí mismo.
        # Pasamos un dummy o adaptamos _extract_data (ver abajo).
        return self._extract_data_buses(source_data, columns, out_format)


    def export_branches(
        self, 
        columns: list[str] | None = None, 
        ids: list[int] | None = None,
        out_format: OutputFormat = 'dataframe'
    ) -> pd.DataFrame | list[dict] | dict:
        """
        Extracts specific data from SolvedBranches, handling unit conversion dynamically.

        Args:
            columns (list[str] | None): List of keys to extract. If None, defaults to 
                ['id', 'bus1', 'bus2', 'p1_pu', 'p1_mw', 'q1_pu', 'q1_mvar', 'p2_pu', 'p2_mw', 'q2_pu', 'q2_mvar', 'loading'].
            ids (list[int] | None): Optional list of Branch IDs to filter results.
            out_format (Literal['dataframe', 'dict', 'records']): Output format.

        Available Keys & Descriptions:
            * **Identification**
                * `id`: Unique identifier of the branch (int).
                * `bus1`: ID of the 'From' bus.
                * `bus2`: ID of the 'To' bus.
                * `loading`: Loading percentage relative to S_max limit. (0.0 if unlimited).

            * **Power Flow at Bus 1 (From)**
                * `p1_pu`, `p1_mw`: Active Power flowing *into* the branch from Bus 1.
                * `q1_pu`, `q1_mvar`: Reactive Power flowing *into* the branch from Bus 1.
                * `s1_mva`: Apparent Power magnitude at Bus 1 in MVA. *(Requires 's_base')*.

            * **Power Flow at Bus 2 (To)**
                * `p2_pu`, `p2_mw`: Active Power flowing *into* the branch from Bus 2.
                * `q2_pu`, `q2_mvar`: Reactive Power flowing *into* the branch from Bus 2.
                * `s2_mva`: Apparent Power magnitude at Bus 2 in MVA. *(Requires 's_base')*.

            * **Current Magnitude**
                * `i1_pu`: Current entering from Bus 1 in p.u.
                * `i1_ka`: Current entering from Bus 1 in kA. *(Requires 's_base' AND 'V_base' at Bus 1)*.
                * `i2_pu`: Current entering from Bus 2 in p.u.
                * `i2_ka`: Current entering from Bus 2 in kA. *(Requires 's_base' AND 'V_base' at Bus 2)*.

            * **Total Losses** (P1 + P2)
                * `ploss_pu`, `ploss_mw`: Total Active Power dissipated in the branch.
                * `qloss_pu`, `qloss_mvar`: Total Reactive Power consumed by the branch.

        Returns:
            pd.DataFrame | list[dict] | dict: The extracted data in the requested format.

        Raises:
            ValueError: If a requested key is unknown.
            ValueError: If a physical unit key is requested but necessary base data (`s_base`, `V_base`) is missing.
        """
        # Defaults
        if columns is None: columns = ['id', 'bus1', 'bus2', 'p1_pu', 'p1_mw', 'q1_pu', 'q1_mvar', 'p2_pu', 'p2_mw', 'q2_pu', 'q2_mvar', 'loading']

        source_data = self.branches
        if ids is not None:
            id_set = set(ids)
            source_data = [br for br in source_data if br.id in id_set]

        # 1. PRE-CÁLCULO: Mapa de Tensiones Base
        # Creamos un diccionario rápido {id: v_base} usando todos los buses de la red
        vbase_map = {b.id: b.V_base for b in self.buses}

        # 2. Llamada al motor de extracción con el mapa
        return self._extract_data_branches(source_data, columns, vbase_map, out_format)


    def to_excel(
        self,
        filepath: str,
        include_buses: bool = True,
        include_branches: bool = True,
        include_meta: bool = True,
        bus_columns: list[str] | None = None,
        branch_columns: list[str] | None = None,
        sheet_names: dict[str, str] | None = None
    ):
        """
        Exports the power flow results to an Excel file (.xlsx) with configurable sheets.

        This method aggregates the solved state (Buses, Branches) and the solver's 
        performance metrics (Metadata) into a single report. It delegates the extraction 
        logic to `export_buses` and `export_branches`, ensuring consistency with 
        other output formats.

        **Defaults:**
        If column lists are not provided, a comprehensive set of standard columns 
        is selected to show the most relevant results (Voltages, Power Flows, Loading).

        Args:
            filepath (str): Destination path for the .xlsx file.
            include_buses (bool): Whether to generate a sheet for Bus Results. Default True.
            include_branches (bool): Whether to generate a sheet for Branch Results. Default True.
            include_meta (bool): Whether to generate a sheet for Solver Information. Default True.
            bus_columns (list[str] | None): Specific keys to export for buses.
                If None, defaults to: 
                ['id', 'type', 'v_pu', 'v_kv', 'theta_deg', 'p_mw', 'q_mvar', 'p_mis', 'q_mis'].
            branch_columns (list[str] | None): Specific keys to export for branches.
                If None, defaults to: 
                ['id', 'bus1', 'bus2', 'loading', 'p1_mw', 'q1_mvar', 'p2_mw', 'q2_mvar', 'ploss_mw', 'qloss_mvar'].
            sheet_names (dict[str, str] | None): Custom names for the Excel sheets.
                Default mapping: `{'buses': 'Bus Results', 'branches': 'Branch Results', 'meta': 'Solver Info'}`.

        Raises:
            ValueError: If a requested column key is invalid or physical conversion fails 
                        (e.g., missing S_base).
            IOError: If the file cannot be written.
        """
        # 1. Configuración de Defaults
        if bus_columns is None:
            bus_columns = [
                'id', 'type', 'v_pu', 'v_kv', 'theta_deg', 
                'p_mw', 'q_mvar', 'p_mis', 'q_mis'
            ]
        
        if branch_columns is None:
            branch_columns = [
                'id', 'bus1', 'bus2', 'loading', 
                'p1_mw', 'q1_mvar', 'p2_mw', 'q2_mvar', 
                'ploss_mw', 'qloss_mvar'
            ]

        # Fusión de nombres de hojas
        sheets = {
            'buses': 'Bus Results', 
            'branches': 'Branch Results', 
            'meta': 'Solver Info'
        }
        if sheet_names:
            sheets.update(sheet_names)

        # 2. Generación de DataFrames de Resultados
        df_buses = None
        if include_buses:
            df_buses = self.export_buses(columns=bus_columns, out_format='dataframe')

        df_branches = None
        if include_branches:
            df_branches = self.export_branches(columns=branch_columns, out_format='dataframe')

        # 3. Generación de DataFrame de Metadatos (Solver Info)
        df_meta = None
        if include_meta:
            # Aplanamos el objeto SolverMetaResult para que sea legible en Excel
            meta_dict = {
                "Method": self.meta.method_name,
                "Converged": self.meta.success,
                "Iterations": self.meta.iterations,
                "Final Max Error": self.meta.final_error,
                "Tolerance Used": self.meta.tolerance_used,
                "Message": self.meta.message,
                "System Base (MVA)": self.s_base
            }
            # Convertimos a DataFrame (Tabla Vertical: Parámetro | Valor)
            df_meta = pd.DataFrame(list(meta_dict.items()), columns=["Metric", "Value"])

        # 4. Escritura a Excel
        with pd.ExcelWriter(filepath) as writer:
            
            # Hoja Solver Info (Suele ser bueno ponerla primero o último, aquí la pongo primera)
            if include_meta and df_meta is not None:
                df_meta.to_excel(writer, sheet_name=sheets['meta'], index=False)

            # Hoja Buses
            if include_buses and df_buses is not None:
                df_buses.to_excel(writer, sheet_name=sheets['buses'], index=False)

            # Hoja Ramas
            if include_branches and df_branches is not None:
                df_branches.to_excel(writer, sheet_name=sheets['branches'], index=False)

    # =========================================================================
    #  MOTORES DE EXTRACCIÓN (SEPARADOS POR TIPO DE FIRMA)
    # =========================================================================

    def _extract_data_buses(self, objects: list, keys: list[str], fmt: str):
        """Motor específico para Buses (Lambda signature: obj, s_base)."""
        getters = _BUS_GETTERS
        if not objects: return pd.DataFrame(columns=keys) if fmt == 'dataframe' else []
        
        keys = [k.lower() for k in keys]
        for k in keys:
            if k not in getters: raise ValueError(f"Unknown Bus key '{k}'")

        records = []
        for obj in objects:
            row = {}
            for k in keys:
                try:
                    # Firma simple: solo objeto y s_base
                    row[k] = getters[k](obj, self.s_base)
                except Exception as e:
                    raise ValueError(f"Error calculating '{k}' for Bus {obj.id}: {str(e)}") from e
            records.append(row)

        return self._format_output(records, keys, fmt)


    def _extract_data_branches(self, objects: list, keys: list[str], vbase_map: dict, fmt: str):
        """Motor específico para Branches (Lambda signature: obj, s_base, vbase_map)."""
        getters = _BRANCH_GETTERS
        if not objects: return pd.DataFrame(columns=keys) if fmt == 'dataframe' else []

        keys = [k.lower() for k in keys]
        for k in keys:
            if k not in getters: raise ValueError(f"Unknown Branch key '{k}'")

        records = []
        for obj in objects:
            row = {}
            for k in keys:
                try:
                    # Firma extendida: pasamos el vbase_map
                    row[k] = getters[k](obj, self.s_base, vbase_map)
                except Exception as e:
                    raise ValueError(f"Error calculating '{k}' for Branch {obj.id}: {str(e)}") from e
            records.append(row)

        return self._format_output(records, keys, fmt)

    def _format_output(self, records: list, keys: list, fmt: str):
        """Helper común para formatear la salida."""
        if fmt == 'dataframe':
            return pd.DataFrame(records)
        elif fmt == 'dict':
            pk = 'id' if 'id' in keys else keys[0]
            return {r[pk]: r for r in records}
        else:
            return records


# =========================================================================
#  4. HELPERS DE CÁLCULO (FUERA DE LA CLASE PARA SER PICKLEABLE SI HICIERA FALTA)
# =========================================================================


def _req_sb(s_base: float | None) -> float:
    """Helper to ensure S_base exists before physical power calculation."""
    if s_base is None:
        raise ValueError("Physical conversion requires 's_base' in PowerFlowResults, but it is None.")
    return s_base

def _req_vb(obj: Any, val: float) -> float:
    """Helper to ensure V_base exists (for buses)."""
    if getattr(obj, 'V_base', None) is None:
         raise ValueError(f"Physical voltage conversion requires 'V_base' for bus {obj.id}, but it is None.")
    return val

def _calc_ika(i_pu: float, s_base: float | None, v_base: float | None, branch_id: int, bus_id: int) -> float:
    """
    Calculates physical current in kA using lookup V_base.
    I_ka = I_pu * S_base / (sqrt(3) * V_base).
    """
    sb = _req_sb(s_base)
    
    if v_base is None:
        # Mensaje de error detallado para que el usuario sepa qué falta
        raise ValueError(
            f"Cannot calculate physical current (kA) for Branch {branch_id} at Bus {branch_id}: "
            f"Bus {bus_id} does not have a defined 'V_base'."
        )
    
    # I_base_kA = S_MVA / (sqrt(3) * V_kV)
    # math.sqrt es más rápido que numpy.sqrt para escalares
    i_base = sb / (sqrt(3) * v_base)
    return i_pu * i_base







# def to_excel(self, filepath: str, include_metadata: bool = True) -> None:
#     """
#     Exports simulation results to an Excel file with multiple sheets.

#     The generated file includes:
#     - 'Bus Results': Detailed bus state (V, P, Q) and mismatches.
#     - 'Branch Results': Branch flows, loading percentages, and losses.
#     - 'Solver Info' (Optional): Metadata about convergence, iterations, and errors.

#     Args:
#         filepath (str): Destination path for the .xlsx file.
#         include_metadata (bool, optional): If True, adds a sheet with solver 
#             diagnostics and metadata. Defaults to True.
#     """
#     import pywerflow.io.excel_io as excel_io
#     excel_io.export_results_to_excel(self, filepath, include_metadata)





# --- ACCESORES DE PANDAS ---

# @property
# def buses_df(self) -> pd.DataFrame:
#     """
#     Returns the bus results as a Pandas DataFrame (in p.u.).
#     """
#     if not self.buses:
#         return pd.DataFrame()
    
#     # Usamos asdict porque SolvedBus tiene __slots__, por lo que vars() fallaría.
#     data = [asdict(b) for b in self.buses]
#     return pd.DataFrame(data)

# @property
# def branches_df(self) -> pd.DataFrame:
#     """
#     Returns the branch results as a Pandas DataFrame (in p.u.).
#     """
#     if not self.branches:
#         return pd.DataFrame()
        
#     # Usamos asdict para convertir recursivamente los dataclasses a dicts
#     data = [asdict(b) for b in self.branches]
#     return pd.DataFrame(data)

# # --- MÉTODOS DE CONVERSIÓN FÍSICA ---

# def get_physical_buses_df(self, base_kv_map: dict[int, float] | None = None) -> pd.DataFrame:
#     """
#     Generates a DataFrame with physical magnitudes (MW, MVar, kV).

#     Args:
#         base_kv_map: Optional dictionary mapping Bus IDs to their Base kV.
#                      Required to calculate physical voltages (kV).

#     Returns:
#         pd.DataFrame: Copy of bus results with added physical columns.
#     """
#     df = self.buses_df.copy()
    
#     if df.empty:
#         return df

#     # 1. Conversión de Potencia (S_base es global para toda la red)
#     # Verificamos que s_base_mva no sea None y sea positivo
#     if self.s_base is not None and self.s_base > 0:
#         factor = self.s_base
#         df['P_MW'] = df['P_net'] * factor
#         df['Q_MVar'] = df['Q_net'] * factor
#         df['P_shunt_MW'] = df['P_shunt'] * factor
#         df['Q_shunt_MVar'] = df['Q_shunt'] * factor
    
#     # 2. Conversión de Voltaje (Requiere mapa de kV base por nudo)
#     if base_kv_map:
#         # Si el DataFrame tiene columna 'id', hacemos el mapeo
#         if 'id' in df.columns:
#             df['base_kv'] = df['id'].map(base_kv_map)
#             # Calculamos kV físicos: V(pu) * V_base(kV)
#             df['V_kV'] = df['V'] * df['base_kv']
        
#     return df

# # --- REPORTING Y EXPORTACIÓN ---

# def print_report(
#     self, 
#     bus_ids: list[int] | Literal['all'] | None = None, 
#     branch_ids: list[int] | Literal['all'] | None = None
# ):
#     """
#     Prints a formatted summary of the power flow results to the console.

#     Args:
#         bus_ids: Optional list of specific Bus IDs to display, or 'all' to show the full table.
#                  Defaults to None (shows only Top 5).
#         branch_ids: Optional list of specific Branch IDs to display, or 'all' to show the full table.
#                  Defaults to None (shows only Top 5).
#     """
#     # Accedemos a meta.success en lugar de self.success
#     if not self.meta.success:
#         print(f"⚠️  SOLVER FAILED: {self.meta.message}")
#         return

#     # Preparamos strings auxiliares para el reporte
#     time_str = f" ({self.meta.extras.get('time', 'N/A')} s)" if 'time' in self.meta.extras else ""
#     iter_str = f"{self.meta.iterations}" if self.meta.iterations is not None else "?"
#     error_str = f"{self.meta.final_error:.2e}" if self.meta.final_error is not None else "?"

#     print(f"\n✅ Converged in {iter_str} iterations{time_str}")
#     print(f"   Max Mismatch: {error_str} p.u.")
#     print("-" * 60)
    
#     # --- LÓGICA DE FILTRADO DE BUSES ---
#     cols_buses = ['id', 'V', 'theta', 'P_net', 'Q_net']
#     available_cols = [c for c in cols_buses if c in self.buses_df.columns]
    
#     b_df_display = self.buses_df[available_cols]
#     b_title = "(Top 5)"

#     if bus_ids == 'all':
#         b_title = "(All)"
#         # No aplicamos filtro, mostramos todo
#     elif isinstance(bus_ids, list):
#         # Filtramos por los IDs solicitados
#         b_df_display = b_df_display[b_df_display['id'].isin(bus_ids)]
#         b_title = f"(Selected: {len(bus_ids)})"
#     else:
#         # Comportamiento por defecto
#         b_df_display = b_df_display.head(5)

#     print(f"BUS RESULTS {b_title}:")
#     print(b_df_display.to_string(index=False))
    
#     # --- LÓGICA DE FILTRADO DE RAMAS ---
#     cols_branches = ['id', 'bus1', 'bus2', 'loading_percent']
#     available_cols_br = [c for c in cols_branches if c in self.branches_df.columns]
    
#     br_df_display = self.branches_df[available_cols_br]
#     br_title = "(Top 5)"

#     if branch_ids == 'all':
#         br_title = "(All)"
#     elif isinstance(branch_ids, list):
#         br_df_display = br_df_display[br_df_display['id'].isin(branch_ids)]
#         br_title = f"(Selected: {len(branch_ids)})"
#     else:
#         br_df_display = br_df_display.head(5)

#     print(f"\nBRANCH RESULTS {br_title}:")
#     print(br_df_display.to_string(index=False))

# def to_excel(self, filepath: str):
#     """
#     Exports the results to an Excel file with multiple sheets.

#     Args:
#         filepath: Destination path for the .xlsx file.
#     """
#     b_df = self.buses_df
#     br_df = self.branches_df

#     # Validar si hay datos antes de escribir
#     with pd.ExcelWriter(filepath) as writer:
#         if not b_df.empty:
#             b_df.to_excel(writer, sheet_name="Buses (pu)", index=False)
#         if not br_df.empty:
#             br_df.to_excel(writer, sheet_name="Branches (pu)", index=False)
        
#         # Guardamos los metadatos en una hoja separada para trazabilidad
#         meta_series = pd.Series(asdict(self.meta))
#         meta_series.to_excel(writer, sheet_name="Metadata", header=False)

