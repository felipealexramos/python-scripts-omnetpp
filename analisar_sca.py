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

# captura id da gNB e valor
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

def dbm_to_watts(p_dbm: float) -> float:
    # P[W] = 10^((dBm-30)/10)
    return 10 ** ((float(p_dbm) - 30.0) / 10.0)

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

    # Throughput por UE
    ue_rx_vals = [float(v) for (_, _, v) in RE_UE_RX.findall(text)]
    ue_rx_mbps = to_mbps(ue_rx_vals)
    sum_rate_mbps = sum(ue_rx_mbps) if ue_rx_mbps else 0.0
    # UEs "ativos" (aprox.) = UEs com throughput > 0
    ue_active_count = sum(1 for v in ue_rx_mbps if v > 0)

    # Delay médio (ignora NaN/Inf)
    ue_delay_vals = [float(v) for (_, _, v) in RE_UE_DELAY.findall(text)]
    ue_delay_ms = to_ms(ue_delay_vals)
    mean_delay_ms = safe_mean(ue_delay_ms, default=0.0)

    # CNProcDemand por gNB (lista por id)
    gnb_proc_pairs = [(int(gnb), float(val)) for (gnb, val) in RE_GNB_PROC.findall(text)]
    gnb_ids = sorted({gid for (gid, _) in gnb_proc_pairs})
    gnb_proc_vals = [val for (_, val) in gnb_proc_pairs]

    mean_proc_gops = safe_mean(gnb_proc_vals, default=0.0)  # média por gNB
    sum_proc_gops  = sum(_finite(gnb_proc_vals))            # soma total (todas gNBs)

    p_dbm = infer_power_from_name(sca)

    return {
        "file": str(sca),
        "p_dbm": p_dbm,
        "sum_rate_mbps": sum_rate_mbps,
        "ue_active_count": ue_active_count,
        "mean_delay_ms": mean_delay_ms,
        "custo_computacional_gops_media_gnb": mean_proc_gops,
        "custo_computacional_gops_soma": sum_proc_gops,
        "gnb_count": len(gnb_ids)
    }

# ---------------------------
# Energia / Eficiência
# ---------------------------
def compute_power_energy_eff(power_dbm, proc_sum_gops, ue_active_mean, thp_sum_mbps, cfg: dict):
    """
    Modelo: P_tot = P_idle + alpha * D_proc + beta * N_UE_ativos + gamma * P_Tx_W
             E_tot = P_tot * T_sim
             ef_mbps_per_j = (Throughput_Mbps) / (P_tot_W)   # Mbps/J ≡ Mbps/W
    """
    g = cfg.get("general", {})
    P_idle = float(g.get("idle_power_w", 0.0))
    alpha  = float(g.get("alpha", 0.0))
    beta   = float(g.get("beta", 0.0))
    gamma  = float(g.get("gamma", 0.0))
    T_sim  = float(g.get("sim_time_s", 20.0))

    P_tx_W = dbm_to_watts(power_dbm or 0.0)

    P_tot_W = P_idle + alpha * float(proc_sum_gops or 0.0) + \
              beta * float(ue_active_mean or 0.0) + \
              gamma * P_tx_W

    # limites opcionais
    limits = cfg.get("limits", {})
    if "min_power_w" in limits:
        P_tot_W = max(P_tot_W, float(limits["min_power_w"]))
    if "max_power_w" in limits:
        P_tot_W = min(P_tot_W, float(limits["max_power_w"]))

    E_tot_J   = P_tot_W * T_sim
    E_tot_kWh = E_tot_J / 3_600_000.0  # 1 kWh = 3.6e6 J

    eff_mbps_per_j = (float(thp_sum_mbps or 0.0)) / max(P_tot_W, 1e-12)

    return {
        "P_tot_W": P_tot_W,
        "E_tot_J": E_tot_J,
        "E_tot_kWh": E_tot_kWh,
        "eff_mbps_per_joule": eff_mbps_per_j,
        "P_tx_W": P_tx_W,
        "sim_time_s": T_sim
    }

