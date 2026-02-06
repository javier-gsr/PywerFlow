import os
import subprocess
import glob
import sys
from pathlib import Path

# Asumimos que el paquete está instalado o accesible (bootstrap eliminado)
from pywerflow.paths.paths import (
        DLL_PATH,              
        SOLVE_METHODS_DIR,     
        COMMON_C_HEADER_PATH   
)

# --- CONFIGURACIÓN ---
COMPILER_COMMAND = "gcc"

# Guardamos la raíz del proyecto (donde está este script build_win_dll.py)
# Usaremos esto como ancla para hacer todas las rutas relativas.
PROJECT_ROOT = Path(__file__).parent.resolve()

def get_relative_path(target_path: Path) -> str:
    """
    Intenta convertir una ruta absoluta a relativa respecto a PROJECT_ROOT.
    Si falla (ej. distinta unidad de disco), devuelve la absoluta.
    """
    try:
        return str(target_path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(target_path)

def build():
    print(f"[Info] Starting build process for: {sys.platform}")

    # 1. Crear directorio bin (Python maneja bien las tildes, esto no falla)
    bin_dir = DLL_PATH.parent
    if not bin_dir.exists():
        try:
            bin_dir.mkdir(parents=True, exist_ok=True)
            print(f"[Info] Created output directory: {bin_dir}")
        except OSError as e:
            print(f"[Error] Could not create directory: {e}")
            return

    # 2. Buscar archivos .c (Glob devuelve strings absolutos o relativos según implementación)
    search_pattern = str(SOLVE_METHODS_DIR / "**" / "*.c")
    c_files_found = glob.glob(search_pattern, recursive=True)

    if not c_files_found:
        print(f"[Error] No .c files found in {SOLVE_METHODS_DIR}")
        return

    # --- TRUCO DE SANITIZACIÓN: CONVERTIR A RELATIVO ---
    # Convertimos TODAS las rutas a relativas (src/pywerflow/...) 
    # para evitar que GCC vea "eléctrico" o "Código".
    
    # A) Archivos fuente
    c_files_rel = [get_relative_path(Path(f)) for f in c_files_found]
    
    # B) Archivo de salida (.dll)
    output_rel = get_relative_path(DLL_PATH)
    
    # C) Directorio de headers (-I)
    include_dir_rel = get_relative_path(COMMON_C_HEADER_PATH.parent)


    print(f"[Info] Found {len(c_files_rel)} source files.")
    print(f"[Info] Using header directory (relative): {include_dir_rel}") 
    
    # 3. Construir Flags con rutas relativas
    FLAGS = [
        "-shared", 
        "-static", 
        "-O3", 
        "-march=native",
        f"-I{include_dir_rel}" 
    ]

    # 4. Construir comando
    cmd = [COMPILER_COMMAND, "-o", output_rel] + c_files_rel + FLAGS
    
    print("\n[Info] Compiling...")
    # print(f"Command: {' '.join(cmd)}")  # Descomenta para ver que ya no hay tildes

    try:
        # IMPORTANTE: cwd=PROJECT_ROOT asegura que las rutas relativas funcionen
        subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        
        print("-" * 60)
        print(f"[SUCCESS] Monolithic DLL generated successfully at:")
        # Mostramos absoluta para que tú sepas dónde está, aunque GCC usó relativa
        print(f"          {DLL_PATH}")
        print("-" * 60)
    except Exception as e:
        print("-" * 60)
        print(f"[FAILURE] Compilation failed: {e}")
        print("-" * 60)

if __name__ == "__main__":
    build()