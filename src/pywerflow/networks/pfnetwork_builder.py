from typing import Sequence, TYPE_CHECKING
import pandas as pd
import numpy as np
import warnings
import json  
from math import radians
from dataclasses import replace 


from pywerflow.io.matpower import read_matpower_file
from pywerflow.buses.input_buses import InputBus, SlackBus, PVBus, PQBus
from pywerflow.buses.bus_types import BusTypes
from pywerflow.branches.pfsolvable_branches import PFSolvableBranch, SimpleTransformer, PiLine, RawBranch, PiTransformer
from pywerflow.networks.pf_network import PowerFlowNetwork
from pywerflow.validation_utils import (
    auto_validate, 
    validator, 
    validate_ranges, 
    validate_types
)






class PFNetworkBuilder:
    """
    Unified builder class for Power Networks.

    This builder enforces a linear workflow:
    1. (Optional) Set System Base Power (S_base).
       * Must be set BEFORE importing any physical data (except voltages).
       * Once set, it cannot be modified to ensure data consistency.
    2. Add Buses and Branches.
       * Duplicates are rejected immediately.
       * Physical units are converted to per-unit immediately.
    3. Build.
       * Validates global topology (Slack count, connectivity).
    """
    
    def __init__(self):
        self._s_base: float | None = None
        
        # Almacenamiento directo de objetos finales (siempre en p.u.)
        self._buses: list[InputBus] = []
        self._branches: list[PFSolvableBranch] = []

        # Sets para control de duplicados O(1)
        self._seen_bus_ids: set[int] = set()
        self._seen_branch_ids: set[int] = set()

    # --- PROPERTIES (READ-ONLY) ---

    @property
    def s_base(self) -> float | None:
        """Read-only access to the System Base MVA."""
        return self._s_base

    @property
    def buses(self) -> list[InputBus]:
        """
        Returns a read-only copy of the added buses.
        """
        return self._buses[:] 

    @property
    def branches(self) -> list[PFSolvableBranch]:
        """
        Returns a read-only copy of the added branches.
        """
        return self._branches[:]

    # --- CONFIGURATION ---

    def set_base_mva(self, s_base_mva: float):
        """
        Sets the system base power (S_base).
        
        This method locks the S_base. Once set, it cannot be changed to prevent
        inconsistencies with previously added data.

        Args:
            s_base_mva: System base power in MVA (must be > 0).

        Raises:
            RuntimeError: If S_base was already set.
            ValueError: If s_base_mva <= 0.
        """
        if self._s_base is not None:
            raise RuntimeError(
                "Builder Configuration Error: 's_base' is already set and cannot be changed. "
                "Changing the base would invalidate previously converted per-unit values."
            )

        self._s_base = float(s_base_mva)
        
        # Validamos que sea positivo usando tu utilidad
        validate_ranges(self, {"s_base": (0, None, "()")}) 
        
        return self

    # --- IMMEDIATE ADDITION (OBJECTS) ---

    def add_buses(self, buses: Sequence[InputBus]):
        """
        Adds fully formed InputBus objects (already in p.u.).

        Args:
            buses: Sequence of InputBus objects.

        Raises:
            ValueError: If a duplicate Bus ID is detected.
        """
        for bus in buses:
            # Validación de Tipo
            if not isinstance(bus, InputBus):
                raise TypeError(f"Expected 'InputBus', got '{type(bus).__name__}'.")

            # Validación de Duplicados (cubre tanto históricos como la propia lista actual)
            if bus.id in self._seen_bus_ids:
                raise ValueError(f"Builder Error: Bus ID {bus.id} is duplicated (already added or repeated in input).")

            self._seen_bus_ids.add(bus.id)
            self._buses.append(bus)
        
        return self

    def add_branches(self, branches: Sequence[PFSolvableBranch]):
        """
        Adds fully formed PFSolvableBranch objects.

        Args:
            branches: Sequence of PFSolvableBranch objects.

        Raises:
            ValueError: If a duplicate Branch ID is detected.
        """
        for branch in branches:
            # Validación de Tipo
            if not isinstance(branch, PFSolvableBranch):
                raise TypeError(f"Expected 'PFSolvableBranch', got '{type(branch).__name__}'.")

            # Validación de Duplicados
            if branch.id in self._seen_branch_ids:
                raise ValueError(f"Builder Error: Branch ID {branch.id} is duplicated.")

            self._seen_branch_ids.add(branch.id)
            self._branches.append(branch)
        
        return self

    # --- IMMEDIATE ADDITION (RAW DATA) ---


    @staticmethod
    def _normalize_input(
        data: pd.DataFrame | np.ndarray | list[list] | list[dict], 
        columns: list[str] | None
    ) -> list[dict]:
        """
        Normalizes raw input data into a standardized list of dictionaries with lowercase keys.

        This helper handles three main data structures:
        1.  **DataFrame:** Ignores 'columns' argument (warns if present), lowercases existing columns, 
            and converts to dict records.
        2.  **Array / List of Lists:** Requires 'columns' argument. Validates that all rows match 
            the column count and maps values to lowercase keys.
        3.  **List of Dictionaries:** Ignores 'columns' argument (warns if present), lowercases all keys in every dictionary.

        Args:
            data: The raw input data.
            columns: Optional list of column names (mandatory for arrays/lists).

        Returns:
            list[dict]: A list of dictionaries where keys are normalized strings.

        Raises:
            TypeError: If the data format is not supported.
            ValueError: If columns are missing for array inputs or row lengths are inconsistent.
        """
        
        # 1. CASO DATAFRAME
        if isinstance(data, pd.DataFrame):
            # Comprobamos si el usuario pasó columns innecesariamente
            if columns is not None:
                warnings.warn("Argument 'columns' ignored when using DataFrame. The columns from the DataFrame itself will be used.")
            
            # Trabajamos sobre una copia para no alterar el objeto original del usuario
            df = data.copy()
            
            # Convertimos todas las columnas a minúsculas
            df.columns = [str(c).lower() for c in df.columns]
            
            # Convertimos a lista de diccionarios (cada fila es un dict con las mismas claves)
            return df.to_dict(orient='records')

        # 2. CASO LISTA DE DICCIONARIOS
        # Detectamos si es una lista y, si tiene contenido, si el primer elemento es un dict.
        # Si está vacía, asumimos que es válida y devolvemos lista vacía.
        elif isinstance(data, list) and (len(data) == 0 or isinstance(data[0], dict)):
            # Comprobamos si el usuario pasó columns innecesariamente
            if columns is not None:
                warnings.warn("Argument 'columns' ignored when using list of dicts. The keys from the dictionaries themselves will be used.")
            
            normalized_list = []
            for row in data:
                # Simplemente reconstruimos el diccionario con las claves en minúscula
                # No validamos si tienen las mismas claves entre sí (según tu instrucción)
                new_row = {str(k).lower(): v for k, v in row.items()}
                normalized_list.append(new_row)
            return normalized_list

        # 3. CASO NDARRAY O LISTA DE LISTAS
        elif isinstance(data, (np.ndarray, list)):
            # Aquí el argumento columns es OBLIGATORIO
            if not columns:
                raise ValueError("The 'columns' argument is mandatory for array-type entries or lists of lists.")
            
            # Normalizamos las columnas objetivo a minúsculas para mantener consistencia con el caso DataFrame
            normalized_cols = [str(c).lower() for c in columns]
            expected_len = len(normalized_cols)
            
            normalized_list = []
            
            for i, row in enumerate(data):
                # Validamos longitud de la fila
                if len(row) != expected_len:
                    raise ValueError(
                        f"Length error in row {i}. "
                        f"{expected_len} elements were expected (according to 'columns'), but {len(row)} were found."
                    )
                
                # Convertimos a diccionario usando zip para mapear columna -> valor
                # Esto garantiza que todos los diccionarios resultantes tengan EXACTAMENTE las mismas claves
                record = dict(zip(normalized_cols, row))
                normalized_list.append(record)
                
            return normalized_list

        # 4. TIPO NO SOPORTADO
        else:
            raise TypeError(f"Unsupported data format: {type(data).__name__}.")


