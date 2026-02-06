from pathlib import Path
from copy import deepcopy

import numpy as np
import matplotlib.pyplot as plt

import pywerflow.paths.paths as paths
from pywerflow.io.excel_report import generate_excel_report
from pywerflow.plotting.plot_network import plot_power_flow_network
from pywerflow.plotting.plot_curve import plot_curve
from pywerflow.plotting.plot_voltage_profile import plot_voltage_profile
from pywerflow.networks.pfnetwork_builder import PFNetworkBuilder
from pywerflow.examples.examples_utils import *
from pywerflow.buses.bus_types import BusTypes


# --- CONFIGURACIÓN DE RUTAS ---
BASE_RESULTS_DIR = Path("ieee14_scenarios")

# Determinar y crear los directorios de salida
RESULTS_DIR = get_unique_results_dir(BASE_RESULTS_DIR)
UNMODIFIED_CASE_DIR = RESULTS_DIR / "1unmodified_case"
LOAD_INCREMENT_DIR = RESULTS_DIR / "2load_increment"
CONTINGENCY_DIR = RESULTS_DIR / "3contingency"
TAPS_DIR = RESULTS_DIR / "4taps"


# Crear los directorios
RESULTS_DIR.mkdir(exist_ok=True, parents=True)
UNMODIFIED_CASE_DIR.mkdir(exist_ok=True, parents=True)
LOAD_INCREMENT_DIR.mkdir(exist_ok=True, parents=True)
CONTINGENCY_DIR.mkdir(exist_ok=True, parents=True)
TAPS_DIR.mkdir(exist_ok=True, parents=True)


