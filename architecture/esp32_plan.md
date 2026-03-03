# Plan de Implementación ESP32 — Robot Moji

**Versión:** 1.0  
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
| Resistencia | 82 kΩ | 1 | Divisor voltaje batería (R_top) |
| Resistencia | 47 kΩ | 1 | Divisor voltaje batería (R_bot) |
| Resistencia | 2 kΩ | 2 | Divisor HC-SR04 Echo (R1, una por sensor) |
| Resistencia | 3 kΩ | 2 | Divisor HC-SR04 Echo (R2, una por sensor) |
| Resistencia | 220 Ω | 3 | Protección LED RGB (una por canal R, G, B) |

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
2. Nombre del proyecto: `esp32-moji-robot`.
3. Board: buscar `Freenove ESP32-S3 WROOM` o seleccionar `Espressif ESP32-S3-DevKitC-1`.
4. Framework: `Arduino`.
5. Confirmar.

### 2.3 Estructura del proyecto

```
esp32-moji-robot/
├── platformio.ini
├── src/
│   ├── main.cpp
│   ├── config.h
│   ├── bluetooth/
│   │   ├── BLEServer.cpp / .h
│   │   └── HeartbeatMonitor.cpp / .h
│   ├── motors/
│   │   └── MotorController.cpp / .h
│   ├── sensors/
│   │   ├── DistanceSensor.cpp / .h
│   │   ├── CliffSensor.cpp / .h
│   │   └── BatteryMonitor.cpp / .h
│   ├── leds/
│   │   └── LEDController.cpp / .h
│   ├── safety/
│   │   └── SafetyMonitor.cpp / .h
│   └── utils/
│       └── Logger.cpp / .h
└── lib/
```

### 2.4 Configurar `platformio.ini`

```ini
[env:esp32s3-moji]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
monitor_speed = 115200
upload_speed = 921600
board_build.flash_size = 16MB
board_build.psram_type = opi
board_build.arduino.memory_type = qio_opi

lib_deps =
  bblanchon/ArduinoJson@^6.21.0
  pololu/VL53L0X@^1.3.1
```

> **Nota**: La librería ESP32 BLE ya viene incluida en el core de Arduino para ESP32.
> No es necesario agregarla como dependencia externa.

### 2.5 Crear `config.h`

Este archivo centraliza todos los pines y constantes del proyecto. Se irá completando a lo largo de las etapas.

