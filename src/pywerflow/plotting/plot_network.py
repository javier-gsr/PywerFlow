"""
Module for visualizing PowerFlowNetwork objects using NetworkX and Matplotlib.

This module provides flexible tools to plot the topology and results of power networks,
adapting legacy plotting logic to the modern PywerFlow architecture.
"""

from typing import Optional, Any, Dict, List, Tuple, Union
import warnings

import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

from pywerflow.networks.pf_network import PowerFlowNetwork
from pywerflow.buses.bus_types import BusTypes
from pywerflow.branches.pfsolvable_branches import PFSolvableBranch, SimpleTransformer, PiTransformer


def plot_power_flow_network(
    network: PowerFlowNetwork,
    ax: Optional[plt.Axes] = None,
    title: Optional[str] = "Power Flow Network",
    show: bool = True,
    
    # --- Configuración de Nudos ---
    node_size: int = 500,
    node_color_map: Optional[Dict[BusTypes, str]] = None,
    font_size: int = 9,
    label_font_weight: str = "bold",
    show_labels: bool = True,
    
    # --- Configuración de Ramas ---
    edge_width: float = 1.5,
    transformer_edge_width: float = 2.5,
    edge_color: str = "gray",
    transformer_edge_color: str = "purple",
    show_branch_ids: bool = True,
    branch_id_font_size: int = 7,
    
    # --- Configuración del Layout ---
    layout_seed: int|None = None,
    figsize: Tuple[int, int] = (12, 8),
    
    # --- Visualización de Resultados ---
    show_results: bool = False,
    result_font_size: int = 8,
    result_color: str = "blue",
    
    # --- Leyenda ---
    show_legend: bool = True,
    legend_loc: str = "best",
) -> Optional[plt.Figure]:
    """
    Plots the topology of a PowerFlowNetwork, distinguishing bus types and branch types.

    This function creates a graph representation where:
    - **Nodes** represent Buses, colored by their type (Slack, PV, PQ).
    - **Edges** represent Branches. Transformers are drawn with a distinct style (dashed/thicker).
    
    It supports displaying simulation results (Voltage magnitude and angle) if the network
    has been solved and `show_results` is True.

    Args:
        network (PowerFlowNetwork): The network instance to visualize.
        ax (Optional[plt.Axes]): A matplotlib axes object to plot on. If None, a new 
            figure and axes are created.
        title (Optional[str]): Title of the plot. Defaults to "Power Flow Network".
        show (bool): If True, calls `plt.show()` at the end. Defaults to True.
        
        node_size (int): Size of the bus nodes. Defaults to 500.
        node_color_map (Optional[Dict[BusTypes, str]]): Dictionary mapping BusTypes to color strings.
            Defaults to `{SLACK: 'red', PV: 'lightgreen', PQ: 'skyblue'}`.
        font_size (int): Font size for bus ID labels. Defaults to 9.
        label_font_weight (str): Font weight for bus ID labels. Defaults to "bold".
        show_labels (bool): If True, displays bus IDs inside the nodes. Defaults to True.
        
        edge_width (float): Width of standard transmission lines. Defaults to 1.5.
        transformer_edge_width (float): Width of transformer branches. Defaults to 2.5.
        edge_color (str): Color of standard transmission lines. Defaults to "gray".
        transformer_edge_color (str): Color of transformer branches. Defaults to "purple".
        show_branch_ids (bool): If True, displays the unique IDs of each branch on the edges.
            Defaults to True.
        branch_id_font_size (int): Font size for the branch ID labels. Defaults to 7.
        
        layout_seed (int): Seed for the spring layout algorithm to ensure reproducible positioning.
            Defaults to None, that means random.
        figsize (Tuple[int, int]): Size of the figure (width, height) if creating a new one.
            Defaults to (12, 8).
            
        show_results (bool): If True, attempts to display solved voltage data (V magnitude and angle)
            next to each node. Requires the network to have a valid solution state. Defaults to False.
        result_font_size (int): Font size for the result text. Defaults to 8.
        result_color (str): Color for the result text. Defaults to "blue".
        
        show_legend (bool): If True, displays a legend explaining node colors and edge styles.
            Defaults to True.
        legend_loc (str): Location of the legend (e.g., 'best', 'upper right'). Defaults to "best".

    Returns:
        Optional[plt.Figure]: The matplotlib Figure object if a new figure was created, 
        or None if an existing `ax` was provided.
    """
    
    # 1. Configuración de Figura/Ejes
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        # Si se proporciona ax, trabajamos sobre él directamente.
        # Asumimos que el usuario maneja la creación de la figura.
        pass

    # 2. Construir Grafo de NetworkX
    G = nx.Graph()
    
    # 2.1 Añadir Nudos (Buses)
    buses = network.get_all_buses()
    for bus in buses:
        # Guardar atributos para colorear y etiquetar después
        G.add_node(bus.id, type=bus.type, obj=bus)

    # 2.2 Añadir Ramas (Branches) y clasificarlas
    normal_edges = []
    transformer_edges = []
    
    branches = network.get_all_branches()
    for branch in branches:
        u, v = branch.bus1, branch.bus2
        
        # Comprobación de integridad: ¿existen los nudos?
        if not G.has_node(u) or not G.has_node(v):
            warnings.warn(
                f"Branch {branch.id} connects missing bus(es) ({u}-{v}). Skipping edge.",
                UserWarning
            )
            continue
            
        # Clasificar según el tipo de instancia
        if isinstance(branch, (SimpleTransformer, PiTransformer)):
            transformer_edges.append((u, v))
            G.add_edge(u, v, type='transformer', obj=branch)
        else:
            normal_edges.append((u, v))
            G.add_edge(u, v, type='line', obj=branch)

    # 3. Determinar Layout
    # Usamos spring_layout por defecto para grafos genéricos sin coordenadas
    pos = nx.spring_layout(G, seed=layout_seed)

    # 4. Preparar Estilos Visuales
    
    # 4.1 Colores de Nudos
    default_colors = {
        BusTypes.SLACK: "red",
        BusTypes.PV: "lightgreen",
        BusTypes.PQ: "skyblue"
    }
    if node_color_map:
        default_colors.update(node_color_map)
        
    node_colors_list = []
    for node_id in G.nodes():
        bus_type = G.nodes[node_id]['type']
        node_colors_list.append(default_colors.get(bus_type, "gray"))

    # 5. Dibujar Elementos
    
    # 5.1 Dibujar Ramas (Capa 1: Fondo)
    nx.draw_networkx_edges(
        G, pos,
        edgelist=normal_edges,
        edge_color=edge_color,
        width=edge_width,
        style="solid",
        ax=ax
    )
    
    nx.draw_networkx_edges(
        G, pos,
        edgelist=transformer_edges,
        edge_color=transformer_edge_color,
        width=transformer_edge_width,
        style="dashed", # Estilo distintivo para transformadores
        ax=ax
    )

    # 5.2 Dibujar Nudos (Capa 2: Medio)
    nx.draw_networkx_nodes(
        G, pos,
        node_color=node_colors_list,
        node_size=node_size,
        edgecolors='black', # Contorno
        ax=ax
    )

    # 5.3 Dibujar Etiquetas (Capa 3: Superior)
    if show_labels:
        nx.draw_networkx_labels(
            G, pos,
            font_size=font_size,
            font_weight=label_font_weight,
            font_color="black",
            ax=ax
        )

    # 5.4 Dibujar IDs de Ramas (Opcional)
    if show_branch_ids:
        # Consolidamos IDs para ramas paralelas para evitar texto solapado
        edge_labels = {}
        for branch in network.get_all_branches():
            u, v = branch.bus1, branch.bus2
            
            # Solo etiquetamos ramas que existen en nuestro grafo (G)
            if not G.has_edge(u, v):
                continue
                
            # Usamos una tupla ordenada como clave para asegurar consistencia no dirigida
            pair = tuple(sorted((u, v)))
            if pair not in edge_labels:
                edge_labels[pair] = str(branch.id)
            else:
                edge_labels[pair] += f", {branch.id}"
        
        nx.draw_networkx_edge_labels(
            G, pos,
            edge_labels=edge_labels,
            font_size=branch_id_font_size,
            ax=ax,
            rotate=False # Mantener texto horizontal para mejor legibilidad
        )

    # 6. Mostrar Resultados (Opcional)
    if show_results:
        # Comprobar si la red tiene datos de solución
        # Accedemos a los arrays internos de la red.
        # Idealmente usaríamos getters públicos, pero para visualización esto es eficiente.
        # Nota: Esto depende de que network._v_arr y network._theta_arr estén actualizados.
        
        try:
            # Intentar obtener los resultados resueltos.
            # Si la red no se ha resuelto, esto podría mostrar valores iniciales o ceros.
            # Asumimos que el usuario sabe lo que hace si pone show_results=True.
            
            # Dado que acceder a miembros privados es arriesgado, usamos los arrays internos
            # que PowerFlowNetwork mantiene actualizados en _last_v_sol_arr
            
            if network._last_v_sol_arr is None or network._last_theta_sol_arr is None:
                warnings.warn("Network has no solution state (run a solver first). Skipping results display.")
            else:
                # Iterar y anotar
                for idx, bus_id in enumerate(network._idx_to_id):
                    if bus_id not in pos: continue
                    
                    x, y = pos[bus_id]
                    v_mag = network._last_v_sol_arr[idx]
                    theta_rad = network._last_theta_sol_arr[idx]
                    theta_deg = np.degrees(theta_rad)
                    
                    label_text = f"{v_mag:.3f}∠{theta_deg:.1f}°"
                    
                    ax.text(
                        x, y - 0.1, # Desplazamiento debajo del nudo
                        label_text,
                        ha='center',
                        va='top',
                        fontsize=result_font_size,
                        color=result_color,
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, ec='none')
                    )
        except Exception as e:
            warnings.warn(f"Could not display results: {e}")

    # 7. Toques Finales
    if title:
        ax.set_title(title, fontsize=14)
    
    ax.axis("off") # Ocultar ejes/marco

    # 8. Leyenda
    if show_legend:
        legend_handles = []
        
        # Leyenda de Nudos
        for b_type, color in default_colors.items():
            legend_handles.append(
                plt.Line2D(
                    [0], [0], 
                    marker='o', 
                    color='w', 
                    label=f"Bus {b_type.name}",
                    markerfacecolor=color, 
                    markersize=10,
                    markeredgecolor='black'
                )
            )
            
        # Leyenda de Ramas
        legend_handles.append(
            plt.Line2D([0], [0], color=edge_color, lw=2, linestyle="solid", label="Line")
        )
        legend_handles.append(
            plt.Line2D([0], [0], color=transformer_edge_color, lw=2, linestyle="dashed", label="Transformer")
        )
        
        ax.legend(handles=legend_handles, loc=legend_loc, frameon=True)

    # 9. Salida
    if show:
        plt.show()
        
    return fig

