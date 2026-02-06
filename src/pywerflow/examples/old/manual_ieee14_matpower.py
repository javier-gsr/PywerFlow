from pprint import pprint
from pywerflow.buses.input_buses import PQBus, PVBus, SlackBus
from pywerflow.branches.pfsolvable_branches import PiLine, SimpleTransformer
from pywerflow.networks.pf_network import PowerFlowNetwork

# Base del sistema: 100 MVA
# Datos extraídos de la tabla oficial IEEE 14-Bus CDF/MATPOWER

buses = [
    # --- SLACK BUS (1) ---
    # Gen: V=1.06, Angle=0
    # Load: 0
    SlackBus(
        id=1, 
        V=1.06, 
        theta=0.0
    ),

    # --- PV BUSES (Generators + Synchronous Condensers) ---
    # Nota: P inyectada = P_gen - P_load
    
    # Bus 2: P_gen=40, P_load=21.7 -> P_net = 18.3 MW = 0.183 pu
    PVBus(
        id=2, 
        P=0.183,  # (40 - 21.7) / 100
        V=1.045
    ),

    # Bus 3: P_gen=0, P_load=94.2 -> P_net = -94.2 MW = -0.942 pu
    PVBus(
        id=3, 
        P=-0.942, # (0 - 94.2) / 100
        V=1.01
    ),

    # Bus 6: P_gen=0, P_load=11.2 -> P_net = -11.2 MW = -0.112 pu
    PVBus(
        id=6, 
        P=-0.112, # (0 - 11.2) / 100
        V=1.07
    ),

    # Bus 8: P_gen=0, P_load=0 -> P_net = 0
    # (Compensador Síncrono Puro)
    PVBus(
        id=8, 
        P=0.0,
        V=1.09
    ),

    # --- PQ BUSES (Loads) ---
    # Nota: P, Q son Inyecciones.
    # P = -P_demand / 100
    # Q = -Q_demand / 100
    
    # Bus 4: Pd=47.8, Qd=-3.9 (¡Carga Capacitiva!)
    # Q_inj = -(-3.9) = +0.039
    PQBus(
        id=4, 
        P=-0.478, 
        Q=0.039
    ),

    # Bus 5: Pd=7.6, Qd=1.6
    PQBus(
        id=5, 
        P=-0.076, 
        Q=-0.016
    ),

    # Bus 7: Pd=0, Qd=0 (Nudo de paso)
    PQBus(
        id=7, 
        P=0.0, 
        Q=0.0
    ),

    # Bus 9: Pd=29.5, Qd=16.6, Bs=19 (Shunt)
    # IMPORTANTE: Bs=19 MVar -> B_shunt = 0.19 pu
    PQBus(
        id=9, 
        P=-0.295, 
        Q=-0.166,   # Consumo inductivo
        B_shunt=0.19 # Banco de condensadores
    ),

    # Bus 10: Pd=9.0, Qd=5.8
    PQBus(
        id=10, 
        P=-0.09, 
        Q=-0.058
    ),

    # Bus 11: Pd=3.5, Qd=1.8
    PQBus(
        id=11, 
        P=-0.035, 
        Q=-0.018
    ),

    # Bus 12: Pd=6.1, Qd=1.6
    PQBus(
        id=12, 
        P=-0.061, 
        Q=-0.016
    ),

    # Bus 13: Pd=13.5, Qd=5.8
    PQBus(
        id=13, 
        P=-0.135, 
        Q=-0.058
    ),

    # Bus 14: Pd=14.9, Qd=5.0
    PQBus(
        id=14, 
        P=-0.149, 
        Q=-0.05
    ),
]








