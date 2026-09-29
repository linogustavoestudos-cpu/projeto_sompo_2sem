# RiskGuard

Projeto que busca prevenir e registrar possíveis causas de sinistros em máquinas e equipamentos agrícolas. Sensores e condições climáticas alimentam um cálculo de risco (risk score) que classifica a operação como NORMAL, ATENÇÃO ou CRÍTICO.

## Como funciona

ESP32 (sensores) → Supabase → API Flask → CSV (`dados_coletados.csv`)

## Tecnologias

- **Linguagens:** Python, C++
- **Microcontrolador:** ESP32 (simulado no Wokwi)
- **Sensores:** DHT22 (temperatura e umidade), MPU6050 (vibração), potenciômetro simulando o sensor de chuva MH-RD
- **Atuador:** LED (pisca devagar em ATENÇÃO e rápido em CRÍTICO)
- **Banco de dados:** Supabase
- **Backend:** Flask (`/sync`, `/latest`, `/saude`)

## Como rodar

1. Rodar a simulação no Wokwi (ou ESP32 físico)
2. `pip install -r requirements.txt`
3. `python app.py`
4. Acessar `http://localhost:5000/sync` para gerar o CSV

## Autor

Gustavo Lino - FIAP
