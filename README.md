**nRF52840 BTHome Soil Moisture Sensor beta version!**  

A low-power CircuitPython firmware for the SuperMini / ProMicro nRF52840 that periodically measures:  
    • 🌱 Soil moisture   
    • 🔋 Battery voltage   
    • 🌡 MCU temperature   
and broadcasts the values as a BTHome v2 Bluetooth Low Energy advertisement.  
https://bthome.io/  
https://www.home-assistant.io/integrations/bthome/  

The board spends almost all of its time in deep sleep, making it suitable for battery-powered plant sensors.  
The firmware works with Home Assistant through an ESPHome Bluetooth Proxy or any BTHome-compatible receiver.  
The board is designed to automatically charge a 3.7V lithium battery, when the USB is connected.

**Features**  
    • BTHome v2 BLE advertisements   
    • Optional AES-CCM encryption   
    • Deep sleep between measurements   
    • GPIO-powered soil sensor to minimize standby current   
    • Battery voltage measurement using an external resistor divider   
    • Configurable measurement interval   
    • Fully configurable through config.py   
    • No code changes required for normal configuration   

**Hardware**  
Designed for inexpensive nRF52840 SuperMini / ProMicro boards running CircuitPython.  
Required components:  
    • nRF52840 SuperMini / ProMicro
    [Aliexpress](https://it.aliexpress.com/item/1005007078900079.html?spm=a2g0o.order_list.order_list_main.10.580d1802PlGF7N&gatewayAdapt=glo2ita)   
    ![Boards image](Images/Boards.png)  
    • Capacitive soil moisture sensor
    [Aliexpress](https://it.aliexpress.com/item/1005007353966390.html?spm=a2g0o.order_list.order_list_main.26.49861802s5ppiQ&gatewayAdapt=glo2ita)   
    • External battery   
    • Two resistors for the battery divider (recommended 1MΩ + 1MΩ 1/4W)  
    • Optional 3D printed shell  
    [Cults3D with LIPO](https://cults3d.com/en/3d-model/gadget/nrf52840-bthome-soil-moisture-sensor-shell-for-lipo-battery)  
    ![Lipo sensor image](Images/Lipo_sensor_image.png)

Example wiring:  

| Signal                   | Board              |  
| ------------------------ | ------------------ |  
| Soil sensor output       | `SOIL_ADC_PIN`     |  
| Soil sensor VCC          | `SENSOR_POWER_PIN` |  
| Soil sensor GND          | GND                |  
| Battery divider midpoint | `BATTERY_ADC_PIN`  |  

Battery divider:  

Battery+  
   |  
  R1 (1MΩ)  
   |  
BATTERY_ADC_PIN  
   |  
  R2 (1MΩ)  
   |  
  GND  

The onboard BAT_VOLT input is intentionally not used because on these clone boards it often follows VDD rather than the actual battery voltage when running from battery power.  

![Board image 1](Images/Board_1.png) ![Board image 2](Images/Board_2.png)

**Installation**  
Copy the following files onto the CIRCUITPY drive:   
code.py  
config.py   
If encryption is desired, you can also copy:  
Key_generator.py   
Reset the board after copying the files.  

**Configuration**  
All user settings are contained in config.py.  
Typical settings include:  

    • device name   
    • sleep interval   
    • advertising duration   
    • GPIO pin assignments   
    • battery calibration   
    • soil moisture calibration   
    • low battery threshold   
    • low moisture threshold   
    • BTHome encryption   

Normally there is no need to modify code.py.  

**BTHome Encryption**  
Encryption is optional but recommended.  
Enable it by setting: ENCRYPT = True  

Generate a random 16-byte key with:  
import os  
print(os.urandom(16).hex())  

or simply run: Key_generator.py  

Or use an on line service

Copy the generated key into: ENCRYPTION_KEY = bytes.fromhex("...")  

The same key must be entered as the Bindkey when adding the device to Home Assistant.  

![Immagine 3](Images/Key.png)

**Battery Calibration**  
The firmware measures battery voltage through an external resistor divider.   

Recommended divider:  
    • R1 = 1 MΩ   
    • R2 = 1 MΩ   

Configure:  
BATTERY_DIVIDER_RATIO = 2  
If necessary, fine-tune: BATTERY_SCALE and BATTERY_OFFSET, using a multimeter.  
Calibration should always be performed while powered from the battery (USB disconnected).  

**Soil Moisture Calibration**  
First determine the raw ADC values.  
Measure:  
    • probe completely dry   
    • probe fully submerged in water   
Then set:  
DRY_VAL = ...  
WET_VAL = ...  
If small corrections are still required, use: HUMIDITY_SCALE and HUMIDITY_OFFSET  

**GPIO Powered Sensor**  
The soil sensor is powered from a GPIO pin instead of permanently from the battery.  
During each measurement cycle the firmware:  
    1. powers the sensor   
    2. waits for stabilization   
    3. performs the ADC measurements   
    4. powers the sensor off   
    5. enters deep sleep   
This significantly reduces standby current.  

**Home Assistant**  
The firmware broadcasts standard BTHome v2 advertisements containing:  
    • Soil moisture (%)   
    • Battery voltage (V)   
    • MCU temperature (°C)   
    • Low moisture binary sensor   
    • Low battery binary sensor   
Encrypted advertisements are fully compatible with Home Assistant by providing the configured Bindkey.  

**Power Consumption**  
Current consumption depends on:  
    • sleep interval   
    • advertising duration   
    • board revision   
    • soil sensor used   
Increasing SLEEP_S can greatly extend battery life.  

This is the consumption with a 250mAh battery and a sleep time of 60 sec:  
![alt text](Images/Consuption_time_250mah_60sec.png)

**Included Files**  
| File               | Description                                      |  
| ------------------ | ------------------------------------------------ |  
| `code.py`          | Main firmware                                    |  
| `config.py`        | User configuration                               |  
| `Key_generator.py` | Generates a random 16-byte BTHome encryption key |  
 

License  
MIT License  
