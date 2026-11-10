"""
Physical drive and partition reader with sector-aligned buffer management.
Handles Windows volume locks, PhysicalDrive, Logical Drive (\\.\\C:) and raw image scanning.
"""
import os
import sys
import ctypes
from typing import List, Dict, Optional, Tuple, BinaryIO
import win32api
import win32file
import win32con


class DriveReader:
    """Provides low-level block/sector read access to disks and partitions."""

    def __init__(self, target_path: str, sector_size: int = 512):
        self.target_path = target_path
        self.sector_size = sector_size
        self._handle = None
        self._total_size: Optional[int] = None

    @staticmethod
    def is_admin() -> bool:
        """Check if current process has administrative elevation."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def list_available_targets() -> List[Dict[str, str]]:
        """
        Lists available targets for scanning:
        Logical partitions (C:, D:, etc.) and Physical Drives (PhysicalDrive0, etc.)
        """
        targets = []

        # 1. Logical Drives (Partition level)
        try:
            drives_bitmask = win32api.GetLogicalDrives()
            for i in range(26):
                if drives_bitmask & (1 << i):
                    drive_letter = f"{chr(65 + i)}:"
                    drive_root = f"{drive_letter}\\"
                    try:
                        drive_type = win32file.GetDriveType(drive_root)
                        # DRIVE_FIXED = 3, DRIVE_REMOVABLE = 2
                        type_str = "Fixed Disk" if drive_type == 3 else ("Removable" if drive_type == 2 else "Drive")
                        targets.append({
                            "id": f"\\\\.\\{drive_letter}",
                            "name": f"Logical Volume {drive_letter} ({type_str})",
                            "type": "volume",
                            "root": drive_root
                        })
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error enumerating logical drives: {e}")

        # 2. Physical Drives (Direct sector level)
        for i in range(16):
            pd_path = f"\\\\.\\PhysicalDrive{i}"
            try:
                h = win32file.CreateFile(
                    pd_path,
                    win32con.GENERIC_READ,
                    win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                    None,
                    win32con.OPEN_EXISTING,
                    0,
                    None
                )
                win32file.CloseHandle(h)
                targets.append({
                    "id": pd_path,
                    "name": f"Physical Disk {i} (Raw Sector Access)",
                    "type": "physical",
                    "root": ""
                })
            except Exception:
                continue

        return targets

    def open(self):
        """Open device handle with read sharing."""
        self._handle = win32file.CreateFile(
            self.target_path,
            win32con.GENERIC_READ,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
            None,
            win32con.OPEN_EXISTING,
            win32file.FILE_FLAG_RANDOM_ACCESS,
            None
        )
        self._determine_size()

    def _determine_size(self):
        """Calculates total size using Win32 API geometry or cluster metrics."""
        try:
            # For logical drives like \\.\C:
            if ":" in self.target_path:
                drive_root = self.target_path.replace("\\\\.\\", "") + "\\"
                spc, bps, free_c, total_c = win32api.GetDiskFreeSpace(drive_root)
                self.sector_size = bps
                self._total_size = total_c * spc * bps
                return
        except Exception:
            pass

        # Fallback to DeviceIoControl IOCTL_DISK_GET_LENGTH_INFO (0x00074059)
        try:
            length_buf = ctypes.c_ulonglong()
            bytes_returned = ctypes.c_ulong()
            success = ctypes.windll.kernel32.DeviceIoControl(
                int(self._handle),
                0x00074059,  # IOCTL_DISK_GET_LENGTH_INFO
                None,
                0,
                ctypes.byref(length_buf),
                ctypes.sizeof(length_buf),
                ctypes.byref(bytes_returned),
                None
            )
            if success:
                self._total_size = length_buf.value
                return
        except Exception:
            pass

        # Conservative default if size probe blocked
        self._total_size = 10 * 1024 * 1024 * 1024  # 10 GB limit

    @property
    def total_size(self) -> int:
        return self._total_size or 0

    def read_exact(self, offset: int, length: int) -> bytes:
        """
        Reads length bytes starting at byte offset.
        Performs sector alignment padding internally for Windows low-level handles.
        """
        if not self._handle:
            raise RuntimeError("Device handle is not opened.")

        aligned_start = (offset // self.sector_size) * self.sector_size
        padding = offset - aligned_start
        aligned_length = ((length + padding + self.sector_size - 1) // self.sector_size) * self.sector_size

        # Seek to sector aligned position
        win32file.SetFilePointer(self._handle, aligned_start, win32file.FILE_BEGIN)
        hr, data = win32file.ReadFile(self._handle, aligned_length, None)

        if padding > 0:
            data = data[padding:]
        return data[:length]

    def close(self):
        if self._handle:
            try:
                win32file.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
