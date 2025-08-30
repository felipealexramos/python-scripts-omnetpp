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
# Regex (genéricos, sem fixar o nome da rede)
# ---------------------------
NUM = r"(\d+(?:\.\d+)?)"
RE_PDBM_FROM_NAME = re.compile(r"(\d+)dBm", re.IGNORECASE)

# vazão recebida por UE (aceita Throughput e Throughtput)
RE_UE_RX = re.compile(
    rf"^scalar\s+.*\.ue\[(\d+)\]\.app\[(\d+)\]\s+"
    rf"(?:cbrReceivedThroughput|cbrReceivedThroughtput):mean\s+{NUM}\s*$",
    re.MULTILINE
)

# delay por UE (frame delay até a UE)
RE_UE_DELAY = re.compile(
    rf"^scalar\s+.*\.ue\[(\d+)\]\.app\[(\d+)\]\s+cbrFrameDelay:mean\s+{NUM}\s*$",
    re.MULTILINE
)

# CNProcDemand por gNB (GOPS)
RE_GNB_PROC = re.compile(
    rf"^scalar\s+.*\.gnb(\d+)\.cellularNic\.mac\s+CNProcDemand:mean\s+{NUM}\s*$",
    re.MULTILINE
)

# opcional: proporção
RE_GNB_PROP = re.compile(
    rf"^scalar\s+.*\.gnb(\d+)\.cellularNic\.mac\s+CNProcDemandProportion:mean\s+{NUM}\s*$",
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
    """Retorna apenas valores finitos (ignora NaN/Inf)."""
    return [v for v in vals if isinstance(v, (int, float)) and math.isfinite(v)]

def to_mbps(values):
    """Converte automaticamente para Mbps: se a mediana finita for >1e5 assume bps."""
    vals = _finite(values)
    if not vals:
        return []
    med = statistics.median(vals)
    if med > 1e5:             # heurística: parece bps
        return [v/1e6 for v in vals]
    return vals               # já era Mbps (ou valor normalizado)

def to_ms(values):
    """
    Converte de segundos para ms (se os números parecerem segundos).
    Importante: remove NaN/Inf antes de decidir a unidade e antes de devolver.
    """
    vals = _finite(values)
    if not vals:
        return []
    med = statistics.median(vals)
    # se mediana < 10, provavelmente está em segundos → ms
    if med < 10.0:
        return [v*1000.0 for v in vals]
    return vals

def safe_mean(values, default=0.0):
    """Média ignorando NaN/Inf; retorna default se vazio."""
    vals = _finite(values)
    return (sum(vals)/len(vals)) if vals else default

def parse_sca(sca: Path):
    text = sca.read_text(errors="ignore")

    # vazão recebida por UE
    ue_rx_vals = [float(v) for (_, _, v) in RE_UE_RX.findall(text)]
    ue_rx_mbps = to_mbps(ue_rx_vals)
    sum_rate_mbps = sum(ue_rx_mbps) if ue_rx_mbps else 0.0

    # delay por UE (média de frame delay na simulação, ignorando NaN/Inf)
    ue_delay_vals = [float(v) for (_, _, v) in RE_UE_DELAY.findall(text)]
    ue_delay_ms = to_ms(ue_delay_vals)  # já vem filtrado
    # média correta: divide apenas pelo número de UEs com valor finito
    mean_delay_ms = safe_mean(ue_delay_ms, default=0.0)

    # processamento por gNB (GOPS)
    gnb_proc_vals = [float(v) for (_, v) in RE_GNB_PROC.findall(text)]
    mean_proc_gops = safe_mean(gnb_proc_vals, default=0.0)

    # proporção (opcional)
    gnb_prop_vals = [float(v) for (_, v) in RE_GNB_PROP.findall(text)]
    mean_prop = safe_mean(gnb_prop_vals, default=0.0)

    p_dbm = infer_power_from_name(sca)

    return {
        "file": str(sca),
        "p_dbm": p_dbm,
        "sum_rate_mbps": sum_rate_mbps,     # soma das UEs (Mbps)
        "mean_delay_ms": mean_delay_ms,     # média entre UEs (ms), ignorando NaN
        "mean_cnproc_gops": mean_proc_gops, # média em GOPS
        "mean_cnprop": mean_prop
    }

def plot_xy(xs, ys, xlabel, ylabel, title, out_png):
    plt.figure()
    plt.plot(xs, ys, marker="o")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle=":")
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()