# --- EDITING AND MANAGEMENT METHODS -----------------------------------------

    def get_bus(self, bus_id: int) -> InputBus:
        """
        Retrieves a bus object previously added to the builder by its unique ID.

        This method performs a search within the internal staging list. It is useful 
        for inspecting the current state of a bus before modifying or removing it.

        Args:
            bus_id (int): The unique identifier of the bus to retrieve.

        Returns:
            InputBus: The bus object corresponding to the provided ID.

        Raises:
            KeyError: If no bus with the specified `bus_id` exists in the builder.
        """
        # Búsqueda lineal en la lista de almacenamiento.
        # Dado que el builder es una etapa temporal, una lista es suficiente.
        for bus in self._buses:
            if bus.id == bus_id:
                return bus
        
        # Si terminamos el bucle sin éxito, lanzamos error.
        raise KeyError(f"Bus ID {bus_id} not found in the Builder staging area.")

    def get_branch(self, branch_id: int) -> PFSolvableBranch:
        """
        Retrieves a branch object previously added to the builder by its unique ID.

        Args:
            branch_id (int): The unique identifier of the branch to retrieve.

        Returns:
            PFSolvableBranch: The branch object corresponding to the provided ID.

        Raises:
            KeyError: If no branch with the specified `branch_id` exists.
        """
        for branch in self._branches:
            if branch.id == branch_id:
                return branch
        
        raise KeyError(f"Branch ID {branch_id} not found in the Builder staging area.")

    def remove_bus(self, bus_id: int):
        """
        Removes a bus from the builder's staging area.

        This operation deletes the bus definition and releases its ID, allowing 
        it to be reused if necessary.

        Args:
            bus_id (int): The unique identifier of the bus to remove.

        Returns:
            self: The builder instance (Fluent Interface).

        Raises:
            KeyError: If the bus ID does not exist.
        """
        idx_to_remove = None
        
        # Buscamos el índice del elemento a borrar.
        for i, bus in enumerate(self._buses):
            if bus.id == bus_id:
                idx_to_remove = i
                break
        
        if idx_to_remove is None:
            raise KeyError(f"Cannot remove: Bus ID {bus_id} does not exist.")
        
        # Eliminamos el objeto de la lista principal.
        del self._buses[idx_to_remove]
        
        # IMPORTANTE: Liberamos el ID del set de control para permitir re-inserción futura.
        self._seen_bus_ids.remove(bus_id)
        
        return self

    def remove_branch(self, branch_id: int):
        """
        Removes a branch from the builder's staging area.

        Args:
            branch_id (int): The unique identifier of the branch to remove.

        Returns:
            self: The builder instance (Fluent Interface).

        Raises:
            KeyError: If the branch ID does not exist.
        """
        idx_to_remove = None
        
        for i, branch in enumerate(self._branches):
            if branch.id == branch_id:
                idx_to_remove = i
                break
        
        if idx_to_remove is None:
            raise KeyError(f"Cannot remove: Branch ID {branch_id} does not exist.")
        
        del self._branches[idx_to_remove]
        self._seen_branch_ids.remove(branch_id)
        
        return self

    def modify_bus(self, bus_id: int, **changes):
        """
        Modifies attributes of an existing bus in the staging area.

        Since `InputBus` objects are immutable (frozen dataclasses), this method 
        does not mutate the object in place. Instead, it creates a new copy with 
        the updated values and replaces the old instance in the internal list.

        **Constraints:**
        The `id` attribute cannot be modified to ensure consistency with the 
        internal indexing sets. To change an ID, remove the bus and add a new one.

        Args:
            bus_id (int): The unique identifier of the bus to modify.
            **changes: Keyword arguments matching the attribute names to update 
                       (e.g., `V=1.05`, `P=0.8`).

        Returns:
            self: The builder instance (Fluent Interface).

        Raises:
            KeyError: If the bus ID is not found.
            ValueError: If an attempt is made to change the 'id' attribute.
            TypeError: If the provided arguments are invalid for the specific Bus class.
        """
        # Bloqueo de seguridad: No permitir cambiar la clave primaria (ID).
        if 'id' in changes:
            raise ValueError("Modifying the 'id' of a bus is forbidden. Please remove it and add a new one.")

        target_idx = None
        current_bus = None
        
        # 1. Localización del objeto objetivo.
        for i, bus in enumerate(self._buses):
            if bus.id == bus_id:
                target_idx = i
                current_bus = bus
                break
        
        if current_bus is None:
            raise KeyError(f"Cannot modify: Bus ID {bus_id} not found.")

        # 2. Aplicación de cambios (Copy-on-write).
        # Usamos dataclasses.replace que devuelve una nueva instancia validada.
        try:
            new_bus = replace(current_bus, **changes)
        except TypeError as e:
            raise TypeError(f"Invalid argument for {type(current_bus).__name__}: {e}") from e

        # 3. Sustitución en la lista.
        self._buses[target_idx] = new_bus
        
        return self

    def modify_branch(self, branch_id: int, **changes):
        """
        Modifies attributes of an existing branch in the staging area.

        Similar to `modify_bus`, this method performs a safe replacement of the 
        immutable branch object.

        **Topology Changes:**
        Unlike the `modify_bus` method, modifying topological connections 
        (`bus1`, `bus2`) IS allowed here. The Builder does not validate 
        connectivity until `build()` is called, allowing you to fix connection 
        errors (e.g., reconnecting a line to a different bus) freely during the 
        construction phase.

        Args:
            branch_id (int): The unique identifier of the branch to modify.
            **changes: Keyword arguments matching the attribute names to update 
                       (e.g., `R=0.01`, `bus2=5`).

        Returns:
            self: The builder instance (Fluent Interface).

        Raises:
            KeyError: If the branch ID is not found.
            ValueError: If an attempt is made to change the 'id' attribute.
            TypeError: If the provided arguments are invalid for the specific Branch class.
        """
        if 'id' in changes:
            raise ValueError("Modifying the 'id' of a branch is forbidden.")

        target_idx = None
        current_branch = None
        
        # 1. Localización del objeto.
        for i, br in enumerate(self._branches):
            if br.id == branch_id:
                target_idx = i
                current_branch = br
                break
        
        if current_branch is None:
            raise KeyError(f"Cannot modify: Branch ID {branch_id} not found.")

        # 2. Aplicación de cambios.
        # Permitimos cambiar bus1/bus2 sin validar existencia todavía (lazy validation).
        try:
            new_branch = replace(current_branch, **changes)
        except TypeError as e:
            raise TypeError(f"Invalid argument for {type(current_branch).__name__}: {e}") from e

        # 3. Sustitución.
        self._branches[target_idx] = new_branch
        
        return self


    def add_buses_from_data(
        self, 
        data: pd.DataFrame | np.ndarray | list[list],
        columns: list[str] | None = None
    ):
        """
        Parses raw data into InputBus objects, handling unit conversion and type-specific logic.

        This method normalizes input data (case-insensitive keys), validates mutual exclusivity 
        between physical and per-unit magnitudes, and maps values to the specific attributes 
        required by each Bus Type (Slack, PV, PQ).

        Args:
            data: Input data source. Can be a pandas DataFrame, a numpy ndarray, or a list of lists.
            columns: List of column names. Mandatory if `data` is not a DataFrame. 
                     If `data` is a DataFrame, its own columns are used.

        Supported Column Names (Case-Insensitive):
            * **Identification:** 'id' (int), 'type' (BusTypes enum or int: 1=PQ, 2=PV, 3=Slack).
            * **Base:** 'base_kv' (Mandatory for physical voltage conversion).
            * **Voltage Magnitude:** 'v_pu', 'v_kv'.
            * **Voltage Angle:** 'theta_rad', 'theta_deg'.
            * **Active Power:** 'p_pu', 'p_mw' (Net); 'pgen_pu', 'pgen_mw' (Generation); 'pload_pu', 'pload_mw' (Load).
            * **Reactive Power:** 'q_pu', 'q_mvar' (Net); 'qgen_pu', 'qgen_mvar' (Generation); 'qload_pu', 'qload_mvar' (Load).
            * **Shunt Admittance:** 'g_pu', 'b_pu', 'g_siemens', 'b_siemens'.

        Conversion Logic:
            * **Physical Voltage ('v_kv'):** Converted using the row's 'base_kv'.
            * **Physical Power ('_mw', '_mvar'):** Converted using the Builder's `s_base`.
            * **Physical Admittance ('_siemens'):** Converted using derived Z_base = (base_kv^2) / s_base.

        Constraints & Precedence:
            1.  **Unit Exclusivity:** A magnitude cannot be defined in both p.u. and physical units simultaneously 
                (e.g., providing both 'p_pu' and 'p_mw' raises an error).
            2.  **Net vs. Component Power:** * If Net Power ('p_...') is provided, Generation and Load columns are forbidden.
                * If Generation or Load is provided, Net Power columns are forbidden.
                * Net Power is calculated as: P_net = P_gen - P_load (missing components assume 0).
            3.  **Missing Base:** providing physical power requires `s_base` to be set in the Builder. 
                Providing physical voltage requires 'base_kv' in the row.

        Bus Type Interpretation:
            * **Slack:** Uses V and Theta as fixed setpoints. Ignores Power (P, Q).
            * **PV:** Uses P and V as fixed setpoints. Uses Theta as initial guess. Ignores Q.
            * **PQ:** Uses P and Q as fixed setpoints. Uses V and Theta as initial guesses.

        Raises:
            ValueError: If constraints (exclusivity, missing base) are violated or IDs are duplicated.
            TypeError: If data types are inconsistent.
        """

        ####################################### CONVERSION #########################################
        # CASO 1: PANDAS DATAFRAME
        normalized_data = self._normalize_input(data, columns)
        

        # Preprocesamiento: Convierto las keys en minusculas
        for i, bus in enumerate(normalized_data):
            bus: dict
            # Busqueda de id y tipo
            id = bus["id"] 
            if not id.is_integer():
                raise ValueError(f"Row {i}: Bus ID must be an integer. Got {id}.")
            id = int(id)
            type = BusTypes(bus["type"])
            
            z_base = bus["base_kv"]**2/self._s_base if ("base_kv" in bus and self._s_base is not None) else None

            # Validación de exclusividad para Voltaje (V)
            if 'v_pu' in bus and 'v_kv' in bus:
                raise ValueError(f"Ambiguity Error: Cannot provide both 'v_pu' and 'v_kv'.")

            # 2. Validación de exclusividad para Ángulo (Theta)
            if 'theta_rad' in bus and 'theta_deg' in bus:
                raise ValueError(f"Ambiguity Error: Cannot provide both 'theta_rad' and 'theta_deg'.")

            # 3. Validación de exclusividad para Conductancia Shunt (G)
            if 'g_pu' in bus and 'g_siemens' in bus:
                raise ValueError(f"Ambiguity Error: Cannot provide both 'g_pu' and 'g_siemens'.")

            # 4. Validación de exclusividad para Susceptancia Shunt (B)
            if 'b_pu' in bus and 'b_siemens' in bus:
                raise ValueError(f"Ambiguity Error: Cannot provide both 'b_pu' and 'b_siemens'.")

            try:
                if type is BusTypes.SLACK:
                    bus_obj = SlackBus(
                        id = id,
                        V = bus["v_pu"] if "v_pu" in bus else bus["v_kv"]/bus["base_kv"],
                        theta = bus["theta_rad"] if "theta_rad" in bus else radians(bus["theta_deg"]),
                        G_shunt = bus["g_pu"] if "g_pu" in bus else (bus["g_siemens"]*z_base if "g_siemens" in bus else 0),
                        B_shunt = bus["b_pu"] if "b_pu" in bus else (bus["b_siemens"]*z_base if "b_siemens" in bus else 0),
                        V_base = bus["base_kv"] if "base_kv" in bus else None,
                    )
                elif type is BusTypes.PV:
                    bus_obj = PVBus(
                        id = id,
                        P = self._extract_power_generic(bus, "p", id),
                        V = bus["v_pu"] if "v_pu" in bus else bus["v_kv"]/bus["base_kv"],
                        G_shunt = bus["g_pu"] if "g_pu" in bus else (bus["g_siemens"]*z_base if "g_siemens" in bus else 0),
                        B_shunt = bus["b_pu"] if "b_pu" in bus else (bus["b_siemens"]*z_base if "b_siemens" in bus else 0),
                        theta_guess = bus["theta_rad"] if "theta_rad" in bus else ( radians(bus["theta_deg"]) if "theta_deg" in bus else 0 ),
                        V_base = bus["base_kv"] if "base_kv" in bus else None,
                    )
                elif type is BusTypes.PQ:
                    bus_obj = PQBus(
                        id = id,
                        P = self._extract_power_generic(bus, "p", id),
                        Q = self._extract_power_generic(bus, "q", id),
                        G_shunt = bus["g_pu"] if "g_pu" in bus else (bus["g_siemens"]*z_base if "g_siemens" in bus else 0),
                        B_shunt = bus["b_pu"] if "b_pu" in bus else (bus["b_siemens"]*z_base if "b_siemens" in bus else 0),
                        V_guess = bus["v_pu"] if "v_pu" in bus else ( bus["v_kv"]/bus["base_kv"] if "base_kv" in bus and "v_kv" in bus else 1),
                        theta_guess = bus["theta_rad"] if "theta_rad" in bus else ( radians(bus["theta_deg"]) if "theta_deg" in bus else 0 ),
                        V_base = bus["base_kv"] if "base_kv" in bus else None,
                    )

                else:
                    raise TypeError(f"Row {i}: Unsupported BusType '{type}'. Expected SLACK, PV, or PQ.")
                
            except KeyError as e:
                raise KeyError(f"Missing required data for Bus {id} ({type}). Details: {str(e)}") from e


            # Verificacion de ID no duplicado
            if bus_obj.id in self._seen_bus_ids:
                raise ValueError(f"Builder Error: Bus ID {bus_obj.id} is duplicated (already added or repeated in input).")


            self._seen_bus_ids.add(bus_obj.id)
            self._buses.append(bus_obj)
      

    def _extract_power_generic(self, bus_dict: dict, prefix: str, bus_id: int) -> float:
        """
        Generic helper to extract Power (P or Q) handling exclusivity rules.
        
        Args:
            bus_dict: The normalized row data.
            prefix: 'p' or 'q'.
            bus_id: ID for error reporting.
        """
        if prefix != "q" and prefix != "p":
            raise RuntimeError(f"CRITICAL ISSUE: An unexpected prefix has been provided for the power (p or q) in the builder: {prefix} ")
        
        unit_suffix = "mw" if prefix=="p" else "mvar"
        # Generamos las claves dinámicamente
        k_net_pu = f"{prefix}_pu"         # ej: p_pu
        k_net_phy = f"{prefix}_{unit_suffix}" # ej: p_mw
        
        k_gen_pu = f"{prefix}gen_pu"      # ej: pgen_pu
        k_gen_phy = f"{prefix}gen_{unit_suffix}"
        
        k_load_pu = f"{prefix}load_pu"
        k_load_phy = f"{prefix}load_{unit_suffix}"

        # Sets de claves presentes en el diccionario
        keys_in_dict = set(bus_dict.keys())
        
        # Grupos de claves
        group_net = {k_net_pu, k_net_phy}
        group_comp = {k_gen_pu, k_gen_phy, k_load_pu, k_load_phy}
        group_phy = {k_net_phy, k_gen_phy, k_load_phy}

        # 1. Chequeo S_base: Si hay ALGUNA variable física, s_base debe existir
        # Intersección de claves presentes con claves físicas posibles
        if not keys_in_dict.isdisjoint(group_phy):
            if self._s_base is None:
                raise ValueError(f"Bus {bus_id}: Physical power data ({unit_suffix.upper()}) provided but Builder 's_base' is not set.")

        # 2. Chequeo Exclusividad: Neto vs Componentes
        has_net = not keys_in_dict.isdisjoint(group_net)
        has_comp = not keys_in_dict.isdisjoint(group_comp)

        if has_net and has_comp:
            raise ValueError(f"Bus {bus_id}: Ambiguous {prefix.upper()} data. Provided both Net value and Generation/Load components.")

        # 3. Extracción Valor Neto
        if has_net:
            # Check doble definición (PU y Fisico a la vez)
            if k_net_pu in bus_dict and k_net_phy in bus_dict:
                raise ValueError(f"Bus {bus_id}: Cannot provide both '{k_net_pu}' and '{k_net_phy}'.")
            
            if k_net_pu in bus_dict:
                return float(bus_dict[k_net_pu])
            else:
                return float(bus_dict[k_net_phy]) / self._s_base

        # 4. Extracción Componentes (Gen - Load)
        elif has_comp:
            # --- GENERACIÓN ---
            if k_gen_pu in bus_dict and k_gen_phy in bus_dict:
                raise ValueError(f"Bus {bus_id}: Cannot provide both '{k_gen_pu}' and '{k_gen_phy}'.")
            
            val_gen = 0.0
            if k_gen_pu in bus_dict:
                val_gen = float(bus_dict[k_gen_pu])
            elif k_gen_phy in bus_dict:
                val_gen = float(bus_dict[k_gen_phy]) / self._s_base
            
            # --- CARGA ---
            if k_load_pu in bus_dict and k_load_phy in bus_dict:
                raise ValueError(f"Bus {bus_id}: Cannot provide both '{k_load_pu}' and '{k_load_phy}'.")
            
            val_load = 0.0
            if k_load_pu in bus_dict:
                val_load = float(bus_dict[k_load_pu])
            elif k_load_phy in bus_dict:
                val_load = float(bus_dict[k_load_phy]) / self._s_base
            
            return val_gen - val_load

        # 5. Si no hay nada
        else:
            raise ValueError(f"Bus {bus_id}: Missing power data for {prefix.upper()}. Must provide either Net or Gen/Load.")


    def _get_p_from_dict_OLD(self, bus_dict: dict):

        net_p_keys = ['p_pu', 'p_mw']
        genload_p_keys = ['pgen_pu', 'pgen_mw', 'pload_pu', 'pload_mw']
        phy_p_keys = ['p_pu', 'p_mw','pgen_pu', 'pgen_mw', 'pload_pu', 'pload_mw']

        net_p_in = [ k for k in net_p_keys if k in bus_dict ]
        genload_p_in = [ k for k in genload_p_keys if k in bus_dict ]
        phy_p_in = [ k for k in phy_p_keys if k in bus_dict ]

        len_net_p_in = len(net_p_in)
        len_genload_p_in = len(genload_p_in)
        len_phy_p_in = len(phy_p_in)
        

        if len_phy_p_in>0 and self._s_base is None:
            raise ValueError("No puedes meter potencias en formato fisico si no has metido antes sbase...")


        # Hay versiones "netas"
        if len_net_p_in > 0: 
            # Tambien hay versiones genload
            if len_genload_p_in > 0:
                raise ValueError(f"Se han metido valores netos de P y tambien versiones gen o load")
            # No hay versiones genload pero hay mas de 1 version neta
            elif len_net_p_in>1:
                raise ValueError(f"Se han metido varios valores de P neta")
            # Solo hay UNA version 
            else:
                return bus_dict[net_p_in[0]] if net_p_in[0]=="p_pu" else bus_dict[net_p_in[0]]/self._s_base
        
        # Hay versiones genload
        elif len_genload_p_in>0:
            if len_genload_p_in > 2:
                raise ValueError("Imposible, puede haber 2 como mucho. Si hay mas algo está mal...")
            # Se han especificado o 1 o 2 p de tipo genload

            # Esto es lo que NO tiene que pasar: Que haya 2 pgen o 2 pload
            elif ("pgen_pu" in bus_dict and "pgen_mw" in bus_dict) or ("pload_pu" in bus_dict and "pload_mw" in bus_dict):
                raise ValueError("Esto mal")
            # Ahora sí, estamos seguros
            else:
                p_gen = bus_dict.get("pgen_pu", 0) + bus_dict.get("pgen_mw", 0)/self._s_base
                p_load = bus_dict.get("pload_pu", 0) + bus_dict.get("pload_mw", 0)/self._s_base
                return p_gen - p_load

        else:
            raise ValueError(f"No se han pasado versiones netas ni versiones genload")

            # Puede ser error
            # Puede ser que todo se decida
            
        

        # * **Active Power:** 'p_pu', 'p_mw' (Net); 'pgen_pu', 'pgen_mw' (Generation); 'pload_pu', 'pload_mw' (Load).
        # * **Reactive Power:** 'q_pu', 'q_mvar' (Net); 'qgen_pu', 'qgen_mvar' (Generation); 'qload_pu', 'qload_mvar' (Load).


    def _get_q_from_dict_OLD(self, bus_dict: dict):

        net_q_keys = ['q_pu', 'q_mw']
        genload_q_keys = ['qgen_pu', 'qgen_mw', 'qload_pu', 'qload_mw']
        phy_q_keys = ['q_pu', 'q_mw','qgen_pu', 'qgen_mw', 'qload_pu', 'qload_mw']

        net_q_in = [ k for k in net_q_keys if k in bus_dict ]
        genload_q_in = [ k for k in genload_q_keys if k in bus_dict ]
        phy_q_in = [ k for k in phy_q_keys if k in bus_dict ]

        len_net_q_in = len(net_q_in)
        len_genload_q_in = len(genload_q_in)
        len_phy_q_in = len(phy_q_in)

        if len_phy_q_in>0 and self._s_base is None:
            raise ValueError("No puedes meter potencias en formato fisico si no has metido antes sbase...")

        # Hay versiones "netas"
        if len_net_q_in > 0: 
            # Tambien hay versiones genload
            if len_genload_q_in > 0:
                raise ValueError(f"Se han metido valores netos de Q y tambien versiones gen o load")
            # No hay versiones genload pero hay mas de 1 version neta
            elif len_net_q_in>1:
                raise ValueError(f"Se han metido varios valores de Q neta")
            # Solo hay UNA version 
            else:
                return bus_dict[net_q_in[0]] if net_q_in[0]=="q_pu" else bus_dict[net_q_in[0]]/self._s_base
        
        # Hay versiones genload
        elif len_genload_q_in>0:
            if len_genload_q_in > 2:
                raise ValueError("Imposible, puede haber 2 como mucho. Si hay mas algo está mal...")
            # Se han especificado o 1 o 2 p de tipo genload

            # Esto es lo que NO tiene que pasar: Que haya 2 pgen o 2 pload
            elif ("qgen_pu" in bus_dict and "qgen_mw" in bus_dict) or ("qload_pu" in bus_dict and "qload_mw" in bus_dict):
                raise ValueError("Esto mal")
            # Ahora sí, estamos seguros
            else:
                p_gen = bus_dict.get("qgen_pu", 0) + bus_dict.get("qgen_mw", 0)/self._s_base
                p_load = bus_dict.get("qload_pu", 0) + bus_dict.get("qload_mw", 0)/self._s_base
                return p_gen - p_load

        else:
            raise ValueError(f"No se han pasado versiones netas ni versiones genload")


        """
        NINGUNA DE LAS KEYS ES "CASE SENSITIVE" PUEDEN USARSE EN MINUSCULA O MAYUSCULA
        Keys especiales: que pueden van a usarse (como columnas en un dataframe, columnas sin "nombre" en un ndarray, etc) (Si se pasa un dataframe se usarán las columnas del propio dataframe en lugar del argumento columns)

        Para dar potencias: 
        "p_pu", "q_pu", "P_MW", "Q_MVA", "pgen_pu", "qgen_pu", "Pgen_MW", "Qgen_MVAr", "pload_pu", "qload_pu", "Pload_MW", "Qload_MVAr"
        
        Para dar tensiones: 
        "v_pu", "v_kV", "theta_rad", "theta_deg"
        
        Para dar admitancias: (No creo que nadie quiera meter esto en siemens pero bueno)
        "g_pu", "b_pu", "g_siemens", "b_siemens"

        Para tipos de nudo:
        "type" (los valores pueden ser objetos BusType o enteros (1,2,3) para (PQ, PV, Slack))
       
        Para proporcionar la base que usa este nudo:
        "base_kv" (o v_base? -> NO PUEDEN SER 2)

        Para ids:
        "id" (enteros positivos)

        Las tensiones dadas en fisico se traducirán usando base kV (obligatorio)
        Las potencias dadas en fisico se traducirán usando base MVA (que debe estar ya en el builder)
        Las admitancias (g y b) dadas en fisico se traducirán usando la impedancia base obtenida a partir de las anteriores (u_base^2 / s_base)
        
        RESTRICCIONES
        Si se da ALGUNA variable _pu NO PUEDE DARSE LA FISICA y si se da alguna fisica NO DEBE DARSE la _pu
        En las potencias: Si aparece alguna con el sufijo gen no puede parecer la simple (ya que la simple se calcula a partir de gen y load -> gen-load).
            Lo mismo a la inversa, si aparece la version sin sufijo, no pueden darse ni gen ni load. Lo que si se permita es que solo exista gen o solo exista load,
            en ese caso se interpreta que la otra es 0.
        
        DISTINTAS INTERPRETACIONES:
        - Slack: En este nudo las potencias NO se usan para nada. Solo se usan V y theta como "valor fijado" del nudo. Tambien la g y la b se usan. 
        - PQ: En este nudo la P y la Q son los "valores fijados del nudo". La theta y la V se usan como "initial guess". Tambien la g y la b se usan. 
        - PV: En este nudo la P y la V son los "valores fijados del nudo". La Q no se usa y la theta se toma como "initial guess". Tambien la g y la b se usan.
        """

        
    def add_branches_from_data(
        self, 
        data: pd.DataFrame | np.ndarray | list[list],
        columns: list[str] | None = None
    ):
        """
        Parses raw data into Branch objects (PiLine or SimpleTransformer).

        This method automatically determines the branch type based on 'tap' and 'shift' values.
        It handles standard alias keys for bus connections and ensures type-specific constraints.

        Args:
            data: Input data source. Can be a pandas DataFrame, a numpy ndarray, or a list of lists.
            columns: List of column names. Mandatory if `data` is not a DataFrame or a list of dicts.

        Supported Column Names (Case-Insensitive):
            * **Identification:** 'id' (int).
            * **Connectivity:** 
                * From: 'bus1' or 'from'.
                * To: 'bus2' or 'to'.
            * **Impedance (p.u.):** 'r', 'x'. (Defaults to 0.0).
            * **Shunt (p.u.):** 'b', 'g'. (Defaults to 0.0).
            * **Transformer Params:** 
                * 'tap': Tap ratio (Default 1.0).
                * 'shift': Phase shift in radians (Default 0.0).
            * **Limits:** 's_max' (Nominal Power). (Default infinity).

        Branch Type Logic:
            * **SimpleTransformer:** Created if `tap != 1.0` OR `shift != 0.0`.
                * *Constraint:* Transformers cannot have shunt parameters ('b' or 'g') in this model.
            * **PiLine:** Created otherwise (standard transmission line).

        Raises:
            ValueError: If mandatory fields are missing, IDs are duplicated, or Trafo constraints are violated.
            TypeError: If data types are inconsistent.
        """
        
        # 1. Normalización de entrada
        normalized_data = self._normalize_input(data, columns)

        for i, row in enumerate(normalized_data):
            
            # --- A. IDENTIFICACIÓN Y CONECTIVIDAD (Obligatorios) ---

            # ID del Branch
            if "id" not in row:
                raise ValueError(f"Row {i}: Missing mandatory field 'id'.")
            
            raw_id = row["id"]
            if isinstance(raw_id, float) and not raw_id.is_integer():
                raise TypeError(f"Row {i}: Branch ID must be an integer. Got {raw_id}.")
            branch_id = int(raw_id)

            # Check duplicados
            if branch_id in self._seen_branch_ids:
                raise ValueError(f"Builder Error: Branch ID {branch_id} is duplicated.")

            # Bus 1 (From) - Soporte de Alias
            bus1 = None
            if "bus1" in row: 
                bus1 = row["bus1"]
            if "from" in row: 
                if bus1: raise ValueError(f"Row {i} (Branch {branch_id}): Ambiguous connection. Cannot provide both 'bus1' and 'from'.")
                bus1 = row["from"]
            

            if bus1 is None:
                raise ValueError(f"Row {i} (Branch {branch_id}): Missing mandatory connection 'bus1' (or 'from').")

            # Bus 2 (To) - Soporte de Alias
            bus2 = None
            if "bus2" in row: 
                bus2 = row["bus2"]
            if "to" in row: 
                if bus2: raise ValueError(f"Row {i} (Branch {branch_id}): Ambiguous connection. Cannot provide both 'bus2' and 'to'.")
                bus2 = row["to"]
            
            if bus2 is None:
                raise ValueError(f"Row {i} (Branch {branch_id}): Missing mandatory connection 'bus2' (or 'to').")

            # Aseguramos que los IDs de buses sean enteros
            try:
                bus1 = int(bus1)
                bus2 = int(bus2)
            except ValueError:
                raise TypeError(f"Row {i} (Branch {branch_id}): Bus IDs must be integers.")

            # --- B. EXTRACCIÓN DE PARÁMETROS (Opcionales con Default) ---
            
            # Impedancia Serie (p.u.)
            r_val = float(row.get("r", None))
            x_val = float(row.get("x", None))

            # Admitancia Shunt (p.u.) - TOTAL de la línea
            g_val = float(row.get("g", 0.0))
            b_val = float(row.get("b", 0.0))

            # Parámetros de Transformador
            tap_val = float(row.get("tap", 1.0))
            shift_val = float(row.get("shift", 0.0))

            # Límite de Potencia (Default infinito)
            s_max_val = float(row.get("s_max", float("inf")))

            # --- C. LÓGICA DE DETERMINACIÓN DE TIPO ---
            
            # Tolerancia numérica pequeña para comparar floats
            epsilon = 0#1e-9
            is_tap_active = abs(tap_val - 1.0) > epsilon
            is_shift_active = abs(shift_val) > epsilon

            # Es un trafo si tiene tap distinto de 1 O shift distinto de 0
            is_transformer = is_tap_active or is_shift_active

            branch_obj = None

            if is_transformer:
                # --- VALIDACIÓN ESPECÍFICA DE TRAFO ---
                # Según tus requisitos: por nuestro modelo de trafo, b y g deben ser 0.
                if abs(g_val) > epsilon or abs(b_val) > epsilon:
                    warnings.warn(
                        f"Branch {branch_id}: Identified as Transformer (tap={tap_val}, shift={shift_val}) "
                        f"but has non-zero shunt parameters (g={g_val}, b={b_val}). "
                        "Using experimental: PiTransformer"
                    )
                    branch_obj = PiTransformer(
                        id=branch_id,
                        bus1=bus1,
                        bus2=bus2,
                        R=r_val,
                        X=x_val,
                        G=g_val,
                        B=b_val,
                        tap_ratio=tap_val,
                        shift=shift_val,
                        S_max=s_max_val
                    )
                    
                else:
                # Mapeo de r/x a Rcc/Xcc
                    branch_obj = SimpleTransformer(
                        id=branch_id,
                        bus1=bus1,
                        bus2=bus2,
                        Rcc=r_val,
                        Xcc=x_val,
                        tap_ratio=tap_val,
                        shift=shift_val,
                        S_max=s_max_val
                    )

            else:
                # --- ES UNA LÍNEA PI ---
                branch_obj = PiLine(
                    id=branch_id,
                    bus1=bus1,
                    bus2=bus2,
                    R=r_val,
                    X=x_val,
                    G=g_val,
                    B=b_val,
                    S_max=s_max_val
                )

            # --- D. ALMACENAMIENTO ---
            
            self._seen_branch_ids.add(branch_id)
            self._branches.append(branch_obj)

        return self


