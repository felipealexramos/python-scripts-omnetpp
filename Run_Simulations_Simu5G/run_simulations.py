#!/usr/bin/env python3
import os
import subprocess
import json
import time
import argparse
from datetime import datetime
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

# ===== Análise / parsing =====
import re, math
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

# ---------------------------
# CLI
# ---------------------------
parser = argparse.ArgumentParser(description="Executa simulações OMNeT++ (Simu5G) e analisa os .sca gerados.")
parser.add_argument("--tx", type=str, required=True,
                    help='Potências de transmissão em dBm. Exemplos: "26" | "20,23,26" | "20 23 26"')
parser.add_argument("--reps", type=int, default=1, help="Número de repetições (default: 1)")
parser.add_argument("--threads", type=int, default=4, help="Processos paralelos (default: 4)")
parser.add_argument("--skip-sim", action="store_true", help="Pula a simulação e roda apenas a análise dos .sca já existentes")
parser.add_argument("--out", type=str, default="/home/felipe/Documentos/tcc/omnet/Run_Simulations_Simu5G/Resultados",
                    help="Pasta de saída para gráficos e tabelas (default: caminho fixo pedido)")
args = parser.parse_args()

# ---------------------------
# Config principais
# ---------------------------
def parse_tx_list(raw: str):
    parts = [p for p in re.split(r"[,\s]+", raw.strip()) if p]
    return parts

TX_POWERS = parse_tx_list(args.tx)
NUM_REPETITIONS = args.reps
NUM_PROCESSES = min(args.threads, cpu_count())
MAX_RETRIES = 3

OMNETPP_BIN_DIR = "/home/felipe/omnetpp-6.1.0-linux-x86_64/omnetpp-6.1/bin"
SIMU5G_PROJECT_ROOT = "/home/felipe/Documentos/tcc/omnet/simu5g"

# .ini e config
CONFIG_NAME = "TrainingToy1_1"
INI_PATH = os.path.join(SIMU5G_PROJECT_ROOT, "simulations", "NR", "application02", "training_toy1_1.ini")

# Base de resultados
RESULT_BASE = os.path.join(SIMU5G_PROJECT_ROOT, "results", "NR", "application02", CONFIG_NAME)

def get_paths_for_tx(tx: str):
    result_dir = os.path.join(RESULT_BASE, f"Pot{tx}")
    log_dir = os.path.join(result_dir, "logs")
    status_path = os.path.join(result_dir, "status.json")
    failed_path = os.path.join(result_dir, "failed_runs.json")
    return result_dir, log_dir, status_path, failed_path

OUT_DIR = args.out
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------
# Montagem do comando opp_run
# ---------------------------
def build_command(tx: str, rep: int):
    """
    Gera o comando completo para o opp_run.
    - Aplica potência nas gNBs (*.gnb[*].cellularNic.phy.eNodeBTxPower)
    - Aplica potência nos UEs (**.ueTxPower)
    - Redireciona resultados para RESULT_DIR (--result-dir)
    """
    result_dir, _, _, _ = get_paths_for_tx(tx)
    return [
        os.path.join(OMNETPP_BIN_DIR, "opp_run"),
        "-r", str(rep),
        "-m", "-u", "Cmdenv",
        "-c", CONFIG_NAME,
        "-f", INI_PATH,
        "--result-dir", result_dir,
        "-n", (
            f"{SIMU5G_PROJECT_ROOT}/src:"
            f"{SIMU5G_PROJECT_ROOT}/simulations:"
            f"{SIMU5G_PROJECT_ROOT}/../inet4.5/src:"
            f"{SIMU5G_PROJECT_ROOT}/../inet4.5/examples:"
            f"{SIMU5G_PROJECT_ROOT}/../inet4.5/showcases"
        ),
        "-l", "./out/gcc-release/src/libsimu5g.so",
        "-l", "../inet4.5/out/gcc-release/src/libINET.so",
        f"--*.gnb[*].cellularNic.phy.eNodeBTxPower={tx}dBm",
        f"--**.ueTxPower={tx}dBm",
    ]

# ---------------------------
# Execução de uma simulação (com tentativas)
# ---------------------------
def run_job(job):
    tx, rep = job["tx"], job["rep"]
    result_dir, log_dir, _, _ = get_paths_for_tx(tx)
    os.makedirs(result_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    attempt = 0
    success = False
    log_file = os.path.join(log_dir, f"log_TX{tx}_R{rep}.txt")
    sca_file = os.path.join(result_dir, CONFIG_NAME, f"{rep}.sca")
    start_time = time.time()

    while attempt < MAX_RETRIES and not success:
        with open(log_file, "w") as log:
            print(f"▶️ TX={tx}dBm | Repetição={rep} | Tentativa={attempt + 1}")
            subprocess.run(
                build_command(tx, rep),
                cwd=SIMU5G_PROJECT_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True
            )
        time.sleep(1)
        success = os.path.exists(sca_file)
        duration = time.time() - start_time

        attempt += 1

    result = {
        "tx_power_dBm": tx,
        "repetition": rep,
        "attempts": attempt,
        "success": success,
        "sca_expected": sca_file,
        "log_path": log_file,
        "duration_sec": round(duration, 2),
        "timestamp": datetime.now().isoformat()
    }

    if not success:
        try:
            with open(log_file, "r") as f:
                tail = f.readlines()[-20:]
            result["log_tail"] = tail
        except Exception:
            result["log_tail"] = ["[Erro ao ler o log]"]

    return result

# ---------------------------
# Funções de análise (.sca)
# ---------------------------
def find_sca_files(root: str):
    sca_files = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".sca"):
                sca_files.append(os.path.join(dirpath, f))
    return sorted(sca_files)