def plot_scatter(xs, ys, xlabel, ylabel, title, out_png):
    plt.figure()
    plt.scatter(xs, ys)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle=":")
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()

def plot_bar(labels, values, ylabel, title, out_png):
    import numpy as np
    x = np.arange(len(labels))
    plt.figure(figsize=(9,4.6))
    plt.bar(x, values)
    plt.xticks(x, labels)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()

def process_topology(topology_dir: Path, out_dir: Path):
    ensure_dir(out_dir)
    sca_files = sorted(topology_dir.glob("*.sca"))
    if not sca_files:
        print(f"[WARN] Sem .sca em {topology_dir}")
        return None

    rows = [parse_sca(s) for s in sca_files if s.is_file()]
    # salva detalhado
    with open(out_dir/"resumo_por_arquivo.json","w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    # agrega por potência (média por potência)
    agg = defaultdict(lambda: {"thp":[], "dly":[], "proc":[], "prop":[]})
    for r in rows:
        if r["p_dbm"] is None:
            continue
        agg[r["p_dbm"]]["thp"].append(r["sum_rate_mbps"])
        agg[r["p_dbm"]]["dly"].append(r["mean_delay_ms"])
        agg[r["p_dbm"]]["proc"].append(r["mean_cnproc_gops"])
        agg[r["p_dbm"]]["prop"].append(r["mean_cnprop"])

    powers = sorted(agg.keys())
    thp_series   = [safe_mean(agg[p]["thp"],  default=0.0) for p in powers]
    delay_series = [safe_mean(agg[p]["dly"],  default=0.0) for p in powers]
    proc_series  = [safe_mean(agg[p]["proc"], default=0.0) for p in powers]
    prop_series  = [safe_mean(agg[p]["prop"], default=0.0) for p in powers]

    # salva agregado por potência
    table = [
        {"potencia_dbm": p,
         "vazao_media_mbps": thp_series[i],
         "delay_medio_ms":   delay_series[i],
         "cnproc_medio_gops":proc_series[i],
         "cnprop_medio":     prop_series[i]}
        for i,p in enumerate(powers)
    ]
    with open(out_dir/"resumo_por_potencia.json","w") as f:
        json.dump(table, f, indent=2, ensure_ascii=False)

    # ----- Gráficos por topologia -----
    name = topology_dir.name

    # Potência × Vazão
    plot_xy(powers, thp_series, "Potência (dBm)", "Vazão média agregada (Mbps)",
            f"{name}: Potência × Vazão", out_dir/"potencia_vs_vazao.png")

    # Potência × CNProcDemand
    plot_xy(powers, proc_series, "Potência (dBm)", "CNProcDemand médio (GOPS)",
        f"{name}: Potência × CNProcDemand", out_dir/"potencia_vs_cnprocdemand.png")

    # Potência × Delay
    plot_xy(powers, delay_series, "Potência (dBm)", "Delay médio (ms)",
            f"{name}: Potência × Delay (cbrFrameDelay)", out_dir/"potencia_vs_delay.png")

    # Opcional: proporção
    if any(v>0 for v in prop_series):
        plot_xy(powers, prop_series, "Potência (dBm)", "CNProcDemandProportion médio",
                f"{name}: Potência × CNProcDemandProportion", out_dir/"potencia_vs_cnprop.png")

    # Trade-off Vazão × Delay (por potência)
    plot_scatter(delay_series, thp_series,
                 "Delay médio (ms)", "Vazão média (Mbps)",
                 f"{name}: Trade-off Vazão × Delay", out_dir/"tradeoff_vazao_delay.png")

    # CNProcDemand × Vazão
    plot_scatter(proc_series, thp_series,
                 "CNProcDemand médio (GOPS)", "Vazão média (Mbps)",
                 f"{name}: CNProcDemand × Vazão", out_dir/"cnproc_vs_vazao.png")

    # ----------- Resumo geral da topologia (média ao longo de TODAS as potências) -----------
    resume_geral = {
        "topologia": name,
        "vazao_media_mbps_todas_potencias": safe_mean(thp_series, default=0.0),
        "delay_medio_ms_todas_potencias":   safe_mean(delay_series, default=0.0),
        "cnproc_medio_gops_todas_potencias":safe_mean(proc_series, default=0.0),
        "potencias_encontradas_dbm": powers
    }
    with open(out_dir/"resumo_geral_topologia.json","w") as f:
        json.dump(resume_geral, f, indent=2, ensure_ascii=False)

    return {"name": name, "powers": powers, "thp": thp_series,
            "delay": delay_series, "proc": proc_series}

def grouped_bars_compare(topologies_data, power_ref, out_png):
    """Barras agrupadas (Toy1..Toy6) para uma potência específica."""
    labels, thp, dly, proc = [], [], [], []
    for t in topologies_data:
        if t is None:
            continue
        labels.append(t["name"])
        if power_ref in t["powers"]:
            idx = t["powers"].index(power_ref)
            thp.append(t["thp"][idx])
            dly.append(t["delay"][idx])
            proc.append(t["proc"][idx])
        else:
            thp.append(0.0); dly.append(0.0); proc.append(0.0)

    import numpy as np
    x = np.arange(len(labels))
    width = 0.27

    plt.figure(figsize=(10,5))
    plt.bar(x - width, thp, width, label="Vazão (Mbps)")
    plt.bar(x,         dly, width, label="Delay (ms)")
    plt.bar(x + width, proc,width, label="CNProc (GOPS)")
    plt.xticks(x, labels)
    plt.ylabel("Valor")
    plt.title(f"Comparação entre Topologias @ {power_ref} dBm")
    plt.legend()
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_png, dpi=180)
    plt.close()

