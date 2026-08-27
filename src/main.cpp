/*
  RiskGuard - Firmware ESP32 (versão reduzida - MVP, Wokwi)

  Sensores usados no MVP:
    - DHT22 (simula DHT11 no Wokwi) -> temperature, humidity
    - Potenciômetro                  -> simula o MH-RD (chuva)
    - MPU6050                        -> vibration_level, vibration_status
*/
#include <arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ---------- WIFI ----------
// No Wokwi, sempre use estas credenciais (rede de simulação):
const char *WIFI_SSID = "Wokwi-GUEST";
const char *WIFI_PASSWORD = "";

// ---------- SUPABASE ----------
const char *SUPABASE_URL = "https://gtiwgtogdjybxksdcwee.supabase.co/rest/v1/sensor_readings";
const char *SUPABASE_ANON_KEY = "sb_publishable_98yjmG84kWLRj32zStgQvw_NqXUzKqx";
const char *MACHINE_ID = "be4c1c76-0202-455b-9792-910657d703aa"; // TRC-001

// ---------- VALORES FIXOS (campos que saíram do MVP mas existem na tabela) ----------
const float VALOR_FIXO_SPEED = 0.0;
const char *VALOR_FIXO_GPS_ZONE = "campo_aberto";

// ---------- PINOS ----------
#define DHTPIN 23        // DHT22 - digital (temperatura + umidade)
#define DHTTYPE DHT22    // no Wokwi usamos DHT22 (não tem DHT11 disponível)
#define POT_CHUVA_PIN 35 // Potenciômetro simulando o MH-RD (chuva) - ADC
// MPU6050 usa I2C fixo: SDA=21, SCL=22

// ---------- OBJETOS DOS SENSORES ----------
DHT dht(DHTPIN, DHTTYPE);
Adafruit_MPU6050 mpu;

// ---------- TIMING (sem delay, usando millis) ----------
const unsigned long INTERVALO_LEITURA_MS = 5000; // envia a cada 5s
unsigned long ultimoEnvio = 0;

// ---------- PESOS DA FÓRMULA DO RISK_SCORE ----------
const float PESO_TEMPERATURA = 0.25;
const float PESO_UMIDADE = 0.20;
const float PESO_CLIMA = 0.30;
const float PESO_VIBRACAO = 0.25;

// =====================================================
// WIFI
// =====================================================
void conectarWiFi()
{
    Serial.print("Conectando ao WiFi");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    unsigned long inicio = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000)
    {
        Serial.print(".");
        delay(300);
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("\nWiFi conectado!");
        Serial.print("IP: ");
        Serial.println(WiFi.localIP());
    }
    else
    {
        Serial.println("\nFalha ao conectar no WiFi.");
    }
}

// =====================================================
// LEITURAS DOS SENSORES
// =====================================================
void lerDHT(float &temperatura, float &umidade)
{
    temperatura = dht.readTemperature();
    umidade = dht.readHumidity();

    if (isnan(temperatura) || isnan(umidade))
    {
        Serial.println("AVISO: falha ao ler o DHT.");
        temperatura = 25.0; // valor de segurança pra não travar a simulação
        umidade = 50.0;
    }
}

float lerChuvaPotenciometro(String &weatherCondition)
{
    int leituraBruta = analogRead(POT_CHUVA_PIN); // 0-4095
    float mmChuva = (leituraBruta / 4095.0) * 50.0;

    if (mmChuva == 0.0)
    {
        weatherCondition = "ensolarado";
    }
    else if (mmChuva <= 2.5)
    {
        weatherCondition = "nublado";
    }
    else if (mmChuva <= 10.0)
    {
        weatherCondition = "chuvoso";
    }
    else
    {
        weatherCondition = "chuvoso_forte";
    }

    return mmChuva;
}

float lerVibracao()
{
    sensors_event_t accel, gyro, temp;
    mpu.getEvent(&accel, &gyro, &temp);

    float magnitude = sqrt(
        accel.acceleration.x * accel.acceleration.x +
        accel.acceleration.y * accel.acceleration.y +
        accel.acceleration.z * accel.acceleration.z);

    return constrain(abs(magnitude - 9.8), 0.0, 18.0);
}

String classificarVibracao(float vibracao)
{
    if (vibracao <= 6.0)
    {
        return "aceitavel";
    }
    else if (vibracao <= 12.0)
    {
        return "medio";
    }
    else
    {
        return "critico";
    }
}

