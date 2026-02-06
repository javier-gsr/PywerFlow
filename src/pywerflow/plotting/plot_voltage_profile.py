from typing import Sequence, Optional, Any
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnchoredText

from pywerflow.buses.solved_buses import SolvedBus

def plot_voltage_profile(
    bus_data: Sequence[SolvedBus] | Sequence[Sequence[SolvedBus]],
    labels: str | Sequence[str] | None = None,
    
    # --- Configuración de los datos ---
    use_kv: bool = False,
    sort_by_id: bool = True,
    
    # --- Configuración de los ejes ---
    ylim: tuple[float, float] | None = None,
    xlim: tuple[float, float] | None = None,
    ylabel: str | None = None,
    xlabel: str = "Bus ID",
    title: str = "Voltage Profile",
    
    # --- Estilo visual ---
    figsize: tuple[int, int] = (12, 6),
    grid: bool | str = "both",
    line_styles: str | Sequence[str] = "-",
    markers: str | Sequence[str] = "o",
    colors: str | Sequence[str] | None = None,
    alpha: float = 0.8,
    linewidth: float = 1.5,
    markersize: float = 4.0,
    
    # --- Líneas de referencia ---
    hline: float | list[float] | None = None,
    hline_color: str = "red",
    hline_style: str = "--",
    
    # --- Cuadro de metadatos ---
    info: dict[str, Any] | str | None = None,
    info_loc: str = "lower left",
    
    # --- Guardado y visualización ---
    filepath: str | None = None,
    dpi: int = 300,
    show: bool = True,
    
    # --- Leyenda ---
    show_legend: bool = True,
    legend_loc: str = "best",
    
    **kwargs
) -> Figure | None:
    """
    Plots the voltage profile (magnitude) for one or multiple scenarios.

    This function visualizes voltage magnitudes across buses. It supports multiple 
    datasets (e.g., scenarios with different load levels), automatic unit conversion 
    (p.u. to kV), and extensive customization for publication-quality figures.

    Args:
        bus_data (Sequence[SolvedBus] | Sequence[Sequence[SolvedBus]]): 
            A single list of SolvedBus objects OR a list of lists of SolvedBus objects.
            Each list represents a scenario/profile line.
        
        labels (str | Sequence[str] | None): 
            Label(s) for the legend. 
            - If a single string, it's used for the single profile.
            - If a list, must match the number of profiles in `bus_data`.
            - If None, defaults to "Profile 1", "Profile 2"...

        use_kv (bool): 
            If True, plots voltage in kV. Requires all buses to have `V_base` defined.
            Raises ValueError if any bus lacks `V_base`.
            Defaults to False (p.u.).

        sort_by_id (bool):
            If True, sorts buses by ID before plotting to ensure a coherent X-axis.
            Defaults to True.

        ylim (tuple[float, float] | None): 
            Fixed Y-axis limits (min, max). Useful for comparing multiple plots 
            on the same scale (e.g., (0.8, 1.2)). Defaults to auto-scale.

        xlim (tuple[float, float] | None): 
            Fixed X-axis limits. Defaults to auto-scale.

        ylabel (str | None): 
            Custom Y-axis label. If None, defaults to "Voltage (p.u.)" or "Voltage (kV)".

        xlabel (str): 
            X-axis label. Defaults to "Bus ID".

        title (str): 
            Main figure title. Defaults to "Voltage Profile".

        figsize (tuple[int, int]): 
            Figure size in inches. Defaults to (12, 6).

        grid (bool | str): 
            Grid configuration ("major", "minor", "both", True, False). Defaults to "both".

        line_styles (str | Sequence[str]): 
            Matplotlib line style(s) (e.g., '-', '--', ':'). 
            Can be a single string (applied to all) or a list matching profiles.

        markers (str | Sequence[str]): 
            Marker style(s) (e.g., 'o', 's', '^'). 
            Can be a single string or a list matching profiles.

        colors (str | Sequence[str] | None): 
            Color(s) for the profiles. If None, uses Matplotlib's default cycle.

        alpha (float): 
            Transparency of the lines/markers. Defaults to 0.8.

        linewidth (float): 
            Width of the profile lines. Defaults to 1.5.

        markersize (float): 
            Size of the markers. Defaults to 4.0.

        hline (float | list[float] | None): 
            Y-coordinate(s) for horizontal reference lines (e.g., limits 0.95, 1.05).

        hline_color (str): 
            Color for reference lines. Defaults to "red".

        hline_style (str): 
            Line style for reference lines. Defaults to "--".

        info (dict | str | None): 
            Metadata to display in an anchored text box (e.g., simulation params).

        info_loc (str): 
            Location of the metadata box. Defaults to "lower left".

        filepath (str | None): 
            Path to save the figure. If None, not saved.

        dpi (int): 
            Resolution for saved figure. Defaults to 300.

        show (bool): 
            Whether to call `plt.show()`. Defaults to True.

        show_legend (bool): 
            Whether to display the legend. Defaults to True.

        legend_loc (str): 
            Legend location. Defaults to "best".

        **kwargs: 
            Additional keyword arguments passed to `ax.plot`.

    Returns:
        matplotlib.figure.Figure | None: The Figure object, or None if input data is empty.
    
    Raises:
        ValueError: If `use_kv` is True but a bus misses `V_base`.
    """

    # --- 1. Normalizar entrada ---
    # Paso todo a lista de listas para procesarlo igual
    if not bus_data:
        return None
    
    # Miro si viene un perfil solo o varios
    # Si el primer elemento es SolvedBus, es un perfil único
    is_single_profile = isinstance(bus_data[0], SolvedBus)
    
    if is_single_profile:
        profiles = [bus_data]
    else:
        profiles = bus_data

    num_profiles = len(profiles)

    # --- 2. Normalizar etiquetas y estilos ---
    if labels is None:
        profile_labels = [f"Profile {i+1}" for i in range(num_profiles)]
    elif isinstance(labels, str):
        profile_labels = [labels] * num_profiles # Si viene un string solo, asumo que es para el perfil único
    else:
        profile_labels = list(labels)
        if len(profile_labels) < num_profiles:
            # Relleno etiquetas si faltan
            profile_labels.extend([f"Profile {i+1}" for i in range(len(profile_labels), num_profiles)])

    # Helper para repetir estilos si solo me pasan uno
    def _expand_style(style, count):
        if isinstance(style, str):
            return [style] * count
        return list(style)

    l_styles = _expand_style(line_styles, num_profiles)
    m_styles = _expand_style(markers, num_profiles)
    
    # --- 3. Preparar la figura ---
    fig, ax = plt.subplots(figsize=figsize)

    # --- 4. Pintar los perfiles ---
    
    # Guardo las X para poner los ticks bien luego
    all_x_ticks = set()

    for i, buses in enumerate(profiles):
        # Ordeno por ID si hace falta para que no salga un zig-zag raro
        if sort_by_id:
            buses = sorted(buses, key=lambda b: b.id)
        
        x_vals = [b.id for b in buses]
        all_x_ticks.update(x_vals)
        
        y_vals = []
        for bus in buses:
            v_val = bus.V
            
            if use_kv:
                if bus.V_base is None:
                    raise ValueError(
                        f"Bus {bus.id} is missing 'V_base', but 'use_kv=True' was requested."
                    )
                v_val *= bus.V_base
            
            y_vals.append(v_val)
        
        # Manejo de colores
        c = colors[i] if (colors and i < len(colors)) else None
        
        ax.plot(
            x_vals, y_vals,
            label=profile_labels[i],
            linestyle=l_styles[i % len(l_styles)],
            marker=m_styles[i % len(m_styles)],
            color=c,
            alpha=alpha,
            linewidth=linewidth,
            markersize=markersize,
            **kwargs
        )

    # --- 5. Configurar los ejes ---
    
    # Lógica para la etiqueta de la Y
    if ylabel is None:
        unit = "kV" if use_kv else "p.u."
        ylabel = f"Voltage Magnitude ({unit})"
    
    ax.set_ylabel(ylabel, fontsize=10, fontweight='bold')
    ax.set_xlabel(xlabel, fontsize=10, fontweight='bold')
    ax.set_title(title, fontsize=12, fontweight='bold')

    if ylim:
        ax.set_ylim(ylim)
    if xlim:
        ax.set_xlim(xlim)

    # Rejilla
    if grid == "both" or grid is True:
        ax.grid(True, which="major", alpha=0.5)
        ax.grid(True, which="minor", alpha=0.2, linestyle=":")
        ax.minorticks_on()
    elif grid:
        ax.grid(True, which=grid, alpha=0.5)

    # Ticks de la X: si hay pocos nudos, pongo los IDs uno a uno
    if len(all_x_ticks) <= 30:
        sorted_ticks = sorted(list(all_x_ticks))
        ax.set_xticks(sorted_ticks)

    # --- 6. Líneas de referencia ---
    if hline is not None:
        lines = hline if isinstance(hline, (list, tuple)) else [hline]
        for y_ref in lines:
            ax.axhline(y_ref, color=hline_color, linestyle=hline_style, alpha=0.7)

    # --- 7. Caja de información ---
    if info:
        if isinstance(info, dict):
            text_str = "\n".join([f"{k}: {v}" for k, v in info.items()])
        else:
            text_str = str(info)
        
        anchored_box = AnchoredText(
            text_str,
            loc=info_loc,
            frameon=True,
            pad=0.5,
            prop=dict(fontsize=9, fontfamily='monospace') # Monospace queda más técnico
        )
        anchored_box.patch.set_boxstyle("round,pad=0.5,rounding_size=0.2")
        anchored_box.patch.set_alpha(0.8)
        anchored_box.patch.set_facecolor("white")
        ax.add_artist(anchored_box)

    # --- 8. Leyenda ---
    if show_legend:
        ax.legend(loc=legend_loc, frameon=True, fontsize="medium")

    fig.tight_layout()

    # --- 9. Salida ---
    if filepath:
        fig.savefig(filepath, dpi=dpi, bbox_inches="tight", pad_inches=0.02)
        print(f"Voltage profile saved to: {filepath}")

    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig