#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
simulate_compare.py
-------------------
Compara as topologias toy1..toy6 a partir dos CSVs de saída de cada simulação.

Procura automaticamente por:
  /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia*/toyN_*/resultados_toyN_resumo_por_potencia.csv

Saídas (sempre):
  - comparacao_agregado.csv
  - energia_vs_potencia_comparacao.png
  - throughput_vs_potencia_comparacao.png
  - eficiencia_vs_potencia_comparacao.png
  - pareto_energia_throughput.png
  - economia_percentual_vs_toy1.png   (se toy1 estiver presente)

Uso sugerido:
  python3 simulate_compare.py \
    --root /home/felipe/Documentos/tcc/omnet/Topologias/Resultados \
    --outdir /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Comparacoes
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


@dataclass
class FoundResult:
    toy: str
    csv_path: Path
    run_dir: Path


# -------------------------------------------------------------
# Descoberta de resultados
# -------------------------------------------------------------
def find_latest_for_toy(root: Path, toy: str) -> Optional[FoundResult]:
    # 1) tente pelo padrão Topologia*/toyX_*
    candidates: List[Path] = []
    for topo_dir in root.glob("Topologia*"):
        for run_dir in topo_dir.glob(f"{toy}_*"):
            csv = run_dir / f"resultados_{toy}_resumo_por_potencia.csv"
            if csv.exists():
                candidates.append(run_dir)

    # 2) fallback: varredura recursiva por CSV com o nome esperado
    if not candidates:
        for csv in root.rglob(f"resultados_{toy}_resumo_por_potencia.csv"):
            candidates.append(csv.parent)

    if not candidates:
        return None

    # escolhe pelo mtime
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return FoundResult(toy=toy, csv_path=latest / f"resultados_{toy}_resumo_por_potencia.csv", run_dir=latest)


# -------------------------------------------------------------
# Plot helpers
# -------------------------------------------------------------
def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def plot_lines(df: pd.DataFrame, x: str, y: str, hue: str, title: str, outfile: Path,
               xlabel: str, ylabel: str):
    plt.figure(figsize=(8, 5.2))
    for toy, g in df.groupby(hue):
        g = g.sort_values(x)
        plt.plot(g[x], g[y], marker="o", label=toy)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outfile, dpi=300)


def plot_scatter(df: pd.DataFrame, x: str, y: str, hue: str, title: str, outfile: Path,
                 xlabel: str, ylabel: str):
    plt.figure(figsize=(7.5, 5.2))
    for toy, g in df.groupby(hue):
        plt.scatter(g[x], g[y], label=toy, s=35)
        # opcional: rótulo do maior TX
        g2 = g.sort_values("TX_dBm")
        if not g2.empty:
            plt.annotate(toy, (g2[x].iloc[-1], g2[y].iloc[-1]),
                         textcoords="offset points", xytext=(6, 6))
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle=":")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outfile, dpi=300)


