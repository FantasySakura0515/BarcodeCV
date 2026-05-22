from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class Frame:
    """Captured frame with metadata."""

    image: np.ndarray
    timestamp: datetime
    camera_id: str
    resolution: tuple[int, int]
    metadata: dict = field(default_factory=dict)


class CameraSource(ABC):
    """Abstract base class for camera sources."""

    @abstractmethod
    def open(self) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def capture_frame(self) -> Frame:
        ...

    @abstractmethod
    def is_open(self) -> bool:
        ...

    @abstractmethod
    def get_resolution(self) -> tuple[int, int]:
        ...

    @abstractmethod
    def set_resolution(self, width: int, height: int) -> None:
        ...

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
