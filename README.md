# Sistema Integrado de Gestão de Simulações e Experimentos em Redes Móveis sem fio com Foco em Eficiência Energética.

## analisar_sca.py — Extração de métricas, gráficos e modelo de energia a partir de .sca

Este script percorre pastas com resultados OMNeT++ (.sca), extrai métricas (vazão, delay, custo computacional), agrega por potência (dBm), e gera gráficos por solução e comparativos. Opcionalmente, aplica um modelo simples de potência/energia para estimar consumo e eficiência.

### Requisitos

- Python 3.8+
- Pacotes:
  - matplotlib
  - numpy
- Arquivos .sca com os resultados de cada cenário/potência.

Instalação rápida dos pacotes:
```bash
pip install matplotlib numpy
```

### Estrutura de entrada

- Base de simulações (default):  
  `/home/felipe/Documentos/tcc/omnet/simu5g/simulations/NR/application03`
- Dentro da base, uma subpasta por “solução” (ex.: Simulation1, …).
- Dentro de cada subpasta, arquivos `.sca` contendo no NOME a potência em dBm, por exemplo:
  - `..._10dBm.sca`
  - `result_23dBm.sca`
  - O padrão deve conter “XdBm” (somente inteiros), pois a potência é inferida do nome via regex `(\d+)dBm`.

Exemplo:
```
application03/
  Simulation1/
    runA_10dBm.sca
    runB_20dBm.sca
  Simulation2/
    exp_10dBm.sca
    exp_20dBm.sca
```

### Saída

- Pasta de saída (default):  
  `/home/felipe/Documentos/tcc/omnet/ResultadosSCA/Graficos`

Para cada solução (subpasta passada em `--solutions`), o script cria:
- `resumo_por_arquivo.json` — métricas de cada .sca.
- `resumo_por_potencia.json` — métricas agregadas por potência (e energia/eficiência, se configurado).
- Gráficos por solução:
  - `potencia_vs_vazao.png`
  - `potencia_vs_delay.png`
  - `potencia_vs_custo.png`
  - Se energia habilitada:
    - `potencia_vs_energia_kwh.png`
    - `potencia_vs_eficiencia.png`
    - `potencia_vs_indice_eficiencia_global.png`

Gráficos comparativos (na raiz da saída):
- Barras: `comparacao_vazao.png`, `comparacao_delay.png`, `comparacao_custo.png`, `comparacao_energia.png`
- Linhas: `comparacao_vazao_linhas.png`, `comparacao_delay_linhas.png`, `comparacao_custo_linhas.png`, `comparacao_energia_linhas.png`
- Dispersão (bolhas): `comparacao_scatter_energia_delay_bolhas.png`

### Funcionamento (pipeline)

1. Busca `.sca` em cada subpasta de solução.
2. Extrai:
   - Vazão por UE: soma e normalização automática para Mbps.
   - Delay por UE: média e normalização automática para ms.
   - Custo computacional (CNProcDemand:mean) por gNB: média e soma.
   - Potência (dBm): inferida do nome do arquivo (ex.: “10dBm”).
3. Agrega por potência (média dos runs).
4. Opcional: calcula potência/energia/eficiência usando o JSON de energia.
5. Gera JSONs de resumo e gráficos por solução e comparativos globais.

Notas de unidade:
- Vazão: se os valores aparentam estar em bps, são convertidos para Mbps; caso contrário, mantidos.
- Delay: se aparenta estar em segundos, é convertido para ms; caso contrário, mantido.

### Sobre nomes “SolutionX” vs “SimulationX”

- Você pode usar qualquer nome de subpasta (ex.: Simulation1..Simulation6).
- Passe esses nomes em `--solutions` ou altere o DEFAULT_SOLUTIONS no script.
- O script salva as saídas em `<out>/<nome-da-solucao>` exatamente como informado.
- O rótulo nos gráficos usa o nome normalizado:
  - “SolutionX” (termo preferido) é utilizado nos gráficos; “SimulationX” permanece “SimulationX”.

