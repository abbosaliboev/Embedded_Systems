"""
Jetson Nano — AI Vision detector.
Runs YOLOv5 (via torch.hub) if available, otherwise sends raw frames.
Sends annotated JPEG frames + detection results to Raspberry Pi.

Compatible with Python 3.6+ and runs without ultralytics package.
"""

import base64
import time
import logging
import sys
from datetime import datetime

import cv2
import requests

_session = requests.Session()   # persistent connection — avoids TCP handshake per frame

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

PI_BASE_URL   = "http://10.198.137.204:5000"
CAMERA_INDEX  = 0
CONFIDENCE    = 0.50
INFERENCE_FPS = 5
FRAME_FPS     = 10      # frame send rate (can be higher than inference)
JPEG_QUALITY  = 40   # lower = faster transfer, still clear enough

# Danger zone (x1, y1, x2, y2) in pixels
DANGER_ZONE = (160, 80, 480, 400)

# ── Load YOLO model ──────────────────────────────────────────────────────────

model = None

def _load_model():
    global model
    try:
        import torch
        logger.info("Loading YOLOv5n via torch.hub...")
        model = torch.hub.load("ultralytics/yolov5", "yolov5n",
                               pretrained=True, trust_repo=True, verbose=False)
        model.conf = CONFIDENCE
        model.classes = [0]   # person only
        logger.info("YOLOv5n loaded")
    except Exception as e:
        logger.warning("torch / YOLOv5 not available — sending raw frames only. (%s)", e)
        model = None

_load_model()

# ── Helpers ──────────────────────────────────────────────────────────────────

def box_in_zone(x1, y1, x2, y2, zone):
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    zx1, zy1, zx2, zy2 = zone
    return zx1 <= cx <= zx2 and zy1 <= cy <= zy2


def run_inference(frame):
    """Returns (person_detected, in_danger_zone, best_conf, list_of_boxes)."""
    if model is None:
        return False, False, 0.0, []
    try:
        results = model(frame)
        detections = results.xyxy[0].cpu().numpy()  # [x1,y1,x2,y2,conf,cls]
        person_detected = False
        in_danger_zone  = False
        best_conf       = 0.0
        boxes = []
        for *xyxy, conf, cls in detections:
            if int(cls) != 0 or conf < CONFIDENCE:
                continue
            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
            person_detected = True
            in_zone = box_in_zone(x1, y1, x2, y2, DANGER_ZONE)
            if in_zone:
                in_danger_zone = True
            best_conf = max(best_conf, float(conf))
            boxes.append((x1, y1, x2, y2, float(conf), in_zone))
        return person_detected, in_danger_zone, best_conf, boxes
    except Exception as e:
        logger.error("Inference error: %s", e)
        return False, False, 0.0, []


def draw_frame(frame, boxes, in_danger_zone):
    out = frame.copy()
    h, w = out.shape[:2]

    # Danger zone
    dz_col = (0, 0, 220) if in_danger_zone else (0, 180, 0)
    zx1, zy1, zx2, zy2 = DANGER_ZONE
    cv2.rectangle(out, (zx1, zy1), (zx2, zy2), dz_col, 2)
    cv2.putText(out, "DANGER ZONE", (zx1 + 4, zy1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, dz_col, 1)

    # Bounding boxes
    for x1, y1, x2, y2, conf, in_zone in boxes:
        col = (0, 0, 255) if in_zone else (0, 255, 0)
        cv2.rectangle(out, (x1, y1), (x2, y2), col, 2)
        label = f"Person {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(out, (x1, y1 - th - 6), (x1 + tw + 4, y1), col, -1)
        cv2.putText(out, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Status bar
    status = "ALERT" if in_danger_zone else ("MONITORING" if model else "NO YOLO")
    col = (0, 0, 255) if in_danger_zone else (0, 200, 0)
    cv2.putText(out, f"Smart Safety Guard | {status}",
                (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)

    # Timestamp
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(out, ts, (8, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (160, 160, 160), 1)
    return out, ts


def send_frame(frame_bgr, timestamp):
    ok, buf = cv2.imencode(".jpg", frame_bgr,
                            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        return
    payload = {
        "image_b64": base64.b64encode(buf.tobytes()).decode(),
        "timestamp": timestamp,
    }
    try:
        _session.post(f"{PI_BASE_URL}/api/frame", json=payload, timeout=2)
    except Exception:
        pass


def post_detection(person, in_zone, conf, ts):
    payload = {
        "person_detected": person,
        "in_danger_zone": in_zone,
        "confidence": round(conf, 3),
        "timestamp": ts,
    }
    try:
        resp = _session.post(f"{PI_BASE_URL}/api/detection", json=payload, timeout=2)
        if resp.status_code == 200:
            logger.info("Sent: person=%s zone=%s conf=%.0f%%",
                        person, in_zone, conf * 100)
    except Exception as e:
        logger.error("Pi unreachable: %s", e)


# ── Main loop ────────────────────────────────────────────────────────────────

def run():
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        logger.error("Cannot open camera %d", CAMERA_INDEX)
        sys.exit(1)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info("Camera %dx%d | YOLO: %s | PI: %s",
                w, h, "YES" if model else "NO", PI_BASE_URL)

    infer_interval = 1.0 / INFERENCE_FPS
    frame_interval = 1.0 / FRAME_FPS
    last_infer = 0.0
    last_frame = 0.0
    last_state = None
    last_boxes = []
    last_in_zone = False

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.warning("Frame read failed, retrying...")
            time.sleep(0.5)
            continue

        now = time.time()
        annotated, ts = draw_frame(frame, last_boxes, last_in_zone)

        # Run YOLO inference at configured FPS
        if model and (now - last_infer) >= infer_interval:
            last_infer = now
            person, in_zone, conf, boxes = run_inference(frame)
            last_boxes   = boxes
            last_in_zone = in_zone
            annotated, ts = draw_frame(frame, boxes, in_zone)

            state = (person, in_zone)
            if state != last_state:
                if person:
                    post_detection(person, in_zone, conf, ts)
                last_state = state

        # Send annotated frame to Pi dashboard
        if (now - last_frame) >= frame_interval:
            last_frame = now
            send_frame(annotated, ts)

        time.sleep(0.02)

    cap.release()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true",
                        help="Run danger zone calibration")
    args = parser.parse_args()

    if args.calibrate:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        ret, frame = cap.read()
        print(f"Frame size: {frame.shape[1]}x{frame.shape[0]}")
        print(f"Current DANGER_ZONE = {DANGER_ZONE}")
        cap.release()
    else:
        run()
