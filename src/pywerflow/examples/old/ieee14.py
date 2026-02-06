from pprint import pprint
from pywerflow.buses.input_buses import PQBus, PVBus, SlackBus
from pywerflow.branches.pfsolvable_branches import PiLine, SimpleTransformer
from pywerflow.networks.pf_network import PowerFlowNetwork

buses = [

    SlackBus(
        id=1, 
        V=1.06, 
        theta=0
        ),

    PVBus(
        id=2, 
        P=0.4-0.217,
        V=1.045,
        ),

    PVBus(
        id=3, 
        P=-0.942,
        V=1.01,
        ),

    PQBus(
        id=4, 
        P=-0.478,
        Q=0,
        ),

    PQBus(
        id=5, 
        P=-0.076,
        Q=-0.016,
        ),

    PVBus(
        id=6, 
        P=-0.112,
        V=1.07,
        ),

    PQBus(
        id=7, 
        P=0,
        Q=0,
        ),

    PVBus(
        id=8, 
        P=0,
        V=1.09,
        ),

    PQBus(
        id=9, 
        P=-0.295,
        Q=-0.166,
        ),

    PQBus(
        id=10, 
        P=-0.09,
        Q=-0.058,
        ),

    PQBus(
        id=11, 
        P=-0.035,
        Q=-0.018,
        ),

    PQBus(
        id=12, 
        P=-0.061,
        Q=-0.016,
        ),

    PQBus(
        id=13, 
        P=-0.135,
        Q=-0.058,
        ),

    PQBus(
        id=14, 
        P=-0.149,
        Q=-0.05,
        ),

]


branches = [

    PiLine(
        id=1, 
        bus1=1,
        bus2=2,
        R=0.01938,
        X=0.05917,
        B=2*0.0264,
        G=0,
    ),

    PiLine(
        id=2, 
        bus1=1,
        bus2=5,
        R=0.05403,
        X=0.22304,
        B=2*0.0246,
        G=0,
    ),

    PiLine(
        id=3, 
        bus1=2,
        bus2=3,
        R=0.04699,
        X=0.19797,
        B=2*0.0219,
        G=0,
    ),

    PiLine(
        id=4, 
        bus1=2,
        bus2=4,
        R=0.05811,
        X=0.17632,
        B=2*0.017,
        G=0,
    ),

    PiLine(
        id=5, 
        bus1=2,
        bus2=5,
        R=0.05695,
        X=0.17388,
        B=2*0.0173,
        G=0,
    ),

    PiLine(
        id=6, 
        bus1=3,
        bus2=4,
        R=0.06701,
        X=0.17103,
        B=2*0.0064,
        G=0,
    ),

    PiLine(
        id=7, 
        bus1=4,
        bus2=5,
        R=0.01335,
        X=0.04211,
        B=0,
        G=0,
    ),

    SimpleTransformer(
        id=8, 
        bus1=4,
        bus2=7,    
        Rcc=0,
        Xcc=0.20912,
        tap_ratio=0.978,
        shift=0,
    ),

    SimpleTransformer(
        id=9, 
        bus1=4,
        bus2=9,    
        Rcc=0,
        Xcc=0.55618,
        tap_ratio=0.969,
        shift=0,
    ),

    SimpleTransformer(
        id=10, 
        bus1=5,
        bus2=6,    
        Rcc=0,
        Xcc=0.25202,
        tap_ratio=0.932,
        shift=0,
    ),

    PiLine(
        id=11, 
        bus1=6,
        bus2=11,
        R=0.09498,
        X=0.1989,
        B=0,
        G=0,
    ),

    PiLine(
        id=12, 
        bus1=6,
        bus2=12,
        R=0.12291,
        X=0.25581,
        B=0,
        G=0,
    ),

    PiLine(
        id=13, 
        bus1=6,
        bus2=13,
        R=0.06615,
        X=0.13027,
        B=0,
        G=0,
    ),

    PiLine(
        id=14, 
        bus1=7,
        bus2=8,
        R=0,
        X=0.17615,
        B=0,
        G=0,
    ),

    PiLine(
        id=15, 
        bus1=7,
        bus2=9,
        R=0,
        X=0.11001,
        B=0,
        G=0,
    ),

    PiLine(
        id=16, 
        bus1=9,
        bus2=10,
        R=0.03181,
        X=0.0845,
        B=0,
        G=0,
    ),

    PiLine(
        id=17, 
        bus1=9,
        bus2=14,
        R=0.12711,
        X=0.27038,
        B=0,
        G=0,
    ),

    PiLine(
        id=18, 
        bus1=10,
        bus2=11,
        R=0.08205,
        X=0.19207,
        B=0,
        G=0,
    ),

    PiLine(
        id=19, 
        bus1=12,
        bus2=13,
        R=0.22092,
        X=0.19988,
        B=0,
        G=0,
    ),

    PiLine(
        id=20, 
        bus1=13,
        bus2=14,
        R=0.17093,
        X=0.34802,
        B=0,
        G=0,
    ),

]
# from dataclasses import replace

# for i in range(len(branches)):
#     branch = branches[i]

#     if hasattr(branch, 'B') and hasattr(branch, 'G'):       
#         current_b = branch.B
#         new_branch = replace(branch, B=2*current_b)
#         branches[i] = new_branch


def print_bus_table(bus_list):
    """
    Imprime una tabla formateada con los datos de los buses,
    aplicando valores por defecto si el atributo no existe.
    """
    
    # Encabezado de la tabla con formato de ancho fijo
    # < : alineado a la izquierda
    # > : alineado a la derecha
    header = f"{'ID':<5} {'TYPE':<10} {'V (pu)':>10} {'Theta (rad)':>12} {'P (pu)':>10} {'Q (pu)':>10}"
    print("-" * 65)
    print(header)
    print("-" * 65)

    for bus in bus_list:
        # 1. Determinar el Tipo (Nombre de la clase)
        bus_type = bus.__class__.__name__.replace("Bus", "").upper()
        
        # 2. Obtener valores usando getattr con tus valores por defecto
        # Si no tiene 'V', usa 1.0
        v = getattr(bus, 'V', 1.0)
        
        # Si no tiene 'theta', usa 0.0
        theta = getattr(bus, 'theta', 0.0)
        
        # Si no tiene 'P', usa 0.0
        p = getattr(bus, 'P', 0.0)
        
        # Si no tiene 'Q', usa 0.0
        q = getattr(bus, 'Q', 0.0)

        # 3. Imprimir fila formateada
        # .4f significa 4 decimales flotantes
        print(f"{bus.id:<5} {bus_type:<10} {v:>10.4f} {theta:>12.4f} {p:>10.4f} {q:>10.4f}")

    print("-" * 65)


network = PowerFlowNetwork(buses, branches)
solver_metadata, solved_buses, solved_branches = network.gauss_seidel_solve_gemini()




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



# for b in solved_branches:
#     print(b.Q_loss * 100)