# Datos oficiales IEEE 14-Bus (Common Data Format / MATPOWER)
branches = [
    # --- TRANSMISSION LINES (Pi Model) ---
    # Columna 5 (b) es la Susceptancia Total de la línea (Total Line Charging).
    
    PiLine(
        id=1, bus1=1, bus2=2, 
        R=0.01938, X=0.05917, B=0.0528, G=0
    ),
    PiLine(
        id=2, bus1=1, bus2=5, 
        R=0.05403, X=0.22304, B=0.0492, G=0
    ),
    PiLine(
        id=3, bus1=2, bus2=3, 
        R=0.04699, X=0.19797, B=0.0438, G=0
    ),
    PiLine(
        id=4, bus1=2, bus2=4, 
        R=0.05811, X=0.17632, B=0.0340, G=0
    ),
    PiLine(
        id=5, bus1=2, bus2=5, 
        R=0.05695, X=0.17388, B=0.0346, G=0
    ),
    PiLine(
        id=6, bus1=3, bus2=4, 
        R=0.06701, X=0.17103, B=0.0128, G=0
    ),
    PiLine(
        id=7, bus1=4, bus2=5, 
        R=0.01335, X=0.04211, B=0.0, G=0
    ),
    # Rama 8 es un Trafo (ver abajo)
    # Rama 9 es un Trafo (ver abajo)
    # Rama 10 es un Trafo (ver abajo)
    
    PiLine(
        id=11, bus1=6, bus2=11, 
        R=0.09498, X=0.19890, B=0.0, G=0
    ),
    PiLine(
        id=12, bus1=6, bus2=12, 
        R=0.12291, X=0.25581, B=0.0, G=0
    ),
    PiLine(
        id=13, bus1=6, bus2=13, 
        R=0.06615, X=0.13027, B=0.0, G=0
    ),
    PiLine(
        id=14, bus1=7, bus2=8, 
        R=0.0, X=0.17615, B=0.0, G=0  # R=0 (Inductancia pura)
    ),
    PiLine(
        id=15, bus1=7, bus2=9, 
        R=0.0, X=0.11001, B=0.0, G=0  # R=0
    ),
    PiLine(
        id=16, bus1=9, bus2=10, 
        R=0.03181, X=0.08450, B=0.0, G=0
    ),
    PiLine(
        id=17, bus1=9, bus2=14, 
        R=0.12711, X=0.27038, B=0.0, G=0
    ),
    PiLine(
        id=18, bus1=10, bus2=11, 
        R=0.08205, X=0.19207, B=0.0, G=0
    ),
    PiLine(
        id=19, bus1=12, bus2=13, 
        R=0.22092, X=0.19988, B=0.0, G=0
    ),
    PiLine(
        id=20, bus1=13, bus2=14, 
        R=0.17093, X=0.34802, B=0.0, G=0
    ),

    # --- TRANSFORMERS ---
    # Detectados por tener columna 'tap' != 0
    # Nota: Rcc suele ser 0 en estos modelos estándar.
    
    SimpleTransformer(
        id=8, bus1=4, bus2=7, 
        Rcc=0.0, Xcc=0.20912, 
        tap_ratio=0.978, shift=0.0
    ),
    SimpleTransformer(
        id=9, bus1=4, bus2=9, 
        Rcc=0.0, Xcc=0.55618, 
        tap_ratio=0.969, shift=0.0
    ),
    SimpleTransformer(
        id=10, bus1=5, bus2=6, 
        Rcc=0.0, Xcc=0.25202, 
        tap_ratio=0.932, shift=0.0
    ),
]





network = PowerFlowNetwork(buses, branches)
solver_metadata, solved_buses, solved_branches = network.gauss_seidel_solve_gemini()

import math

def print_bus_results(solved_buses):
    """
    Imprime una tabla formateada estilo MATPOWER a partir de una lista de objetos SolvedBus.
    """
    # Ordenamos por ID para asegurar que la tabla salga bonita (1, 2, 3...)
    # (Asumiendo que 'solved_buses' es la lista que te devolvió el solver)
    sorted_buses = sorted(solved_buses, key=lambda b: b.id)

    print("\n--- RESULTADOS PYWERFLOW (Estilo MATPOWER) ---")
    
    # Encabezado con anchos fijos
    # :<N  -> Alineado a la izquierda, N espacios
    # :>N  -> Alineado a la derecha, N espacios
    header = f"{'ID':<5} {'V (pu)':<10} {'Th (deg)':<12} {'Th (rad)':<12} {'P_net(pu)':<12} {'Q_net(pu)':<12}"
    print(header)
    print("-" * 66)

    for bus in sorted_buses:
        # Conversión al vuelo: Radianes -> Grados
        theta_deg = math.degrees(bus.theta)
        
        # Fila formateada
        # .4f -> 4 decimales flotantes
        print(f"{bus.id:<5} "
              f"{bus.V:<10.4f} "
              f"{theta_deg:<12.4f} "
              f"{bus.theta:<12.4f} "
              f"{bus.P_net:<12.4f} "
              f"{bus.Q_net:<12.4f}")

    print("-" * 66)


pprint(solver_metadata)
print()

from pywerflow.buses.bus_types import BusTypes
for b in solved_buses:
    if b.original_type is BusTypes.SLACK:
        pass
        print(f"Slack id {b.id} -> P={b.P_net}   Q={b.Q_net}")

    if b.original_type is BusTypes.PQ:
        print(f"PQ id {b.id} -> V={b.V}   theta={b.theta}")
    if b.original_type is BusTypes.PV:
        print(f"PV id {b.id} -> Q={b.Q_net}   theta={b.theta}")
        pass


print_bus_results(solved_buses)