Renomeando de Solution1..Solution6 para Simulation1..Simulation6:
- Basta rodar com `--solutions Simulation1 Simulation2 ...` ou alterar `DEFAULT_SOLUTIONS` no arquivo.

### Uso rápido

Exemplos (Linux):

- Usando padrões internos (edite DEFAULT_SOLUTIONS/BASE/OUT se quiser):
```bash
python3 analisar_sca.py
```

- Especificando base, saída e soluções “Simulation1..6”:
```bash
python3 analisar_sca.py \
  --base /home/felipe/Documentos/tcc/omnet/simu5g/simulations/NR/application03 \
  --out  /home/felipe/Documentos/tcc/omnet/ResultadosSCA/Graficos \
  --solutions Simulation1 Simulation2 Simulation3 Simulation4 Simulation5 Simulation6
```

- Selecionando métricas e tipos de gráfico:
```bash
python3 analisar_sca.py --solutions Simulation1 Simulation2 \
  --metrics throughput delay proc \
  --charts per-solution comparisons
```

- Com modelo de energia:
```bash
python3 analisar_sca.py --solutions Simulation1 Simulation2 \
  --metrics energy efficiency ieg throughput delay \
  --charts per-solution comparisons scatter \
  --energy-cfg energy_config.json
```

Ajuda:
```bash
python3 analisar_sca.py -h
```

### Parâmetros

- `--base` (str): pasta base com subpastas de soluções. Default no código.
- `--solutions` (lista): nomes das subpastas a processar (ex.: Simulation1 Simulation2 …).
- `--out` (str): pasta raiz de saída dos gráficos/JSONs.
- `--energy-cfg` (arquivo JSON): ativa e parametriza energia/eficiência.
- `--metrics` (lista): quais métricas gerar. Opções:
  - `throughput`, `delay`, `proc`, `energy`, `efficiency`, `ieg`, ou `all` (default).
- `--charts` (lista): tipos de gráfico:
  - `per-solution` (linhas), `comparisons` (barras), `scatter`.

Observação: se solicitar métricas de energia/eficiência sem `--energy-cfg`, o script avisa e ignora essas métricas.

### Configuração de energia (JSON)

Estrutura esperada:
```json
{
  "general": {
    "idle_power_w": 50.0,
    "alpha": 2.0,
    "beta": 0.5,
    "gamma": 1.0,
    "sim_time_s": 20.0,
    "delay_ref_ms": 10.0
  },
  "limits": {
    "min_power_w": 10.0,
    "max_power_w": 5000.0
  }
}
```

- Modelo:
  - P_tot = P_idle + alpha*D_proc + beta*N_UE_ativos + gamma*P_Tx_W
  - E_tot = P_tot * T_sim
  - Eficiência = Throughput_Mbps / P_tot_W (Mbps/W)
  - IEG = (Thp/E) * 1/(1 + Delay/D0)
- P_Tx_W é derivada da potência (dBm) do nome do arquivo `.sca`.

### Dicas e solução de problemas

- “[WARN] Sem .sca em …”: verifique `--base`, o nome em `--solutions` e se há arquivos `.sca`.
- Potência não reconhecida: confirme “XdBm” no NOME do arquivo `.sca` (números inteiros).
- Barras/gráficos vazios: pode não haver potência comum entre soluções; garanta que todas tenham os mesmos “XdBm”.
- Falta de pacotes: instale `matplotlib` e `numpy`.

### Licença

Uso interno acadêmico. Ajuste conforme sua

## Projeto OMNeT++ / Simu5G + Simulações

Guia rápido para executar:
- Simulações reais no OMNeT++/Simu5G, com análise automática dos .sca.
- Simulações sintéticas (solution1..solution6) em Python, com geração de CSVs e gráficos.
- Comparação entre cenários a partir dos resultados gerados.

