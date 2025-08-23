
import os
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =====================================================
# calculate.py  — versão robusta (com cenários e 5 gráficos extras)
# =====================================================
# O script:
# 1) calcula energia/eficiência por potência usando DOIS MODELOS:
#    (A) Modelo base: P_gNB = P_idle + α*D_proc + β*N_UE + γ*P_TX
#    (B) Modelo estendido: coeficientes dependem de P_TX
#         P_idle(P) = P_idle_base + k_idle*P
#         α(P)      = α_base     + k_α*P
#         β(P)      = β_base     + k_β*P
# 2) permite parametrizar múltiplos CENÁRIOS;
# 3) salva CSVs;
# 4) gera automaticamente os 5 gráficos extras:
#    - pareto_throughput_vs_energy.png
#    - stack_energy_breakdown_<cenario>.png
#    - efficiency_per_ue.png
#    - marginal_gain.png
#    - economy_percent_between_configs.png
# além dos gráficos clássicos:
#    - energia_vs_potencia.png
#    - eficiencia_vs_potencia.png
#    - comparacao_consumo.png
# =====================================================

# ---------- Configuração global de saída ----------
OUTDIR = os.environ.get("OUTDIR", ".")
os.makedirs(OUTDIR, exist_ok=True)

# ---------- Helpers ----------
def dbm_to_watts(dbm: float) -> float:
    return 10 ** (dbm/10) * 1e-3

def annotate_points(ax, x, y, labels):
    for xi, yi, lab in zip(x, y, labels):
        ax.annotate(str(lab), (xi, yi), textcoords="offset points", xytext=(0, 6), ha='center', fontsize=8)

@dataclass
class Scenario:
    name: str
    # Parâmetros médios do cenário
    D_proc: float                    # (GOPS) demanda média de processamento
    N_UE: int                        # número médio de UEs ativos
    T_sim: float                     # duração (s)
    # Curva de potência de transmissão (dBm) e throughput (Mbps)
    potencias_dbm: List[float]
    throughput_mbps: List[float]
    # Modelo de transmissão: peso γ (W/W)
    gamma: float = 1.0
    # Coeficientes BASE (modelo A)
    P_idle: float = 100.0
    alpha: float = 0.05
    beta: float  = 0.5
    # Sensibilidades vs. P_TX (modelo B)
    Pidle_base: Optional[float] = None
    k_idle: Optional[float]     = None
    alpha_base: Optional[float] = None
    k_alpha: Optional[float]    = None
    beta_base: Optional[float]  = None
    k_beta: Optional[float]     = None

    def uses_extended(self) -> bool:
        return all(v is not None for v in [self.Pidle_base, self.k_idle,
                                           self.alpha_base, self.k_alpha,
                                           self.beta_base, self.k_beta])

def energy_components(scn: Scenario, p_dbm: float):
    P_tx = dbm_to_watts(p_dbm)
    if scn.uses_extended():
        Pidle = scn.Pidle_base + scn.k_idle * P_tx
        alpha = scn.alpha_base + scn.k_alpha * P_tx
        beta  = scn.beta_base  + scn.k_beta  * P_tx
    else:
        Pidle = scn.P_idle
        alpha = scn.alpha
        beta  = scn.beta
    P_proc = alpha * scn.D_proc
    P_ue   = beta  * scn.N_UE
    P_tx_c = scn.gamma * P_tx
    P_gnb  = Pidle + P_proc + P_ue + P_tx_c
    return dict(P_tx_W=P_tx, P_idle=Pidle, P_proc=P_proc, P_ue=P_ue, P_tx=P_tx_c, P_gnb=P_gnb)

def compute_dataframe(scn: Scenario) -> pd.DataFrame:
    rows = []
    for p_dbm, th_mbps in zip(scn.potencias_dbm, scn.throughput_mbps):
        comps = energy_components(scn, p_dbm)
        E_total = comps["P_gnb"] * scn.T_sim
        throughput_bits = th_mbps * 1e6  # Mbps -> bps
        eff_bits_per_J  = throughput_bits / comps["P_gnb"]
        rows.append({
            "Cenário": scn.name,
            "Potência (dBm)": p_dbm,
            "Potência Tx (W)": comps["P_tx_W"],
            "P_idle (W)": comps["P_idle"],
            "P_proc (W)": comps["P_proc"],
            "P_UE (W)":   comps["P_ue"],
            "P_TxComp (W)": comps["P_tx"],
            "P_gNB (W)": comps["P_gnb"],
            "Energia (J)": E_total,
            "Throughput (Mbps)": th_mbps,
            "Eficiência (bits/J)": eff_bits_per_J,
            "UEs": scn.N_UE
        })
    df = pd.DataFrame(rows)
    # Ordena por potência
    return df.sort_values("Potência (dBm)").reset_index(drop=True)

