import socket

ESP_IP = "192.168.4.1"
PORT = 1234

def send_command(command: str):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print(f"Connecting to ESP32 at {ESP_IP}:{PORT}...")
        s.connect((ESP_IP, PORT))
        s.sendall(f"{command}\n".encode())
        response = s.recv(1024)
        print("ESP32:", response.decode())

send_command("START")  # Start control loop
#send_command("STOP")  # Stop control loop

"""
#include <WiFi.h>

const char* ssid = "ESP32_AP";       // Network name you choose
const char* password = "12345678";   // Network password you choose

WiFiServer server(1234); // TCP port
bool loopActive = false;

void setup() {
  Serial.begin(115200);

  // Start ESP32 as access point
  WiFi.softAP(ssid, password);
  Serial.println("Access Point started");
  Serial.print("Connect to Wi-Fi SSID: ");
  Serial.println(ssid);
  Serial.print("AP IP address: ");
  Serial.println(WiFi.softAPIP());

  server.begin();
  Serial.println("TCP server started");
}

void startControlLoop() { loopActive = true; }
void stopControlLoop() { loopActive = false; }

void loop() {
  WiFiClient client = server.available();
  if (client) {
    while (client.connected()) {
      if (client.available()) {
        String cmd = client.readStringUntil('\n');
        cmd.trim();
        if (cmd == "START") {
          client.println("Starting control loop...");
          startControlLoop();
        } else if (cmd == "STOP") {
          client.println("Stopping control loop...");
          stopControlLoop();
        } else {
          client.println("Unknown command");
        }
      }
    }
    client.stop();
  }

  if (loopActive) {
    int val = analogRead(34);
    Serial.println(val);
    delay(100);
  }
}
"""

"""
Flash the ESP32 sketch that sets it up as an AP and runs the TCP server.

On your computer, connect to the Wi-Fi network broadcast by the ESP32 (SSID/password you defined in the sketch, e.g., ESP32_AP / 12345678).

Run your Python client code while connected. The Python script talks to the ESP32 over the TCP port (e.g., 1234) using the ESP32’s AP IP — usually 192.168.4.1 by default.

Send commands like "START" or "STOP" — the ESP32 receives them and toggles the control loop.
"""