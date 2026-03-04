from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class DecodeResult:
    """Result of a DataMatrix decode attempt."""

    content: str
    decoder_used: str
    decode_time_ms: float
    success: bool
    error_message: str | None = None


class DataMatrixDecoder(ABC):
    """Abstract base class for DataMatrix decoders."""

    @abstractmethod
    def decode(self, image: np.ndarray) -> list[DecodeResult]:
        ...

    @abstractmethod
    def name(self) -> str:
        ...