# Regex robusto para linhas attr/scalar (suporta aspas e notação científica)
_S_ATTR   = re.compile(r'^attr\s+(\S+)\s+(.+)$')
_S_SCALAR = re.compile(r'^scalar\s+(".*?"|\S+)\s+(".*?"|\S+)\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)')

def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        return s[1:-1]
    return s

def parse_sca_file(path: str):
    scalars = []
    attrs = {}
    with open(path, "r", errors="ignore") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            ma = _S_ATTR.match(line)
            if ma:
                key, val = ma.group(1), _unquote(ma.group(2))
                attrs[key] = val
                continue
            ms = _S_SCALAR.match(line)
            if ms:
                module = _unquote(ms.group(1))
                name   = _unquote(ms.group(2))
                try:
                    value = float(ms.group(3))
                except ValueError:
                    value = math.nan
                scalars.append((module, name, value))
    df = pd.DataFrame(scalars, columns=["module", "name", "value"])
    return df, attrs

def potencia_from_filename(path: str) -> float:
    m = re.search(r"_pot(\d+)", os.path.basename(path))
    if m:
        try:
            return float(m.group(1))
        except:
            pass
    # fallback: usa a pasta PotXX
    m2 = re.search(r"Pot(\d+)", path)
    if m2:
        try:
            return float(m2.group(1))
        except:
            pass
    return float("nan")

def collect_all_scalars(files):
    rows = []
    for f in files:
        df, attrs = parse_sca_file(f)
        pot = potencia_from_filename(f)
        repetition = attrs.get("repetition", None)
        configname = attrs.get("configname", None)
        runid = attrs.get("runid", attrs.get("runID", None))
        for _, r in df.iterrows():
            rows.append({
                "filepath": f,
                "configname": configname,
                "repetition": repetition,
                "run_id": runid,
                "potencia_dbm": pot,
                "module": r["module"],
                "name": r["name"],
                "value": r["value"],
            })
    return pd.DataFrame(rows)

def summarize_metrics(df: pd.DataFrame):
    # padrões tolerantes
    pat_thr  = re.compile(r"throughput", re.I)
    pat_sinr = re.compile(r"(sinr|snir)", re.I)
    pat_rsrp = re.compile(r"rsrp", re.I)
    pat_rsrq = re.compile(r"rsrq", re.I)

    thr  = df[df["name"].str.contains(pat_thr,  na=False)].copy()
    sinr = df[df["name"].str.contains(pat_sinr, na=False)].copy()
    rsrp = df[df["name"].str.contains(pat_rsrp, na=False)].copy()
    rsrq = df[df["name"].str.contains(pat_rsrq, na=False)].copy()

    def agg_by_power(sub: pd.DataFrame, how: str, label: str):
        if sub.empty:
            return pd.DataFrame(columns=["potencia_dbm", label])
        g = sub.groupby("potencia_dbm")["value"].agg(how).reset_index().sort_values("potencia_dbm")
        g.columns = ["potencia_dbm", label]
        return g

    thr_sum   = thr.groupby(["potencia_dbm"]).agg(total_throughput=("value", "sum")).reset_index().sort_values("potencia_dbm")
    thr_mean  = agg_by_power(thr,  "mean", "throughput_medio")
    sinr_mean = agg_by_power(sinr, "mean", "sinr_medio")
    rsrq_mean = agg_by_power(rsrq, "mean", "rsrq_medio")
    rsrp_mean = agg_by_power(rsrp, "mean", "rsrp_medio")

    return {"thr_sum": thr_sum, "thr_mean": thr_mean, "sinr_mean": sinr_mean,
            "rsrq_mean": rsrq_mean, "rsrp_mean": rsrp_mean, "raw": df}

def save_plot(x, y, xlabel, ylabel, title, outpath):
    plt.figure()
    plt.plot(x, y, marker="o")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()

