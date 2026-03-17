import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_PATH = os.environ.get("FIELDCORE_DB", os.path.join(BASE_DIR, "sensors.db"))
DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

# Sensor calibration: raw capacitance range for moisture normalization
MOISTURE_RAW_MIN = 0
MOISTURE_RAW_MAX = 700
