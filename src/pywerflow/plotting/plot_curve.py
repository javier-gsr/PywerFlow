from warnings import warn
from collections.abc import Sequence
from typing import Any
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnchoredText

def plot_curve(
    y_data: np.ndarray | list,
    x_data: np.ndarray | list | None = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    scale: str = "linear",
    figsize: tuple[int, int] = (10, 6),
    # --- Opciones de Guardado y Visualización ---
    filepath: str | None = None,
    dpi: int = 300,
    show: bool = True,
    # --- Líneas de Referencia ---
    hline: float | list[float] | None = None,
    hline_label: str | list[str] | None = None,   # CORRECCIÓN
    vline: float | list[float] | None = None,
    vline_label: str | list[str] | None = None,   # CORRECCIÓN
    # --- Caja de Metadatos ---
    info: dict[str, Any] | str | None = None,
    info_loc: str = "lower left",
    # --- Estilo ---
    grid: bool | str = "auto",
    line_fmt: str = "-",
    **kwargs
) -> Figure | None:
    """
    Generates a robust, highly customizable 2D plot using Matplotlib's Object-Oriented API.

    This utility is designed for scientific visualization, offering intelligent defaults 
    (such as automatic marker suppression for high-density data), built-in support for 
    multiple reference lines with grouped legends, and streamlined file saving.

    Args:
        y_data (np.ndarray | list): 
            The dependent variable data (Y-axis). Must be a 1D sequence of numbers.
            If the array is empty, the function logs a warning and returns None.

        x_data (np.ndarray | list | None, optional): 
            The independent variable data (X-axis). 
            - If None: Automatically generates a sequential index (0, 1, ..., N-1).
            - If provided: Must be a 1D array matching the length of `y_data`.
            Defaults to None.

        title (str, optional): 
            Main title of the figure. Defaults to "".

        xlabel (str, optional): 
            Label for the X-axis. Defaults to "".

        ylabel (str, optional): 
            Label for the Y-axis. Defaults to "".

        scale (str, optional): 
            Y-axis scaling. Valid options: {'linear', 'log', 'symlog', 'logit'}.
            - If 'log' is chosen and data contains non-positive values, a warning is issued 
              instead of an error, allowing Matplotlib to mask invalid points.
            Defaults to "linear".

        figsize (tuple[int, int], optional): 
            Figure dimensions in inches (width, height). Defaults to (10, 6).

        filepath (str | None, optional):
            File path to save the plot (e.g., "plots/results.png"). 
            If None, the plot is not saved to disk.
            The format is inferred from the file extension.
            Defaults to None.

        dpi (int, optional):
            Resolution in Dots Per Inch for the saved file. 
            High values (e.g., 300) are recommended for publication quality.
            Only applies if `filepath` is provided.
            Defaults to 300.

        show (bool, optional):
            Whether to open the interactive plot window (`plt.show()`).
            Set to False to generate/save plots in the background without blocking execution.
            Defaults to True.

        hline (float | list[float] | None, optional): 
            Y-coordinate(s) for horizontal reference line(s).
            Can be a single float or a list of floats.
            Drawn as red dashed lines (`--`) by default.
            Defaults to None.

        hline_label (str | list[str] | None, optional): 
            Legend label(s) for the horizontal reference line(s).
            - If a single string is provided but `hline` is a list, the label is assigned 
              only to the first line. This groups all lines under a single legend entry.
            - If a list is provided, it attempts to map labels one-to-one.
            Defaults to None.

        vline (float | list[float] | None, optional): 
            X-coordinate(s) for vertical reference line(s).
            Can be a single float or a list of floats.
            Drawn as gray dash-dot lines (`-.`) by default.
            Defaults to None.

        vline_label (str | list[str] | None, optional): 
            Legend label(s) for the vertical reference line(s).
            Follows the same grouping logic as `hline_label`.
            Defaults to None.
        
        info (dict[str, Any] | str | None, optional):
            Additional metadata to display in a small text box within the plot area.
            - If a dictionary: Formats as "Key: Value" lines.
            - If a string: Displays the text directly.
            Useful for showing simulation parameters (e.g., {'alpha': 1.5}).
            Defaults to None.

        info_loc (str, optional):
            Location code for the info text box. 
            Common options: 'upper right', 'upper left', 'lower right', 'lower left'.
            Defaults to "lower left".
        
        grid (bool | str, optional): 
            Configuration for grid visibility.
            - "auto": Enables 'both' (major+minor) grids for log/symlog scales, and 'major' for linear.
            - True: Enables major grid.
            - False: Disables grid.
            - str: Specific Matplotlib grid setting (e.g., "major", "minor", "both").
            Defaults to "auto".

        line_fmt (str, optional): 
            Matplotlib format string defining line style, marker, and color (e.g., 'o-' or 'g--').
            Smart Logic: If no marker is explicitly set here or in `kwargs`:
            - Data points <= 150: Adds markers ('o') for visibility.
            - Data points > 150: Removes markers to prevent visual clutter.
            Defaults to "-".

        **kwargs: 
            Additional keyword arguments passed to `ax.plot()`.
            Common examples: `color`, `linewidth`, `alpha`, `marker`, `markersize`, `label`.

    Returns:
        matplotlib.figure.Figure | None: 
            The Figure object created. Returns None if input data was empty.
            Returning the Figure allows for further post-processing or external saving.

    Raises:
        ValueError: If `y_data` or `x_data` are not 1D arrays, or if their shapes do not match.
        ValueError: If an invalid `scale` option is provided.
    """

    # ------------------------------------------------------------------
    # 1. Preparación y validación de datos
    # ------------------------------------------------------------------
    y = np.asarray(y_data)

    if y.size == 0:
        warn("'y_data' is empty. Plot skipped.")
        return None

    if y.ndim != 1:  # CORRECCIÓN
        raise ValueError("y_data must be a 1D array.")

    N = y.size

    if x_data is None:
        x = np.arange(N)
    else:
        x = np.asarray(x_data)
        if x.ndim != 1:  # CORRECCIÓN
            raise ValueError("x_data must be a 1D array.")
        if x.size != N:
            raise ValueError(
                f"Shape mismatch: x_data has length {x.size}, y_data has length {N}."
            )

    # ------------------------------------------------------------------
    # 2. Validación de escala
    # ------------------------------------------------------------------
    valid_scales = {"linear", "log", "symlog", "logit"}
    if scale not in valid_scales:
        raise ValueError(f"Invalid scale '{scale}'. Valid options: {valid_scales}")

    if scale == "log" and np.any(y <= 0):  # CORRECCIÓN
        warn("Log scale requested but y_data contains non-positive values.")

    # ------------------------------------------------------------------
    # 3. Lógica de marcadores inteligentes
    # ------------------------------------------------------------------
    marker_chars = "o.v^<>*+x|dDsphH,_"
    user_specified_marker = (
        "marker" in kwargs or any(c in line_fmt for c in marker_chars)
    )

    if not user_specified_marker:
        if N > 150 and line_fmt == "o-":
            line_fmt = "-"
        elif N <= 150 and line_fmt == "-":
            line_fmt = "o-"

    # Valores por defecto razonables
    kwargs.setdefault("linewidth", 1.5)

    user_provided_label = "label" in kwargs  # CORRECCIÓN

    # ------------------------------------------------------------------
    # 4. Creación de figura y plot principal
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=figsize)  # CORRECCIÓN: usar API orientada a objetos
    ax.plot(x, y, line_fmt, **kwargs)

    # ------------------------------------------------------------------
    # 5. Líneas de referencia
    # ------------------------------------------------------------------
    def _plot_ref_lines(values, labels, horizontal: bool):
        if values is None:
            return

        vals = values if isinstance(values, Sequence) and not isinstance(values, str) else [values]

        if labels is None:
            labs = [None] * len(vals)
        elif isinstance(labels, str):
            labs = [labels] + [None] * (len(vals) - 1)
        else:
            labs = list(labels)
            if len(labs) < len(vals):
                labs += [None] * (len(vals) - len(labs))

        for v, l in zip(vals, labs):
            if horizontal:
                ax.axhline(
                    y=v, color="red", linestyle="--",
                    alpha=0.7, linewidth=1.2, label=l
                )
            else:
                ax.axvline(
                    x=v, color="gray", linestyle="-.",
                    alpha=0.7, linewidth=1.2, label=l
                )

    _plot_ref_lines(hline, hline_label, horizontal=True)
    _plot_ref_lines(vline, vline_label, horizontal=False)



    # ------------------------------------------------------------------
    # 6. Caja de Información (Metadata Box)
    # ------------------------------------------------------------------
    if info:
        # 1. Formatear el texto
        if isinstance(info, dict):
            # Convierte {'alpha': 1.5, 'tol': 1e-9} en:
            # alpha: 1.5
            # tol: 1e-9
            text_str = "\n".join([f"{k}: {v}" for k, v in info.items()])
        else:
            text_str = str(info)
        
        # 2. Crear la caja anclada
        anchored_box = AnchoredText(
            text_str,
            loc=info_loc,
            frameon=True,
            pad=0.5,
            prop=dict(fontsize=9, fontfamily='monospace') # Monospace queda muy "técnico/pro"
        )
        # Estilo de la cajita (transparente para no tapar mucho)
        anchored_box.patch.set_boxstyle("round,pad=0.5,rounding_size=0.2")
        anchored_box.patch.set_alpha(0.8) 
        anchored_box.patch.set_facecolor("white")
        anchored_box.patch.set_edgecolor("gray")
        
        ax.add_artist(anchored_box)
    # ------------------------------------------------------------------
    # 7. Escalas y grid
    # ------------------------------------------------------------------
    ax.set_yscale(scale)

    if grid == "auto":
        grid_which = "both" if scale in {"log", "symlog", "logit"} else "major"  # CORRECCIÓN
        ax.grid(True, which=grid_which, alpha=0.4)
    elif isinstance(grid, bool) and grid:
        ax.grid(True, alpha=0.4)
    elif isinstance(grid, str):
        ax.grid(True, which=grid, alpha=0.4)

    # ------------------------------------------------------------------
    # 8. Etiquetas, ticks y leyenda
    # ------------------------------------------------------------------
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    if N < 15 and x_data is None:
        ax.set_xticks(x)

    if hline is not None or vline is not None or user_provided_label:
        ax.legend(loc="best", frameon=True, fontsize="small")  # CORRECCIÓN

    fig.tight_layout()

    # ------------------------------------------------------------------
    # 9. Guardado y visualización
    # ------------------------------------------------------------------
    if filepath:
        fig.savefig(filepath, dpi=dpi, bbox_inches="tight", pad_inches=0.02)
        print(f"Plot saved successfully to: {filepath}")

    if show:
        plt.show()
    else:
        plt.close(fig)

    return fig