def analyze_results(result_roots):
    # Coleta todos os .sca de todas as potências informadas
    files = []
    for root in result_roots:
        files.extend(find_sca_files(root))
    if not files:
        print(f"[ANÁLISE] Nenhum .sca encontrado em: {result_roots}")
        return

    df_all = collect_all_scalars(files)
    # Exporta CSV bruto e nomes para diagnóstico
    raw_csv = os.path.join(OUT_DIR, "scalars_raw.csv")
    df_all.to_csv(raw_csv, index=False)
    (df_all["name"].value_counts()).to_csv(os.path.join(OUT_DIR, "debug_scalar_names.txt"), header=["count"])

    metrics = summarize_metrics(df_all)

    # Exporta Excel
    xlsx_path = os.path.join(OUT_DIR, "sumarios_metricas.xlsx")
    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
        for k, v in metrics.items():
            if isinstance(v, pd.DataFrame) and not v.empty:
                v.to_excel(writer, sheet_name=k, index=False)

    # Gráficos
    if not metrics["thr_sum"].empty:
        save_plot(metrics["thr_sum"]["potencia_dbm"], metrics["thr_sum"]["total_throughput"],
                  "Potência (dBm)", "Throughput total (unid.)", "Potência x Throughput Total",
                  os.path.join(OUT_DIR, "potencia_vs_throughput_total.png"))

    if not metrics["thr_mean"].empty:
        save_plot(metrics["thr_mean"]["potencia_dbm"], metrics["thr_mean"]["throughput_medio"],
                  "Potência (dBm)", "Throughput médio (unid.)", "Potência x Throughput Médio",
                  os.path.join(OUT_DIR, "potencia_vs_throughput_medio.png"))

    if not metrics["sinr_mean"].empty:
        save_plot(metrics["sinr_mean"]["potencia_dbm"], metrics["sinr_mean"]["sinr_medio"],
                  "Potência (dBm)", "SINR médio (dB)", "Potência x SINR Médio",
                  os.path.join(OUT_DIR, "potencia_vs_sinr_medio.png"))

    if not metrics["rsrp_mean"].empty:
        save_plot(metrics["rsrp_mean"]["potencia_dbm"], metrics["rsrp_mean"]["rsrp_medio"],
                  "Potência (dBm)", "RSRP médio (dBm)", "Potência x RSRP Médio",
                  os.path.join(OUT_DIR, "potencia_vs_rsrp_medio.png"))

    if not metrics["rsrq_mean"].empty:
        save_plot(metrics["rsrq_mean"]["potencia_dbm"], metrics["rsrq_mean"]["rsrq_medio"],
                  "Potência (dBm)", "RSRQ médio (dB)", "Potência x RSRQ Médio",
                  os.path.join(OUT_DIR, "potencia_vs_rsrq_medio.png"))

    # README
    readme_path = os.path.join(OUT_DIR, "README.txt")
    with open(readme_path, "w") as fh:
        fh.write(
            "Saídas geradas:\n"
            f"- CSV bruto dos scalars: {raw_csv}\n"
            f"- Planilha Excel com resumos: {xlsx_path}\n"
            "- Figuras (se métricas existirem):\n"
            "  - potencia_vs_throughput_total.png\n"
            "  - potencia_vs_throughput_medio.png\n"
            "  - potencia_vs_sinr_medio.png\n"
            "  - potencia_vs_rsrp_medio.png\n"
            "  - potencia_vs_rsrq_medio.png\n"
        )
    print(f"[ANÁLISE] Concluída. Arquivos salvos em: {OUT_DIR}")

# ---------------------------
# Execução
# ---------------------------
if not args.skip_sim:
    print(f"🚀 Iniciando simulações OMNeT++ | potências={TX_POWERS} dBm | repetições={NUM_REPETITIONS} | paralelismo={NUM_PROCESSES}")
    for tx in TX_POWERS:
        result_dir, log_dir, status_path, failed_path = get_paths_for_tx(tx)
        os.makedirs(result_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)

        # Jobs desta potência
        jobs = [{"tx": tx, "rep": rep} for rep in range(NUM_REPETITIONS)]
        results = []
        with Pool(processes=NUM_PROCESSES) as pool:
            with tqdm(total=len(jobs), desc=f"Simulações TX={tx}dBm", unit="exec") as pbar:
                for res in pool.imap_unordered(run_job, jobs):
                    results.append(res)
                    pbar.update(1)

        # Persistência do status por potência
        failed = [r for r in results if not r["success"]]
        with open(status_path, "w") as f:
            json.dump({
                "tx_power_dBm": tx,
                "repetitions": NUM_REPETITIONS,
                "result_dir": result_dir,
                "runs": results
            }, f, indent=2, ensure_ascii=False)
        if failed:
            with open(failed_path, "w") as f:
                json.dump(failed, f, indent=2, ensure_ascii=False)

        print(f"✅ TX={tx}dBm finalizado. Resumo: {status_path} | Falhas: {failed_path if failed else 'Nenhuma'}")
else:
    print("⏭  Pulando simulações (modo --skip-sim).")

# Sempre roda a análise ao final (agrega todas as potências solicitadas)
print("📈 Iniciando análise dos resultados (.sca)...")
roots = [get_paths_for_tx(tx)[0] for tx in TX_POWERS]
analyze_results(roots)