import sys
from pathlib import Path
import os

# --- ANCLA ---
# Definimos la raiz del paquete (src/pywerflow/)
PACKAGE_ROOT = Path(__file__).parent.parent.resolve()


# --- RUTAS DE BINARIO MONOLITICO (DLLs) ---
DLL_PATH = PACKAGE_ROOT / "bin" / "c_methods.dll"

# --- RUTAS DE CÓDIGO FUENTE C (Para el Builder) ---
# Ruta de solve methods
SOLVE_METHODS_DIR = PACKAGE_ROOT / "solvers"
# Ruta del sub-modulo c_manager 
C_MANAGER_DIR = PACKAGE_ROOT / "solvers" / "c_backend"
# Header de todos los archivos .c
COMMON_C_HEADER_PATH = PACKAGE_ROOT / "solvers" / "c_backend" / "c_common.h"


# ----- RECURSOS Y CASOS --------------
RESOURCES_DIR = PACKAGE_ROOT / "resources"
IEEE_CASES_DIR = RESOURCES_DIR / "ieee_cases"

IEEE14_PATH = IEEE_CASES_DIR / "case14.m"
IEEE30_PATH = IEEE_CASES_DIR / "case_ieee30.m"
IEEE57_PATH = IEEE_CASES_DIR / "case57.m"
IEEE118_PATH = IEEE_CASES_DIR / "case118.m"
IEEE145_PATH = IEEE_CASES_DIR / "case145.m"
IEEE300_PATH = IEEE_CASES_DIR / "case300.m"
