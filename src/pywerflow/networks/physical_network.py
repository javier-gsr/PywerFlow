from pywerflow.networks.base_network import BaseNetwork
from pywerflow.utils.validation_utils import auto_validate, validator, validate_ranges, validate_types
from pywerflow.branches.pfsolvable_branches import SimpleTransformer

class PhysicalNetwork(BaseNetwork):
    """
    Red definida con magnitudes físicas absolutas. 
    Tiene una lista de nudos y una lista de buses
    Tiene una estructura interna con sus propios indices
    """
    # mismo init que la base ¿? si

    @validator
    def _validate_non_pu_transformers(self):
        for id, branch in self._branches.items():
            if isinstance(branch, SimpleTransformer): # La red fisica no permite trafos pu
                raise TypeError(
                    f"Consistency Error: 'PhysicalNetwork' expects components defined in absolute physical units. "
                    f"Branch ID '{id}' is of type '{type(branch).__name__}' "
                    f"Please use 'PhysicalTransformer' to maintain network consistency."
                )



"""
¿QUE NARICES NECESITO AHORA?

Necesito que esta clase maneje las "redes fisicas". Debe ser capaz de convertirse en una red PU que sea resoluble. 

"""