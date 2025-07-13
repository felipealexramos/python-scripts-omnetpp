import re
import os
import time

def extract_information(file_path):
    ue_received  = {}
    ue_generated = {}

    try:
        with open(file_path, 'r') as file:
            data = file.read()

            # Ajustado: Nome da rede 'MultiCell_SA_5cells_12BSs'
            matches = re.findall(
                r'scalar MultiCell_SA_5cells_12BSs\.ue\[(\d+)\]\.app\[0\] cbrReceivedThroughtput:mean (\d+(?:\.\d+)?)',
                data)
            for match in matches:
                value = float(match[1])
                ue_index = int(match[0])
                ue_received[ue_index] = value

            # Ajustado: Nome da rede 'MultiCell_SA_5cells_12BSs'
            matches = re.findall(
                r'scalar MultiCell_SA_5cells_12BSs\.server\.app\[(\d+)\] cbrGeneratedThroughtput:mean (\d+(?:\.\d+)?)',
                data)
            for match in matches:
                value = float(match[1])
                ue_index = int(match[0])
                ue_generated[ue_index] = value

    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None, None

    return ue_generated, ue_received

def extract_gnb_information(file_path):
    gnb_data = {}
    gnb_cost = {}
    last_split = {}
    last_solution = {} # Inicialize se for usar e não for preenchido no loop
    gnb_blocks = {}

    try:
        with open(file_path, 'r') as file:
            data = file.read()

            # Ajustado: Nome da rede 'MultiCell_SA_5cells_12BSs'
            matches = re.finditer(
                r'MultiCell_SA_5cells_12BSs\.gnb(\d+)\.cellularNic\.mac CNProcDemandProportion:mean (\d+(?:\.\d+)?)',
                data)
            for match in matches:
                gnb_index = int(match.group(1))
                value = float(match.group(2))
                gnb_data[gnb_index] = value

            # Ajustado: Nome da rede 'MultiCell_SA_5cells_12BSs'
            matches = re.finditer(
                r'MultiCell_SA_5cells_12BSs\.gnb(\d+)\.cellularNic\.mac CNProcDemand:mean (\d+(?:\.\d+)?)',
                data)
            for match in matches:
                gnb_index = int(match.group(1))
                value = float(match.group(2))
                gnb_cost[gnb_index] = value
            
            # Ajustado: Nome da rede 'MultiCell_SA_5cells_12BSs' - regex para placementSolution
            matches = re.finditer(
                r"config \*\.gnb(\d+)\.cellInfo\.placementSolution \"\\\"\{\\\\\\\"(\d+)\\\\\\\": \{\\\\\\\"(\d+)\\\\\\\": (\d+(?:\.\d+)?)",
                data)
            for match in matches:
                gnb_index = int(match.group(1))
                value = float(match.group(4))
                last_split[gnb_index] = [value]
                # A lógica para 'last_solution' não está clara no exemplo, então deixei comentada
                # last_solution[gnb_index] = 7 if value == 0.48 else 2 if value == 0.8 else -1

            # Ajustado: Nome da rede 'MultiCell_SA_5cells_12BSs'
            matches = re.finditer(
                r'MultiCell_SA_5cells_12BSs\.gnb(\d+)\.cellularNic\.mac avgServedBlocksDl:mean (\d+(?:\.\d+)?)',
                data)
            for match in matches:
                gnb_index = int(match.group(1))
                value = float(match.group(2))
                gnb_blocks[gnb_index] = value

    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None, None, None, None, None

    return gnb_data, gnb_cost, last_split, last_solution, gnb_blocks