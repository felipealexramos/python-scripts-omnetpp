import pandas as pd
import matplotlib.pyplot as plt
import ipywidgets as widgets
from IPython.display import display, clear_output

# Interface interativa para simular consumo de energia
def calcular_energia(P_idle, alpha, D_proc, beta, num_UEs, T_sim, potencias_dbm):
    resultados = []
    for pot in potencias_dbm:
        P_gnb = P_idle + alpha * D_proc + beta * num_UEs
        E_total = P_gnb * T_sim
        resultados.append({
            "Potência (dBm)": pot,
            "Potência Média gNB (W)": P_gnb,
            "Energia Total Consumida (J)": E_total
        })
    df = pd.DataFrame(resultados)
    return df

def plotar(df):
    plt.figure(figsize=(10, 6))
    plt.plot(df["Potência (dBm)"], df["Energia Total Consumida (J)"], marker="o")
    plt.title("Energia Total Consumida vs Potência de Transmissão")
    plt.xlabel("Potência de Transmissão (dBm)")
    plt.ylabel("Energia Total Consumida (J)")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def atualizar(P_idle, alpha, D_proc, beta, num_UEs, T_sim, potencias_texto):
    clear_output(wait=True)
    try:
        potencias = [int(p.strip()) for p in potencias_texto.split(",") if p.strip().isdigit()]
        df = calcular_energia(P_idle, alpha, D_proc, beta, num_UEs, T_sim, potencias)
        display(df)
        plotar(df)
    except Exception as e:
        print(f"Erro ao processar entradas: {e}")

# Widgets
P_idle_widget = widgets.FloatText(value=500, description="P_idle (W)")
alpha_widget = widgets.FloatText(value=10, description="Alpha")
D_proc_widget = widgets.FloatText(value=1.5, description="D_proc")
beta_widget = widgets.FloatText(value=5, description="Beta")
num_UEs_widget = widgets.IntText(value=39, description="# UEs")
T_sim_widget = widgets.FloatText(value=5, description="T_sim (s)")
potencias_widget = widgets.Text(value="6,16,26,36,46,56", description="Potências (dBm)", layout=widgets.Layout(width='400px'))

botao = widgets.Button(description="Calcular")

ui = widgets.VBox([
    widgets.HBox([P_idle_widget, alpha_widget, D_proc_widget]),
    widgets.HBox([beta_widget, num_UEs_widget, T_sim_widget]),
    potencias_widget,
    botao
])

def on_click(b):
    atualizar(
        P_idle_widget.value,
        alpha_widget.value,
        D_proc_widget.value,
        beta_widget.value,
        num_UEs_widget.value,
        T_sim_widget.value,
        potencias_widget.value
    )

botao.on_click(on_click)
display(ui)
