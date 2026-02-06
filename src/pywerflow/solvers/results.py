from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
import numpy as np

# Usamos TYPE_CHECKING para que 'matplotlib' no sea una dependencia obligatoria
if TYPE_CHECKING:
    from matplotlib.figure import Figure
    
@dataclass(frozen=True, slots=True)
class SolverMetaResult:
    """
    Standardized result metadata container for all power flow solvers.
    Carries diagnostic information rather than the raw voltage vector.
    """
    # --- 1. ESTADO PRINCIPAL (Obligatorio) ---
    success: bool
    """True if the solver converged mathematically and physically; False otherwise."""

    method_name: str
    """Identifier of the specific algorithm used (e.g., 'Gauss-Seidel', 'Newton-Raphson')."""

    message: str
    """Human-readable description of the outcome"""

    # --- 2. RENDIMIENTO ALGORÍTMICO (Opcional / None por defecto) ---
    iterations: int | None = None
    """Steps performed by the iterative solver."""

    # execution_time: float | None = None
    # """Time spent in the numerical engine (seconds)."""

    # --- 3. PRECISIÓN NUMÉRICA (Opcional / None por defecto) ---
    final_error: float | None = None
    """The final error value reached by the solver's stopping criterion."""

    tolerance_used: float | None = None
    """The tolerance threshold used to determine convergence."""

    error_history: np.ndarray | list | None = None
    """The error history of the method throughout its iterations, if the method supports it."""

    # --- 4. INFORMACIÓN ADICIONAL ---
    extras: dict[str] = field(default_factory=dict) # Diccionario vacío
    """
    Dictionary containing any additional metadata or specific parameters.
    Can hold method-specific metrics (e.g., 'alpha') or shared diagnostic data.
    """



    def plot_convergence(self, **kwargs) -> "Figure | None":
        """
        Generates a convergence plot using the solver's error history.
        
        It automatically sets up the axes, titles, and tolerance lines based on the 
        solver metadata, but allows full override via kwargs.

        Args:
            **kwargs: Arguments passed directly to `plot_curve`.
                      Examples: `filepath="conv.png"`, `title="My Title"`, `color="magenta"`.

        Returns:
            matplotlib.figure.Figure | None: The figure object, or None if no history exists.
        
        Raises:
            ValueError: If the solver did not produce an error history.
            ImportError: If 'matplotlib' is not installed in the environment.
        """
        # 1. Validación de Datos (Defensiva)
        if self.error_history is None or len(self.error_history) == 0:
            raise ValueError(
                f"The method '{self.method_name}' did not produce an error history, "
                "or it was not recorded in the results."
            )

        # 2. Check de Dependencia Externa (Soft Dependency)
        try:
            import matplotlib.pyplot
        except ImportError as e:
            raise ImportError(
                "Optional dependency 'matplotlib' is required to use .plot_convergence(). "
                "Please install it via 'pip install matplotlib'."
            ) from e

        # 3. Importación del Módulo Interno
        # Hacemos esto FUERA del try/except anterior.
        # Si esto falla, es un bug de la librería (ruta incorrecta), no falta de dependencia.
        from pywerflow.plotting.plot_curve import plot_curve

        # 4. Preparación de Ejes
        y_data = np.asarray(self.error_history)
        # Eje X basado en iteraciones naturales (1, 2, 3...)
        x_data = np.arange(1, len(y_data) + 1)

        # 5. Configuración de Defaults Inteligentes
        plot_args = {
            "y_data": y_data,
            "x_data": x_data,
            "title": f"Error Evolution: {self.method_name}",
            "xlabel": "Iteration",
            "ylabel": "Max Error",
            "scale": "log",
            "grid": "auto",
            "line_fmt": "-", 
            "linewidth": 1.5,
            "info": self.extras
        }

        # 6. Inyección de Tolerancia (si existe en los metadatos)
        if self.tolerance_used is not None:
            plot_args["hline"] = self.tolerance_used
            plot_args["hline_label"] = f"Tolerance ({self.tolerance_used:.1e})"

        # 7. Merge: Los kwargs del usuario tienen prioridad sobre los defaults
        plot_args.update(kwargs)

        # 8. Llamada al motor gráfico
        return plot_curve(**plot_args)