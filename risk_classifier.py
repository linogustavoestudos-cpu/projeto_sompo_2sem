"""
risk_classifier.py
-------------------
Reaplica no backend a MESMA regra de classificacao de risco que ja
existe no firmware do ESP32 (funcao classificarRisco() no main.cpp).

Por que calcular de novo se o ESP32 ja manda o risk_score pronto?
Porque a Sompo pede resultados "explicaveis" e um "score por
equipamento" - ter essa regra tambem no backend permite reclassificar
o historico inteiro (ex: se decidirem mudar os limites de risco no
futuro, nao precisam reprogramar todos os ESP32 em campo, so rodar de
novo esse script sobre os dados ja salvos).

MELHORIA (clima real): ajustar_por_clima() sobe a classificacao um
degrau quando a API meteorologica indica chuva forte ou vento forte
na regiao. Esses limites seguem faixas meteorologicas usuais.
"""

from config import LIMITE_RISK_SCORE_CRITICO, LIMITE_RISK_SCORE_ATENCAO

# Limites do clima real (podem ser ajustados sem mexer no resto)
LIMITE_CHUVA_FORTE_MM = 10.0   # mm na ultima hora
LIMITE_VENTO_FORTE_KMH = 40.0  # km/h


def classificar_risco(risk_score: float, vibration_status: str) -> str:
    """
    Mesma regra do firmware: vibracao critica forca CRITICO
    independente do score geral (um tombamento e grave sozinho).
    """
    if vibration_status == "critico" or risk_score >= LIMITE_RISK_SCORE_CRITICO:
        return "CRITICO"
    if vibration_status == "medio" or risk_score >= LIMITE_RISK_SCORE_ATENCAO:
        return "ATENCAO"
    return "NORMAL"


def alerta_clima(chuva_mm, vento_kmh) -> str:
    """Rotulo do alerta meteorologico: nenhum / chuva_forte / vento_forte / chuva_e_vento."""
    chuva = float(chuva_mm or 0)
    vento = float(vento_kmh or 0)
    chuva_forte = chuva >= LIMITE_CHUVA_FORTE_MM
    vento_forte = vento >= LIMITE_VENTO_FORTE_KMH
    if chuva_forte and vento_forte:
        return "chuva_e_vento"
    if chuva_forte:
        return "chuva_forte"
    if vento_forte:
        return "vento_forte"
    return "nenhum"


def ajustar_por_clima(classificacao: str, chuva_mm, vento_kmh) -> str:
    """Sobe um degrau (NORMAL->ATENCAO->CRITICO) se houver alerta de clima."""
    if alerta_clima(chuva_mm, vento_kmh) == "nenhum":
        return classificacao
    degrau_acima = {"NORMAL": "ATENCAO", "ATENCAO": "CRITICO", "CRITICO": "CRITICO"}
    return degrau_acima.get(classificacao, classificacao)


# ---------- Previsao (dias futuros) ----------
# Limites diarios (ajustaveis). Sao faixas meteorologicas usuais, nao
# regras oficiais da Sompo: ajuste conforme a operacao real.
LIMITE_DIA_CHUVA_CRITICA_MM = 20.0
LIMITE_DIA_CHUVA_ATENCAO_MM = 5.0
LIMITE_DIA_PROB_ATENCAO_PCT = 70.0


def classificar_dia_previsao(chuva_mm, prob_chuva_pct, vento_max_kmh):
    """Classifica um dia FUTURO: NORMAL / ATENCAO / CRITICO."""
    chuva = float(chuva_mm or 0)
    prob = float(prob_chuva_pct or 0)
    vento = float(vento_max_kmh or 0)
    if chuva >= LIMITE_DIA_CHUVA_CRITICA_MM or vento >= LIMITE_VENTO_FORTE_KMH:
        return "CRITICO"
    if (chuva >= LIMITE_DIA_CHUVA_ATENCAO_MM or prob >= LIMITE_DIA_PROB_ATENCAO_PCT
            or vento >= LIMITE_DIA_VENTO_ATENCAO_KMH):
        return "ATENCAO"
    return "NORMAL"


RECOMENDACAO_DIA = {
    "NORMAL": "Bom para operar em campo",
    "ATENCAO": "Operar com cautela / avaliar rotas",
    "CRITICO": "Evitar operacao em campo / replanejar rotas",
}
