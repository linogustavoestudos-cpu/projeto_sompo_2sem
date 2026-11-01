"""
clima.py
--------
Melhoria da Sprint 3: contexto meteorologico REAL via API Open-Meteo.

Ideia (para explicar na apresentacao):
  - O ESP32 mede a maquina e o ambiente LOCAL (sensores).
  - A API de clima traz o contexto REGIONAL (chuva, vento, temperatura).
  - O backend cruza os dois: se ha chuva forte ou vento forte na regiao,
    o nivel de risco da leitura sobe um degrau (regra explicavel, em
    risk_classifier.py -> ajustar_por_clima).

Open-Meteo e gratuita e NAO precisa de chave de API nem cadastro.

Uso:
    python clima.py            # enriquece o dados_coletados.csv (uma vez)
    (ou automatico: o endpoint /sync do app.py ja chama enriquecer_csv())
"""

import csv
import os
import tempfile
from datetime import datetime, timezone

import requests

from risk_classifier import (ajustar_por_clima, alerta_clima,
                             classificar_dia_previsao, RECOMENDACAO_DIA)

# Coordenadas usadas para consultar o clima. Padrao = mesma coordenada
# fixa da fazenda usada no firmware. Para trocar sem mexer no codigo:
#   set CLIMA_LAT=-22.90   e   set CLIMA_LON=-47.06   (Windows)
LATITUDE = float(os.getenv("CLIMA_LAT", "-23.550520"))
LONGITUDE = float(os.getenv("CLIMA_LON", "-46.633308"))

# Se o seu storage.py grava o CSV em outro lugar, defina CSV_PATH ou
# troque este caminho.
CAMINHO_CSV_PADRAO = os.getenv(
    "CSV_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_coletados.csv"),
)

TIMEOUT_S = 15
URL_PREVISAO = "https://api.open-meteo.com/v1/forecast"          # atual + ultimos ~3 meses
URL_ARQUIVO = "https://archive-api.open-meteo.com/v1/archive"    # historico antigo
VARIAVEIS = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"

# Colunas novas adicionadas ao CSV
COLUNAS_CLIMA = [
    "clima_temp_externa",
    "clima_umidade_externa",
    "clima_chuva_mm",
    "clima_vento_kmh",
    "alerta_clima",
    "classificacao_com_clima",
]


def buscar_clima_atual(lat=LATITUDE, lon=LONGITUDE):
    """Clima de agora na regiao (usado pelo endpoint /clima)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": VARIAVEIS + ",weather_code",
        "timezone": "UTC",
    }
    resp = requests.get(URL_PREVISAO, params=params, timeout=TIMEOUT_S)
    resp.raise_for_status()
    atual = resp.json()["current"]
    chuva = atual.get("precipitation") or 0.0
    vento = atual.get("wind_speed_10m") or 0.0
    return {
        "hora_utc": atual["time"],
        "temp_externa_c": atual.get("temperature_2m"),
        "umidade_externa_pct": atual.get("relative_humidity_2m"),
        "chuva_mm": chuva,
        "vento_kmh": vento,
        "alerta_clima": alerta_clima(chuva, vento),
        "latitude": lat,
        "longitude": lon,
        "fonte": "Open-Meteo",
    }


def buscar_previsao(dias=7, lat=LATITUDE, lon=LONGITUDE):
    """
    Previsao diaria dos proximos dias (Open-Meteo) ja classificada por
    risco para a operacao em campo. Usada por /previsao e /painel.
    """
    dias = max(1, min(int(dias), 16))
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ("temperature_2m_max,temperature_2m_min,precipitation_sum,"
                  "precipitation_probability_max,wind_speed_10m_max"),
        "forecast_days": dias,
        "timezone": "America/Sao_Paulo",
    }
    resp = requests.get(URL_PREVISAO, params=params, timeout=TIMEOUT_S)
    resp.raise_for_status()
    d = resp.json()["daily"]

    lista = []
    for i, dia in enumerate(d["time"]):
        chuva = d["precipitation_sum"][i] or 0.0
        prob = d["precipitation_probability_max"][i] or 0.0
        vento = d["wind_speed_10m_max"][i] or 0.0
        nivel = classificar_dia_previsao(chuva, prob, vento)
        lista.append({
            "data": dia,
            "temp_min_c": d["temperature_2m_min"][i],
            "temp_max_c": d["temperature_2m_max"][i],
            "chuva_mm": chuva,
            "prob_chuva_pct": prob,
            "vento_max_kmh": vento,
            "nivel_risco": nivel,
            "recomendacao": RECOMENDACAO_DIA[nivel],
        })
    melhor = next((x["data"] for x in lista if x["nivel_risco"] == "NORMAL"), None)
    return {"fonte": "Open-Meteo", "latitude": lat, "longitude": lon,
            "primeiro_dia_bom_para_operar": melhor, "dias": lista}


def buscar_clima_historico(data_ini, data_fim, lat=LATITUDE, lon=LONGITUDE):
    """
    Clima hora a hora entre duas datas (formato 'YYYY-MM-DD', em UTC).
    Devolve {'2026-08-24T23:00': {...}, ...}.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": data_ini,
        "end_date": data_fim,
        "hourly": VARIAVEIS,
        "timezone": "UTC",
    }
    ultimo_erro = None
    for url in (URL_PREVISAO, URL_ARQUIVO):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT_S)
            resp.raise_for_status()
            horario = resp.json()["hourly"]
            break
        except (requests.RequestException, KeyError, ValueError) as e:
            ultimo_erro = e
    else:
        raise RuntimeError(f"Open-Meteo indisponivel: {ultimo_erro}")

    tabela = {}
    for i, hora in enumerate(horario["time"]):
        tabela[hora] = {
            "temp": horario["temperature_2m"][i],
            "umidade": horario["relative_humidity_2m"][i],
            "chuva": horario["precipitation"][i],
            "vento": horario["wind_speed_10m"][i],
        }
    return tabela