# -------------------------------------------------------------
# Consolidação e comparação
# -------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Comparação de resultados toy1..toy6.")
    parser.add_argument("--root", type=str,
                        default="/home/felipe/Documentos/tcc/omnet/Topologias/Resultados",
                        help="Pasta raiz onde ficam Topologia*/")
    parser.add_argument("--outdir", type=str, default=None,
                        help="Pasta de saída para Comparacoes/")
    parser.add_argument("--toys", type=str, default="toy1,toy2,toy3,toy4,toy5,toy6",
                        help="Lista de cenários separados por vírgula")
    args = parser.parse_args()

    root = Path(args.root)
    outbase = Path(args.outdir) if args.outdir else (root / "Comparacoes")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = outbase / f"compare_{timestamp}"
    ensure_dir(outdir)

    toys = [t.strip() for t in args.toys.split(",") if t.strip()]

    found: Dict[str, FoundResult] = {}
    missing: List[str] = []
    for toy in toys:
        fr = find_latest_for_toy(root, toy)
        if fr is None:
            missing.append(toy)
        else:
            found[toy] = fr

    if missing:
        print("[AVISO] Não encontrei resultados para:", ", ".join(missing))
        print("         Esses cenários serão ignorados na comparação.")

    if not found:
        raise SystemExit("Nenhum resultado encontrado. Rode as simulações primeiro.")

    # Carrega e empilha
    rows = []
    for toy, fr in found.items():
        df = pd.read_csv(fr.csv_path)
        # garantir nomes
        if "TX_dBm" not in df.columns:
            # alguns pandas salvam o índice como "Unnamed: 0"
            # tentativa de detectar a 1a coluna se o nome veio como índice
            df.rename(columns={df.columns[0]: "TX_dBm"}, inplace=True)
        df["toy"] = toy
        rows.append(df[["TX_dBm", "Energia_W", "Throughput_Mbps", "toy"]])

    all_df = pd.concat(rows, ignore_index=True)
    all_df["Eficiência_Mbps_por_W"] = np.where(
        all_df["Energia_W"] > 0, all_df["Throughput_Mbps"] / all_df["Energia_W"], 0.0
    )

    # Salva CSV agregado
    all_df.to_csv(outdir / "comparacao_agregado.csv", index=False)

    # --------- Gráficos principais ----------
    plot_lines(
        df=all_df, x="TX_dBm", y="Energia_W", hue="toy",
        title="Energia total × Potência — comparação toy1..toy6",
        outfile=outdir / "energia_vs_potencia_comparacao.png",
        xlabel="Potência (dBm)", ylabel="Energia total (W)"
    )

    plot_lines(
        df=all_df, x="TX_dBm", y="Throughput_Mbps", hue="toy",
        title="Throughput total × Potência — comparação toy1..toy6",
        outfile=outdir / "throughput_vs_potencia_comparacao.png",
        xlabel="Potência (dBm)", ylabel="Throughput total (Mbps)"
    )

    plot_lines(
        df=all_df, x="TX_dBm", y="Eficiência_Mbps_por_W", hue="toy",
        title="Eficiência (Mbps/J) × Potência — comparação toy1..toy6",
        outfile=outdir / "eficiencia_vs_potencia_comparacao.png",
        xlabel="Potência (dBm)", ylabel="Eficiência (Mbps/J)"
    )

    plot_scatter(
        df=all_df, x="Energia_W", y="Throughput_Mbps", hue="toy",
        title="Pareto — Throughput × Energia (todas as potências)",
        outfile=outdir / "pareto_energia_throughput.png",
        xlabel="Energia total (W)", ylabel="Throughput total (Mbps)"
    )

    # --------- Economia % vs toy1 (se existir) ----------
    if "toy1" in found:
        econ_rows = []
        base_df = all_df[all_df["toy"] == "toy1"][["TX_dBm", "Energia_W"]].rename(
            columns={"Energia_W": "Energia_base"})
        for toy in all_df["toy"].unique():
            if toy == "toy1":
                continue
            merged = pd.merge(
                all_df[all_df["toy"] == toy][["TX_dBm", "Energia_W"]], base_df, on="TX_dBm", how="inner"
            )
            if merged.empty:
                continue
            merged["toy"] = toy
            merged["Economia_%"] = np.where(
                merged["Energia_base"] > 0,
                (merged["Energia_base"] - merged["Energia_W"]) / merged["Energia_base"] * 100.0,
                0.0
            )
            econ_rows.append(merged[["TX_dBm", "toy", "Economia_%"]])
        if econ_rows:
            econ = pd.concat(econ_rows, ignore_index=True)
            econ.to_csv(outdir / "economia_percentual_vs_toy1.csv", index=False)

            plt.figure(figsize=(8, 5.2))
            for toy, g in econ.groupby("toy"):
                g = g.sort_values("TX_dBm")
                plt.plot(g["TX_dBm"], g["Economia_%"], marker="o", label=toy)
            plt.axhline(0, color="k", linewidth=0.8)
            plt.xlabel("Potência (dBm)")
            plt.ylabel("Economia de energia (%) vs toy1")
            plt.title("Economia de energia (%) em relação ao D-RAN puro (toy1)")
            plt.grid(True, linestyle=":")
            plt.legend()
            plt.tight_layout()
            plt.savefig(outdir / "economia_percentual_vs_toy1.png", dpi=300)

    print(f"[OK] Comparações salvas em: {outdir}")
    print("Arquivos gerados:")
    for f in [
        "comparacao_agregado.csv",
        "energia_vs_potencia_comparacao.png",
        "throughput_vs_potencia_comparacao.png",
        "eficiencia_vs_potencia_comparacao.png",
        "pareto_energia_throughput.png",
        "economia_percentual_vs_toy1.csv",
        "economia_percentual_vs_toy1.png",
    ]:
        p = outdir / f
        if p.exists():
            print(" -", f)


if __name__ == "__main__":
    main()
