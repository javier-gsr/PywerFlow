from pprint import pprint
from pywerflow.buses.input_buses import PQBus, PVBus, SlackBus
from pywerflow.branches.pfsolvable_branches import PiLine
from pywerflow.networks.pf_network import PowerFlowNetwork
Sb = 100 # MVA

buses = [

    SlackBus(
        id=1, 
        V=1.04, 
        theta=0),

    PVBus(
        id=2, 
        P=163/Sb, 
        V=1.025
        ),

    PVBus(
        id=3, 
        P=85/Sb, 
        V=1.025
        ),

    PQBus(
        id=4, 
        P=0, 
        Q=0
        ),

    PQBus(
        id=5, 
        P=-125/Sb, 
        Q=-50/Sb
        ),

    PQBus(
        id=6, 
        P=-90/Sb, 
        Q=-30/Sb
        ),

    PQBus(
        id=7, 
        P=0, 
        Q=0
        ),

    PQBus(
        id=8, 
        P=-100/Sb, 
        Q=-35/Sb
        ),

    PQBus(
        id=9, 
        P=0, 
        Q=0
        ),
]


branches = [

    PiLine(
        id=1, 
        bus1=1,
        bus2=4,
        R=0,
        X=0.0576,
        B=0,
        G=0,
    ),

    PiLine(
        id=2, 
        bus1=4,
        bus2=5,
        R=0.01,
        X=0.085,
        B=0.176,
        G=0,
    ),

    PiLine(
        id=3, 
        bus1=4,
        bus2=6,
        R=0.017,
        X=0.092,
        B=0.158,
        G=0,
    ),

    PiLine(
        id=4, 
        bus1=6,
        bus2=9,
        R=0.039,
        X=0.17,
        B=0.358,
        G=0,
    ),

    PiLine(
        id=5, 
        bus1=5,
        bus2=7,
        R=0.032,
        X=0.161,
        B=0.306,
        G=0,
    ),

    PiLine(
        id=6, 
        bus1=9,
        bus2=3,
        R=0,
        X=0.0586,
        B=0,
        G=0,
    ),

    PiLine(
        id=7, 
        bus1=7,
        bus2=2,
        R=0,
        X=0.0625,
        B=0,
        G=0,
    ),

    PiLine(
        id=8, 
        bus1=9,
        bus2=8,
        R=0.0119,
        X=0.1008,
        B=0.209,
        G=0,
    ),

    PiLine(
        id=9, 
        bus1=7,
        bus2=8,
        R=0.0085,
        X=0.072,
        B=0.149,
        G=0,
    ),
    
]




network = PowerFlowNetwork(buses, branches)
solver_metadata, solved_buses, solved_branches = network.gauss_seidel_solve_gemini()
pprint(solver_metadata)

for b in solved_buses:
    pprint(float(b.V))
    print()

print()

# for b in solved_branches:
#     pprint(b)
#     print()