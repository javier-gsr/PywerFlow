import ctypes
import numpy as np
from numpy.ctypeslib import ndpointer

# --- DEFINICIONES DE TIPOS NUEVOS C ---

class MethodResponse(ctypes.Structure):
    _fields_ = [
        ("status_code", ctypes.c_int8),
        ("iterations", ctypes.c_uint32),
        ("final_error", ctypes.c_double)
    ]


# --- DICCIONARIO MAESTRO DE FIRMAS ---
# Clave: Nombre exacto de la función en C
# Valor: Diccionario con 'argtypes' y 'restype'

C_METHODS_CONFIG = {

    "gauss_seidel": {
        "argtypes": [
            ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),    # pqv_data
            ndpointer(dtype=np.bool, ndim=1, flags='C_CONTIGUOUS'),       # bus_types
            ndpointer(dtype=np.complex128, ndim=1, flags='C_CONTIGUOUS'), # adm_matrix
            ndpointer(dtype=np.complex128, ndim=1, flags='C_CONTIGUOUS'), # v0_data
            ctypes.c_uint32, # N
            ctypes.c_double, # epsilon
            ctypes.c_uint32, # max_iterations
            ctypes.c_uint32, # v_fixing_step
            ctypes.c_double, # acceleration_factor
            ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS'),    # error_history
            ctypes.c_uint32, # err_history_limit
        ],
        "restype": MethodResponse
    },

    # Futuro ejemplo:
    # "fast_decoupled": {
    #     "argtypes": [ ... ],
    #     "restype": MethodResponse
    # }
}