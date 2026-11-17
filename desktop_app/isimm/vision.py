import math
import queue
import time
import threading
from urllib.parse import urlsplit


class GazeTimer:
    def __init__(self, target=5.0, grace=0.35):
        self.target, self.grace = target, grace
        self.elapsed = 0.0
        self.last = self.seen = self.center = self.started = None
        self.latched = False

    def update(self, now, center):
        if self.seen is None or now - self.seen > self.grace:
            self.elapsed = 0.0
            self.last = self.center = self.started = None
            self.latched = False
        if center is None:
            self.last = None
            return 0 if not self.elapsed else self.elapsed / self.target, False
        if self.center and math.dist(self.center, center) > 0.14:
            self.elapsed = 0.0
            self.last = self.started = None
            self.latched = False
        if self.started is None:
            self.started = now
        if self.last is not None:
            self.elapsed = min(self.target, self.elapsed + (now - self.last))
        self.last = self.seen = now
        self.center = center
        fire = self.elapsed >= self.target and not self.latched
        self.latched |= fire
        return self.elapsed / self.target, fire


def geometry(faces, cfg, aspect=1.0):
    boxes = []
    for face in faces:
        xs, ys = [p.x for p in face], [p.y for p in face]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    if len(faces) != 1:
        return boxes, None, "Plusieurs visages" if faces else "Aucun visage"
    p = faces[0]
    # Ratios dans le repère du visage. Une paupière fermée invalide la mesure.
    if len(p) < 478:
        return boxes, None, "Iris indisponibles"
    nose, left, right = p[1], p[234], p[454]
    # Coordonnées dans le plan du visage, en unités de hauteur d’image.
    # La rotation du téléphone ne doit pas transformer la largeur en quasi-zéro.
    dx, dy = (right.x - left.x) * aspect, right.y - left.y
    width = math.hypot(dx, dy)
    if width < cfg.min_face * min(aspect, 1.0):
        return boxes, None, "Rapprochez-vous"
    ux, uy = dx / width, dy / width

    def horizontal(index):
        return (p[index].x - left.x) * aspect * ux + (p[index].y - left.y) * uy

    def vertical(index):
        return -(p[index].x - left.x) * aspect * uy + (p[index].y - left.y) * ux

    yaw = abs(horizontal(1) / width - 0.5)
    height = vertical(152) - vertical(10)
    if abs(height) < 0.001:
        return boxes, None, "Regard décalé"
    sign = math.copysign(1.0, height)
    pitch = (vertical(1) - vertical(10)) / height
    direct = yaw <= cfg.yaw and abs(pitch - cfg.pitch) <= 0.17
    for a, b, top, bottom, iris in [
        (33, 133, 159, 145, 468),
        (362, 263, 386, 374, 473),
    ]:
        start, end = horizontal(a), horizontal(b)
        span = abs(end - start)
        opening = sign * (vertical(bottom) - vertical(top))
        x = (horizontal(iris) - min(start, end)) / max(0.001, span)
        y = sign * (vertical(iris) - vertical(top)) / max(0.001, opening)
        direct &= (
            opening > span * 0.12 and abs(x - 0.5) <= cfg.iris and abs(y - 0.5) <= 0.35
        )
    return (
        boxes,
        ((left.x + right.x) / 2, nose.y) if direct else None,
        "Regard vers la caméra" if direct else "Regard décalé",
    )


def camera_worker(cfg, frames, events, stop, armed):
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    def publish(payload):
        try:
            frames.put_nowait(payload)
        except queue.Full:
            pass

    try:
        if urlsplit(cfg.camera).scheme not in ("http", "https", "rtsp"):
            raise ValueError("URL caméra invalide")
        opts = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=str(cfg.models / "face_landmarker.task")
            ),
            num_faces=3,
            running_mode=vision.RunningMode.VIDEO,
        )
        with vision.FaceLandmarker.create_from_options(opts) as detector:
            last_ms = 0
            latest = queue.Queue(1)

            def replace(frame):
                try:
                    latest.get_nowait()
                except queue.Empty:
                    pass
                latest.put_nowait(frame)

            def capture():
                while not stop.is_set():
                    cap = cv2.VideoCapture(
                        cfg.camera,
                        cv2.CAP_FFMPEG,
                        [
                            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                            2500,
                            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                            2000,
                        ],
                    )
                    try:
                        while cap.isOpened() and not stop.is_set():
                            ok, img = cap.read()
                            if not ok:
                                break
                            replace((time.monotonic(), img))
                    finally:
                        cap.release()
                    replace((time.monotonic(), None))
                    stop.wait(1.5)

            reader = threading.Thread(target=capture, daemon=True)
            reader.start()
            last_detection = 0.0
            timer = GazeTimer()
            while not stop.is_set():
                try:
                    now, img = latest.get(timeout=0.2)
                except queue.Empty:
                    continue
                if img is None:
                    timer = GazeTimer()
                    publish((None, "Flux coupé · reconnexion", 0))
                    continue
                if now - last_detection < (1 / 15 if armed.is_set() else 0.20):
                    continue
                last_detection = now
                h, w = img.shape[:2]
                img = cv2.resize(img, (480, max(1, round(480 * h / w))))
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                stamp = max(last_ms + 1, int(now * 1000))
                last_ms = stamp
                result = detector.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), stamp
                )
                boxes, center, label = geometry(
                    result.face_landmarks, cfg, img.shape[1] / img.shape[0]
                )
                if len(boxes) > 1:
                    timer = GazeTimer()
                progress, fire = timer.update(now, center)
                if fire and armed.is_set():
                    events.put(("gaze", now - timer.started))
                for x, y, x2, y2 in boxes:
                    cv2.rectangle(
                        img,
                        (int(x * img.shape[1]), int(y * img.shape[0])),
                        (int(x2 * img.shape[1]), int(y2 * img.shape[0])),
                        (160, 210, 48),
                        2,
                    )
                ok, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 68])
                if ok:
                    publish((jpeg.tobytes(), label, progress if armed.is_set() else 0))
            reader.join(2.8)
    except Exception as exc:
        events.put(
            (
                "notice",
                "Caméra indisponible · "
                + type(exc).__name__
                + " · activation manuelle disponible.",
            )
        )
    finally:
        frames.cancel_join_thread()
