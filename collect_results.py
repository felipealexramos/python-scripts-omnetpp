import os
import pandas as pd
from functions import extract_information, extract_gnb_information

# --- Configurações de Coleta (Devem ser as mesmas do script de execução) ---
# Ajuste para o caminho real da raiz do seu projeto Simu5G no Linux
SIMU5G_PROJECT_ROOT = "/home/felipe/Documentos/tcc/omnet/simu5g" 

CONFIG_NAME = "Toy1" # Deve ser igual ao CONFIG_NAME usado em run_simulations.py
TX_POWERS = ["6", "16", "26", "36", "46", "56"] # Valores de TXPower
NUM_REPETITIONS_SCRIPT = 10 # Número de repetições feitas pelo script (igual ao run_simulations.py)

# Caminho onde os arquivos .sca foram salvos pelo OMNeT++
RESULTS_BASE_DIR_OMNET = os.path.join(SIMU5G_PROJECT_ROOT, "results")

# --- Execução Principal da Coleta ---
if __name__ == "__main__":
    all_simulation_data = []

    print("Starting data collection from .sca files...")
    for tx_power in TX_POWERS:
        for rep in range(NUM_REPETITIONS_SCRIPT): # Itera sobre as repetições feitas pelo script
            # Constrói o caminho para o arquivo .sca esperado, baseado no toy1_1.ini
            sca_filename = f"{CONFIG_NAME}/{tx_power}dBm-{rep}.sca"
            sca_file_path = os.path.join(RESULTS_BASE_DIR_OMNET, sca_filename)

            if os.path.exists(sca_file_path):
                print(f"Processing results from: {sca_file_path}")
                
                # Extrai os dados usando as funções do functions.py
                ue_generated, ue_received = extract_information(sca_file_path) 
                gnb_data, gnb_cost, last_split, last_solution, gnb_blocks = extract_gnb_information(sca_file_path)

                # Estrutura para consolidar os dados
                # Crie uma linha para cada UE de cada simulação/repetição/potência
                
                # Assumindo 39 UEs, como em 'numUe = ${numUEs=39}' no toy1_1.ini
                num_ues_in_sim = 39 
                for ue_idx in range(num_ues_in_sim): 
                    row_data = {
                        "Config_Name": CONFIG_NAME,
                        "TXPower": tx_power,
                        "Repetition": rep,
                        "UE_Index": ue_idx,
                        "UE_Received_Throughput": ue_received.get(ue_idx, 0.0) if ue_received else 0.0,
                        "UE_Generated_Throughput": ue_generated.get(ue_idx, 0.0) if ue_generated else 0.0,
                    }
                    all_simulation_data.append(row_data)

                # Você também pode adicionar uma linha para dados agregados de GNBs por simulação, se desejar
                if gnb_data and gnb_cost:
                    gnb_aggregated_row = {
                        "Config_Name": CONFIG_NAME,
                        "TXPower": tx_power,
                        "Repetition": rep,
                        "UE_Index": "AGGREGATED_GNB_DATA", # Identificador para linha agregada
                        "Total_GNB_Demand_Prop": sum(gnb_data.values()),
                        "Total_GNB_Demand_GOPS": sum(gnb_cost.values()),
                        "Total_GNB_Blocks": sum(gnb_blocks.values()) if gnb_blocks else 0.0,
                    }
                    all_simulation_data.append(gnb_aggregated_row)


            else:
                print(f"Results file NOT found for TXPower={tx_power}, Repetition={rep}: {sca_file_path}. Skipping.")

    # Converte a lista de dicionários para um DataFrame do pandas
    if all_simulation_data:
        df = pd.DataFrame(all_simulation_data)
        output_csv_path = os.path.join(SIMU5G_PROJECT_ROOT, "analysis", "collected_toy1_results.csv")
        os.makedirs(os.path.dirname(output_csv_path), exist_ok=True) # Cria a pasta 'analysis'
        df.to_csv(output_csv_path, index=False)
        print(f"\nAll data collected and saved to: {output_csv_path}")
    else:
        print("\nNo data was collected. Please check simulation execution and .sca file paths/contents.")