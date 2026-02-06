import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from prettytable import PrettyTable, ALL

def plot_funcs(
    funcs,
    etiquetas=None,
    rango=(-1, 1),
    puntos=1000,
    titulo="Gráfico de funciones",
    xlabel="x",
    ylabel="y",
    colores=None,
    estilos=None,
    grosor=1.5,
    grid=True,
    legend=True,
    margen=0.05,
    figsize=(8, 5),
    background="#ffffff"
):
    """
    Grafica una lista de funciones reales (lambda no vectorizables).
    Permite personalizar casi todos los aspectos del gráfico.
    
    Parámetros:
      funcs: lista de funciones f(x)
      etiquetas: lista de etiquetas para la leyenda
      rango: tupla (xmin, xmax)
      puntos: número de puntos a evaluar
      titulo, xlabel, ylabel: textos
      colores: lista de colores opcionales
      estilos: lista de estilos de línea ('-', '--', ':', etc.)
      grosor: grosor de línea
      grid: mostrar cuadrícula
      legend: mostrar leyenda
      margen: fracción de margen lateral
      figsize: tamaño del gráfico
      background: color de fondo
    """

    x = np.linspace(rango[0], rango[1], puntos)
    plt.figure(figsize=figsize, facecolor=background)

    for i, f in enumerate(funcs):
        # Evaluación punto a punto (para funciones no vectorizables)
        if not callable(f):
            continue
        y = np.array([f(val) for val in x])
        color = colores[i] if colores and i < len(colores) else None
        estilo = estilos[i] if estilos and i < len(estilos) else '-'
        label = etiquetas[i] if etiquetas and i < len(etiquetas) else None
        plt.plot(x, y, linestyle=estilo, color=color, linewidth=grosor, label=label)

    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if grid:
        plt.grid(True, linestyle='--', alpha=0.7)
    if legend and etiquetas:
        plt.legend()
    plt.xlim(rango[0] - margen, rango[1] + margen)
    plt.tight_layout()
    plt.show()



def plot_phasors(
    fasores,
    etiquetas=None,
    titulo="Diagrama fasorial",
    colores=None,
    estilos=None,
    grosor=2,
    escala=1.1,
    figsize=(6, 6),
    grid=True,
    eje=True,
    legend=True,
    background="#ffffff"
):
    """
    Dibuja un diagrama fasorial (vectores complejos).
    
    Parámetros:
      fasores: lista de números complejos
      etiquetas: lista de etiquetas opcionales
      colores: lista de colores
      estilos: lista de estilos ('-', '--', etc.)
      grosor: grosor de línea
      escala: factor de margen respecto al fasor más largo
      figsize: tamaño de la figura
      grid, eje, legend: opciones de visualización
      background: color de fondo
    """

    plt.figure(figsize=figsize, facecolor=background)
    ax = plt.gca()
    ax.set_aspect('equal', adjustable='box')

    max_len = 0
    for i, z in enumerate(fasores):
        color = colores[i] if colores and i < len(colores) else None
        estilo = estilos[i] if estilos and i < len(estilos) else '-'
        label = etiquetas[i] if etiquetas and i < len(etiquetas) else None

        # Dibujar flecha desde el origen
        plt.arrow(
            0, 0, np.real(z), np.imag(z),
            head_width=0.05 * abs(z), head_length=0.1 * abs(z),
            length_includes_head=True,
            color=color,
            linestyle=estilo,
            linewidth=grosor,
            label=label
        )

        max_len = max(max_len, abs(z))

    # Ejes
    if eje:
        plt.axhline(0, color='black', linewidth=0.8)
        plt.axvline(0, color='black', linewidth=0.8)

    if grid:
        plt.grid(True, linestyle='--', alpha=0.6)

    plt.title(titulo)
    plt.xlim(-max_len * escala, max_len * escala)
    plt.ylim(-max_len * escala, max_len * escala)

    if legend and etiquetas:
        plt.legend()
    plt.xlabel("Parte real")
    plt.ylabel("Parte imaginaria")
    plt.tight_layout()
    plt.show()




# ======================================
#     Plot functions
# ======================================

