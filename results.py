#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, glob, math, argparse
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------
# Caminhos do Felipe
# ---------------------------
DEFAULT_SCA_DIR = "/home/felipe/Documentos/tcc/omnet/ResultadosSCA"
DEFAULT_OUT_DIR = "/home/felipe/Documentos/tcc/omnet/ResultadosSCA/Graficos"

# ---------------------------
# Aliases de métricas (case-insensitive)
# ---------------------------
ALIASES: Dict[str, List[str]] = {
    "throughput": [
        "ReceivedThroughput", "receivedThroughput", "throughput",
        "ueThroughput", "avgThroughput", "cellThroughput", "app.rxThroughput"
    ],
    "sinr": [
        "SINR", "avgSINR", "meanSINR", "phy.sinr", "gNB_sinr", "ueSINR", "rsrpSinr"
    ],
    "cn_procdemand": [
        "CNProcDemand", "CnProcDemand", "cnProcDemand", "coreProcDemand", "procDemand"
    ],
    "tx_power": [
        "eNodeBTxPower", "gNBTxPower", "txPower", "phy.txPower", "eNBtxPower"
    ],
}

# Potência em dBm no caminho, ex.: ".../Pot26/..." ou ".../Power46/..."
REGEX_POT_IN_PATH = re.compile(r"(?:Pot|Potencia|Power)(\d{1,2})", re.IGNORECASE)

# ---------------------------
# Leitura do .sca simples
# ---------------------------
SCALAR_LINE = re.compile(r'^scalar\s+([^\s]+)\s+([^\s]+)\s+([-\d.eE]+)(?:\s+(\S+))?', re.UNICODE)

@dataclass
class ScalarRecord:
    module: str
    name: str
    value: float
    unit: Optional[str] = None

def parse_sca_file(path: str) -> List[ScalarRecord]:
    out: List[ScalarRecord] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.startswith("scalar"):
                continue
            m = SCALAR_LINE.match(line.strip())
            if not m:
                continue
            module, name, value, unit = m.groups()
            try:
                v = float(value)
            except ValueError:
                continue
            out.append(ScalarRecord(module, name, v, unit))
    return out

def agg_metric(records: List[ScalarRecord], candidates: List[str]) -> Optional[float]:
    cand = [c.lower() for c in candidates]
    vals: List[float] = []
    for r in records:
        n = r.name.lower()
        if n in cand or any(c in n for c in cand):
            vals.append(r.value)
    if not vals:
        return None
    return float(sum(vals) / len(vals))

def watts_to_dbm(w: float) -> float:
    return 10.0 * math.log10(max(w, 1e-12) / 1e-3)

def infer_power_dbm(path: str, records: List[ScalarRecord]) -> Optional[float]:
    # 1) preferir scalar de potência
    tx = agg_metric(records, ALIASES["tx_power"])
    if tx is not None:
        # Se vier em Watts (ex.: 40 W), converte para dBm; se já for dBm (~6..56), retorna
        if tx > 1.0:  # heurística
            return watts_to_dbm(tx)
        return tx
    # 2) tentar pelo caminho
    m = REGEX_POT_IN_PATH.search(path)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None

# ---------------------------
# Modelo energético (Plano B)
# P̄_gNB = P_idle + α * D_proc + β * N_UEs
# com P_idle, α, β dependentes de P_tx (em W)
# ---------------------------
@dataclass
class EnergyCalib:
    P_idle_base: float = 80.0   # W
    k_idle: float = 0.5         # W por W de P_tx
    alpha_base: float = 0.04    # W/GOPS
    k_alpha: float = 0.0001     # (W/GOPS)/W
    beta_base: float = 0.3      # W/UE
    k_beta: float = 0.005       # (W/UE)/W

def dbm_to_watts(dbm: float) -> float:
    return 10 ** (dbm / 10.0) * 1e-3

def gnb_power_energy(ptx_dbm: float, dproc_gops: float, n_ues: int, tsim: float, calib: EnergyCalib) -> Tuple[float, float]:
    ptx_w = dbm_to_watts(ptx_dbm)
    P_idle = calib.P_idle_base + calib.k_idle * ptx_w
    alpha  = calib.alpha_base  + calib.k_alpha * ptx_w
    beta   = calib.beta_base   + calib.k_beta * ptx_w
    P_avg  = P_idle + alpha * dproc_gops + beta * n_ues
    E_tot  = P_avg * tsim
    return P_avg, E_tot

# ---------------------------
# Utilidades
# ---------------------------
def ensure_dir(d: str):
    os.makedirs(d, exist_ok=True)

def plot_xy(x, y, xlabel, ylabel, title, outpath):
    plt.figure()
    plt.plot(x, y, marker="o")
    plt.xlabel(xlabel); plt.ylabel(ylabel); plt.title(title)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(outpath, dpi=220)
    plt.close()

