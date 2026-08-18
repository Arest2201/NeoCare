# NeoCare Pro v2.0 - Sistema No Invasivo de Detección de Dolor y Signos Vitales Neonatales

**NeoCare Pro** es una plataforma médica de vanguardia basada en Visión por Computadora e Inteligencia Artificial para el monitoreo continuo, en tiempo real y sin contacto del dolor, estrés y signos vitales (Frecuencia Cardíaca, Variabilidad Cardíaca y Respiración) en pacientes neonatales y pediátricos.

---

## Fundamentación Clínica y Algorítmica

NeoCare implementa las escalas clínicas validadas de neonatología:
1. **NFCS (Neonatal Facial Coding System)**:
   - **AU4 (Brow Bulge / Ceño Fruncido)**: Acercamiento medial y descenso de cejas.
   - **AU6/7 (Eye Squeeze / Cierre Ocular Forzado)**: Reducción del Eye Aspect Ratio (EAR) y elevación infraorbital.
   - **AU9/10 (Nasolabial Furrow / Surco Nasolabial)**: Profundización del surco y elevación de las comisuras alares nasales.
   - **AU25/27 (Mouth Stretch & Open Lips / Boca Abierta y Estirada)**: Apertura y distorsión labial medida con el Mouth Aspect Ratio (MAR).
2. **rPPG Multicromático (CHROM / POS)**:
   - Extracción de fotopletismografía remota en múltiples regiones de interés (frente y mejillas) con cancelación de artefactos de iluminación.
   - Filtrado pasa-banda Butterworth orden 4 (0.7 - 3.5 Hz) para rangos neonatales (42 a 210 bpm).
   - Cálculo de **Variabilidad de la Frecuencia Cardíaca (VFC / HRV: RMSSD y SDNN)** como biomarcador de estrés autonómico y tono vagal.
3. **Frecuencia Respiratoria Óptica (FR / BrPM)**:
   - Estimación no invasiva de respiraciones por minuto mediante modulación de amplitud/frecuencia del pulso arterial y micro-movimientos.
4. **NeoCare Distress Index (NDI 0-10)**:
   - Índice continuo multimodal que fusiona la expresión facial NFCS (70%) con la respuesta fisiológica autonómica (30%).
   - Clasificación en cuatro estados clínicos:
     - 🟢 **0.0 - 2.5**: Relajado / Confort
     - 🟡 **2.6 - 4.5**: Molestia Leve
     - 🟠 **4.6 - 6.5**: Dolor Moderado
     - 🔴 **6.6 - 10.0**: Dolor Severo / Crisis (Alarma visual)

---

## 🖥️ Interfaz de Monitor de UCI Neonatal (HUD)

El sistema superpone un panel de telemetría médica en tiempo real:
- **Osciloscopio PPG**: Visualización en vivo de la onda de pulso de volumen sanguíneo (BVP).
- **Desglose NFCS**: Barras de intensidad en tiempo real para AU4, AU6, AU9 y AU25.
- **Medidor Maestro NDI**: Gauge graduado con categorías dinámicas y colores hospitalarios.
- **Signos Vitales**: FC en tiempo real (BPM), VFC (RMSSD en ms), Respiración (rpm) y Calidad de Señal rPPG (SNR).

---

## ⌨️ Controles por Teclado en Vivo

| Tecla | Acción |
|---|---|
| `[ESPACIO]` | **Pausar / Reanudar** el procesamiento y captura de video |
| `[C]` | **Recalibrar línea base** de cejas, boca y frecuencia cardíaca |
| `[E]` | **Registrar evento clínico** (Punción de talón, aspiración, consuelo, etc.) |
| `[M]` | **Mostrar / Ocultar** la malla facial 3D (*FaceMesh*) |
| `[S]` | **Guardar instantánea (Snapshot)** de la pantalla actual |
| `[R]` | **Activar / Desactivar** la grabación de telemetría a CSV |
| `[Q]` o `[ESC]` | **Finalizar sesión** y exportar reportes automáticos |

---

## Reportes Clínicos y Auditoría

Al concluir cada sesión, NeoCare genera automáticamente en `neocare_records/`:
1. **Reporte Gráfico en Alta Resolución (`.png` y `.pdf`)**:
   - Panel 1: Frecuencia Cardíaca con zonas fisiológicas (normal, taquicardia, bradicardia).
   - Panel 2: Variabilidad Cardíaca (RMSSD) y Frecuencia Respiratoria (rpm).
   - Panel 3: Desglose temporal de Unidades de Acción Facial NFCS.
   - Panel 4: NeoCare Distress Index (NDI) con marcadores de intervenciones médicas.
2. **Dashboard Web Interactivo (`.html`)**:
   - Reporte responsivo con gráficos dinámicos interactivos basados en *Chart.js*.
3. **Telemetría en Tiempo Real (`.csv`)**:
   - Registro segundo a segundo de todas las variables biomédicas para investigación o IA.
4. **Resumen Ejecutivo (`.json`)**:
   - Estadísticas consolidadas: tiempo en dolor, AUC de dolor, FC promedio/máxima/mínima y eventos clínicos.

---

## Instalación y Uso

### 1. Requisitos previos
Instalar dependencias:
```bash
pip install -r requirements.txt
```

### 2. Ejecutar con Cámara Web en Vivo
```bash
python main.py
```

### 3. Opciones de Línea de Comandos
```bash
# Analizar un archivo de video pregrabado
python main.py --video ruta/al/video_paciente.mp4

# Establecer tiempo de observación (ej. 120 segundos)
python main.py --duration 120

# Cambiar algoritmo rPPG (CHROM, POS o GREEN)
python main.py --algo CHROM

# Especificar tiempo de calibración inicial (ej. 10 segundos)
python main.py --calib 10

# Especificar carpeta de salida personalizada
python main.py --output-dir reportes_paciente_01
```

---

## Estructura del Proyecto

```
neocare/
├── neocare/
│   ├── config.py                 # Parámetros clínicos, rPPG y tema visual
│   ├── core/
│   │   ├── face_tracker.py       # MediaPipe FaceMesh + One-Euro Filter + Pose 3D
│   │   ├── facial_actions.py     # Extracción de Unidades de Acción Facial NFCS
│   │   ├── rppg_engine.py        # Motor rPPG CHROM/POS + Filtro Butterworth + HRV
│   │   ├── respiration_engine.py # Estimación de Frecuencia Respiratoria
│   │   └── pain_classifier.py    # Fusión multimodal NFCS + rPPG + PIPP-R
│   ├── ui/
│   │   ├── widgets.py            # Componentes gráficos de alta definición
│   │   └── hud_overlay.py        # Renderizador del HUD médico completo
│   ├── export/
│   │   ├── data_logger.py        # Registro en tiempo real en CSV y JSON
│   │   ├── clinical_report.py    # Generador de gráficos multipanel Matplotlib
│   │   └── interactive_html.py   # Dashboard web interactivo HTML5 + Chart.js
│   └── utils/
│       ├── geometry.py           # Distancias 3D, IPD y cálculo de pose cefálica
│       └── signal_processing.py  # Filtros digitales SOS, FFT, SNR y picos
├── tests/
│   └── test_neocare.py           # Suite de pruebas unitarias
├── main.py                       # Aplicación interactiva principal
├── requirements.txt              # Dependencias de Python
└── README.md                     # Manual y documentación técnica
```
