"""LoRa packet listener for the RFM95W radio on Raspberry Pi.

Continuously polls the LoRa radio for incoming CSV packets from field
sensor nodes. Each valid packet is parsed and inserted into SQLite via
the shared process_reading() pipeline.

Packet format from Arduino: node_id,moisture_pct,temperature_c,vcc_millivolts
(CSV string, UTF-8 encoded)

The Arduino sandeepmistry/arduino-LoRa library sends raw bytes — no
RadioHead header is prepended. The Adafruit Python library returns the
full packet bytes when with_header=True, so we use the payload directly.

Run: python3 -m services.lora_listener
"""

import logging
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lora_listener")

# Graceful shutdown flag
_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down...", signum)
    _running = False


def init_radio():
    """Initialize the RFM95W radio via SPI.

    Returns the rfm9x object. Raises ImportError if CircuitPython
    libraries are not installed (expected on non-Pi development machines).
    """
    import board
    import busio
    import digitalio
    import adafruit_rfm9x

    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    cs = digitalio.DigitalInOut(board.CE1)
    reset = digitalio.DigitalInOut(board.D25)

    rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, 915.0)

    # Match Arduino LoRa library defaults
    rfm9x.spreading_factor = 7
    rfm9x.signal_bandwidth = 125000
    rfm9x.coding_rate = 5
    rfm9x.enable_crc = False  # Arduino LoRa library defaults CRC off
    rfm9x.receive_timeout = 5.0

    return rfm9x


def listen(rfm9x):
    """Main receive loop. Polls the radio and processes valid packets."""
    from services.reading_processor import process_reading

    logger.info("Listening on 915 MHz (SF7, BW125k, CR4/5)...")

    while _running:
        packet = rfm9x.receive(with_header=True, keep_listening=True)

        if packet is None:
            continue

        if len(packet) < 1:
            logger.warning("Empty packet, discarding")
            continue

        payload = packet
        rssi = rfm9x.last_rssi

        try:
            csv_string = payload.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("Packet failed UTF-8 decode (%d bytes), discarding", len(payload))
            continue

        logger.info("Received: %r (RSSI: %d dBm)", csv_string, rssi)

        try:
            process_reading(csv_string, rssi=rssi)
        except ValueError as e:
            logger.warning("Invalid reading: %s", e)
        except Exception:
            logger.exception("Unexpected error processing reading")

    logger.info("Listener stopped.")


def main():
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        rfm9x = init_radio()
    except ImportError:
        logger.error(
            "CircuitPython libraries not available. "
            "This script must run on a Raspberry Pi with adafruit-circuitpython-rfm9x installed."
        )
        sys.exit(1)
    except Exception:
        logger.exception("Failed to initialize LoRa radio")
        sys.exit(1)

    listen(rfm9x)


if __name__ == "__main__":
    main()
