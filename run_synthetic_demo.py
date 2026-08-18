"""
Script de demostración y simulación para NeoCare Pro v2.0.
Genera una sesión sintética de 30 segundos con simulación de reposo, punción de talón y recuperación.
"""
import os
import sys
import time
import numpy as np

# Configurar encoding UTF-8 seguro para terminales Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from neocare.config import NeoCareConfig
from neocare.export import (
    MedicalDataLogger,
    ClinicalReportGenerator,
    generate_interactive_html
)


def run_simulation(output_dir: str = "neocare_records"):
    config = NeoCareConfig()
    config.OUTPUT_DIR = os.path.abspath(output_dir)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("=" * 70)
    print("[*] INICIANDO SIMULACION CLINICA NEOCARE PRO")
    print("Escenario: Reposo inicial (0-10s) -> Puncion de talon (10-20s) -> Consuelo (20-30s)")
    print("=" * 70)

    logger = MedicalDataLogger(output_dir=config.OUTPUT_DIR, session_id="demo_clinical_simulation")

    duration = 30.0
    fps = 30.0
    n_frames = int(duration * fps)

    for i in range(n_frames):
        t = i / fps

        # Simulación de respuesta fisiológica y facial según fase clínica
        if t < 10.0:
            # Fase 1: Reposo y confort basal
            phase = "Reposo Basal"
            hr = 135.0 + 2.0 * np.sin(2 * np.pi * 0.2 * t) + np.random.normal(0, 0.5)
            rmssd = 32.0 + np.random.normal(0, 1.5)
            brpm = 42.0 + np.random.normal(0, 0.8)
            au4 = 0
            au6 = 0
            au9 = 0
            au25 = 0
            ndi_raw = 0.8 + np.random.uniform(0, 0.4)
            ndi_smooth = 1.0 + 0.2 * np.sin(t)
            cat = "RELAJADO / CONFORT"
            alarm = False

        elif t < 20.0:
            # Fase 2: Punción de talón (Heel Lance) - Dolor agudo y taquicardia
            phase = "Punción de Talón (Dolor Agudo)"
            if t == 10.0 or (i == int(10.0 * fps)):
                logger.log_clinical_event(t, "Punción de Talón", "Procedimiento invasivo doloroso")

            # Aumento reactivo de FC y caída de VFC
            progress = (t - 10.0) / 10.0
            hr = 140.0 + 45.0 * np.sin(progress * np.pi) + np.random.normal(0, 1.2)
            rmssd = max(8.0, 30.0 - 20.0 * np.sin(progress * np.pi) + np.random.normal(0, 0.8))
            brpm = 58.0 + np.random.normal(0, 1.5)

            # Activación de Unidades de Acción Facial NFCS
            au4 = 2 if progress < 0.7 else 3  # Ceño fruncido
            au6 = 3  # Cierre forzado de ojos
            au9 = 2  # Surco nasolabial acentuado
            au25 = 2 if progress < 0.5 else 3 # Llanto / Boca estirada

            ndi_raw = 7.5 + 1.8 * np.sin(progress * np.pi) + np.random.normal(0, 0.3)
            ndi_smooth = min(9.5, 6.8 + 2.4 * np.sin(progress * np.pi))
            cat = "DOLOR SEVERO / CRISIS"
            alarm = True

        else:
            # Fase 3: Consuelo y recuperación
            phase = "Consuelo y Contención"
            if t == 20.0 or (i == int(20.0 * fps)):
                logger.log_clinical_event(t, "Consuelo / Succión no nutritiva", "Intervención analgésica no farmacológica")

            decay = (30.0 - t) / 10.0
            hr = 138.0 + 25.0 * decay + np.random.normal(0, 0.8)
            rmssd = 18.0 + 12.0 * (1.0 - decay) + np.random.normal(0, 1.0)
            brpm = 44.0 + np.random.normal(0, 1.0)

            au4 = 1 if decay > 0.5 else 0
            au6 = 1 if decay > 0.4 else 0
            au9 = 1 if decay > 0.6 else 0
            au25 = 0

            ndi_raw = 2.0 + 3.0 * decay + np.random.normal(0, 0.3)
            ndi_smooth = 2.0 + 2.8 * decay
            cat = "MOLESTIA LEVE" if ndi_smooth > 2.5 else "RELAJADO / CONFORT"
            alarm = False

        rppg_data = {
            "bpm": float(hr),
            "snr_db": 8.5,
            "signal_quality_pct": 92,
            "hrv": {"rmssd": float(rmssd), "sdnn": float(rmssd * 1.15)}
        }
        resp_data = {"brpm": float(brpm)}
        facial_data = {
            "is_calibrating": False,
            "scores": {
                "au4_brow_bulge": au4,
                "au6_eye_squeeze": au6,
                "au9_nasolabial": au9,
                "au25_mouth_stretch": au25,
                "nfcs_total_visual": au4 + au6 + au9 + au25
            },
            "intensities": {
                "brow_intensity": au4 / 3.0,
                "eye_intensity": au6 / 3.0,
                "nasolabial_intensity": au9 / 3.0,
                "mouth_intensity": au25 / 3.0
            }
        }
        pain_data = {
            "ndi_score": float(ndi_raw),
            "ndi_smooth": float(ndi_smooth),
            "category": cat,
            "alarm_triggered": alarm,
            "physio_score": 3 if hr > 165 else 0
        }
        track_data = {"head_pose": {"pitch": 1.2, "yaw": 0.8, "roll": 0.3}}

        logger.log_frame(
            elapsed_seconds=t,
            rppg_eval=rppg_data,
            resp_eval=resp_data,
            facial_eval=facial_data,
            pain_eval=pain_data,
            tracking_data=track_data,
            active_event=""
        )

    # Consolidar y exportar
    summary = logger.generate_summary()

    report_gen = ClinicalReportGenerator(thresholds=config.clinical)
    report_img_path = os.path.join(config.OUTPUT_DIR, f"{logger.session_id}_report.png")
    report_gen.generate_report(summary, logger.records, report_img_path)

    report_html_path = os.path.join(config.OUTPUT_DIR, f"{logger.session_id}_interactive.html")
    generate_interactive_html(summary, logger.records, report_html_path)

    print("\n[OK] SIMULACION CLINICA COMPLETADA EXITOSAMENTE")
    print(f" - Grafico Clinico PNG: {report_img_path}")
    print(f" - Reporte Clinico PDF: {os.path.splitext(report_img_path)[0] + '.pdf'}")
    print(f" - Dashboard HTML5:     {report_html_path}")
    print(f" - Telemetria CSV:      {logger.csv_filename}")
    print(f" - Resumen JSON:        {logger.json_filename}")


if __name__ == "__main__":
    run_simulation()
