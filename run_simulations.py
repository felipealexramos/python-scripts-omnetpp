import os
import subprocess
import json
import time
import argparse
from datetime import datetime
from tqdm import tqdm
from multiprocessing import Pool, cpu_count

# Argumentos via CLI
parser = argparse.ArgumentParser(description="Executa simulações OMNeT++ com múltiplas repetições e potência.")
parser.add_argument("--tx", type=str, required=True, help="Potência de transmissão (ex: 26)")
parser.add_argument("--reps", type=int, default=1, help="Número de repetições")
parser.add_argument("--threads", type=int, default=4, help="Número de processos paralelos")
args = parser.parse_args()

# Configurações principais
TX_POWER = args.tx
NUM_REPETITIONS = args.reps
NUM_PROCESSES = min(args.threads, cpu_count())
MAX_RETRIES = 3

OMNETPP_BIN_DIR = "/home/felipe/omnetpp-6.1.0-linux-x86_64/omnetpp-6.1/bin"
SIMU5G_PROJECT_ROOT = "/home/felipe/Documentos/tcc/omnet/simu5g"
CONFIG_NAME = "Toy1"
INI_PATH = os.path.join(SIMU5G_PROJECT_ROOT, "simulations", "NR", "application01", "training_toy1_1.ini")

# Novo: subpasta por potência (Pot6, Pot16, etc)
RESULT_DIR = os.path.join(SIMU5G_PROJECT_ROOT, "results", CONFIG_NAME, f"Pot{TX_POWER}")
LOG_DIR = os.path.join(RESULT_DIR, "logs")
STATUS_PATH = os.path.join(RESULT_DIR, "status.json")
FAILED_PATH = os.path.join(RESULT_DIR, "failed_runs.json")

os.makedirs(LOG_DIR, exist_ok=True)

# Função que constrói o comando
def build_command(tx, rep):
    return [
        os.path.join(OMNETPP_BIN_DIR, "opp_run"),
        "-r", str(rep),
        "-m", "-u", "Cmdenv",
        "-c", CONFIG_NAME,
        "-f", INI_PATH,
        "-n", f"{SIMU5G_PROJECT_ROOT}/src:{SIMU5G_PROJECT_ROOT}/simulations:" +
              f"{SIMU5G_PROJECT_ROOT}/../inet4.5/src:{SIMU5G_PROJECT_ROOT}/../inet4.5/examples:" +
              f"{SIMU5G_PROJECT_ROOT}/../inet4.5/showcases",
        "-l", "./out/gcc-release/src/libsimu5g.so",
        "-l", "../inet4.5/out/gcc-release/src/libINET.so",
        f"---MultiCell_SA_5cells_12BSs.gnb[*].cellularNic.phy.eNodeBTxPower={tx}dBm"  # <--- CORRECTED PATH
    ]


# Função de simulação com tentativas e logging
def run_simulation(rep):
    attempt = 0
    success = False
    log_file = os.path.join(LOG_DIR, f"log_TX{TX_POWER}_R{rep}.txt")
    sca_file = os.path.join(RESULT_DIR, f"{rep}.sca")
    start_time = time.time()

    while attempt < MAX_RETRIES and not success:
        with open(log_file, "w") as log:
            print(f"▶️ TX={TX_POWER}dBm | Repetição={rep} | Tentativa={attempt + 1}")
            process = subprocess.run(build_command(TX_POWER, rep), cwd=SIMU5G_PROJECT_ROOT,
                                     stdout=log, stderr=subprocess.STDOUT, text=True)
            time.sleep(1)

        success = os.path.exists(sca_file)
        duration = time.time() - start_time

        result = {
            "tx_power": TX_POWER,
            "repetition": rep,
            "attempt": attempt + 1,
            "success": success,
            "sca_generated": success,
            "log_path": log_file,
            "sca_path": sca_file,
            "duration_sec": round(duration, 2),
            "timestamp": datetime.now().isoformat()
        }

        if not success:
            try:
                with open(log_file, "r") as f:
                    result["log_tail"] = f.readlines()[-10:]
            except:
                result["log_tail"] = ["[Erro ao ler log]"]

        attempt += 1

    return result

# Execução paralela
print(f"🚀 Iniciando simulações OMNeT++ em paralelo para TX={TX_POWER}dBm com {NUM_REPETITIONS} repetições")

with Pool(processes=NUM_PROCESSES) as pool:
    with tqdm(total=NUM_REPETITIONS, desc="Simulações", unit="exec") as pbar:
        results = []
        for res in pool.imap_unordered(run_simulation, range(NUM_REPETITIONS)):
            results.append(res)
            pbar.update(1)

# Salvar resultados
with open(STATUS_PATH, "w") as f:
    json.dump({
        "tx_power": TX_POWER,
        "repetitions": NUM_REPETITIONS,
        "runs": results
    }, f, indent=2)

failed = [r for r in results if not r["success"]]
if failed:
    with open(FAILED_PATH, "w") as f:
        json.dump(failed, f, indent=2)

print("\n✅ Simulações finalizadas.")
print(f"📄 Resumo: {STATUS_PATH}")
print(f"⚠️ Falhas: {FAILED_PATH if failed else 'Nenhuma falha registrada.'}")
