"""
Recycle Bin parser for modern Windows ($I / $R file structure).
Supports both pre-Windows 10 (Format 1) and Windows 10/11 (Format 2).
Accurately categorizes items:
- "In Recycle Bin" when the corresponding $R payload file still exists.
- "Permanently Deleted" when the $R payload file has been purged/emptied, but the $I metadata index remains.
"""
import os
import struct
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import win32api

from src.core.models import RecoverableFile


class RecycleBinScanner:
    """Parses $Recycle.Bin structures across all logical volumes."""

    @staticmethod
    def filetime_to_datetime(filetime: int) -> str:
        """Converts Windows 64-bit FILETIME (100ns intervals since 1601-01-01) to readable string."""
        try:
            epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
            dt = epoch + timedelta(microseconds=filetime // 10)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def scan_all_drives(cls) -> List[RecoverableFile]:
        """Scans all system drive roots for $Recycle.Bin directories."""
        results: List[RecoverableFile] = []
        drives_mask = win32api.GetLogicalDrives()

        for i in range(26):
            if drives_mask & (1 << i):
                drive_letter = f"{chr(65 + i)}:\\"
                bin_path = os.path.join(drive_letter, "$Recycle.Bin")
                if os.path.exists(bin_path):
                    results.extend(cls.scan_recycle_path(bin_path))

        return results

    @classmethod
    def scan_recycle_path(cls, recycle_bin_path: str) -> List[RecoverableFile]:
        """Iterates through user SID subfolders and parses $I headers."""
        found_files: List[RecoverableFile] = []

        try:
            for root, dirs, files in os.walk(recycle_bin_path):
                for f_name in files:
                    if f_name.startswith("$I"):
                        i_path = os.path.join(root, f_name)
                        r_path = os.path.join(root, "$R" + f_name[2:])

                        entry = cls._parse_i_file(i_path, r_path)
                        if entry:
                            found_files.append(entry)
        except Exception as e:
            print(f"Error accessing Recycle Bin path {recycle_bin_path}: {e}")

        return found_files

    @classmethod
    def _parse_i_file(cls, i_file_path: str, r_file_path: str) -> Optional[RecoverableFile]:
        """Parses $I file format 1 (Win Vista/7) and format 2 (Win 8/10/11)."""
        try:
            with open(i_file_path, "rb") as f:
                data = f.read()

            if len(data) < 24:
                return None

            header_version = struct.unpack("<Q", data[0:8])[0]

            if header_version == 1:
                # Format 1: 8 bytes version, 8 bytes size, 8 bytes filetime, UTF-16LE string (max 260 chars)
                file_size = struct.unpack("<Q", data[8:16])[0]
                filetime = struct.unpack("<Q", data[16:24])[0]
                orig_path_raw = data[24:24 + 520]
                original_path = orig_path_raw.decode("utf-16le", errors="ignore").split("\x00")[0]
            elif header_version == 2:
                # Format 2: 8 bytes version, 8 bytes size, 8 bytes filetime, 4 bytes name char count, UTF-16LE
                file_size = struct.unpack("<Q", data[8:16])[0]
                filetime = struct.unpack("<Q", data[16:24])[0]
                if len(data) < 28:
                    return None
                char_count = struct.unpack("<I", data[24:28])[0]
                orig_path_raw = data[28:28 + (char_count * 2)]
                original_path = orig_path_raw.decode("utf-16le", errors="ignore").split("\x00")[0]
            else:
                return None

            if not original_path:
                original_path = os.path.basename(r_file_path)

            file_name = os.path.basename(original_path) or f"recovered_{os.path.basename(r_file_path)}"
            actual_exists = os.path.exists(r_file_path)
            actual_size = os.path.getsize(r_file_path) if actual_exists else file_size

            # If $R payload was emptied/deleted, it's Permanently Deleted (Purged from Recycle Bin)
            status_str = "In Recycle Bin" if actual_exists else "Permanently Deleted"
            source_str = "Recycle Bin" if actual_exists else "Recycle Bin (Purged)"

            return RecoverableFile(
                file_id=f"rb_{os.path.basename(i_file_path)}",
                name=file_name,
                size=actual_size,
                source_type=source_str,
                status=status_str,
                timestamp=cls.filetime_to_datetime(filetime),
                location=original_path,
                metadata={
                    "i_path": i_file_path,
                    "r_path": r_file_path,
                    "original_path": original_path,
                    "payload_exists": actual_exists,
                    "is_directory": os.path.isdir(r_file_path) if actual_exists else False
                }
            )
        except Exception:
            return None
