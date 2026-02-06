import ctypes
import os
from pywerflow.solvers.c_backend.c_methods_registry import  C_METHODS_CONFIG, MethodResponse
from pywerflow.paths.paths import DLL_PATH

_lib = None

def get_library():
    """
    Loads the monolithic DLL using the centralized path configuration.
    """
    global _lib
    if _lib is not None:
        return _lib

    # 1. Usamos la ruta centralizada
    dll_path_str = str(DLL_PATH)

    if not os.path.exists(dll_path_str):
        raise FileNotFoundError(
            f"C Engine DLL not found at: {dll_path_str}\n"
            "Please run 'python build_win_dll.py' to compile the C extensions."
        )

    try:
        # 2. Cargar DLL
        lib = ctypes.CDLL(dll_path_str)
        
        # 3. Configurar firmas
        for func_name, config in C_METHODS_CONFIG.items():
            if hasattr(lib, func_name):
                c_func = getattr(lib, func_name)
                c_func.argtypes = config["argtypes"]
                c_func.restype = config["restype"]
            else:
                # Opcional: Warning si falta alguna función esperada
                # print(f"[WARNING] Function '{func_name}' found in registry but NOT in DLL.")
                pass

        _lib = lib
        return lib
        
    except OSError as e:
        raise RuntimeError(f"Failed to load C Engine DLL: {e}")