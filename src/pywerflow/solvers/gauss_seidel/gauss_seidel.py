import numpy as np
import ctypes
from pywerflow.solvers.results import SolverMetaResult
from pywerflow.solvers.c_backend.c_manager import get_library

METHOD_NAME = "Gauss-Seidel"
EXTRAS = ["accel_factor", "fix_step", "history_truncated"]

MAX_SAFE_N = 65535


def gauss_seidel(
    pqv_arr: np.ndarray,
    bus_types: np.ndarray, 
    Ymatrix: np.ndarray, 
    v0: np.ndarray,
    tolerance: float,
    max_iterations: int, 
    fix_step: int, 
    accel_factor: float,
    err_history_limit: int,
) -> tuple[np.ndarray, SolverMetaResult]:
    """
    Solves the Power Flow problem using the Gauss-Seidel method via the C Engine.

    Args:
        pqv_arr (np.ndarray): Interleaved array containing [P0, Q0 or V0, P1, Q1 or V1, ...].
            Must be of type float64 and shape (2*(N-1),). Without the slack bus.
            For PQ buses, the second value is Q. For PV buses, it is V magnitude.
        bus_types (np.ndarray): Boolean array identifying bus types.
            True for PQ buses, False for PV buses. Shape (N-1,). Without the slack bus
        Ymatrix (np.ndarray): The nodal admittance matrix flattened 
            (row-major order). Must be complex128 and shape (N*N,).
            The slack bus must be in the last row and column.
        v0 (np.ndarray): Initial voltage guess (complex). 
            Shape (N,). This array is copied and not modified in place.
            The slack must be in the last row.
        tolerance (float): The convergence threshold (epsilon). 
            The method stops if max(|V_new - V_old|) < tolerance.
        max_iterations (int): Maximum number of iterations allowed before reporting divergence.
        fix_step (int): Iteration from which the correction in the voltage of the PV nodes begins to be applied.
            The method will be forced to perform at least the iterations necessary to reach fix_step.
        accel_factor (float): Acceleration factor (alpha) applied to the voltage.
            Optimal values are usually between 1.4 and 1.6. 
            A value of 1 means that the factor does not apply.
        err_history_limit (int): Maximum number of iterations to record in the error history.
            If the method iterates more than this limit, the history will be truncated 
            to save memory, but the calculation will continue until convergence or max_iterations.
    Raises:
        ValueError: If system size N is invalid (< 1) or exceeds safety limits.
        ValueError: If configuration parameters (like max_iterations) are inconsistent.
        OverflowError: If arithmetic overflow is detected in the C backend.
        RuntimeError: For unknown internal errors in the C engine.

    Returns:
        tuple[np.ndarray, SolverMetaResult]: A tuple containing:
            1. The complex voltage solution array (shape N,).
            2. A metadata object with method details.
    """
    
    # 1. Obtener la instancia única de la librería C cargada
    # El manager ya se encargó de buscar el DLL y configurar argtypes/restype
    lib = get_library()
    
    N = len(v0)
    # --- SANITY CHECKS (Validaciones Previas) ---
    # Mantenemos esta protección en Python para dar un error descriptivo antes de llamar a C

    if N > MAX_SAFE_N:
        raise ValueError(f"System too large ({N} nodes). "
                         f"Safety limit for 32-bit arithmetic is {MAX_SAFE_N}.")

    # 2. Preparar datos para C (C_CONTIGUOUS)
    # Es vital que los datos estén ordenados en memoria para que C los lea bien
    pqv_c = np.ascontiguousarray(pqv_arr, dtype=np.float64)
    types_c = np.ascontiguousarray(bus_types, dtype=np.bool)
    Ybus_c = np.ascontiguousarray(Ymatrix, dtype=np.complex128)
    # Creamos una copia para no modificar el v0 original del usuario
    v_solution = np.ascontiguousarray(v0.copy(), dtype=np.complex128)
    # Creamos el array para que C almacene el historial de errores
    err_history_limit = min(int(err_history_limit), int(max_iterations))
    error_history = np.zeros(err_history_limit, dtype=np.float64)
    error_history = np.ascontiguousarray(error_history, dtype=np.float64)

    # 3. Llamada al Motor C
    # Aunque argtypes ya está configurado en el manager, usar los wrappers de ctypes (c_uint32, etc.)
    # en la llamada es una buena práctica para asegurar que pasamos el tipo exacto.
    response = lib.gauss_seidel(
        pqv_c, 
        types_c, 
        Ybus_c, 
        v_solution, 
        ctypes.c_uint32(N), 
        ctypes.c_double(tolerance), 
        ctypes.c_uint32(max_iterations), 
        ctypes.c_uint32(fix_step),
        ctypes.c_double(accel_factor),
        error_history,
        ctypes.c_uint32(err_history_limit),
    )

    # 4. Gestión de la Respuesta
    # La estructura MethodResponse ya fue interpretada por ctypes gracias al manager
    code = response.status_code
    iters = response.iterations
    final_error = response.final_error


    # --- Lógica de Historial y Truncamiento ---
    if iters > err_history_limit:
        # Hemos iterado más de lo que podíamos guardar -> Historial lleno y truncado
        valid_history = error_history # Todo el array está lleno
        history_truncated = True
    else:
        # Hemos terminado antes de llenar el buffer -> Recortamos los ceros sobrantes
        history_truncated = False
        valid_history = error_history[:iters]


    # Preparamos los extras comunes
    extras_result = {
        "accel_factor": accel_factor,
        "fix_step": fix_step,
        "history_truncated": history_truncated # Flag informativo
    }

    # Creación del resultado según el código
    if code == 0:
        meta_result = SolverMetaResult(
            success = True,
            method_name = METHOD_NAME,
            message = "The method has converged.",
            iterations = iters,
            final_error = final_error,
            tolerance_used = tolerance,
            error_history=valid_history,
            extras = extras_result
        )
        return v_solution, meta_result
        
    elif code == -1:
        meta_result = SolverMetaResult(
            success = False,
            method_name = METHOD_NAME,
            message = f"The method has reached the iteration limit ({max_iterations}). It diverged.",
            iterations = iters,
            final_error = final_error,
            tolerance_used = tolerance,
            error_history=valid_history,
            extras = extras_result
        )
        
        return v0, meta_result
    
    elif code == -2:
        raise ValueError("Input error: System size N < 1.")
    elif code == -3:
        raise ValueError("Invalid configuration: 'max_iterations' must be greater than 'v_fixing_step'.")
    elif code == -4:
        raise OverflowError("Arithmetic overflow risk detected in C backend.")
    else:
        raise RuntimeError(f"Unknown error code returned from C Engine: {code}")
    




