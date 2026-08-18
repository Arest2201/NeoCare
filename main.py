"""
NeoCare Pro v2.0 - Sistema Principal de Monitoreo Neonatal de Dolor y Signos Vitales.

Uso:
  python main.py                      # Usar cámara web por defecto
  python main.py --video paciente.mp4 # Analizar archivo de video pregrabado
  python main.py --duration 120       # Monitorear durante 120 segundos
  python main.py --algo CHROM         # Algoritmo rPPG: CHROM, POS, GREEN
"""
import argparse
import os
import sys
import time
import cv2
import numpy as np
import warnings

# Configurar encoding UTF-8 seguro para terminales Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Suprimir advertencias deprecadas de librerías subyacentes
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message="SymbolDatabase.GetPrototype() is deprecated")

from neocare.config import NeoCareConfig
from neocare.core import (
    FaceTracker,
    FacialActionExtractor,
    RppgEngine,
    RespirationEngine,
    PainDistressClassifier
)
from neocare.ui import HudRenderer
from neocare.export import (
    MedicalDataLogger,
    ClinicalReportGenerator,
    generate_interactive_html
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NeoCare Pro - Monitoreo no invasivo de dolor neonatal y signos vitales"
    )
    parser.add_argument("--camera", type=int, default=0, help="Índice de la cámara web (default: 0)")
    parser.add_argument("--video", type=str, default=None, help="Ruta a archivo de video para análisis")
    parser.add_argument("--duration", type=int, default=60, help="Tiempo de observación en segundos (0 = indefinido)")
    parser.add_argument("--calib", type=int, default=5, help="Tiempo de calibración de cejas y FC en segundos")
    parser.add_argument("--algo", type=str, choices=["CHROM", "POS", "GREEN"], default="CHROM", help="Algoritmo rPPG")
    parser.add_argument("--width", type=int, default=1280, help="Ancho de captura de video")
    parser.add_argument("--height", type=int, default=720, help="Alto de captura de video")
    parser.add_argument("--output-dir", type=str, default="neocare_records", help="Directorio de reportes")
    parser.add_argument("--no-mesh", action="store_true", help="Ocultar la malla facial por defecto")
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Configuración general
    config = NeoCareConfig()
    config.DEFAULT_OBSERVATION_TIME = args.duration
    config.CALIBRATION_TIME = args.calib
    config.rppg.ALGORITHM = args.algo
    config.OUTPUT_DIR = os.path.abspath(args.output_dir)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("=" * 70)
    print("[*] NEOCARE PRO - SISTEMA DE MONITOREO NEONATAL NO INVASIVO")
    print(f"Version: 2.0 | Algoritmo rPPG: {config.rppg.ALGORITHM} | Calibracion: {config.CALIBRATION_TIME}s")
    print(f"Directorio de guardado: {config.OUTPUT_DIR}")
    print("=" * 70)

    # Inicializar captura de video
    if args.video:
        print(f"[*] Abriendo archivo de video: {args.video}")
        cap = cv2.VideoCapture(args.video)
    else:
        print(f"[*] Inicializando camara web (ID: {args.camera})...")
        cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print(f"[ERROR] No se pudo abrir la fuente de video (Camara/Archivo).")
        sys.exit(1)

    # Instanciar módulos del núcleo
    tracker = FaceTracker()
    facial_actions = FacialActionExtractor(thresholds=config.clinical)
    rppg = RppgEngine(config=config.rppg, clinical=config.clinical)
    respiration = RespirationEngine(config=config.rppg, clinical=config.clinical)
    pain_classifier = PainDistressClassifier(thresholds=config.clinical)
    hud = HudRenderer(config=config)
    logger = MedicalDataLogger(output_dir=config.OUTPUT_DIR)

    # Variables de control de bucle
    start_time = time.time()
    last_frame_time = start_time
    is_paused = False
    is_recording = True
    show_mesh = not args.no_mesh
    active_event_tag = ""
    event_display_timer = 0.0

    # Eventos clínicos predefinidos para rotación rápida
    clinical_events_cycle = [
        "Puncion de Talon (Heel Lance)",
        "Aspiracion de Via Aerea",
        "Cambio de Panal",
        "Consuelo / Contencion",
        "Reposo Basal"
    ]
    event_cycle_idx = 0

    print("\n[INSTRUCCIONES DE USO]")
    print(" - Manten el rostro en reposo durante los primeros segundos para calibrar la linea base.")
    print(" - [ESPACIO] : Pausar / Reanudar analisis")
    print(" - [C]       : Recalibrar linea base (Cejas / FC)")
    print(" - [E]       : Registrar evento clinico (ej. Puncion, Consuelo)")
    print(" - [M]       : Mostrar / Ocultar malla facial")
    print(" - [S]       : Guardar reporte instantaneo (Snapshot)")
    print(" - [Q / ESC] : Finalizar sesion y generar reportes clinicos completos\n")

    try:
        while True:
            current_time = time.time()
            dt = current_time - last_frame_time
            last_frame_time = current_time

            if not is_paused:
                ret, frame = cap.read()
                if not ret:
                    print("[INFO] Fin del video o desconexión de la cámara.")
                    break

                # Voltear horizontalmente si es cámara en vivo para efecto espejo natural
                if not args.video:
                    frame = cv2.flip(frame, 1)

                elapsed = current_time - start_time
                is_calibrating = elapsed < config.CALIBRATION_TIME

                # 1. Detección y rastreo facial 3D
                tracking_data = tracker.process(frame, timestamp=current_time)

                facial_eval = {}
                rppg_eval = {}
                resp_eval = {}
                pain_eval = {}

                if tracking_data:
                    pts_2d = tracking_data["landmarks_2d"]
                    ipd = tracking_data["ipd"]
                    head_pose = tracking_data["head_pose"]
                    rois = tracking_data["rois"]

                    # 2. Análisis de Unidades de Acción Facial (NFCS)
                    facial_eval = facial_actions.evaluate(
                        pts_2d=pts_2d,
                        ipd=ipd,
                        is_calibrating=is_calibrating
                    )

                    # 3. Procesamiento rPPG multicromático
                    rppg.add_frame_data(rois, timestamp=current_time, head_pose=head_pose)
                    rppg_eval = rppg.process(head_pose=head_pose)

                    # 4. Procesamiento de frecuencia respiratoria
                    luminance = tracking_data.get("luminance", 128.0)
                    respiration.add_sample(luminance, timestamp=current_time)
                    resp_eval = respiration.process()

                    # 5. Fusión multimodal y clasificación de dolor
                    pain_eval = pain_classifier.evaluate(
                        facial_eval=facial_eval,
                        rppg_eval=rppg_eval,
                        dt_seconds=max(0.01, dt)
                    )

                    # 6. Registro de datos en tiempo real
                    if is_recording:
                        logger.log_frame(
                            elapsed_seconds=elapsed,
                            rppg_eval=rppg_eval,
                            resp_eval=resp_eval,
                            facial_eval=facial_eval,
                            pain_eval=pain_eval,
                            tracking_data=tracking_data,
                            active_event=active_event_tag
                        )
                else:
                    # Rostro no detectado
                    facial_eval = {"is_calibrating": is_calibrating}
                    rppg_eval = {}
                    resp_eval = {}
                    pain_eval = {}

                # 7. Renderizar HUD médico
                display_frame = hud.render(
                    frame=frame,
                    tracking_data=tracking_data,
                    facial_eval=facial_eval,
                    rppg_eval=rppg_eval,
                    resp_eval=resp_eval,
                    pain_eval=pain_eval,
                    elapsed_time=elapsed,
                    is_paused=is_paused,
                    is_recording=is_recording,
                    show_mesh=show_mesh
                )

                # Limpiar etiqueta de evento temporal tras 3 segundos
                if active_event_tag and (current_time - event_display_timer) > 3.0:
                    active_event_tag = ""

                # Comprobar si se completó el tiempo de observación
                if config.DEFAULT_OBSERVATION_TIME > 0 and elapsed >= config.DEFAULT_OBSERVATION_TIME:
                    print(f"\n[INFO] Tiempo de observación completado ({config.DEFAULT_OBSERVATION_TIME}s).")
                    break

            # Mostrar ventana OpenCV
            cv2.imshow("NeoCare Pro - Neonatal Pain & Vitals Monitor", display_frame)

            # Gestión de teclas
            key = cv2.waitKey(1) & 0xFF
            if key in [ord("q"), ord("Q"), 27]:  # 'q' o ESC para salir
                break
            elif key == ord(" "):  # Espacio para pausar/reanudar
                is_paused = not is_paused
                print(f"[*] {'PAUSADO' if is_paused else 'REANUDADO'}")
            elif key in [ord("c"), ord("C")]:  # Recalibrar
                print("[*] Recalibrando línea base...")
                facial_actions.reset_calibration()
                rppg.reset()
                pain_classifier.reset()
                start_time = time.time()
            elif key in [ord("m"), ord("M")]:  # Alternar malla
                show_mesh = not show_mesh
            elif key in [ord("r"), ord("R")]:  # Alternar grabación
                is_recording = not is_recording
                print(f"[*] Grabación de telemetría: {'ACTIVADA' if is_recording else 'DESACTIVADA'}")
            elif key in [ord("e"), ord("E")]:  # Registrar evento clínico
                event_name = clinical_events_cycle[event_cycle_idx % len(clinical_events_cycle)]
                event_cycle_idx += 1
                active_event_tag = event_name
                event_display_timer = time.time()
                logger.log_clinical_event(
                    elapsed_seconds=time.time() - start_time,
                    event_name=event_name,
                    notes="Marcado por el operador clínico"
                )
                print(f"[EVENTO REGISTRADO] -> {event_name}")
            elif key in [ord("s"), ord("S")]:  # Guardar snapshot y reporte intermedio
                snap_path = os.path.join(config.OUTPUT_DIR, f"snapshot_{int(time.time())}.png")
                cv2.imwrite(snap_path, display_frame)
                print(f"[SNAPSHOT] Guardado en: {snap_path}")

    except KeyboardInterrupt:
        print("\n[INFO] Sesión interrumpida por el usuario.")

    finally:
        # Liberar recursos de cámara y ventanas
        cap.release()
        tracker.close()
        cv2.destroyAllWindows()

        print("\n" + "=" * 70)
        print("[*] GENERANDO INFORMES Y REPORTES CLINICOS FINALES...")
        print("=" * 70)

        # Generar resumen consolidado
        summary = logger.generate_summary()

        if "error" not in summary:
            # 1. Reporte Gráfico en Matplotlib (PNG + PDF)
            report_gen = ClinicalReportGenerator(thresholds=config.clinical)
            report_img_path = os.path.join(config.OUTPUT_DIR, f"{logger.session_id}_report.png")
            report_gen.generate_report(summary, logger.records, report_img_path)

            # 2. Reporte Web Interactivo HTML5
            report_html_path = os.path.join(config.OUTPUT_DIR, f"{logger.session_id}_interactive.html")
            generate_interactive_html(summary, logger.records, report_html_path)

            # 3. Mostrar resumen en consola
            v_stats = summary.get("vitals_statistics", {})
            p_stats = summary.get("pain_and_distress_metrics", {})
            print(f"\n[RESUMEN DE SESION: {logger.session_id}]")
            print(f" - Tiempo total observado: {summary.get('total_observed_seconds', 0)} s")
            print(f" - Total de muestras analizadas: {summary.get('total_samples', 0)}")
            print(f" - Frecuencia Cardiaca Media: {v_stats.get('heart_rate_mean_bpm', 'N/A')} bpm (Max: {v_stats.get('heart_rate_max_bpm', 'N/A')}, Min: {v_stats.get('heart_rate_min_bpm', 'N/A')})")
            print(f" - Variabilidad Cardiaca (RMSSD): {v_stats.get('hrv_rmssd_mean_ms', 'N/A')} ms")
            print(f" - Frecuencia Respiratoria Media: {v_stats.get('respiration_mean_brpm', 'N/A')} rpm")
            print(f" - NeoCare Distress Index (NDI) Medio: {p_stats.get('ndi_mean', 0.0)} / 10 (Pico: {p_stats.get('ndi_max', 0.0)})")
            print(f" - Tiempo total en dolor / estres: {p_stats.get('time_in_pain_seconds', 0.0)} s ({p_stats.get('time_in_pain_percentage', 0.0)}%)")
            print(f" - Area bajo la curva de dolor (AUC): {p_stats.get('pain_auc_score', 0.0)}")

            print("\n[ARCHIVOS GENERADOS]")
            print(f" 1. Telemetria CSV:        {logger.csv_filename}")
            print(f" 2. Resumen JSON:          {logger.json_filename}")
            print(f" 3. Graficos Clinicos PNG: {report_img_path}")
            print(f" 4. Reporte Clinico PDF:   {os.path.splitext(report_img_path)[0] + '.pdf'}")
            print(f" 5. Dashboard HTML5:       {report_html_path}")
            print("=" * 70)
        else:
            print("[INFO] No se registraron suficientes datos para generar los reportes.")


if __name__ == "__main__":
    main()
