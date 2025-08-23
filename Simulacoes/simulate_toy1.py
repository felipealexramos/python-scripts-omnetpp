#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simulate_toy1.py
----------------
Simulação sintética da "Solução 1" (toy1_1.ini) *sem ler o .ini*:
- Todas as gNBs operando em D-RAN (assumimos gNBs 4..12 como rádios).
- CUs desligadas (não contabilizam energia).
- CoMP desabilitado.
- Geração automática de TABELAS (.csv) e GRÁFICOS (.png).
- Saída: /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1/<timestamp>/

Como executar (exemplo):
    python3 simulate_toy1.py \
      --outdir /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1 \
      --tx 20,23,26,29,32
"""
from __future__ import annotations

import json
import argparse
from dataclasses import dataclass, asdict
from typing import List
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =============================================================
# Parâmetros gerais
# =============================================================
RESULT_BASE = Path("/home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1")
SIM_NAME = "toy1"
DEFAULT_TX_POWERS_DBM = [20, 23, 26, 29, 32]

# Topologia "Solução 1"
# Observação: no seu ambiente os rádios mapeiam em gNBs 4..12 (DU1..DU9). gNB1..3 representam CUs.
DRAN_GNBS: List[int] = list(range(4, 13))  # 4..12

# Carga (mantemos fixo por enquanto)
UES_PER_GNB = 10
BASE_THROUGHPUT_PER_UE = 5.0  # Mbps

# =============================================================
# Modelo de energia (mesma base dos demais cenários)
# =============================================================
@dataclass
class EnergyCoeffs:
    P_idle_DU: float = 80.0      # W
    P_idle_Xhaul: float = 10.0   # W por gNB (fronthaul/backhaul)
    k_proc_DU: float = 1.5       # W por UE (processamento na DU)
    k_tx: float = 0.8            # W por dBm (PA/linha RF)

EC = EnergyCoeffs()

# =============================================================
# Utilitários e cálculos
# =============================================================
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def energy_dran(ues: int, tx_dbm: float) -> float:
    """Potência média para gNB em D-RAN (CUs desligadas, sem custo adicional)."""
    return EC.P_idle_DU + EC.k_proc_DU * ues + EC.k_tx * tx_dbm + EC.P_idle_Xhaul

def throughput_gnb(ues: int, tx_dbm: float, max_tx: float) -> float:
    """Throughput sintético (Mbps) por gNB, escalando com a potência relativa."""
    base = ues * BASE_THROUGHPUT_PER_UE * (tx_dbm / max(1.0, max_tx))
    return base  # sem ganho de CoMP

def simulate_one_power(tx_dbm: float, max_tx: float) -> pd.DataFrame:
    rows = []
    for g in DRAN_GNBS:
        e = energy_dran(UES_PER_GNB, tx_dbm)
        th = throughput_gnb(UES_PER_GNB, tx_dbm, max_tx)
        rows.append({
            "Sim": SIM_NAME, "Tipo": "DRAN", "Cluster": "-",
            "gNB": g, "TX_dBm": tx_dbm, "UEs": UES_PER_GNB,
            "Energia_W": e, "Throughput_Mbps": th
        })
    df = pd.DataFrame(rows)
    df["Energia_J"] = df["Energia_W"] * 1.0   # janela de 1 s
    df["Eficiencia_Mbps_por_J"] = np.where(
        df["Energia_J"] > 0, df["Throughput_Mbps"] / df["Energia_J"], 0.0
    )
    return df

# =============================================================
# Gráficos
# =============================================================
def plot_energy_vs_power(df_all: pd.DataFrame, outdir: Path):
    g = df_all.groupby(["TX_dBm", "Tipo"], as_index=False)["Energia_W"].sum()
    plt.figure(figsize=(7, 5.2))
    for t, gt in g.groupby("Tipo"):
        plt.plot(gt["TX_dBm"], gt["Energia_W"], marker="o", label=t)
    plt.xlabel("Potência (dBm)"); plt.ylabel("Energia (W)")
    plt.title("Consumo de energia por configuração (toy1)")
    plt.grid(True, linestyle=":"); plt.legend(); plt.tight_layout()
    plt.savefig(outdir / "energia_vs_potencia_toy1.png", dpi=300)

def plot_efficiency_vs_power(df_all: pd.DataFrame, outdir: Path):
    g = df_all.groupby(["TX_dBm", "Tipo"], as_index=False).agg(
        Energia_W=("Energia_W", "sum"),
        Throughput_Mbps=("Throughput_Mbps", "sum")
    )
    g["Eficiência (Mbps/J)"] = np.where(
        g["Energia_W"] > 0, g["Throughput_Mbps"] / g["Energia_W"], 0.0
    )
    plt.figure(figsize=(7, 5.2))
    for t, gt in g.groupby("Tipo"):
        plt.plot(gt["TX_dBm"], gt["Eficiência (Mbps/J)"], marker="s", label=t)
    plt.xlabel("Potência (dBm)"); plt.ylabel("Eficiência (Mbps/J)")
    plt.title("Eficiência energética por configuração (toy1)")
    plt.grid(True, linestyle=":"); plt.legend(); plt.tight_layout()
    plt.savefig(outdir / "eficiencia_vs_potencia_toy1.png", dpi=300)

def plot_stack_energy(df_all: pd.DataFrame, outdir: Path):
    g = df_all.groupby(["TX_dBm", "Tipo"], as_index=False)["Energia_W"].sum().pivot(
        index="TX_dBm", columns="Tipo", values="Energia_W"
    ).fillna(0.0)
    # Ordem desejada nas colunas
    cols = [c for c in ["DRAN", "CLUSTER", "CU_CLUSTER"] if c in g.columns]
    g = g.reindex(columns=cols, fill_value=0.0)
    ax = g.plot(kind="bar", stacked=True, figsize=(8, 5.2))
    ax.set_xlabel("Potência (dBm)")
    ax.set_ylabel("Energia (W)")
    ax.set_title("Decomposição da energia (toy1)")
    ax.grid(True, axis="y", linestyle=":")
    plt.tight_layout()
    plt.savefig(outdir / "stack_energy_breakdown_toy1.png", dpi=300)

# =============================================================
# Main
# =============================================================
def main():
    parser = argparse.ArgumentParser(description="Simulação sintética do cenário toy1 (Solução 1 - tudo D-RAN).")
    parser.add_argument("--outdir", type=str, default=None,
                        help="Pasta base de saída (default Topologia1)")
    parser.add_argument("--tx", type=str, default=None,
                        help="Lista de potências dBm separadas por vírgula (ex.: 20,23,26,29,32)")
    args = parser.parse_args()

    # Lista de potências
    if args.tx:
        tx_list = [float(x.strip()) for x in args.tx.split(",") if x.strip()]
    else:
        tx_list = DEFAULT_TX_POWERS_DBM[:]
    max_tx = max(tx_list)

    # Pasta de saída com timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path(args.outdir) if args.outdir else RESULT_BASE
    outdir = base / f"{SIM_NAME}_{timestamp}"
    ensure_dir(outdir)

    # Simulação
    frames = [simulate_one_power(p, max_tx) for p in tx_list]
    df_all = pd.concat(frames, ignore_index=True)

    # Tabelas
    df_all.to_csv(outdir / "resultados_toy1_detalhado.csv", index=False)
    df_all.groupby(["TX_dBm"]).agg(
        Energia_W=("Energia_W", "sum"),
        Throughput_Mbps=("Throughput_Mbps", "sum")
    ).to_csv(outdir / "resultados_toy1_resumo_por_potencia.csv")

    # Metadados
    meta = {
        "sim": SIM_NAME,
        "clusters": [],                 # nenhum cluster
        "dran_gnbs": DRAN_GNBS,         # 4..12
        "ues_per_gnb": UES_PER_GNB,
        "tx_powers_dbm": tx_list,
        "energy_coeffs": asdict(EC),
        "comp_enabled": False,
        "cus_off": True,
        "generated_at": timestamp,
        "output_dir": str(outdir)
    }
    with open(outdir / "metadata_toy1.json", "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # Gráficos
    plot_energy_vs_power(df_all, outdir)
    plot_efficiency_vs_power(df_all, outdir)
    plot_stack_energy(df_all, outdir)

    print(f"[OK] Resultados salvos em: {outdir}")
    print("Arquivos gerados:")
    print(" - resultados_toy1_detalhado.csv")
    print(" - resultados_toy1_resumo_por_potencia.csv")
    print(" - energia_vs_potencia_toy1.png")
    print(" - eficiencia_vs_potencia_toy1.png")
    print(" - stack_energy_breakdown_toy1.png")
    print(" - metadata_toy1.json")

if __name__ == "__main__":
    main()