Sumário:
- [Estrutura do repositório](#estrutura-do-repositório)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e ambiente Python](#instalação-e-ambiente-python)
- [Execução (OMNeT++/Simu5G)](#execução-omnet++simu5g)
- [Simulações sintéticas (pasta Simulacoes)](#simulações-sintéticas-pasta-simulacoes)
- [Comparação entre cenários (solution1..solution6)](#comparação-entre-cenários-solution1solution6)
- [Solução de problemas](#solução-de-problemas)

---

### Estrutura do repositório

- Run_Simulations_Simu5G/
  - run_simulations.py  → executa cenários no OMNeT++/Simu5G e analisa .sca
- Simulacoes/
  - simulate_solution1.py    → simulação sintética (Solução 1: D-RAN) e gráficos
  - simulate_compare.py → consolida e compara resultados (solution1..solution6)
- Topologias/Resultados/
  - Topologia1/...      → saída padrão do solution1 (com timestamp)
  - Comparacoes/...     → saída da comparação entre cenários
- simu5g/               → projeto Simu5G (esperado já compilado)
- inet4.5/              → dependência do Simu5G (esperada)
- README.md             → este guia

---

### Pré-requisitos

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

### Instalação e ambiente Python

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

### Execução (OMNeT++/Simu5G)

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
- Usa a configuração `TrainingSolution1_1` do arquivo:
  - `simu5g/simulations/NR/application02/training_solution1_1.ini`
- Organiza saídas por potência:
  - `simu5g/results/NR/application02/TrainingSolution1_1/Pot<TX>/...`
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
- Se a `libsimu5g.so` ou `libINET.so` não forem carregadas, verifique os caminhos `-l` no script e se o projeto foi compilado (Modo release).

---

### Simulações sintéticas (pasta Simulacoes)

Esses scripts não usam o OMNeT++; geram dados sintéticos, CSVs e gráficos diretamente.

#### solution1 — D-RAN puro: `Simulacoes/simulate_solution1.py`

Descrição:
- Simula cenário “Solução 1” (todas as gNBs como D-RAN, CUs desligadas, sem CoMP).
- Gera tabelas por potência de transmissão e gráficos de energia/eficiência.

Execução:
```bash
# Exemplo com saída padrão (Topologia1) e potências definidas
python3 Simulacoes/simulate_solution1.py --tx 20,23,26,29,32

# Exemplo definindo a pasta base de saída
python3 Simulacoes/simulate_solution1.py \
  --outdir /home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1 \
  --tx 20,23,26,29,32
```

Saídas (com timestamp):
- `resultados_solution1_detalhado.csv`
- `resultados_solution1_resumo_por_potencia.csv`
- `energia_vs_potencia_solution1.png`
- `eficiencia_vs_potencia_solution1.png`
- `stack_energy_breakdown_solution1.png`
- `metadata_solution1.json`

Padrão de diretório:
- `/home/felipe/Documentos/tcc/omnet/Topologias/Resultados/Topologia1/solution1_<timestamp>/...`

---

### Comparação entre cenários (solution1..solution6)

Script: `Simulacoes/simulate_compare.py`

Descrição:
- Procura automaticamente pelos CSVs de resumo de cada solutionN:
  - `Topologias/Resultados/Topologia*/solutionN_*/resultados_solutionN_resumo_por_potencia.csv`
- Consolida, gera comparações e gráficos agregados.
- Se solution1 estiver presente, calcula economia (%) de energia em relação ao D-RAN puro.

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
- `economia_percentual_vs_solution1.csv` (se solution1 encontrado)
- `economia_percentual_vs_solution1.png` (se aplicável)

Observações:
- Se algum solutionN não for encontrado, ele será ignorado com aviso.
- O script usa o resultado mais recente de cada solution (pelo mtime).

---

### Solução de problemas

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

### Comandos rápidos (resumo)

```bash
# 0) Ambiente
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install pandas numpy matplotlib tqdm xlsxwriter

# 1) Simulação sintética (solution1)
python3 Simulacoes/simulate_solution1.py --tx 20,23,26,29,32

# 2) Comparar cenários (usando resultados existentes)
python3 Simulacoes/simulate_compare.py --root Topologias/Resultados --outdir Topologias/Resultados/Comparacoes

# 3) Simulação real (Simu5G) + análise
python3 Run_Simulations_Simu5G/run_simulations.py --tx 26 --reps 5 --threads 4
```

---