def plot_power_network(network_data):
    
    """
    Dibuja un gráfico de la red eléctrica.
    Dibuja líneas normales y transformadores (has_T=True) con estilos diferentes.
    
    Parameters:
        network_data (dict): Diccionario con "buses" y "lines".
    """
    buses = network_data["buses"]
    lines = network_data["lines"]

    # Crear grafo vacío
    G = nx.Graph()

    # --- NUEVO: Listas separadas para líneas y trafos ---
    normal_lines = []
    transformer_lines = []

    # Añadir nodos (buses)
    for bus in buses:
        bus_id = str(bus["id"])
        G.add_node(bus_id, type=bus["type"].upper())

    # Añadir líneas (edges) y CLASIFICARLAS
    for line in lines:
        b1 = str(line["bus1"])
        b2 = str(line["bus2"])
        
        # G.add_edge(b1, b2) # Quitamos esto para hacerlo después
        
        # Usamos .get() para evitar errores si la clave no existiera
        if line.get("has_T", False):
            transformer_lines.append((b1, b2))
        else:
            normal_lines.append((b1, b2))

    # Añadir TODAS las aristas al grafo (necesario para el layout)
    G.add_edges_from(normal_lines)
    G.add_edges_from(transformer_lines)

    # Posiciones automáticas para el grafo
    pos = nx.spring_layout(G, seed=42)

    # Colores según tipo de bus (sin cambios)
    node_colors = []
    for n in G.nodes(data=True):
        t = n[1]["type"]
        if t == "SLACK":
            node_colors.append("red")
        elif t == "PQ":
            node_colors.append("skyblue")
        elif t == "PV":
            node_colors.append("lightgreen")
        else:
            node_colors.append("gray")

    # --- NUEVO: Dibujar aristas en dos pasadas ---
    plt.figure(figsize=(12, 8)) # Opcional: hacer el gráfico más grande
    
    # 1. Dibujar líneas normales
    nx.draw_networkx_edges(
        G, pos, 
        edgelist=normal_lines, 
        edge_color="gray", 
        width=1.5,
        style="solid" # Estilo normal
    )
    
    # 2. Dibujar transformadores
    nx.draw_networkx_edges(
        G, pos, 
        edgelist=transformer_lines, 
        edge_color="purple", # Color distintivo
        width=2.0,        # Ligeramente más grueso
        style="dashed"    # Estilo discontinuo
    )

    # Dibujar nodos y etiquetas (sin cambios)
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500, edgecolors='black')
    nx.draw_networkx_labels(G, pos, font_size=9, font_weight="bold")

    # Título y leyenda
    plt.title("Grafo de la Red Eléctrica", fontsize=14)
    
    # --- NUEVO: Leyenda actualizada ---
    
    # Crear handles para la leyenda (combinando nodos y aristas)
    legend_handles = []
    
    # Leyenda de Nodos
    node_labels = {"SLACK": "red", "PQ": "skyblue", "PV": "lightgreen"}
    for typ, color in node_labels.items():
        legend_handles.append(
            plt.scatter([], [], c=color, label=f"Nudo {typ}", s=100, edgecolors='black')
        )
        
    # Leyenda de Aristas
    legend_handles.append(
        plt.Line2D([0], [0], color="gray", lw=2, linestyle="solid", label="Línea")
    )
    legend_handles.append(
        plt.Line2D([0], [0], color="purple", lw=2, linestyle="dashed", label="Transformador")
    )

    plt.legend(handles=legend_handles, loc="best", frameon=True, labelspacing=1)
    
    plt.axis("off")
    plt.tight_layout()
    plt.savefig("network_graph.svg") # Corregí tu comentario (era SVG, no PNG)
    print("Gráfico guardado como 'network_graph.svg'")
    plt.close() # Cierra la figura para liberar memoria


