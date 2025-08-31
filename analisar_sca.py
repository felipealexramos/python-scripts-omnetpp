#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, json, argparse, statistics, math
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

# ---------------------------
# Caminhos padrão
# ---------------------------
DEFAULT_BASE = "/home/felipe/Documentos/tcc/omnet/simu5g/simulations/NR/application03"
DEFAULT_OUT  = "/home/felipe/Documentos/tcc/omnet/ResultadosSCA/Graficos"
DEFAULT_TOYS = ["Toy1","Toy2","Toy3","Toy4","Toy5","Toy6"]

# ---------------------------
# Regex
# ---------------------------
NUM = r"(\d+(?:\.\d+)?)"
RE_PDBM_FROM_NAME = re.compile(r"(\d+)dBm", re.IGNORECASE)

RE_UE_RX = re.compile(
    rf"^scalar\s+.*\.ue\[(\d+)\]\.app\[(\d+)\]\s+"
    rf"(?:cbrReceivedThroughput|cbrReceivedThroughtput):mean\s+{NUM}\s*$",
    re.MULTILINE
)

RE_UE_DELAY = re.compile(
    rf"^scalar\s+.*\.ue\[(\d+)\]\.app\[(\d+)\]\s+cbrFrameDelay:mean\s+{NUM}\s*$",
    re.MULTILINE
)

RE_GNB_PROC = re.compile(
    rf"^scalar\s+.*\.gnb(\d+)\.cellularNic\.mac\s+CNProcDemand:mean\s+{NUM}\s*$",
    re.MULTILINE
)

# ---------------------------
# Utilidades
# ---------------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)
    return p

def infer_power_from_name(path: Path):
    m = RE_PDBM_FROM_NAME.search(path.name)
    return int(m.group(1)) if m else None

def _finite(vals):
    return [v for v in vals if isinstance(v, (int, float)) and math.isfinite(v)]

def to_mbps(values):
    vals = _finite([float(v) for v in values])
    if not vals:
        return []
    med = statistics.median(vals)
    return [v/1e6 for v in vals] if med > 1e5 else vals

def to_ms(values):
    vals = _finite([float(v) for v in values])
    if not vals:
        return []
    med = statistics.median(vals)
    return [v*1000.0 for v in vals] if med < 10.0 else vals

def safe_mean(values, default=0.0):
    vals = _finite(values)
    return (sum(vals)/len(vals)) if vals else default

def toy_to_solucao(name: str) -> str:
    if name.lower().startswith("toy") and len(name) > 3 and name[3:].isdigit():
        return f"Solução{name[3:]}"
    return name.replace("Toy", "Solução")

# ---------------------------
# Parser .sca
# ---------------------------
def parse_sca(sca: Path):
    text = sca.read_text(errors="ignore")

    ue_rx_vals = [float(v) for (_, _, v) in RE_UE_RX.findall(text)]
    ue_rx_mbps = to_mbps(ue_rx_vals)
    sum_rate_mbps = sum(ue_rx_mbps) if ue_rx_mbps else 0.0

    ue_delay_vals = [float(v) for (_, _, v) in RE_UE_DELAY.findall(text)]
    ue_delay_ms = to_ms(ue_delay_vals)
    mean_delay_ms = safe_mean(ue_delay_ms, default=0.0)

    gnb_proc_vals = [float(v) for (_, v) in RE_GNB_PROC.findall(text)]
    mean_proc_gops = safe_mean(gnb_proc_vals, default=0.0)

    p_dbm = infer_power_from_name(sca)

    return {
        "file": str(sca),
        "p_dbm": p_dbm,
        "sum_rate_mbps": sum_rate_mbps,
        "mean_delay_ms": mean_delay_ms,
        "custo_computacional_gops": mean_proc_gops
    }

