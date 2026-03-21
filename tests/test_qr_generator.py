"""Tests para el generador de QR."""

import pytest
import tempfile
import os
from app.qr import QRGenerator


class TestQRGenerator:
    """Tests para QRGenerator."""
    
    def test_generate_qr_from_text(self):
        """Probar generación de QR desde texto."""
        with tempfile.TemporaryDirectory() as temp_dir:
            qr_gen = QRGenerator(output_folder=temp_dir)
            filepath = qr_gen.generate_qr_from_text("Hola Mundo", "test.png")
            
            assert filepath is not None
            assert os.path.exists(filepath)
            assert filepath.endswith("test.png")
    
    def test_generate_qr_from_data(self):
        """Probar generación de QR desde diccionario."""
        with tempfile.TemporaryDirectory() as temp_dir:
            qr_gen = QRGenerator(output_folder=temp_dir)
            data = {"name": "Juan", "email": "juan@email.com"}
            filepath = qr_gen.generate_qr_from_data(data, "test_data.png")
            
            assert filepath is not None
            assert os.path.exists(filepath)
    
    def test_generate_qr_batch(self):
        """Probar generación de múltiples QR."""
        with tempfile.TemporaryDirectory() as temp_dir:
            qr_gen = QRGenerator(output_folder=temp_dir)
            data_list = ["Texto1", "Texto2", "Texto3"]
            results = qr_gen.generate_qr_batch(data_list)
            
            assert len(results) == 3
            for filepath in results:
                assert os.path.exists(filepath)