```cpp
// src/config.h
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

// ─── SENSORES CLIFF VL53L0X (I²C) ───────────────────────────────────────────
#define I2C_SDA          21
#define I2C_SCL          22
#define XSHUT_CLIFF_FL   11   // Front-Left
#define XSHUT_CLIFF_FR   12   // Front-Right
#define XSHUT_CLIFF_RR   13   // Rear

#define CLIFF_THRESHOLD_MM      80  // < 80mm al suelo = vacío (precipicio)
#define CLIFF_CHECK_INTERVAL_MS 100

// ─── BATERÍA ─────────────────────────────────────────────────────────────────
#define BATTERY_ADC_PIN        8    // ADC1_CH7, divisor 82kΩ / 47kΩ
#define BATTERY_ADC_SAMPLES   10    // Promedio de lecturas
#define BATTERY_VOLTAGE_MIN   6.0f  // V (3.0V × 2S)
#define BATTERY_VOLTAGE_MAX   8.4f  // V (4.2V × 2S)
#define BATTERY_DIVIDER_RATIO 2.7447f  // (82k+47k)/47k
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
Hacer que el robot se mueva hacia adelante, hacia atrás y gire. Leer el voltaje de la batería. Al final de esta etapa el robot se podrá controlar desde el Serial Monitor.

### 3.1 Alimentación y batería

#### Configuración de la batería

La batería es un pack de **6 celdas 18650 en configuración 2S3P**:
- **2S** = 2 celdas en serie → 7.4V nominal (8.4V máximo)
- **3P** = 3 grupos en paralelo → mayor capacidad (ej. 9000 mAh con celdas de 3000 mAh)
- El **BMS 2S 20A** protege contra sobrecarga, sobredescarga y cortocircuito

```
[Batería 2S3P]──────[BMS 2S 20A]──────[Interruptor]──────┬──[Buck #1 5V]──[L298N VIN / Motores]
                                                           │
                                                           └──[Buck #2 5V]──[ESP32 VIN / Sensores]
```

> **Importante**: Nunca conectar la batería directamente al ESP32. Usar siempre Buck Converter #2 para bajar a 5V antes del pin VIN. El regulador interno del ESP32 convierte 5V → 3.3V.

#### Circuito divisor de voltaje para lectura de batería (GPIO 8)

El ADC del ESP32-S3 soporta máximo 3.3V. La batería puede llegar a 8.4V, por lo que se necesita un divisor resistivo:

```
Bat+ (hasta 8.4V)
    │
   82kΩ
    │
    ├─────── GPIO 8 (ADC1_CH7)
    │
   47kΩ
    │
   GND

V_gpio = 8.4V × 47k / (82k + 47k) = 3.06V  ✅ seguro
```

Materiales: 1× resistencia 82 kΩ, 1× resistencia 47 kΩ.

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

#### `src/motors/MotorController.h`

```cpp
#pragma once
#include <Arduino.h>
#include "../config.h"

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
#include "MotorController.h"

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

#### `src/sensors/BatteryMonitor.h`

```cpp
#pragma once
#include <Arduino.h>
#include "../config.h"

class BatteryMonitor {
public:
  void begin();
  float readVoltage();
  uint8_t readPercentage();
  bool isLow();
};
```

#### `src/sensors/BatteryMonitor.cpp`

```cpp
#include "BatteryMonitor.h"

void BatteryMonitor::begin() {
  analogReadResolution(12);
  Serial.println("[BATTERY] BatteryMonitor iniciado");
}

float BatteryMonitor::readVoltage() {
  uint32_t sum = 0;
  for (int i = 0; i < BATTERY_ADC_SAMPLES; i++) {
    sum += analogRead(BATTERY_ADC_PIN);
    delay(2);
  }
  float adcAvg = sum / (float)BATTERY_ADC_SAMPLES;
  float vAdc   = adcAvg * 3.3f / 4095.0f;
  return vAdc * BATTERY_DIVIDER_RATIO;
}

uint8_t BatteryMonitor::readPercentage() {
  float v = readVoltage();
  if (v >= BATTERY_VOLTAGE_MAX) return 100;
  if (v <= BATTERY_VOLTAGE_MIN) return 0;
  return (uint8_t)(100.0f * (v - BATTERY_VOLTAGE_MIN) /
                             (BATTERY_VOLTAGE_MAX - BATTERY_VOLTAGE_MIN));
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
    Serial.printf("[BATT] %.2f V | %d%%\n",
                  battery.readVoltage(), battery.readPercentage());
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
      case 'b': Serial.printf("[BATT] %.2f V | %d%%\n",
                              battery.readVoltage(), battery.readPercentage()); break;
      default: break;
    }
    printMenu();
  }
}
```

### 3.4 Prueba de la Etapa 1

**Procedimiento**:

1. Con la batería desconectada, verificar con multímetro que los Buck Converters dan exactamente 5V en su salida antes de conectar cualquier componente.
2. Conectar solo el circuito del divisor de batería (GPIO 8 + 82kΩ + 47kΩ).
3. Subir el código al ESP32.
4. Abrir Serial Monitor (115200 baud).
5. Verificar que imprime el voltaje de batería cada 5 segundos. Comparar con el multímetro.
6. Conectar el L298N y los motores (sin las ruedas si es posible, o elevando el robot).
7. Enviar `w` → los motores deben girar hacia adelante durante 2 segundos.
8. Enviar `s` → los motores deben girar hacia atrás.
9. Enviar `a` y `d` → el robot debe girar.
10. Enviar `x` → los motores se deben detener inmediatamente.

**Criterios de éxito**:
- ✅ Lectura de batería coincide (±0.1V) con el multímetro
- ✅ El robot avanza en línea recta (si no, ajustar velocidades de cada motor)
- ✅ El robot gira en ambas direcciones
- ✅ El comando `x` detiene los motores inmediatamente

**Problemas comunes**:
- *Un motor gira al revés*: intercambiar OUT1/OUT2 de ese motor en el L298N.
- *Los motores no giran aunque el LED del L298N enciende*: verificar que el jumper de ENA/ENB esté **quitado** y que el pin GPIO esté enviando PWM.
- *Lectura de batería incorrecta*: verificar valores de resistencias con multímetro.

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

#### `src/sensors/DistanceSensor.h`

```cpp
#pragma once
#include <Arduino.h>
#include "../config.h"

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
#include "DistanceSensor.h"

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

#### `src/safety/SafetyMonitor.h`

```cpp
#pragma once
#include <Arduino.h>
#include "../sensors/DistanceSensor.h"
#include "../motors/MotorController.h"
#include "../config.h"

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
#include "SafetyMonitor.h"

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

#### `src/leds/LEDController.h`

```cpp
#pragma once
#include <Arduino.h>
#include "../config.h"

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
#include "LEDController.h"
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
Conectar el ESP32 con un dispositivo Android (o app BLE genérica como **nRF Connect**) para recibir comandos de movimiento y LED, y enviar telemetría. Implementar el heartbeat para el modo BRAIN_OFFLINE.

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

```json
// Mover en dirección continua
{"type": "move", "direction": "forward", "speed": 150}
{"type": "move", "direction": "backward", "speed": 150}
{"type": "move", "direction": "left", "speed": 150}
{"type": "move", "direction": "right", "speed": 150}

// Parar
{"type": "stop"}

// Secuencia de movimientos (para gestos compuestos)
{
  "type": "move_sequence",
  "total_duration_ms": 2400,
  "steps": [
    {"direction": "rotate_right", "speed": 50, "duration_ms": 800},
    {"direction": "stop",         "speed": 0,  "duration_ms": 400},
    {"direction": "rotate_left",  "speed": 50, "duration_ms": 800},
    {"direction": "stop",         "speed": 0,  "duration_ms": 400}
  ]
}

// Control de LED
{"type": "light", "r": 0, "g": 255, "b": 0, "pattern": "solid"}
{"type": "light", "r": 255, "g": 0, "b": 0, "pattern": "blink"}

// Heartbeat (cada 1s desde Android)
{"type": "heartbeat", "timestamp": 1234567890}

// Solicitar telemetría
{"type": "telemetry"}
```

#### Formato de telemetría (ESP32 → Android)

```json
{
  "type": "telemetry",
  "timestamp": 1234567890,
  "battery": {"voltage": 7.2, "percentage": 75},
  "sensors": {
    "distance_front": 150,
    "distance_rear": 200
  },
  "motors": {"direction": "stop"},
  "leds": {"mode": "idle"},
  "heartbeat": {"brain_online": true},
  "uptime": 3600
}
```

### 6.2 Código — Etapa 4

#### `src/bluetooth/BLEServer.h`

```cpp
#pragma once
#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ArduinoJson.h>
#include "../config.h"

// Callbacks de comandos recibidos
typedef std::function<void(const char* direction, uint8_t speed)> MoveCallback;
typedef std::function<void()>                                      StopCallback;
typedef std::function<void(uint8_t r, uint8_t g, uint8_t b)>      LightCallback;
typedef std::function<void(JsonArray& steps)>                      SequenceCallback;

class RobotBLEServer : public BLEServerCallbacks, public BLECharacteristicCallbacks {
public:
  void begin();
  bool isConnected() const { return _connected; }
  void sendTelemetry(const String& json);
  void registerCallbacks(MoveCallback    onMove,
                         StopCallback    onStop,
                         LightCallback   onLight,
                         SequenceCallback onSequence);
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
  MoveCallback      _onMove;
  StopCallback      _onStop;
  LightCallback     _onLight;
  SequenceCallback  _onSequence;

  void handleCommand(const String& json);
};

extern RobotBLEServer bleServer;
```

#### `src/bluetooth/BLEServer.cpp`

```cpp
#include "BLEServer.h"

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

void RobotBLEServer::registerCallbacks(MoveCallback     onMove,
                                        StopCallback     onStop,
                                        LightCallback    onLight,
                                        SequenceCallback onSequence) {
  _onMove     = onMove;
  _onStop     = onStop;
  _onLight    = onLight;
  _onSequence = onSequence;
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

  } else if (strcmp(type, "move") == 0 && _onMove) {
    _onMove(doc["direction"] | "stop", doc["speed"] | 0);

  } else if (strcmp(type, "stop") == 0 && _onStop) {
    _onStop();

  } else if (strcmp(type, "light") == 0 && _onLight) {
    _onLight(doc["r"] | 0, doc["g"] | 0, doc["b"] | 0);

  } else if (strcmp(type, "move_sequence") == 0 && _onSequence) {
    JsonArray steps = doc["steps"];
    _onSequence(steps);
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

Direction parseDirection(const char* s) {
  if (strcmp(s, "forward")     == 0) return Direction::FORWARD;
  if (strcmp(s, "backward")    == 0) return Direction::BACKWARD;
  if (strcmp(s, "left")        == 0) return Direction::LEFT;
  if (strcmp(s, "right")       == 0) return Direction::RIGHT;
  if (strcmp(s, "rotate_left") == 0) return Direction::LEFT;
  if (strcmp(s, "rotate_right")== 0) return Direction::RIGHT;
  return Direction::STOP;
}

String buildTelemetry() {
  StaticJsonDocument<512> doc;
  doc["type"]      = "telemetry";
  doc["timestamp"] = millis();

  JsonObject batt = doc.createNestedObject("battery");
  batt["voltage"]    = battery.readVoltage();
  batt["percentage"] = battery.readPercentage();

  JsonObject sens = doc.createNestedObject("sensors");
  sens["distance_front"] = frontSensor.readCm();
  sens["distance_rear"]  = rearSensor.readCm();

  JsonObject heartbeat = doc.createNestedObject("heartbeat");
  heartbeat["brain_online"] = bleServer.isBrainOnline();

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
    // onMove
    [](const char* dir, uint8_t speed) {
      currentDir = parseDirection(dir);
      if (currentDir == Direction::STOP) {
        motors.stop();
        led.setMode(LEDMode::IDLE);
      } else {
        motors.move(currentDir, speed);
        led.setMode(LEDMode::MOVING);
      }
    },
    // onStop
    []() {
      currentDir = Direction::STOP;
      motors.stop();
      led.setMode(LEDMode::IDLE);
    },
    // onLight
    [](uint8_t r, uint8_t g, uint8_t b) {
      led.setCustom(r, g, b);
    },
    // onSequence
    [](JsonArray& steps) {
      for (JsonObject step : steps) {
        const char* dir   = step["direction"] | "stop";
        uint8_t     speed = step["speed"]     | 0;
        uint32_t    dur   = step["duration_ms"] | 0;
        Direction   d     = parseDirection(dir);
        if (d == Direction::STOP) {
          motors.stop();
          led.setMode(LEDMode::IDLE);
        } else {
          motors.move(d, speed);
          led.setMode(LEDMode::MOVING);
        }
        delay(dur);  // Bloquea — para producción se recomienda estado máquina
      }
      motors.stop();
      currentDir = Direction::STOP;
      led.setMode(LEDMode::IDLE);
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
6. Enviar: `{"type":"move","direction":"forward","speed":150}` → el robot avanza y el LED se pone verde.
7. Enviar: `{"type":"stop"}` → el robot se detiene.
8. Suscribirse a notificaciones en la característica `6E400003` (Notify). Cada 1 segundo debe llegar el JSON de telemetría con voltaje y distancias.
9. **Probar BRAIN_OFFLINE**: conectar con nRF Connect, mover el robot, y luego **no enviar heartbeats** durante 3 segundos. El robot debe:
   - Detenerse solo
   - El LED cambia a ámbar pulsante
   - Serial Monitor imprime `[SAFETY] BRAIN_OFFLINE → STOP + LED ámbar`
10. Enviar un heartbeat → el robot vuelve a IDLE con LED azul.

**Criterios de éxito**:
- ✅ El dispositivo aparece como `RobotESP32` al escanear
- ✅ Los comandos de movimiento mueven el robot correctamente
- ✅ La telemetría llega cada 1 segundo a nRF Connect
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

### 7.3 Conexión VL53L0X ↔ ESP32-S3

Los tres sensores comparten los pines I²C (SDA y SCL) pero cada uno tiene su propio pin XSHUT:

```
ESP32-S3        VL53L0X (los 3 comparten I²C)
────────        ──────────────────────────────
GPIO 21 (SDA) ──── SDA de los 3 sensores (bus compartido)
GPIO 22 (SCL) ──── SCL de los 3 sensores (bus compartido)
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

#### `src/sensors/CliffSensor.h`

```cpp
#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <VL53L0X.h>
#include "../config.h"

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
#include "CliffSensor.h"

// Direcciones I²C únicas para cada sensor
#define ADDR_CLIFF_FL 0x30
#define ADDR_CLIFF_FR 0x31
#define ADDR_CLIFF_RR 0x32

void CliffSensor::begin() {
  Wire.begin(I2C_SDA, I2C_SCL);

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
// Actualizar src/safety/SafetyMonitor.h para añadir CliffSensor
#pragma once
#include <Arduino.h>
#include "../sensors/DistanceSensor.h"
#include "../sensors/CliffSensor.h"
#include "../motors/MotorController.h"
#include "../config.h"

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
#include "SafetyMonitor.h"

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

Direction parseDirection(const char* s) {
  if (strcmp(s, "forward")     == 0) return Direction::FORWARD;
  if (strcmp(s, "backward")    == 0) return Direction::BACKWARD;
  if (strcmp(s, "left")        == 0) return Direction::LEFT;
  if (strcmp(s, "right")       == 0) return Direction::RIGHT;
  if (strcmp(s, "rotate_left") == 0) return Direction::LEFT;
  if (strcmp(s, "rotate_right")== 0) return Direction::RIGHT;
  return Direction::STOP;
}

String buildTelemetry() {
  StaticJsonDocument<512> doc;
  doc["type"]      = "telemetry";
  doc["timestamp"] = millis();

  JsonObject batt = doc.createNestedObject("battery");
  batt["voltage"]    = battery.readVoltage();
  batt["percentage"] = battery.readPercentage();

  JsonObject sens = doc.createNestedObject("sensors");
  sens["cliff_front_left"]  = cliff.readFL();
  sens["cliff_front_right"] = cliff.readFR();
  sens["cliff_rear"]        = cliff.readRR();
  sens["distance_front"]    = frontSensor.readCm();
  sens["distance_rear"]     = rearSensor.readCm();

  JsonObject hb = doc.createNestedObject("heartbeat");
  hb["brain_online"] = bleServer.isBrainOnline();

  doc["uptime"] = millis() / 1000;

  String out;
  serializeJson(doc, out);
  return out;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("=== MOJI ESP32 — Sistema Completo v1.0 ===");

  motors.begin();
  battery.begin();
  frontSensor.begin();
  rearSensor.begin();
  cliff.begin();           // ← Nuevo en Etapa 5
  led.begin();
  led.setMode(LEDMode::IDLE);

  bleServer.registerCallbacks(
    [](const char* dir, uint8_t speed) {
      if (cliffActive) { Serial.println("[SAFETY] Cliff activo — comando ignorado"); return; }
      currentDir = parseDirection(dir);
      if (currentDir == Direction::STOP) { motors.stop(); led.setMode(LEDMode::IDLE); }
      else                               { motors.move(currentDir, speed); led.setMode(LEDMode::MOVING); }
    },
    []() {
      currentDir = Direction::STOP;
      motors.stop();
      led.setMode(LEDMode::IDLE);
    },
    [](uint8_t r, uint8_t g, uint8_t b) { led.setCustom(r, g, b); },
    [](JsonArray& steps) {
      for (JsonObject step : steps) {
        if (cliffActive) break;
        Direction d = parseDirection(step["direction"] | "stop");
        uint8_t   s = step["speed"] | 0;
        uint32_t  t = step["duration_ms"] | 0;
        if (d == Direction::STOP) { motors.stop(); led.setMode(LEDMode::IDLE); }
        else                      { motors.move(d, s); led.setMode(LEDMode::MOVING); }
        delay(t);
      }
      motors.stop(); currentDir = Direction::STOP; led.setMode(LEDMode::IDLE);
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
2. Con nRF Connect, enviar comandos de movimiento normales. Verificar que la telemetría incluye los campos `cliff_front_left`, `cliff_front_right`, `cliff_rear` en `false`.
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
| 8  | Batería ADC | ADC1_CH7 — divisor 82kΩ/47kΩ |
| 11 | XSHUT VL53L0X Cliff Front-Left | control I²C address |
| 12 | XSHUT VL53L0X Cliff Front-Right | control I²C address |
| 13 | XSHUT VL53L0X Cliff Rear | control I²C address |
| 21 | I²C SDA (VL53L0X × 3) | Bus compartido |
| 22 | I²C SCL (VL53L0X × 3) | Bus compartido |
| 38 | LED RGB — Canal Rojo | PWM LEDC ch0, 220Ω serie |
| 39 | LED RGB — Canal Verde | PWM LEDC ch1, 220Ω serie |
| 40 | LED RGB — Canal Azul | PWM LEDC ch2, 220Ω serie |
| 41 | L298N IN1 — Motor Izq FWD | Salida digital |
| 42 | L298N IN2 — Motor Izq REV | Salida digital |
| 47 | L298N IN3 — Motor Der FWD | Salida digital |
| 48 | L298N IN4 — Motor Der REV | Salida digital |

**Pines reservados — NO usar**: GPIO 0, 3, 19, 20, 35, 36, 37, 45, 46.

---

*Documento autosuficiente — no requiere leer robot_architecture.md para implementar el firmware.*