def plot_pu_power_network(network_data):
    """
    Dibuja un gráfico de la red eléctrica desde datos en p.u.
    - Muestra líneas vs. transformadores con estilos diferentes.
    - Etiqueta nudos: ID (dentro) y Section_ID (fuera, a un lado).
    - MUEVO: Muestra un cuadro de info TABULADO y filtrado por alias.

    Parameters:
        network_data (dict): Diccionario con "buses" (dict), "lines" (dict),
                             "sections" (list) y "S_base" (float).
    """
    
    # 1. MAPA DE ALIAS (Ahora también actúa como FILTRO)
    # ----------------------------------------------------
    # Formato: "clave_interna": ("Nombre a mostrar", decimales)
    # ¡SOLO las claves que estén aquí se mostrarán!
    alias_map = {
        "V_base": ("Vb", 2), # Puedes cambiar "Vb" por "U_base (kV)"
        "Z_base": ("Zb", 2),
        "I_base": ("Ib", 2),
        "theta_base": ("φb", 2),
        # Añade aquí cualquier otra clave_base que tengas
    }
    decs_S_base = 2 #Decimales que se muestran de la S base

    # 2. LEER DATOS
    # ----------------------------------------------------
    buses_dict = network_data["buses"]
    lines_dict = network_data["lines"]
    sections_list = network_data["sections"]
    s_base = network_data["S_base"]

    # ... (Secciones 3, 4, 5 - Creación del Grafo - Sin cambios) ...
    
    G = nx.Graph()
    normal_lines = []
    transformer_lines = []
    labels_main = {}
    
    for bus_id, bus in buses_dict.items():
        bus_id_str = str(bus_id)
        G.add_node(bus_id_str, type=bus["type"].upper())
        labels_main[bus_id_str] = bus_id_str

    for line in lines_dict.values():
        b1 = str(line["bus1"])
        b2 = str(line["bus2"])
        if line.get("has_T", False): transformer_lines.append((b1, b2))
        else: normal_lines.append((b1, b2))

    G.add_edges_from(normal_lines)
    G.add_edges_from(transformer_lines)
    pos = nx.spring_layout(G, seed=42)

    node_colors = []
    for n in G.nodes(data=True):
        t = n[1]["type"]
        if t == "SLACK": node_colors.append("red")
        elif t == "PQ": node_colors.append("skyblue")
        elif t == "PV": node_colors.append("lightgreen")
        else: node_colors.append("gray")

    # 6. DIBUJAR EL GRAFO
    # ----------------------------------------------------
    plt.figure(figsize=(14, 9))
    ax = plt.gca() 

    nx.draw_networkx_edges(G, pos, edgelist=normal_lines, edge_color="gray", width=1.5, style="solid")
    nx.draw_networkx_edges(G, pos, edgelist=transformer_lines, edge_color="purple", width=2.0, style="dashed")
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500, edgecolors='black')
    
    # 7. DIBUJO DE ETIQUETAS (Sin cambios)
    # ----------------------------------------------------
    nx.draw_networkx_labels(G, pos, labels=labels_main, 
                            font_size=9, font_weight="bold", font_color="black")

    for bus_id_str, (x, y) in pos.items():
        bus_id_int = int(bus_id_str) 
        bus_data = buses_dict[bus_id_int]
        sec_label = f"S{bus_data['section']}"
        ax.text(x + 0.04, y + 0.04, sec_label,
                ha='left', va='bottom', fontsize=7,
                color='dimgray', fontweight='bold')

    plt.title("Grafo de la Red Eléctrica (modelo p.u.)", fontsize=16)
    plt.axis("off")

    # 8. LEYENDA DE TIPOS (Sin cambios)
    # ----------------------------------------------------
    legend_handles = []
    node_labels = {"SLACK": "red", "PQ": "skyblue", "PV": "lightgreen"}
    for typ, color in node_labels.items():
        legend_handles.append(plt.scatter([], [], c=color, label=f"Nudo {typ}", s=100, edgecolors='black'))
    legend_handles.append(plt.Line2D([0], [0], color="gray", lw=2, linestyle="solid", label="Línea"))
    legend_handles.append(plt.Line2D([0], [0], color="purple", lw=2, linestyle="dashed", label="Transformador"))
    plt.legend(handles=legend_handles, loc="lower left", frameon=True, labelspacing=1, fontsize=9)

    # 9. NUEVO: CUADRO DE INFORMACIÓN (Formato TABLA)
    # ----------------------------------------------------
    
    # --- 9a. Determinar Columnas y Anchos ---
    col_width_map = {} # {'U_base': 10, 'Z_base': 12}
    ordered_keys = []    # ['U_base', 'Z_base']
    
    # Encontrar todas las claves presentes en los datos Y en el alias_map
    for sec in sections_list:
        for key in sec.keys():
            if key in alias_map and key not in col_width_map:
                # Inicializar ancho con el largo del alias (cabecera)
                col_width_map[key] = len(alias_map[key][0])
                ordered_keys.append(key)
    
    # Ajustar ancho de columna según los datos
    for sec in sections_list:
        for key in ordered_keys:
            if key in sec:
                value = sec[key]
                decimals = alias_map[key][1]
                val_str = f"{value:.{decimals}f}"
                # El ancho es el máximo entre el alias y el dato más largo
                col_width_map[key] = max(col_width_map[key], len(val_str))

    # --- 9b. Construir la cadena de texto ---
    info_text = f"S_base (Sistema): {s_base:.4f}\n" 
    
    # Cabecera de la tabla
    header_row = f"{'Sección':<8} |" # 8 chars para "Sec XX "
    sep_row =    f"{'-'*8:<8} |"
    
    for key in ordered_keys:
        alias = alias_map[key][0]
        width = col_width_map[key]
        header_row += f" {alias:>{width}} |" # Alinear cabecera a la derecha
        sep_row    += f" {'-'*width:>{width}} |"

    info_text += header_row + "\n"
    info_text += sep_row + "\n"

    # Filas de datos
    for sec in sections_list:
        row_str = f"{'Sec ' + str(sec['id']):<8} |"
        for key in ordered_keys:
            width = col_width_map[key]
            if key in sec:
                value = sec[key]
                decimals = alias_map[key][1]
                val_str = f"{value:.{decimals}f}"
                row_str += f" {val_str:>{width}} |" # Alinear dato a la derecha
            else:
                row_str += f" {'-':>{width}} |" # Si no hay dato
        info_text += row_str + "\n"

    # --- 9c. Dibujar el cuadro de texto ---
    ax.text(0.01, 0.99, info_text,
             transform=ax.transAxes, 
             fontsize=9, # Un poco más pequeño para que quepa la tabla
             fontfamily='monospace', # ¡CRUCIAL para que se alinee!
             va='top', 
             ha='left', 
             bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.7))

    # 10. GUARDAR Y MOSTRAR
    # ----------------------------------------------------
    plt.tight_layout()
    plt.savefig("network_graph_sections.svg")
    print("Gráfico guardado como 'network_graph_sections.svg'")
    plt.close()


