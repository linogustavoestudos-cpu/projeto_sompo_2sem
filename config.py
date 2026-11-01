"""
config.py
---------
Configurações centrais do projeto RiskGuard - versão ajustada para o
schema REAL da tabela `sensor_readings` (confirmado via curl) e para o
MVP de 3 sensores (temperatura/umidade, chuva, vibração).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Supabase ---
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL")
# Usamos a chave SECRETA aqui: a Flask é backend, e precisamos ler
# (GET) os dados que o ESP32 já gravou - leitura ampla é papel do
# backend, não do dispositivo de campo.
SUPABASE_SECRET_KEY = os.environ.get(
    "SUPABASE_SECRET_KEY")
SUPABASE_TABLE = "sensor_readings"

# --- Arquivo CSV pedido pela Sprint 3 ---
CSV_PATH = os.path.join(os.path.dirname(__file__), "dados_coletados.csv")
CSV_COLUMNS = [
    "id_equipamento",      # machine_id
    "tipo_operacao",       # fixo no MVP - ver TIPO_OPERACAO_PADRAO abaixo
    "temperatura",
    "umidade",
    "chuva_mm",            # rain_percent
    "weather_condition",
    "vibracao",            # vibration_level
    "vibration_status",
    "risk_score",
    # calculada pela própria Flask (NORMAL/ATENCAO/CRITICO)
    "classificacao",
    "data_hora",           # created_at
]

TIPO_OPERACAO_PADRAO = "campo"

# Arquivo que guarda o timestamp da última leitura já sincronizada,
# pra não duplicar linhas no CSV toda vez que rodarmos o /sync.
ULTIMO_SYNC_PATH = os.path.join(os.path.dirname(__file__), "ultimo_sync.txt")

# --- Limites para classificação de risco (mesma lógica do firmware) ---
LIMITE_RISK_SCORE_CRITICO = 70.0
LIMITE_RISK_SCORE_ATENCAO = 40.0
