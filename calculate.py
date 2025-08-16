import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Função de cálculo da energia e eficiência
def calcular_energia(config_id, P_idle, alpha, D_proc, beta, gamma, num_UEs, T_sim, potencias_dbm, throughput_mbps):
    resultados = []
    for pot_dbm in potencias_dbm:
        P_tx = 10 ** (pot_dbm / 10) * 1e-3  # dBm -> W
        P_gnb = P_idle + alpha * D_proc + beta * num_UEs + gamma * P_tx
        E_total = P_gnb * T_sim  # J
        eficiencia = (throughput_mbps * 1e6 / 8 * T_sim) / E_total  # bits/J
        
        resultados.append({
            "Config": config_id,
            "Potência (dBm)": pot_dbm,
            "Potência Tx (W)": round(P_tx, 4),
            "Potência Média gNB (W)": round(P_gnb, 2),
            "Energia Total Consumida (J)": round(E_total, 2),
            "Eficiência Energética (bits/J)": eficiencia
        })
    return pd.DataFrame(resultados)

# Configurações de exemplo
configs = [
    {
        "config_id": "Configuração 1",
        "P_idle": 500, "alpha": 10, "D_proc": 1.5,
        "beta": 5, "gamma": 5, "num_UEs": 39,
        "T_sim": 5, "potencias_dbm": [6, 16, 26, 36, 46, 56],
        "throughput_mbps": 120
    },
    {
        "config_id": "Configuração 2",
        "P_idle": 450, "alpha": 9, "D_proc": 1.3,
        "beta": 4.5, "gamma": 4.8, "num_UEs": 39,
        "T_sim": 5, "potencias_dbm": [6, 16, 26, 36, 46, 56],
        "throughput_mbps": 115
    }
]

# Calcular resultados para todas as configs
dfs = [calcular_energia(**cfg) for cfg in configs]
df_geral = pd.concat(dfs, ignore_index=True)

# ---- Gráfico 1: Energia × Potência ----
plt.figure(figsize=(10, 6))
for cfg in df_geral["Config"].unique():
    subset = df_geral[df_geral["Config"] == cfg]
    plt.plot(subset["Potência (dBm)"], subset["Energia Total Consumida (J)"], marker="o", label=cfg)

plt.title("Energia Total Consumida vs Potência de Transmissão")
plt.xlabel("Potência de Transmissão (dBm)")
plt.ylabel("Energia Total Consumida (J)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("energia_vs_potencia.png", dpi=300)

# ---- Gráfico 2: Eficiência × Potência ----
plt.figure(figsize=(10, 6))
for cfg in df_geral["Config"].unique():
    subset = df_geral[df_geral["Config"] == cfg]
    plt.plot(subset["Potência (dBm)"], subset["Eficiência Energética (bits/J)"], marker="s", label=cfg)

plt.title("Eficiência Energética vs Potência de Transmissão")
plt.xlabel("Potência de Transmissão (dBm)")
plt.ylabel("Eficiência Energética (bits/J)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("eficiencia_vs_potencia.png", dpi=300)

# ---- Gráfico 3: Comparação de Consumo ----
consumo_medio = df_geral.groupby("Config")["Energia Total Consumida (J)"].mean()
plt.figure(figsize=(8, 5))
consumo_medio.plot(kind="bar", color=["#1f77b4", "#ff7f0e"])
plt.title("Consumo Médio de Energia por Configuração")
plt.ylabel("Energia Total Consumida (J)")
plt.grid(axis="y")
plt.tight_layout()
plt.savefig("comparacao_consumo.png", dpi=300)

print("Gráficos gerados: energia_vs_potencia.png, eficiencia_vs_potencia.png, comparacao_consumo.png")
