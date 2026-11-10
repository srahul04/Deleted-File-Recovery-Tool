"""
Core models and data structures for data recovery operations.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class RecoverableFile:
    file_id: str
    name: str
    size: int
    source_type: str  # "Recycle Bin" or "Deep Carved"
    status: str       # "In Recycle Bin" or "Permanently Deleted"
    timestamp: str    # "YYYY-MM-DD HH:MM:SS"
    location: str     # Path or sector offset description
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def formatted_size(self) -> str:
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.2f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.2f} MB"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.2f} GB"
