"""
Recovery manager that performs safe physical file extraction and Recycle Bin restoration.
"""
import os
import shutil
import subprocess
from typing import Optional, Callable
from src.core.models import RecoverableFile
from src.core.drive_reader import DriveReader


class RecoveryManager:
    """Manages file extraction to target restoration folders."""

    @staticmethod
    def recover_file(file_entry: RecoverableFile,
                     destination_dir: str,
                     progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """Restores a given file entry (Recycle Bin or Deep Carved). Returns saved file path."""
        os.makedirs(destination_dir, exist_ok=True)

        if file_entry.source_type == "Recycle Bin":
            return RecoveryManager._recover_from_recycle_bin(file_entry, destination_dir, progress_callback)
        else:
            return RecoveryManager._recover_from_raw_device(file_entry, destination_dir, progress_callback)

    @staticmethod
    def _recover_from_recycle_bin(file_entry: RecoverableFile,
                                  destination_dir: str,
                                  progress_callback: Optional[Callable[[float], None]] = None) -> str:
        r_path = file_entry.metadata.get("r_path")
        is_dir = file_entry.metadata.get("is_directory", False)

        if not r_path or not os.path.exists(r_path):
            raise FileNotFoundError(f"Underlying Recycle Bin container missing: {r_path}")

        target_name = file_entry.name or "recovered_item"
        # Sanitize filename
        safe_name = "".join(c for c in target_name if c.isalnum() or c in (" ", "-", "_", "."))
        dest_path = RecoveryManager._unique_destination(destination_dir, safe_name)

        if is_dir:
            shutil.copytree(r_path, dest_path, dirs_exist_ok=True)
            if progress_callback:
                progress_callback(100.0)
            return dest_path
        else:
            total_size = os.path.getsize(r_path)
            copied = 0
            with open(r_path, "rb") as src, open(dest_path, "wb") as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    copied += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback((copied / total_size) * 100.0)
            return dest_path

    @staticmethod
    def _recover_from_raw_device(file_entry: RecoverableFile,
                                 destination_dir: str,
                                 progress_callback: Optional[Callable[[float], None]] = None) -> str:
        target_path = file_entry.metadata.get("target")
        offset = file_entry.metadata.get("offset")
        size = file_entry.metadata.get("size")

        if not target_path or offset is None or not size:
            raise ValueError("Incomplete metadata for sector-level file restoration.")

        dest_path = RecoveryManager._unique_destination(destination_dir, file_entry.name)

        with DriveReader(target_path) as reader:
            bytes_left = size
            copied = 0
            chunk_size = 512 * 1024  # 512 KB chunks

            with open(dest_path, "wb") as dst:
                while bytes_left > 0:
                    read_len = min(chunk_size, bytes_left)
                    data = reader.read_exact(offset + copied, read_len)
                    if not data:
                        break
                    dst.write(data)
                    copied += len(data)
                    bytes_left -= len(data)
                    if progress_callback:
                        progress_callback((copied / size) * 100.0)

        if os.path.exists(dest_path) and os.path.getsize(dest_path) == 0:
            os.remove(dest_path)
            raise ValueError("Extracted file is empty.")

        return dest_path

    @staticmethod
    def _unique_destination(dest_dir: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(dest_dir, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{base}_{counter}{ext}")
            counter += 1
        return candidate
