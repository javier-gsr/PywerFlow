from pathlib import Path

def get_unique_results_dir(base_dir: Path) -> Path:
    """Busca un nombre de directorio que no exista añadiendo sufijos numéricos."""
    if not base_dir.exists():
        return base_dir
    
    counter = 2
    while True:
        new_dir = base_dir.with_name(f"{base_dir.name}_{counter}")
        if not new_dir.exists():
            return new_dir
        counter += 1
