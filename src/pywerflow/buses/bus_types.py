from enum import Enum

class BusTypes(Enum):
    """
    Enumeration representing the type of a bus in the power flow problem.
    """
    SLACK = 3
    """Reference bus (Swing bus). Absorbs system losses."""
    
    PV = 2
    """Generator bus. P and V are controlled."""
    
    PQ = 1
    """Load bus. P and Q are fixed."""



