# Asegúrate de que pywerflow está en tu PYTHONPATH o ejecuta esto desde la raíz del proyecto
import math
import os
import numpy as np
from pywerflow.networks.pfnetwork_builder import PFNetworkBuilder
from pywerflow.buses.base_buses import BaseBus
from pywerflow.buses.input_buses import InputBus
from pywerflow.buses.bus_types import BusTypes


def test_build_network():
    print("--- INICIANDO TEST DE CONSTRUCCIÓN ---")
    
    # 1. Instanciar Builder
    builder = PFNetworkBuilder()
    
    # 2. Cargar archivo (Ajusta la ruta si es necesario)
    case_path = "matpower_cases/case9.m" 
    print(f"Leyendo archivo: {case_path}")
    
    try:
        # Usamos el método wrapper que acabamos de crear
        builder.load_matpower(case_path)
        print("-> Archivo parseado y datos inyectados en el Builder correctamente.")
        
    except Exception as e:
        print(f"ERROR FATAL leyendo Matpower: {e}")
        return

    # 3. Construir la Red (Aquí saltan las validaciones topológicas)
    try:
        network = builder.build()
        print("-> Network construida exitosamente.")
        
    except ValueError as e:
        print(f"ERROR DE VALIDACIÓN: {e}")
        return

    # 4. Inspeccionar resultados
    print("\n--- RESUMEN DE LA RED ---")
    print(f"Potencia Base: {network.s_base_mva} MVA")
    print(f"Total Buses:   {len(network.buses)}")
    print(f"Total Ramas:   {len(network.branches)}")
    
    # Verificamos el Slack
    slack = next(b for b in network.buses if b.type == BusTypes.SLACK)
    print(f"Slack Bus ID:  {slack.id} (V={slack.V} p.u., Theta={slack.theta} rad)")
    
    # Verificamos un generador (PV)
    pv_buses = [b for b in network.buses if b.type == BusTypes.PV]
    if pv_buses:
        print(f"Ejemplo PV ({pv_buses[0].id}): P={pv_buses[0].P:.4f} p.u., V={pv_buses[0].V:.4f} p.u.")