# ---------------------------
# Pipeline principal
# ---------------------------
def main():
    ap = argparse.ArgumentParser(description="Extrai métricas de .sca (Simu5G) e gera gráficos e CSV.")
    ap.add_argument("--sca-dir", default=DEFAULT_SCA_DIR, help="Pasta com os .sca")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Pasta para salvar gráficos/CSV")
    ap.add_argument("--tsim", type=float, default=20.0, help="Tempo de simulação (s)")
    ap.add_argument("--num-ues", type=int, default=39, help="Número médio de UEs ativos")
    ap.add_argument("--powers", type=float, nargs="*", default=[6,16,26,36,46,56], help="Potências esperadas (dBm)")
    # calibração
    ap.add_argument("--P_idle_base", type=float, default=80.0)
    ap.add_argument("--k_idle", type=float, default=0.5)
    ap.add_argument("--alpha_base", type=float, default=0.04)
    ap.add_argument("--k_alpha", type=float, default=0.0001)
    ap.add_argument("--beta_base", type=float, default=0.3)
    ap.add_argument("--k_beta", type=float, default=0.005)
    args = ap.parse_args()

    ensure_dir(args.out_dir)
    calib = EnergyCalib(args.P_idle_base, args.k_idle, args.alpha_base, args.k_alpha, args.beta_base, args.k_beta)

    sca_paths = sorted(set(glob.glob(os.path.join(args.sca_dir, "**", "*.sca"), recursive=True)))
    if not sca_paths:
        raise SystemExit(f"Nenhum .sca encontrado em: {args.sca_dir}")

    rows = []
    for p in sca_paths:
        recs = parse_sca_file(p)
        thr  = agg_metric(recs, ALIASES["throughput"])
        sinr = agg_metric(recs, ALIASES["sinr"])
        cn   = agg_metric(recs, ALIASES["cn_procdemand"])
        pdbm = infer_power_dbm(p, recs)
        rows.append({"path": p, "power_dbm": pdbm, "throughput": thr, "sinr": sinr, "cn_procdemand": cn})

    df = pd.DataFrame(rows)

    # tentativa extra de inferir potência por nome do diretório
    miss = df["power_dbm"].isna()
    if miss.any():
        fixed = []
        for path in df.loc[miss, "path"]:
            m = REGEX_POT_IN_PATH.search(os.path.dirname(path))
            fixed.append(float(m.group(1)) if m else None)
        df.loc[miss, "power_dbm"] = fixed

    # manter apenas potências esperadas, se fornecidas
    if args.powers:
        df = df[df["power_dbm"].isin(args.powers)]

    # agregação por potência
    agg = df.groupby("power_dbm", as_index=False).agg({
        "throughput": "mean",
        "sinr": "mean",
        "cn_procdemand": "mean",
    }).sort_values("power_dbm")

    # calcular P̄_gNB, Energia e Eficiência
    Pavg_list, E_list = [], []
    for _, r in agg.iterrows():
        pdbm = float(r["power_dbm"])
        dproc = float(r["cn_procdemand"]) if pd.notna(r["cn_procdemand"]) else 0.0
        Pavg, Etot = gnb_power_energy(pdbm, dproc, args.num_ues, args.tsim, calib)
        Pavg_list.append(Pavg); E_list.append(Etot)
    agg["Pavg_gNB_W"] = Pavg_list
    agg["E_total_J"] = E_list
    # Eficiência energética: Throughput / Energia (use a unidade do seu throughput)
    agg["EE_throughput_per_J"] = agg["throughput"] / agg["E_total_J"]

    # salvar CSV
    ensure_dir(args.out_dir)
    csv_path = os.path.join(args.out_dir, "resumo_por_potencia.csv")
    agg.to_csv(csv_path, index=False)

    # ---- Gráficos ----
    # 1) Throughput × Potência
    if agg["throughput"].notna().any():
        plot_xy(agg["power_dbm"], agg["throughput"],
                "Potência de Tx (dBm)", "Throughput médio (unidade do .sca)",
                "Throughput × Potência", os.path.join(args.out_dir, "01_throughput_vs_power.png"))
    # 2) SINR × Potência
    if agg["sinr"].notna().any():
        plot_xy(agg["power_dbm"], agg["sinr"],
                "Potência de Tx (dBm)", "SINR médio (dB)",
                "Qualidade de Sinal (SINR) × Potência", os.path.join(args.out_dir, "02_sinr_vs_power.png"))
    # 3) CNProcDemand × Potência
    if agg["cn_procdemand"].notna().any():
        plot_xy(agg["power_dbm"], agg["cn_procdemand"],
                "Potência de Tx (dBm)", "Demanda de Processamento (GOPS)",
                "CNProcDemand × Potência", os.path.join(args.out_dir, "03_cnprocdemand_vs_power.png"))
    # 4) P̄_gNB × Potência
    plot_xy(agg["power_dbm"], agg["Pavg_gNB_W"],
            "Potência de Tx (dBm)", "Potência média da gNB (W)",
            "Potência média da gNB × Potência", os.path.join(args.out_dir, "04_pavg_gnb_vs_power.png"))
    # 5) Energia Total × Potência
    plot_xy(agg["power_dbm"], agg["E_total_J"],
            "Potência de Tx (dBm)", "Energia total (J)",
            f"Energia Total × Potência (T_sim={args.tsim}s, N_UEs={args.num_ues})",
            os.path.join(args.out_dir, "05_energy_vs_power.png"))
    # 6) Eficiência Energética × Potência
    if agg["EE_throughput_per_J"].notna().any():
        plot_xy(agg["power_dbm"], agg["EE_throughput_per_J"],
                "Potência de Tx (dBm)", "Eficiência (Throughput/J)",
                "Eficiência Energética × Potência", os.path.join(args.out_dir, "06_efficiency_vs_power.png"))

    print(f"✅ CSV: {csv_path}")
    print(f"✅ Gráficos salvos em: {args.out_dir}")
    print(agg)

if __name__ == "__main__":
    main()
