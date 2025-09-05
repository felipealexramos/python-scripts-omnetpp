#!/usr/bin/env python3
import os
import subprocess
import json
import time
import argparse
from datetime import datetime
from tqdm import tqdm
from multiprocessing import Pool, cpu_count
import re

# ---------------------------
# CLI
# ---------------------------
parser = argparse.ArgumentParser(description="Executa simulações OMNeT++ (Simu5G).")
parser.add_argument("--tx", type=str, required=True,
                    help='Potências de transmissão em dBm. Exemplos: "26" | "20,23,26" | "20 23 26"')
parser.add_argument("--reps", type=int, default=1, help="Número de repetições (default: 1)")
parser.add_argument("--threads", type=int, default=4, help="Processos paralelos (default: 4)")
parser.add_argument("--skip-sim", action="store_true", help="Pula a simulação")
parser.add_argument("--simu5g-root", type=str, 
                    help="Caminho para a pasta raiz do Simu5G (opcional)")
parser.add_argument("--app-dir", type=str, default="application02",
                    help="Diretório da aplicação dentro de simulations/NR/ (default: application02)")
parser.add_argument("--ini-file", type=str, default="training_toy1_1.ini",
                    help="Nome do arquivo .ini (default: training_toy1_1.ini)")
parser.add_argument("--config-name", type=str, default="TrainingToy1_1",
                    help="Nome da configuração no arquivo .ini (default: TrainingToy1_1)")
parser.add_argument("--result-dir", type=str,
                    help="Diretório personalizado para resultados .sca (opcional)")
parser.add_argument("--out", type=str, default="/home/felipe/Documentos/tcc/omnet/Run_Simulations_Simu5G/Resultados",
                    help="Pasta de saída para logs e arquivos de status (default: caminho fixo predefinido)")
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

OMNETPP_BIN_DIR = "/home/felipe/omnetpp-6.1.0-linux-x86_64/omnetpp-6.1/bin" # Ajuste conforme necessário
# Usar argumento da linha de comando se fornecido, senão usar o valor padrão
SIMU5G_PROJECT_ROOT = args.simu5g_root if args.simu5g_root else "/home/felipe/Documentos/tcc/omnet/simu5g"

# .ini e config
CONFIG_NAME = args.config_name
APP_DIR = args.app_dir
INI_FILE = args.ini_file
INI_PATH = os.path.join(SIMU5G_PROJECT_ROOT, "simulations", "NR", APP_DIR, INI_FILE)

# Base de resultados (usar diretório personalizado se fornecido)
if args.result_dir:
    RESULT_BASE = args.result_dir
else:
    RESULT_BASE = os.path.join(SIMU5G_PROJECT_ROOT, "results", "NR", APP_DIR, CONFIG_NAME)

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
# Execução
# ---------------------------
if not args.skip_sim:
    print(f"🚀 Iniciando simulações OMNeT++ | potências={TX_POWERS} dBm | repetições={NUM_REPETITIONS} | paralelismo={NUM_PROCESSES}")
    print(f"📂 Simu5G: {SIMU5G_PROJECT_ROOT}")
    print(f"📂 Resultados: {RESULT_BASE}")
    
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