def solve_case(case_path: str, initial:bool = True, **kwargs):
    print(f"--- RESOLVIENDO {os.path.basename(case_path)} CON GAUSS-SEIDEL ---")

    # 1. Construir la red
    builder = PFNetworkBuilder()
    try:
        builder.load_matpower(case_path)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {case_path}")
        return

    network = builder.build()
    
    if initial:
        # --- NUEVO BLOQUE: VISUALIZACIÓN DEL ESTADO INICIAL ---
        s_base = builder._s_base
        has_base = s_base is not None and s_base > 0
        factor = s_base if has_base else 1.0
        
        p_unit = "MW" if has_base else "p.u."
        q_unit = "MVar" if has_base else "p.u."
        
        print(f"\n--- ESTADO INICIAL DE LA RED (Base: {s_base if has_base else 'N/A'} MVA) ---")
        print(f"{'Bus ID':<7} | {'Type':<6} | {'V (set/gs)':<10} | {'Ang (deg)':<10} | {'P ' + p_unit:<10} | {'Q ' + q_unit:<10}")
        print("-" * 65)

        sorted_input_buses = sorted(network._buses.values(), key=lambda b: b.id)

        for bus in sorted_input_buses:
            # Valores por defecto para visualización
            v_str = "-"
            ang_str = "-"
            p_str = "-"
            q_str = "-"

            # Lógica de extracción según tipo de Bus (InputBus)
            if bus.type == BusTypes.SLACK:
                # Slack: V y Theta son fijos (Setpoints). P y Q son incógnitas.
                v_str = f"{bus.V:.4f}"
                ang_str = f"{math.degrees(bus.theta):.2f}"
                p_str = "Slack (?)"
                q_str = "Slack (?)"

            elif bus.type == BusTypes.PV:
                # PV: P y V son fijos. Theta es guess. Q es incógnita.
                v_str = f"{bus.V:.4f}"
                ang_str = f"{math.degrees(bus.theta_guess):.2f} (gs)"
                p_str = f"{bus.P * factor:.4f}"
                q_str = "PV (?)"

            elif bus.type == BusTypes.PQ:
                # PQ: P y Q son fijos. V y Theta son guesses.
                v_str = f"{bus.V_guess:.4f} (gs)"
                ang_str = f"{math.degrees(bus.theta_guess):.2f} (gs)"
                p_str = f"{bus.P * factor:.4f}"
                q_str = f"{bus.Q * factor:.4f}"

            print(f"{bus.id:<7} | {bus.type.name:<6} | {v_str:<10} | {ang_str:<10} | {p_str:<10} | {q_str:<10}")
        
        print("-" * 65 + "\n")
        # ------------------------------------------------------


    # 2. Resolver
    # Gauss-Seidel devuelve un objeto PowerFlowResults
    print("Iniciando solver...")
    try:
        # results = network.gauss_seidel_solve(tol=1e-9, max_it=100000)
        results = network.newton_raphson_solve( **kwargs )

    except RuntimeError as e:
        print(f"Error crítico en el solver: {e}")
        return

    # 3. Analizar Resultados
    # Accedemos a los metadatos a través de results.meta
    if results.meta.success:
        print("\n¡CONVERGENCIA ALCANZADA! 🚀")
        print(f"Iteraciones: {results.meta.iterations}")
        print(f"Error Final: {results.meta.final_error:.2e}")
        


        # 4. Mostrar Voltajes resultantes (Iteración manual)
        print("\n--- Resultados de Voltaje ---")
        # Cabecera de la tabla para que quede bonito
        print(f"{'Bus ID':<7} | {'V (p.u.)':<9} | {'Ang (deg)':<10} | {'P Net':<10} | {'Q Net':<10}")
        print("-" * 58)
        # Ordenamos los buses resueltos por ID para mostrarlo bonito
        # results.buses es una lista de objetos SolvedBus
        sorted_solved_buses = sorted(results.buses, key=lambda b: b.id)
        
        for bus in sorted_solved_buses:
            v_mag = bus.V
            v_ang_deg = math.degrees(bus.theta) # Convertimos rad a deg
            
            # Extraemos P y Q netas (Generación - Carga)
            p_val = bus.P_net
            q_val = bus.Q_net
            
            # Imprimimos formateado en columnas
            print(f"{bus.id:<7} | {v_mag:<9.4f} | {v_ang_deg:<10.2f} | {p_val:<10.4f} | {q_val:<10.4f}")

    else:
        print("\n⚠️ EL SOLVER DIVERGIÓ O FALLÓ")
        print(f"Mensaje: {results.meta.message}")
        print(f"Iteraciones realizadas: {results.meta.iterations}")

    from pywerflow.plotting.plot_network import plot_power_flow_network
    import random
    network.export_buses
    network.to_excel(filepath="net300.xlsx", bus_columns=['id', 'type', 'base_kv', "v_kv", 'v_pu', 'theta_deg', 'p_pu', "p_mw", 'q_pu', "q_mvar", 'g_pu', 'b_pu'])
    plot_power_flow_network(network, node_size=200, font_size=8, layout_seed=random.randint(0,2**32))
 


if __name__ == "__main__":
    # Asegúrate de que el archivo exista en esta ruta
    casedir = r"C:\Users\javir\Desktop\TFG\TFG Sistema eléctrico\Código\PywerFlow\src\pywerflow\examples\ieee9\matpower_cases"
    
    
    
    case =   118

    match case:

        case 9:
            solve_case(
                case_path = casedir + r"\case9.m",
                tol = 1e-9,
                max_it = 10000,
                initial_guess = None
                )
        case 14:
            solve_case(
                case_path = casedir + r"\case14.m",
                tol = 1e-9,
                max_it = 10000,
                initial_guess = None
                )
        case 30:
            solve_case(
                case_path = casedir + r"\case30.m",
                tol = 1e-9,
                max_it = 10000,
                initial_guess = None
                )
        case 118:
            solve_case(
                case_path = casedir + r"\case118.m",
                tol = 1e-9,
                max_it = 10000,
                initial_guess = None
                )
        case 300:
            solve_case(
                case_path = casedir + r"\case300.m",
                tol = 1e-9,
                max_it = 10000,
                initial_guess = None
                )

