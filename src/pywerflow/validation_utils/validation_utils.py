from typing import Callable, Any


def validator(func: Callable):
    """
    Decorator that marks a method as a validator.

    This decorator does not modify the function's behavior; it merely attaches 
    an internal attribute (`__is_validator__`) to the function object. 
    This tag is later used by the `auto_validate` function to identify 
    and execute validation logic.
    """
    func.__is_validator__ = True
    return func



def auto_validate(instance) -> None:
    """
    Automatically executes all methods decorated with `@validator` for the given instance.

    This function implements a **Lazy Caching** strategy to optimize performance:
    
    1.  **First Run (Introspection):** When called for the first time on a class, 
        it scans the entire Method Resolution Order (MRO) to build a consolidated 
        list of validator methods. This list respects inheritance order (Base -> Child) 
        and definition order.
    2.  **Subsequent Runs (Cached):** The list is stored in the class attribute 
        `__cached_validators__`. Future instances of the same class skip the 
        introspection step and execute the cached list directly, achieving O(1) overhead.

    Args:
        instance: The object instance to validate (usually `self`).

    Raises:
        Any exception raised by the individual validator methods.
    """
    cls = type(instance)
    
    # ¿Ya tenemos la lista de validadores guardada en la CLASE?
    # Buscamos un atributo oculto en la clase (no en la instancia)
    validators_list = getattr(cls, "__cached_validators__", None)

    # Si NO existe (es la primera vez que instanciamos esta clase):
    if validators_list is None:
        validators_list = []
        
        # Hacemos el escaneo pesado (MRO) SOLO AHORA
        
        # Recorremos la jerarquía de clases al revés (Object -> Base -> Hijas.. )
        # Así las clases definidas por los padres se ejecutan antes (aunque hayan sido reescritas)
        for base in reversed(cls.__mro__):
            if base is object: # No nos interesa el caso base
                continue
            
            # Recorremos el diccionario de cada clase
            # En Python 3.6+, esto respeta el orden de inserción (escritura en el archivo).
            for name, value in base.__dict__.items():
                if (getattr(value, "__is_validator__", False) and 
                    name not in validators_list):
                    
                    validators_list.append(name)
        

        # Una vez obtenida la lista de metodos validadores la guardamos en la clase 
        # La próxima vez, 'getattr' lo encontrará a la primera y no habrá que hacer la busqueda
        setattr(cls, "__cached_validators__", validators_list)



    # Aquí llega tanto el primer objeto (después de la busqueda) 
    # como los siguientes (directamente del caché)
    for method_name in validators_list:
        getattr(instance, method_name)()





def validate_types(instance, type_map: dict[str, Any]) -> None:
    """
    Generic helper to validate attribute types at runtime.
    
    Args:
        instance: The object instance to check (usually 'self').
        type_map: A dictionary mapping attribute names to expected types.
                  Example: {'id': int, 'Q': str, 'ratio': (int, float)}
    
    Raises:
        TypeError: If an attribute has the wrong type.
        AttributeError: If an attribute name in the map does not exist in the instance.
    """
    # Obtengo el nombre de la clase del objeto que quiere usar este helper
    class_name = type(instance).__name__

    # Obtengo el nombre de la clase que quiere usar este helper
    for attr_name, expected_types in type_map.items():
        # Obtenemos el valor de cada atributo en esta instancia (fallará si el atributo no existe, lo cual es correcto)
        try:
            value = getattr(instance, attr_name)
        except AttributeError:
            raise AttributeError(f"Configuration Error: Attribute '{attr_name}' defined in validation map does not exist in class '{class_name}'.")

        # Comprobamos el tipo
        if not isinstance(value, expected_types):
            actual_type_name = type(value).__name__
            raise TypeError(
                f"Invalid Type for '{attr_name}' in {class_name}. "
                f"Expected type/s '{expected_types}', got '{actual_type_name}' (Value: {value})."
            )
        

def validate_ranges(instance: Any, range_map: dict[str, tuple[Any, Any, str]]) -> None:
    """
    Generic helper to validate attribute numeric ranges.
    
    Supports standard interval notation for bounds (bounds_str argument):
    - "[]" : Inclusive.           Min <= val <= Max
    - "()" : Exclusive.           Min <  val <  Max
    - "[)" : Inclusive Min, Exclusive Max.
    - "(]" : Exclusive Min, Inclusive Max.
    
    Use `None` in min or max to indicate no limit (infinity).
    
    Args:
        instance: The object instance.
        range_map: Dict mapping 'attribute_name' -> (min, max, bounds_str).
    
    Raises:
        ValueError: If value is out of range (while validation).
        AttributeError: If attribute is missing (class config error).
    """
    # Obtenemos el nombre de la clase
    class_name = type(instance).__name__

    # Recorremos los atributos a validar
    for attr_name, specs in range_map.items():
        try:
            val = getattr(instance, attr_name)
        except AttributeError:
             raise AttributeError(f"Config Error: Attribute '{attr_name}' not found in {class_name}.")

        # Integridad de la tupla de configuración (specs)
        if len(specs) != 3:
            raise ValueError(f"Config Error for '{attr_name}': Expected tuple (min, max, bounds_str), got {specs}.")

        # Buscamos los limites y su categoría. Dejo que falle si hay un IndexError
        min_limit, max_limit = specs[0], specs[1]
        bounds = specs[2] 

        # VALIDACION DE VERDAD

        try:
            # Limite inferior
            if min_limit is not None:
                if bounds[0] == '[': # Inclusive (>=)
                    if not (val >= min_limit):
                        raise ValueError(f"Value Error for '{attr_name}' in {class_name}. Got {val}, expected >= {min_limit}.")
                elif bounds[0] == '(': # Exclusive (>)
                    if not (val > min_limit):
                        raise ValueError(f"Value Error for '{attr_name}' in {class_name}. Got {val}, expected > {min_limit}.")
                else:
                    raise ValueError(f"Invalid bounds notation '{bounds}' for {attr_name}. Use '[]', '()', '[)', or '(]'.")

            # Límite SUPERIOR
            if max_limit is not None:
                if bounds[1] == ']': # Inclusive (<=)
                    if not (val <= max_limit):
                        raise ValueError(f"Value Error for '{attr_name}' in {class_name}. Got {val}, expected <= {max_limit}.")
                elif bounds[1] == ')':  # Exclusive (<)
                    if not (val < max_limit):
                        raise ValueError(f"Value Error for '{attr_name}' in {class_name}. Got {val}, expected < {max_limit}.")
                else: 
                    raise ValueError(f"Invalid bounds notation '{bounds}' for {attr_name}. Use '[]', '()', '[)', or '(]'.")
        except TypeError as e:
            raise TypeError(
                f"Comparison Error for '{attr_name}' in {class_name}. "
                f"Cannot compare value '{val}' (type {type(val).__name__}) "
                f"with limits ({min_limit}, {max_limit})."
            ) from e