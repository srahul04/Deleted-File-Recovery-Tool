"""
Base file carving interfaces and signature catalog.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Tuple
import io


class BaseCarver(ABC):
    """Abstract base class for format-specific carvers."""
    
    file_type: str = "bin"
    signatures: List[bytes] = []

    @abstractmethod
    def get_file_size(self, stream, start_offset: int, max_search_size: int = 100 * 1024 * 1024) -> Optional[int]:
        """
        Calculates the exact or bounded size of the file starting at start_offset.
        Returns size in bytes or None if invalid.
        """
        pass

    def validate_content(self, data: bytes) -> bool:
        """Optional heuristic check to confirm extracted header and body validity."""
        return len(data) >= len(self.signatures[0])