# ---------- Cenários de exemplo (edite conforme seus dados) ----------
potencias = [5,10,15,20,25,30,35,40,45,50,55,60]
def saturating_throughput(dbm):
    # curva apenas para exemplo; substitua pelos dados reais do Simu5G quando tiver
    return 20 + 60*(1 - np.exp(-(dbm-5)/18))  # Mbps

th_curve = [float(saturating_throughput(p)) for p in potencias]

scenarios: List[Scenario] = [
    # Cenário 1 — Modelo base
    Scenario(
        name="Configuração 1",
        D_proc=50.0, N_UE=10, T_sim=20.0,
        potencias_dbm=potencias,
        throughput_mbps=th_curve,
        gamma=1.0,
        P_idle=100.0, alpha=0.05, beta=0.5
    ),
    # Cenário 2 — Modelo estendido (com sensibilidades)
    Scenario(
        name="Configuração 2",
        D_proc=60.0, N_UE=12, T_sim=20.0,
        potencias_dbm=potencias,
        throughput_mbps=[v*1.03 for v in th_curve],  # levemente maior
        gamma=1.0,
        Pidle_base=90.0, k_idle=0.5,
        alpha_base=0.04, k_alpha=0.0001,
        beta_base=0.30,  k_beta=0.005
    )
]

# ---------- Cálculo e persistência ----------
frames = []
for scn in scenarios:
    df = compute_dataframe(scn)
    frames.append(df)
    csv_path = os.path.join(OUTDIR, f"results_{scn.name.replace(' ','_')}.csv")
    df.to_csv(csv_path, index=False)

df_all = pd.concat(frames, ignore_index=True)
df_all.to_csv(os.path.join(OUTDIR, "results_all.csv"), index=False)

# ---------- Gráficos clássicos ----------
def plot_energy_vs_power(df: pd.DataFrame):
    plt.figure(figsize=(8,5))
    for name, group in df.groupby("Cenário"):
        plt.plot(group["Potência (dBm)"], group["Energia (J)"], marker="o", label=name)
    plt.xlabel("Potência de Transmissão (dBm)")
    plt.ylabel("Energia Total Consumida (J)")
    plt.title("Energia vs. Potência de Transmissão")
    plt.grid(True, linestyle=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "energia_vs_potencia.png"), dpi=300)

def plot_efficiency_vs_power(df: pd.DataFrame):
    plt.figure(figsize=(8,5))
    for name, group in df.groupby("Cenário"):
        plt.plot(group["Potência (dBm)"], group["Eficiência (bits/J)"], marker="o", label=name)
    plt.xlabel("Potência de Transmissão (dBm)")
    plt.ylabel("Eficiência (bits/J)")
    plt.title("Eficiência Energética vs. Potência")
    plt.grid(True, linestyle=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "eficiencia_vs_potencia.png"), dpi=300)

def plot_energy_bar_by_config(df: pd.DataFrame):
    consumo_medio = df.groupby("Cenário")["Energia (J)"].mean().sort_values()
    plt.figure(figsize=(6,5))
    consumo_medio.plot(kind="bar")
    plt.ylabel("Energia Média (J)")
    plt.title("Consumo Médio de Energia por Configuração")
    plt.grid(axis="y", linestyle=":")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "comparacao_consumo.png"), dpi=300)

plot_energy_vs_power(df_all)
plot_efficiency_vs_power(df_all)
plot_energy_bar_by_config(df_all)

# ---------- 5 Gráficos EXTRA ----------
# 1) Pareto Throughput vs Energia
def plot_pareto(df: pd.DataFrame):
    plt.figure(figsize=(7.5,6))
    for name, g in df.groupby("Cenário"):
        plt.scatter(g["Energia (J)"], g["Throughput (Mbps)"], label=name, s=45)
        annotate_points(plt.gca(), g["Energia (J)"], g["Throughput (Mbps)"], g["Potência (dBm)"])
    plt.xlabel("Energia (J)")
    plt.ylabel("Vazão Total (Mbps)")
    plt.title("Fronteira Pareto: Vazão vs Energia")
    plt.grid(True, linestyle=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "pareto_throughput_vs_energy.png"), dpi=300)