def plot_solved_power_network(network_data, show_results=True):
    """
    Dibuja un gráfico de la red eléctrica.
    
    Si network_data contiene resultados (ej. 'V_sol_pu') y show_results=True,
    mostrará los voltajes y ángulos en los nudos.

    Parameters:
        network_data (dict): Diccionario con "buses", "lines", "sections", "S_base".
                             Puede contener opcionalmente los resultados de la simulación.
        show_results (bool): Si es True, intenta dibujar los voltajes y ángulos.
    """
    
    # 1. MAPA DE ALIAS (Sin cambios)
    # ----------------------------------------------------
    alias_map = {
        "U_base": ("Vb (kV)", 2), 
        "Z_base": ("Zb (Ω)", 2),
        "I_base": ("Ib (A)", 3),
    }

    # 2. LEER DATOS (Sin cambios)
    # ----------------------------------------------------
    buses_dict = network_data["buses"]
    lines_dict = network_data["lines"]
    sections_list = network_data.get("sections", []) # .get() para robustez
    s_base = network_data.get("S_base", "N/A")

    # 3. CREACIÓN DEL GRAFO (Sin cambios)
    # ----------------------------------------------------
    G = nx.Graph()
    normal_lines = []
    transformer_lines = []
    labels_main = {} # Etiqueta ID (centro)
    
    for bus_id, bus in buses_dict.items():
        bus_id_str = str(bus_id)
        G.add_node(bus_id_str, type=bus["type"].upper())
        labels_main[bus_id_str] = bus_id_str

    # 4. CLASIFICAR ARISTAS (Sin cambios)
    # ----------------------------------------------------
    for line in lines_dict.values():
        b1 = str(line["bus1"])
        b2 = str(line["bus2"])
        if line.get("has_T", False): transformer_lines.append((b1, b2))
        else: normal_lines.append((b1, b2))

    G.add_edges_from(normal_lines)
    G.add_edges_from(transformer_lines)
    pos = nx.spring_layout(G, seed=42)

    # 5. COLORES DE NODOS (Sin cambios)
    # ----------------------------------------------------
    node_colors = []
    for n in G.nodes(data=True):
        t = n[1]["type"]
        if t == "SLACK": node_colors.append("red")
        elif t == "PQ": node_colors.append("skyblue")
        elif t == "PV": node_colors.append("lightgreen")
        else: node_colors.append("gray")

    # 6. DIBUJAR EL GRAFO (Base)
    # ----------------------------------------------------
    plt.figure(figsize=(15, 10)) # Un poco más grande
    ax = plt.gca() 

    # Aristas
    nx.draw_networkx_edges(G, pos, edgelist=normal_lines, edge_color="gray", width=1.5, style="solid")
    nx.draw_networkx_edges(G, pos, edgelist=transformer_lines, edge_color="purple", width=2.0, style="dashed")
    
    # Nodos
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=500, edgecolors='black')
    
    # 7. DIBUJO DE ETIQUETAS (ID + Sección + Resultados)
    # ----------------------------------------------------
    
    # 7a: Dibujar ID del Nudo (CENTRO)
    nx.draw_networkx_labels(G, pos, labels=labels_main, 
                            font_size=9, font_weight="bold", font_color="black")

    # 7b y 7c: Dibujar etiquetas de Sección y Resultados
    for bus_id_str, (x, y) in pos.items():
        bus_id_int = int(bus_id_str) 
        
        # Puede que el bus_id no esté en el dict si es un nudo intermedio
        if bus_id_int not in buses_dict: 
            continue
            
        bus_data = buses_dict[bus_id_int]
        
        # 7b: Dibujar ID de Sección (Arriba-Derecha)
        if "section" in bus_data:
            sec_label = f"S{bus_data['section']}"
            ax.text(x + 0.04, y + 0.04, sec_label,
                    ha='left', va='bottom', fontsize=7,
                    color='dimgray', fontweight='bold')
                
        # 7c: NUEVO - Dibujar Resultados de Voltaje (Abajo-Centro)
        if show_results and "V_sol_pu" in bus_data and "theta_sol_deg" in bus_data:
            v_mag = bus_data["V_sol_pu"]
            v_ang_deg = bus_data["theta_sol_deg"]
            
            # Formato: V∠θ°
            v_label = f"{v_mag:.3f}∠{v_ang_deg:.2f}°"
            
            # Dibujar el texto *debajo* del nudo (y - offset)
            ax.text(x, y - 0.05, v_label,
                    ha='center', # Centrado horizontalmente
                    va='top',    # Alineado verticalmente (anclado por arriba)
                    fontsize=8,
                    color='blue', # Color distintivo para los resultados
                    fontweight='normal',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.5, ec='none')) # Fondo semitransparente

    # 8. LEYENDA DE TIPOS (Sin cambios)
    # ----------------------------------------------------
    legend_handles = []
    # ... (código de la leyenda de nudos y líneas) ...
    node_labels = {"SLACK": "red", "PQ": "skyblue", "PV": "lightgreen"}
    for typ, color in node_labels.items():
        legend_handles.append(plt.scatter([], [], c=color, label=f"Nudo {typ}", s=100, edgecolors='black'))
    legend_handles.append(plt.Line2D([0], [0], color="gray", lw=2, linestyle="solid", label="Línea"))
    legend_handles.append(plt.Line2D([0], [0], color="purple", lw=2, linestyle="dashed", label="Transformador"))
    plt.legend(handles=legend_handles, loc="lower left", frameon=True, labelspacing=1, fontsize=9)


    # 9. CUADRO DE INFORMACIÓN (Tabla de Secciones) (Sin cambios)
    # ----------------------------------------------------
    # ... (código que genera la tabla de texto) ...
    if sections_list: # Solo mostrar si hay secciones
        # ... (copia aquí la lógica de la "Sección 9" de la respuesta anterior) ...
        # --- 9a. Determinar Columnas y Anchos ---
        col_width_map = {} 
        ordered_keys = []    
        
        for sec in sections_list:
            for key in sec.keys():
                if key in alias_map and key not in col_width_map:
                    col_width_map[key] = len(alias_map[key][0])
                    ordered_keys.append(key)
        
        for sec in sections_list:
            for key in ordered_keys:
                if key in sec:
                    value = sec[key]
                    decimals = alias_map[key][1]
                    val_str = f"{value:.{decimals}f}"
                    col_width_map[key] = max(col_width_map[key], len(val_str))

        # --- 9b. Construir la cadena de texto ---
        info_text = f"S_base (Sistema): {s_base} MVA\n" 
        header_row = f"{'Sección':<8} |"
        sep_row =    f"{'-'*8:<8} |"
        
        for key in ordered_keys:
            alias = alias_map[key][0]
            width = col_width_map[key]
            header_row += f" {alias:>{width}} |"
            sep_row    += f" {'-'*width:>{width}} |"

        info_text += header_row + "\n" + sep_row + "\n"

        for sec in sections_list:
            row_str = f"{'Sec ' + str(sec['id']):<8} |"
            for key in ordered_keys:
                width = col_width_map[key]
                if key in sec:
                    value = sec[key]
                    decimals = alias_map[key][1]
                    val_str = f"{value:.{decimals}f}"
                    row_str += f" {val_str:>{width}} |"
                else:
                    row_str += f" {'-':>{width}} |"
            info_text += row_str + "\n"

        # --- 9c. Dibujar el cuadro de texto ---
        ax.text(0.01, 0.99, info_text,
                 transform=ax.transAxes, fontsize=8, fontfamily='monospace',
                 va='top', ha='left', 
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='wheat', alpha=0.7))


    # 10. TÍTULO Y GUARDADO
    # ----------------------------------------------------
    
    # NUEVO: Título dinámico
    if show_results and "V_sol_pu" in list(buses_dict.values())[0]:
        plt.title("Grafo de la Red Eléctrica (Resultados del Flujo)", fontsize=16)
        filename = "network_graph_solved.svg"
    else:
        plt.title("Grafo de la Red Eléctrica (Resuelta)", fontsize=16)
        filename = "network_graph_solved.svg"

    plt.tight_layout()
    plt.savefig(filename)
    print(f"Gráfico guardado como '{filename}'")
    plt.show() 




