# config.py — sensor configuration
# Copy this file to the CIRCUITPY drive and edit it there.
# code.py imports from here; you never need to touch code.py to reconfigure.

import board

DEVICE_NAME = "nRF52840 Soil moisture sensor"

# ── Timing ───────────────────────────────────────────────────────────────────
ADV_DURATION_S = 5          # seconds to keep advertising each wake cycle
                            # Increase this if the Bluetooth proxy does not reliably receive the advertisement.
SLEEP_S        = 60         # seconds to sleep between readings

# ── BTHome v2 encryption ─────────────────────────────────────────────────────
# Set ENCRYPT = True and replace ENCRYPTION_KEY with your own 16-byte key.
# The same key must be entered as the "Bindkey" in Home Assistant when adding
# the device.  Generate a random key on the board:
#    import os; print(os.urandom(16).hex())
# or copy Key_generator.py to the board and run it.
ENCRYPT        = True
ENCRYPTION_KEY = bytes.fromhex("490b52a8fa848d43d145e5692b436db7")   # REPLACE with your 16-byte key before enabling

# --- Pins ---
# This targets the "ProMicro/SuperMini nRF52840" clone family (V1940 and
# similar AliExpress boards; officially supported by CircuitPython as
# "SuperMini NRF52840" by ICBbuy). On these boards P0.13/P0.04 are fixed
# by the board hardware rather than by user wiring:
#   - board.AIN5 (P0.29) is used for an EXTERNAL resistor divider wired to
#     the battery. The onboard BAT_VOLT/AIN2 sense circuit was found to track
#     VDD rather than true cell voltage when running from battery only (reading
#     compresses and also varies with load/moisture changes), making it
#     unreliable. An external divider on a free ADC pin avoids this entirely.
#     Wiring: Battery+ → R1 → AIN5 → R2 → GND. Use high-value resistors
#     (≥470kΩ) to minimise quiescent current. Set BATTERY_DIVIDER_RATIO to
#     (R1+R2)/R2 and calibrate against a multimeter reading.
# This board's `board` module does NOT define Arduino-style names like A0/A1/D2
# -- only P0_xx/P1_xx pin names plus a few aliases (AIN0, AIN2, AIN5, AIN7,
# BAT_VOLT, VCC_OFF, LED, RX, TX, SCL, SDA, SCK, MOSI, MISO). AIN2 is already
# used by BAT_VOLT, so the soil sensor uses another free analog-capable pin:
# AIN0 (P0.02). If you wired the soil sensor elsewhere, use board.AIN5
# (P0.29) or board.AIN7 (P0.31) instead, matching your wiring.

# ── ADC pins ──────────────────────────────────────────────────────────────────
# Change these if you wired the sensors to different pins.
SOIL_ADC_PIN    = board.AIN0   # soil moisture sensor output
BATTERY_ADC_PIN = board.AIN7   # external resistor divider (Battery+ → R1 → AIN7 → R2 → GND)

# ── power pin ──────────────────────────────────────────────────────────
# The SENSOR_POWER_PIN pin is controlled by the board
# so that the connected sensor is turned on and off to limit consumption. 
SENSOR_POWER_PIN = board.P0_17
# Logic levels used to switch the sensor supply.
SENSOR_POWER_ON_VALUE  = True
SENSOR_POWER_OFF_VALUE = False

# ── Battery calibration ───────────────────────────────────────────────────────
# 1. Read "Battery raw ADC" from the serial console while measuring the real
#    battery voltage with a multimeter at the same time.
# 2. Set BATTERY_DIVIDER_RATIO = real_voltage / (raw / 65535 * 3.6)
# 3. Fine-tune with BATTERY_SCALE / BATTERY_OFFSET afterwards if needed.
# Perform the calibration with the USB cable disconnected, otherwise the
# board may measure USB supply voltage instead of the battery.
BATTERY_DIVIDER_RATIO = 2    # (R1 + R2) / R2 for your chosen resistors
BATTERY_SCALE         = 0.93     # multiplicative fine-tune
BATTERY_OFFSET        = 0.0     # additive fine-tune (V)

# ── Soil moisture calibration ─────────────────────────────────────────────────
# You can read DRY_VAL and WET_VAL in the serial shell
# If you can't, simply adjust HUMIDITY_SCALE and HUMIDITY_OFFSET
DRY_VAL         = 65515 # DRY_VAL  : raw ADC reading with the probe in dry air
WET_VAL         = 28160 # WET_VAL  : raw ADC reading with the probe fully submerged in water
# Adjust HUMIDITY_SCALE / HUMIDITY_OFFSET after real-world spot-checks.
HUMIDITY_SCALE  = 1
HUMIDITY_OFFSET = 0.0

# ── Alert thresholds ──────────────────────────────────────────────────────────
LOW_MOISTURE_THRESHOLD = 20.0   # % — below this the Moisture binary sensor turns on
LOW_BATTERY_THRESHOLD  = 3.3   # V — below this the Battery binary sensor turns on