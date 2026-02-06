// Compilar con  gcc -shared -o gauss_seidel.dll -O3 -march=native -static gauss_seidel.c
#include "c_common.h" 
#include <stdio.h>
#include <stdlib.h> 
#include <complex.h> 
#include <math.h>
// stdin y stdbool ya está en c_common

#define UINT32_MAX_SQRT 65535 // La raiz cuadrada de UINT32_MAX (redondeada hacia abajo)
#define ERROR_LOG_CHUNK_SIZE 100 // El tamaño que se va a usar para ir almacenando los errores acumulados


// --- BARRERA DE SEGURIDAD DE TIPOS ---
// Son condiciones que se evaluan en tiempo de compilacion, si fallan, entonces no puede compilar
_Static_assert(sizeof(double) == 8, 
    "CRITICAL COMPILATION ERROR: Architecture does not use 64-bit 'double' (IEEE 754).");
_Static_assert(sizeof(double complex) == 16, 
    "CRITICAL COMPILATION ERROR: 'double complex' size must be 16 bytes.");


/*                                                            
pqv_data debe tener la estructura [P, Q, P, Q, P, V, P, V, P, Q]. Donde cada "par" (P_i, Q_i+1) o (P_i, V_i+1) corresponden al nudo de indice i/2
bus_types indica si el nudo del indice i es PQ (true) o PV (false)...
adm_matrix es la matriz de admitancias (2x2 aplanada) ordenada del mismo modo que los nudos en bus_types (se espera el nudo slack en el ultimo indice)
v0_data es una matriz compleja con las tensiones complejas iniciales (initial guess) CON el slack (en el caso de nudos PQ son "inventadas", en el caso de los PV 
    puedes elegir como modulo la V conocida, en el caso del Slack, el ultimo nudo, este tiene su numero complejo correspondiente a su P y theta final)
N es el numero de nudos (contando el slack)
epsilon es el error, por debajo del cual se considerará que ha convergido el metodo cuando max( |U_k+1 - U_k| ) < epsilon  (max es el maximo de los errores de todos 
    los nudos en una iteracion dada)
max_iterations es el numero maximo de iteraciones que permitimos hacer al método. Si se supera entonces devolvemos NULL y consideramos que diverge
v_fixing_step es el paso (k) a partir del cual se empezará a aplicar la correcion de tensión para los nudos PQ
acceleration_factor es el factor (alpha) de aceleracion, sus valores optimos están entre 1.4 y 1.6. Disminuye el numero de iteraciones. El equivalente a no ponerlo es alpha = 1
error_history es un array donde meter el error asociado al método en cada iteración
err_history_limit es el tamaño del array anterior, y el límite a partir del cual YA no se deben meter más elementos en el array

Devuelve algun tipo de codigo de error o el numero de iteraciones, si no hay errores.
*/
EXPORT MethodResponse gauss_seidel(
    const double * restrict pqv_data,
    const bool * restrict bus_types,
    const double complex * restrict adm_matrix, 
    double complex * restrict v0_data,
    const uint32_t N,
    const double epsilon,
    const uint32_t max_iterations,
    const uint32_t v_fixing_step,
    const double acceleration_factor,
    double * restrict error_history,   // <--- 1. Array donde escribir
    const uint32_t err_history_limit       // <--- 2. Tope de escritura (el tamaño del array de historial)
)
    {
    MethodResponse method_response = {0,0,0};

    if (N < 1) {
        // Error por no tener nudos suficientes... 
        method_response.status_code = -2;
        return method_response; 
    }

    if (max_iterations <= v_fixing_step){
        // Error porque el "paso en el cual empiezas el fixing" no 
        // puede ser inferior al maximo de iteraciones -> El fixing debe suceder si o si
        // En el limite (v_fixing_step==max_iterations-1) el fixing step solo se ejecutará 1 vez, pero al menos el algoritmo se detendrá con un error
        method_response.status_code = -3;
        return method_response;
    }
    // ESTO FUNCIONARÄ AUNQUE N*N DESBORDE?
    if ( N > UINT32_MAX_SQRT ){
        // La matriz de admitancias NO cabe. Al intentar acceder a su ultima fila (o antes)
        // Los indices van a desbordar.
        method_response.status_code = -4;
        return method_response;
    }


    // Número de iteracion, en cada una se recorren todos los nudos
    uint32_t k = 0;
    // Indice de cada nudo
    uint32_t i = 0;       
    // Iterador para el sumatorio que recorre los demas nudos, en cada nudo (i)
    uint32_t j = 0;       
    // Inicializacion del error
    double max_error = epsilon + 1;
    // Numero de nudos PQ y PV, sin contar el slack
    uint32_t M = N - 1;

    // Inicializaciones de matriz compleja de tensiones (Contiene todos los "initial guess" de nudos PQ y PV + el slack)
    double complex *v_results = v0_data; 

    // Booleano que activa las correcciones de los modulos de las tensiones de los nudos PV. Se activa en k = v_fixing_step 
    bool active_fix = false;
   
    // Otras variables que se usarán durante el cálculo 
    double complex summation;
    double complex old_v;
    double complex new_v;
    uint32_t Ni;
    double Q;
    double v_re;
    double v_im;
    double y_im;
    double sum_re; 
    double sum_im;
    double mod_sq; 
    double current_error;

    // El bucle solo puede detenerse si:
    //      - El error maximo se minimiza por debajo de epsilon
    //      - Se alcanza el maximo de iteraciones
    // ESTO SOLO SI ya se ha alcanzado el "fixing step", si este no se alcanza las demas condiciones no pueden parar el bucle aun

    
    while (  (k<=v_fixing_step) || ( (max_error>epsilon) && (k<max_iterations) )  ){

        // Reseteo el maximo error
        max_error = 0;

        // ¿Aplicar ya el factor de corrección?
        if (k == v_fixing_step){
            active_fix = true;
        }

        // Recorro todos los nudos PQ y PV
        i = 0;
        while(i<M){ // Aqui no incluyo el Slack al iterar, pues no hay que actualizar su tension

            old_v = v_results[i];

            // Los siguientes 2 bucles son practicamente un producto escalar entre una fila de la matriz de admitancias y el vector actual de tensiones complejas
            j=0;
            summation = 0;
            Ni = N*i; // Para no repetir la multiplicacion todo el rato
            while (j<i){
                summation += adm_matrix[Ni+j] * v_results[j];
                j++;
            }
            j++;
            while (j<N){ // El slack tambien se evalua aqui (su tensión importa)
                summation += adm_matrix[Ni+j] * v_results[j];
                j++;
            }

            if (bus_types[i]){
                // El nudo i es PQ
                new_v = (1/adm_matrix[Ni+i]) * ( (pqv_data[2*i] - I * pqv_data[2*i+1]) / conj(old_v) - summation ); 
                new_v = old_v + acceleration_factor * (new_v - old_v);
            }
            
            else {
                // El nudo i es PV
                
                // Summation es literalmete la I inyectada por el nudo, SALVO por su propia componente (producida por la admitacion mutua). 
                // Por tanto se cumple la relacion: summ + Yii * Ii = Ii
                // Que combinada con la relacion: Q = Im( Ui * Ii* )
                // Hace que se pueda calcular Q como:  Im(Ui)*Re(sum) - Re(Ui)*Im(sum) - |Ui|^2 * Im(Yii)
                v_re = creal(old_v);
                v_im = cimag(old_v);
                y_im = cimag(adm_matrix[Ni+i]); 
                sum_re = creal(summation);
                sum_im = cimag(summation);
                mod_sq = v_re * v_re + v_im * v_im;
                Q = v_im * sum_re - v_re * sum_im - mod_sq * y_im;
                
                
                new_v = (1/adm_matrix[Ni+i]) * ( (pqv_data[2*i] - I * Q) / conj(old_v) - summation );
                new_v = old_v + acceleration_factor * (new_v - old_v);

                if (active_fix){
                    new_v *= ( pqv_data[2*i+1] / cabs(new_v) );
                }
            }
            // Asigno el resultado con su "factor de aceleracion"
            v_results[i] = new_v;

            // Actualizo el error maximo si este es mas grande que el anterior mas grande
            current_error = cabs(new_v-old_v);
            if ( current_error > max_error ){
                max_error = current_error;
            }

            i++;
        }

        if ( k < err_history_limit ) {
            error_history[k] = max_error;
        }

        k++;
    }

    method_response.iterations = k;
    method_response.final_error = max_error;

    if (k>=max_iterations){
        method_response.status_code = -1;
        return(method_response); // se llegó al numero máximo de iteraciones (diverge)
        }


    method_response.status_code = 0;
    return(method_response); // Devuelvo limite de iteraciones
}

