#include <WiFi.h>
#include "MS5837.h"
#include <Wire.h>

#define SENSOR_ADDR 0x76
#define CMD_RESET 0x1E
#define CMD_CONVERT_D1 0x48
#define CMD_CONVERT_D2 0x58
#define CMD_ADC_READ 0x00
uint16_t C[7];

const char* ssid = "hydroboticsDataTransmission";
const char* password = "controlfloat";

//wifi server IP:192.168.4.1, port:1234
WiFiServer server(1234);
WiFiClient client; 

//logic variables
bool sequenceRunning = false;
bool reverse = false; 
bool pumpIn = false; 
bool pumpOut = false; 
unsigned long stepStartTime = 0;
int step = 0;
bool readPressureData = false;
unsigned long manualStartTime = 0;
const unsigned long MANUAL_DURATION = 10000; // 10 seconds
static unsigned long lastPressure = 0;

void setup() {
  //start data transmission
  Serial.begin(115200);

  pinMode(D3, OUTPUT);
  pinMode(D4, OUTPUT);

  //start WiFi as server 
  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(ssid, password);

  if (ok) {
    Serial.println("Network started");
    Serial.print("IP address: ");
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());
  } else {
    Serial.println("failed");
  }
  // give ap time to init
  delay(1000);
  server.begin();
  server.setNoDelay(true); // prevents buffering issues on ESP32
  Serial.println("TCP server started");

  // ---- I2C + Pressure Sensor ----
  Wire.begin();

  Wire.beginTransmission(SENSOR_ADDR);
  Wire.write(CMD_RESET);
  Wire.endTransmission();
  delay(10);

  readPROM();

  Serial.println("PROM:");
  for (int i = 0; i < 7; i++) {
    Serial.println(C[i]);
  }
}

void testSequence() {

  unsigned long currentTime = millis();

  switch (step) {
    case 0: // Pump in 20 sec
    //write pump to go in one direction, check this before testing in water, if opposite, swap d3 to low and d4 to high 
    //swap d3 to high and d4 to low in the second case for when the pump swaps direction
    //do similar swaps in loop function below where i have marked
      digitalWrite(D3, HIGH);
      digitalWrite(D4, LOW);

      if (currentTime - stepStartTime >= 20000) {
        step = 1;
        stepStartTime = currentTime;
      }
      break;
    case 1: // Wait 5 sec
      digitalWrite(D3, LOW);
      digitalWrite(D4, LOW);

      if (currentTime - stepStartTime >= 5000) {
        step = 2;
        stepStartTime = currentTime;
      }
      break;
    case 2: //pump in opposite direction to first test case to pump water out
      digitalWrite(D3, LOW);
      digitalWrite(D4, HIGH);

      if (currentTime - stepStartTime >= 20000) {
        stopSequence();
      }
      break;
  }
}

//sequence to stop the test midway
void stopSequence() {
  digitalWrite(D3, LOW);
  digitalWrite(D4, LOW);
  sequenceRunning = false;
  step = 0;
}

