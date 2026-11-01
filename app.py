"""
app.py
------
API Flask do projeto RiskGuard - Sprint 3.

Endpoints:
  GET /sync   -> busca leituras novas no Supabase, classifica e grava no CSV
  GET /latest -> mostra a leitura mais recente já sincronizada (útil pro vídeo)
  GET /clima  -> clima real da região agora (API Open-Meteo) + alerta
  GET /previsao?dias=7 -> previsão dos próximos dias, classificada por risco
  GET /painel -> página visual (clima de hoje + próximos dias) para a apresentação
  GET /saude  -> confirma que a API está no ar

Como rodar:
    pip install flask requests
    python app.py

Como usar (durante o vídeo/demonstração):
    1. Deixe o ESP32 rodando (Wokwi ou físico), enviando pro Supabase
    2. Abra http://localhost:5000/sync no navegador (ou rode
       curl http://localhost:5000/sync) sempre que quiser puxar as
       leituras novas pro CSV
    3. Abra o arquivo dados_coletados.csv pra mostrar os dados

Isso cumpre o pedido do professor (ESP32 -> API Flask -> CSV): o ESP32
alimenta o Supabase, e é a API Flask quem processa esses dados e forma
a base de dados em CSV, com identificação do equipamento, tipo de
operação, medições, classificação e data/hora, exatamente como pedido.
"""

from flask import Flask, jsonify, render_template_string, request

from storage import buscar_novas_leituras, salvar_leituras_csv
from risk_classifier import classificar_risco
# melhoria: clima real
from clima import buscar_clima_atual, buscar_previsao, enriquecer_csv

app = Flask(__name__)


@app.route("/sync", methods=["GET"])
def sync():
    """Busca leituras novas no Supabase e grava no CSV local."""
    try:
        leituras = buscar_novas_leituras()
    except Exception as e:
        return jsonify({"erro": f"Falha ao consultar o Supabase: {e}"}), 502

    qtd_gravadas = salvar_leituras_csv(leituras)

    # Melhoria: cruza cada leitura com o clima real da região. Se a API
    # de clima falhar, o CSV continua salvo normalmente (sem as colunas).
    try:
        qtd_clima = enriquecer_csv()
        clima_msg = f"{qtd_clima} linha(s) enriquecida(s) com clima real."
    except Exception as e:
        clima_msg = f"Clima indisponível agora ({e}). CSV salvo sem dados de clima."

    return jsonify({
        "leituras_novas": qtd_gravadas,
        "mensagem": (
            f"{qtd_gravadas} leitura(s) sincronizada(s) para o CSV."
            if qtd_gravadas > 0 else
            "Nenhuma leitura nova desde a última sincronização."
        ),
        "clima": clima_msg,
    }), 200


@app.route("/latest", methods=["GET"])
def latest():
    """Mostra a leitura mais recente do Supabase, já classificada (só
    consulta - não grava no CSV, use /sync pra isso)."""
    import requests
    from config import SUPABASE_URL, SUPABASE_SECRET_KEY, SUPABASE_TABLE

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}"
    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
    }
    params = {"select": "*", "order": "created_at.desc", "limit": "1"}

    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    dados = resp.json()

    if not dados:
        return jsonify({"mensagem": "Nenhuma leitura encontrada."}), 404

    leitura = dados[0]
    classificacao = classificar_risco(
        risk_score=leitura.get("risk_score", 0),
        vibration_status=leitura.get("vibration_status", ""),
    )
    leitura["classificacao"] = classificacao
    return jsonify(leitura), 200


@app.route("/clima", methods=["GET"])
def clima():
    """Clima real da região agora (Open-Meteo) e se há alerta de chuva/vento."""
    try:
        return jsonify(buscar_clima_atual()), 200
    except Exception as e:
        return jsonify({"erro": f"Falha ao consultar a API de clima: {e}"}), 502


@app.route("/previsao", methods=["GET"])
def previsao():
    """Previsao dos proximos dias, classificada por risco (JSON)."""
    try:
        dias = int(request.args.get("dias", 7))
        return jsonify(buscar_previsao(dias)), 200
    except Exception as e:
        return jsonify({"erro": f"Falha ao consultar a previsao: {e}"}), 502


PAINEL_HTML = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>RiskGuard - Clima e planejamento de rotas</title>
<style>
 body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f4f6f8;color:#1b2733}
 h1{margin:0 0 4px} .sub{color:#5b6b7a;margin-bottom:20px}
 .card{background:#fff;border-radius:10px;padding:16px 20px;margin-bottom:20px;box-shadow:0 1px 4px #0002}
 table{border-collapse:collapse;width:100%} th,td{padding:10px;text-align:center;border-bottom:1px solid #e3e8ee}
 th{background:#1b2733;color:#fff} .NORMAL{background:#d8f3dc}.ATENCAO{background:#fff3bf}.CRITICO{background:#ffd6d6}
 .agora span{display:inline-block;margin-right:28px}
</style></head><body>
<h1>RiskGuard &mdash; Clima real e planejamento de rotas</h1>
<div class="sub">Fonte: Open-Meteo &bull; coordenadas {{ lat }}, {{ lon }}</div>
{% if erro %}<div class="card CRITICO">Nao foi possivel consultar a API de clima: {{ erro }}</div>{% else %}
<div class="card agora"><h3>Agora na regiao</h3>
 <span><b>{{ a.temp_externa_c }} &deg;C</b> temperatura</span>
 <span><b>{{ a.umidade_externa_pct }}%</b> umidade</span>
 <span><b>{{ a.chuva_mm }} mm</b> chuva</span>
 <span><b>{{ a.vento_kmh }} km/h</b> vento</span>
 <span>Alerta: <b>{{ a.alerta_clima }}</b></span></div>
<div class="card"><h3>Proximos dias &mdash; janela de operacao para os tratores</h3>
<table><tr><th>Data</th><th>   Temperatura min / max (&deg;C)</th><th>Chuva (mm)</th><th>Prob. chuva</th><th>Vento max (km/h)</th><th>Risco</th><th>Recomendacao</th></tr>
{% for d in p.dias %}<tr class="{{ d.nivel_risco }}"><td>{{ d.data }}</td><td>{{ d.temp_min_c }} / {{ d.temp_max_c }}</td>
<td>{{ d.chuva_mm }}</td><td>{{ d.prob_chuva_pct }}%</td><td>{{ d.vento_max_kmh }}</td><td><b>{{ d.nivel_risco }}</b></td><td>{{ d.recomendacao }}</td></tr>{% endfor %}
</table>
<p>Primeiro dia bom para operar: <b>{{ p.primeiro_dia_bom_para_operar or "nenhum nos proximos dias" }}</b></p></div>{% endif %}
</body></html>"""


@app.route("/painel", methods=["GET"])
def painel():
    """Pagina visual para a apresentacao: clima de hoje + previsao."""
    try:
        atual = buscar_clima_atual()
        prev = buscar_previsao(7)
        return render_template_string(PAINEL_HTML, a=atual, p=prev,
                                      lat=atual["latitude"], lon=atual["longitude"], erro=None)
    except Exception as e:
        return render_template_string(PAINEL_HTML, erro=str(e), lat="-", lon="-"), 502


@app.route("/saude", methods=["GET"])
def saude():
    return jsonify({"status": "API no ar"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
