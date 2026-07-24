# CircuitPython firmware for a BTHome soil moisture sensor.
# Target: SuperMini / ProMicro nRF52840 (CircuitPython)
#
# Reads soil moisture, battery voltage, and the MCU die temperature,
# then broadcasts the measurements as a BTHome v2 BLE advertisement
# for Home Assistant (via an ESPHome Bluetooth Proxy or any compatible
# BTHome receiver). The board then enters deep sleep for SLEEP_S seconds
# before waking up and repeating the cycle.
#
# Pin assignments (SOIL_ADC_PIN, BATTERY_ADC_PIN, SENSOR_POWER_PIN)
# are configured in config.py using board.* pin names.

import time
import board
import digitalio
import analogio
import microcontroller
import alarm
import _bleio
import aesio

from config import *

ADC_SAMPLES  = 10
ADC_DELAY_S  = 0.01

# Battery voltage measurement using an external resistor divider.

ADC_REF_V             = 3.6     # nRF52840 ADC uses a 3.6V internal reference by default
                                # (0.6V bandgap, 1/6 gain → full scale = 3.6V). If readings
                                # still seem off after recalibrating BATTERY_DIVIDER_RATIO,
                                # verify against a multimeter and adjust this value.
ADC_MAX_RAW           = 65535   # 16-bit ADC

def _aes_ccm_encrypt(key, nonce, plaintext):
    """
    AES-128-CCM encryption (M=4 byte tag, L=2 byte length field, no AAD).
    This is what BTHome v2 specifies for encrypted advertisements.

    Returns ciphertext + 4-byte MIC (len = len(plaintext) + 4).

    Parameters
    ----------
    key       : 16 bytes  – the BTHome binding key
    nonce     : 13 bytes  – MAC(6) + UUID(2) + device_info(1) + counter(4)
    plaintext : bytes     – the raw BTHome object data to encrypt
    """
    def xor16(a, b):
        return bytes(x ^ y for x, y in zip(a, b))

    def aes_ecb(block):
        out = bytearray(16)
        aesio.AES(bytearray(key), aesio.MODE_ECB).encrypt_into(bytearray(block), out)
        return bytes(out)

    msg_len = len(plaintext)
    # Pad to a full block boundary for CBC-MAC processing
    padded = plaintext + b'\x00' * ((-msg_len) % 16)

    # ── CBC-MAC ─────────────────────────────────────────────────────────────
    # B_0 flags: no Adata → bit6=0, M=4 → bits5-3 = (M-2)/2 = 1 → 0x08,
    #            L=2       → bits2-0 = L-1 = 1                   → 0x01
    #            total = 0x09
    b0  = bytes([0x09]) + nonce + msg_len.to_bytes(2, "big")   # exactly 16 bytes
    mac = aes_ecb(b0)
    for i in range(0, len(padded), 16):
        mac = aes_ecb(xor16(mac, padded[i:i + 16]))

    # ── CTR keystream ────────────────────────────────────────────────────────
    # A_i = flags(0x01=L-1) + nonce + i as 2-byte big-endian
    def ctr_block(i):
        return bytes([0x01]) + nonce + i.to_bytes(2, "big")

    # MIC = first 4 bytes of AES(A_0) XOR CBC-MAC output
    mic = xor16(aes_ecb(ctr_block(0)), mac)[:4]

    # Ciphertext: XOR each plaintext block with AES(A_1), AES(A_2), …
    ciphertext = bytearray()
    for i, off in enumerate(range(0, len(padded), 16), start=1):
        ks = aes_ecb(ctr_block(i))
        ciphertext.extend(xor16(ks, padded[off:off + 16]))

    return bytes(ciphertext[:msg_len]) + bytes(mic)


