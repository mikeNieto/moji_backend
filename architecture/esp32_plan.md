# Plan de Implementación ESP32 — Robot Moji

**Versión:** 1.1  
**Fecha:** Marzo 2026  
**Microcontrolador:** ESP32-S3 WROOM (Freenove FNK0082)  
**Framework:** Arduino / PlatformIO

---

## Tabla de Contenidos

1. [Lista Completa de Componentes](#1-lista-completa-de-componentes)
2. [Configuración Inicial del Proyecto](#2-configuración-inicial-del-proyecto)
3. [Etapa 1 — Motores y Batería](#3-etapa-1--motores-y-batería)
4. [Etapa 2 — Sensores de Distancia HC-SR04](#4-etapa-2--sensores-de-distancia-hc-sr04)
5. [Etapa 3 — LED RGB](#5-etapa-3--led-rgb)
6. [Etapa 4 — BLE (Bluetooth Low Energy)](#6-etapa-4--ble-bluetooth-low-energy)
7. [Etapa 5 — Sensores Cliff VL53L0X](#7-etapa-5--sensores-cliff-vl53l0x)
8. [Referencia Rápida de Pines](#8-referencia-rápida-de-pines)

---

## 1. Lista Completa de Componentes

### Microcontrolador

| Componente | Especificación | Cantidad |
|------------|---------------|----------|
| ESP32-S3 WROOM | Freenove FNK0082 (N8R8 o N16R8) | 1 |

### Sistema de Movimiento

| Componente | Especificación | Cantidad |
|------------|---------------|----------|
| Driver de motores | L298N Dual H-Bridge | 1 |
| Motor DC | Gear Motor TT Yellow for Arduino Robotic Car, 5V | 2 |
| Rueda de apoyo | Rueda loca / caster | 1 |

### Sensores

| Componente | Especificación | Cantidad |
|------------|---------------|----------|
| Sensor ultrasónico | HC-SR04 (5V, detección de obstáculos) | 2 |
| Sensor de corriente/voltaje | INA219 (I²C, high-side, batería) | 1 |
| Sensor ToF | VL53L0X (I²C, detección de cliff/caídas) | 3 |

### Indicación Visual

| Componente | Especificación | Cantidad |
|------------|---------------|----------|
| LED RGB | 4 patas, ánodo común, 256 valores por canal | 1 |

### Alimentación

| Componente | Especificación | Cantidad |
|------------|---------------|----------|
| Celdas de batería | 18650 Li-ion (mín. 3000 mAh recomendado) | 6 |
| BMS | 2S 20A para Li-ion 18650 | 1 |
| Buck Converter | 6–8.4V → 5V (para motores L298N) | 1 |
| Buck Converter | 6–8.4V → 5V (para ESP32 + sensores) | 1 |
| Interruptor | Power switch | 1 |

### Resistencias y Pasivos

| Componente | Valor | Cantidad | Uso |
|------------|-------|----------|-----|
| Resistencia | 2 kΩ | 2 | Divisor HC-SR04 Echo (R1, una por sensor) |
| Resistencia | 3 kΩ | 2 | Divisor HC-SR04 Echo (R2, una por sensor) |
| Resistencia | 220 Ω | 3 | Protección LED RGB (una por canal R, G, B) |

> **Nota**: El divisor 82 kΩ / 47 kΩ deja de ser necesario porque en esta versión del plan la batería se monitorea con un **INA219** por I²C.

### Herramientas y Misceláneos

| Ítem | Uso |
|------|-----|
| Protoboard y cables dupont | Prototipado |
| Multímetro | Verificación de voltajes |
| Cable USB-C | Programación / Serial Monitor |
| Teléfono Android con BLE | Pruebas de conectividad |
| App BLE genérica (ej. nRF Connect) | Pruebas de BLE antes de la app Android |

---

## 2. Configuración Inicial del Proyecto

### 2.1 Instalar PlatformIO

PlatformIO se usa como framework de desarrollo en lugar del Arduino IDE. Ofrece gestión de librerías, compilación y monitor serial integrados.

1. Instalar [VS Code](https://code.visualstudio.com/) si no está instalado.
2. Instalar la extensión **PlatformIO IDE** desde el marketplace de VS Code.
3. Reiniciar VS Code.

### 2.2 Crear el proyecto

Desde la pantalla de inicio de PlatformIO:

1. Seleccionar **"New Project"**.
2. Nombre del proyecto: `moji_robot`.
3. Board: buscar `Freenove ESP32-S3 WROOM` o seleccionar `Espressif ESP32-S3-DevKitC-1`.
4. Framework: `Arduino`.
5. Confirmar.

### 2.3 Estructura del proyecto

```
moji_robot/
├── platformio.ini
├── include/
│   ├── config.h
│   ├── bluetooth/
│   │   ├── BLEServer.h
│   │   └── HeartbeatMonitor.h
│   ├── motors/
│   │   └── MotorController.h
│   ├── sensors/
│   │   ├── DistanceSensor.h
│   │   ├── CliffSensor.h
│   │   └── BatteryMonitor.h
│   ├── leds/
│   │   └── LEDController.h
│   ├── safety/
│   │   └── SafetyMonitor.h
│   └── utils/
│       └── Logger.h
├── src/
│   ├── main.cpp
│   ├── bluetooth/
│   │   ├── BLEServer.cpp
│   │   └── HeartbeatMonitor.cpp
│   ├── motors/
│   │   └── MotorController.cpp
│   ├── sensors/
│   │   ├── DistanceSensor.cpp
│   │   ├── CliffSensor.cpp
│   │   └── BatteryMonitor.cpp
│   ├── leds/
│   │   └── LEDController.cpp
│   ├── safety/
│   │   └── SafetyMonitor.cpp
│   └── utils/
│       └── Logger.cpp
└── lib/
```

> **Nota**: En PlatformIO los headers pueden compilarse aunque estén dentro de `src/`, pero siguiendo la convención del proyecto y el `include/README`, en este plan todos los archivos `.h` viven en `include/` y los `.cpp` en `src/`.

### 2.4 Configurar `platformio.ini`

```ini
[env:freenove_esp32_s3_wroom]
platform = espressif32
board = freenove_esp32_s3_wroom
framework = arduino
monitor_speed = 115200
upload_speed = 921600

lib_deps =
  bblanchon/ArduinoJson@^6.21.0
  adafruit/Adafruit INA219@^1.2.3
  pololu/VL53L0X@^1.3.1
```

> **Nota**: La librería ESP32 BLE ya viene incluida en el core de Arduino para ESP32.
> No es necesario agregarla como dependencia externa.
>
> Si en tu instalación no aparece la placa Freenove y usas `esp32-s3-devkitc-1`, cambia únicamente el valor de `board`.

### 2.5 Crear `include/config.h`

Este archivo centraliza todos los pines y constantes del proyecto. Se irá completando a lo largo de las etapas.

```cpp
// include/config.h
#pragma once

// ─── MOTORES ────────────────────────────────────────────────────────────────
#define MOTOR_IN1  41    // Motor Izquierdo → Adelante
#define MOTOR_IN2  42    // Motor Izquierdo → Atrás
#define MOTOR_IN3  47    // Motor Derecho  → Adelante
#define MOTOR_IN4  48    // Motor Derecho  → Atrás
#define MOTOR_ENA   1    // Enable Motor Izquierdo (PWM)
#define MOTOR_ENB   2    // Enable Motor Derecho   (PWM)

#define MOTOR_PWM_FREQ       1000   // Hz
#define MOTOR_PWM_RESOLUTION    8   // bits (0–255)
#define MOTOR_RAMP_STEP        10   // % por ciclo de rampa
#define MOTOR_RAMP_DELAY_MS    50   // ms entre pasos de rampa
#define MOTION_FIXED_SPEED    200   // PWM fijo usado por comandos BLE de movimiento
#define MOTION_MS_PER_10_CM_AT_SPEED_200 350  // TODO: calibrar ms que tarda en avanzar 10 cm a speed 200
#define MOTION_MS_PER_90_DEG_AT_SPEED_200 420 // TODO: calibrar ms que tarda en girar 90 grados a speed 200

// ─── SENSORES DISTANCIA HC-SR04 ─────────────────────────────────────────────
#define DIST_TRIG_FRONT  4
#define DIST_ECHO_FRONT  5
#define DIST_TRIG_REAR   6
#define DIST_ECHO_REAR   7

#define DISTANCE_THRESHOLD_CM   10  // Detener si obstáculo < 10 cm
#define ULTRASONIC_TIMEOUT_US 30000 // Timeout por lectura

// ─── LED RGB (ánodo común) ───────────────────────────────────────────────────
#define LED_PIN_R  38
#define LED_PIN_G  39
#define LED_PIN_B  40

#define LED_PWM_FREQ       1000  // Hz
#define LED_PWM_CHANNEL_R     0
#define LED_PWM_CHANNEL_G     1
#define LED_PWM_CHANNEL_B     2
#define LED_PWM_RESOLUTION    8  // 8 bits → 0–255

// ─── BLUETOOTH ──────────────────────────────────────────────────────────────
#define BLE_DEVICE_NAME        "RobotESP32"
#define BLE_MTU_SIZE            512
#define HEARTBEAT_TIMEOUT_MS   3000  // 3s sin heartbeat → BRAIN_OFFLINE
#define HEARTBEAT_INTERVAL_MS  1000  // Se espera un heartbeat cada 1s

// ─── BUS I²C COMPARTIDO (INA219 + VL53L0X) ─────────────────────────────────
#define I2C_SDA           8
#define I2C_SCL           9
#define INA219_I2C_ADDRESS 0x40

// ─── SENSORES CLIFF VL53L0X (I²C) ───────────────────────────────────────────
#define XSHUT_CLIFF_FL   11   // Front-Left
#define XSHUT_CLIFF_FR   12   // Front-Right
#define XSHUT_CLIFF_RR   13   // Rear

#define CLIFF_THRESHOLD_MM      80  // < 80mm al suelo = vacío (precipicio)
#define CLIFF_CHECK_INTERVAL_MS 100

// ─── BATERÍA ─────────────────────────────────────────────────────────────────
#define BATTERY_VOLTAGE_MIN   6.0f  // V (3.0V × 2S)
#define BATTERY_VOLTAGE_MAX   8.4f  // V (4.2V × 2S)
#define LOW_BATTERY_THRESHOLD  10   // %

// ─── TELEMETRÍA ──────────────────────────────────────────────────────────────
#define TELEMETRY_INTERVAL_MS 1000
```

### 2.6 Verificar que el ESP32-S3 se detecta

1. Conectar el ESP32-S3 por USB-C.
2. En PlatformIO, abrir un terminal y ejecutar:
   ```
   pio device list
   ```
3. Debe aparecer un puerto `/dev/ttyUSB0` o `/dev/ttyACM0` (Linux) o `COMx` (Windows).
4. Si no aparece, instalar drivers CH340/CP2102 según el chip USB que traiga la placa.

### 2.7 Test inicial — Blink LED de la placa

Antes de conectar cualquier componente externo, verificar que la cadena de compilación y upload funciona:

```cpp
// src/main.cpp — test de compilación y upload básico
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  Serial.println("=== Moji ESP32 Boot OK ===");
}

void loop() {
  Serial.println("tick");
  delay(1000);
}
```

**Verificación**: Abrir el Serial Monitor de PlatformIO (115200 baud). Cada segundo debe aparecer `tick`. Si funciona, el toolchain está correctamente configurado.

---

## 3. Etapa 1 — Motores y Batería

### Objetivo
Hacer que el robot se mueva hacia adelante, hacia atrás y gire. Leer **voltaje, corriente y potencia** de la batería con un **INA219**. Al final de esta etapa el robot se podrá controlar desde el Serial Monitor y reportará telemetría básica de energía.

### 3.1 Alimentación y batería

#### Configuración de la batería

La batería es un pack de **6 celdas 18650 en configuración 2S3P**:
- **2S** = 2 celdas en serie → 7.4V nominal (8.4V máximo)
- **3P** = 3 grupos en paralelo → mayor capacidad (ej. 9000 mAh con celdas de 3000 mAh)
- El **BMS 2S 20A** protege contra sobrecarga, sobredescarga y cortocircuito

```
[Batería 2S3P]──────[BMS 2S 20A]──────[Interruptor]──────[INA219 VIN+]
                                                          [INA219 VIN-]──────┬──[Buck #1 5V]──[L298N VIN / Motores]
                                                                              │
                                                                              └──[Buck #2 5V]──[ESP32 VIN / Sensores]
```

> **Importante**: Nunca conectar la batería directamente al ESP32. Usar siempre Buck Converter #2 para bajar a 5V antes del pin VIN. El regulador interno del ESP32 convierte 5V → 3.3V.

#### Inserción del INA219 en la línea principal de batería

El **INA219** permite medir en **high-side** la batería completa del robot sin mover la referencia de tierra. La colocación correcta es entre la salida principal del pack y las dos ramas que alimentan los buck converters.

```
[Batería 2S3P]──────[BMS 2S 20A]──────[Interruptor]──────[INA219 VIN+]
                                                          [INA219 VIN-]──────┬──[Buck #1 5V]──[L298N VIN / Motores]
                                                                              │
                                                                              └──[Buck #2 5V]──[ESP32 VIN / Sensores]
```

> **Importante**: `VIN+` del INA219 va hacia el lado de la batería y `VIN-` hacia el lado de la carga. Si se invierten, las lecturas de corriente quedan negativas o incorrectas.

#### Conexión INA219 ↔ ESP32-S3

El INA219 comparte el mismo bus I²C que más adelante usarán los VL53L0X. No requiere GPIOs nuevos.

> **Nota de placa**: En la **Freenove ESP32-S3 WROOM** usada por este proyecto no conviene asumir el clásico par `GPIO 21/22` de otras ESP32. En PlatformIO con el board `freenove_esp32_s3_wroom` y el core Arduino `esp32s3`, el bus I²C de este proyecto se fija en **GPIO 8 (SDA)** y **GPIO 9 (SCL)**.

```
INA219             ESP32-S3 / Alimentación
──────             ───────────────────────
VCC        ──────  3.3V del ESP32
GND        ──────  GND común
SDA        ──────  GPIO 8
SCL        ──────  GPIO 9
VIN+       ──────  Positivo principal desde interruptor / salida del BMS
VIN-       ──────  Nodo positivo que alimenta Buck #1 y Buck #2
```

> **Crítico**: Alimenta el INA219 con **3.3V**, no con 5V. Muchos módulos traen pull-ups I²C a `VCC`; si lo alimentas a 5V, `SDA` y `SCL` también subirán a 5V y eso no es seguro para el ESP32-S3.

#### Señales recibidas desde el INA219

Por I²C, el ESP32 recibe del INA219 estas magnitudes:

- `bus_voltage`: voltaje en el lado de carga
- `shunt_voltage`: caída en la resistencia shunt interna
- `load_voltage`: estimación del voltaje real del pack hacia la carga (`bus + shunt`)
- `current_mA`: corriente instantánea consumida por el robot
- `power_mW`: potencia instantánea

Dirección I²C por defecto del INA219: `0x40`.

> **Compatibilidad con el resto del plan**: el INA219 usa `0x40`, mientras que los tres VL53L0X terminan en `0x30`, `0x31` y `0x32`. No hay conflicto de direcciones en el mismo bus.

### 3.2 Conexión del L298N y motores

El L298N es un driver de doble puente H que permite controlar 2 motores DC con dirección y velocidad (PWM).

#### Diagrama de conexión L298N ↔ ESP32-S3

```
L298N              ESP32-S3
──────             ────────
IN1       ──────   GPIO 41  (Motor Izq → Adelante)
IN2       ──────   GPIO 42  (Motor Izq → Atrás)
IN3       ──────   GPIO 47  (Motor Der → Adelante)
IN4       ──────   GPIO 48  (Motor Der → Atrás)
ENA       ──────   GPIO 1   (PWM velocidad Motor Izq)
ENB       ──────   GPIO 2   (PWM velocidad Motor Der)
GND       ──────   GND del ESP32
```

```
L298N              Alimentación
──────             ────────────
VIN (12V)  ──────  Buck #1 salida 5V  (positivo)
GND        ──────  Buck #1 GND

L298N              Motores
──────             ──────
OUT1 (+)   ──────  Motor Izquierdo terminal +
OUT2 (-)   ──────  Motor Izquierdo terminal -
OUT3 (+)   ──────  Motor Derecho terminal +
OUT4 (-)   ──────  Motor Derecho terminal -
```

> **Nota**: El L298N tiene un jumper en ENA y ENB. Para control por PWM se **retira el jumper** y se conecta el pin ENA/ENB directamente al GPIO del ESP32.

#### Tabla de lógica de dirección

| Dirección     | IN1 | IN2 | IN3 | IN4 | ENA (PWM) | ENB (PWM) |
|---------------|-----|-----|-----|-----|-----------|-----------|
| Adelante      | H   | L   | H   | L   | speed%    | speed%    |
| Atrás         | L   | H   | L   | H   | speed%    | speed%    |
| Girar Izq     | L   | H   | H   | L   | speed%    | speed%    |
| Girar Der     | H   | L   | L   | H   | speed%    | speed%    |
| Parar (freno) | L   | L   | L   | L   | 0         | 0         |

### 3.3 Código — Etapa 1

#### `include/motors/MotorController.h`

```cpp
#pragma once
#include <Arduino.h>
#include "config.h"

enum class Direction { FORWARD, BACKWARD, LEFT, RIGHT, STOP };

class MotorController {
public:
  void begin();
  void move(Direction dir, uint8_t speed);
  void stop();
  void runFor(Direction dir, uint8_t speed, uint32_t durationMs);

private:
  uint8_t _currentSpeed = 0;
  void applyMotors(bool in1, bool in2, bool in3, bool in4, uint8_t speed);
  uint8_t rampStep(uint8_t target);
};
```

#### `src/motors/MotorController.cpp`

```cpp
#include "motors/MotorController.h"

void MotorController::begin() {
  // Pines de dirección
  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);
  pinMode(MOTOR_IN3, OUTPUT);
  pinMode(MOTOR_IN4, OUTPUT);

  // PWM — API ledcAttachChannel (ESP32 Arduino 2.x)
  ledcAttachChannel(MOTOR_ENA, MOTOR_PWM_FREQ, MOTOR_PWM_RESOLUTION, 3);
  ledcAttachChannel(MOTOR_ENB, MOTOR_PWM_FREQ, MOTOR_PWM_RESOLUTION, 4);

  stop();
  Serial.println("[MOTOR] MotorController iniciado");
}

void MotorController::applyMotors(bool in1, bool in2, bool in3, bool in4, uint8_t speed) {
  digitalWrite(MOTOR_IN1, in1);
  digitalWrite(MOTOR_IN2, in2);
  digitalWrite(MOTOR_IN3, in3);
  digitalWrite(MOTOR_IN4, in4);
  ledcWrite(MOTOR_ENA, speed);
  ledcWrite(MOTOR_ENB, speed);
  _currentSpeed = speed;
}

void MotorController::move(Direction dir, uint8_t speed) {
  switch (dir) {
    case Direction::FORWARD:  applyMotors(1,0,1,0, speed); break;
    case Direction::BACKWARD: applyMotors(0,1,0,1, speed); break;
    case Direction::LEFT:     applyMotors(0,1,1,0, speed); break;
    case Direction::RIGHT:    applyMotors(1,0,0,1, speed); break;
    case Direction::STOP:     stop(); break;
  }
}

void MotorController::stop() {
  applyMotors(0,0,0,0, 0);
  Serial.println("[MOTOR] STOP");
}

void MotorController::runFor(Direction dir, uint8_t speed, uint32_t durationMs) {
  move(dir, speed);
  delay(durationMs);
  stop();
}
```

#### `include/sensors/BatteryMonitor.h`

```cpp
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include "config.h"

struct BatteryReading {
  float busVoltage = 0.0f;
  float shuntVoltage = 0.0f;
  float loadVoltage = 0.0f;
  float currentmA = 0.0f;
  float powermW = 0.0f;
  uint8_t percentage = 0;
  bool sensorOk = false;
};

class BatteryMonitor {
public:
  bool begin();
  BatteryReading read();
  float readVoltage();
  float readCurrentmA();
  float readPowermW();
  uint8_t readPercentage();
  bool isLow();

private:
  Adafruit_INA219 _ina219 = Adafruit_INA219(INA219_I2C_ADDRESS);
  bool _connected = false;

  uint8_t percentageFromVoltage(float voltage) const;
};
```

#### `src/sensors/BatteryMonitor.cpp`

```cpp
#include "sensors/BatteryMonitor.h"

bool BatteryMonitor::begin() {
  Wire.begin(I2C_SDA, I2C_SCL);

  _connected = _ina219.begin();
  if (!_connected) {
    Serial.println("[BATTERY] ERROR: INA219 no detectado en 0x40");
    return false;
  }

  _ina219.setCalibration_32V_2A();
  Serial.println("[BATTERY] INA219 iniciado @ 0x40");
  return true;
}

uint8_t BatteryMonitor::percentageFromVoltage(float voltage) const {
  if (voltage >= BATTERY_VOLTAGE_MAX) return 100;
  if (voltage <= BATTERY_VOLTAGE_MIN) return 0;

  return (uint8_t)(100.0f * (voltage - BATTERY_VOLTAGE_MIN) /
                             (BATTERY_VOLTAGE_MAX - BATTERY_VOLTAGE_MIN));
}

BatteryReading BatteryMonitor::read() {
  BatteryReading reading;
  reading.sensorOk = _connected;
  if (!_connected) return reading;

  reading.busVoltage   = _ina219.getBusVoltage_V();
  reading.shuntVoltage = _ina219.getShuntVoltage_mV();
  reading.loadVoltage  = reading.busVoltage + (reading.shuntVoltage / 1000.0f);
  reading.currentmA    = _ina219.getCurrent_mA();
  reading.powermW      = _ina219.getPower_mW();
  reading.percentage   = percentageFromVoltage(reading.loadVoltage);
  return reading;
}

float BatteryMonitor::readVoltage() {
  return read().loadVoltage;
}

float BatteryMonitor::readCurrentmA() {
  return read().currentmA;
}

float BatteryMonitor::readPowermW() {
  return read().powermW;
}

uint8_t BatteryMonitor::readPercentage() {
  return read().percentage;
}

bool BatteryMonitor::isLow() {
  return readPercentage() < LOW_BATTERY_THRESHOLD;
}
```

#### `src/main.cpp` — Test Etapa 1

```cpp
#include <Arduino.h>
#include "config.h"
#include "motors/MotorController.h"
#include "sensors/BatteryMonitor.h"

MotorController motors;
BatteryMonitor  battery;

void printBattery() {
  BatteryReading reading = battery.read();
  if (!reading.sensorOk) {
    Serial.println("[BATT] ERROR: INA219 no disponible");
    return;
  }

  Serial.printf("[BATT] Bus: %.2f V | Load: %.2f V | Current: %.1f mA | Power: %.1f mW | %d%%\n",
                reading.busVoltage,
                reading.loadVoltage,
                reading.currentmA,
                reading.powermW,
                reading.percentage);
}

void printMenu() {
  Serial.println("\n=== TEST MOTORES Y BATERÍA ===");
  Serial.println("w → Adelante 2s");
  Serial.println("s → Atrás   2s");
  Serial.println("a → Izq     1s");
  Serial.println("d → Der     1s");
  Serial.println("x → STOP");
  Serial.println("b → Leer batería");
  Serial.println("==============================");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("=== MOJI ESP32 — Etapa 1: Motores + Batería ===");
  motors.begin();
  battery.begin();
  printMenu();
}

void loop() {
  // Leer batería cada 5 segundos
  static unsigned long lastBatt = 0;
  if (millis() - lastBatt > 5000) {
    printBattery();
    lastBatt = millis();
  }

  // Control por Serial Monitor
  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'w': Serial.println("→ ADELANTE"); motors.runFor(Direction::FORWARD,  150, 2000); break;
      case 's': Serial.println("→ ATRÁS");   motors.runFor(Direction::BACKWARD, 150, 2000); break;
      case 'a': Serial.println("→ IZQUIERDA"); motors.runFor(Direction::LEFT,   150, 1000); break;
      case 'd': Serial.println("→ DERECHA");  motors.runFor(Direction::RIGHT,   150, 1000); break;
      case 'x': Serial.println("→ STOP");     motors.stop(); break;
      case 'b': printBattery(); break;
      default: break;
    }
    printMenu();
  }
}
```

### 3.4 Prueba de la Etapa 1

**Procedimiento**:

1. Con la batería desconectada, verificar con multímetro que los Buck Converters dan exactamente 5V en su salida antes de conectar cualquier componente.
2. Insertar el INA219 en la línea positiva principal, entre el interruptor y la distribución hacia los dos buck converters.
3. Conectar `VCC` del INA219 a `3.3V`, `GND` a GND, `SDA` a GPIO 8 y `SCL` a GPIO 9.
4. Subir el código al ESP32.
5. Abrir Serial Monitor (115200 baud).
6. Verificar que aparece `[BATTERY] INA219 iniciado @ 0x40`. Si aparece error, revisar alimentación a 3.3V, dirección I²C y cableado `SDA/SCL`.
7. Verificar que cada 5 segundos imprime `Bus`, `Load`, `Current` y `Power`. Comparar `Load` con el multímetro entre el positivo principal y GND.
8. Conectar el L298N y los motores (sin las ruedas si es posible, o elevando el robot).
9. Enviar `w` → los motores deben girar hacia adelante durante 2 segundos y la corriente debe subir respecto al reposo.
10. Enviar `s` → los motores deben girar hacia atrás.
11. Enviar `a` y `d` → el robot debe girar.
12. Enviar `x` → los motores se deben detener inmediatamente.

**Criterios de éxito**:
- ✅ El INA219 responde en `0x40` y el firmware lo inicializa
- ✅ `Load voltage` coincide aproximadamente (±0.1V) con el multímetro
- ✅ La corriente en reposo es baja y aumenta al mover los motores
- ✅ La potencia reportada es coherente con el cambio de carga
- ✅ El robot avanza en línea recta (si no, ajustar velocidades de cada motor)
- ✅ El robot gira en ambas direcciones
- ✅ El comando `x` detiene los motores inmediatamente

**Problemas comunes**:
- *Un motor gira al revés*: intercambiar OUT1/OUT2 de ese motor en el L298N.
- *Los motores no giran aunque el LED del L298N enciende*: verificar que el jumper de ENA/ENB esté **quitado** y que el pin GPIO esté enviando PWM.
- *El INA219 no aparece*: revisar que el módulo esté alimentado con **3.3V** y que `SDA/SCL` estén en GPIO 8/9.
- *Voltaje correcto pero corriente en cero*: verificar que la línea positiva de la batería realmente pase por `VIN+` y `VIN-` del INA219.
- *Corriente negativa*: invertir `VIN+` y `VIN-`.
- *Lectura saturada al arrancar motores*: usar una calibración más alta o considerar un sensor con mayor margen si el robot supera el rango del shunt.

---

## 4. Etapa 2 — Sensores de Distancia HC-SR04

### Objetivo
Detectar obstáculos frontales y traseros. Integrar parada de seguridad automática: si hay un obstáculo a menos de 10 cm en la dirección de movimiento, el robot se detiene solo.

### 4.1 Circuito protector de voltaje para el pin Echo

El HC-SR04 opera a 5V y su pin Echo devuelve una señal de 5V. El GPIO del ESP32-S3 soporta máximo 3.3V. Sin protección el GPIO puede dañarse con el tiempo. Se usa un divisor resistivo para bajar la señal a 3.0V:

```
HC-SR04 Echo (5V)
    │
   2kΩ
    │
    ├─────── GPIO (ESP32)    → V = 5V × 3k/(2k+3k) = 3.0V  ✅
    │
   3kΩ
    │
   GND
```

Materiales por sensor: 1× resistencia 2 kΩ + 1× resistencia 3 kΩ.  
Para 2 sensores: 2× 2 kΩ + 2× 3 kΩ.

### 4.2 Conexión HC-SR04 ↔ ESP32-S3

#### Sensor FRONTAL

```
HC-SR04 Frontal    ESP32-S3
──────────────     ────────
VCC       ──────   5V  (del Buck #2)
GND       ──────   GND
Trig      ──────   GPIO 4
Echo      ──────   [↑ divisor resistivo 2kΩ+3kΩ] ──── GPIO 5
```

#### Sensor TRASERO

```
HC-SR04 Trasero    ESP32-S3
──────────────     ────────
VCC       ──────   5V  (del Buck #2)
GND       ──────   GND
Trig      ──────   GPIO 6
Echo      ──────   [↑ divisor resistivo 2kΩ+3kΩ] ──── GPIO 7
```

### 4.3 Código — Etapa 2

#### `include/sensors/DistanceSensor.h`

```cpp
#pragma once
#include <Arduino.h>
#include "config.h"

class DistanceSensor {
public:
  DistanceSensor(uint8_t trigPin, uint8_t echoPin, const char* name);
  void begin();
  float readCm();       // Distancia en centímetros (-1 si timeout)
  bool isObstacle();    // true si distancia < DISTANCE_THRESHOLD_CM

private:
  uint8_t  _trig, _echo;
  const char* _name;
};
```

#### `src/sensors/DistanceSensor.cpp`

```cpp
#include "sensors/DistanceSensor.h"

DistanceSensor::DistanceSensor(uint8_t trigPin, uint8_t echoPin, const char* name)
  : _trig(trigPin), _echo(echoPin), _name(name) {}

void DistanceSensor::begin() {
  pinMode(_trig, OUTPUT);
  pinMode(_echo, INPUT);
  digitalWrite(_trig, LOW);
  Serial.printf("[DIST] %s iniciado (Trig=%d Echo=%d)\n", _name, _trig, _echo);
}

float DistanceSensor::readCm() {
  // Pulso de 10µs en Trig
  digitalWrite(_trig, LOW);  delayMicroseconds(2);
  digitalWrite(_trig, HIGH); delayMicroseconds(10);
  digitalWrite(_trig, LOW);

  long duration = pulseIn(_echo, HIGH, ULTRASONIC_TIMEOUT_US);
  if (duration == 0) return -1.0f;  // Timeout

  return duration * 0.0343f / 2.0f;  // cm (sonido a 343 m/s)
}

bool DistanceSensor::isObstacle() {
  float d = readCm();
  if (d < 0) return false;  // Timeout → asumir libre
  return d < DISTANCE_THRESHOLD_CM;
}
```

#### `include/safety/SafetyMonitor.h`

```cpp
#pragma once
#include <Arduino.h>
#include "sensors/DistanceSensor.h"
#include "motors/MotorController.h"
#include "config.h"

class SafetyMonitor {
public:
  SafetyMonitor(DistanceSensor& front, DistanceSensor& rear, MotorController& motors);
  // Llamar periódicamente desde el loop. Devuelve true si hay emergencia.
  bool check(Direction currentDir);

private:
  DistanceSensor& _front;
  DistanceSensor& _rear;
  MotorController& _motors;
};
```

#### `src/safety/SafetyMonitor.cpp`

```cpp
#include "safety/SafetyMonitor.h"

SafetyMonitor::SafetyMonitor(DistanceSensor& front, DistanceSensor& rear, MotorController& motors)
  : _front(front), _rear(rear), _motors(motors) {}

bool SafetyMonitor::check(Direction currentDir) {
  // Solo verificar en la dirección de movimiento activa
  if (currentDir == Direction::FORWARD  && _front.isObstacle()) {
    Serial.println("[SAFETY] Obstáculo FRONTAL < 10cm → STOP");
    _motors.stop();
    return true;
  }
  if (currentDir == Direction::BACKWARD && _rear.isObstacle()) {
    Serial.println("[SAFETY] Obstáculo TRASERO < 10cm → STOP");
    _motors.stop();
    return true;
  }
  return false;
}
```

#### `src/main.cpp` — Test Etapa 2

```cpp
#include <Arduino.h>
#include "config.h"
#include "motors/MotorController.h"
#include "sensors/BatteryMonitor.h"
#include "sensors/DistanceSensor.h"
#include "safety/SafetyMonitor.h"

MotorController  motors;
BatteryMonitor   battery;
DistanceSensor   frontSensor(DIST_TRIG_FRONT, DIST_ECHO_FRONT, "FRONTAL");
DistanceSensor   rearSensor (DIST_TRIG_REAR,  DIST_ECHO_REAR,  "TRASERO");
SafetyMonitor    safety(frontSensor, rearSensor, motors);

Direction currentDir = Direction::STOP;

void printMenu() {
  Serial.println("\n=== TEST MOTORES + SENSORES ===");
  Serial.println("w → Adelante | s → Atrás | a/d → Girar | x → STOP");
  Serial.println("r → Leer sensores | b → Batería");
  Serial.println("================================");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("=== MOJI ESP32 — Etapa 2: Sensores de Distancia ===");
  motors.begin();
  battery.begin();
  frontSensor.begin();
  rearSensor.begin();
  printMenu();
}

void loop() {
  // Monitor de seguridad cada 100ms
  static unsigned long lastSafety = 0;
  if (millis() - lastSafety > 100) {
    if (safety.check(currentDir)) {
      currentDir = Direction::STOP;
    }
    lastSafety = millis();
  }

  // Log de sensores cada 1s
  static unsigned long lastLog = 0;
  if (millis() - lastLog > 1000) {
    float fd = frontSensor.readCm();
    float rd = rearSensor.readCm();
    Serial.printf("[DIST] Frontal: %.1f cm | Trasero: %.1f cm | Batt: %d%%\n",
                  fd, rd, battery.readPercentage());
    lastLog = millis();
  }

  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'w': currentDir = Direction::FORWARD;  motors.move(currentDir, 150); break;
      case 's': currentDir = Direction::BACKWARD; motors.move(currentDir, 150); break;
      case 'a': currentDir = Direction::LEFT;     motors.move(currentDir, 150); break;
      case 'd': currentDir = Direction::RIGHT;    motors.move(currentDir, 150); break;
      case 'x': currentDir = Direction::STOP;     motors.stop(); break;
      case 'r':
        Serial.printf("[DIST] Frontal: %.1f cm | Trasero: %.1f cm\n",
                      frontSensor.readCm(), rearSensor.readCm()); break;
      case 'b':
        Serial.printf("[BATT] %.2f V | %d%%\n",
                      battery.readVoltage(), battery.readPercentage()); break;
      default: break;
    }
    printMenu();
  }
}
```

### 4.4 Prueba de la Etapa 2

**Procedimiento**:

1. Subir el código y abrir Serial Monitor.
2. Enviar `r` para leer los sensores en reposo. Verificar que devuelven distancias coherentes (comparar con una regla).
3. Colocar la mano frente al sensor frontal a diferentes distancias y confirmar que la lectura es aproximadamente correcta.
4. Enviar `w` para avanzar. Acercar un objeto desde el frente a menos de 10 cm. El robot debe **detenerse solo** aunque no se envíe el comando `x`.
5. Enviar `s` para retroceder. Colocar un obstáculo por detrás. El robot debe detenerse solo.
6. Con el Serial Monitor, verificar que los logs indican `[SAFETY] Obstáculo FRONTAL < 10cm → STOP`.

**Criterios de éxito**:
- ✅ Lecturas de distancia precisas (±2 cm en rango 5–200 cm)
- ✅ Parada automática al detectar obstáculo frontal durante avance
- ✅ Parada automática al detectar obstáculo trasero durante retroceso
- ✅ Las lecturas tienen `-1` cuando no hay objeto en el rango
- ✅ La batería sigue reportando correctamente

**Problemas comunes**:
- *Lecturas muy erráticas*: verificar el divisor resistivo; medir con multímetro el pin Echo (debe llegar a ~3V con el pulso).
- *El robot no se detiene*: asegurarse de que `safety.check()` se llama en el loop con la dirección actual.
- *Los sensores siempre retornan -1*: verificar que VCC del HC-SR04 está en 5V (no 3.3V).

---

## 5. Etapa 3 — LED RGB

### Objetivo
Controlar el LED RGB para indicar visualmente el estado del robot. Implementar los modos: IDLE (azul respiración), MOVING (verde sólido), ERROR (rojo parpadeante), BRAIN_OFFLINE (ámbar pulsante) y LOW BATTERY (naranja parpadeante).

### 5.1 Conexión LED RGB ↔ ESP32-S3

El LED RGB es de **ánodo común**: la pata más larga se conecta a 3.3V. Cada cátodo (R, G, B) se conecta a su GPIO a través de una resistencia de protección de 220Ω.

```
3.3V ──── Ánodo (pata larga del LED)

GPIO 38 ──── 220Ω ──── Cátodo R (Rojo)
GPIO 39 ──── 220Ω ──── Cátodo G (Verde)
GPIO 40 ──── 220Ω ──── Cátodo B (Azul)
```

> **Lógica invertida**: En ánodo común, LOW en el GPIO enciende el LED y HIGH lo apaga. El controlador maneja esto internamente usando `255 - valor` para que la API externa sea intuitiva (0 = apagado, 255 = máximo brillo).

Corrientes aproximadas:
- Rojo: (3.3V - 2.0V) / 220Ω ≈ 5.9 mA ✅
- Verde: (3.3V - 3.0V) / 220Ω ≈ 1.4 mA ✅
- Azul: (3.3V - 3.0V) / 220Ω ≈ 1.4 mA ✅

### 5.2 Código — Etapa 3

#### `include/leds/LEDController.h`

```cpp
#pragma once
#include <Arduino.h>
#include "config.h"

enum class LEDMode { IDLE, MOVING, ERROR_STATE, BRAIN_OFFLINE, LOW_BATTERY, CUSTOM };

class LEDController {
public:
  void begin();
  void setMode(LEDMode mode);
  void setCustom(uint8_t r, uint8_t g, uint8_t b);
  // Llamar periódicamente para actualizar efectos animados
  void update();

private:
  LEDMode  _mode    = LEDMode::IDLE;
  uint8_t  _r = 0, _g = 0, _b = 0;
  uint32_t _lastUpdate = 0;
  float    _breathePhase = 0.0f;
  bool     _blinkState   = false;

  void writeRGB(uint8_t r, uint8_t g, uint8_t b);
  void animateBreathe(uint8_t r, uint8_t g, uint8_t b, float speed);
  void animateBlink(uint8_t r, uint8_t g, uint8_t b, uint32_t periodMs);
};
```

#### `src/leds/LEDController.cpp`

```cpp
#include "leds/LEDController.h"
#include <math.h>

void LEDController::begin() {
  ledcAttachChannel(LED_PIN_R, LED_PWM_FREQ, LED_PWM_RESOLUTION, LED_PWM_CHANNEL_R);
  ledcAttachChannel(LED_PIN_G, LED_PWM_FREQ, LED_PWM_RESOLUTION, LED_PWM_CHANNEL_G);
  ledcAttachChannel(LED_PIN_B, LED_PWM_FREQ, LED_PWM_RESOLUTION, LED_PWM_CHANNEL_B);
  writeRGB(0, 0, 0);
  Serial.println("[LED] LEDController iniciado");
}

// ánodo común: invertir valores
void LEDController::writeRGB(uint8_t r, uint8_t g, uint8_t b) {
  ledcWrite(LED_PIN_R, 255 - r);
  ledcWrite(LED_PIN_G, 255 - g);
  ledcWrite(LED_PIN_B, 255 - b);
}

void LEDController::setMode(LEDMode mode) {
  _mode = mode;
  _breathePhase = 0.0f;
  _blinkState   = false;
}

void LEDController::setCustom(uint8_t r, uint8_t g, uint8_t b) {
  _mode = LEDMode::CUSTOM;
  _r = r; _g = g; _b = b;
}

void LEDController::animateBreathe(uint8_t r, uint8_t g, uint8_t b, float speed) {
  // Ciclo ~3s a speed=1.0, más rápido con speed mayor
  _breathePhase += speed * 0.02f;
  if (_breathePhase > TWO_PI) _breathePhase -= TWO_PI;
  float factor = (sin(_breathePhase) + 1.0f) / 2.0f;  // 0.0 – 1.0
  writeRGB((uint8_t)(r * factor), (uint8_t)(g * factor), (uint8_t)(b * factor));
}

void LEDController::animateBlink(uint8_t r, uint8_t g, uint8_t b, uint32_t periodMs) {
  if (millis() - _lastUpdate > periodMs / 2) {
    _blinkState = !_blinkState;
    _lastUpdate = millis();
  }
  writeRGB(_blinkState ? r : 0, _blinkState ? g : 0, _blinkState ? b : 0);
}

void LEDController::update() {
  switch (_mode) {
    case LEDMode::IDLE:
      // Azul suave, respiración lenta (~3s)
      animateBreathe(0, 80, 200, 0.8f);
      break;
    case LEDMode::MOVING:
      // Verde sólido
      writeRGB(0, 200, 0);
      break;
    case LEDMode::ERROR_STATE:
      // Rojo parpadeante rápido (2 Hz → 250ms por semiciclo)
      animateBlink(255, 0, 0, 500);
      break;
    case LEDMode::BRAIN_OFFLINE:
      // Ámbar pulsante suave (1 Hz)
      animateBreathe(255, 160, 0, 1.5f);
      break;
    case LEDMode::LOW_BATTERY:
      // Naranja parpadeante lento (0.5 Hz → 1000ms por semiciclo)
      animateBlink(255, 100, 0, 2000);
      break;
    case LEDMode::CUSTOM:
      writeRGB(_r, _g, _b);
      break;
  }
}
```

#### `src/main.cpp` — Test Etapa 3

```cpp
#include <Arduino.h>
#include "config.h"
#include "motors/MotorController.h"
#include "sensors/BatteryMonitor.h"
#include "sensors/DistanceSensor.h"
#include "safety/SafetyMonitor.h"
#include "leds/LEDController.h"

MotorController  motors;
BatteryMonitor   battery;
DistanceSensor   frontSensor(DIST_TRIG_FRONT, DIST_ECHO_FRONT, "FRONTAL");
DistanceSensor   rearSensor (DIST_TRIG_REAR,  DIST_ECHO_REAR,  "TRASERO");
SafetyMonitor    safety(frontSensor, rearSensor, motors);
LEDController    led;

Direction currentDir = Direction::STOP;

void printMenu() {
  Serial.println("\n=== TEST MOTORES + SENSORES + LED ===");
  Serial.println("w/s/a/d → Mover | x → STOP");
  Serial.println("1 → IDLE | 2 → MOVING | 3 → ERROR | 4 → BRAIN_OFFLINE | 5 → LOW_BATT");
  Serial.println("r → Sensores | b → Batería");
  Serial.println("=====================================");
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("=== MOJI ESP32 — Etapa 3: LED RGB ===");
  motors.begin();
  battery.begin();
  frontSensor.begin();
  rearSensor.begin();
  led.begin();
  led.setMode(LEDMode::IDLE);
  printMenu();
}

void loop() {
  led.update();  // Actualizar efectos LED

  // Seguridad
  static unsigned long lastSafety = 0;
  if (millis() - lastSafety > 100) {
    if (safety.check(currentDir)) {
      currentDir = Direction::STOP;
      led.setMode(LEDMode::ERROR_STATE);
    }
    lastSafety = millis();
  }

  // Batería baja
  if (battery.isLow()) led.setMode(LEDMode::LOW_BATTERY);

  // Log periódico
  static unsigned long lastLog = 0;
  if (millis() - lastLog > 2000) {
    Serial.printf("[STATUS] Frontal: %.1f cm | Trasero: %.1f cm | Batt: %d%%\n",
                  frontSensor.readCm(), rearSensor.readCm(), battery.readPercentage());
    lastLog = millis();
  }

  if (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'w': currentDir = Direction::FORWARD;  motors.move(currentDir, 150); led.setMode(LEDMode::MOVING); break;
      case 's': currentDir = Direction::BACKWARD; motors.move(currentDir, 150); led.setMode(LEDMode::MOVING); break;
      case 'a': currentDir = Direction::LEFT;     motors.move(currentDir, 150); led.setMode(LEDMode::MOVING); break;
      case 'd': currentDir = Direction::RIGHT;    motors.move(currentDir, 150); led.setMode(LEDMode::MOVING); break;
      case 'x': currentDir = Direction::STOP;     motors.stop();                led.setMode(LEDMode::IDLE);   break;
      case '1': led.setMode(LEDMode::IDLE);          Serial.println("→ LED IDLE");          break;
      case '2': led.setMode(LEDMode::MOVING);        Serial.println("→ LED MOVING");        break;
      case '3': led.setMode(LEDMode::ERROR_STATE);   Serial.println("→ LED ERROR");         break;
      case '4': led.setMode(LEDMode::BRAIN_OFFLINE); Serial.println("→ LED BRAIN_OFFLINE"); break;
      case '5': led.setMode(LEDMode::LOW_BATTERY);   Serial.println("→ LED LOW_BATTERY");   break;
      case 'r':
        Serial.printf("[DIST] Frontal: %.1f cm | Trasero: %.1f cm\n",
                      frontSensor.readCm(), rearSensor.readCm()); break;
      case 'b':
        Serial.printf("[BATT] %.2f V | %d%%\n",
                      battery.readVoltage(), battery.readPercentage()); break;
      default: break;
    }
    printMenu();
  }
}
```

### 5.3 Prueba de la Etapa 3

**Procedimiento**:

1. Subir el código. El LED debe arrancar en modo IDLE con respiración azul.
2. Enviar `1` → respiración azul suave.
3. Enviar `2` → verde sólido.
4. Enviar `3` → rojo parpadeante.
5. Enviar `4` → ámbar pulsante.
6. Enviar `5` → naranja parpadeante lento.
7. Mover el robot con `w`/`s` → el LED cambia a verde mientras se mueve y vuelve a IDLE al parar.
8. Acercar un obstáculo durante el movimiento → la seguridad para el robot y el LED cambia a rojo.

**Criterios de éxito**:
- ✅ Cada modo muestra el color y patrón correcto
- ✅ La transición de modos es inmediata
- ✅ Los efectos animados (respiración, parpadeo) son suaves
- ✅ El LED no afecta el funcionamiento de motores ni sensores

**Problemas comunes**:
- *El LED siempre está encendido al máximo*: verificar que el ánodo está en 3.3V (no en 5V) y que la lógica de inversión (`255 - valor`) está aplicada.
- *Solo un canal funciona*: verificar que los tres pines (38, 39, 40) están correctamente conectados y los canales LEDC asignados no colisionan con los de los motores.

---

## 6. Etapa 4 — BLE (Bluetooth Low Energy)

### Objetivo
Conectar el ESP32 con un dispositivo Android (o app BLE genérica como **nRF Connect**) para recibir primitivas físicas (`turn_*`, `move_*`, `led_color`), secuencias compiladas y enviar telemetría. Implementar el heartbeat para el modo BRAIN_OFFLINE.

> **Estrategia de prueba incremental**: Antes de integrar con la app Android de Moji, se prueba con la app gratuita **nRF Connect** (Android/iOS). Esto permite verificar el protocolo BLE de forma independiente.

### 6.1 Protocolo BLE

```
Nombre del dispositivo: "RobotESP32"
Service UUID:  6E400001-B5A3-F393-E0A9-E50E24DCCA9E

Característica TX (Write — Android → ESP32):
  UUID:        6E400002-B5A3-F393-E0A9-E50E24DCCA9E
  Propiedades: WRITE, WRITE_NO_RESPONSE
  Máx bytes:   512

Característica RX (Notify — ESP32 → Android):
  UUID:        6E400003-B5A3-F393-E0A9-E50E24DCCA9E
  Propiedades: NOTIFY
  Intervalo:   Cada 1 segundo (telemetría) + on-demand
```

#### Formato de comandos (Android → ESP32)

> **Nota sobre movimiento calibrado**: el firmware usa velocidad fija `200` para todos los comandos de movimiento BLE. Los comandos por `cm` y por `degrees` se convierten internamente a `duration_ms` usando las constantes `MOTION_MS_PER_10_CM_AT_SPEED_200` y `MOTION_MS_PER_90_DEG_AT_SPEED_200` definidas en `config.h`, para que luego puedas calibrarlas en el robot real.

```json
// Primitivas físicas alineadas con la arquitectura backend v2.0
{"type": "turn_right_deg", "degrees": 90}
{"type": "turn_left_deg", "degrees": 90}
{"type": "move_forward_duration", "duration_ms": 1500}
{"type": "move_backward_duration", "duration_ms": 800}
{"type": "move_forward_cm", "cm": 50}
{"type": "move_backward_cm", "cm": 20}

// Parar
{"type": "stop"}

// Secuencia de movimientos (Android compila aquí búsquedas faciales o gestos)
{
  "type": "move_sequence",
  "steps": [
    {"type": "turn_right_deg", "degrees": 90},
    {"type": "stop"},
    {"type": "move_forward_cm", "cm": 15},
    {"type": "led_color", "r": 0, "g": 255, "b": 0, "duration_ms": 400}
  ]
}

// Control de LED
{"type": "led_color", "r": 0, "g": 255, "b": 0, "duration_ms": 1000}
{"type": "led_color", "r": 255, "g": 0, "b": 0, "duration_ms": 600}

// Heartbeat (cada 1s desde Android)
{"type": "heartbeat", "timestamp": 1234567890}

// Solicitar telemetría
{"type": "telemetry", "request": "all"}
```

El ESP32 no necesita entender aliases de alto nivel como `wave`, `nod` o `shake_head`. Android debe expandirlos previamente a `move_sequence` usando únicamente primitivas físicas.

#### Formato de telemetría (ESP32 → Android)

```json
{
  "type": "telemetry",
  "timestamp": 1234567890,
  "battery": {
    "bus_voltage": 7.18,
    "load_voltage": 7.21,
    "shunt_voltage_mv": 28.0,
    "current_ma": 410.5,
    "power_mw": 2959.7,
    "percentage": 75,
    "sensor_ok": true
  },
  "sensors": {
    "distance_front": 150,
    "distance_rear": 200,
    "cliff_front_left": 62,
    "cliff_front_right": 61,
    "cliff_rear": 60
  },
  "motors": {
    "state": "stop",
    "last_action": "move_forward_cm"
  },
  "leds": {"mode": "idle"},
  "heartbeat": {"brain_online": true},
  "safety": {
    "cliff_active": false,
    "obstacle_blocked": false
  },
  "uptime": 3600
}
```

### 6.2 Código — Etapa 4

#### `include/bluetooth/BLEServer.h`

```cpp
#pragma once
#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ArduinoJson.h>
#include "config.h"

// Callbacks de comandos recibidos
typedef std::function<void(JsonObject& action)>                    PrimitiveCallback;
typedef std::function<void()>                                      StopCallback;
typedef std::function<void(JsonArray& steps)>                      SequenceCallback;
typedef std::function<void()>                                      TelemetryRequestCallback;

class RobotBLEServer : public BLEServerCallbacks, public BLECharacteristicCallbacks {
public:
  void begin();
  bool isConnected() const { return _connected; }
  void sendTelemetry(const String& json);
  void registerCallbacks(PrimitiveCallback        onPrimitive,
                         StopCallback             onStop,
                         SequenceCallback         onSequence,
                         TelemetryRequestCallback onTelemetryRequest = nullptr);
  // Llamar periódicamente
  void update();
  bool isBrainOnline() const;

  // BLEServerCallbacks
  void onConnect(BLEServer* server)    override;
  void onDisconnect(BLEServer* server) override;

  // BLECharacteristicCallbacks
  void onWrite(BLECharacteristic* characteristic) override;

private:
  bool              _connected      = false;
  unsigned long     _lastHeartbeat  = 0;
  BLECharacteristic* _pRxChar       = nullptr;
  PrimitiveCallback _onPrimitive;
  StopCallback      _onStop;
  SequenceCallback  _onSequence;
  TelemetryRequestCallback _onTelemetryRequest;

  void handleCommand(const String& json);
};

extern RobotBLEServer bleServer;
```

#### `src/bluetooth/BLEServer.cpp`

```cpp
#include "bluetooth/BLEServer.h"

#define SERVICE_UUID  "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHAR_TX_UUID  "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  // Write (Android → ESP32)
#define CHAR_RX_UUID  "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  // Notify (ESP32 → Android)

RobotBLEServer bleServer;

void RobotBLEServer::begin() {
  BLEDevice::init(BLE_DEVICE_NAME);
  BLEDevice::setMTU(BLE_MTU_SIZE);

  BLEServer* pServer = BLEDevice::createServer();
  pServer->setCallbacks(this);

  BLEService* pService = pServer->createService(SERVICE_UUID);

  // TX — recibe comandos desde Android
  BLECharacteristic* pTxChar = pService->createCharacteristic(
    CHAR_TX_UUID,
    BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
  );
  pTxChar->setCallbacks(this);

  // RX — envía notificaciones a Android
  _pRxChar = pService->createCharacteristic(
    CHAR_RX_UUID,
    BLECharacteristic::PROPERTY_NOTIFY
  );
  _pRxChar->addDescriptor(new BLE2902());

  pService->start();

  BLEAdvertising* pAdv = BLEDevice::getAdvertising();
  pAdv->addServiceUUID(SERVICE_UUID);
  pAdv->setScanResponse(true);
  pAdv->setMinPreferred(0x06);
  BLEDevice::startAdvertising();

  Serial.println("[BLE] Advertising como 'RobotESP32'...");
}

void RobotBLEServer::registerCallbacks(PrimitiveCallback        onPrimitive,
                                       StopCallback             onStop,
                                       SequenceCallback         onSequence,
                                       TelemetryRequestCallback onTelemetryRequest) {
  _onPrimitive        = onPrimitive;
  _onStop             = onStop;
  _onSequence         = onSequence;
  _onTelemetryRequest = onTelemetryRequest;
}

void RobotBLEServer::onConnect(BLEServer* server) {
  _connected     = true;
  _lastHeartbeat = millis();
  Serial.println("[BLE] Cliente conectado");
}

void RobotBLEServer::onDisconnect(BLEServer* server) {
  _connected = false;
  Serial.println("[BLE] Cliente desconectado → restart advertising");
  BLEDevice::startAdvertising();
}

void RobotBLEServer::onWrite(BLECharacteristic* characteristic) {
  String value = characteristic->getValue().c_str();
  if (value.length() > 0) {
    handleCommand(value);
  }
}

void RobotBLEServer::handleCommand(const String& json) {
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, json);
  if (err) {
    Serial.printf("[BLE] JSON error: %s\n", err.c_str());
    return;
  }

  const char* type = doc["type"];
  Serial.printf("[BLE] CMD recibido: %s\n", type);

  if (strcmp(type, "heartbeat") == 0) {
    _lastHeartbeat = millis();

  } else if (strcmp(type, "stop") == 0 && _onStop) {
    _onStop();

  } else if (strcmp(type, "move_sequence") == 0 && _onSequence) {
    JsonArray steps = doc["steps"];
    _onSequence(steps);

  } else if ((strcmp(type, "turn_right_deg") == 0 ||
              strcmp(type, "turn_left_deg") == 0 ||
              strcmp(type, "move_forward_duration") == 0 ||
              strcmp(type, "move_backward_duration") == 0 ||
              strcmp(type, "move_forward_cm") == 0 ||
              strcmp(type, "move_backward_cm") == 0 ||
              strcmp(type, "led_color") == 0) && _onPrimitive) {
    JsonObject action = doc.as<JsonObject>();
    _onPrimitive(action);

  } else if (strcmp(type, "telemetry") == 0 && _onTelemetryRequest) {
    _onTelemetryRequest();
  }
}

void RobotBLEServer::sendTelemetry(const String& json) {
  if (!_connected || !_pRxChar) return;
  _pRxChar->setValue(json.c_str());
  _pRxChar->notify();
}

bool RobotBLEServer::isBrainOnline() const {
  if (!_connected) return false;
  return (millis() - _lastHeartbeat) < HEARTBEAT_TIMEOUT_MS;
}

void RobotBLEServer::update() {
  // Detectar BRAIN_OFFLINE si hay conexión pero no heartbeat
  if (_connected && !isBrainOnline()) {
    static bool offlineLogged = false;
    if (!offlineLogged) {
      Serial.println("[BLE] BRAIN_OFFLINE — heartbeat perdido > 3s");
      offlineLogged = true;
    }
  } else {
    // Reset flag cuando el brain vuelve
  }
}
```

#### `src/main.cpp` — Test Etapa 4 (sistema completo sin cliff sensors)

```cpp
#include <Arduino.h>
#include "config.h"
#include "motors/MotorController.h"
#include "sensors/BatteryMonitor.h"
#include "sensors/DistanceSensor.h"
#include "safety/SafetyMonitor.h"
#include "leds/LEDController.h"
#include "bluetooth/BLEServer.h"
#include <ArduinoJson.h>

MotorController  motors;
BatteryMonitor   battery;
DistanceSensor   frontSensor(DIST_TRIG_FRONT, DIST_ECHO_FRONT, "FRONTAL");
DistanceSensor   rearSensor (DIST_TRIG_REAR,  DIST_ECHO_REAR,  "TRASERO");
SafetyMonitor    safety(frontSensor, rearSensor, motors);
LEDController    led;

Direction currentDir = Direction::STOP;
bool      brainWasOnline = false;
const char* currentAction = "idle";

const char* directionToString(Direction dir) {
  switch (dir) {
    case Direction::FORWARD:  return "forward";
    case Direction::BACKWARD: return "backward";
    case Direction::LEFT:     return "left";
    case Direction::RIGHT:    return "right";
    default:                  return "stop";
  }
}

void finishMotionAction() {
  motors.stop();
  currentDir = Direction::STOP;
  if (!battery.isLow()) {
    led.setMode(LEDMode::IDLE);
  }
}

void executePrimitiveAction(JsonObject& action) {
  const char* type       = action["type"] | "";
  uint8_t     speed      = action["speed"] | 0;
  uint32_t    durationMs = action["duration_ms"] | 0;

  if (strcmp(type, "turn_right_deg") == 0) {
    currentAction = "turn_right_deg";
    currentDir = Direction::RIGHT;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::RIGHT, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "turn_left_deg") == 0) {
    currentAction = "turn_left_deg";
    currentDir = Direction::LEFT;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::LEFT, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "move_forward_cm") == 0) {
    currentAction = "move_forward_cm";
    currentDir = Direction::FORWARD;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::FORWARD, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "move_backward_cm") == 0) {
    currentAction = "move_backward_cm";
    currentDir = Direction::BACKWARD;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::BACKWARD, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "led_color") == 0) {
    currentAction = "led_color";
    led.setCustom(action["r"] | 0, action["g"] | 0, action["b"] | 0);
    if (durationMs > 0) {
      delay(durationMs);
      if (!battery.isLow()) {
        led.setMode(LEDMode::IDLE);
      }
    }
  }
}

String buildTelemetry() {
  StaticJsonDocument<768> doc;
  doc["type"]      = "telemetry";
  doc["timestamp"] = millis();

  BatteryReading battReading = battery.read();

  JsonObject batt = doc.createNestedObject("battery");
  batt["bus_voltage"]      = battReading.busVoltage;
  batt["load_voltage"]     = battReading.loadVoltage;
  batt["shunt_voltage_mv"] = battReading.shuntVoltage;
  batt["current_ma"]       = battReading.currentmA;
  batt["power_mw"]         = battReading.powermW;
  batt["percentage"]       = battReading.percentage;
  batt["sensor_ok"]        = battReading.sensorOk;

  JsonObject sens = doc.createNestedObject("sensors");
  sens["distance_front"] = frontSensor.readCm();
  sens["distance_rear"]  = rearSensor.readCm();

  JsonObject motorsJson = doc.createNestedObject("motors");
  motorsJson["state"] = directionToString(currentDir);
  motorsJson["last_action"] = currentAction;

  JsonObject heartbeat = doc.createNestedObject("heartbeat");
  heartbeat["brain_online"] = bleServer.isBrainOnline();

  JsonObject safetyJson = doc.createNestedObject("safety");
  safetyJson["cliff_active"] = false;
  safetyJson["obstacle_blocked"] =
    (currentDir == Direction::FORWARD && frontSensor.isObstacle()) ||
    (currentDir == Direction::BACKWARD && rearSensor.isObstacle());

  doc["uptime"] = millis() / 1000;

  String out;
  serializeJson(doc, out);
  return out;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("=== MOJI ESP32 — Etapa 4: BLE ===");

  motors.begin();
  battery.begin();
  frontSensor.begin();
  rearSensor.begin();
  led.begin();
  led.setMode(LEDMode::IDLE);

  // Registrar callbacks BLE
  bleServer.registerCallbacks(
    // onPrimitive
    [](JsonObject& action) {
      executePrimitiveAction(action);
    },
    // onStop
    []() {
      currentAction = "stop";
      currentDir = Direction::STOP;
      motors.stop();
      led.setMode(LEDMode::IDLE);
    },
    // onSequence
    [](JsonArray& steps) {
      for (JsonObject step : steps) {
        executePrimitiveAction(step);
      }
      currentAction = "idle";
      finishMotionAction();
    },
    // onTelemetryRequest
    []() {
      if (bleServer.isConnected()) {
        bleServer.sendTelemetry(buildTelemetry());
      }
    }
  );

  bleServer.begin();
}

void loop() {
  led.update();
  bleServer.update();

  // Gestión BRAIN_OFFLINE
  bool brainOnline = bleServer.isBrainOnline();
  if (bleServer.isConnected() && !brainOnline && brainWasOnline) {
    Serial.println("[SAFETY] BRAIN_OFFLINE → STOP + LED ámbar");
    motors.stop();
    currentDir = Direction::STOP;
    led.setMode(LEDMode::BRAIN_OFFLINE);
  }
  if (brainOnline && !brainWasOnline) {
    Serial.println("[BLE] Brain recuperado");
    led.setMode(LEDMode::IDLE);
  }
  brainWasOnline = brainOnline;

  // Seguridad sensores de distancia
  static unsigned long lastSafety = 0;
  if (millis() - lastSafety > 100) {
    if (safety.check(currentDir)) {
      currentDir = Direction::STOP;
      led.setMode(LEDMode::ERROR_STATE);
    }
    lastSafety = millis();
  }

  // Telemetría periódica
  static unsigned long lastTelemetry = 0;
  if (millis() - lastTelemetry > TELEMETRY_INTERVAL_MS) {
    if (bleServer.isConnected()) {
      bleServer.sendTelemetry(buildTelemetry());
    }
    lastTelemetry = millis();
  }

  // Batería baja
  if (battery.isLow()) led.setMode(LEDMode::LOW_BATTERY);
}
```

### 6.3 Prueba de la Etapa 4

**Herramienta**: app **nRF Connect** (disponible en Google Play / App Store) para probar BLE sin la app Android de Moji.

**Procedimiento**:

1. Subir el código y abrir Serial Monitor. Debe aparecer: `[BLE] Advertising como 'RobotESP32'...`
2. Abrir **nRF Connect** en el teléfono. Escanear dispositivos BLE. Debe aparecer `RobotESP32`.
3. Conectar. En el Serial Monitor debe aparecer `[BLE] Cliente conectado`.
4. En nRF Connect, ir al servicio `6E400001...` → característica `6E400002` (Write).
5. Enviar el JSON: `{"type":"heartbeat","timestamp":0}` → en el Serial Monitor aparece `[BLE] CMD recibido: heartbeat`.
6. Enviar: `{"type":"move_forward_duration","duration_ms":1500}` → el robot avanza durante 1.5 s a velocidad fija 200 y el LED se pone verde durante la acción.
7. Enviar: `{"type":"led_color","r":0,"g":255,"b":0,"duration_ms":1000}` → el LED cambia temporalmente a verde y luego vuelve a IDLE.
8. Enviar: `{"type":"move_sequence","steps":[{"type":"turn_right_deg","degrees":90},{"type":"stop"},{"type":"move_forward_cm","cm":15},{"type":"led_color","r":255,"g":140,"b":0,"duration_ms":600}]}` → el robot ejecuta la secuencia completa aceptando giros por grados, desplazamientos por centímetros, `stop` y `led_color`.
9. Suscribirse a notificaciones en la característica `6E400003` (Notify). Cada 1 segundo debe llegar el JSON de telemetría con `bus_voltage`, `load_voltage`, `current_ma`, `power_mw`, distancias y estado de seguridad.
10. **Probar BRAIN_OFFLINE**: conectar con nRF Connect, mover el robot, y luego **no enviar heartbeats** durante 3 segundos. El robot debe:
   - Detenerse solo
   - El LED cambia a ámbar pulsante
   - Serial Monitor imprime `[SAFETY] BRAIN_OFFLINE → STOP + LED ámbar`
11. Enviar un heartbeat → el robot vuelve a IDLE con LED azul.

**Criterios de éxito**:
- ✅ El dispositivo aparece como `RobotESP32` al escanear
- ✅ Las primitivas `turn_*`, `move_*`, `stop` y `led_color` se ejecutan correctamente
- ✅ `turn_right_deg` y `turn_left_deg` convierten `degrees` a tiempo de giro usando la constante de calibración
- ✅ `move_forward_cm` y `move_backward_cm` convierten `cm` a tiempo de movimiento usando la constante de calibración
- ✅ `move_forward_duration` y `move_backward_duration` usan siempre velocidad fija `200`
- ✅ Al terminar cualquier movimiento o secuencia, el LED vuelve a IDLE (azul respiración)
- ✅ La telemetría llega cada 1 segundo a nRF Connect
- ✅ El bloque `battery` incluye voltaje, corriente, potencia y estado del sensor INA219
- ✅ BRAIN_OFFLINE se activa a los 3s sin heartbeat
- ✅ El robot se recupera al recibir heartbeat
- ✅ Los sensores de distancia siguen bloqueando movimientos peligrosos via BLE

**Problemas comunes**:
- *El ESP32 no aparece al escanear*: reiniciar el ESP32; verificar que `BLEDevice::init()` se llama correctamente.
- *El robot no responde a comandos BLE*: verificar que el JSON está bien formateado (sin saltos de línea extra); nRF Connect a veces necesita enviar el dato como "UTF-8".
- *La telemetría no llega*: verificar que la suscripción CCCD está habilitada en nRF Connect (activar "Enable CCCDs" al conectar).

---

## 7. Etapa 5 — Sensores Cliff VL53L0X

### Objetivo
Detectar el borde de una mesa o caída de escaleras. Tres sensores VL53L0X (Time-of-Flight) miran hacia abajo desde el frente-izquierdo, frente-derecho y trasero del robot. Si alguno deja de detectar el suelo (distancia demasiado alta), el robot se detiene.

### 7.1 Cómo funciona la detección de cliff

Los VL53L0X son sensores de distancia láser (ToF). Montados mirando hacia abajo detectan el suelo a una distancia fija (ej. 30–50 mm). Si el robot llega al borde de una mesa o una escalera, el sensor ya no ve el suelo a esa distancia sino el vacío, y devuelve una distancia mucho mayor (o error de lectura). En ese caso el sistema dispara una parada de emergencia.

```
Robot sobre superficie plana:     Sensor lee ~40mm → OK
Robot en borde de mesa/escalera:  Sensor lee >80mm o timeout → CLIFF DETECTADO → STOP
```

### 7.2 Problema: todos los VL53L0X comparten dirección I²C

Los tres VL53L0X tienen la misma dirección I²C de fábrica (`0x29`). Para poder usarlos en el mismo bus I²C simultáneamente, se usa el pin **XSHUT** de cada sensor para inicializarlos uno por uno y asignarle una dirección única.

El **INA219** ya está en ese mismo bus con dirección `0x40`, por lo que no hay conflicto mientras los VL53L0X se reasignen correctamente a `0x30`, `0x31` y `0x32`.

### 7.3 Conexión VL53L0X ↔ ESP32-S3

Los tres sensores comparten los pines I²C (SDA y SCL) pero cada uno tiene su propio pin XSHUT:

```
ESP32-S3        VL53L0X (los 3 comparten I²C)
────────        ──────────────────────────────
GPIO 8 (SDA)  ──── SDA de los 3 sensores + INA219 (bus compartido)
GPIO 9 (SCL)  ──── SCL de los 3 sensores + INA219 (bus compartido)
3.3V          ──── VIN de los 3 sensores
GND           ──── GND de los 3 sensores

GPIO 11       ──── XSHUT del sensor Cliff Front-Left
GPIO 12       ──── XSHUT del sensor Cliff Front-Right
GPIO 13       ──── XSHUT del sensor Cliff Rear
```

> **Orientación física**: los tres sensores se montan mirando hacia abajo, cerca del borde inferior del chasis. El sensor trasero detecta el borde durante el movimiento hacia atrás; los dos frontales lo hacen durante el movimiento hacia adelante.

### 7.4 Inicialización con direcciones únicas

```cpp
// Secuencia de inicialización I²C para 3 VL53L0X:
// 1. Poner todos los XSHUT en LOW → todos los sensores en reset (apagados)
// 2. Activar sensor 1 (XSHUT = HIGH) → inicia con dirección 0x29
// 3. Cambiar dirección de sensor 1 a 0x30
// 4. Activar sensor 2 → cambia a 0x31
// 5. Activar sensor 3 → queda en 0x29 (o cambiar a 0x32)
```

### 7.5 Código — Etapa 5

#### `include/sensors/CliffSensor.h`

```cpp
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <VL53L0X.h>
#include "config.h"

class CliffSensor {
public:
  void begin();
  bool isCliffDetected();   // true si algún sensor detecta precipicio
  bool readFL();            // Front-Left
  bool readFR();            // Front-Right
  bool readRR();            // Rear

private:
  VL53L0X _sensorFL;
  VL53L0X _sensorFR;
  VL53L0X _sensorRR;

  bool _checkSensor(VL53L0X& sensor);
};
```

#### `src/sensors/CliffSensor.cpp`

```cpp
#include "sensors/CliffSensor.h"

// Direcciones I²C únicas para cada sensor
#define ADDR_CLIFF_FL 0x30
#define ADDR_CLIFF_FR 0x31
#define ADDR_CLIFF_RR 0x32

void CliffSensor::begin() {
  Wire.begin(I2C_SDA, I2C_SCL);  // mismo bus que el INA219

  // 1. Apagar todos los sensores (XSHUT LOW)
  pinMode(XSHUT_CLIFF_FL, OUTPUT); digitalWrite(XSHUT_CLIFF_FL, LOW);
  pinMode(XSHUT_CLIFF_FR, OUTPUT); digitalWrite(XSHUT_CLIFF_FR, LOW);
  pinMode(XSHUT_CLIFF_RR, OUTPUT); digitalWrite(XSHUT_CLIFF_RR, LOW);
  delay(10);

  // 2. Inicializar Front-Left en 0x30
  digitalWrite(XSHUT_CLIFF_FL, HIGH); delay(10);
  _sensorFL.init();
  _sensorFL.setAddress(ADDR_CLIFF_FL);
  _sensorFL.setTimeout(100);
  _sensorFL.startContinuous(50);
  Serial.println("[CLIFF] Front-Left VL53L0X OK @ 0x30");

  // 3. Inicializar Front-Right en 0x31
  digitalWrite(XSHUT_CLIFF_FR, HIGH); delay(10);
  _sensorFR.init();
  _sensorFR.setAddress(ADDR_CLIFF_FR);
  _sensorFR.setTimeout(100);
  _sensorFR.startContinuous(50);
  Serial.println("[CLIFF] Front-Right VL53L0X OK @ 0x31");

  // 4. Inicializar Rear en 0x32
  digitalWrite(XSHUT_CLIFF_RR, HIGH); delay(10);
  _sensorRR.init();
  _sensorRR.setAddress(ADDR_CLIFF_RR);
  _sensorRR.setTimeout(100);
  _sensorRR.startContinuous(50);
  Serial.println("[CLIFF] Rear VL53L0X OK @ 0x32");
}

bool CliffSensor::_checkSensor(VL53L0X& sensor) {
  uint16_t dist = sensor.readRangeContinuousMillimeters();
  if (sensor.timeoutOccurred()) return true;  // Timeout = precipicio
  return dist > CLIFF_THRESHOLD_MM;           // > 80mm = precipicio
}

bool CliffSensor::readFL() { return _checkSensor(_sensorFL); }
bool CliffSensor::readFR() { return _checkSensor(_sensorFR); }
bool CliffSensor::readRR() { return _checkSensor(_sensorRR); }

bool CliffSensor::isCliffDetected() {
  return readFL() || readFR() || readRR();
}
```

#### Actualizar `SafetyMonitor` para incluir cliff

```cpp
// Actualizar include/safety/SafetyMonitor.h para añadir CliffSensor
#pragma once
#include <Arduino.h>
#include "sensors/DistanceSensor.h"
#include "sensors/CliffSensor.h"
#include "motors/MotorController.h"
#include "config.h"

class SafetyMonitor {
public:
  SafetyMonitor(DistanceSensor& front, DistanceSensor& rear,
                CliffSensor& cliff, MotorController& motors);
  bool check(Direction currentDir);

private:
  DistanceSensor& _front;
  DistanceSensor& _rear;
  CliffSensor&    _cliff;
  MotorController& _motors;
};
```

```cpp
// src/safety/SafetyMonitor.cpp actualizado
#include "safety/SafetyMonitor.h"

SafetyMonitor::SafetyMonitor(DistanceSensor& front, DistanceSensor& rear,
                              CliffSensor& cliff, MotorController& motors)
  : _front(front), _rear(rear), _cliff(cliff), _motors(motors) {}

bool SafetyMonitor::check(Direction currentDir) {
  // Prioridad 1: Cliff (siempre activo)
  if (_cliff.isCliffDetected()) {
    Serial.println("[SAFETY] ¡CLIFF DETECTADO! → STOP EMERGENCIA");
    _motors.stop();
    return true;
  }
  // Prioridad 2: Obstáculo frontal
  if (currentDir == Direction::FORWARD && _front.isObstacle()) {
    Serial.println("[SAFETY] Obstáculo FRONTAL < 10cm → STOP");
    _motors.stop();
    return true;
  }
  // Prioridad 3: Obstáculo trasero
  if (currentDir == Direction::BACKWARD && _rear.isObstacle()) {
    Serial.println("[SAFETY] Obstáculo TRASERO < 10cm → STOP");
    _motors.stop();
    return true;
  }
  return false;
}
```

#### `src/main.cpp` — Sistema completo final

```cpp
#include <Arduino.h>
#include "config.h"
#include "motors/MotorController.h"
#include "sensors/BatteryMonitor.h"
#include "sensors/DistanceSensor.h"
#include "sensors/CliffSensor.h"
#include "safety/SafetyMonitor.h"
#include "leds/LEDController.h"
#include "bluetooth/BLEServer.h"
#include <ArduinoJson.h>

MotorController  motors;
BatteryMonitor   battery;
DistanceSensor   frontSensor(DIST_TRIG_FRONT, DIST_ECHO_FRONT, "FRONTAL");
DistanceSensor   rearSensor (DIST_TRIG_REAR,  DIST_ECHO_REAR,  "TRASERO");
CliffSensor      cliff;
SafetyMonitor    safety(frontSensor, rearSensor, cliff, motors);
LEDController    led;

Direction currentDir    = Direction::STOP;
bool      brainWasOnline = false;
bool      cliffActive    = false;
const char* currentAction = "idle";

const char* directionToString(Direction dir) {
  switch (dir) {
    case Direction::FORWARD:  return "forward";
    case Direction::BACKWARD: return "backward";
    case Direction::LEFT:     return "left";
    case Direction::RIGHT:    return "right";
    default:                  return "stop";
  }
}

void finishMotionAction() {
  motors.stop();
  currentDir = Direction::STOP;
  if (!cliffActive && !battery.isLow()) {
    led.setMode(LEDMode::IDLE);
  }
}

void executePrimitiveAction(JsonObject& action) {
  const char* type       = action["type"] | "";
  uint8_t     speed      = action["speed"] | 0;
  uint32_t    durationMs = action["duration_ms"] | 0;

  if (cliffActive && strcmp(type, "led_color") != 0) {
    Serial.println("[SAFETY] Cliff activo — comando ignorado");
    return;
  }

  if (strcmp(type, "turn_right_deg") == 0) {
    currentAction = "turn_right_deg";
    currentDir = Direction::RIGHT;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::RIGHT, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "turn_left_deg") == 0) {
    currentAction = "turn_left_deg";
    currentDir = Direction::LEFT;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::LEFT, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "move_forward_cm") == 0) {
    currentAction = "move_forward_cm";
    currentDir = Direction::FORWARD;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::FORWARD, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "move_backward_cm") == 0) {
    currentAction = "move_backward_cm";
    currentDir = Direction::BACKWARD;
    led.setMode(LEDMode::MOVING);
    motors.runFor(Direction::BACKWARD, speed, durationMs);
    finishMotionAction();

  } else if (strcmp(type, "led_color") == 0) {
    currentAction = "led_color";
    led.setCustom(action["r"] | 0, action["g"] | 0, action["b"] | 0);
    if (durationMs > 0) {
      delay(durationMs);
      if (!cliffActive && !battery.isLow()) {
        led.setMode(LEDMode::IDLE);
      }
    }
  }
}

String buildTelemetry() {
  StaticJsonDocument<768> doc;
  doc["type"]      = "telemetry";
  doc["timestamp"] = millis();

  BatteryReading battReading = battery.read();

  JsonObject batt = doc.createNestedObject("battery");
  batt["bus_voltage"]      = battReading.busVoltage;
  batt["load_voltage"]     = battReading.loadVoltage;
  batt["shunt_voltage_mv"] = battReading.shuntVoltage;
  batt["current_ma"]       = battReading.currentmA;
  batt["power_mw"]         = battReading.powermW;
  batt["percentage"]       = battReading.percentage;
  batt["sensor_ok"]        = battReading.sensorOk;

  JsonObject sens = doc.createNestedObject("sensors");
  sens["cliff_front_left"]  = cliff.readFL();
  sens["cliff_front_right"] = cliff.readFR();
  sens["cliff_rear"]        = cliff.readRR();
  sens["distance_front"]    = frontSensor.readCm();
  sens["distance_rear"]     = rearSensor.readCm();

  JsonObject motorsJson = doc.createNestedObject("motors");
  motorsJson["state"] = directionToString(currentDir);
  motorsJson["last_action"] = currentAction;

  JsonObject hb = doc.createNestedObject("heartbeat");
  hb["brain_online"] = bleServer.isBrainOnline();

  JsonObject safetyJson = doc.createNestedObject("safety");
  safetyJson["cliff_active"] = cliffActive;
  safetyJson["obstacle_blocked"] =
    (currentDir == Direction::FORWARD && frontSensor.isObstacle()) ||
    (currentDir == Direction::BACKWARD && rearSensor.isObstacle());

  doc["uptime"] = millis() / 1000;

  String out;
  serializeJson(doc, out);
  return out;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("=== MOJI ESP32 — Sistema Completo v1.1 ===");

  motors.begin();
  battery.begin();
  frontSensor.begin();
  rearSensor.begin();
  cliff.begin();           // ← Nuevo en Etapa 5
  led.begin();
  led.setMode(LEDMode::IDLE);

  bleServer.registerCallbacks(
    [](JsonObject& action) {
      executePrimitiveAction(action);
    },
    []() {
      currentAction = "stop";
      currentDir = Direction::STOP;
      motors.stop();
      led.setMode(LEDMode::IDLE);
    },
    [](JsonArray& steps) {
      for (JsonObject step : steps) {
        if (cliffActive) break;
        executePrimitiveAction(step);
      }
      currentAction = "idle";
      finishMotionAction();
    },
    []() {
      if (bleServer.isConnected()) bleServer.sendTelemetry(buildTelemetry());
    }
  );

  bleServer.begin();
  Serial.println("=== Sistema listo ===");
}

void loop() {
  led.update();
  bleServer.update();

  // BRAIN_OFFLINE
  bool brainOnline = bleServer.isBrainOnline();
  if (bleServer.isConnected() && !brainOnline && brainWasOnline) {
    motors.stop(); currentDir = Direction::STOP;
    led.setMode(LEDMode::BRAIN_OFFLINE);
    Serial.println("[SAFETY] BRAIN_OFFLINE → STOP + LED ámbar");
  }
  if (brainOnline && !brainWasOnline) {
    if (!cliffActive) led.setMode(LEDMode::IDLE);
    Serial.println("[BLE] Brain recuperado");
  }
  brainWasOnline = brainOnline;

  // Seguridad completa (cliff + distancia)
  static unsigned long lastSafety = 0;
  if (millis() - lastSafety > CLIFF_CHECK_INTERVAL_MS) {
    bool emergency = safety.check(currentDir);
    if (emergency) {
      currentDir   = Direction::STOP;
      cliffActive  = true;
      led.setMode(LEDMode::ERROR_STATE);
      if (bleServer.isConnected()) bleServer.sendTelemetry(buildTelemetry());
    } else {
      cliffActive = false;
    }
    lastSafety = millis();
  }

  // Telemetría periódica
  static unsigned long lastTelemetry = 0;
  if (millis() - lastTelemetry > TELEMETRY_INTERVAL_MS) {
    if (bleServer.isConnected()) bleServer.sendTelemetry(buildTelemetry());
    lastTelemetry = millis();
  }

  // Batería baja
  if (battery.isLow() && !cliffActive) led.setMode(LEDMode::LOW_BATTERY);
}
```

### 7.6 Calibración del umbral cliff

El umbral `CLIFF_THRESHOLD_MM = 80` (en `config.h`) debe calibrarse según la altura real del robot sobre el suelo:

1. Montar los sensores VL53L0X mirando hacia abajo en el chasis.
2. Colocar el robot sobre una superficie plana.
3. Leer el valor de distancia desde el Serial Monitor. Anotarlo como `H_suelo`.
4. Asegurarse de que `CLIFF_THRESHOLD_MM > H_suelo + 20mm` (margen de seguridad).
5. Colocar el robot en el borde de una mesa y verificar que los sensores de la parte del borde reportan una distancia mayor al umbral.

**Ejemplo típico**: si el suelo está a 40 mm del sensor, usar `CLIFF_THRESHOLD_MM = 65` (margen de 25 mm).

### 7.7 Prueba de la Etapa 5

**Procedimiento**:

1. Verificar que los tres sensores VL53L0X se inicializan correctamente en el Serial Monitor:
   ```
   [CLIFF] Front-Left VL53L0X OK @ 0x30
   [CLIFF] Front-Right VL53L0X OK @ 0x31
   [CLIFF] Rear VL53L0X OK @ 0x32
   ```
2. Con nRF Connect, enviar comandos de movimiento normales. Verificar que la telemetría incluye los campos `cliff_front_left`, `cliff_front_right`, `cliff_rear` en `false` y que el bloque `battery` trae `current_ma` y `power_mw`.
3. Colocar el robot cerca del borde de una mesa y moverlo hacia el borde. El robot debe detenerse solo **antes de caer**.
4. Verificar que el LED cambia a rojo y que la telemetría reporta el cliff en `true`.
5. Mover el robot de vuelta al centro de la mesa. Los sensores deben reportar `false` y el robot responde nuevamente a comandos.
6. Intentar enviar un comando de movimiento cuando hay cliff activo → el comando debe ser ignorado (`[SAFETY] Cliff activo — comando ignorado`).

**Criterios de éxito**:
- ✅ Los tres sensores se inicializan con direcciones únicas
- ✅ El robot se detiene ante el borde de una mesa
- ✅ Los valores de cliff se reflejan en la telemetría BLE
- ✅ Ningún comando de movimiento puede sobrescribir la parada de cliff
- ✅ El sistema completo (motores + sensores + LED + BLE + cliff) funciona integrado

**Problemas comunes**:
- *Solo 1 o 2 sensores inicializan*: verificar conexiones XSHUT; medir con multímetro que el sinal llega a HIGH cuando corresponde.
- *Todos reportan error de timeout*: verificar que SDA/SCL están bien conectados y que alguno no tiene un pull-up faltante (los VL53L0X internamente ya incluyen pull-ups, pero una conexión floja puede causar problemas).
- *Los umbrales no detectan el borde*: recalibrar `CLIFF_THRESHOLD_MM` como se describe en la sección anterior.

---

## 8. Referencia Rápida de Pines

| GPIO | Función | Notas |
|------|---------|-------|
| 1  | PWM Enable Motor Izq (ENA) | PWM 1kHz 8-bit |
| 2  | PWM Enable Motor Der (ENB) | PWM 1kHz 8-bit |
| 4  | HC-SR04 Frontal — Trigger | Salida digital |
| 5  | HC-SR04 Frontal — Echo | Entrada — ¡divisor resistivo 2kΩ+3kΩ! |
| 6  | HC-SR04 Trasero — Trigger | Salida digital |
| 7  | HC-SR04 Trasero — Echo | Entrada — ¡divisor resistivo 2kΩ+3kΩ! |
| 8  | I²C SDA (INA219 + VL53L0X × 3) | Bus compartido |
| 9  | I²C SCL (INA219 + VL53L0X × 3) | Bus compartido |
| 11 | XSHUT VL53L0X Cliff Front-Left | control I²C address |
| 12 | XSHUT VL53L0X Cliff Front-Right | control I²C address |
| 13 | XSHUT VL53L0X Cliff Rear | control I²C address |
| 38 | LED RGB — Canal Rojo | PWM LEDC ch0, 220Ω serie |
| 39 | LED RGB — Canal Verde | PWM LEDC ch1, 220Ω serie |
| 40 | LED RGB — Canal Azul | PWM LEDC ch2, 220Ω serie |
| 41 | L298N IN1 — Motor Izq FWD | Salida digital |
| 42 | L298N IN2 — Motor Izq REV | Salida digital |
| 47 | L298N IN3 — Motor Der FWD | Salida digital |
| 48 | L298N IN4 — Motor Der REV | Salida digital |

**Pines libres recomendados para futuras expansiones**: GPIO 10, 14, 15, 16, 17 y 18.

**Pines libres condicionales**: GPIO 43 y 44 pueden usarse si no necesitas UART0 dedicado para otro periférico.

**Pines a evitar en este proyecto**:

- GPIO 19 y 20: usados por USB-JTAG por defecto
- GPIO 26 a 37: reservados por SPI flash / PSRAM en esta familia de placas
- GPIO 0, 3, 45 y 46: pines de strapping; solo usarlos si controlas el impacto en el arranque

---

*Documento autosuficiente — no requiere leer robot_architecture.md para implementar el firmware.*