# ---------------------------
# Gráficos auxiliares
# ---------------------------
def plot_xy_multi(power_axis, series_by_solution, ylabel, title, out_png):
    plt.figure(figsize=(9.5,5))
    for sol_name, ys in series_by_solution.items():
        yplotted = [ys.get(p, 0.0) for p in power_axis]
        plt.plot(power_axis, yplotted, marker="o", label=sol_name)
    plt.xlabel("Potência (dBm)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle=":")
    plt.legend(loc="lower right")  # <-- sempre inferior direita
    plt.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close()

def plot_grouped_bars_by_power(labels_solucoes, power_axis, values_by_power, ylabel, title, out_png):
    import numpy as np
    fig, ax = plt.subplots(figsize=(max(10, 1.3*len(labels_solucoes)), 5))
    x = np.arange(len(labels_solucoes))
    n = len(power_axis)
    width = min(0.8 / max(n, 1), 0.18)
    offsets = (np.arange(n) - (n-1)/2.0) * width

    for i, p in enumerate(power_axis):
        vals = values_by_power.get(p, [0.0]*len(labels_solucoes))
        ax.bar(x + offsets[i], vals, width, label=f"{p} dBm")

    ax.set_xticks(x)
    ax.set_xticklabels(labels_solucoes)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    ax.legend(title="Potência", loc="lower right")  # <-- sempre inferior direita
    fig.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close()

# ---------------------------
# Processamento por solução
# ---------------------------
def process_topology(topology_dir: Path, out_dir: Path):
    ensure_dir(out_dir)
    sca_files = sorted(topology_dir.glob("*.sca"))
    if not sca_files:
        print(f"[WARN] Sem .sca em {topology_dir}")
        return None

    rows = [parse_sca(s) for s in sca_files if s.is_file()]
    with open(out_dir/"resumo_por_arquivo.json","w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    agg = defaultdict(lambda: {"thp":[], "dly":[], "proc":[]})
    for r in rows:
        if r["p_dbm"] is None:
            continue
        agg[r["p_dbm"]]["thp"].append(r["sum_rate_mbps"])
        agg[r["p_dbm"]]["dly"].append(r["mean_delay_ms"])
        agg[r["p_dbm"]]["proc"].append(r["custo_computacional_gops"])

    powers = sorted(agg.keys())
    thp_series   = [safe_mean(agg[p]["thp"])  for p in powers]
    delay_series = [safe_mean(agg[p]["dly"])  for p in powers]
    proc_series  = [safe_mean(agg[p]["proc"]) for p in powers]

    table = [
        {"potencia_dbm": p,
         "vazao_media_mbps": thp_series[i],
         "delay_medio_ms":   delay_series[i],
         "custo_computacional_gops": proc_series[i]}
        for i,p in enumerate(powers)
    ]
    with open(out_dir/"resumo_por_potencia.json","w") as f:
        json.dump(table, f, indent=2, ensure_ascii=False)

    name = toy_to_solucao(topology_dir.name)

    plot_xy_multi(powers, {name: dict(zip(powers, thp_series))},
                  "Vazão média (Mbps)", f"{name}: Potência × Vazão",
                  out_dir/"potencia_vs_vazao.png")

    plot_xy_multi(powers, {name: dict(zip(powers, delay_series))},
                  "Delay médio (ms)", f"{name}: Potência × Delay",
                  out_dir/"potencia_vs_delay.png")

    plot_xy_multi(powers, {name: dict(zip(powers, proc_series))},
                  "Custo computacional (GOPS)", f"{name}: Potência × Custo computacional",
                  out_dir/"potencia_vs_custo.png")

    return {"name": name, "powers": powers, "thp": thp_series,
            "delay": delay_series, "proc": proc_series}

# ---------------------------
# Comparações globais
# ---------------------------
def comparisons_all_solutions(topologies_data, out_root: Path):
    power_axis = sorted({p for t in topologies_data for p in (t["powers"] if t else [])})
    labels_solucoes = [t["name"] for t in topologies_data if t]

    thp_by_sol  = {t["name"]: dict(zip(t["powers"], t["thp"]))   for t in topologies_data if t}
    dly_by_sol  = {t["name"]: dict(zip(t["powers"], t["delay"])) for t in topologies_data if t}
    proc_by_sol = {t["name"]: dict(zip(t["powers"], t["proc"]))  for t in topologies_data if t}

    def to_values_by_power(by_sol):
        result = {}
        for p in power_axis:
            vals = []
            for sol in labels_solucoes:
                vals.append(by_sol.get(sol, {}).get(p, 0.0))
            result[p] = vals
        return result

    plot_grouped_bars_by_power(labels_solucoes, power_axis,
        to_values_by_power(thp_by_sol),
        "Vazão média (Mbps)", "Vazão × Solução",
        out_root/"comparacao_vazao.png")

    plot_grouped_bars_by_power(labels_solucoes, power_axis,
        to_values_by_power(dly_by_sol),
        "Delay médio (ms)", "Delay × Solução",
        out_root/"comparacao_delay.png")

    plot_grouped_bars_by_power(labels_solucoes, power_axis,
        to_values_by_power(proc_by_sol),
        "Custo computacional (GOPS)", "Custo computacional × Solução",
        out_root/"comparacao_custo.png")

    plot_xy_multi(power_axis, thp_by_sol, "Vazão média (Mbps)",
                  "Vazão × Potência", out_root/"comparacao_vazao_linhas.png")
    plot_xy_multi(power_axis, dly_by_sol, "Delay médio (ms)",
                  "Delay × Potência", out_root/"comparacao_delay_linhas.png")
    plot_xy_multi(power_axis, proc_by_sol, "Custo computacional (GOPS)",
                  "Custo computacional × Potência", out_root/"comparacao_custo_linhas.png")

    resumo = {
        "power_axis_dbm": power_axis,
        "solucoes": labels_solucoes,
        "vazao_mbps": {sol: [thp_by_sol[sol].get(p, 0.0) for p in power_axis] for sol in labels_solucoes},
        "delay_ms":   {sol: [dly_by_sol[sol].get(p, 0.0) for p in power_axis] for sol in labels_solucoes},
        "custo_gops": {sol: [proc_by_sol[sol].get(p, 0.0) for p in power_axis] for sol in labels_solucoes},
    }
    with open(out_root/"comparacao.json","w") as f:
        json.dump(resumo, f, indent=2, ensure_ascii=False)

# ---------------------------
# Main
# ---------------------------
def main():
    ap = argparse.ArgumentParser(description="Extrai métricas dos .sca e gera gráficos.")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--toys", nargs="*", default=DEFAULT_TOYS)
    ap.add_argument("--out",  default=DEFAULT_OUT)
    args = ap.parse_args()

    out_root = Path(args.out)
    ensure_dir(out_root)

    topologies_data = []
    base = Path(args.base)
    for toy in args.toys:
        topologies_data.append(process_topology(base/toy, ensure_dir(out_root/toy)))

    comparisons_all_solutions([t for t in topologies_data if t], out_root)

if __name__ == "__main__":
    main()
