
import os
import warnings
from pywerflow.buses.input_buses import PQBus, PVBus, SlackBus
from pywerflow.branches.pfsolvable_branches import PiLine
from pywerflow.networks.pfnetwork_builder import PFNetworkBuilder
from pywerflow.io import json_io

def test_json_io():
    print("Testing JSON I/O...")
    
    # 1. Create a simple network
    builder = PFNetworkBuilder()
    builder.set_base_mva(100.0)
    
    b1 = SlackBus(id=1, V=1.05, theta=0.0)
    b2 = PQBus(id=2, P=-0.5, Q=-0.1, V_guess=1.0)
    b3 = PVBus(id=3, P=0.4, V=1.02, theta_guess=0.0)
    
    l1 = PiLine(id=1, bus1=1, bus2=2, R=0.01, X=0.1, G=0.0, B=0.01)
    l2 = PiLine(id=2, bus1=2, bus2=3, R=0.01, X=0.1, G=0.0, B=0.01)
    
    builder.add_buses([b1, b2, b3])
    builder.add_branches([l1, l2])
    
    net = builder.build()
    print("Network built successfully.")

    # 2. Disable a bus to test the memory recovery logic
    print("Disabling Bus 3...")
    net.set_bus_status(3, active=False)
    
    # 3. Save to JSON
    json_path = "test_network.json"
    print(f"Saving to {json_path}...")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        net.to_json(json_path)
        if w:
            print(f"Warnings captured during save: {[str(warn.message) for warn in w]}")

    # 4. Load from JSON
    print(f"Loading from {json_path}...")
    builder2 = PFNetworkBuilder()
    builder2.load_json(json_path)
    net2 = builder2.build()
    
    # 5. Verify consistency
    print("Verifying loaded network...")
    
    # Check S_base
    assert net2.s_base == 100.0, f"S_base mismatch: {net2.s_base}"
    
    # Check Buses
    # Bus 3 should be back to its ORIGINAL PV definition, not the dummy PQ
    b3_loaded = net2.get_bus(3)
    assert isinstance(b3_loaded, PVBus), f"Bus 3 type mismatch. Expected PVBus, got {type(b3_loaded)}"
    assert b3_loaded.P == 0.4, f"Bus 3 P mismatch: {b3_loaded.P}"
    
    print("All checks passed!")
    
    # Clean up
    if os.path.exists(json_path):
        os.remove(json_path)

if __name__ == "__main__":
    test_json_io()