class BTHomeSoilSensor:
    def __init__(self):
        self._soil_adc = analogio.AnalogIn(SOIL_ADC_PIN)
        self._batt_adc = analogio.AnalogIn(BATTERY_ADC_PIN)

    # ── Sensors (read once per wake) ──────────────────────────────

    def read_humidity(self):
        readings = []
        for _ in range(ADC_SAMPLES):
            readings.append(self._soil_adc.value)
            time.sleep(ADC_DELAY_S)
        readings.sort()
        trimmed = readings[1:-1]
        raw = sum(trimmed) // len(trimmed)
        print(f"Moisture raw ADC: {raw}")
        raw = max(WET_VAL, min(DRY_VAL, raw))
        humidity = (DRY_VAL - raw) / (DRY_VAL - WET_VAL) * 100.0
        humidity = humidity * HUMIDITY_SCALE + HUMIDITY_OFFSET  # ← calibration
        humidity = max(0.0, min(100.0, humidity))               # ← clamp to valid range
        return round(humidity, 1)

    def read_temperature(self):
        return round(microcontroller.cpu.temperature, 1)

    def read_battery_voltage(self):
        raw   = self._batt_adc.value
        v_adc = (raw / ADC_MAX_RAW) * ADC_REF_V
        v_bat = v_adc * BATTERY_DIVIDER_RATIO
        v_bat = v_bat * BATTERY_SCALE + BATTERY_OFFSET   # ← apply fine-tune corrections
        print("Battery raw ADC: {}  (v_adc={:.3f}V before divider ratio)".format(raw, v_adc))
        return round(max(2.8, min(10, v_bat)), 3)

    def deinit(self):
        self._soil_adc.deinit()
        self._batt_adc.deinit()

    # ── BTHome v2 BLE advertisement ───────────────────────────────────

    @staticmethod
    def _build_obj_bytes(humidity, temperature, battery_v):
        """
        Build the raw BTHome v2 object data (13 bytes).
        These are either placed directly in the payload (unencrypted)
        or passed to _aes_ccm_encrypt (encrypted).

        Object IDs used (must be in ascending order per BTHome spec):
          0x02  Temperature   int16  signed    factor 0.01   → °C
          0x03  Humidity      uint16 unsigned  factor 0.01   → %
          0x0C  Voltage       uint16 unsigned  factor 0.001  → V
          0x15  Battery       uint8  binary    0=OK 1=Low
          0x20  Moisture      uint8  binary    0=Dry 1=Wet
        """
        obj = bytearray()
        obj.append(0x02)
        obj.extend(int(round(temperature * 100)).to_bytes(2, "little", signed=True))
        obj.append(0x03)
        obj.extend(int(round(humidity * 100)).to_bytes(2, "little"))
        obj.append(0x0C)
        obj.extend(int(round(battery_v * 1000)).to_bytes(2, "little"))
        obj.append(0x15)
        obj.append(0x01 if battery_v < LOW_BATTERY_THRESHOLD else 0x00)
        obj.append(0x20)
        obj.append(0x00 if humidity < LOW_MOISTURE_THRESHOLD else 0x01)
        return bytes(obj)

    def _build_adv_data(self, humidity, temperature, battery_v, counter):
        obj     = self._build_obj_bytes(humidity, temperature, battery_v)
        payload = bytearray(b'\x02\x01\x06')   # BLE flags

        if not ENCRYPT:
            # Unencrypted — device_info=0x40
            # Service data length = type(1)+UUID(2)+device_info(1)+obj(13) = 17 = 0x11
            payload.extend(b'\x11\x16\xD2\xFC\x40')
            payload.extend(obj)
        else:
            # Encrypted — device_info=0x41
            # Nonce (13 B) = MAC(6) + UUID(2: D2 FC) + device_info(1: 41) + counter(4 LE)
            device_info = 0x41
            # address_bytes is LSB-first (wire order); BTHome/HA constructs
            # the nonce using the address MSB-first (as displayed, e.g. C9:E2:…).
            mac_bytes   = bytes(reversed(_bleio.adapter.address.address_bytes))
            nonce       = (mac_bytes
                           + bytes([0xD2, 0xFC, device_info])
                           + counter.to_bytes(4, "little"))
            encrypted   = _aes_ccm_encrypt(ENCRYPTION_KEY, nonce, obj)
            ciphertext  = encrypted[:-4]
            mic         = encrypted[-4:]
            # Service data length = type(1)+UUID(2)+device_info(1)+cipher(13)+counter(4)+MIC(4) = 25 = 0x19
            payload.extend(b'\x19\x16\xD2\xFC')
            payload.append(device_info)
            payload.extend(ciphertext)
            payload.extend(counter.to_bytes(4, "little"))
            payload.extend(mic)

        return bytes(payload)

    @staticmethod
    def _build_resp_data():
        name = DEVICE_NAME.encode("ascii")
        resp = bytearray()
        resp.append(len(name) + 1)
        resp.append(0x09)
        resp.extend(name)
        return bytes(resp)

    def advertise(self, humidity, temperature, battery_v, counter):
        adv_data  = self._build_adv_data(humidity, temperature, battery_v, counter)
        resp_data = self._build_resp_data()
        _bleio.adapter.start_advertising(
            adv_data,
            scan_response=resp_data,
            connectable=False,
        )

    def stop(self):
        _bleio.adapter.stop_advertising()



# ── Main ──────────────────────────────────────────────────────────

def main():
    from microcontroller import nvm

    sensor_power = digitalio.DigitalInOut(SENSOR_POWER_PIN)
    sensor_power.direction = digitalio.Direction.OUTPUT
    sensor_power.value = SENSOR_POWER_OFF_VALUE

    # Counter persisted in NVM (first 4 bytes)
    try:
        adv_counter = int.from_bytes(nvm[0:4], "little")
    except Exception:
        adv_counter = 0

    # Power the soil sensor from the GPIO.
    # The sensor is energized only during the measurement cycle to minimize
    # current consumption while the board is in deep sleep.
    sensor_power.value = SENSOR_POWER_ON_VALUE
    time.sleep(0.5)

    device = BTHomeSoilSensor()

    humidity = device.read_humidity()
    temperature = device.read_temperature()
    battery_v = device.read_battery_voltage()

    # Release ADC peripherals before starting BLE advertising.
    device.deinit()

    print("Moisture: {}%  Temp: {}C  Battery: {}V".format(
        humidity, temperature, battery_v))

    device.advertise(humidity, temperature, battery_v, adv_counter)

    time.sleep(ADV_DURATION_S)

    device.stop()

    adv_counter = (adv_counter + 1) & 0xFFFFFFFF
    try:
        nvm[0:4] = adv_counter.to_bytes(4, "little")
    except Exception as e:
        print("NVM write failed:", e)

    sensor_power.value = SENSOR_POWER_OFF_VALUE
    time.sleep(0.1)
    sensor_power.deinit()

    # Put the board into deep sleep until the next measurement cycle.
    print("Deep sleeping {}s...".format(SLEEP_S))

    time_alarm = alarm.time.TimeAlarm(
        monotonic_time=time.monotonic() + SLEEP_S
    )

    alarm.exit_and_deep_sleep_until_alarms(time_alarm)


main()
