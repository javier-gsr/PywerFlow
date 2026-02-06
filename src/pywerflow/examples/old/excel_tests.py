import os
import sys
import warnings
import pandas as pd
import numpy as np

# Ajusta esto según tu estructura de carpetas si es necesario
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pywerflow.networks.pfnetwork_builder import PFNetworkBuilder
from pywerflow.io.excel_report import generate_excel_report
from pywerflow.buses.bus_types import BusTypes

# Constantes para la prueba
OUTPUT_DIR = "stress_test_outputs"
CASE_PATH = r"C:\Users\javir\Desktop\TFG\TFG Sistema eléctrico\Código\PywerFlow\src\pywerflow\examples\ieee9\matpower_cases\case300.m"  # Ajusta a tu ruta real

def setup_network():
    """Carga la red base limpia para cada test."""
    print(f"--> Cargando {CASE_PATH}...")
    builder = PFNetworkBuilder()
    builder.load_matpower(CASE_PATH)
    network = builder.build()
    return network

def run_stress_test():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("==================================================")
    print("   INICIANDO STRESS TEST DE EXPORTACIÓN (IO)      ")
    print("==================================================")

    # -------------------------------------------------------------------------
    # TEST 1: REPORT COMPLETO ESTÁNDAR (HAPPY PATH)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Generando Reporte Completo Estándar (Baseline)...")
    net = setup_network()
    res = net.newton_raphson_solve(tol=1e-4, max_it=20)
    
    file_1 = os.path.join(OUTPUT_DIR, "01_Full_Report_Standard.xlsx")
    generate_excel_report(
        filepath=file_1,
        network=net,
        results=res,
        sheet_names={'meta': 'RESUMEN', 'res_buses': 'RESULTADOS_NUDOS'}
    )
    print(f"   OK -> Generado: {file_1}")

    # -------------------------------------------------------------------------
    # TEST 2: EL "NUDO ZOMBI" (BUSES DESHABILITADOS)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Probando Exportación con Buses Deshabilitados...")
    net = setup_network()
    
    # Deshabilitamos nudos importantes (ej: nudo 10 y 50)
    # Guardamos sus valores originales para comparar mentalmente
    original_bus_10 = net.get_bus(10)
    print(f"   -> Deshabilitando Bus 10 (Tipo original: {original_bus_10.type.name}, P={original_bus_10.P})")
    
    net.set_bus_status(10, active=False)
    
    # Resolvemos la red (ahora el Bus 10 es un dummy flotante)
    res = net.newton_raphson_solve()
    
    # Exportamos solo los inputs de la red
    file_2 = os.path.join(OUTPUT_DIR, "02_Disabled_Buses_Input.xlsx")
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        net.to_excel(
            filepath=file_2,
            include_branches=False,
            include_s_base=False,
            bus_columns=['id', 'type', 'p_pu', 'v_guess'] # Columnas clave
        )
        print(f"   -> Warnings capturados: {len(w)}")
        if len(w) > 0:
            print(f"      Mensaje: {w[0].message}")

    print(f"   OK -> Generado: {file_2}")

    # -------------------------------------------------------------------------
    # TEST 3: EL "FÍSICO ROTO" (SIN S_BASE)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Provocando Error por falta de S_base...")
    net = setup_network()
    
    # SABOTAJE: Eliminamos la S_base de la red a la fuerza
    net._s_base = None 
    print("   -> S_base eliminada (set a None).")

    try:
        # Intentamos exportar en MW (requiere S_base)
        net.export_buses(columns=['id', 'p_mw'])
        print("   [FALLO] El código debería haber lanzado error y no lo hizo.")
    except ValueError as e:
        print(f"   [ÉXITO] Error capturado correctamente: {e}")

    # -------------------------------------------------------------------------
    # TEST 4: EL "VOLTAJE HUECO" (BUS SIN V_BASE)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Provocando Error por falta de V_base en un nudo...")
    net = setup_network()
    
    # SABOTAJE: Quitamos V_base al nudo 5
    # Usamos modify_bus si está disponible o hackeamos el objeto (dado que son inmutables, usamos update)
    # Asumimos que existe modify_bus como definimos antes
    from dataclasses import replace
    bus5 = net.get_bus(5)
    bus5_broken = replace(bus5, V_base=None) # Lo rompemos
    net.update_bus(bus5_broken)
    print(f"   -> Bus 5 saboteado (V_base = None).")

    try:
        # Intentamos exportar KV para toda la red. Debería fallar al llegar al 5.
        net.export_buses(columns=['id', 'v_kv'])
        print("   [FALLO] El código debería haber lanzado error y no lo hizo.")
    except ValueError as e:
        print(f"   [ÉXITO] Error capturado correctamente: {e}")

    # -------------------------------------------------------------------------
    # TEST 5: CUSTOMIZACIÓN EXTREMA Y ORDEN
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Exportación con Columnas Raras y Desordenadas...")
    net = setup_network()
    
    cols = ['b_pu', 'id', 'type', 'g_pu'] # Orden caótico intencional
    file_5 = os.path.join(OUTPUT_DIR, "05_Chaos_Columns.xlsx")
    
    net.to_excel(
        filepath=file_5,
        include_branches=False,
        bus_columns=cols
    )
    print(f"   OK -> Generado: {file_5}. Verificar orden de columnas.")

    # -------------------------------------------------------------------------
    # TEST 6: CONSISTENCIA REPORT FULL (BASE MIXTA)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Reporte Full con Inconsistencia de Bases (Network vs Results)...")
    net = setup_network()
    
    # 1. Resolvemos con S_base original (ej: 100)
    res = net.newton_raphson_solve()
    
    # 2. SABOTAJE: Cambiamos la base de la red DESPUÉS de resolver
    # Esto simula un usuario que toca lo que no debe
    original_base = net.s_base
    net._s_base = 1337.0 
    print(f"   -> Base original: {original_base}. Base saboteada: {net.s_base}")
    
    file_6 = os.path.join(OUTPUT_DIR, "06_Inconsistent_Base.xlsx")
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        generate_excel_report(
            filepath=file_6,
            network=net,
            results=res
        )
        print(f"   -> Warnings de consistencia capturados: {len(w)}")
        if len(w) > 0:
            print(f"      Mensaje: {w[0].message}")

    print(f"   OK -> Generado: {file_6}")
    print("\n--- FIN DE LOS TESTS ---")

if __name__ == "__main__":
    run_stress_test()