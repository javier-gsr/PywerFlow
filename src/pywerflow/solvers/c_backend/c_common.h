#ifndef C_COMMON_H
#define C_COMMON_H

#include <stdint.h>
#include <stdbool.h>
// Nota: No incluimos math.h ni stdio.h aquí porque el struct no los necesita.
// Los archivos .c individuales los incluirán si los necesitan.

#ifdef _WIN32
    #define EXPORT __declspec(dllexport)
#else
    #define EXPORT
#endif

typedef struct {
    int8_t status_code;    // 0: Success, <0: Error
    uint32_t iterations;   // Number of iterations performed
    double final_error;
} MethodResponse;

#endif