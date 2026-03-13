import socket
import threading
import os
import time

ESP32_IP = "192.168.4.1"
PORT = 1234
outputPath = "telemetry.csv"
running = False
class Client():
    def __init__(self, ip=ESP32_IP, port=PORT, output=outputPath):
        self.ESP32_IP = ip
        self.PORT = port
        self.outputPath = output
        self.running = False

    def start(self):
        if os.path.dirname(self.outputPath):
            os.makedirs(os.path.dirname(self.outputPath), exist_ok=True)
        print("Connecting to ESP32...")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.ESP32_IP, self.PORT))
        except Exception as e:
            print("Connection failed:", e)
            return
        self.running = True
        print("Connected to ESP32\n")
        print("Commands:")
        print("starttest, stoptest, pumpin, pumpout, readPressure, stopPressure\n")
        # Start receiver thread
        print("Starting telemetry receiver...")
        threading.Thread(target=self.receive_loop, args=(self.sock,), daemon=True).start()

        # Run send loop in main thread
        print("Ready to send commands. Type 'exit' to quit.")
        self.send_loop(self.sock)

    def receive_loop(self, sock):
        """Continuously receive telemetry from ESP32."""
        with open(self.outputPath, "a") as f:
          while self.running:
              try:
                  data = sock.recv(1024)
                  if not data:
                      print("Connection closed")
                      self.running = False
                      break
                  for line in data.decode(errors="ignore").splitlines():
                    f.write(f"{time.time()},{line.strip()}\n")
                    f.flush()

              except Exception as e:
                  print("Receive error:", e)
                  self.running = False
                  break

    def send_loop(self, sock):
        """Allow user to send commands."""
        while self.running:
            try:
                cmd = input("> ")

                if cmd.lower() == "exit":
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except:
                        pass
                    sock.close()
                    self.running = False
                    break

                sock.sendall((cmd + "\n").encode())

            except Exception as e:
                print("Send error:", e)
                self.running = False
                break

client = Client(ip=ESP32_IP, port=PORT, output=outputPath)
try:
    client.start()
except KeyboardInterrupt:
    print("\nExiting...")
    client.running = False
    try:
        client.sock.shutdown(socket.SHUT_RDWR)
    except:
        pass
    client.sock.close()