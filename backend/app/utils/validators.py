"""Data validators."""

import re
import logging

logger = logging.getLogger(__name__)


def validate_email(email):
    """Validar formato de email."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone):
    """Validar formato de teléfono."""
    # Eliminar caracteres especiales
    cleaned = re.sub(r'[^\d]', '', phone)
    return len(cleaned) >= 7


def validate_required_fields(data, required_fields):
    """Validar campos requeridos."""
    missing = [field for field in required_fields if field not in data or not data[field]]
    return len(missing) == 0, missing
