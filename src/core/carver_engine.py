"""
Deep file carver for unallocated disk space and raw sector streams.
Handles chunk streaming, signature matching across chunk boundaries, and file size detection.
"""
import io
from datetime import datetime
from typing import List, Generator, Callable, Optional

from src.core.models import RecoverableFile
from src.core.drive_reader import DriveReader
from src.carvers.signatures import ALL_CARVERS, BaseCarver


class DeepCarverEngine:
    """Carves deleted files from raw sector devices or logical volumes."""

    def __init__(self, target_path: str, chunk_size: int = 4 * 1024 * 1024):
        self.target_path = target_path
        self.chunk_size = chunk_size
        self.carvers: List[BaseCarver] = ALL_CARVERS
        self.is_cancelled = False

    def scan(self,
             progress_callback: Optional[Callable[[float, str], None]] = None,
             file_found_callback: Optional[Callable[[RecoverableFile], None]] = None) -> List[RecoverableFile]:
        """
        Scans the selected target. Yields found recoverable files and periodically updates progress.
        """
        results: List[RecoverableFile] = []

        with DriveReader(self.target_path) as reader:
            total_size = reader.total_size
            if total_size <= 0:
                total_size = 10 * 1024 * 1024 * 1024  # Default 10 GB limit

            current_offset = 0
            # Buffer overlap (64 KB) to avoid missing file signatures split across chunk boundaries
            overlap_size = 64 * 1024
            last_overlap = b""

            while current_offset < total_size and not self.is_cancelled:
                read_amount = min(self.chunk_size, total_size - current_offset)
                try:
                    data = reader.read_exact(current_offset, read_amount)
                except Exception as e:
                    # Sector read error or end of medium
                    current_offset += self.chunk_size
                    continue

                if not data:
                    break

                combined_chunk = last_overlap + data
                chunk_base_offset = current_offset - len(last_overlap)

                # Search signatures
                for carver in self.carvers:
                    for sig in carver.signatures:
                        sig_pos = 0
                        while not self.is_cancelled:
                            sig_pos = combined_chunk.find(sig, sig_pos)
                            if sig_pos == -1:
                                break

                            abs_file_offset = chunk_base_offset + sig_pos
                            
                            # Determine exact file size using streaming wrapper around DriveReader
                            file_size = self._probe_file_size(reader, carver, abs_file_offset)
                            if file_size and file_size > len(sig):
                                file_id = f"carve_{carver.file_type}_{abs_file_offset}"
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
                                rec_file = RecoverableFile(
                                    file_id=file_id,
                                    name=f"recovered_{abs_file_offset:010d}.{carver.file_type}",
                                    size=file_size,
                                    source_type="Deep Carved",
                                    status="Permanently Deleted",
                                    timestamp=now_str,
                                    location=f"{self.target_path} (Offset: 0x{abs_file_offset:08X})",
                                    metadata={
                                        "target": self.target_path,
                                        "offset": abs_file_offset,
                                        "size": file_size,
                                        "type": carver.file_type
                                    }
                                )
                                results.append(rec_file)
                                if file_found_callback:
                                    file_found_callback(rec_file)

                            sig_pos += max(1, len(sig))

                current_offset += len(data)
                last_overlap = data[-overlap_size:] if len(data) >= overlap_size else data

                if progress_callback:
                    pct = min(100.0, (current_offset / total_size) * 100.0)
                    progress_callback(pct, f"Scanned {current_offset // (1024*1024)} MB of {total_size // (1024*1024)} MB")

        return results

    def _probe_file_size(self, reader: DriveReader, carver: BaseCarver, start_offset: int) -> Optional[int]:
        """Wrap drive reader window in a virtual stream to allow carver to parse headers."""
        class StreamProbe:
            def __init__(self, drive_reader: DriveReader, base_pos: int):
                self.r = drive_reader
                self.base = base_pos
                self.curr = 0

            def seek(self, pos: int):
                self.curr = pos - self.base

            def read(self, n: int) -> bytes:
                try:
                    data = self.r.read_exact(self.base + self.curr, n)
                    self.curr += len(data)
                    return data
                except Exception:
                    return b""

        probe = StreamProbe(reader, start_offset)
        try:
            return carver.get_file_size(probe, start_offset)
        except Exception:
            return None
