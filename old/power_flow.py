from read_files_utils import read_power_network_excel, verify_power_network, export_ybus_to_csv
from plot_utils import plot_power_network, plot_pu_power_network,plot_solved_power_network, to_pretty_table
import logging
import math as m
from copy import deepcopy
from cmath import phase, rect
import sys
from warnings import warn
import numpy as np
from scipy.optimize import fsolve, newton, root
from prettytable import PrettyTable


LOGGER = logging.getLogger(__name__ )


def config_logging():
    # --- 1. CONFIGURACIÓN DEL LOGGER ---
    # Esta es la parte que puedes poner al inicio de tu script principal
    # o en un módulo de configuración.

    # Define el nombre de tu LOGGER específico

    # Establece el nivel MÍNIMO que el LOGGER procesará.
    # .DEBUG es el nivel más bajo, por lo que capturará TODO.

    # Evita que los logs se envíen también al LOGGER "raíz" (root)
    # Esto previene mensajes duplicados si el root ya tiene un handler.
    
    
    
    logging.propagate = False

    # Crea un formato de log estándar
    log_format = '%(funcName)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # --- 2. CONFIGURACIÓN DEL HANDLER DE CONSOLA (StreamHandler) ---

    # sys.stdout asegura que se imprima en la salida estándar
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # Muestra todos los niveles en consola
    console_handler.setFormatter(formatter)


    # --- FILTRO PARA EL FILE HANDLER, SOLO QUIERO QUE SE MUESTREN LOS MENSAJES DE ESTE LOGGER ----
    only_this_logger_filter = logging.Filter(name=LOGGER.name)

    # --- 3. CONFIGURACIÓN DEL HANDLER DE FICHERO (FileHandler) ---

    # mode='w' (write) sobrescribe el log cada vez que se ejecuta el script.
    # (Usa mode='a' (append) si quieres mantener un historial entre ejecuciones)
    file_handler = logging.FileHandler('tfg_flujo.log', mode='w', encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # Escribe todos los niveles en el fichero
    file_handler.setFormatter(formatter)
    file_handler.addFilter(only_this_logger_filter)

    handlers = [
        # console_handler, 
        file_handler,
        ]
    logging.basicConfig(level=logging.DEBUG, handlers=handlers)


def normalize_angle(angle):
  """
  Normaliza un ángulo en radianes al rango [-pi, +pi) usando módulo.
  """
  return (angle + m.pi) % (2*m.pi) - m.pi


def ang_distance(alpha, beta):
  """
  Calcula la distancia más corta (absoluta) entre dos ángulos
   alpha y beta en radianes.
  """
  pi2 = m.pi*2

  raw_distance = abs(alpha%pi2 - beta%pi2)
  distance = raw_distance if raw_distance<=m.pi else pi2-raw_distance

  return distance


def network_data_to_pu_model(network_data: dict[str, list[dict[str, any]]], V_base0 = None, S_base = None):
    """
    Convierte la informacion de una red electrica en terminos absolutos
    en una red eléctrica en p.u. sin transformadores.
    """

    # Error relativo maximo para la tensión base en caso de discrepancia:
    max_V_error = 0.001
    max_theta_error = 0.001

    # ENSAMBLAR ESTRUCTURAS DE DATOS UTILES:


    # Para cada bus existe una lista de otros buses al os cuales está conectado 
    buses_to_destinations = {bus["id"]:[] for bus in network_data["buses"]}
    for line in network_data["lines"]:
        bus1 = line["bus1"]
        bus2 = line["bus2"]
        buses_to_destinations[bus1].append( ( bus2, line ) )
        buses_to_destinations[bus2].append( ( bus1, line ) )

    
    # Eleccion de S base
    if S_base is None:
        pv_buses_s = [abs(bus["P"]) for bus in network_data["buses"] if bus["type"]=="PV"]
        pq_buses_s = [m.sqrt(bus["P"]**2+bus["Q"]**2) for bus in network_data["buses"] if bus["type"]=="PQ"]
        S_base = sum(pq_buses_s+pv_buses_s) / (len(pv_buses_s)+len(pq_buses_s))

    # Eleccion de secciones y sus V bases
    slack_bus = [bus for bus in network_data["buses"] if bus["type"]=="Slack"][0]

    # Desde el slack puedo recorrer las lineas para ir cruzando toda la red

    buses_in_sections = { 1:[slack_bus["id"]] }  # Section : list[Bus ID]
    buses_to_sections = { slack_bus["id"]:1 }    # Bus ID : Section
    if V_base0 is None:
        sections_to_Vbase = { 1:slack_bus["V"] }
    else:
        sections_to_Vbase = { 1:V_base0}

    
    sections_to_theta_base = { 1:slack_bus["theta"] }
    
    same_sections = [] # Tuplas de pares (section, section) que se han detectado que son iguales

    new_origins = list(buses_to_sections.items())  # Tuplas Bus ID, Section
    origins = True

    explored = [slack_bus["id"]] # Nudos ya explorados ()

    LOGGER.debug(f"Comenzando recorrido por la red...")

    while origins:

        origins = new_origins  # Origenes recogidos de la ultima iteracion (se van a usar ahora)
        new_origins = []       # Origenes que se van a rellenar en la proxima iteracion

        for orig, section in origins:
            destinations = buses_to_destinations[orig]
            LOGGER.debug(f"Origen: {orig}. Da lugar a destinos: {[dest[0] for dest in destinations]}")
            for dest, line in destinations:
                LOGGER.debug(f"Recorriendo desde origen {orig} a destino {dest}")
                
                if dest in explored:
                    LOGGER.debug(f"Destino {dest} previamente explorado.")

                    if line["has_T"]:  # Ya explorada y ES un trafo 
                        LOGGER.debug(f"Línea {line["id"]} es un trafo.")
                        # Ya tiene seccion y valores base asignados
                        dest_section = buses_to_sections[dest]
                        # Valores base del origen (de la seccion de origen)
                        V_base = sections_to_Vbase[section]    
                        theta_base = sections_to_theta_base[section]
                        # Valores esperados
                        expected_V_base_dest = V_base*abs(line["T-rt"]) if line["bus2"]==orig else V_base/abs(line["T-rt"]) 
                        expected_theta_base_dest = normalize_angle(theta_base+phase(line["T-rt"]) if line["bus2"]==orig else theta_base-phase(line["T-rt"]))  
                        # Hago verificaciones
                        if dest_section == buses_to_sections[orig]:
                            LOGGER.error(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su seccion {section} es la misma que la del origen {orig}")
                            raise RuntimeError(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su seccion {section} es la misma que la del origen {orig}")
                        if expected_V_base_dest != sections_to_Vbase[dest_section]:
                            LOGGER.warning(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su tension base ({sections_to_Vbase[dest_section]}) no coincide con la esperada ({expected_V_base_dest}). Origen: {orig}")
                            warn(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su tension base ({sections_to_Vbase[dest_section]}) no coincide con la esperada ({expected_V_base_dest}). Origen: {orig}")
                            V_relative_error = (expected_V_base_dest - sections_to_Vbase[dest_section]) / (expected_V_base_dest)
                            if max_V_error < V_relative_error:
                                raise RuntimeError(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su tension base ({sections_to_Vbase[dest_section]}) no coincide con la esperada ({expected_V_base_dest}). Origen: {orig}")  
                        
                        if expected_theta_base_dest != sections_to_theta_base[dest_section]:
                            LOGGER.warning(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su theta base ({sections_to_theta_base[dest_section]}) no coincide con la esperada ({expected_theta_base_dest}). Origen: {orig}")
                            warn(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su theta base ({sections_to_theta_base[dest_section]}) no coincide con la esperada ({expected_theta_base_dest}). Origen: {orig}")
                            theta_error = ang_distance(expected_theta_base_dest, sections_to_theta_base[dest_section])
                            if max_theta_error < theta_error:
                                raise RuntimeError(f"Se ha encontrado un destino {dest} previamente explorado atravesando un trafo y su theta base ({sections_to_theta_base[dest_section]}) no coincide con la esperada ({expected_theta_base_dest}). Origen: {orig}")  
                        # ESTE BUSCADOR MUERE AQUI

                    else:  # Ya explorada y NO ES un trafo 
                        LOGGER.debug(f"Línea {line["id"]} no un trafo.")
                        dest_section = buses_to_sections[dest]
                        if dest_section!=section:   # Compruebo si NO está en mi misma seccion
                            # Si NO ESTÁ. Entonces me apunto que estas 2 secciones en realidad son la misma
                            same_sections.append( (dest_section,section) )
                            LOGGER.debug(f"Otro buscador asignó una sección distinta a este bus: {dest_section}. Mientras que la sección del bus buscador: {section}")
                            # ESTE BUSCADOR MUERE AQUI
                            # TODO: VERIFICAR (AL FINAL DE LA BUSQUEDA) POR SEGURIDAD QUE TODAS LAS SECCIONES QUE "SON IGUALES" SEGUN ESTA LISTA TAMBIEN TIENEN MISMOS VBASE Y THETABASE

                        # Si sí está en mi misma sección simplemente no hago nada, este buscador muere aqui
                    

                else:
                    explored.append(dest)
                    LOGGER.debug(f"Destino {dest} explorado por primera vez.")
                    
                    if line["has_T"]: # Nunca explorada y ES un trafo
                        LOGGER.debug(f"Línea {line["id"]} es un trafo.")
                        # Creo una nueva seccion
                        new_section = max(buses_in_sections.keys())+1 # Creo una nueva seccion
                        buses_in_sections[new_section] = [dest]   # Añado a la nueva seccion
                        buses_to_sections[dest] = new_section     # Lo apunto como que esa es su seccion
                        # Valores base del origen (de la seccion de origen)
                        V_base = sections_to_Vbase[section]    
                        theta_base = sections_to_theta_base[section]
                        # Asignacion de valores para la nueva sección.
                        sections_to_Vbase[new_section] = V_base*abs(line["T-rt"]) if line["bus2"]==orig else V_base/abs(line["T-rt"])  # PORQUE |rt| = V_base1/V_base2
                        sections_to_theta_base[new_section] = normalize_angle(theta_base+phase(line["T-rt"]) if line["bus2"]==orig else theta_base-phase(line["T-rt"])) # PORQUE phase(rt) = theta_base1-theta_base2

                        new_origins.append((dest,new_section)) # Nuevo origen para la siguiente generacion de buscadores
                        LOGGER.debug(f"Creada nueva sección {new_section} y añadido el destino {dest}. Con valores base: V={sections_to_Vbase[new_section]}, theta={sections_to_theta_base[new_section]}")



                    else: # Nunca explorada y NO ES un trafo
                        LOGGER.debug(f"Línea {line["id"]} no es un trafo.")
                        buses_in_sections[section].append(dest) # Está en la misma seccion que yo y lo añado
                        buses_to_sections[dest] = section       # Apunto que esta es su seccion
                        new_origins.append((dest, section))     # Nuevo origen para la siguiente generacion de buscadores
                        LOGGER.debug(f"Añadido el destino {dest} a la sección {section}")

            LOGGER.debug(f"Nuevos destinos: {[org[0] for org in new_origins]}")
            LOGGER.debug(f"--------------------------------------------------------------------------------------------------------------------------------------")
        LOGGER.debug(f"--------------------------------------------------------------------------------------------------------------------------------------")


    # ENSAMBLAJE DE SECCIONES DEFINITIVAS
    sections_to_data = { sec: {"buses": buses, "V_base": sections_to_Vbase[sec], "theta_base": sections_to_theta_base[sec]} for sec, buses in buses_in_sections.items() }


    sections_str = ""
    for section, data in sections_to_data.items():
            theta_base = data["theta_base"]
            V_base = data["V_base"]
            buses = data["buses"]

            sections_str += (f"""Seccion {section}:
        - buses: {buses}
        - V_base: {V_base}
        - theta_base: {theta_base}
""")
            
    LOGGER.debug(f"Secciones obtenidas tras la busqueda:\n{sections_str}")
        
            
    LOGGER.debug(f"Comenzando proceso de agrupar secciones catalogadas como iguales...")
    LOGGER.debug(f"Pares de secciones catalogadas como iguales: {same_sections}")

    equal_sections_list = []  # Listas de sets. Cada set contiene IDs de secciones iguales entre ellas
    section_to_its_index = {}  # Diccionario  ID_seccion: index que le corresponde en la lista anterior 
    for sec1, sec2 in same_sections:
        if sec1 in section_to_its_index:
            index = section_to_its_index[sec1]
        elif sec2 in section_to_its_index:
            index = section_to_its_index[sec2] # ANTES AQUI PONIA SEC1 tambien -> Solved 17/11/2025
        else:
            # Se crea un nuevo set
            index = len(equal_sections_list)
            equal_sections_list.append( set() ) 

        equal_sections_list[index].add(sec1)
        equal_sections_list[index].add(sec2)
        section_to_its_index[sec1] = index
        section_to_its_index[sec2] = index

    LOGGER.debug(f"Secciones catalogadas como iguales agrupadas: {equal_sections_list}")
    LOGGER.debug(f"Comenzando agrupación de los buses con secciones catalogadas como iguales a una sola seccion unificada...")


    for equivalent_sections in equal_sections_list:  # Recorro cada set en la lista de sets [ set_secciones_iguales1 ,  set_secciones_iguales2 , ... ]
        LOGGER.debug(f"Agrupación de secciones {equivalent_sections}:")
        unified_section = min(equivalent_sections)  # Cojo la seccion con menor ID
        LOGGER.debug(f"   Las secciones {equivalent_sections} se agruparán en una sola: Sección {unified_section}")
        equivalent_sections.remove(unified_section) # Elimino esa sección del set
        for moving_sec in equivalent_sections:       # Recorro cada seccion en cada set {seccion2, seccion3, ...} habiendo eliminado antes la menor de ellas: seccion1
            LOGGER.debug(f"   Comenzando migración de sección {moving_sec} a sección {unified_section}")
            unified_data = sections_to_data[unified_section]
            moving_data = sections_to_data[moving_sec]
            del sections_to_data[moving_sec]
            # Verificaciones
            if unified_data["V_base"] != moving_data["V_base"]:
                warn(f"Se están fusionando 2 secciones: {(unified_section, moving_sec)}. Sus V_base no coinciden: {(unified_data["V_base"], moving_data["V_base"])}")
                LOGGER.warning(f"Se están fusionando 2 secciones: {(unified_section, moving_sec)}. Sus V_base no coinciden: {(unified_data["V_base"], moving_data["V_base"])}")
                V_relative_error = abs(unified_data["V_base"] - moving_data["V_base"]) / (unified_data["V_base"])
                if max_V_error < V_relative_error:
                    raise RuntimeError(f"Se están fusionando 2 secciones: {(unified_section, moving_sec)}. Sus V_base no coinciden: {(unified_data["V_base"], moving_data["V_base"])}")
                        
            if unified_data["theta_base"] != moving_data["theta_base"]:
                warn(f"Se están fusionando 2 secciones: {(unified_section, moving_sec)}. Sus theta_base no coinciden: {(unified_data["theta_base"], moving_data["theta_base"])}")
                LOGGER.warning(f"Se están fusionando 2 secciones: {(unified_section, moving_sec)}. Sus theta_base no coinciden: {(unified_data["theta_base"], moving_data["theta_base"])}")
                theta_error = ang_distance(unified_data["theta_base"], moving_data["theta_base"])
                if max_theta_error < theta_error:
                    raise RuntimeError(f"Se están fusionando 2 secciones: {(unified_section, moving_sec)}. Sus theta_base no coinciden: {(unified_data["theta_base"], moving_data["theta_base"])}")  

            LOGGER.debug(f"     - Verificaciones pasadas")
            # Añado los buses de una (la seccion borrada) a la otra (la seccion donde se unifica)
            unified_data["buses"] += moving_data["buses"]
            LOGGER.debug(f"     - Datos migrados a la sección {unified_section}")

    sections_str = ""
    for section, data in sections_to_data.items():
            theta_base = data["theta_base"]
            V_base = data["V_base"]
            buses = data["buses"]

            sections_str += (f"""Seccion {section}:
        - buses: {buses}
        - V_base: {V_base}
        - theta_base: {theta_base}
""")
            
    LOGGER.debug(f"Secciones obtenidas tras la agrupación:\n{sections_str}")

    LOGGER.debug(f"Ensamblando diccionario final de datos de secciones. Convirtiendo las magnitudes físicas de cada bus a 'por unidad' eligiendo las bases según su sección.")

    sections_data_list = []
    buses_dict = {bus_data["id"]:deepcopy(bus_data) for bus_data in network_data["buses"]}
    lines_dict = {line_data["id"]:deepcopy(line_data) for line_data in network_data["lines"]}
    
    for new_sec_index, sec_data in enumerate(sections_to_data.values()):
        
        LOGGER.debug(f"  Recorriendo sección {new_sec_index}. Calculando el resto de sus valores base...")

        sec_data["Z_base"] = sec_data["V_base"]**2 / S_base
        sec_data["Y_base"] = 1/sec_data["Z_base"]
        sec_data["I_base"] = S_base / sec_data["V_base"]
        sec_data["S_base"] = S_base
        sec_data["id"] = new_sec_index
        sections_data_list.append(sec_data)

        LOGGER.debug(f"  Datos de la seccion {new_sec_index} procesados y añadidos con éxito.")
        LOGGER.debug(f"  Analizando buses de esta sección y convirtiendo sus magnitudes a p.u...")

        for bus_id in sec_data["buses"]:
            bus_data = buses_dict[bus_id]
            bus_data["section"] = new_sec_index
            match bus_data["type"]:
                case "PV":
                    bus_data["P"] = bus_data["P"] / sec_data["S_base"]
                    bus_data["V"] = bus_data["V"] / sec_data["V_base"]
                case "PQ":
                    bus_data["P"] = bus_data["P"] / sec_data["S_base"]
                    bus_data["Q"] = bus_data["Q"] / sec_data["S_base"]
                case "Slack":
                    bus_data["theta"] = bus_data["theta"] - sec_data["theta_base"]
                    bus_data["V"] = bus_data["V"] / sec_data["V_base"]
                case _:
                    raise RuntimeError(f"Se ha encontrado un bus ({bus_id}) cuyo tipo ({bus_data["type"]}) es invalido")
                
            if bus_data.get("theta0") is not None:
                bus_data["theta0"] = bus_data["theta0"] - sec_data["theta_base"]
            if bus_data.get("V0") is not None:
                bus_data["V0"] = bus_data["V0"] / sec_data["V_base"]


            LOGGER.debug(f"    Conversión a p.u. completada para el bus {bus_data["id"]}. Conversiones de valores iniciales (opcional) efectuadas: theta0: {bool(bus_data.get("theta0") is not None)} | V0: {bool(bus_data.get("V0") is not None)}")


    for line_id in lines_dict:
        line_data = lines_dict[line_id]

        if line_data["has_T"]:  # Esta linea divide 2 secciones (es un trafo)
            
            if line_data["Z"] or line_data["Y"]:
                raise RuntimeError("Se ha analizado una linea con trafo que posee valores Z o Y.")

            pseudo_line_section = buses_dict[line_data["bus1"]]["section"]
            line_data["Z"] = line_data["T-Zcc"] / sections_data_list[pseudo_line_section]["Z_base"]
            line_data["Y"] = 0 + 0j

            line_data["section"] = pseudo_line_section # Le agrego una key con su "pseudo-seccion", en realidad esta linea divide 2 secciones... peeero bueno podemos decir que "pertenece" o "su impedancia fue medida" desde el devanado primario 

            # Este trafo ha sido convertido en una linea Pi como cualquier otra :)
            # Las claves has_T, T_rt y T-Zcc se quedan como eco del pasado, PERO AQUI YA NO HAY UN TRAFO REALMENTE -> Se ha eliminado gracias al modelo pu


        else: # Los 2 buses de esta linea están en la misma seccion (es una linea PI)
            bus1_id = line_data["bus1"]
            bus1_data = buses_dict[bus1_id]
            line_section = bus1_data["section"]
            line_section_data = sections_data_list[line_section]

            line_data["Z"] = line_data["Z"] / line_section_data["Z_base"]
            line_data["Y"] = line_data["Y"] / line_section_data["Y_base"]

            line_data["section"] = line_section # Le agrego una key con su seccion 

            if line_data["T-Zcc"] or line_data["T-rt"]:
                raise RuntimeError("Se ha analizado una linea SIN trafo (linea PI) que posee valores T-Zcc o T-rt")



    # Ahora section es una lista donde LA POSICION en la lista es el index de esa section
    # Ahora buses y lines son diccionarios id: data   donde cada data sigue conteniendo la id
    # En el caso de los buses, su data contiene ahora la seccion a la que pertenece
    # mas cosas....

    return {"buses":buses_dict, "lines":lines_dict, "sections": sections_data_list, "S_base": S_base}


def get_admitance_matrix(network_pu_data):
    buses = network_pu_data["buses"]
    lines = network_pu_data["lines"]
    N = len(buses)

    
    bus_ids_sorted = sorted(list(buses.keys()), key=int)


    bus_to_idex_in_Ymat = {bus_id: i for i, bus_id in enumerate(bus_ids_sorted)}
    Y_matrix = np.zeros((N, N), dtype=complex)


    for line_data in lines.values():

        # Obtener IDs de bus y sus índices de matriz
        bus1_id = line_data["bus1"]
        bus2_id = line_data["bus2"]
        
        # Mapear ID de bus a índice de matriz
        bus1_idx = bus_to_idex_in_Ymat[bus1_id]
        bus2_idx = bus_to_idex_in_Ymat[bus2_id]
        
        # Obtener parámetros del modelo PI
        Z_series = line_data["Z"]
        Y_shunt = line_data["Y"]

        # --- A. Contribución de la Admitancia paralelo (Modelo PI) ---
        # Se añade Y/2 a la diagonal en ambos extremos
        Y_matrix[bus1_idx, bus1_idx] += Y_shunt / 2 
        Y_matrix[bus2_idx, bus2_idx] += Y_shunt / 2


        Y_series = 1.0 / Z_series
        # --- B. Contribución de la Admitancia Serie ---
        # --- Modelo Línea Normal (Simétrico) ---
        Y_matrix[bus1_idx, bus1_idx] += Y_series
        Y_matrix[bus2_idx, bus2_idx] += Y_series
        Y_matrix[bus1_idx, bus2_idx] -= Y_series
        Y_matrix[bus2_idx, bus1_idx] -= Y_series


    return {"Y_matrix":Y_matrix , "buses_ids_to_matrix_idxs": bus_to_idex_in_Ymat}


def solve_pu_model2(network_pu_data, method="hybr", use_x0_data=False):    
    # Error relativo maximo para la potencia (Q y P)
    LOGGER.debug("Preparando resolución del modelo p.u.")

    max_P_error = 0.0001
    max_Q_error = 0.0001

    
    buses = network_pu_data["buses"]
    lines = network_pu_data["lines"]
    
    Y_matrix_data = get_admitance_matrix(network_pu_data)
    Y_matrix = Y_matrix_data["Y_matrix"]
    buses_ids_to_matrix_idxs = Y_matrix_data["buses_ids_to_matrix_idxs"]
    matrix_idxs_to_buses_ids = {bus_mat_idx:bus_id for bus_id, bus_mat_idx in buses_ids_to_matrix_idxs.items()}

    
    LOGGER.debug(f"Matriz de admitancias (p.u.) calculada:\n{to_pretty_table(Y_matrix)}")


    N = len(buses) # Numero de buses
    LOGGER.debug(f"Número de buses: {N}")

    # X es la lista de incognitas
    # Hay K nodos PV -> K ecuaciones (ecs P), K incognitas (theta)
    # Hay R nodos PQ -> 2*R ecuaciones (ecs P,Q), 2*R incognitas (V, theta)

    # Los primeros K valores de X serán las thetas correspondientes a los nudos PU
    # Los siguientes R valores serán las V de los nudos PV y los siguientes R las thetas

    bus_ids_sorted = sorted(list(buses.keys()), key=int)
    ordered_buses = {bus_id: buses[bus_id] for bus_id in bus_ids_sorted}

    PV_buses = [bus for bus in buses.values() if bus["type"]=="PV"]
    PV_buses_ids_to_list_idx = {bus["id"]:idx for idx, bus in enumerate(PV_buses)}
    
    PQ_buses = [bus for bus in buses.values() if bus["type"]=="PQ"]
    PQ_buses_ids_to_list_idx = {bus["id"]:idx for idx, bus in enumerate(PQ_buses)}

    K = len(PV_buses)
    R = len(PQ_buses)

    LOGGER.debug(f"Número de buses PV (K): {K}")
    LOGGER.debug(f"Número de buses PQ (R): {R}")


    LOGGER.debug(f"Definiendo función del sistema de ecuaciones...")
    # Definimos el sistema. Una funcion f(X) = 0 (cuando X es la solución)
    def eq_system(X):
        X = list(X)
        PV_thetas = X[ : K] # primeros K valores
        PQ_voltages = X[K : K+R] # siguientes R valores
        PQ_thetas = X[K+R : K+2*R] # siguientes R valores (realmente es "hasta el final", puedo ahorrarm el K+2*R)
        
        result_list = []

        # Calculamos las ecuaciones Pi correspondientes a los nudos PV que añaden su incognita theta
        for i, theta_i in enumerate(PV_thetas):
            bus_data = PV_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PV_buses
            bus_id = bus_data["id"]         # Localizo la ID de este bus
            bus_matrix_idx = buses_ids_to_matrix_idxs[bus_id]  # Localizo su posicion en la matriz de admitancias
            Pi = bus_data["P"]
            Vi = bus_data["V"]
            
            sum = 0 # Calculo del sumatorio de la ecuacion para P
            for j, Y_in_bus_row in enumerate(Y_matrix[bus_matrix_idx]): # Recorremos la fila correspondiente a este bus, en esa fila están todas las admitancias que le conectan con el resto de nudos (admitancias mutuas) y "consigo mismo (admitancia propia)"
                if Y_in_bus_row == 0:
                    continue
                
                other_bus_id = matrix_idxs_to_buses_ids[j]  # Calculo la id de bus que estoy evaluando (el bus conectado al original)
                other_bus_data = buses[other_bus_id]
                match other_bus_data["type"]:
                    case "Slack":
                        Vj = other_bus_data["V"] 
                        theta_j = other_bus_data["theta"]
                    case "PV":
                        Vj = other_bus_data["V"]
                        theta_j_idx = PV_buses_ids_to_list_idx[other_bus_id]
                        theta_j = X[theta_j_idx]

                    case "PQ":
                        V_j_idx = PQ_buses_ids_to_list_idx[other_bus_id] + K 
                        theta_j_idx = V_j_idx + R
                        Vj = X[V_j_idx]
                        theta_j = X[theta_j_idx]
                    case _:
                        LOGGER.critical(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                        raise RuntimeError(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                
                Gij = Y_in_bus_row.real
                Bij = Y_in_bus_row.imag
                theta_ij = theta_i - theta_j
                sum +=  Vj * ( Gij*m.cos(theta_ij) + Bij*m.sin(theta_ij) )

            result_list.append( Pi - Vi*sum )
 
        aux_P_results_list = []


        # Calculamos las ecuaciones Pi, Qi correspondientes a los nudos PQ que añaden sus incognitas theta y V
        for i, (Vi, theta_i) in enumerate(zip(PQ_voltages, PQ_thetas)):
            bus_data = PQ_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PQ_buses
            bus_id = bus_data["id"]         # Localizo la ID de este bus
            bus_matrix_idx = buses_ids_to_matrix_idxs[bus_id]  # Localizo su posicion en la matriz de admitancias
            Pi = bus_data["P"]  # Su valor P es conocido
            Qi = bus_data["Q"]  # Su valor Q es conocido

            sumP = sumQ = 0 # Calculo del sumatorio de la ecuacion para P y para Q
            for j, Y_in_bus_row in enumerate(Y_matrix[bus_matrix_idx]): # Recorremos la fila correspondiente a este bus, en esa fila están todas las admitancias que le conectan con el resto de nudos (admitancias mutuas) y "consigo mismo (admitancia propia)"
                if Y_in_bus_row == 0:
                    continue
                
                other_bus_id = matrix_idxs_to_buses_ids[j]  # Calculo la id de bus que estoy evaluando (el bus conectado al original)
                other_bus_data = buses[other_bus_id]

                match other_bus_data["type"]:
                    case "Slack":
                        Vj = other_bus_data["V"] 
                        theta_j = other_bus_data["theta"]
                    case "PV":
                        Vj = other_bus_data["V"]
                        theta_j_idx = PV_buses_ids_to_list_idx[other_bus_id]
                        theta_j = X[theta_j_idx]

                    case "PQ":
                        V_j_idx = PQ_buses_ids_to_list_idx[other_bus_id] + K 
                        theta_j_idx = V_j_idx + R
                        Vj = X[V_j_idx]
                        theta_j = X[theta_j_idx]
                    case _:
                        LOGGER.critical(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                        raise RuntimeError(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                
                Gij = Y_in_bus_row.real
                Bij = Y_in_bus_row.imag
                theta_ij = theta_i - theta_j

                sumP +=  Vj * ( Gij*m.cos(theta_ij) + Bij*m.sin(theta_ij) )
                sumQ +=  Vj * ( Gij*m.sin(theta_ij) - Bij*m.cos(theta_ij) )

            result_list.append( Qi - Vi*sumQ )
            aux_P_results_list.append( Pi - Vi*sumP )


            # Se retorna la lista de "resultados" de cada ecuacion alineado de esta forma:
            #  X[:K] <-> RESULT[:K] : K ecuaciones de P para cada nudo PV alineadas con sus K thetas 
            #  X[K:K+R] <-> RESULT[K:K+R] : R ecuaciones de Q para cada nudo PQ alineadas con sus R voltages 
            #  X[K+R:] <-> RESULT[K+R:] : R ecuaciones de P para cada nudo PQ alineadas con sus R thetas 

        return result_list + aux_P_results_list

    LOGGER.debug(f"Función del sistema definida exitosamente.")

    X0 = []

    if not use_x0_data:
        # # Valor inicial (semilla del método de Newton)
        X0 += [0] * K  # Thetas de todos los PV buses a 0
        X0 += [1] * R  # Tension de todos los PQ buses a 1
        X0 += [0] * R  # Thetas de todos los PQ buses a 0
    else:
        try:
            X0 += [bus["theta0"] for bus in PV_buses] # Thetas 0 personalizados (se espera que estén en el diccionario)
            X0 += [bus["V0"] for bus in PQ_buses]
            X0 += [bus["theta0"] for bus in PQ_buses]
        except KeyError as e:
            LOGGER.critical("Fallo al intentar buscar un valor para las keys theta0 o V0 en alguno de los diccionarios de los buses PV o PQ. Cuando se activa el argumento 'use_x0_data', se espera que existan estas keys en los diccionarios")
            raise ValueError("Fallo al intentar buscar un valor para las keys theta0 o V0 en alguno de los diccionarios de los buses PV o PQ. Cuando se activa el argumento 'use_x0_data', se espera que existan estas keys en los diccionarios") from e
        if None in X0:
            LOGGER.critical("Se ha encontrado al menos un 'None' como valor de theta0 o V0 en algun nodo PV o PQ. Cuando se activa el argumento 'use_x0_data' se espera que estos valores existan")
            raise ValueError("Se ha encontrado al menos un 'None' como valor de theta0 o V0 en algun nodo PV o PQ. Cuando se activa el argumento 'use_x0_data' se espera que estos valores existan")


    LOGGER.debug(f"Valores iniciales para resolver:\n    PV thetas: {X0[:K]}\n    PQ thetas: {X0[K+R : K+2*R]}\n    PQ voltages: {X0[K : K+R]}")

    LOGGER.debug(f"Resolviendo con scipy.root. Método {method}")
    # Resolver con root
    solution_object = root(eq_system, X0, method=method)

    if solution_object.success:
        LOGGER.info(f"¡Convergencia Exitosa! ({solution_object.message})")
    else:
        LOGGER.warning(f"No convergió correctamente. ({solution_object.message})")
        return None

    sol = solution_object.x

    LOGGER.debug(f"Solución bruta: \n{sol}")
    
    PV_thetas = sol[ : K] # primeros K valores
    PQ_voltages = sol[K : K+R] # siguientes R valores
    PQ_thetas = sol[K+R : K+2*R] # siguientes R valores
    
    LOGGER.debug(f"Valores obtenidos en la solución:\n    PV thetas: {PV_thetas}\n    PQ thetas: {PQ_thetas}\n    PQ voltages: {PQ_voltages}")

    # Añado las soluciones a los diccionarios. Creando de paso nuevos diccionarios "resueltos"

    solved_network_pu_data = deepcopy(network_pu_data)
    solved_buses = solved_network_pu_data["buses"]
     
    LOGGER.debug("Añadiendo los voltages y las thetas (normalizadas) resueltas al diccionario de cada bus")
    for i, theta_i in enumerate(PV_thetas):
        bus_data = PV_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PV_buses
        bus_id = bus_data["id"]         # Localizo la ID de este bus
        solved_buses[bus_id]["theta"] = theta_i
        LOGGER.debug(f"La theta con índice {i} en el vector solución se corresponde con el bus PV de ID {bus_id}. Añadiendo su theta a su diccionario...")


    for i, (Vi, theta_i) in enumerate(zip(PQ_voltages, PQ_thetas)):
        bus_data = PQ_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PQ_buses
        bus_id = bus_data["id"]         # Localizo la ID de este bus

        solved_buses[bus_id]["V"] = Vi
        solved_buses[bus_id]["theta"] = theta_i

        LOGGER.debug(f"El voltage con índice {i+K} y la theta con indice {i+K+R} en el vector solución se corresponden con el bus PQ de ID {bus_id}. Añadiendo sus valores de theta y voltage a su diccionario...")


    # Añadimos a cada bus las "intensidades" que salen de él (esto sería mas eficiente con un producto matricial I=Y*U) 
    # Antes necesito crear el vector de tensiones
    complex_V_vector = np.array( [ rect(solved_buses[matrix_idxs_to_buses_ids[idx]]["V"], 
                                        solved_buses[matrix_idxs_to_buses_ids[idx]]["theta"]) 
                                  for idx in range(len(Y_matrix[0])) ] )

    for bus_id, bus_data in solved_buses.items():
        bus_mat_idx = buses_ids_to_matrix_idxs[bus_id]
        Y_row = Y_matrix[bus_mat_idx]

        I = np.dot( Y_row , complex_V_vector )
        bus_data["I"] = I
        V = rect(bus_data["V"], bus_data["theta"])
        S = V * I.conjugate()
        Q = S.imag
        P = S.real

        if "Q" not in bus_data:
            # Añadir Q
            bus_data["Q"] = Q
        elif max_Q_error < abs(bus_data["Q"]-Q)/Q:
            LOGGER.error(f"Se ha encontrado un valor de P ({bus_data["Q"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({Q}).")
            # raise RuntimeError(f"Se ha encontrado un valor de P ({bus_data["Q"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({Q}).")

        if "P" not in bus_data:
            # Añadir P
            bus_data["P"]= P
        elif max_P_error < abs(bus_data["P"]-P)/P:
            LOGGER.error(f"Se ha encontrado un valor de P ({bus_data["P"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({P}).")
            # raise RuntimeError(f"Se ha encontrado un valor de P ({bus_data["P"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({P}).")


    return solved_network_pu_data


def solve_pu_model(network_pu_data):    
    # Error relativo maximo para la potencia (Q y P)
    LOGGER.debug("Preparando resolución del modelo p.u.")

    max_P_error = 0.0001
    max_Q_error = 0.0001

    
    buses = network_pu_data["buses"]
    lines = network_pu_data["lines"]
    
    Y_matrix_data = get_admitance_matrix(network_pu_data)
    Y_matrix = Y_matrix_data["Y_matrix"]
    buses_ids_to_matrix_idxs = Y_matrix_data["buses_ids_to_matrix_idxs"]
    matrix_idxs_to_buses_ids = {bus_mat_idx:bus_id for bus_id, bus_mat_idx in buses_ids_to_matrix_idxs.items()}

    
    LOGGER.debug(f"Matriz de admitancias (p.u.) calculada:\n{to_pretty_table(Y_matrix)}")


    N = len(buses) # Numero de buses
    LOGGER.debug(f"Número de buses: {N}")

    # X es la lista de incognitas
    # Hay K nodos PV -> K ecuaciones (ecs P), K incognitas (theta)
    # Hay R nodos PQ -> 2*R ecuaciones (ecs P,Q), 2*R incognitas (V, theta)

    # Los primeros K valores de X serán las thetas correspondientes a los nudos PU
    # Los siguientes R valores serán las V de los nudos PV y los siguientes R las thetas

    bus_ids_sorted = sorted(list(buses.keys()), key=int)
    ordered_buses = {bus_id: buses[bus_id] for bus_id in bus_ids_sorted}

    PV_buses = [bus for bus in buses.values() if bus["type"]=="PV"]
    PV_buses_ids_to_list_idx = {bus["id"]:idx for idx, bus in enumerate(PV_buses)}
    
    PQ_buses = [bus for bus in buses.values() if bus["type"]=="PQ"]
    PQ_buses_ids_to_list_idx = {bus["id"]:idx for idx, bus in enumerate(PQ_buses)}

    K = len(PV_buses)
    R = len(PQ_buses)

    LOGGER.debug(f"Número de buses PV (K): {K}")
    LOGGER.debug(f"Número de buses PQ (R): {R}")


    LOGGER.debug(f"Definiendo función del sistema de ecuaciones...")
    # Definimos el sistema. Una funcion f(X) = 0 (cuando X es la solución)
    def eq_system(X):
        X = list(X)
        PV_thetas = X[ : K] # primeros K valores
        PQ_voltages = X[K : K+R] # siguientes R valores
        PQ_thetas = X[K+R : K+2*R] # siguientes R valores (realmente es "hasta el final", puedo ahorrarm el K+2*R)
        
        result_list = []

        # Calculamos las ecuaciones Pi correspondientes a los nudos PV que añaden su incognita theta
        for i, theta_i in enumerate(PV_thetas):
            bus_data = PV_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PV_buses
            bus_id = bus_data["id"]         # Localizo la ID de este bus
            bus_matrix_idx = buses_ids_to_matrix_idxs[bus_id]  # Localizo su posicion en la matriz de admitancias
            Pi = bus_data["P"]
            Vi = bus_data["V"]
            
            sum = 0 # Calculo del sumatorio de la ecuacion para P
            for j, Y_in_bus_row in enumerate(Y_matrix[bus_matrix_idx]): # Recorremos la fila correspondiente a este bus, en esa fila están todas las admitancias que le conectan con el resto de nudos (admitancias mutuas) y "consigo mismo (admitancia propia)"
                if Y_in_bus_row == 0:
                    continue
                
                other_bus_id = matrix_idxs_to_buses_ids[j]  # Calculo la id de bus que estoy evaluando (el bus conectado al original)
                other_bus_data = buses[other_bus_id]
                match other_bus_data["type"]:
                    case "Slack":
                        Vj = other_bus_data["V"] 
                        theta_j = other_bus_data["theta"]
                    case "PV":
                        Vj = other_bus_data["V"]
                        theta_j_idx = PV_buses_ids_to_list_idx[other_bus_id]
                        theta_j = X[theta_j_idx]

                    case "PQ":
                        V_j_idx = PQ_buses_ids_to_list_idx[other_bus_id] + K 
                        theta_j_idx = V_j_idx + R
                        Vj = X[V_j_idx]
                        theta_j = X[theta_j_idx]
                    case _:
                        LOGGER.critical(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                        raise RuntimeError(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                
                Gij = Y_in_bus_row.real
                Bij = Y_in_bus_row.imag
                theta_ij = theta_i - theta_j
                sum +=  Vj * ( Gij*m.cos(theta_ij) + Bij*m.sin(theta_ij) )

            result_list.append( Pi - Vi*sum )
 
        aux_P_results_list = []


        # Calculamos las ecuaciones Pi, Qi correspondientes a los nudos PQ que añaden sus incognitas theta y V
        for i, (Vi, theta_i) in enumerate(zip(PQ_voltages, PQ_thetas)):
            bus_data = PQ_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PQ_buses
            bus_id = bus_data["id"]         # Localizo la ID de este bus
            bus_matrix_idx = buses_ids_to_matrix_idxs[bus_id]  # Localizo su posicion en la matriz de admitancias
            Pi = bus_data["P"]  # Su valor P es conocido
            Qi = bus_data["Q"]  # Su valor Q es conocido

            sumP = sumQ = 0 # Calculo del sumatorio de la ecuacion para P y para Q
            for j, Y_in_bus_row in enumerate(Y_matrix[bus_matrix_idx]): # Recorremos la fila correspondiente a este bus, en esa fila están todas las admitancias que le conectan con el resto de nudos (admitancias mutuas) y "consigo mismo (admitancia propia)"
                if Y_in_bus_row == 0:
                    continue
                
                other_bus_id = matrix_idxs_to_buses_ids[j]  # Calculo la id de bus que estoy evaluando (el bus conectado al original)
                other_bus_data = buses[other_bus_id]

                match other_bus_data["type"]:
                    case "Slack":
                        Vj = other_bus_data["V"] 
                        theta_j = other_bus_data["theta"]
                    case "PV":
                        Vj = other_bus_data["V"]
                        theta_j_idx = PV_buses_ids_to_list_idx[other_bus_id]
                        theta_j = X[theta_j_idx]

                    case "PQ":
                        V_j_idx = PQ_buses_ids_to_list_idx[other_bus_id] + K 
                        theta_j_idx = V_j_idx + R
                        Vj = X[V_j_idx]
                        theta_j = X[theta_j_idx]
                    case _:
                        LOGGER.critical(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                        raise RuntimeError(f"Se ha detectado un nudo (ID: {other_bus_id}) que no es ni Slack, ni PQ, ni PV. Tipo: {other_bus_data["type"]}")
                
                Gij = Y_in_bus_row.real
                Bij = Y_in_bus_row.imag
                theta_ij = theta_i - theta_j

                sumP +=  Vj * ( Gij*m.cos(theta_ij) + Bij*m.sin(theta_ij) )
                sumQ +=  Vj * ( Gij*m.sin(theta_ij) - Bij*m.cos(theta_ij) )

            result_list.append( Qi - Vi*sumQ )
            aux_P_results_list.append( Pi - Vi*sumP )


            # Se retorna la lista de "resultados" de cada ecuacion alineado de esta forma:
            #  X[:K] <-> RESULT[:K] : K ecuaciones de P para cada nudo PV alineadas con sus K thetas 
            #  X[K:K+R] <-> RESULT[K:K+R] : R ecuaciones de Q para cada nudo PQ alineadas con sus R voltages 
            #  X[K+R:] <-> RESULT[K+R:] : R ecuaciones de P para cada nudo PQ alineadas con sus R thetas 

        return result_list + aux_P_results_list

    LOGGER.debug(f"Función del sistema definida exitosamente.")

    # # Valor inicial (semilla del método de Newton)
    X0 = []
    X0 += [0] * K  # Thetas de todos los PV buses a 0
    X0 += [1] * R  # Tension de todos los PQ buses a 1
    X0 += [0] * R  # Thetas de todos los PQ buses a 0

    LOGGER.debug(f"Valores iniciales para resolver:\n    PV thetas: {X0[:K]}\n    PQ thetas: {X0[K+R : K+2*R]}\n    PQ voltages: {X0[K : K+R]}")

    # Resolver
    sol = fsolve(eq_system, X0)

    LOGGER.debug(f"Solución obtenida con scipy.fsolve")
    LOGGER.debug(f"Solución bruta: \n{sol}")
    
    PV_thetas = sol[ : K] # primeros K valores
    PQ_voltages = sol[K : K+R] # siguientes R valores
    PQ_thetas = sol[K+R : K+2*R] # siguientes R valores
    
    LOGGER.debug(f"Valores obtenidos en la solución:\n    PV thetas: {PV_thetas}\n    PQ thetas: {PQ_thetas}\n    PQ voltages: {PQ_voltages}")

    # Añado las soluciones a los diccionarios. Creando de paso nuevos diccionarios "resueltos"

    solved_network_pu_data = deepcopy(network_pu_data)
    solved_buses = solved_network_pu_data["buses"]
     
    LOGGER.debug("Añadiendo los voltages y las thetas (normalizadas) resueltas al diccionario de cada bus")
    for i, theta_i in enumerate(PV_thetas):
        bus_data = PV_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PV_buses
        bus_id = bus_data["id"]         # Localizo la ID de este bus
        solved_buses[bus_id]["theta"] = theta_i
        LOGGER.debug(f"La theta con índice {i} en el vector solución se corresponde con el bus PV de ID {bus_id}. Añadiendo su theta a su diccionario...")


    for i, (Vi, theta_i) in enumerate(zip(PQ_voltages, PQ_thetas)):
        bus_data = PQ_buses[i]          # Cada bus se corresponde con la "i" que le toque segun su index en la lista PQ_buses
        bus_id = bus_data["id"]         # Localizo la ID de este bus

        solved_buses[bus_id]["V"] = Vi
        solved_buses[bus_id]["theta"] = theta_i

        LOGGER.debug(f"El voltage con índice {i+K} y la theta con indice {i+K+R} en el vector solución se corresponden con el bus PQ de ID {bus_id}. Añadiendo sus valores de theta y voltage a su diccionario...")


    # Añadimos a cada bus las "intensidades" que salen de él (esto sería mas eficiente con un producto matricial I=Y*U) 
    # Antes necesito crear el vector de tensiones
    complex_V_vector = np.array( [ rect(solved_buses[matrix_idxs_to_buses_ids[idx]]["V"], 
                                        solved_buses[matrix_idxs_to_buses_ids[idx]]["theta"]) 
                                  for idx in range(len(Y_matrix[0])) ] )

    for bus_id, bus_data in solved_buses.items():
        bus_mat_idx = buses_ids_to_matrix_idxs[bus_id]
        Y_row = Y_matrix[bus_mat_idx]

        I = np.dot( Y_row , complex_V_vector )
        bus_data["I"] = I
        V = rect(bus_data["V"], bus_data["theta"])
        S = V * I.conjugate()
        Q = S.imag
        P = S.real

        if "Q" not in bus_data:
            # Añadir Q
            bus_data["Q"] = Q
        elif max_Q_error < abs(bus_data["Q"]-Q)/Q:
            LOGGER.error(f"Se ha encontrado un valor de P ({bus_data["Q"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({Q}).")
            # raise RuntimeError(f"Se ha encontrado un valor de P ({bus_data["Q"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({Q}).")

        if "P" not in bus_data:
            # Añadir P
            bus_data["P"]= P
        elif max_P_error < abs(bus_data["P"]-P)/P:
            LOGGER.error(f"Se ha encontrado un valor de P ({bus_data["P"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({P}).")
            # raise RuntimeError(f"Se ha encontrado un valor de P ({bus_data["P"]}) en el bus {bus_id} que no se corresponde con el que se calcula tras resolver el flujo de cargas ({P}).")


    return solved_network_pu_data
