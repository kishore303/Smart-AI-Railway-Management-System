from abc import ABC, abstractmethod
from typing import Any, Dict


class BasePredictor(ABC):
    @abstractmethod
    def validate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and coerce features. Raises ValueError on invalid."""
        raise NotImplementedError

    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Returns dict with prediction and metadata. Validates internally."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_type(self) -> str:
        raise NotImplementedError

    @property
    def is_demo(self) -> bool:
        return False

    @property
    def artifact_filename(self) -> str:
        return ""

    @property
    def version(self) -> str:
        return "1.0"