# 2) Decomposição (barras empilhadas) — uma figura por cenário
def plot_stack_energy(df: pd.DataFrame, scn_name: str):
    g = df[df["Cenário"]==scn_name]
    base = np.zeros(len(g))
    plt.figure(figsize=(9,5))
    for comp, label in [("P_idle (W)", "Idle"),
                        ("P_proc (W)", "Proc."),
                        ("P_UE (W)",   "UE"),
                        ("P_TxComp (W)", "Tx")]:
        plt.bar(g["Potência (dBm)"], g[comp], bottom=base, label=label, width=2.8)
        base = base + g[comp].values
    plt.xlabel("Potência (dBm)")
    plt.ylabel("Potência média (W)")
    plt.title(f"Decomposição da Potência — {scn_name}")
    plt.grid(axis="y", linestyle=":")
    plt.legend()
    plt.tight_layout()
    fname = f"stack_energy_breakdown_{scn_name.replace(' ','_')}.png"
    plt.savefig(os.path.join(OUTDIR, fname), dpi=300)

# 3) Eficiência por UE (bits/J/UE)
def plot_eff_per_ue(df: pd.DataFrame):
    df2 = df.copy()
    df2["Eff_per_UE"] = df2["Eficiência (bits/J)"] / df2["UEs"]
    plt.figure(figsize=(8,5))
    for name, g in df2.groupby("Cenário"):
        plt.plot(g["Potência (dBm)"], g["Eff_per_UE"], marker="o", label=name)
    plt.xlabel("Potência (dBm)")
    plt.ylabel("Eficiência por UE (bits/J/UE)")
    plt.title("Eficiência Energética Normalizada por UE")
    plt.grid(True, linestyle=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "efficiency_per_ue.png"), dpi=300)

# 4) Ganho marginal (ΔThroughput / ΔEnergia)
def plot_marginal_gain(df: pd.DataFrame):
    plt.figure(figsize=(8,5))
    for name, g in df.groupby("Cenário"):
        g = g.sort_values("Potência (dBm)")
        dE = np.diff(g["Energia (J)"])
        dT = np.diff(g["Throughput (Mbps)"])*1e6  # bps
        gain = dT / dE
        x = g["Potência (dBm)"].values[1:]
        plt.plot(x, gain, marker="o", label=name)
    plt.xlabel("Potência (dBm)")
    plt.ylabel("Ganho marginal (bps/J)")
    plt.title("Ganho Marginal de Vazão por Unidade de Energia")
    plt.grid(True, linestyle=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "marginal_gain.png"), dpi=300)

# 5) Economia percentual entre configurações (por potência)
def plot_economy_percent(df: pd.DataFrame):
    if df["Cenário"].nunique() < 2:
        return
    a, b = list(df["Cenário"].unique())[:2]
    g1 = df[df["Cenário"]==a].set_index("Potência (dBm)")
    g2 = df[df["Cenário"]==b].set_index("Potência (dBm)")
    common = sorted(set(g1.index) & set(g2.index))
    econ = (g1.loc[common, "Energia (J)"] - g2.loc[common, "Energia (J)"]) / g1.loc[common, "Energia (J)"] * 100.0
    plt.figure(figsize=(8,5))
    plt.bar(common, econ, width=2.8)
    plt.axhline(0, color="k", linewidth=0.8)
    plt.xlabel("Potência (dBm)")
    plt.ylabel(f"Economia de {b} vs {a} (\%)")
    plt.title("Economia Percentual de Energia entre Configurações")
    plt.grid(axis="y", linestyle=":")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, "economy_percent_between_configs.png"), dpi=300)

# Executa plots extras
plot_pareto(df_all)
for scn in [s.name for s in scenarios]:
    plot_stack_energy(df_all, scn)
plot_eff_per_ue(df_all)
plot_marginal_gain(df_all)
plot_economy_percent(df_all)

print(f"Arquivos CSV salvos em: {OUTDIR}")
print("Gráficos gerados:")
print("- energia_vs_potencia.png")
print("- eficiencia_vs_potencia.png")
print("- comparacao_consumo.png")
print("- pareto_throughput_vs_energy.png")
for scn in [s.name for s in scenarios]:
    print(f"- stack_energy_breakdown_{scn.replace(' ','_')}.png")
print("- efficiency_per_ue.png")
print("- marginal_gain.png")
print("- economy_percent_between_configs.png")