"""Tests para los importadores."""

import pytest
import tempfile
import os
from app.importers import CSVImporter, ExcelImporter, TextImporter


class TestCSVImporter:
    """Tests para CSVImporter."""
    
    def test_read_csv_file(self):
        """Probar lectura de archivo CSV."""
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("nombre,email,telefono\n")
            f.write("Juan,juan@email.com,1234567890\n")
            f.write("María,maria@email.com,0987654321\n")
            temp_path = f.name
        
        try:
            importer = CSVImporter(temp_path, "test_table")
            assert importer.read_file() == True
            assert len(importer.data) == 2
            assert importer.data[0]['nombre'] == 'Juan'
        finally:
            os.unlink(temp_path)
    
    def test_validate_csv_data(self):
        """Probar validación de datos CSV."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("nombre,email,telefono\n")
            f.write("Juan,juan@email.com,1234567890\n")
            temp_path = f.name
        
        try:
            importer = CSVImporter(temp_path, "test_table")
            importer.read_file()
            assert importer.validate_data() == True
            assert len(importer.errors) == 0
        finally:
            os.unlink(temp_path)


class TestExcelImporter:
    """Tests para ExcelImporter."""
    
    def test_read_excel_file(self):
        """Probar lectura de archivo Excel."""
        # Este test requeriría crear un archivo Excel real
        # Se puede implementar con openpyxl para crear archivos de test
        pass


class TestTextImporter:
    """Tests para TextImporter."""
    
    def test_read_txt_file(self):
        """Probar lectura de archivo TXT."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("nombre\temail\ttelefono\n")
            f.write("Juan\tjuan@email.com\t1234567890\n")
            f.write("María\tmaria@email.com\t0987654321\n")
            temp_path = f.name
        
        try:
            importer = TextImporter(temp_path, "test_table", delimiter='\t')
            assert importer.read_file() == True
            assert len(importer.data) == 2
        finally:
            os.unlink(temp_path)