def to_pretty_table(raw_table: dict[any, list] | list[dict] | np.ndarray):
    """
    Convierte distintas estructuras de datos a una "prettytable" 

    Args:
        raw_table (dict[any, list] | list[dict] | np.ndarray): Una estructura de datos convertible en una tabla. Ultima adicion: 2D ARRAY

    Returns:
        _type_: _description_
    """

    table = PrettyTable()

    # Modo "Lista de diccionarios donde cada diccionario tiene las mismas keys, que son las columnas"
    if isinstance(raw_table, (list)):
        keys = set()
        for dict_in_table in raw_table:
            keys |= set( dict_in_table.keys() )

        columns = list(keys)
        table.field_names = columns

        for dict_in_table in raw_table:
            values = [dict_in_table.get(column) for column in columns]
            table.add_row(values)

    # Modo "Diccionario de columna: lista"
    elif isinstance(raw_table, (dict)):
        
        for column, value_list in raw_table.items():
            table.add_column(column, value_list)

    # Modo "ndarray" 2D
    elif isinstance(raw_table, (np.ndarray)):
        if raw_table.ndim != 2:
            raise ValueError("Los np.array solo pueden convertirse si son 2D")
        table.header = False # Sin cabecera
        table.hrules = ALL   # Lineas diviendo todas las celdas
        for row in raw_table:
                table.add_row(row)

    return table