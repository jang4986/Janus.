"""Pipeline AI phân tích nội dung video của backend.

- ``app.ai.pipeline.analyse_video``: điểm vào duy nhất mà service sử dụng.
- ``app.ai.nsfw``: adapter cho NSFW-Detection (Adult) — đã triển khai.
- ``app.ai.placeholders``: các detector chưa triển khai (violence, sound, text).
"""

from app.ai.base import (
    AnalysisReport,
    Detection,
    DetectorNotImplementedError,
    DetectorUnavailableError,
)

__all__ = [
    "AnalysisReport",
    "Detection",
    "DetectorNotImplementedError",
    "DetectorUnavailableError",
]