def overall_comparisons(topologies_data, out_root: Path):
    """
    Gera gráficos individuais (um por métrica) comparando Toy1..Toy6,
    onde cada valor é a MÉDIA da métrica ao longo de TODAS as potências
    disponíveis da topologia.
    """
    labels, mean_thp, mean_dly, mean_proc = [], [], [], []

    for t in topologies_data:
        if not t:
            continue
        labels.append(t["name"])
        mean_thp.append(safe_mean(t["thp"], default=0.0))
        mean_dly.append(safe_mean(t["delay"], default=0.0))
        mean_proc.append(safe_mean(t["proc"], default=0.0))

    # 1) Média de vazão × Topologias
    plot_bar(labels, mean_thp,
             "Vazão média (Mbps)",
             "Média de Vazão (somando/agrupando todas as potências) × Topologias",
             out_root/"comparacao_media_vazao_por_topologia.png")

    # 2) Média de delay × Topologias
    plot_bar(labels, mean_dly,
             "Delay médio (ms)",
             "Média de Delay (ignorando UEs NaN; agregando todas as potências) × Topologias",
             out_root/"comparacao_media_delay_por_topologia.png")

    # 3) Média de demanda de processamento × Topologias
    plot_bar(labels, mean_proc,
             "CNProcDemand médio (GOPS)",
             "Média de Demanda de Processamento (todas as potências) × Topologias",
             out_root/"comparacao_media_proc_por_topologia.png")

    # Também salva um JSON resumo com essas comparações
    resumo = []
    for i, lab in enumerate(labels):
        resumo.append({
            "topologia": lab,
            "vazao_media_mbps_todas_potencias": mean_thp[i],
            "delay_medio_ms_todas_potencias":   mean_dly[i],
            "cnproc_medio_gops_todas_potencias":mean_proc[i]
        })
    with open(out_root/"comparacao_media_por_topologia.json","w") as f:
        json.dump(resumo, f, indent=2, ensure_ascii=False)

def energy_from_resume(resume_json, energy_cfg):
    """
    Calcula Energia total (J) e Energia/bit (J/bit) usando parâmetros de um JSON:
    {
      "sim_time_s": 20,
      "p_idle_w": 0,
      "k_cnproc_w_per_gops": 1.0,
      "k_thp_w_per_mbps": 0.0
    }
    Fórmula simples: P = p_idle + k1*CNProc(GOPS) + k2*Throughput(Mbps)
    E = P * sim_time_s ;  J/bit = E / (Throughput*1e6 * sim_time_s)
    """
    sim_t  = energy_cfg.get("sim_time_s", 20)
    p_idle = energy_cfg.get("p_idle_w", 0.0)
    k1     = energy_cfg.get("k_cnproc_w_per_gops", 1.0)
    k2     = energy_cfg.get("k_thp_w_per_mbps", 0.0)

    with open(resume_json) as f:
        rows = json.load(f)

    # retorna um dict por potência
    en = {}
    for r in rows:
        thp = max(r["vazao_media_mbps"], 1e-12)
        proc = r["cnproc_medio_gops"]
        pwr = p_idle + k1*proc + k2*thp
        e_j = pwr * sim_t
        e_per_bit = e_j / (thp*1e6*sim_t)
        en[r["potencia_dbm"]] = {"P_W": pwr, "E_J": e_j, "J_per_bit": e_per_bit}
    return en