# ... (Dentro de class PFNetworkBuilder) ...

    def load_matpower(self, filepath: str):
        """
        Loads a Matpower (.m) file from disk into this Builder instance.

        It uses the external reader `read_matpower_file` to extract raw data
        and then populates the builder using its own public API methods.

        .. note::
            **Information Loss Warning:** Some Matpower-specific data is currently 
            ignored during import:
            *   **Limits:** Reactive power (Qmin/Qmax) and Voltage (Vmin/Vmax) limits.
            *   **Ratings:** Secondary thermal ratings (Rate B, Rate C).
            *   **Status:** Elements (buses/branches) with status <= 0 are skipped.

        Args:
            filepath: Absolute or relative path to the .m file.

        Returns:
            self: Fluent interface.
        """

        # 1. Obtener datos crudos estructurados (listas de dicts)
        buses_data, branches_data, base_mva = read_matpower_file(filepath)
        
        # 2. Configurar la base del sistema
        self.set_base_mva(base_mva)
        
        # 3. Inyectar buses
        self.add_buses_from_data(buses_data)
        
        # 4. Inyectar ramas
        self.add_branches_from_data(branches_data)
        
        return self
    # --- BUILD METHOD ---

    def load_json(self, filepath: str):
        """
        Loads network data from a JSON file directly into the Builder.

        This method uses the `json_io` module to deserialize the file directly into
        PywerFlow objects (InputBus and PFSolvableBranch subclasses), bypassing
        intermediate data transformations.

        Args:
            filepath (str): Path to the source .json file.

        Returns:
            PFNetworkBuilder: The builder instance itself (Fluent Interface).
        
        Raises:
            ValueError: If `s_base` in the file conflicts with an already set `s_base` in the builder.
        """
        import pywerflow.io.json_io as json_io
        
        # 1. Load native objects directly
        buses, branches, s_base = json_io.load_network_from_json(filepath)

        # 2. Configure S_base
        if self._s_base is None:
            self.set_base_mva(s_base)
        elif abs(self._s_base - s_base) > 1e-6:
            warnings.warn(
                f"JSON Load Warning: The file specifies s_base={s_base} MVA, "
                f"but the builder is already set to {self._s_base} MVA. "
                "The loaded components will be added assuming their per-unit values are valid for the CURRENT base."
            )

        # 3. Add Objects Directly
        self.add_buses(buses)
        self.add_branches(branches)

        return self


    def build(self) -> PowerFlowNetwork:
        """
        Constructs the Power Network.

        Returns:
            PUNetwork: A power flow network object.
        """        
        # 1. Chequeo básico de existencia
        if not self._buses:
            raise ValueError("Builder Error: Cannot build a network without buses.")

        if not self._branches:
            raise ValueError("Builder Error: Cannot build a network without branches.")

        # 3. Instanciación
        net = PowerFlowNetwork(
            buses=self._buses,
            branches=self._branches,
            S_base=self._s_base 
        )
        
        return net