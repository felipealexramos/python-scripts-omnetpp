#!/usr/bin/env python3
import os
import subprocess
import json
import time
import argparse
from datetime import datetime
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

# ---------------------------
# CLI
# ---------------------------
parser = argparse.ArgumentParser(description="Executa simulações OMNeT++ (Simu5G) com múltiplas repetições e potência.")
parser.add_argument("--tx", type=str, required=True, help="Potência de transmissão em dBm (ex: 26)")
parser.add_argument("--reps", type=int, default=1, help="Número de repetições (default: 1)")
parser.add_argument("--threads", type=int, default=4, help="Processos paralelos (default: 4)")
args = parser.parse_args()

# ---------------------------
# Config principais
# ---------------------------
TX_POWER = args.tx
NUM_REPETITIONS = args.reps
NUM_PROCESSES = min(args.threads, cpu_count())
MAX_RETRIES = 3

OMNETPP_BIN_DIR = "/home/felipe/omnetpp-6.1.0-linux-x86_64/omnetpp-6.1/bin"
SIMU5G_PROJECT_ROOT = "/home/felipe/Documentos/tcc/omnet/simu5g"

# .ini e config
CONFIG_NAME = "TrainingToy1_1"
INI_PATH = os.path.join(SIMU5G_PROJECT_ROOT, "simulations", "NR", "application02", "training_toy1_1.ini")

# Resultados organizados por app/config/potência
RESULT_DIR = os.path.join(SIMU5G_PROJECT_ROOT, "results", "NR", "application02", CONFIG_NAME, f"Pot{TX_POWER}")
LOG_DIR = os.path.join(RESULT_DIR, "logs")
STATUS_PATH = os.path.join(RESULT_DIR, "status.json")
FAILED_PATH = os.path.join(RESULT_DIR, "failed_runs.json")

os.makedirs(LOG_DIR, exist_ok=True)

# ---------------------------
# Montagem do comando opp_run
# ---------------------------
def build_command(tx, rep):
    """
    Gera o comando completo para o opp_run.
    - Aplica potência nas gNBs (*.gnb[*].cellularNic.phy.eNodeBTxPower)
    - Aplica potência nos UEs (**.ueTxPower)
    - Redireciona resultados para RESULT_DIR (--result-dir)
    """
    return [
        os.path.join(OMNETPP_BIN_DIR, "opp_run"),
        "-r", str(rep),
        "-m", "-u", "Cmdenv",
        "-c", CONFIG_NAME,
        "-f", INI_PATH,
        "--result-dir", RESULT_DIR,
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
def run_simulation(rep):
    attempt = 0
    success = False
    log_file = os.path.join(LOG_DIR, f"log_TX{TX_POWER}_R{rep}.txt")
    # Conforme seu .ini, o nome do scalar fica: ${resultdir}/${configname}/${repetition}.sca
    sca_file = os.path.join(RESULT_DIR, CONFIG_NAME, f"{rep}.sca")
    start_time = time.time()

    while attempt < MAX_RETRIES and not success:
        with open(log_file, "w") as log:
            print(f"▶️ TX={TX_POWER}dBm | Repetição={rep} | Tentativa={attempt + 1}")
            process = subprocess.run(
                build_command(TX_POWER, rep),
                cwd=SIMU5G_PROJECT_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True
            )
        time.sleep(1)

        success = os.path.exists(sca_file)
        duration = time.time() - start_time

        result = {
            "tx_power_dBm": TX_POWER,
            "repetition": rep,
            "attempt": attempt + 1,
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

        attempt += 1

    return result

# ---------------------------
# Execução paralela
# ---------------------------
print(f"🚀 Iniciando simulações OMNeT++ para TX={TX_POWER} dBm | repetições={NUM_REPETITIONS} | paralelismo={NUM_PROCESSES}")
results = []

with Pool(processes=NUM_PROCESSES) as pool:
    with tqdm(total=NUM_REPETITIONS, desc="Simulações", unit="exec") as pbar:
        for res in pool.imap_unordered(run_simulation, range(NUM_REPETITIONS)):
            results.append(res)
            pbar.update(1)

# ---------------------------
# Persistência do status
# ---------------------------
os.makedirs(RESULT_DIR, exist_ok=True)

with open(STATUS_PATH, "w") as f:
    json.dump({
        "tx_power_dBm": TX_POWER,
        "repetitions": NUM_REPETITIONS,
        "result_dir": RESULT_DIR,
        "runs": results
    }, f, indent=2, ensure_ascii=False)

failed = [r for r in results if not r["success"]]
if failed:
    with open(FAILED_PATH, "w") as f:
        json.dump(failed, f, indent=2, ensure_ascii=False)

print("\n✅ Simulações finalizadas.")
print(f"📄 Resumo: {STATUS_PATH}")
print(f"⚠️ Falhas: {FAILED_PATH if failed else 'Nenhuma falha registrada.'}")
