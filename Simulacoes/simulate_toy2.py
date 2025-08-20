#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simulate_toy2.py
----------------
Simulação do cenário "toy2_1.ini" com 3 clusters CoMP e gNBs em D-RAN,
gerando TABELAS e GRÁFICOS automaticamente e salvando tudo na pasta
de resultados definida pelo usuário.

Estrutura desejada:
- Este arquivo deve ficar em:  .../omnet/Simulacoes/simulate_toy2.py
- Os resultados serão salvos em: /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1/<carimbo_data>/

Como definido pelo usuário:
  - Formar 3 clusters com CoMP:
      • (5, 6), ancorado no 5 e na CU2
      • (8, 9), ancorado no 8 e na CU1
      • (11, 12), ancorado no 11 e na CU3
  - gNBs rodando como D-RAN: 4, 7 e 10

OBS: Este script NÃO executa o OMNeT++; ele é um "harness" em Python que
     reproduz/sintetiza métricas (energia, vazão, eficiência) para o TCC,
     permitindo análises e gráficos consistentes com os demais cenários.
     Ajuste os coeficientes de energia/ganhos de CoMP conforme necessário.
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =============================================================
# PARÂMETROS GERAIS
# =============================================================
RESULT_BASE = Path("/home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1")
SIM_NAME = "toy2"
TX_POWERS_DBM = [20, 23, 26, 29, 32]

# =============================================================
# TOPOLOGIA toy2
# =============================================================
CLUSTERS = [
    {"members": [5, 6],  "anchor_gnb": 5,  "anchor_cu": "CU2"},
    {"members": [8, 9],  "anchor_gnb": 8,  "anchor_cu": "CU1"},
    {"members": [11,12], "anchor_gnb": 11, "anchor_cu": "CU3"},
]
DRAN_GNBS = [4, 7, 10]
UES_PER_GNB = 10
BASE_THROUGHPUT_PER_UE = 5.0  # Mbps

# =============================================================
# MODELO DE ENERGIA (ajustável)
# =============================================================
@dataclass
class EnergyCoeffs:
    P_idle_DU: float = 80.0     # DU local em D-RAN (W)
    P_idle_CU: float = 120.0    # CU do cluster (W)
    P_idle_Xhaul: float = 10.0  # fronthaul/backhaul por gNB (W)
    k_proc_DU: float = 1.5      # W por UE
    k_proc_CU: float = 2.0      # W por UE (usado na CU agregada — aqui simplificado)
    k_tx: float = 0.8           # W por dBm

@dataclass
class CompTuning:
    th_gain_pct: float = 18.0   # ganho de throughput por gNB no CoMP (%)
    energy_overhead_w: float = 6.0  # overhead extra por gNB no cluster (W)

EC = EnergyCoeffs()
CT = CompTuning()

# =============================================================
# CÁLCULOS
# =============================================================
def energy_dran(ues: int, tx_dbm: float) -> float:
    return EC.P_idle_DU + EC.k_proc_DU * ues + EC.k_tx * tx_dbm + EC.P_idle_Xhaul

def energy_cluster(members: List[int], ues_per_gnb: int, tx_dbm: float):
    per_member_energy = {}
    total = 0.0
    for g in members:
        e = (EC.k_proc_DU * ues_per_gnb) + (EC.k_tx * tx_dbm) + EC.P_idle_Xhaul + CT.energy_overhead_w
        per_member_energy[g] = e
        total += e
    total += EC.P_idle_CU  # CU do cluster
    return total, per_member_energy

def throughput_gnb(ues: int, tx_dbm: float, comp_gain: float = 0.0) -> float:
    base = ues * BASE_THROUGHPUT_PER_UE * (tx_dbm / max(TX_POWERS_DBM))
    return base * (1.0 + comp_gain/100.0)

def simulate_one_power(tx_dbm: float) -> pd.DataFrame:
    rows = []
    # D-RANs
    for g in DRAN_GNBS:
        e = energy_dran(UES_PER_GNB, tx_dbm)
        th = throughput_gnb(UES_PER_GNB, tx_dbm, comp_gain=0.0)
        rows.append({"Sim": SIM_NAME, "Tipo": "DRAN", "Cluster": "-", "gNB": g,
                     "TX_dBm": tx_dbm, "UEs": UES_PER_GNB, "Energia_W": e, "Throughput_Mbps": th})
    # Clusters
    for c_idx, c in enumerate(CLUSTERS, start=1):
        tot_e, per_member = energy_cluster(c["members"], UES_PER_GNB, tx_dbm)
        for g in c["members"]:
            e = per_member[g]
            th = throughput_gnb(UES_PER_GNB, tx_dbm, comp_gain=CT.th_gain_pct)
            rows.append({"Sim": SIM_NAME, "Tipo": "CLUSTER", "Cluster": f"C{c_idx}", "gNB": g,
                         "TX_dBm": tx_dbm, "UEs": UES_PER_GNB, "Energia_W": e, "Throughput_Mbps": th})
        # Linha da CU do cluster (útil para empilhados)
        rows.append({"Sim": SIM_NAME, "Tipo": "CU_CLUSTER", "Cluster": f"C{c_idx}", "gNB": f"CU_{c_idx}",
                     "TX_dBm": tx_dbm, "UEs": len(c["members"]) * UES_PER_GNB,
                     "Energia_W": EC.P_idle_CU, "Throughput_Mbps": 0.0})
    df = pd.DataFrame(rows)
    df["Energia_J"] = df["Energia_W"] * 1.0        # janela de 1 s (ajuste se quiser)
    df["Eficiencia_Mbps_por_J"] = np.where(df["Energia_J"] > 0, df["Throughput_Mbps"]/df["Energia_J"], 0.0)
    return df

