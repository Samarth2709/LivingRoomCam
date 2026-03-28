from __future__ import annotations

from dataclasses import dataclass
import importlib

from .types import FaceDetection, FrameAnalysis


class VisionBackend:
    name = "noop"

    def analyze_frame(self, jpeg_bytes: bytes) -> FrameAnalysis:
        return FrameAnalysis(width=0, height=0, detections=[], backend_name=self.name)


class NoopVisionBackend(VisionBackend):
    name = "noop"


@dataclass
class OpenCvHaarBackend(VisionBackend):
    name: str = "opencv_haar"

    def __post_init__(self) -> None:
        cv2 = importlib.import_module("cv2")
        self._cv2 = cv2
        self._np = importlib.import_module("numpy")
        self._cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if self._cascade.empty():
            raise RuntimeError("Unable to load OpenCV Haar cascade")

    def analyze_frame(self, jpeg_bytes: bytes) -> FrameAnalysis:
        np = self._np
        cv2 = self._cv2
        array = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return FrameAnalysis(width=0, height=0, detections=[], backend_name=self.name)
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(60, 60),
        )
        detections: list[FaceDetection] = []
        for x, y, w, h in faces:
            crop = image[y : y + h, x : x + w]
            crop_gray = gray[y : y + h, x : x + w]
            quality = self._quality(crop_gray, width * height, w * h)
            embedding = self._embedding(crop_gray)
            ok, encoded = cv2.imencode(".jpg", crop)
            detections.append(
                FaceDetection(
                    bbox=(int(x), int(y), int(w), int(h)),
                    quality=quality,
                    embedding=embedding,
                    crop_jpeg=encoded.tobytes() if ok else None,
                )
            )
        return FrameAnalysis(width=width, height=height, detections=detections, backend_name=self.name)

    def _embedding(self, gray_crop) -> list[float]:
        cv2 = self._cv2
        np = self._np
        resized = cv2.resize(gray_crop, (16, 16))
        vector = resized.astype("float32").reshape(-1)
        vector -= vector.mean()
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector.tolist()

    def _quality(self, gray_crop, frame_area: int, crop_area: int) -> float:
        cv2 = self._cv2
        sharpness = float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())
        area_ratio = crop_area / max(1, frame_area)
        score = min(1.0, sharpness / 500.0) * min(1.0, area_ratio * 10.0)
        return round(score, 4)


def build_backend(name: str) -> VisionBackend:
    if name == "noop":
        return NoopVisionBackend()
    if name == "opencv_haar":
        return OpenCvHaarBackend()
    raise ValueError(f"Unsupported vision backend: {name}")
