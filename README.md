# Projeto OMNeT++ / Simu5G + Simulações Sintéticas

Guia rápido para executar:
- Simulações reais no OMNeT++/Simu5G, com análise automática dos .sca.
- Simulações sintéticas (toy1..toy6) em Python, com geração de CSVs e gráficos.
- Comparação entre cenários a partir dos resultados gerados.

Sumário:
- [Estrutura do repositório](#estrutura-do-repositório)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e ambiente Python](#instalação-e-ambiente-python)
- [Execução (OMNeT++/Simu5G)](#execução-omnet++simu5g)
- [Simulações sintéticas (pasta Simulacoes)](#simulações-sintéticas-pasta-simulacoes)
- [Comparação entre cenários (toy1..toy6)](#comparação-entre-cenários-toy1toy6)
- [Solução de problemas](#solução-de-problemas)

---

## Estrutura do repositório

- Run_Simulations_Simu5G/
  - run_simulations.py  → executa cenários no OMNeT++/Simu5G e analisa .sca
- Simulacoes/
  - simulate_toy1.py    → simulação sintética (Solução 1: D-RAN) e gráficos
  - simulate_compare.py → consolida e compara resultados (toy1..toy6)
- Topologias/Resultados/
  - Topologia1/...      → saída padrão do toy1 (com timestamp)
  - Comparacoes/...     → saída da comparação entre cenários
- simu5g/               → projeto Simu5G (esperado já compilado)
- inet4.5/              → dependência do Simu5G (esperada)
- README.md             → este guia

---

## Pré-requisitos

- Linux com Python 3.10+.
- OMNeT++ instalado (ex.: 6.1.x) e acessível em:
  - OMNETPP_BIN_DIR: `/home/felipe/omnetpp-6.1.0-linux-x86_64/omnetpp-6.1/bin`
- Projeto Simu5G compilado e acessível em:
  - SIMU5G_PROJECT_ROOT: `/home/felipe/Documentos/tcc/omnet/simu5g`
- Bibliotecas Python:
  - pandas, numpy, matplotlib, tqdm, xlsxwriter

Se seus caminhos diferirem, ajuste as constantes no run_simulations.py:
- OMNETPP_BIN_DIR, SIMU5G_PROJECT_ROOT, INI_PATH

---

## Instalação e ambiente Pytho🚀 Iniciando simulações OMNeT++ para TX=26 dBm | repetições=5 | paralelismo=4
Simulações:   0%|                                                                                              | 0/5 [00:00<?, ?exec/s]▶️ TX=26dBm | Repetição=1 | Tentativa=1
▶️ TX=26dBm | Repetição=2 | Tentativa=1
▶️ TX=26dBm | Repetição=0 | Tentativa=1
▶️ TX=26dBm | Repetição=3 | Tentativa=1
Simulações:  20%|█████████████████                                                                    | 1/5 [03:16<13:07, 196.78s/exec]▶️ TX=26dBm | Repetição=4 | Tentativa=1
Simulações: 100%|██████████████████████████████████████████████████████████████████████████████████████| 5/5 [05:50<00:00, 70.10s/exec]

✅ Simulações finalizadas.
📄 Resumo: /home/felipe/Documentos/tcc/omnet/simu5g/results/NR/application02/TrainingToy1_1/Pot26/status.json
⚠️ Falhas: Nenhuma falha registrada.
📈 Iniciando análise dos resultados (.sca)...
Traceback (most recent call last):
  File "/home/felipe/Documentos/tcc/omnet/Run_Simulations_Simu5G/run_simulations.py", line 347, in <module>
    analyze_results()
  File "/home/felipe/Documentos/tcc/omnet/Run_Simulations_Simu5G/run_simulations.py", line 265, in analyze_results
    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/felipe/Documentos/tcc/omnet/.venv/lib/python3.12/site-packages/pandas/io/excel/_xlsxwriter.py", line 197, in __init__
    from xlsxwriter import Workbook
ModuleNotFoundError: No module named 'xlsxwriter'n

Recomendado usar venv no diretório do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pandas numpy matplotlib tqdm xlsxwriter
```

Dica: para trabalhar com notebooks no VS Code, instale a extensão “Jupyter” e (opcional) o pacote:
```bash
python -m pip install notebook ipykernel
```

Para desativar a venv:
```bash
deactivate
```

---

## Execução (OMNeT++/Simu5G)

Script principal:
- Caminho: `Run_Simulations_Simu5G/run_simulations.py`
- Função: roda o OMNeT++ com Simu5G, muda a potência TX, gerencia repetições e analisa automaticamente os .sca gerados.

Parâmetros:
- --tx        (obrigatório) Potência de transmissão em dBm. Ex.: 26
- --reps      Número de repetições (default: 1)
- --threads   Processos em paralelo (default: 4)
- --skip-sim  Pula a simulação e roda apenas a análise dos .sca existentes
- --out       Pasta de saída para CSVs/gráficos da análise (default já definido no script)

Exemplos:
```bash
# 1) Rodar simulações reais no Simu5G e analisar resultados
python3 Run_Simulations_Simu5G/run_simulations.py --tx 26 --reps 5 --threads 4

# 2) Apenas analisar (sem simular), utilizando .sca já existentes
python3 Run_Simulations_Simu5G/run_simulations.py --tx 26 --skip-sim
```

O que o script faz:
- Monta o comando do `opp_run` aplicando:
  - `--*.gnb[*].cellularNic.phy.eNodeBTxPower=<TX>dBm`
  - `--**.ueTxPower=<TX>dBm`
- Usa a configuração `TrainingToy1_1` do arquivo:
  - `simu5g/simulations/NR/application02/training_toy1_1.ini`
- Organiza saídas por potência:
  - `simu5g/results/NR/application02/TrainingToy1_1/Pot<TX>/...`
- Cria logs por repetição em:
  - `.../Pot<TX>/logs/log_TX<TX>_R<rep>.txt`
- Tenta até 3 vezes por repetição se não aparecer o `.sca` esperado.
- Ao final, executa a análise dos `.sca` encontrados e salva em `--out`:
  - `scalars_raw.csv` (todos os scalars encontrados)
  - `sumarios_metricas.xlsx` (abas com resumos)
  - Gráficos: potencia_vs_throughput_total.png, ..._medio.png, ...sinr..., ...rsrp..., ...rsrq...
  - `README.txt` com o índice das saídas
  - `status.json` e, se houver falhas, `failed_runs.json` no diretório de resultados

Atenção aos caminhos:
- Se o `opp_run` não for encontrado, ajuste `OMNETPP_BIN_DIR`.
- Se a `libsimu5g.so` ou `libINET.so` não for carregada, verifique os caminhos `-l` no script e se o projeto foi compilado (Modo release).

---

## Simulações sintéticas (pasta Simulacoes)

Esses scripts não usam o OMNeT++; geram dados sintéticos, CSVs e gráficos diretamente.

### toy1 — D-RAN puro: `Simulacoes/simulate_toy1.py`

Descrição:
- Simula cenário “Solução 1” (todas as gNBs como D-RAN, CUs desligadas, sem CoMP).
- Gera tabelas por potência de transmissão e gráficos de energia/eficiência.

Execução:
```bash
# Exemplo com saída padrão (Topologia1) e potências definidas
python3 Simulacoes/simulate_toy1.py --tx 20,23,26,29,32

# Exemplo definindo a pasta base de saída
python3 Simulacoes/simulate_toy1.py \
  --outdir /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1 \
  --tx 20,23,26,29,32
```

Saídas (com timestamp):
- `resultados_toy1_detalhado.csv`
- `resultados_toy1_resumo_por_potencia.csv`
- `energia_vs_potencia_toy1.png`
- `eficiencia_vs_potencia_toy1.png`
- `stack_energy_breakdown_toy1.png`
- `metadata_toy1.json`

Padrão de diretório:
- `/home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1/toy1_<timestamp>/...`

---

## Comparação entre cenários (toy1..toy6)

Script: `Simulacoes/simulate_compare.py`

Descrição:
- Procura automaticamente pelos CSVs de resumo de cada toyN:
  - `Topologias/Resultados/Topologia*/toyN_*/resultados_toyN_resumo_por_potencia.csv`
- Consolida, gera comparações e gráficos agregados.
- Se toy1 estiver presente, calcula economia (%) de energia em relação ao D-RAN puro.

Execução sugerida:
```bash
python3 Simulacoes/simulate_compare.py \
  --root /home/felipe/Documentos/tcc/omnet/Topologias/Resultados \
  --outdir /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Comparacoes
```

Saídas:
- `comparacao_agregado.csv`
- `energia_vs_potencia_comparacao.png`
- `throughput_vs_potencia_comparacao.png`
- `eficiencia_vs_potencia_comparacao.png`
- `pareto_energia_throughput.png`
- `economia_percentual_vs_toy1.csv` (se toy1 encontrado)
- `economia_percentual_vs_toy1.png` (se aplicável)

Observações:
- Se algum toyN não for encontrado, ele será ignorado com aviso.
- O script usa o resultado mais recente de cada toy (pelo mtime).

---

## Solução de problemas

- `ModuleNotFoundError: No module named 'pandas'`
  - Ative a venv e instale dependências:
    ```bash
    source .venv/bin/activate
    python -m pip install pandas numpy matplotlib tqdm xlsxwriter
    ```

- `zsh: command not found: jupyter`
  - Instale se quiser usar notebooks (opcional):
    ```bash
    python -m pip install notebook ipykernel
    ```

- `opp_run: command not found` ou libs .so não carregam
  - Ajuste `OMNETPP_BIN_DIR` no `run_simulations.py`.
  - Verifique se o Simu5G e o INET foram compilados (gerando `libsimu5g.so` e `libINET.so` caminhos usados no `-l`).

- `.sca` não gerado
  - Verifique se `INI_PATH` aponta para um `.ini` existente e se o `CONFIG_NAME` existe nesse `.ini`.
  - Confira permissões de escrita em `results/.../Pot<TX>/`.

---

## Comandos rápidos (resumo)

```bash
# 0) Ambiente
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install pandas numpy matplotlib tqdm xlsxwriter

# 1) Simulação sintética (toy1)
python3 Simulacoes/simulate_toy1.py --tx 20,23,26,29,32

# 2) Comparar cenários (usando resultados existentes)
python3 Simulacoes/simulate_compare.py --root Topologias/Resultados --outdir Topologias/Resultados/Comparacoes

# 3) Simulação real (Simu5G) + análise
python3 Run_Simulations_Simu5G/run_simulations.py --tx 26 --reps 5 --threads 4
```

---