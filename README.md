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
- **Backend:** Flask (`/sync`, `/latest`, `/saude`, `/previsao`, `/painel`)

## Como rodar

   1. Copie `src/secrets.example.h` para `src/secrets.h` e preencha com suas credenciais (Wi-Fi e Supabase)
   2. Rode a simulação no Wokwi (ou em um ESP32 físico)
   3. Copie `.env.example` para `.env` e preencha com a URL e a chave do Supabase
   4. `pip install -r requirements.txt`
   5. `python app.py`
   6. Acesse `http://localhost:5000/sync` para gerar o CSV (`dados_coletados.csv`)
      
## Autor

Gustavo Lino - FIAP
