import numpy as np
import numpy as np
from scipy.sparse import csr_matrix, diags, bmat
from scipy.sparse.linalg import spsolve
from pywerflow.solvers.results import SolverMetaResult

METHOD_NAME = "Newton-Raphson"
EXTRAS = []


def newton_raphson(
    Ymatrix: np.ndarray,
    p_arr: np.ndarray,
    q_arr: np.ndarray,
    v0_arr: np.ndarray,
    theta0_arr: np.ndarray,
    pq_idxs: np.ndarray,
    pv_idxs: np.ndarray,
    tol: float,
    max_it: int,
) -> tuple[np.ndarray, SolverMetaResult]:
    """
    Solves the Power Flow problem using the Newton-Raphson method (Polar Coordinates).

    This implementation uses the Modified Jacobian formulation where the voltage 
    magnitude corrections are normalized (Delta U / U).

    Args:
        Ymatrix (csr_matrix | np.ndarray): The complex Nodal Admittance Matrix (Y_bus) 
            of the system. Shape (N, N). If a dense array is provided, it will be 
            converted to a scipy sparse matrix.
        p_arr (np.ndarray): Net active power injections (Generation - Load) for 
            all buses in per-unit. Shape (N,). Used as the target P values.
        q_arr (np.ndarray): Net reactive power injections (Generation - Load) for 
            all buses in per-unit. Shape (N,). Used as the target Q values.
        v0_arr (np.ndarray): Initial voltage magnitudes (p.u.). Shape (N,). 
            This array is modified in-place during execution. 
            For PQ nodes, it acts as the initial guess and holds the solution.
            For PV/Slack nodes, it holds the fixed setpoints.
        theta0_arr (np.ndarray): Initial voltage angles (radians). Shape (N,). 
            This array is modified in-place during execution.
            For PQ/PV nodes, it acts as the initial guess and holds the solution.
            For Slack nodes, it holds the fixed reference angle.
        pq_idxs (np.ndarray): Array of integer indices identifying PQ buses.
        pv_idxs (np.ndarray): Array of integer indices identifying PV buses.
        tol (float, optional): Convergence tolerance. The method succeeds if the 
            maximum absolute mismatch is less than this value. 
        max_it (int, optional): Maximum number of iterations allowed. 

    Returns:
        tuple[np.ndarray, SolverMetaResult]: A tuple containing:
            1. The final complex voltage array (N,) constructed as V * exp(j*theta).
            2. A metadata object containing success status, message, iteration count, 
               and final error.
    """
    max_it = int(max_it)
    
    # 1. Preparación de Estructuras Dispersas
    # Convertimos Ybus a CSR (Sparse) para operaciones matriciales rápidas
    Ybus_csr = csr_matrix(Ymatrix)

    # Creamos un mapeo indices del vector X y delta X (que se corresponden con thetas y u incógnitas) 
    # A los vectores v0_arr y theta0_arr que contienen todas (algunas hay que actualizarlas durante el bucle y otras no)
    # implememntar aqui <--
    # Mapeo de indices )
    # Calculamos dimensiones para saber dónde cortar el vector de resultados dx luego
    n_pv = len(pv_idxs)
    n_pq = len(pq_idxs)
    n_pvpq = n_pv + n_pq
    theta_unknown_idxs = np.concatenate((pv_idxs, pq_idxs))
    v_unknown_idxs = pq_idxs

    # Hay que crear un vector pq_sch que contiene
    # - Las primeras p filas son P correspondientes a nudos PV
    # - Las siguientes q filas son P correspondientes a nudos PQ
    # - Las siguientes q filas son Q correspondientes a nudos PQ
    pq_sch = np.concatenate((
                            p_arr[pv_idxs], 
                            p_arr[pq_idxs], 
                            q_arr[pq_idxs]
                            ))

    # Inicialización de variables de estado del solver
    max_error = tol + 1.0
    success = False
    final_message = f"The method has reached the iteration limit ({max_it}). It diverged."
    
    final_iterations = 0
    error_history = []

    for i in range(1, max_it+1):
        # 1. Cacular el nuevo vector f(x) usando la x de la iteración anterior
        # Se calcula usando v0_arr y theta0_arr utilizando las ecs del flujo de cargas para:
        #   - Calcular las nuevas P para los nudos PQ y PV
        #   - Calcular las nuevas Q para los nudos PQ
        V_complex = v0_arr * np.exp(1j * theta0_arr)
        S_calc_all = V_complex * np.conj( Ybus_csr.dot(V_complex) )
        # E. Ensamblaje del vector calculado 'f(x)' con la estructura requerida
        pq_calc = np.concatenate((
            S_calc_all[pv_idxs].real, 
            S_calc_all[pq_idxs].real, 
            S_calc_all[pq_idxs].imag,
        ))
        pq_mismatch = pq_calc - pq_sch # valor de f(x) en esta iteración


        # Paso intermedio: Revision del error
        # Máximo de los valores absolutos
        max_error = np.max(np.abs(pq_mismatch))
        
        error_history.append(float(max_error))

        # Si ya hemos convergido con este cálculo, salimos antes de resolver Jacobiano
        if max_error <= tol:
            success = True
            final_message = "The method has converged."
            final_iterations = i-1  # Realmente esta iteracion no se ha completado asi que no se cuenta
            break

        # 2. Calcular la matriz Jacobiana en esta iteración.
        
        # Matriz diagonal de V_complex y su conjugado: el vector (N,) actualizado en la iteracion anterior
        diagV = diags(V_complex)
        diagV_conj = diags(np.conj(V_complex))
        
        # Matriz Auxiliar = diag(V) * conj(Ybus) * diag(V*)
        # Esta matriz contiene los términos V_i * V_j * Y_ij * ... necesarios para las derivadas
        aux_matrix = diagV @ Ybus_csr.conj() @ diagV_conj
        
        # Matrices Diagonales de Potencia
        # Usamos las potencias calculadas en el paso 1 (para todo el sistema)
        # S_calc_all contiene las potencias complejas de TODOS los nudos
        diagP = diags(S_calc_all.real)
        diagQ = diags(S_calc_all.imag)
        
        # D. Construcción de sub-matrices del Jacobiano
        # H = Im(aux) - diag(Q)
        H = aux_matrix.imag - diagQ
        
        # N = Re(aux) + diag(P)
        N = aux_matrix.real + diagP
        
        # M = - Re(aux) + diag(P)
        M = diagP - aux_matrix.real
        
        # L = Im(aux) + diag(Q)
        L = aux_matrix.imag + diagQ
        
        # Recorte y Ensamblaje del Jacobiano Reducido
        # Extraemos solo las submatrices correspondientes a las incógnitas
        # H: Derivadas dP/dTheta (Filas: PV+PQ, Cols: PV+PQ)
        J11 = H[theta_unknown_idxs, :][:, theta_unknown_idxs]
        
        # N: Derivadas dP/dU (Filas: PV+PQ, Cols: PQ)
        J12 = N[theta_unknown_idxs, :][:, v_unknown_idxs]
        
        # M: Derivadas dQ/dTheta (Filas: PQ, Cols: PV+PQ)
        J21 = M[v_unknown_idxs, :][:, theta_unknown_idxs]
        
        # L: Derivadas dQ/dU (Filas: PQ, Cols: PQ)
        J22 = L[v_unknown_idxs, :][:, v_unknown_idxs]
        
        # Matriz Jacobiana Final (Sparse CSR)
        jacobian = bmat([
            [J11, J12],
            [J21, J22]
        ], format='csr')


        # 3. Resolver el sistema lineal
        # Ecuación: J * deltaX = -f(x)
        try:
            delta_x = spsolve(jacobian, -pq_mismatch)
        except Exception:
            # Error crítico matemático (Matriz singular o mal condicionada)
            success = False
            max_error = float('inf')
            final_message = "Linear Algebra Error: The Jacobian matrix is singular or ill-conditioned. Unable to solve the update step."
            final_iterations = i
            break

        
        # 4. Actualizar el estado (x_new = x_old + delta_x)
        
        # El vector delta_x tiene:
        #   - primero todas las correcciones de ángulo (PV + PQ)
        #   - después todas las correcciones relativas de tensión (PQ)        
        # Slicing del vector solución (Vistas sin copia)
        d_theta = delta_x[:n_pvpq]       # Delta Theta (PV + PQ)
        d_v_rel = delta_x[n_pvpq:]       # Delta V / V (PQ)
        
        # Actualizar Ángulos (PQ y PV) (Mascara eficiente sobre el array global)
        theta0_arr[theta_unknown_idxs] += d_theta
        
        # Actualizar Tensiones (Solo PQ)
        # Aquí d_v_rel contiene deltav / v
        # V_new = V_old * (1 + dV_rel)
        v0_arr[v_unknown_idxs] *= (1 + d_v_rel)

    else:
        # Si se sale por el limite de iteraciones
        final_iterations = max_it



    # Construcción del vector complejo final
    v_complex_solution = v0_arr * np.exp(1j * theta0_arr)
    
    meta = SolverMetaResult(
        success=success,
        method_name=METHOD_NAME,
        message=final_message,
        iterations=final_iterations,
        final_error=max_error,
        tolerance_used=tol,
        error_history= np.array(error_history),
    )
    return v_complex_solution, meta