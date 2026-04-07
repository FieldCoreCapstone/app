import board
import busio
import digitalio
import adafruit_rfm9x

# Setup SPI and control pins
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.CE1)
reset = digitalio.DigitalInOut(board.D25)

# Initialize radio at 915 MHz
rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, 915.0)

# Match Arduino defaults explicitly
rfm9x.spreading_factor = 7
rfm9x.signal_bandwidth = 125000
rfm9x.coding_rate = 5
rfm9x.enable_crc = False  # Arduino LoRa library defaults to CRC off

rfm9x.receive_timeout = 15.0

print("RFM95W initialized. Listening on 915 MHz...")
print("Waiting for packets...\n")

while True:
    packet = rfm9x.receive(with_header=True, keep_listening=True)
    if packet is not None:
        print(f"Received ({len(packet)} bytes): {packet}")
        try:
            print(f"  As text: {packet.decode('utf-8')}")
        except UnicodeDecodeError:
            print(f"  As hex:  {packet.hex()}")
        print(f"  RSSI: {rfm9x.last_rssi} dBm")
        print(f"  SNR:  {rfm9x.last_snr} dB")
        print()
    else:
        print(".", end="", flush=True)