def _hora_cheia(data_hora):
    """'2026-08-24T23:20:16.02+00:00' -> '2026-08-24T23:00' (UTC)."""
    dt = datetime.fromisoformat(data_hora)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")


def enriquecer_csv(caminho=CAMINHO_CSV_PADRAO, lat=LATITUDE, lon=LONGITUDE):
    """
    Adiciona ao CSV as colunas de clima real (so nas linhas que ainda nao
    tem). Pode rodar varias vezes sem duplicar nada.
    Devolve quantas linhas foram enriquecidas.
    """
    if not os.path.exists(caminho):
        return 0

    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        campos = list(leitor.fieldnames or [])
        linhas = list(leitor)

    pendentes = [l for l in linhas if not l.get("clima_temp_externa")]
    if not pendentes:
        return 0

    horas = [_hora_cheia(l["data_hora"]) for l in pendentes]
    tabela = buscar_clima_historico(min(horas)[:10], max(horas)[:10], lat, lon)

    for coluna in COLUNAS_CLIMA:
        if coluna not in campos:
            campos.append(coluna)

    enriquecidas = 0
    for linha, hora in zip(pendentes, horas):
        dados = tabela.get(hora)
        if not dados or dados["temp"] is None:
            continue  # hora ainda sem dado na API: fica em branco
        chuva = dados["chuva"] or 0.0
        vento = dados["vento"] or 0.0
        linha["clima_temp_externa"] = dados["temp"]
        linha["clima_umidade_externa"] = dados["umidade"]
        linha["clima_chuva_mm"] = chuva
        linha["clima_vento_kmh"] = vento
        linha["alerta_clima"] = alerta_clima(chuva, vento)
        linha["classificacao_com_clima"] = ajustar_por_clima(
            linha.get("classificacao", ""), chuva, vento
        )
        enriquecidas += 1

    # grava em arquivo temporario e troca no final (nao corrompe o CSV)
    pasta = os.path.dirname(os.path.abspath(caminho))
    fd, tmp = tempfile.mkstemp(suffix=".csv", dir=pasta)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=campos, restval="")
            escritor.writeheader()
            escritor.writerows(linhas)
        os.replace(tmp, caminho)
    except PermissionError:
        os.remove(tmp)
        raise PermissionError(
            "Nao consegui gravar o CSV. Feche o arquivo no Excel e tente de novo."
        )
    return enriquecidas


if __name__ == "__main__":
    n = enriquecer_csv()
    print(f"{n} linha(s) enriquecida(s) com clima real em {CAMINHO_CSV_PADRAO}")