def compute_global_eff_index(thp_mbps, energy_j, delay_ms, cfg: dict):
    """Índice de Eficiência Global (IEG) = (Thp/E) * 1/(1 + Delay/D0)."""
    D0 = float(cfg.get("general", {}).get("delay_ref_ms", 10.0))
    thp = float(thp_mbps or 0.0)
    ene = max(float(energy_j or 0.0), 1e-12)
    dly = max(float(delay_ms or 0.0), 0.0)
    return (thp / ene) * (1.0 / (1.0 + dly / D0))

# ---------------------------
# Gráficos auxiliares (legenda inferior direita)
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
    plt.legend(loc="lower right")
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
    ax.legend(title="Potência", loc="lower right")
    fig.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close()

# ---------------------------
# Processamento por solução
# ---------------------------
def process_topology(topology_dir: Path, out_dir: Path, energy_cfg: dict | None):
    ensure_dir(out_dir)
    sca_files = sorted(topology_dir.glob("*.sca"))
    if not sca_files:
        print(f"[WARN] Sem .sca em {topology_dir}")
        return None

    rows = [parse_sca(s) for s in sca_files if s.is_file()]
    with open(out_dir/"resumo_por_arquivo.json","w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    agg = defaultdict(lambda: {
        "thp":[], "dly":[], "proc_mean":[], "proc_sum":[], "ues_active":[], "gnb_count":[]
    })

    for r in rows:
        if r["p_dbm"] is None:
            continue
        p = r["p_dbm"]
        agg[p]["thp"].append(r["sum_rate_mbps"])
        agg[p]["dly"].append(r["mean_delay_ms"])
        agg[p]["proc_mean"].append(r["custo_computacional_gops_media_gnb"])
        agg[p]["proc_sum"].append(r["custo_computacional_gops_soma"])
        agg[p]["ues_active"].append(r["ue_active_count"])
        agg[p]["gnb_count"].append(r["gnb_count"])

    powers = sorted(agg.keys())
    thp_series      = [safe_mean(agg[p]["thp"])       for p in powers]
    delay_series    = [safe_mean(agg[p]["dly"])       for p in powers]
    proc_mean_series= [safe_mean(agg[p]["proc_mean"]) for p in powers]
    proc_sum_series = [safe_mean(agg[p]["proc_sum"])  for p in powers]
    ues_act_series  = [safe_mean(agg[p]["ues_active"])for p in powers]
    gnb_count_ser   = [int(round(safe_mean(agg[p]["gnb_count"], 0))) for p in powers]

    # Tabela por potência (inclui energia/eficiência quando cfg fornecido)
    table = []
    for i, p in enumerate(powers):
        row = {
            "potencia_dbm": p,
            "vazao_media_mbps": thp_series[i],
            "delay_medio_ms":   delay_series[i],
            "custo_computacional_gops_media_gnb": proc_mean_series[i],
            "custo_computacional_gops_soma":      proc_sum_series[i],
            "ues_ativos_medios": ues_act_series[i],
            "gnb_count": gnb_count_ser[i]
        }
        if energy_cfg:
            em = compute_power_energy_eff(
                p,
                proc_sum_series[i],
                ues_act_series[i],
                thp_series[i],
                energy_cfg
            )
            row.update(em)
            # índice de eficiência global
            row["global_eff_index"] = compute_global_eff_index(
                thp_series[i], em["E_tot_J"], delay_series[i], energy_cfg
            )
        table.append(row)

    with open(out_dir/"resumo_por_potencia.json","w") as f:
        json.dump(table, f, indent=2, ensure_ascii=False)

    # Nome normalizado
    name = toy_to_solucao(topology_dir.name)

    # Gráficos EXISTENTES (inalterados)
    plot_xy_multi(powers, {name: dict(zip(powers, thp_series))},
                  "Vazão média (Mbps)", f"{name}: Potência × Vazão",
                  out_dir/"potencia_vs_vazao.png")
    plot_xy_multi(powers, {name: dict(zip(powers, delay_series))},
                  "Delay médio (ms)", f"{name}: Potência × Delay",
                  out_dir/"potencia_vs_delay.png")
    plot_xy_multi(powers, {name: dict(zip(powers, proc_mean_series))},
                  "Custo computacional (GOPS)", f"{name}: Potência × Custo computacional",
                  out_dir/"potencia_vs_custo.png")

    # NOVOS gráficos por Solução (se energy_cfg)
    if energy_cfg:
        energia_kwh = []
        eficiencia  = []
        ieg_series  = []
        for i, p in enumerate(powers):
            em = compute_power_energy_eff(p, proc_sum_series[i], ues_act_series[i], thp_series[i], energy_cfg)
            energia_kwh.append(em["E_tot_kWh"])
            eficiencia.append(em["eff_mbps_per_joule"])
            ieg_series.append(compute_global_eff_index(thp_series[i], em["E_tot_J"], delay_series[i], energy_cfg))

        plot_xy_multi(
            powers, {name: dict(zip(powers, energia_kwh))},
            "Energia total (kWh)", f"{name}: Potência × Energia (kWh)",
            out_dir/"potencia_vs_energia_kwh.png"
        )
        plot_xy_multi(
            powers, {name: dict(zip(powers, eficiencia))},
            "Eficiência (Mbps/J)", f"{name}: Potência × Eficiência energética",
            out_dir/"potencia_vs_eficiencia.png"
        )
        plot_xy_multi(
            powers, {name: dict(zip(powers, ieg_series))},
            "Índice de Eficiência Global (a.u.)", f"{name}: Potência × IEG",
            out_dir/"potencia_vs_indice_eficiencia_global.png"
        )

    return {
        "name": name, "powers": powers,
        "thp": thp_series, "delay": delay_series, "proc": proc_mean_series
    }

