"""
Concrete carvers for common digital forensics file formats:
JPEG, PNG, PDF, ZIP/Office, MP4/MOV, and Windows PE (EXE/DLL).
"""
import struct
from typing import Optional, List
from src.carvers.base import BaseCarver


class JPEGCarver(BaseCarver):
    file_type = "jpg"
    signatures = [b'\xFF\xD8\xFF\xE0', b'\xFF\xD8\xFF\xE1', b'\xFF\xD8\xFF\xEE', b'\xFF\xD8\xFF\xDB']

    def get_file_size(self, stream, start_offset: int, max_search_size: int = 50 * 1024 * 1024) -> Optional[int]:
        stream.seek(start_offset)
        header = stream.read(2)
        if header != b'\xFF\xD8':
            return None

        # Search forward for EOI marker FF D9
        chunk_size = 65536
        offset_in_file = 2
        last_byte = b''

        while offset_in_file < max_search_size:
            read_len = min(chunk_size, max_search_size - offset_in_file)
            data = stream.read(read_len)
            if not data:
                break

            combined = last_byte + data
            eoi = combined.find(b'\xFF\xD9')
            if eoi != -1:
                # Found EOI marker
                return offset_in_file - len(last_byte) + eoi + 2

            last_byte = data[-1:]
            offset_in_file += len(data)

        return None


class PNGCarver(BaseCarver):
    file_type = "png"
    signatures = [b'\x89PNG\r\n\x1a\n']

    def get_file_size(self, stream, start_offset: int, max_search_size: int = 100 * 1024 * 1024) -> Optional[int]:
        stream.seek(start_offset)
        sig = stream.read(8)
        if sig != b'\x89PNG\r\n\x1a\n':
            return None

        curr = 8
        while curr < max_search_size:
            header = stream.read(8)
            if len(header) < 8:
                return None
            chunk_len = struct.unpack('>I', header[0:4])[0]
            chunk_type = header[4:8]

            if chunk_len > max_search_size:
                return None

            curr += 8 + chunk_len + 4  # 4-byte length + 4-byte type + data + 4-byte CRC
            if chunk_type == b'IEND':
                return curr

            stream.seek(start_offset + curr)

        return None


class PDFCarver(BaseCarver):
    file_type = "pdf"
    signatures = [b'%PDF-']

    def get_file_size(self, stream, start_offset: int, max_search_size: int = 150 * 1024 * 1024) -> Optional[int]:
        stream.seek(start_offset)
        data = stream.read(max_search_size)
        if not data.startswith(b'%PDF-'):
            return None

        eof_pos = data.rfind(b'%%EOF')
        if eof_pos == -1:
            return None

        end = eof_pos + 5
        # Skip trailing white space / newlines
        while end < len(data) and data[end] in (10, 13, 32):
            end += 1
        return end


class ZIPCarver(BaseCarver):
    file_type = "zip"
    signatures = [b'PK\x03\x04']

    def get_file_size(self, stream, start_offset: int, max_search_size: int = 250 * 1024 * 1024) -> Optional[int]:
        stream.seek(start_offset)
        data = stream.read(max_search_size)
        if len(data) < 22 or not data.startswith(b'PK\x03\x04'):
            return None

        eocd_pos = data.rfind(b'PK\x05\x06')
        if eocd_pos == -1 or len(data) < eocd_pos + 22:
            return None

        comment_len = struct.unpack('<H', data[eocd_pos + 20:eocd_pos + 22])[0]
        total_len = eocd_pos + 22 + comment_len
        return min(total_len, len(data))


class MP4Carver(BaseCarver):
    file_type = "mp4"
    signatures = [b'ftyp']  # Offset 4 usually

    def get_file_size(self, stream, start_offset: int, max_search_size: int = 1024 * 1024 * 1024) -> Optional[int]:
        stream.seek(start_offset)
        header = stream.read(8)
        if len(header) < 8:
            return None
        box_size = struct.unpack('>I', header[0:4])[0]
        box_type = header[4:8]
        if box_type != b'ftyp' or box_size < 8:
            return None

        # Traverse ISO base media atoms
        curr_offset = 0
        while curr_offset < max_search_size:
            stream.seek(start_offset + curr_offset)
            atom_hdr = stream.read(8)
            if len(atom_hdr) < 8:
                break
            sz = struct.unpack('>I', atom_hdr[0:4])[0]
            if sz == 0:  # Box extends to end of file
                curr_offset += 8
                break
            if sz == 1:  # 64-bit large box
                large_sz_bytes = stream.read(8)
                if len(large_sz_bytes) < 8:
                    break
                sz = struct.unpack('>Q', large_sz_bytes)[0]
            if sz < 8 or sz > max_search_size:
                break
            curr_offset += sz
            # If we've traversed at least moov/mdat, or passed standard size
            if curr_offset > 512:
                # Stop if next atom type is non-printable or corrupt
                stream.seek(start_offset + curr_offset)
                nxt = stream.read(8)
                if len(nxt) < 8 or not all(32 <= b <= 126 for b in nxt[4:8]):
                    return curr_offset

        return curr_offset if curr_offset > 8 else None


class EXECarver(BaseCarver):
    file_type = "exe"
    signatures = [b'MZ']

    def get_file_size(self, stream, start_offset: int, max_search_size: int = 500 * 1024 * 1024) -> Optional[int]:
        stream.seek(start_offset)
        dos_hdr = stream.read(64)
        if len(dos_hdr) < 64 or dos_hdr[:2] != b'MZ':
            return None

        pe_offset = struct.unpack('<I', dos_hdr[0x3C:0x40])[0]
        if pe_offset + 24 > max_search_size:
            return None

        stream.seek(start_offset + pe_offset)
        pe_sig = stream.read(4)
        if pe_sig != b'PE\x00\x00':
            return None

        coff_hdr = stream.read(20)
        if len(coff_hdr) < 20:
            return None

        num_sections = struct.unpack('<H', coff_hdr[2:4])[0]
        opt_hdr_size = struct.unpack('<H', coff_hdr[16:18])[0]

        if opt_hdr_size > 0:
            stream.seek(start_offset + pe_offset + 24 + opt_hdr_size)
            max_raw_end = pe_offset + 24 + opt_hdr_size
            for _ in range(num_sections):
                section_hdr = stream.read(40)
                if len(section_hdr) < 40:
                    break
                raw_data_size = struct.unpack('<I', section_hdr[16:20])[0]
                raw_data_offset = struct.unpack('<I', section_hdr[20:24])[0]
                section_end = raw_data_offset + raw_data_size
                if section_end > max_raw_end:
                    max_raw_end = section_end

            if max_raw_end > 0:
                return min(max_raw_end, max_search_size)

        return None


ALL_CARVERS: List[BaseCarver] = [
    JPEGCarver(),
    PNGCarver(),
    PDFCarver(),
    ZIPCarver(),
    EXECarver()
]
