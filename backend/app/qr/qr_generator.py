"""QR code generator."""

import qrcode
import logging
import json
import os
from datetime import datetime
from app.config import config

logger = logging.getLogger(__name__)


class QRGenerator:
    """Generador de códigos QR."""
    
    def __init__(self, output_folder=None):
        """
        Inicializar generador.
        
        Args:
            output_folder: Carpeta para guardar QR (por defecto config.QR_FOLDER)
        """
        self.output_folder = output_folder or config.QR_FOLDER
        os.makedirs(self.output_folder, exist_ok=True)
    
    def generate_qr_from_text(self, text, filename=None):
        """
        Generar QR desde texto simple.
        
        Args:
            text: Texto a codificar en QR
            filename: Nombre del archivo (opcional)
        
        Returns:
            Ruta del archivo generado
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(text)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"qr_{timestamp}.png"
            
            filepath = os.path.join(self.output_folder, filename)
            img.save(filepath)
            
            logger.info(f"QR generado: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error generando QR: {e}")
            return None
    
    def generate_qr_from_data(self, data_dict, filename=None):
        """
        Generar QR desde un diccionario de datos.
        
        Args:
            data_dict: Diccionario con datos a codificar
            filename: Nombre del archivo (opcional)
        
        Returns:
            Ruta del archivo generado
        """
        try:
            # Serializar diccionario a JSON
            json_data = json.dumps(data_dict, ensure_ascii=False)
            return self.generate_qr_from_text(json_data, filename)
        except Exception as e:
            logger.error(f"Error generando QR desde datos: {e}")
            return None
    
    def generate_qr_batch(self, data_list, prefix="qr"):
        """
        Generar múltiples QR.
        
        Args:
            data_list: Lista de textos o diccionarios
            prefix: Prefijo para los nombres de archivo
        
        Returns:
            Lista de rutas de archivos generados
        """
        results = []
        for i, data in enumerate(data_list):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}_{i}.png"
            
            if isinstance(data, dict):
                filepath = self.generate_qr_from_data(data, filename)
            else:
                filepath = self.generate_qr_from_text(str(data), filename)
            
            if filepath:
                results.append(filepath)
        
        return results
