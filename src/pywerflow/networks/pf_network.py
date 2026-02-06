import warnings
from math import degrees
from dataclasses import replace  
from typing import Literal, Any
from math import degrees

from scipy.sparse import coo_matrix, csr_matrix
import numpy as np
import pandas as pd



from pywerflow.networks.base_network import BaseNetwork
from pywerflow.validation_utils import auto_validate, validator, validate_ranges, validate_types
from pywerflow.branches.base_branches import SolvedBranch
from pywerflow.branches.pfsolvable_branches import PFSolvableBranch
from pywerflow.buses.bus_types import BusTypes
from pywerflow.buses.solved_buses import SolvedBus
from pywerflow.buses.input_buses import InputBus, PQBus, PVBus, SlackBus
from pywerflow.solvers.gauss_seidel.gauss_seidel import gauss_seidel
from pywerflow.solvers.newton_rapshon.newton_raphson import newton_raphson

from pywerflow.solvers.results import SolverMetaResult
from pywerflow.networks.pfresults import PowerFlowResults


# NOTA: Solo los metodos publicos deberían revisar si el estado interno está actualizado. 
# Los metodos privados pueden confiar en que han sido llamados por un metodo publico, con lo cual, se fían de que 
# han sido llamados en las circunstancias correctas

class PowerFlowNetwork(BaseNetwork):

    # BUSES Y RAMAS (DATOS DE ALTO NIVEL)  ---------------------------------------------------
    _branches: dict[int, PFSolvableBranch]  # Fuente unica de verdad
    _buses: dict[int, InputBus]             # Fuente unica de verdad
    _s_base: float | None                    # En MVA

    # ESTRUCTURA INTERNA DE DATOS  ---------------------------------------------------
    # IDs de los distintos tipos de buses
    _pq_idxs: np.ndarray | None
    _pv_idxs: np.ndarray | None
    _slack_idx: int | None

    # Mapping ID->IDX e IDX->ID
    _id_to_idx: dict[int, int] | None
    _idx_to_id: list[int]  | None
    
    # Parámetros shunt de los buses
    _G_shunts: np.ndarray | None
    _B_shunts: np.ndarray | None
    
    # Estado de la red conocido (mezcla de valores "initial guess" y "parametros conocidos")
    _v_arr: np.ndarray | None     # Magnitud V
    _theta_arr: np.ndarray | None # Ángulo theta (radianes)
    _p_arr: np.ndarray | None     # P inyectada neta (Generación - Carga)
    _q_arr: np.ndarray | None     # Q inyectada neta (Generación - Carga)

    # MATRIZ DE ADMITANCIAS ---------------------------------------------------
    _y_matrix: csr_matrix | np.ndarray | None
    
    # ULTIMA SOLUCION -> ESTADO DE LA RED DE LA ULTIMA SOLUCION ---------------------------------------------------
    _last_v_sol_arr: np.ndarray | None
    _last_theta_sol_arr: np.ndarray | None

    # Diccionario de buses deshabilitados
    _disabled_buses_memory: dict[int, InputBus]

    # BOOLEANOS PARA CONTROLAR GENERACIÓN DE DATOS ---------------------------------------------------
    # Estos booleanos son False si cada variable del grupo de variables que protegen están actualizadas
    # con respecto a los "datos de alto nivel".
    # esto significa que si un método altera CUALQUIER atributo de la funcion, debe marcarlo
    _internal_data_outdated: bool  # False si todo el conjunto de "internal data" refleja los buses y branches actuales
    _y_matrix_outdated: bool       # False si _y_matrix refleja los buses y branches actuales
    _last_sol_outdated: bool       # False si _last_v_sol_arr y _last_theta_sol_arr representa una solución válida a partir de los buses y branches actuales


    def __init__(self, buses: list[InputBus], branches: list[PFSolvableBranch], S_base: float|None = None):
        """
        Initializes the Per-Unit Network.

        Args:
            buses: List of input buses (nodes).
            branches: List of solvable branches.
        """
        super().__init__(buses, branches)
        self._s_base = S_base

        self._pq_idxs = None
        self._pv_idxs = None
        self._slack_idx = None
        self._id_to_idx = None
        self._idx_to_id = None 
        self._G_shunts = None
        self._B_shunts = None
        self._v_arr = None 
        self._p_arr = None 
        self._q_arr = None
        self._theta_arr = None

        self._y_matrix = None       

        self._last_v_sol_arr = None
        self._last_theta_sol_arr = None

        self._internal_data_outdated = True   
        self._y_matrix_outdated = True  
        self._last_sol_outdated = True

        self._disabled_buses_memory: dict[int, InputBus] = {}


    @validator
    def _validate_solvable_branches(self):
        """
        Validates that all branches in the network are mathematically solvable.
        
        Raises:
            TypeError: If a branch is not a subclass of PFSolvableBranch.
        """
        for id, branch in self._branches.items():
            if not isinstance(branch, PFSolvableBranch):
                raise TypeError(
                    f"Consistency Error: PUNetwork requires solvable branches (subclasses of PFSolvableBranch). "
                    f"Branch ID '{id}' is of type '{type(branch).__name__}'. "
                )


    def _invalidate_cache(self):
        """
        Marks all internal data structures as outdated.
        Should be called whenever the network topology or parameters are modified.
        """
        self._internal_data_outdated = True
        self._y_matrix_outdated = True
        self._last_sol_outdated = True


    def _ensure_internal_data(self):
        """
        Ensures that internal Numpy arrays (indices, P, Q, V, Theta) are consistent 
        with the high-level bus data. Regenerates them if marked as outdated.
        """
        if self._internal_data_outdated:
            self._generate_internal_bus_data()
            self._generate_internal_branch_data()
            self._internal_data_outdated = False # Marco los datos como actualizados


    def _ensure_y_matrix(self):
        """
        Ensures that the Y-Bus matrix is consistent with the current network topology.
        Automatically triggers internal data generation if needed.
        """
        if self._y_matrix_outdated:  
            self._ensure_internal_data() # Me aseguro de que los datos internos están bien
            self._build_y_matrix()  # Luego ya construyo la matriz
            self._y_matrix_outdated = False # Marco la matriz como válida


    def _generate_internal_bus_data(self):
        """
        Generates flattened Numpy arrays and index mappings from the high-level bus objects.
        """
        pq_idxs = []
        pv_idxs = []
        slack_idx = None

        id_to_idx = {}
        idx_to_id = []

        N = len(self._buses)

        G_shunts = np.zeros(N, dtype=float)
        B_shunts = np.zeros(N, dtype=float) 

        v_arr = np.zeros(N, dtype=float) 
        p_arr = np.zeros(N, dtype=float)  
        q_arr = np.zeros(N, dtype=float)  
        theta_arr = np.zeros(N, dtype=float)  

        # Recorremos por ids (primero las pequeñas y luego las grandes)
        for idx, bus in enumerate(sorted(self._buses.values(), key=lambda b: b.id)):
            
            id_to_idx[bus.id] = idx
            idx_to_id.append(bus.id)

            G_shunts[idx] = bus.G_shunt
            B_shunts[idx] = bus.B_shunt

            if bus.type is BusTypes.PQ:
                bus: PQBus # Nota para el IDE
                pq_idxs.append(idx)
                p_arr[idx] = bus.P
                q_arr[idx] = bus.Q
                # Esto es V_guess
                v_arr[idx] = bus.V_guess
                # Esto es theta_guess
                theta_arr[idx] = bus.theta_guess

            elif bus.type is BusTypes.PV:
                bus: PVBus # Nota para el IDE
                pv_idxs.append(idx)
                p_arr[idx] = bus.P
                v_arr[idx] = bus.V
                # Esto es theta_guess
                theta_arr[idx] = bus.theta_guess

            elif bus.type is BusTypes.SLACK:
                bus: SlackBus # Nota para el IDE
                if slack_idx is None:
                    slack_idx = idx
                    v_arr[idx] = bus.V
                    theta_arr[idx] = bus.theta
                     
                else:
                    raise RuntimeError(
                        f"INTERNAL ERROR: Data corruption detected in PuNetwork generation. "
                        f"Expected 1 Slack bus. Detected at least 2 with ids {idx_to_id[slack_idx]} and {bus.id}"
                        f"Please report this bug to the developer."
                    )
                
            else:
                raise RuntimeError(
                    f"CRITICAL IMPLEMENTATION ERROR: Bus ID {bus.id} has type '{bus.type}', "
                    f"but logic for this BusType is missing in '_generate_internal_data'. "
                )

        self._pq_idxs = np.array(pq_idxs, dtype=int)
        self._pv_idxs = np.array(pv_idxs, dtype=int)
        self._slack_idx = slack_idx
        self._id_to_idx = id_to_idx
        self._idx_to_id = idx_to_id 
        self._G_shunts = G_shunts
        self._B_shunts = B_shunts
        self._v_arr = v_arr 
        self._p_arr = p_arr 
        self._q_arr = q_arr
        self._theta_arr = theta_arr


    def _generate_internal_branch_data(self):
        """
        Placeholder for generating flattened branch arrays if needed for 
        vectorized post-processing in the future.
        """
        pass


    def _build_y_matrix(self):
        """
        Constructs the nodal admittance matrix (Y-Bus).
        This matrix includes branch admittances and bus shunt admittances.
        """
        # Listas para acumular los tripletes (fila, columna, valor)
        # Pre-allocating es difícil con listas, pero el append de Python es bastante rápido.
        
        # Inicializamos matriz de NxN, donde N es el numero de buses
        N = len(self._buses)    
        y_matrix = np.zeros(shape=(N,N), dtype=complex)
            
        id_to_idx = self._id_to_idx
        
        # Recorremos las branches. El orden en el que se recorra da igual
        # Para cada Branch, "sumamos" su matriz de admitancias, en la "sub-matriz"
        # correspondiente de Y matrix
        for branch in self._branches.values():
            b1_idx = id_to_idx[branch.bus1]
            b2_idx = id_to_idx[branch.bus2]
            
            y_matrix[np.ix_(
                [b1_idx, b2_idx], 
                [b1_idx, b2_idx])
                ] +=  branch.get_admittance_matrix()

        # Ahora aplicamos las admitancias "shunt" de cada nudo
        for id, bus in self._buses.items():
            bus_idx = id_to_idx[id] 
            y_matrix[bus_idx, bus_idx] += bus.get_shunt_admittance()


        self._y_matrix = y_matrix
            

    def _updates_last_sol(self, v_arr: np.ndarray, theta_arr: np.ndarray):
        """
        Updates the solution cache with the latest results from the solver.
        
        Args:
            v_arr: Array of voltage magnitudes (p.u.) sorted by internal index.
            theta_arr: Array of voltage angles (radians) sorted by internal index.
        """
        
        self._last_v_sol_arr = v_arr
        self._last_theta_sol_arr = theta_arr

        self._last_sol_outdated = False


    def _apply_initial_guess(
        self, 
        current_v: np.ndarray, 
        current_theta: np.ndarray, 
        guess_dict: dict[int, dict[str, float]]
    ):
        """
        Applies customized initial guesses to the working arrays.
        Safely handles physical constraints (Slack/PV limits override guesses).

        Args:
            current_v: Working array for Voltage Magnitude (modified in-place).
            current_theta: Working array for Voltage Angle (modified in-place).
            guess_dict: Dictionary mapping Bus ID to {'V': ..., 'theta': ...}.
        """
        for bus_id, values in guess_dict.items():
            # 1. Validación de existencia
            if bus_id not in self._id_to_idx:
                warnings.warn(
                    f"Initial Guess ignored: Bus ID '{bus_id}' does not exist on the network.", 
                    UserWarning
                )
                continue

            idx = self._id_to_idx[bus_id]
            bus_type = self._buses[bus_id].type
            
            # 2. Aplicar Voltaje (V)
            # Regla: Solo los PQ aceptan sugerencias de V. 
            # PV y Slack tienen V impuesta por su setpoint físico.
            if 'V' in values:
                if bus_type is BusTypes.PQ:
                    current_v[idx] = values['V']
                else:
                    # Warning para PV o Slack
                    warnings.warn(
                        f"Initial Guess Warning (Bus {bus_id}): Voltage guess ignored. "
                        f"Bus type is '{bus_type.name}', so Voltage is fixed by the component/reference.",
                        UserWarning
                    )

            # 3. Aplicar Ángulo (Theta)
            # Regla: PQ y PV aceptan sugerencias de Theta.
            # Slack tiene Theta impuesto (referencia 0º usualmente).
            if 'theta' in values:
                if bus_type is BusTypes.PQ or bus_type is BusTypes.PV:
                    current_theta[idx] = values['theta']
                else:
                    # Warning para Slack
                    warnings.warn(
                        f"Initial Guess Warning (Bus {bus_id}): Angle guess ignored. "
                        f"Bus type is '{bus_type.name}' (Reference), so Angle is fixed.",
                        UserWarning
                    )

        return current_v, current_theta


    def _build_solved_buses(self, v_complex: np.ndarray) -> list[SolvedBus]:
        """
        Calculates nodal quantities (Injections, Shunts, Mismatches) using vectorized operations.

        Args:
            v_complex: Complex voltage array sorted by internal index.

        Returns:
            List of SolvedBus objects.
        """
        N = len(self._buses)
        
        # --- A) VECTORIZED MATH (C-Speed) ---
        
        # 1. Nodal Injections (I = Y * V) and Power (S = V * I*)
        current_injections = self._y_matrix @ v_complex
        s_injections = v_complex * np.conj(current_injections)
        
        p_calc = s_injections.real
        q_calc = s_injections.imag
        
        # 2. Shunt Powers (V^2 * Y_shunt)
        # We use the magnitudes directly from cache to avoid complex abs() overhead
        v_mag_sq = self._last_v_sol_arr ** 2
        p_shunts = v_mag_sq * self._G_shunts
        q_shunts = -v_mag_sq * self._B_shunts # Negative for B convention
        
        # 3. Mismatches (Calculate ALL differences first)
        # It's faster to subtract arrays of size 10,000 once than to do 10,000 subtractions in a loop
        p_diffs = p_calc - self._p_arr
        q_diffs = q_calc - self._q_arr
        v_diffs = self._last_v_sol_arr - self._v_arr

        # --- B) OBJECT CREATION (Python Loop) ---
        solved_buses = []
        
        # Pre-fetch arrays to avoid self lookup inside loop
        last_theta = self._last_theta_sol_arr
        last_v = self._last_v_sol_arr
        
        for idx in range(N):
            bus_id = self._idx_to_id[idx]
            input_bus = self._buses[bus_id]
            b_type = input_bus.type
            
            # Select relevant mismatch based on type
            p_mis = None
            q_mis = None
            v_mis = None

            if b_type is BusTypes.PQ:
                p_mis = p_diffs[idx]
                q_mis = q_diffs[idx]
            elif b_type is BusTypes.PV:
                p_mis = p_diffs[idx]
                v_mis = v_diffs[idx]
            elif b_type is BusTypes.SLACK:
                v_mis = v_diffs[idx]

            # Create Object
            solved_buses.append(SolvedBus(
                id=bus_id,
                V=last_v[idx],
                theta=last_theta[idx],
                P_net=p_calc[idx],
                Q_net=q_calc[idx],
                I=abs(current_injections[idx]),
                phi=np.angle(current_injections[idx]),
                P_shunt=p_shunts[idx],
                Q_shunt=q_shunts[idx],
                original_type=b_type,
                final_type=b_type, 
                is_v_limited=False,
                is_q_limited=False,
                P_mismatch=p_mis if p_mis is not None else 0.0,
                Q_mismatch=q_mis if q_mis is not None else 0.0,
                V_mismatch=v_mis if v_mis is not None else 0.0,
                V_base=input_bus.V_base,
            ))
            
        return solved_buses


    def _build_solved_branches(self, v_complex: np.ndarray) -> list[SolvedBranch]:
        """
        Calculates branch flows and losses using vectorized operations.

        Args:
            v_complex: Complex voltage array sorted by internal index.

        Returns:
            List of SolvedBranch objects.
        """
        branches = list(self._branches.values())
        M = len(branches)
        
        if M == 0:
            return []

        # --- A) DATA EXTRACTION (Prepare for Vectorization) ---
        # We need to extract indices and primitive admittances to perform matrix ops
        
        # Arrays to hold indices
        idx1_arr = np.zeros(M, dtype=int)
        idx2_arr = np.zeros(M, dtype=int)
        
        # Arrays to hold Y-Primitive components (y11, y12, y21, y22)
        y11_arr = np.zeros(M, dtype=complex)
        y12_arr = np.zeros(M, dtype=complex)
        y21_arr = np.zeros(M, dtype=complex)
        y22_arr = np.zeros(M, dtype=complex)
        
        # Array for limits
        s_max_arr = np.zeros(M, dtype=float)

        # Loop to populate arrays (One pass)
        for i, branch in enumerate(branches):
            idx1_arr[i] = self._id_to_idx[branch.bus1]
            idx2_arr[i] = self._id_to_idx[branch.bus2]
            
            # Get primitive (2x2)
            y_prim = branch.get_admittance_matrix()
            y11_arr[i] = y_prim[0, 0]
            y12_arr[i] = y_prim[0, 1]
            y21_arr[i] = y_prim[1, 0]
            y22_arr[i] = y_prim[1, 1]
            
            if branch.S_max and branch.S_max > 0:
                s_max_arr[i] = branch.S_max
            else:
                s_max_arr[i] = np.inf

        # --- B) VECTORIZED MATH (C-Speed) ---
        
        # Get Voltages at branch ends (Advanced Indexing)
        v1 = v_complex[idx1_arr]
        v2 = v_complex[idx2_arr]
        
        # Calculate Currents (Vectorized)
        # I1 = Y11*V1 + Y12*V2
        i1 = y11_arr * v1 + y12_arr * v2
        i2 = y21_arr * v1 + y22_arr * v2
        
        # Calculate Powers (S = V * I*)
        s1 = v1 * np.conj(i1)
        s2 = v2 * np.conj(i2)
        
        # Calculate Losses
        s_loss = s1 + s2
        
        # Calculate Loading %
        # max(abs(s1), abs(s2)) element-wise
        s_flow_max = np.maximum(np.abs(s1), np.abs(s2))
        loading_arr = (s_flow_max / s_max_arr) * 100.0
        
        # Handle infinite limits (NaN results)
        loading_arr[s_max_arr == np.inf] = 0.0

        # --- C) OBJECT CREATION (Python Loop) ---
        solved_branches = []
        
        for k in range(M):
            branch = branches[k]
            
            solved_branches.append(SolvedBranch(
                id=branch.id,
                bus1=branch.bus1,
                bus2=branch.bus2,
                P1=s1[k].real, Q1=s1[k].imag, S1=abs(s1[k]),
                P2=s2[k].real, Q2=s2[k].imag, S2=abs(s2[k]),
                I1=abs(i1[k]), phi1=np.angle(i1[k]),
                I2=abs(i2[k]), phi2=np.angle(i2[k]),
                P_loss=s_loss[k].real, Q_loss=s_loss[k].imag,
                loading_percent=loading_arr[k]
            ))
            
        return solved_branches


    def _build_solution_results(self, v_complex: np.ndarray | None) -> tuple[list[SolvedBus], list[SolvedBranch]]:
        """
        Orchestrates the calculation of physical results (Buses and Branches).
        Uses the latest cached solution.

        Args:
            v_complex (np.ndarray | None): Optional pre-calculated complex voltage array 
                sorted by internal index. 

                .. **CRITICAL CONSISTENCY CHECK**
                    
                    If provided, this vector **MUST** correspond exactly to the solution currently 
                    cached in ``self._last_v_sol_arr`` and ``self._last_theta_sol_arr``.
                    
                    This method mixes data from the cache (for magnitudes/angles) and this vector 
                    (for injections/flows). If they diverge, the resulting physical objects 
                    will be mathematically inconsistent (e.g., Power != V * I). 
                    
                    Defaults to None (recalculates from cache).

        Returns:
            Tuple containing list of SolvedBus and list of SolvedBranch.
        """
        # 1. Reconstruir Vector de Voltaje Complejo (Solo si no se proporciona)
        if v_complex is None:
            v_complex = self._last_v_sol_arr * (np.cos(self._last_theta_sol_arr) + 1j * np.sin(self._last_theta_sol_arr))

        # 2. Construir Buses 
        solved_buses = self._build_solved_buses(v_complex)

        # 3. Construir Ramas 
        solved_branches = self._build_solved_branches(v_complex)

        return solved_buses, solved_branches
    

    def gauss_seidel_solve(
            self, 
            tol: float = 1e-9, 
            max_it: int = 1000, 
            fix_step: int = 4,
            alpha: float = 1.0,
            err_history_limit: int = 10000,
            initial_guess: dict[int, dict[str, float]] | None = None,

            # pq_switching: bool = False,
            # pv_switching: bool = False,
        ) -> PowerFlowResults:
            """
            Executes the Gauss-Seidel Power Flow algorithm on the network.

            This method orchestrates the data preparation, calls the optimized C-backend solver,
            updates the internal network state, and calculates all physical quantities 
            (branch flows, losses, mismatches) to return a fully solved system state.

            Args:
                tol (float): Convergence tolerance (max voltage mismatch in p.u.).
                    Defaults to 1e-9 if None.
                max_it (int): Maximum number of iterations. 
                    Defaults to 1000 if None.
                fix_step (int): Iteration step to start applying the correction to the V module at the PV nodes.
                    Defaults to 4 if None.
                alpha (float): Acceleration factor for voltage updates.
                    Defaults to 1.0 (no acceleration) if None.
                err_history_limit (int): Maximum number of iterations to record in the error history.
                    If the method iterates more than this limit, the history will be truncated 
                    to save memory, but the calculation will continue until convergence or max_iterations.
                    Defaults to 10000.
                initial_guess (dict[int, dict[str, float]] | None): Optional manual start values.
                    Format: { bus_id: {'v': 1.0, 'theta': 0.0 }, ... }. 
                    Theta values must be in radians.     
                    This is a **sparse dictionary**: it is not necessary to specify all buses. 
                    Only the specific buses and values provided here will temporarily 
                    override the internal configuration for this execution. 
                    Any bus (or field) not present in this dictionary will retain its 
                    current internal "initial guess" state.
            Returns:
                PowerFlowResults: Object containing metadata, buses, branches and base power.

            Raises:
                RuntimeError: If the internal data cannot be generated or the C solver fails explicitly.
            """
            
            self._ensure_internal_data()
            self._ensure_y_matrix()

            # Aplicar los nuevos initial guess
            if initial_guess is not None:
                v_arr = self._v_arr.copy()
                theta_arr = self._theta_arr.copy()
                self._apply_initial_guess(v_arr, theta_arr, initial_guess)
            else:
                # Si no hay que modificar los arrays me ahorro el trabajo de copiarlos
                v_arr = self._v_arr
                theta_arr =  self._theta_arr

            # --- 3. Data Construction for C Engine ---
            # (Lógica para aplanar matrices y ordenar índices)
            
            N = len(self._buses)
            
            # A) Construcción de PQV (Interleaved)
            pqv_col_2 = self._q_arr.copy() # Copia base Q (para buses PQ)
            pqv_col_2[self._pv_idxs] = self._v_arr[self._pv_idxs] # Sobrescribir PVs con V
            
            pqv_matrix = np.column_stack((self._p_arr, pqv_col_2))
            
            # Máscara para excluir el Slack (Gauss-Seidel no itera sobre el Slack)
            mask = np.ones(N, dtype=bool)
            mask[self._slack_idx] = False
            
            pqv_1darr = pqv_matrix[mask].ravel() # Filtrar y aplanar

            # B) Construcción de Bus Types (Bool Mask)
            pqpv_bus_types = np.zeros(N, dtype=bool)
            pqpv_bus_types[self._pq_idxs] = True # PQ = True, PV = False
            pqpv_bus_types = pqpv_bus_types[mask] # Quitar slack

            # C) Permutación de Y-Matrix (Slack al final)
            # Vector de índices: [Resto..., Slack]
            perm_indices = np.concatenate((np.arange(N)[mask], [self._slack_idx]))
            
            # Reordenamos la Y-matrix para enviarla al solver
            # Nota: self._y_matrix no se modifica, creamos una vista/copia para el solver
            y_matrix_solver = self._y_matrix[np.ix_(perm_indices, perm_indices)]

            # D) Vector de Voltaje Inicial (Complex)
            v0_complex = v_arr * (np.cos(theta_arr) + 1j * np.sin(theta_arr))
            v0_permuted = v0_complex[perm_indices]

            # --- 4. Call C Solver ---
            v_final_permuted, meta_result = gauss_seidel(
                pqv_arr=pqv_1darr,
                bus_types=pqpv_bus_types,
                Ymatrix=y_matrix_solver.ravel(),
                v0=v0_permuted,
                tolerance= float(tol),
                max_iterations= int(max_it),
                fix_step= int(fix_step),
                accel_factor= float(alpha),
                err_history_limit= int(err_history_limit),
            )


            # --- 5. Post-Processing & State Update ---
            
            # Reconstruimos el vector de tensiones en el orden original interno (0..N)
            # v_final_permuted está ordenado según perm_indices.
            # Asignamos inversamente: full_v[idx_original] = v_final[posicion_permutada]
            v_complex_solution = np.zeros(N, dtype=complex)
            v_complex_solution[perm_indices] = v_final_permuted
            
            # Actualizo el ultimo "estado actual" resuelto de la red
            self._updates_last_sol(
                v_arr = np.abs(v_complex_solution),
                theta_arr = np.angle(v_complex_solution)
            )

            # Delego el cálculo físico al método común
            solved_buses, solved_branches = self._build_solution_results(v_complex_solution)

            return PowerFlowResults(
                meta=meta_result,
                buses=solved_buses,
                branches=solved_branches,
                s_base=self._s_base 
            )


    def newton_raphson_solve(
            self,
            tol: float = 1e-9,
            max_it: int = 20,
            initial_guess: dict[int, dict[str, float]] | None = None,
        ) -> PowerFlowResults:
        """
        Executes the Newton-Raphson Power Flow algorithm on the network.

        This method prepares the internal data structures, handles initial guesses,
        and invokes the numerical solver. Finally, it constructs the physical 
        results (flows, losses) based on the converged state.

        Args:
            tol (float): Convergence tolerance (max power mismatch in p.u.).
                Defaults to 1e-9.
            max_it (int): Maximum number of iterations.
                Defaults to 20.
            initial_guess (dict[int, dict[str, float]] | None): Optional manual start values.
                Format: { bus_id: {'V': 1.0, 'theta': 0.0 }, ... }. 
                Theta values must be in radians.
                Only the specific buses provided here will temporarily override 
                the internal configuration for this execution.

        Returns:
            PowerFlowResults: Object containing metadata, solved buses, and branches.

        Raises:
            RuntimeError: If the internal data cannot be generated.
        """
        # Importación local para evitar dependencias circulares a nivel de módulo

        # 1. Asegurar consistencia de datos internos
        # Si la red ha cambiado (se han añadido buses/ramas), regeneramos los arrays
        self._ensure_internal_data()
        self._ensure_y_matrix()

        # 2. Gestión de Initial Guess (Manual override)
        # Trabajamos sobre copias para no modificar el estado "por defecto" de la red
        # si el solver falla o diverge.
        v_start = self._v_arr.copy()
        theta_start = self._theta_arr.copy()

        # Aplicar los overrides del usuario si existen
        if initial_guess is not None:
            self._apply_initial_guess(v_start, theta_start, initial_guess)

        # 3. Llamada al Solver Numérico
        # Pasamos los arrays y la matriz Y. 
        # Nota: newton_raphson_solver modifica v_start y theta_start in-place.
        v_final_complex, meta_result = newton_raphson(
            Ymatrix=self._y_matrix,
            p_arr=self._p_arr,
            q_arr=self._q_arr,
            v0_arr=v_start,
            theta0_arr=theta_start,
            pq_idxs=self._pq_idxs,
            pv_idxs=self._pv_idxs,
            tol=tol,
            max_it=max_it,
        )

        # 4. Post-Procesado y Actualización de Estado
        
        # Actualizamos la caché interna de "última solución" con los resultados finales
        # Esto permite que otros métodos usen estos resultados sin re-calcular
        self._updates_last_sol(
            v_arr=np.abs(v_final_complex),
            theta_arr=np.angle(v_final_complex)
        )

        # Construimos los objetos físicos de alto nivel (SolvedBus y SolvedBranch)
        # Calculando flujos, pérdidas y desajustes finales
        solved_buses, solved_branches = self._build_solution_results(v_final_complex)

        return PowerFlowResults(
            meta=meta_result,
            buses=solved_buses,
            branches=solved_branches,
            s_base=self._s_base
        )


    # --- MÉTODOS DE ACCESO (GETTERS) --------------------------------------------

    def get_bus(self, bus_id: int) -> InputBus:
        """
        Retrieves a specific bus object from the network by its ID.

        Args:
            bus_id (int): The unique identifier of the bus to retrieve.

        Returns:
            InputBus: The bus object corresponding to the provided ID.

        Raises:
            KeyError: If the specified 'bus_id' does not exist in the network topology.
        """
        if bus_id not in self._buses:
            raise KeyError(f"Bus ID {bus_id} not found in the network.")
        return self._buses[bus_id]

    def get_all_buses(self) -> list[InputBus]:
        """
        Retrieves a list containing all the bus objects defined in the network.

        Returns:
            list[InputBus]: A list of all InputBus instances currently in the network.
        """
        return list(self._buses.values())

    def get_branch(self, branch_id: int) -> PFSolvableBranch:
        """
        Retrieves a specific branch object from the network by its ID.

        Args:
            branch_id (int): The unique identifier of the branch to retrieve.

        Returns:
            PFSolvableBranch: The branch object corresponding to the provided ID.

        Raises:
            KeyError: If the specified 'branch_id' does not exist in the network topology.
        """
        if branch_id not in self._branches:
            raise KeyError(f"Branch ID {branch_id} not found in the network.")
        return self._branches[branch_id]

    def get_all_branches(self) -> list[PFSolvableBranch]:
        """
        Retrieves a list containing all the branch objects defined in the network.

        Returns:
            list[PFSolvableBranch]: A list of all PFSolvableBranch instances currently in the network.
        """
        return list(self._branches.values())

    @property
    def s_base(self):
        return self._s_base

    # --- MÉTODOS DE MODIFICACIÓN ESTRUCTURAL ------------------------------------

    def update_bus(self, new_bus: InputBus):
        """
        Replaces an existing bus in the network with a new definition instance.

        This method allows dynamic modification of bus parameters (e.g., changing a 
        PQ bus to a PV bus, modifying setpoints, limits, or initial guesses) while 
        preserving the network structure. Since 'InputBus' objects are immutable 
        dataclasses, modification is achieved by full object replacement.

        **Side Effects:**
            - Triggers a global cache invalidation (`_invalidate_cache()`).
            - The internal Y-Bus matrix and NumPy arrays will be regenerated 
              during the next solver call.

        **Constraints:**
            - The Slack/Reference bus cannot be modified at runtime to ensure 
              topological stability.
            - The ID of 'new_bus' must match the ID of an existing bus in the network 
              (creating new buses is not supported by this method).
            - **Disabled buses cannot be modified.** You must reactivate the bus 
              using `set_bus_status(id, active=True)` before applying changes.

        Args:
            new_bus (InputBus): The new bus instance that will overwrite the 
                                existing one with the same ID.

        Raises:
            KeyError: If the bus ID does not exist in the network.
            ValueError: If attempting to replace the SLACK bus.
            ValueError: If attempting to update a disabled bus.
        """
        # 1. Validaciones básicas
        if new_bus.id not in self._buses:
            raise KeyError(f"Cannot update: Bus ID {new_bus.id} does not exist in the network.")
        
        current_bus = self._buses[new_bus.id]

        # 1.1 --- PROTECCIÓN PARA BUSES DESACTIVADOS ---
        if new_bus.id in self._disabled_buses_memory:
            raise ValueError(
                f"Operation denied: Bus {new_bus.id} is currently deactivated. "
                "You must reactivate it using 'set_bus_status(id, active=True)' before modifying its parameters."
            )

        # 2. Protección del Slack
        if current_bus.type == BusTypes.SLACK:
            raise ValueError(
                f"Forbidden operation: Cannot replace or modify the Slack bus (ID {new_bus.id}) "
                "at runtime to prevent topological inconsistencies."
            )

        # 3. Sustitución
        self._buses[new_bus.id] = new_bus
        
        # 4. Invalidar caché (Obligatorio para que se recalculen las matrices)
        self._invalidate_cache()


    def modify_bus(self, bus_id: int, **changes):
        """
        Replaces an existing bus in the network with a new definition instance.

        This method facilitates the dynamic modification of bus parameters (e.g., 
        changing a PQ bus to a PV bus, updating voltage setpoints, limits, or 
        initial guesses) while maintaining the network's integrity. Since 
        'InputBus' objects are immutable dataclasses, updates are achieved by 
        replacing the entire object instance.

        **Side Effects:**
            - Triggers a global cache invalidation via ``_invalidate_cache()``.
            - Forces the regeneration of the internal Y-Bus matrix and NumPy 
              arrays during the next solver execution.

        **Constraints:**
            - The Slack/Reference bus cannot be modified at runtime to ensure 
              topological stability and reference consistency.
            - The ID of ``new_bus`` must correspond to an existing bus in the 
              network (this method does not support creating new nodes, only 
              updating existing ones).

        Args:
            new_bus (InputBus): The new bus instance that will overwrite the 
                existing bus associated with the same ID.

        Raises:
            KeyError: If the bus ID contained in ``new_bus`` does not exist in 
                the network.
            ValueError: If the operation attempts to replace the SLACK bus.
        """
        # 1. Recuperamos el nudo actual (si no existe, get_bus lanzará KeyError)
        current_bus = self.get_bus(bus_id)

        # 2. Usamos 'replace' para crear una copia con los cambios aplicados.
        #    Si el usuario pasa un atributo que no existe (ej: 'potencia' en vez de 'P'),
        #    replace lanzará un TypeError automáticamente, lo cual es buena validación.
        try:
            new_bus = replace(current_bus, **changes)
        except TypeError as e:
            raise ValueError(f"Error when modifying the bus {bus_id}: {e}") from e
            

        # 3. Delegamos en update_bus para que haga la sustitución segura y limpie la caché
        self.update_bus(new_bus)
 
    # --- GESTIÓN DE ESTADO (ON/OFF) ---------------------------------------------

    def set_bus_status(self, bus_id: int, active: bool, keep_shunt: bool = False):
        """
        Toggles the active status of a specific bus in the network.

        This method simulates connecting or disconnecting a bus without removing 
        it from the topology matrix structure.

        **Behavior when 'active=False' (Disconnect):**
            1. The original bus object is backed up to an internal memory.
            2. The bus is replaced by a "Dummy" PQ bus with:
               - P = 0.0, Q = 0.0 (No injection/load).
               - **Shunts:** If ``keep_shunt=True``, original G/B are kept. 
                 If ``False``, they are set to 0.0.
               - Original V_base is preserved. 
               - V_guess is set to the best available estimate (p.u.) for stability.
            3. Effectively, the node becomes a floating node (or just a passive shunt).

        **Behavior when 'active=True' (Reconnect):**
            1. Checks if a backup of the original bus exists.
            2. If found, restores the original bus object with all its parameters.
            3. Removes the backup from memory.

        **Side Effects:**
            - Triggers a global cache invalidation.

        Args:
            bus_id (int): The ID of the bus to modify.
            active (bool): 'True' to activate/restore the bus, 'False' to deactivate/isolate it.
            keep_shunt (bool): Only used when ``active=False``. If ``True``, the 
                shunt admittance (G, B) of the bus remains connected to the network 
                even if the load/generation is disconnected. Defaults to ``False``.

        Raises:
            KeyError: If the bus ID does not exist.
            ValueError: If attempting to deactivate the SLACK bus (forbidden).
        """
        if bus_id not in self._buses:
            raise KeyError(f"Bus ID {bus_id} not found.")

        current_bus = self._buses[bus_id]

        # Protección del Slack
        if current_bus.type == BusTypes.SLACK:
            raise ValueError("Cannot deactivate the Slack bus.")

        # CASO 1: DESACTIVAR (Turn OFF)
        if not active:
            # Si ya está desactivado (está en memoria), no hacemos nada o lanzamos warning
            if bus_id in self._disabled_buses_memory:
                warnings.warn(f"Bus {bus_id} was already deactivated. Command ignored.")
                return

            # 1. Guardar backup del original
            self._disabled_buses_memory[bus_id] = current_bus

            # 2. Determinar valores para el Dummy 

            # Lógica del Shunt (keep_shunt)
            g_val = current_bus.G_shunt if keep_shunt else 0.0
            b_val = current_bus.B_shunt if keep_shunt else 0.0

            # 3. Crear nudo "Dummy" (PQ con inyección nula)
            dummy_bus = PQBus(
                id=bus_id,
                P=0.0,
                Q=0.0,
                G_shunt=g_val, # Aplicamos la lógica elegida
                B_shunt=b_val, 
                V_guess= getattr(current_bus, 'V', getattr(current_bus, 'V_guess', 1.0)), # Usamos el valor corregido en p.u.
                V_base=current_bus.V_base
            )

            # 4. Sustituir en la red
            self._buses[bus_id] = dummy_bus
            self._invalidate_cache()

        # CASO 2: REACTIVAR (Turn ON)
        else:
            # Verificamos si tenemos una copia original guardada
            if bus_id not in self._disabled_buses_memory:
                # Si no está en memoria, asumimos que ya está activo.
                return

            # 1. Recuperar original
            original_bus = self._disabled_buses_memory.pop(bus_id)

            # 2. Restaurar en la red
            self._buses[bus_id] = original_bus
            self._invalidate_cache()


    # --- CONSULTA DE ESTADO (STATUS QUERIES) ------------------------------------

    def get_disabled_buses(self) -> list[InputBus]:
        """
        Retrieves a list of all buses that are currently deactivated (offline).

        Returns:
            list[InputBus]: A list containing the original InputBus objects 
            that are currently stored in memory. These buses are physically 
            disconnected from the active topology (replaced by dummy buses).
        """
        # Devolvemos los valores del diccionario de memoria como una lista
        return list(self._disabled_buses_memory.values())

    def is_bus_disabled(self, bus_id: int) -> bool:
        """
        Checks if a specific bus is currently deactivated.

        Args:
            bus_id (int): The unique identifier of the bus.

        Returns:
            bool: True if the bus is disabled (stored in memory), False otherwise.
        """
        # Simplemente comprobamos si el ID está en el diccionario de memoria
        return bus_id in self._disabled_buses_memory


    # ---- CONVERSION A OTROS FORMATOS ------

    def export_buses(
        self, 
        columns: list[str], 
        out_format: Literal['records', 'dataframe'] = 'records'
    ) -> list[dict] | pd.DataFrame:
        """
        Exports the bus definitions to a standard format (List of Dicts or DataFrame).

        **Handling of Disabled Buses:**
        If the network contains disabled buses (temporarily deactivated via 
        `set_bus_status`), this method will export the **ORIGINAL** bus definition 
        stored in memory, not the temporary "Dummy" object currently active in 
        the topology. A warning will be issued to alert the user.

        This ensures that the export represents the complete asset definition of 
        the network, regardless of the current operational status.

        Args:
            columns (list[str]): List of keys to extract. Case-insensitive.
                Supported Keys:
                    - **Meta:** 'id', 'type', 'base_kv'.
                    - **Setpoints (Fixed):** 'v_pu', 'v_kv', 'theta_rad', 'theta_deg'.
                    - **Guesses (Initial):** 'v_guess', 'theta_guess_rad', 'theta_guess_deg'.
                    - **Power (Input):** 'p_pu', 'p_mw', 'q_pu', 'q_mvar'.
                    - **Shunt:** 'g_pu', 'b_pu'.
            out_format (str): Output format. 
                - 'records': Returns a list of dictionaries (native Python).
                - 'dataframe': Returns a pandas DataFrame.

        Returns:
            list[dict] | pd.DataFrame: The exported data.
        """
        # 1. Comprobación de buses deshabilitados (Aviso al usuario)
        if self._disabled_buses_memory:
            warnings.warn(
                f"Export Warning: The network contains {len(self._disabled_buses_memory)} disabled buses. "
                "The export will use the ORIGINAL bus definitions from backup memory, "
                "ignoring the temporary 'dummy' objects used by the solver.",
                UserWarning
            )

        results = []
        
        # 2. Iteración ordenada (Determinismo)
        # Obtenemos todos los IDs ordenados para iterar
        all_ids = sorted(self._buses.keys())
        
        for bus_id in all_ids:
            # 3. Selección del objeto fuente (Activo vs Memoria)
            if bus_id in self._disabled_buses_memory:
                # Si está deshabilitado, usamos el objeto ORIGINAL guardado en memoria
                bus = self._disabled_buses_memory[bus_id]
            else:
                # Si está activo, usamos el objeto actual de la red
                bus = self._buses[bus_id]

            row = {}
            for col in columns:
                k = col.lower()
                val = None
                
                # --- Lógica de Extracción (Idéntica a la anterior) ---

                # Identificación y Metadatos
                if k == 'id': val = bus.id
                elif k == 'type': val = bus.type.name 
                elif k == 'base_kv': val = bus.V_base

                # Tensión (Separación Estricta: Setpoint vs Guess)
                elif k == 'v_pu': val = getattr(bus, 'V', None)
                elif k == 'v_kv': 
                    v_pu = getattr(bus, 'V', None)
                    if v_pu is not None:
                        if bus.V_base is None:
                            raise ValueError(f"Export Error (Bus {bus.id}): Cannot export 'v_kv', 'V_base' is missing.")
                        val = v_pu * bus.V_base
                
                elif k == 'v_guess': val = getattr(bus, 'V_guess', None)

                # Ángulo (Separación Estricta)
                elif k == 'theta_rad': val = getattr(bus, 'theta', None)
                elif k == 'theta_deg': 
                    rad = getattr(bus, 'theta', None)
                    if rad is not None: val = degrees(rad)
                
                elif k == 'theta_guess_rad': val = getattr(bus, 'theta_guess', None)
                elif k == 'theta_guess_deg':
                    rad = getattr(bus, 'theta_guess', None)
                    if rad is not None: val = degrees(rad)

                # Potencias de Entrada
                elif k == 'p_pu': val = getattr(bus, 'P', None)
                elif k == 'p_mw': 
                    p_pu = getattr(bus, 'P', None)
                    if p_pu is not None:
                        if self._s_base is None:
                            raise ValueError(f"Export Error: Cannot export 'p_mw'. Network 's_base' is not defined.")
                        val = p_pu * self._s_base
                
                elif k == 'q_pu': val = getattr(bus, 'Q', None)
                elif k == 'q_mvar':
                    q_pu = getattr(bus, 'Q', None)
                    if q_pu is not None:
                        if self._s_base is None:
                            raise ValueError(f"Export Error: Cannot export 'q_mvar'. Network 's_base' is not defined.")
                        val = q_pu * self._s_base

                # Shunts
                elif k == 'g_pu': val = bus.G_shunt
                elif k == 'b_pu': val = bus.B_shunt
                
                row[col] = val
            results.append(row)

        # --- FORMATTING OUTPUT ---
        if out_format == 'dataframe':
            return pd.DataFrame(results)
        elif out_format == 'records':
            return results
        else:
            raise ValueError(f"Invalid output format: '{out_format}'. Use 'records' or 'dataframe'.")

    def export_branches(
        self, 
        columns: list[str], 
        out_format: Literal['records', 'dataframe'] = 'records'
    ) -> list[dict] | pd.DataFrame:
        """
        Exports the branch definitions to a standard format (List of Dicts or DataFrame).

        Args:
            columns (list[str]): List of keys to extract. Case-insensitive.
                Supported Keys:
                    - 'id', 'type'.
                    - 'bus1', 'from', 'bus2', 'to'.
                    - 'r', 'x', 'g', 'b'.
                    - 'tap', 'shift', 's_max'.
            out_format (str): 'records' or 'dataframe'.

        Returns:
            list[dict] | pd.DataFrame: The exported data.
        """
        results = []
        sorted_branches = sorted(self._branches.values(), key=lambda b: b.id)
        
        for branch in sorted_branches:
            row = {}
            for col in columns:
                k = col.lower()
                val = None
                
                if k == 'id': val = branch.id
                elif k == 'type': val = branch.__class__.__name__ 
                elif k in ('bus1', 'from'): val = branch.bus1
                elif k in ('bus2', 'to'): val = branch.bus2
                
                # Impedancias (Duck Typing)
                elif k == 'r': val = getattr(branch, 'R', getattr(branch, 'Rcc', 0.0))
                elif k == 'x': val = getattr(branch, 'X', getattr(branch, 'Xcc', 0.0))
                elif k == 'g': val = getattr(branch, 'G', 0.0)
                elif k == 'b': val = getattr(branch, 'B', 0.0)
                
                # Transformadores
                elif k == 'tap': val = getattr(branch, 'tap_ratio', 1.0)
                elif k == 'shift': val = getattr(branch, 'shift', 0.0)
                
                elif k == 's_max': val = getattr(branch, 'S_max', float('inf'))
                
                row[col] = val
            results.append(row)

        # --- FORMATTING OUTPUT ---
        if out_format == 'dataframe':
            return pd.DataFrame(results)
        elif out_format == 'records':
            return results
        else:
            raise ValueError(f"Invalid output format: '{out_format}'. Use 'records' or 'dataframe'.")


    def to_excel(
        self,
        filepath: str,
        include_buses: bool = True,
        include_branches: bool = True,
        include_s_base: bool = True,
        bus_columns: list[str] | None = None,
        branch_columns: list[str] | None = None,
        sheet_names: dict[str, str] | None = None
    ):
        """
        Exports the network definition to an Excel file (.xlsx) with configurable sheets.

        This method acts as a high-level wrapper around `export_buses` and 
        `export_branches`, directing their DataFrame outputs to specific sheets 
        in an Excel workbook. It also supports exporting global parameters (S_base).

        **Defaults:**
        If column lists are not provided, a comprehensive set of standard columns 
        is selected by default to ensure a useful export.

        Args:
            filepath (str): Destination path for the .xlsx file.
            include_buses (bool): Whether to generate a sheet for Buses. Default True.
            include_branches (bool): Whether to generate a sheet for Branches. Default True.
            include_s_base (bool): Whether to generate a sheet for General Data. Default True.
            bus_columns (list[str] | None): Specific keys to export for buses. 
                If None, defaults to: ['id', 'type', 'base_kv', 'v_pu', 'theta_deg', 'p_pu', 'q_pu', 'g_pu', 'b_pu'].
                See `export_buses` for all available keys.
            branch_columns (list[str] | None): Specific keys to export for branches.
                If None, defaults to: ['id', 'type', 'bus1', 'bus2', 'r', 'x', 'b', 'tap', 'shift', 's_max'].
                See `export_branches` for all available keys.
            sheet_names (dict[str, str] | None): Custom names for the Excel sheets.
                Default mapping: `{'buses': 'Buses', 'branches': 'Branches', 's_base': 'General'}`.
                You can override specific keys without providing the whole dictionary.

        Raises:
            ValueError: If a requested column key is invalid (raised by underlying export methods).
            IOError: If the file cannot be written (e.g., open in another program).
        """
        # 1. Configuración de Defaults
        if bus_columns is None:
            bus_columns = [
                "id", "type", "base_kv", 
                "v_pu", "theta_deg", 
                "p_pu", "q_pu", 
                "g_pu", "b_pu"
            ]
        
        if branch_columns is None:
            branch_columns = [
                "id", "type", "bus1", "bus2", 
                "r", "x", "b", "g", 
                "tap", "shift", "s_max"
            ]

        # Fusión de nombres de hojas (Defaults + Custom)
        sheets = {'buses': 'Buses', 'branches': 'Branches', 's_base': 'General'}
        if sheet_names:
            sheets.update(sheet_names)

        # 2. Generación de DataFrames
        # Usamos los métodos existentes con 'dataframe' como formato
        df_buses = None
        if include_buses:
            df_buses = self.export_buses(columns=bus_columns, out_format='dataframe')

        df_branches = None
        if include_branches:
            df_branches = self.export_branches(columns=branch_columns, out_format='dataframe')

        df_general = None
        if include_s_base:
            # Creamos un DF simple llave-valor para los generales
            df_general = pd.DataFrame([
                {"Parameter": "S_base_MVA", "Value": self._s_base},
                {"Parameter": "Network_Size_Buses", "Value": len(self._buses)},
                {"Parameter": "Network_Size_Branches", "Value": len(self._branches)}
            ])

        # 3. Escritura a Excel
        # Usamos 'xlsxwriter' o 'openpyxl' según disponibilidad (Pandas lo gestiona)
        with pd.ExcelWriter(filepath) as writer:
            
            # Hoja General
            if include_s_base and df_general is not None:
                df_general.to_excel(writer, sheet_name=sheets['s_base'], index=False)

            # Hoja Buses
            if include_buses and df_buses is not None:
                df_buses.to_excel(writer, sheet_name=sheets['buses'], index=False)

            # Hoja Ramas
            if include_branches and df_branches is not None:
                df_branches.to_excel(writer, sheet_name=sheets['branches'], index=False)


    def to_json(self, filepath: str) -> None:
        """
        Exports the current network state to a JSON file.

        This export includes all buses (both active and currently disabled in memory),
        branches, and the system base power. It uses direct object serialization 
        to ensure fidelity.

        Note:
            If the network contains disabled buses, a warning will be issued. 
            The ORIGINAL (active) definitions of those buses will be saved instead 
            of the temporary dummy buses. The "disabled" status itself is NOT 
            preserved in the JSON file; they will be active upon reload.

        Args:
            filepath (str): Destination path for the .json file.
        """
        import pywerflow.io.json_io as json_io
        json_io.network_to_json(self, filepath)





    # def gauss_seidel_solve(self, tol=None, alpha=None, max_it=None, fix_step=None):
    #     self._ensure_internal_data()
    #     self._ensure_y_matrix()

    #     # CONTRUCCION DE PQV ----------------------------------------------------

    #     # 1. Construimos la "Columna 2" (La mixta V/Q)
    #     # Empezamos copiando el array de Q completo (cubre los PQ)
    #     pqv_col_2 = self._q_arr.copy()
    #     N = len(pqv_col_2) # Calculamos N ya que estamos...

    #     # Sobrescribimos SOLO las posiciones PV con valores de V
    #     pqv_col_2[self._pv_idxs] = self._v_arr[self._pv_idxs]

    #     # 2. Construimos una matriz temporal Nx2
    #     # Columna 1: P (Siempre es P independientemente del bus)
    #     # Columna 2: La mixta que acabamos de crear
    #     # Resultado: [[P0, Mix0], [P1, Mix1], [P2, Mix2]...] (donde mix puede ser V o Q)
    #     pqv_matrix = np.column_stack((self._p_arr, pqv_col_2))

    #     # 3. Eliminamos la fila del Slack con máscara booleana
    #     mask = np.ones(N, dtype=bool)
    #     mask[self._slack_idx] = False
        
    #     # Aplicamos la máscara (Filtra la fila del slack) (la quita)
    #     pqv_matrix = pqv_matrix[mask]

    #     # 4. Aplanamos (Flatten)
    #     # ravel() convierte la matriz [[P, M], [P, M]] en [P, M, P, M...]
    #     pqv_1darr = pqv_matrix.ravel()
        
        
    #     # CONTRUCCION DE bustypes ----------------------------------------------------
    #     # 1. Crear array base de Falsos (Asumimos PV por defecto)
    #     # Tamaño N completo
    #     pqpv_bus_types = np.zeros(N, dtype=bool)

    #     # 2. Marcar los PQ como True
    #     # Usamos los índices internos cacheados (Vectorizado, instantáneo)
    #     pqpv_bus_types[self._pq_idxs] = True

    #     # 4. Usamos la misma mascara que antes para quitar el slack
    #     pqpv_bus_types = pqpv_bus_types[mask]


    #     # CONSTRUCCION DE y_matrix ----------------------------------------------------
    #     # 1. Construimos el VECTOR DE PERMUTACIÓN
    #     # Concatenamos: [Indices_No_Slack] + [Indice_Slack]
    #     # Ej: Si N=10 y Slack=4 -> [0,1,2,3,5,6,7...] + [4] -> [0,1,2,3,...9,4]
    #     perm_indices = np.concatenate((
    #         np.arange(N)[mask],  # Indices MENOS el slack [0,1,2,3,5,6,7...] (si el slack fuera el 4)
    #         [self._slack_idx]    # Indice DEL slack [4] (si el slack fuera el 4)
    #     ))
    
    #     # 2. Aplicamos la permutación
    #     # Usamos np.ix_ para reordenar filas y columnas simultáneamente.
    #     # Retornará la misma matriz pero con las filas y las columnas puestas según el orden de perm_indices
    #     y_matrix = self._y_matrix[np.ix_(perm_indices, perm_indices)]


    #     # CONSTRUCCION DE v0 ----------------------------------------------------
       
    #     # 1. Conversión Polar -> Rectangular (Vectorizada)
    #     # V_complex = Magnitud * e^(j * angulo)
    #     # Esto genera un array complejo ordenado por ID (orden interno original)
    #     v0_complex_1darr = self._v_arr * (np.cos(self._theta_arr) + 1j * np.sin(self._theta_arr))

    #     # 2. Reordenar y Retornar
    #     # Al usar indexing avanzado, NumPy crea una copia reordenada
    #     v0_complex_1darr = v0_complex_1darr[perm_indices]
    

    #     v_final_ordered, k = gauss_seidel(
    #         pqv = pqv_1darr,
    #         pqpv_bus_types = pqpv_bus_types,
    #         Ybus = y_matrix.ravel(),
    #         v0 = v0_complex_1darr,
    #     )

    #     # --- POST-PROCESADO ---
        
    #     # v_final_ordered tiene el orden [Resto..., Slack]
    #     # perm_indices tiene qué índice original corresponde a cada posición de v_final
    #     # Así que podemos asignar directamente usando los índices a la izquierda.
    #     solved_v_arr = np.zeros(dtype=float)
    #     solved_theta_arr = np.zeros(dtype=float)

    #     # Actualizamos Magnitudes
    #     solved_v_arr[perm_indices] = np.abs(v_final_ordered)
    #     # Actualizamos Ángulos
    #     solved_theta_arr[perm_indices] = np.angle(v_final_ordered)
        
    #     for i, (v, theta) in enumerate(zip(solved_v_arr, solved_theta_arr)):
    #         print(i, v, theta)

    #     # HACER ALGO CON LA K (codigos de error)
    #     # HACER ALGO CON LA SOLUCION (SolvedBuses ?)

    #     return k # Retornamos iteraciones

    


    # def solve(self):
    #     """
    #     Metodo para resolver el flujo de cargas. Una vez la matriz de admitancias ya está calculada.
    #     """
    #     pass


    # def to_physical(self):
    #     """
    #     Metodo para convertir a red fisica, requiere que se conozcan las secciones
    #     """
    #     pass


    # def modify_network(self):
    #     """
    #     Ya que la red es inmutable, este metodo permite crear una nueva a partir de esta modificando algunas cosas
    #     """
    #     pass








"""
COSAS QUE HACER:
    - la matriz de admitancias deberia ser una "matriz dispersa" -> csr_matrix (considerarlo)

    """