def run():

    ################################ CARGAR LA RED USANDO EL BUILDER #############################
    builder = PFNetworkBuilder()
    builder.load_matpower( paths.IEEE14_PATH )

    ######################################## CREAR LA RED ######################################
    network = builder.build()


    # ============================
    # PASO 1: CASO BASE (SIN MODIFICACIONES)
    # =========================================================================

    print("Paso 1: Resolviendo caso base...")

    original_gs_results = network.gauss_seidel_solve(alpha=1.4, fix_step=15)
    original_nr_results = network.newton_raphson_solve()
    print(f"  ✅ Caso base convergido en {original_gs_results.meta.iterations} iteraciones con el método {original_gs_results.meta.method_name}.")
    print(f"  ✅ Caso base convergido en {original_nr_results.meta.iterations} iteraciones con el método {original_nr_results.meta.method_name}.")

    ################################ IMPRIMIR RESUMEN EN CONSOLA ###########################

    # Que pongo aqui? 

    ############################# ALMACENAR RESULTADOS EN FORMA DE REPORTE Y GENERAR GRAFICOS #################
    generate_excel_report(
        filepath= UNMODIFIED_CASE_DIR / "ieee14_gs_report.xlsx",
        network= network,
        results= original_gs_results,
        in_bus_columns = ['id', 'type', 'v_pu', 'theta_rad', 'theta_deg', 'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'g_pu', 'b_pu'],
        in_branch_columns = ['id', 'type', 'bus1', 'bus2', 'r', 'x', 'g', 'b', 'tap', 'shift', 's_max'],
        res_bus_columns = ['id', 'type', 'v_pu', 'theta_rad', 'theta_deg', 'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'p_mis', 'q_mis', 'pshunt_pu', 'pshunt_mw', 'qshunt_pu', 'qshunt_mvar'],
        res_branch_columns = ['id', 'bus1', 'bus2','p1_mw', 'q1_mvar', 'p2_mw', 'q2_mvar', 'ploss_mw', 'qloss_mvar', 'ploss_pu', 'qloss_pu'],
        )

    generate_excel_report(
        filepath= UNMODIFIED_CASE_DIR / "ieee14_nr_report.xlsx",
        network= network,
        results= original_nr_results,
        in_bus_columns = ['id', 'type', 'v_pu', 'theta_rad', 'theta_deg', 'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'g_pu', 'b_pu'],
        in_branch_columns = ['id', 'type', 'bus1', 'bus2', 'r', 'x', 'g', 'b', 'tap', 'shift', 's_max'],
        res_bus_columns = ['id', 'type', 'v_pu', 'theta_rad', 'theta_deg', 'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'p_mis', 'q_mis', 'pshunt_pu', 'pshunt_mw', 'qshunt_pu', 'qshunt_mvar'],
        res_branch_columns = ['id', 'bus1', 'bus2','p1_mw', 'q1_mvar', 'p2_mw', 'q2_mvar', 'ploss_mw', 'qloss_mvar', 'ploss_pu', 'qloss_pu'],
    )

    fig=plot_power_flow_network(network, title="Topología sistema IEEE de 14 nudos", show=False , layout_seed=62, branch_id_font_size=10)
    fig.savefig(RESULTS_DIR / "network.pdf", bbox_inches='tight', pad_inches=0.01)
    
    original_gs_results.meta.plot_convergence(filepath=UNMODIFIED_CASE_DIR / "gs_convergence.pdf", marker="", show=False)
    original_nr_results.meta.plot_convergence(filepath=UNMODIFIED_CASE_DIR / "nr_convergence.pdf", marker="", show=False)



    # Gráfico del perfil de tensiones
    plot_voltage_profile(
        bus_data=original_nr_results.buses,
        title="Perfil de tensiones - Caso base (IEEE 14)",
        filepath=UNMODIFIED_CASE_DIR / "base_voltage_nr_profile.pdf",
        show=False,
        ylim=(0.9, 1.1) # Intervalo fijo para ver variaciones
    )

    # Gráfico del perfil de tensiones 
    plot_voltage_profile(
        bus_data=original_gs_results.buses,
        title="Perfil de tensiones - Caso base (IEEE 14)",
        filepath=UNMODIFIED_CASE_DIR / "base_voltage_gs_profile.pdf",
        show=False,
        ylim=(0.9, 1.1) # Intervalo fijo para ver variaciones
    )







    # =========================================================================
    # PASO 2: INCREMENTO GRADUAL DE CARGA 
    # =========================================================================
    print("\nPaso 2: Variando carga en todo el sistema (Factor Lambda)...")
    
    # lambdas = [ 1, 1.2, 1.4, 1.6, 1.8, 2, 2.2, 2.4, 2.6, 2.8, 3, 3.2, 3.4, 3.6, 3.8, 4, 4.2, 4.4, 4.6, 4.8, 5  ]
    lambdas = list( np.linspace(1,5.5,100))
    all_scenario_buses = [] # Para el gráfico múltiple
    plot_labels = []
    plot_buses = []
    min_voltages = [] # Para la evolución de Vmin
    critical_bus_ids = [] # Para saber QUIÉN tiene la tensión mínima
    valid_lambdas = [] # Guardar solo las lambdas que convergen
    
    # Listas para almacenar P y Q máximas generadas (de cualquier nudo PV o Slack)
    max_p_gens = []
    max_q_gens = []

    buses = builder.buses

    for lb in lambdas:
        # Construimos una red modificada desde el builder con una lambda incrementada
        builder_cpy = deepcopy(builder)
        for bus in buses:
            if bus.type == BusTypes.PQ and bus.P < 0:
                builder_cpy.modify_bus(bus_id=bus.id, 
                                       P = bus.P*lb,  
                                       Q = bus.Q*lb,
                                       )

        # Resolvemos para esta red "mas cargada"
        more_loaded_network = builder_cpy.build()
        
        # res = more_loaded_network.gauss_seidel_solve(alpha=1.4, fix_step=15)
        res = more_loaded_network.newton_raphson_solve()
        
        if res.meta.success:
            print(f"  Lambda = {lb:.2f}: Convergido (Err: {res.meta.final_error:.2e}).")
            all_scenario_buses.append(res.buses)
            valid_lambdas.append(lb)
            
            # --- ANÁLISIS DE TENSIÓN MÍNIMA ---
            critical_bus = min(res.buses, key=lambda b: b.V)
            min_voltages.append(critical_bus.V)
            critical_bus_ids.append(critical_bus.id)

            # --- ANÁLISIS DE MÁXIMA GENERACIÓN ---
            # Filtramos solo generadores (PV y Slack)
            gens = [b for b in res.buses if b.original_type in (BusTypes.PV, BusTypes.SLACK)]
            if gens:
                # P máxima (MW)
                p_max = max(b.P_net for b in gens) * network.s_base
                max_p_gens.append(p_max)
                
                # Q máxima (MVar)
                q_max = max(b.Q_net for b in gens) * network.s_base
                max_q_gens.append(q_max)
            
            if lb in  (1,1.5,2,2.5,3,3.5,4,4.5):
                plot_buses.append(res.buses)
                plot_labels.append(f"λ = {lb:.1f}")
        else:
            print(f"  Lambda = {lb:.2f}: ❌ DIVERGENCIA")

    # Generar Perfil de Tensiones Múltiple
    plot_voltage_profile(
        bus_data=plot_buses,
        labels=plot_labels,
        title="Variación de perfil de tensiones al incrementar la carga",
        ylabel="Tensión (p.u.)",
        ylim=(0.7, 1.1), # Bajo el límite para ver la caída
        filepath=LOAD_INCREMENT_DIR / "loading_comparison.pdf",
        show=False
    )

    # Generar Curva de Evolución de Voltaje Mínimo
    fig = plot_curve(
        y_data=min_voltages,
        x_data=valid_lambdas,
        title="Evolución de la Tensión Mínima del Sistema vs Factor de Carga",
        xlabel="Factor de Carga (λ)",
        ylabel="Tensión Mínima (p.u.)",
        marker=None, 
        line_fmt="-",
        color="crimson",
        filepath=None, # No guardamos todavía, vamos a editar la figura
        show=False
    )

    if fig:
        ax = fig.gca()
        
        # Lógica para detectar regiones (cambios de nudo crítico)
        # regions será una lista de tuplas: (indice_inicio, indice_fin, bus_id)
        regions = []
        if critical_bus_ids:
            current_start = 0
            current_bus = critical_bus_ids[0]
            
            for i, bus_id in enumerate(critical_bus_ids):
                if bus_id != current_bus:
                    # Se acabó una región, guardamos la anterior
                    regions.append((current_start, i-1, current_bus))
                    # Empezamos nueva región
                    current_start = i
                    current_bus = bus_id
            # Guardar la última región
            regions.append((current_start, len(critical_bus_ids)-1, current_bus))

        # Pintar las regiones
        # Colores de fondo más distintos para notar la separación
        # Usamos una paleta pastel más variada: Azul, Verde, Amarillo, Rojo, Púrpura
        bg_colors = ['#dbeafe', '#dcfce7', '#fef9c3', '#fee2e2', '#f3e8ff'] 
        
        for i, (start_idx, end_idx, bus_id) in enumerate(regions):
            l_start = valid_lambdas[start_idx]
            l_end = valid_lambdas[end_idx]
            
            # Si es la última región y es muy estrecha (un solo punto), le damos un poco de ancho visual
            if l_start == l_end:
                l_end = l_start + 0.05 

            # Pintar franja vertical
            color = bg_colors[i % len(bg_colors)]
            ax.axvspan(l_start, l_end, color=color, alpha=0.5, zorder=0)
            
            # Añadir etiqueta de texto centrada en la región
            mid_point = (l_start + l_end) / 2
            # Ponemos el texto en la parte media-baja (0.15 de la altura del eje)
            trans = ax.get_xaxis_transform() 
            ax.text(mid_point, 0.15, f"Nudo {bus_id}", transform=trans, 
                    ha='center', va='bottom', fontsize=10, fontweight='bold', 
                    color='#444444', rotation=90) # Rotado 90 para que quepa mejor si la franja es estrecha

        # Guardamos manualmente ahora que hemos pintado encima
        save_path = LOAD_INCREMENT_DIR / "min_v_evolution_regions.pdf"
        fig.savefig(save_path, bbox_inches='tight', pad_inches=0.01)
        print(f"Gráfico de evolución guardado con regiones en: {save_path}")
        plt.close(fig)



    # ---  GRÁFICO DOBLE EJE: P y Q MÁXIMAS DE GENERACIÓN ---
    fig_pq, ax1 = plt.subplots(figsize=(10, 6))
    
    # Eje Izquierdo: Potencia Activa (P)
    color_p = 'tab:blue'
    ax1.set_xlabel('Factor de Carga (λ)', fontweight='bold')
    ax1.set_ylabel('P Máxima Generada (MW)', color=color_p, fontweight='bold')
    ax1.plot(valid_lambdas, max_p_gens, color=color_p, linestyle='-', linewidth=2, label='P Max (MW)')
    ax1.tick_params(axis='y', labelcolor=color_p)
    ax1.grid(True, alpha=0.3)

    # Eje Derecho: Potencia Reactiva (Q)
    ax2 = ax1.twinx()
    color_q = 'tab:green'
    ax2.set_ylabel('Q Máxima Generada (MVar)', color=color_q, fontweight='bold')
    ax2.plot(valid_lambdas, max_q_gens, color=color_q, linestyle='--', linewidth=2, label='Q Max (MVar)')
    ax2.tick_params(axis='y', labelcolor=color_q)

    plt.title('Evolución de la Máxima Generación en el Sistema (P y Q)', fontsize=12, fontweight='bold')
    fig_pq.tight_layout()
    
    # Guardar
    save_path_pq = LOAD_INCREMENT_DIR / "max_gen_p_q_evolution.pdf"
    fig_pq.savefig(save_path_pq, bbox_inches='tight', pad_inches=0.01)
    print(f"Gráfico de generación P/Q guardado en: {save_path_pq}")
    plt.close(fig_pq)






    # =========================================================================
    # PASO 3: CONTINGENCIA - Se elimina una línea
    # =========================================================================
    print("\nPaso 3: Analizando contingencia (Eliminación de la rama ID 4)...")
    
    # 1. Resolver caso original (ya lo tenemos de nr_results, pero por claridad lo referenciamos)
    v_profile_original = original_nr_results.buses
    
    # 2. Crear escenario de contingencia
    builder_cpy = deepcopy(builder)
    
    # Eliminamos la rama que conecta los nudos 2 y 4 (ID 4)
    builder_cpy.remove_branch(branch_id=4)

    # Construimos la red y resolvemos
    contingency_network = builder_cpy.build()
    res_contingency = contingency_network.newton_raphson_solve()
    
    if res_contingency.meta.success:
        print(f"  ✅ Contingencia convergida en {res_contingency.meta.iterations} iteraciones.")
        
        # 3. Generar perfil doble de tensiones
        plot_voltage_profile(
            bus_data=[v_profile_original, res_contingency.buses],
            labels=["Caso Base", "Rama 4 desconectada (2-4)"],
            title="Impacto en el Perfil de Tensiones por Contingencia",
            ylim=(1, 1.1),
            filepath=CONTINGENCY_DIR / "contingency_voltage_impact.pdf",
            show=False
        )
        
        # 4. Generar reporte específico
        generate_excel_report(
            filepath=CONTINGENCY_DIR / "ieee14_contingency_report.xlsx",
            network=contingency_network,
            results=res_contingency,
            in_bus_columns = ['id', 'type', 'v_pu', 'theta_rad', 'theta_deg', 'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'g_pu', 'b_pu'],
            in_branch_columns = ['id', 'type', 'bus1', 'bus2', 'r', 'x', 'g', 'b', 'tap', 'shift', 's_max'],
            res_bus_columns = ['id', 'type', 'v_pu', 'theta_rad', 'theta_deg', 'p_pu', 'p_mw', 'q_pu', 'q_mvar', 'p_mis', 'q_mis', 'pshunt_pu', 'pshunt_mw', 'qshunt_pu', 'qshunt_mvar'],
            res_branch_columns = ['id', 'bus1', 'bus2','p1_mw', 'q1_mvar', 'p2_mw', 'q2_mvar', 'ploss_mw', 'qloss_mvar', 'ploss_pu', 'qloss_pu'],
        )

        # 5. Generar perfil de potencia aparente por rama (Comparativo)
        # Obtenemos todos los IDs de ramas originales para el eje X
        all_branch_ids = sorted([br.id for br in network.get_all_branches()])
        
        # Mapeamos los flujos (S_max = max(S1, S2)) para el caso base
        base_flows = {br.id: max(br.S1, br.S2) * network.s_base for br in original_nr_results.branches}
        # Mapeamos los flujos para el caso con contingencia (la rama 4 no estará en res_contingency.branches)
        cont_flows = {br.id: max(br.S1, br.S2) * contingency_network.s_base for br in res_contingency.branches}

        # Preparamos las listas para el eje Y
        y_base = [base_flows.get(bid, 0.0) for bid in all_branch_ids]
        y_cont = [cont_flows.get(bid, 0.0) for bid in all_branch_ids]

        # Usamos matplotlib directamente para el perfil de ramas
        fig_flow, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(all_branch_ids, y_base, 'o-', color='gray', label='Caso Base', alpha=0.6)
        ax.plot(all_branch_ids, y_cont, 's--', color='darkorange', label='Rama 4 desconectada')
        
        ax.set_title("Redistribución de Flujos de Potencia Aparente", fontsize=12, fontweight='bold')
        ax.set_xlabel("ID de la Rama", fontweight='bold')
        ax.set_ylabel("Carga de la Rama (MVA)", fontweight='bold')
        ax.set_xticks(all_branch_ids)
        ax.grid(True, alpha=0.3)
        ax.legend()

        save_path_flow = CONTINGENCY_DIR / "contingency_flow_impact.pdf"
        fig_flow.savefig(save_path_flow, bbox_inches='tight', pad_inches=0.01)
        print(f"  ✅ Gráfico de impacto de flujos guardado en: {save_path_flow}")
        plt.close(fig_flow)
    else:
        print("  ❌ La contingencia provocó divergencia en el sistema.")
    









    # =========================================================================
    # PASO 4: REGULACIÓN POR TAP (TRANSFORMADOR)
    # =========================================================================
    print("\nPaso 4: Analizando regulación por Tap (Rama 10, Nudos 5-6)...")
    
    # 1. Crear escenario modificado
    builder_cpy = deepcopy(builder)
    
    # Obtenemos la rama original para saber su tap actual (rama 10: 5-6)
    transf_br = builder_cpy.get_branch(10)
    
    # Aumentamos el tap un 10%
    new_tap = transf_br.tap_ratio * 1.1
    builder_cpy.modify_branch(10, tap_ratio=new_tap)

    # Construimos la red y resolvemos
    tap_network = builder_cpy.build()
    res_tap = tap_network.newton_raphson_solve()
    
    if res_tap.meta.success:
        print(f"  ✅ Caso con Tap modificado ({new_tap:.3f}) convergido.")
        
        # 2. Generar perfil doble de tensiones
        plot_voltage_profile(
            bus_data=[original_nr_results.buses, res_tap.buses],
            labels=["Caso Base (Tap=1.0)", f"Tap incrementado (+10%) en Rama 10"],
            title="Efecto de la Regulación por Tap en el Perfil de Tensiones",
            ylim=(0.95, 1.1),
            filepath=TAPS_DIR / "tap_regulation_impact.pdf",
            show=False
        )
        
        # 3. Generar reporte
        generate_excel_report(
            filepath=TAPS_DIR / "ieee14_tap_modification_report.xlsx",
            network=tap_network,
            results=res_tap
        )
    else:
        print("  ❌ El ajuste del tap provocó divergencia.")




    # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
    print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




if __name__ == "__main__":
    run()




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# PS_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# PS_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# PS_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# PS_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# PS_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# PS_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# PS_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



# S_DIR / "ieee14_tap_modification_report.xlsx",
#             network=tap_network,
#             results=res_tap
#         )
#     else:
#         print("  ❌ El ajuste del tap provocó divergencia.")




#     # 3. VISUALIZACIÓN DE LA TOPOLOGÍA FINAL
#     print(f"\n--- Estudio finalizado. Revisa la carpeta '{RESULTS_DIR}' ---")




# if __name__ == "__main__":
#     run()



