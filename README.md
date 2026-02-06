# PywerFlow
Librería hecha en Python para mi TFG. Ofrece herramientas útiles para el análisis y resolución de redes y del flujo de cargas.

> ⚠️ **Nota de Compatibilidad:** Actualmente, este proyecto está construido y probado principalmente para **Windows (x64)**. El soporte para Linux o macOS requiere compilación manual del motor C y no está garantizado en esta versión.

## Instalación

**Requisitos:**
Asegúrate de tener Python 3.11 o superior instalado y accesible desde la línea de comandos con el comando `python`.

**Pasos para la instalación en modo editable:**

1.  **Clona el repositorio:**
    ```bash
    git clone https://github.com/javier-gsr/PywerFlow.git
    ```
2.  **Navega al directorio del proyecto:**
    ```bash
    cd PywerFlow
    ```
3.  **Crea un entorno virtual:**
    Se recomienda usar un entorno virtual para aislar las dependencias del proyecto.
    ```bash
    python -m venv venv
    ```
4.  **Activa el entorno virtual:**
    -   **En Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    -   **En macOS y Linux:**
        ```bash
        source venv/bin/activate
        ```
5.  **Instala las dependencias en modo editable:**
    Esto instalará la librería y sus dependencias, permitiéndote realizar cambios en el código fuente.
    ```bash
    pip install -e .
    ```

---

## Funciones escritas en C

Para maximizar el rendimiento, algunos algoritmos iterativos pesados (como Gauss-Seidel) están escritos en C y se ejecutan mediante una librería dinámica (`.dll`).

### Uso Básico
El repositorio **ya incluye el binario compilado** (`src/pywerflow/bin/c_methods.dll`), por lo que **no necesitas instalar compiladores** ni hacer pasos extra para usar la librería en Windows x64. Simplemente instala el paquete con `pip` y úsalo.

### Recompilación Manual (Desarrolladores)
Si modificas el código fuente C (`src/pywerflow/solve_methods/**/*.c`) o necesitas regenerar la DLL por cualquier motivo, puedes usar el script de construcción incluido.

**Requisitos para compilar:**
* **GCC:** Debes tener un compilador C instalado (se recomienda **MinGW-w64** en Windows) y añadido a las variables de entorno (`PATH`).
* Comprueba que tienes acceso ejecutando `gcc --version` en tu terminal.

**Cómo compilar:**
Ejecuta el siguiente script desde la raíz del proyecto:
```bash
python build_win_dll.py
```

Si todo va bien, verás un mensaje [SUCCESS] indicando que la DLL se ha actualizado correctamente en la carpeta bin.