# ---------------------------
# Comparações globais
# ---------------------------
def comparisons_all_solutions(topologies_data, out_root: Path, energy_cfg: dict | None):
    import numpy as np

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

    # EXISTENTES (inalterados)
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

    # NOVOS comparativos globais (se energy_cfg)
    if energy_cfg:
        # Reabrimos os JSONs gerados por solução para capturar Energia/IEG por potência
        energia_vals = {sol: [] for sol in labels_solucoes}
        eficien_vals = {sol: [] for sol in labels_solucoes}
        ieg_vals     = {sol: [] for sol in labels_solucoes}

        scatter_E, scatter_D, scatter_S, scatter_C = [], [], [], []  # energia, delay, size(vazão), cor(solução)
        color_map = {sol: i for i, sol in enumerate(labels_solucoes)}

        for sol in labels_solucoes:
            toy_dir = sol.replace("Solução", "Toy")
            rjson = Path(out_root) / toy_dir / "resumo_por_potencia.json"
            if not rjson.exists():
                continue
            rows = json.loads(rjson.read_text())
            byp = {r["potencia_dbm"]: r for r in rows}
            for p in power_axis:
                thp = byp.get(p, {}).get("vazao_media_mbps", 0.0)
                dly = byp.get(p, {}).get("delay_medio_ms", 0.0)
                if "E_tot_kWh" in byp.get(p, {}):
                    E_kWh = byp[p]["E_tot_kWh"]
                    E_J   = byp[p]["E_tot_J"]
                    eff   = byp[p]["eff_mbps_per_joule"]
                else:
                    # recalcula se necessário
                    proc_sum = byp.get(p, {}).get("custo_computacional_gops_soma", 0.0)
                    ues = byp.get(p, {}).get("ues_ativos_medios", 0.0)
                    em = compute_power_energy_eff(p, proc_sum, ues, thp, energy_cfg)
                    E_kWh = em["E_tot_kWh"]; E_J = em["E_tot_J"]; eff = em["eff_mbps_per_joule"]

                energia_vals[sol].append(E_kWh)
                eficien_vals[sol].append(eff)

                ieg = compute_global_eff_index(thp, E_J, dly, energy_cfg)
                ieg_vals[sol].append(ieg)

                # dados do scatter (um ponto por solução×potência)
                scatter_E.append(E_kWh)
                scatter_D.append(dly)
                # escala de tamanho simples: s = a*thp + b, garantindo tamanho mínimo
                s = max(thp, 0.1) * 8.0
                scatter_S.append(s)
                scatter_C.append(color_map[sol])

        # 1) Scatter: Energia (kWh) x Delay (ms) com tamanho = Vazão (Mbps)
        plt.figure(figsize=(10,6))
        sc = plt.scatter(scatter_E, scatter_D, s=scatter_S, c=scatter_C, cmap="tab10", alpha=0.8, edgecolors="k", linewidths=0.3)
        # criar legenda por solução
        handles = []
        import matplotlib.patches as mpatches
        for sol, idx in color_map.items():
            patch = mpatches.Patch(color=plt.cm.tab10(idx), label=sol)
            handles.append(patch)
        plt.legend(handles=handles, loc="lower right", title="Soluções")
        plt.xlabel("Energia total (kWh)")
        plt.ylabel("Delay médio (ms)")
        plt.title("Eficiência: Energia × Delay (tamanho = Vazão em Mbps)")
        plt.grid(True, linestyle=":")
        plt.tight_layout()
        plt.savefig(Path(out_root)/"comparacao_scatter_energia_delay_bolhas.png", dpi=300)
        plt.close()

        # 2) Barras: IEG por Solução com uma barra por potência
        def dict_to_vbp(d):
            return {p: [d[sol][i] if i < len(d[sol]) else 0.0 for sol in labels_solucoes]
                    for i, p in enumerate(power_axis)}
        plot_grouped_bars_by_power(
            labels_solucoes, power_axis, dict_to_vbp(ieg_vals),
            "Índice de Eficiência Global (a.u.)",
            "IEG × Solução (uma barra por potência)",
            Path(out_root)/"comparacao_indice_eficiencia_global_barras_por_potencia.png"
        )

        # 3) Barras: IEG médio por Solução (média ao longo das potências)
        ieg_media = [safe_mean(ieg_vals[sol]) for sol in labels_solucoes]
        x = np.arange(len(labels_solucoes))
        plt.figure(figsize=(max(10, 1.2*len(labels_solucoes)), 5))
        plt.bar(x, ieg_media)
        plt.xticks(x, labels_solucoes)
        plt.ylabel("Índice de Eficiência Global (a.u.)")
        plt.title("IEG médio por Solução (média nas potências)")
        plt.grid(axis="y", linestyle=":", alpha=0.6)
        plt.tight_layout()
        plt.savefig(Path(out_root)/"comparacao_indice_eficiencia_global_barras_media.png", dpi=300)
        plt.close()

# ---------------------------
# Main
# ---------------------------
def main():
    ap = argparse.ArgumentParser(description="Extrai métricas dos .sca, gera gráficos e calcula energia/eficiência.")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--toys", nargs="*", default=DEFAULT_TOYS)
    ap.add_argument("--out",  default=DEFAULT_OUT)
    ap.add_argument("--energy-cfg", help="Arquivo JSON com parâmetros energéticos (idle_power_w, alpha, beta, gamma, sim_time_s, delay_ref_ms, ...)")
    args = ap.parse_args()

    out_root = Path(args.out)
    ensure_dir(out_root)

    energy_cfg = None
    if args.energy_cfg:
        energy_cfg = json.loads(Path(args.energy_cfg).read_text())

    topologies_data = []
    base = Path(args.base)
    for toy in args.toys:
        topologies_data.append(process_topology(base/toy, ensure_dir(out_root/toy), energy_cfg))

    comparisons_all_solutions([t for t in topologies_data if t], out_root, energy_cfg)

if __name__ == "__main__":
    main()