float calcularRiskScore(float temperatura, float umidade, float mmChuva, float vibracao)
{
    float tempNorm = constrain((temperatura / 50.0) * 100.0, 0, 100);
    float umidNorm = constrain(umidade, 0, 100);
    float climaNorm = constrain((mmChuva / 50.0) * 100.0, 0, 100);
    float vibNorm = constrain((vibracao / 18.0) * 100.0, 0, 100);

    float score = (tempNorm * PESO_TEMPERATURA) +
                  (umidNorm * PESO_UMIDADE) +
                  (climaNorm * PESO_CLIMA) +
                  (vibNorm * PESO_VIBRACAO);

    return constrain(score, 0, 100);
}

// =====================================================
// ENVIO: POST HTTPS pro Supabase
// =====================================================
void enviarParaSupabase(float temperatura, float umidade, float mmChuva,
                        String weatherCondition, float vibracao,
                        String vibrationStatus, float riskScore)
{

    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("ERRO: WiFi desconectado, não foi possível enviar.");
        return;
    }

    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    http.begin(client, SUPABASE_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("apikey", SUPABASE_ANON_KEY);
    http.addHeader("Authorization", String("Bearer ") + SUPABASE_ANON_KEY);
    http.addHeader("Prefer", "return=minimal");

    String payload = "{";
    payload += "\"machine_id\":\"" + String(MACHINE_ID) + "\",";
    payload += "\"temperature\":" + String(temperatura, 2) + ",";
    payload += "\"humidity\":" + String(umidade, 2) + ",";
    payload += "\"speed\":" + String(VALOR_FIXO_SPEED, 2) + ",";
    payload += "\"weather_condition\":\"" + weatherCondition + "\",";
    payload += "\"rain_percent\":" + String(mmChuva, 2) + ",";
    payload += "\"gps_zone\":\"" + String(VALOR_FIXO_GPS_ZONE) + "\",";
    payload += "\"vibration_level\":" + String(vibracao, 2) + ",";
    payload += "\"vibration_status\":\"" + vibrationStatus + "\",";
    payload += "\"risk_score\":" + String(riskScore, 2);
    payload += "}";

    int statusCode = http.POST(payload);

    if (statusCode < 0)
    {
        Serial.print("Falha de conexão (");
        Serial.print(statusCode);
        Serial.println("), tentando de novo...");
        delay(500);
        statusCode = http.POST(payload);
    }

    Serial.print("POST status: ");
    Serial.println(statusCode);

    if (statusCode == 201 || statusCode == 200)
    {
        Serial.println("Leitura enviada com sucesso!");
    }
    else
    {
        Serial.println("Erro ao enviar:");
        Serial.println(http.getString());
    }

    http.end();
}

// =====================================================
// CICLO COMPLETO: ler tudo, calcular, enviar
// =====================================================
void processarCicloDeLeitura()
{
    float temperatura, umidade;
    lerDHT(temperatura, umidade);

    String weatherCondition;
    float mmChuva = lerChuvaPotenciometro(weatherCondition);

    float vibracao = lerVibracao();
    String vibrationStatus = classificarVibracao(vibracao);

    float riskScore = calcularRiskScore(temperatura, umidade, mmChuva, vibracao);

    Serial.println("---- Leitura ----");
    Serial.printf("Temp: %.2f C | Umidade: %.2f%%\n", temperatura, umidade);
    Serial.printf("Chuva (potenciometro): %.2f mm | Clima: %s\n", mmChuva, weatherCondition.c_str());
    Serial.printf("Vibracao: %.2f (%s)\n", vibracao, vibrationStatus.c_str());
    Serial.printf("Risk Score: %.2f\n", riskScore);

    enviarParaSupabase(temperatura, umidade, mmChuva, weatherCondition,
                       vibracao, vibrationStatus, riskScore);
}

// =====================================================
// SETUP
// =====================================================
void setup()
{
    Serial.begin(115200);
    delay(100);

    dht.begin();

    Wire.begin(); // SDA=21, SCL=22
    if (!mpu.begin())
    {
        Serial.println("ERRO: MPU6050 não encontrado. Verifique a fiação.");
    }
    else
    {
        mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
        mpu.setGyroRange(MPU6050_RANGE_500_DEG);
        Serial.println("MPU6050 inicializado.");
    }

    conectarWiFi();

    if (WiFi.status() == WL_CONNECTED)
    {
        delay(1500);
    }

    ultimoEnvio = millis() - INTERVALO_LEITURA_MS;
}

// =====================================================
// LOOP
// =====================================================
void loop()
{
    unsigned long agora = millis();

    if (agora - ultimoEnvio >= INTERVALO_LEITURA_MS)
    {
        ultimoEnvio = agora;
        processarCicloDeLeitura();
    }
}