void loop() {
  static String msgBuffer = "";

  // Accept new client only if none is connected
  if (!client.connected()) {
    //initiates a new client if there is no client currently connected 
    WiFiClient newClient = server.available();
    if (newClient) {
      client = newClient;
      //outputs connected to esp32 on client network
      Serial.println("Client connected!");
      client.println("Connected to ESP32");
      for (int i = 0; i < 7; i++) {
        client.println(C[i]);
      }
    } else {
      static unsigned long lastPrint = 0;
      if (millis() - lastPrint > 2000) {
        Serial.println("Waiting for client...");
        Serial.print("Server IP: ");
        Serial.println(WiFi.softAPIP());
        lastPrint = millis();
      }
    }
  }

  // Read incoming data from client (non-blocking)
  while (client && client.connected() && client.available()) {
    //read character from client and add to an array that holds the message
    char c = client.read();
    if (c != '\r') { // ignore carriage return
      msgBuffer += c;
    }
  }

  // Process message if any data is in buffer
  if (msgBuffer.length() > 0) {
  msgBuffer.trim();
  Serial.println("Received: " + msgBuffer);

    if (msgBuffer.equalsIgnoreCase("starttest")) {
      //starts the test sequence and takes a time variable at that time
      sequenceRunning = true;
      pumpIn = false;
      pumpOut = false;
      step = 0;
      stepStartTime = millis();
      client.println("Test started");

    } else if (msgBuffer.equalsIgnoreCase("stoptest")) {
      //stops the test sequence 
      stopSequence();
      pumpIn = false;
      pumpOut = false;
      client.println("Test stopped");

    } else if (msgBuffer.equalsIgnoreCase("pumpin")) {

      stopSequence();
      pumpIn = true;
      pumpOut = false;
      manualStartTime = millis();
      client.println("Pumping in for 10 seconds");

    } else if (msgBuffer.equalsIgnoreCase("pumpout")) {

      stopSequence();
      pumpOut = true;
      pumpIn = false;
      manualStartTime = millis();
      client.println("Pumping out for 10 seconds");
    } else if (msgBuffer.equalsIgnoreCase("readPressure")){
      readPressureData = true;
      client.println("Measuring pressure");
    } else if (msgBuffer.equalsIgnoreCase("stopPressure")){
      readPressureData = false;
      client.println("Stopping pressure measurement");
    }

    msgBuffer = "";
  }

  // Control the pump continuously
  if (sequenceRunning) {

    testSequence();

  } else if (pumpIn) {
    //swap high with low and vice versa if the pump is pumping out instead of in
    digitalWrite(D3, HIGH);
    digitalWrite(D4, LOW);

  //if the time since starting the pump sequence and current time is greater than the duration of the manual control, then stop the pumps
    if (millis() - manualStartTime >= MANUAL_DURATION) {
      pumpIn = false;
      digitalWrite(D3, LOW);
      digitalWrite(D4, LOW);
      Serial.println("Pump in complete");
    }
  } else if (pumpOut) {
    //swap high with low and vice versa if the pump is pumping in instead of out
    digitalWrite(D3, LOW);
    digitalWrite(D4, HIGH);

    //if the time since starting the pump sequence and current time is greater than the duration of the manual control, then stop the pumps
    if (millis() - manualStartTime >= MANUAL_DURATION) {
      pumpOut = false;
      digitalWrite(D3, LOW);
      digitalWrite(D4, LOW);
      Serial.println("Pump out complete");
    }

  } else {

    digitalWrite(D3, LOW);
    digitalWrite(D4, LOW);
  }

  // read pressure telemetry at 20hz
  if (readPressureData && millis() - lastPressure > 50){
    lastPressure = millis();
    readPressureSensor();
  }
}

void readPROM() {
  for (uint8_t i = 0; i < 7; i++) {
    Wire.beginTransmission(SENSOR_ADDR);
    Wire.write(0xA0 + (i * 2));
    Wire.endTransmission();

    Wire.requestFrom(SENSOR_ADDR, 2);
    C[i]  = Wire.read() << 8;
    C[i] |= Wire.read();
  }
}

uint32_t readADC() {
  Wire.beginTransmission(SENSOR_ADDR);
  Wire.write(CMD_ADC_READ);
  Wire.endTransmission();

  Wire.requestFrom(SENSOR_ADDR, 3);
  uint32_t value = 0;
  value = Wire.read() << 16;
  value |= Wire.read() << 8;
  value |= Wire.read();
  return value;
}

void readPressureSensor() {
  // start pressure conversion
  Wire.beginTransmission(SENSOR_ADDR);
  Wire.write(CMD_CONVERT_D1);
  Wire.endTransmission();
  delay(10);

  uint32_t D1 = readADC();

  // start temperature conversion
  Wire.beginTransmission(SENSOR_ADDR);
  Wire.write(CMD_CONVERT_D2);
  Wire.endTransmission();
  delay(10);

  uint32_t D2 = readADC();
  Serial.print("D1=");
  Serial.print(D1);
  Serial.print("  D2=");
  Serial.println(D2);
  client.println("D1:" + String(D1, 3)+
      ",D2:" + String(D2, 3));

  int32_t dT = D2 - (uint32_t)C[5] * 256;
  int32_t TEMP = 2000 + (int64_t)dT * C[6] / 8388608;

  int64_t OFF  = (int64_t)C[2] * 65536 + ((int64_t)C[4] * dT) / 128;
  int64_t SENS = (int64_t)C[1] * 32768 + ((int64_t)C[3] * dT) / 256;

  int32_t Praw = (((D1 * SENS) / 2097152) - OFF) / 32768;

  // ------------------------------
  // FIX: MS5803 pressure scaling
  // ------------------------------

  // Final pressure in mbar (no division)
  float pressure_mbar = Praw;

  float temperature_C = TEMP / 100.0f;

  // Depth formula (seawater density)
  float depth_m = (pressure_mbar - 1013.25f) / (1029.0f / 10.0f);

  Serial.println(temperature_C);
  Serial.println(pressure_mbar);
  Serial.println(depth_m);
  Serial.println(millis());
  if (client && client.connected()){
    client.println(
      "T:" + String(temperature_C, 3) +
      ",P:" + String(pressure_mbar, 3) +
      ",D:" + String(depth_m, 3) +
      ",TIME:" + String(millis())
    );
  }
}