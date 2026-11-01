"""
storage.py
----------
Responsabilidade única: buscar leituras novas no Supabase e gravar no
CSV local. Esta é a mudança de arquitetura: antes a Flask RECEBIA POST
do ESP32; agora ela BUSCA (GET) as leituras que o ESP32 já gravou
direto no Supabase. Isso evita depender da rede simulada do
Wokwi conseguir alcançar o localhost do seu PC (ela não consegue).

Fluxo: ESP32 --HTTPS--> Supabase  |  Flask --HTTPS GET--> Supabase --> CSV
"""

from __future__ import annotations  # compatibilidade com Python < 3.10

import csv
import os
from datetime import datetime, timezone

import requests

from config import (
    CSV_PATH,
    CSV_COLUMNS,
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
    SUPABASE_TABLE,
    TIPO_OPERACAO_PADRAO,
    ULTIMO_SYNC_PATH,
)
from risk_classifier import classificar_risco


def _garantir_csv_existe():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def _ler_ultimo_sync() -> str | None:
    """Lê o timestamp da última leitura já sincronizada (se existir)."""
    if os.path.exists(ULTIMO_SYNC_PATH):
        with open(ULTIMO_SYNC_PATH, "r", encoding="utf-8") as f:
            valor = f.read().strip()
            return valor if valor else None
    return None


def _salvar_ultimo_sync(timestamp: str):
    with open(ULTIMO_SYNC_PATH, "w", encoding="utf-8") as f:
        f.write(timestamp)


def buscar_novas_leituras() -> list[dict]:
    """
    Busca no Supabase todas as leituras criadas DEPOIS da última
    sincronização. Na primeira execução (sem histórico de sync), busca
    as últimas 50 leituras, pra não trazer o banco inteiro de uma vez.
    """
    ultimo_sync = _ler_ultimo_sync()

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
    }
    params = {
        "select": "*",
        "order": "created_at.asc",
    }

    if ultimo_sync:
        params["created_at"] = f"gt.{ultimo_sync}"
    else:
        # primeira vez: pega só as últimas 50 pra não trazer tudo
        params["order"] = "created_at.desc"
        params["limit"] = "50"

    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    leituras = resp.json()

    if not ultimo_sync:
        leituras = list(reversed(leituras))  # volta pra ordem cronológica

    return leituras


def salvar_leituras_csv(leituras: list[dict]) -> int:
    """
    Classifica e grava cada leitura no CSV. Retorna quantas linhas
    foram gravadas.
    """
    if not leituras:
        return 0

    _garantir_csv_existe()

    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        for leitura in leituras:
            classificacao = classificar_risco(
                risk_score=leitura.get("risk_score", 0),
                vibration_status=leitura.get("vibration_status", ""),
            )
            writer.writerow({
                "id_equipamento": leitura.get("machine_id"),
                "tipo_operacao": TIPO_OPERACAO_PADRAO,
                "temperatura": leitura.get("temperature"),
                "umidade": leitura.get("humidity"),
                "chuva_mm": leitura.get("rain_percent"),
                "weather_condition": leitura.get("weather_condition"),
                "vibracao": leitura.get("vibration_level"),
                "vibration_status": leitura.get("vibration_status"),
                "risk_score": leitura.get("risk_score"),
                "classificacao": classificacao,
                "data_hora": leitura.get("created_at"),
            })

    # marca a última leitura sincronizada pra não duplicar da próxima vez
    _salvar_ultimo_sync(leituras[-1]["created_at"])
    return len(leituras)
