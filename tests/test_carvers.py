import io
import unittest
import struct
import zipfile
from src.carvers.signatures import JPEGCarver, PNGCarver, PDFCarver, ZIPCarver, EXECarver
from src.core.models import RecoverableFile


class TestFileCarvers(unittest.TestCase):
    def test_jpeg_carver(self):
        carver = JPEGCarver()
        dummy_jpeg = b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + b'IMAGE_DATA' + b'\xFF\xD9'
        stream = io.BytesIO(dummy_jpeg)
        size = carver.get_file_size(stream, 0)
        self.assertEqual(size, len(dummy_jpeg))

    def test_png_carver(self):
        carver = PNGCarver()
        ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + b'A' * 13 + b'CRC1'
        iend_chunk = struct.pack('>I', 0) + b'IEND' + b'CRC2'
        dummy_png = b'\x89PNG\r\n\x1a\n' + ihdr_chunk + iend_chunk
        stream = io.BytesIO(dummy_png)
        size = carver.get_file_size(stream, 0)
        self.assertEqual(size, len(dummy_png))

    def test_pdf_carver(self):
        carver = PDFCarver()
        dummy_pdf = b'%PDF-1.4\n1 0 obj\n<< /Title (Test) >>\nendobj\ntrailer\n<<>>\nstartxref\n100\n%%EOF\n'
        stream = io.BytesIO(dummy_pdf)
        size = carver.get_file_size(stream, 0)
        self.assertEqual(size, len(dummy_pdf))

    def test_zip_carver(self):
        carver = ZIPCarver()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('document.txt', 'Forensic unit test data')
        raw_zip = buf.getvalue()
        stream = io.BytesIO(raw_zip)
        size = carver.get_file_size(stream, 0)
        self.assertEqual(size, len(raw_zip))

    def test_recoverable_file_formatting(self):
        rf = RecoverableFile(
            file_id="1",
            name="photo.jpg",
            size=1024 * 1024 * 5,
            source_type="Deep Carved",
            status="Permanently Deleted",
            timestamp="2026-11-10 12:00:00",
            location="Drive 0"
        )
        self.assertEqual(rf.formatted_size, "5.00 MB")


if __name__ == '__main__':
    unittest.main()