def plot_energy_comparison(base_out_dir: Path, toys, power_ref, energy_cfg, out_png):
    """Energia × Topologia (na potência escolhida), a partir de resumo_por_potencia.json."""
    vals_e, vals_jbit, labels = [], [], []
    for toy in toys:
        rjson = base_out_dir/toy/"resumo_por_potencia.json"
        if not rjson.exists():
            continue
        en = energy_from_resume(rjson, energy_cfg)
        if power_ref in en:
            labels.append(toy)
            vals_e.append(en[power_ref]["E_J"])
            vals_jbit.append(en[power_ref]["J_per_bit"])

    import numpy as np
    x = np.arange(len(labels))
    width = 0.35

    # gráfico 1: Energia total (J)
    plt.figure(figsize=(9,4.6))
    plt.bar(x, vals_e, width)
    plt.xticks(x, labels)
    plt.ylabel("Energia total (J)")
    plt.title(f"Energia × Topologia @ {power_ref} dBm")
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_png.with_name("energia_total_por_topologia.png"), dpi=180)
    plt.close()

    # gráfico 2: Energia por bit (J/bit)
    plt.figure(figsize=(9,4.6))
    plt.bar(x, vals_jbit, width)
    plt.xticks(x, labels)
    plt.ylabel("Energia por bit (J/bit)")
    plt.title(f"Energia/bit × Topologia @ {power_ref} dBm")
    plt.grid(axis="y", linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(out_png.with_name("energia_por_bit_por_topologia.png"), dpi=180)
    plt.close()

def main():
    ap = argparse.ArgumentParser(description="Extrai métricas dos .sca e gera gráficos.")
    ap.add_argument("--base", default=DEFAULT_BASE, help="Diretório base com Toy1..Toy6")
    ap.add_argument("--toys", nargs="*", default=DEFAULT_TOYS, help="Quais topologias processar")
    ap.add_argument("--out",  default=DEFAULT_OUT, help="Diretório base de saída")
    ap.add_argument("--files", nargs="*", help="(Opcional) Lista explícita de .sca (ignora --toys)")
    ap.add_argument("--compare-power", type=int, default=26, help="Potência (dBm) para comparação entre topologias")
    ap.add_argument("--energy-cfg", help="JSON com parâmetros de energia (sim_time_s, p_idle_w, k_cnproc_w_per_gops, k_thp_w_per_mbps)")
    args = ap.parse_args()

    out_root = Path(args.out)
    ensure_dir(out_root)

    topologies_data = []

    if args.files:
        # agrupa por pasta mãe (ToyX)
        groups = defaultdict(list)
        for f in args.files:
            p = Path(f).resolve()
            if p.is_file(): groups[p.parent.name].append(p)
        for toy, files in groups.items():
            tmp = Path(f".tmp_sca_{toy}"); ensure_dir(tmp)
            for sca in files:
                link = tmp/sca.name
                if not link.exists():
                    try: link.symlink_to(sca)
                    except FileExistsError: pass
            out_dir = ensure_dir(out_root/toy)
            topologies_data.append(process_topology(tmp, out_dir))
            # cleanup
            for l in tmp.glob("*"): l.unlink(missing_ok=True)
            tmp.rmdir()
    else:
        base = Path(args.base)
        for toy in args.toys:
            topologies_data.append(
                process_topology(base/toy, ensure_dir(out_root/toy))
            )

    # barras agrupadas (Toy1..Toy6) na potência escolhida
    grouped_bars_compare(
        [t for t in topologies_data if t], args.compare_power,
        out_root/f"comparacao_topologias_{args.compare_power}dBm.png"
    )

    # NOVO: comparações individuais (média em TODAS as potências) × Topologias
    overall_comparisons([t for t in topologies_data if t], out_root)

    # Energia × Topologia (se energy-cfg fornecido)
    if args.energy_cfg:
        with open(args.energy_cfg) as f:
            cfg = json.load(f)
        plot_energy_comparison(out_root, args.toys, args.compare_power, cfg,
                               out_root/"energia_total_por_topologia.png")

if __name__ == "__main__":
    main()