# =============================================================
# GRÁFICOS
# =============================================================
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def plot_energy_vs_power(df_all: pd.DataFrame, outdir: Path):
    g = df_all.groupby(["TX_dBm", "Tipo"], as_index=False)["Energia_W"].sum()
    plt.figure(figsize=(7,5.2))
    for t, gt in g.groupby("Tipo"):
        plt.plot(gt["TX_dBm"], gt["Energia_W"], marker="o", label=t)
    plt.xlabel("Potência (dBm)"); plt.ylabel("Energia (W)")
    plt.title("Consumo de energia por configuração (toy2)")
    plt.grid(True, linestyle=":"); plt.legend(); plt.tight_layout()
    plt.savefig(outdir / "energia_vs_potencia_toy2.png", dpi=300)

def plot_efficiency_vs_power(df_all: pd.DataFrame, outdir: Path):
    g = df_all.groupby(["TX_dBm", "Tipo"], as_index=False).agg(
        Energia_W=("Energia_W","sum"), Throughput_Mbps=("Throughput_Mbps","sum")
    )
    g["Eficiência (Mbps/J)"] = np.where(g["Energia_W"]>0, g["Throughput_Mbps"]/g["Energia_W"], 0.0)
    plt.figure(figsize=(7,5.2))
    for t, gt in g.groupby("Tipo"):
        plt.plot(gt["TX_dBm"], gt["Eficiência (Mbps/J)"], marker="s", label=t)
    plt.xlabel("Potência (dBm)"); plt.ylabel("Eficiência (Mbps/J)")
    plt.title("Eficiência energética por configuração (toy2)")
    plt.grid(True, linestyle=":"); plt.legend(); plt.tight_layout()
    plt.savefig(outdir / "eficiencia_vs_potencia_toy2.png", dpi=300)

def plot_stack_energy(df_all: pd.DataFrame, outdir: Path):
    g = df_all.groupby(["TX_dBm", "Tipo"], as_index=False)["Energia_W"].sum().pivot(
        index="TX_dBm", columns="Tipo", values="Energia_W"
    ).fillna(0.0)
    g = g.reindex(columns=["DRAN", "CLUSTER", "CU_CLUSTER"], fill_value=0.0)
    g.plot(kind="bar", stacked=True, figsize=(8,5.2))
    plt.xlabel("Potência (dBm)"); plt.ylabel("Energia (W)")
    plt.title("Decomposição da energia (toy2)")
    plt.grid(True, axis="y", linestyle=":"); plt.tight_layout()
    plt.savefig(outdir / "stack_energy_breakdown_toy2.png", dpi=300)

# =============================================================
# MAIN
# =============================================================
def main():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = RESULT_BASE / f"{SIM_NAME}_{timestamp}"
    ensure_dir(outdir)

    frames = [simulate_one_power(p) for p in TX_POWERS_DBM]
    df_all = pd.concat(frames, ignore_index=True)

    # Tabelas
    df_all.to_csv(outdir / "resultados_toy2_detalhado.csv", index=False)
    df_all.groupby(["TX_dBm"]).agg(
        Energia_W=("Energia_W","sum"),
        Throughput_Mbps=("Throughput_Mbps","sum")
    ).to_csv(outdir / "resultados_toy2_resumo_por_potencia.csv")

    # Metadados
    meta = {
        "sim": SIM_NAME,
        "clusters": CLUSTERS,
        "dran_gnbs": DRAN_GNBS,
        "ues_per_gnb": UES_PER_GNB,
        "tx_powers_dbm": TX_POWERS_DBM,
        "energy_coeffs": asdict(EC),
        "comp_tuning": asdict(CT),
        "generated_at": timestamp,
        "output_dir": str(outdir)
    }
    with open(outdir / "metadata_toy2.json","w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # Gráficos
    plot_energy_vs_power(df_all, outdir)
    plot_efficiency_vs_power(df_all, outdir)
    plot_stack_energy(df_all, outdir)

    print(f"[OK] Resultados salvos em: {outdir}")
    print("Arquivos gerados:")
    print(" - resultados_toy2_detalhado.csv")
    print(" - resultados_toy2_resumo_por_potencia.csv")
    print(" - energia_vs_potencia_toy2.png")
    print(" - eficiencia_vs_potencia_toy2.png")
    print(" - stack_energy_breakdown_toy2.png")
    print(" - metadata_toy2.json")

if __name__ == "__main__":
    main()
