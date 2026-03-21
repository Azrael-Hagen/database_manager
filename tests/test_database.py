"""Tests para la conexión a base de datos."""

import pytest
from app.database import DatabaseConnection


class TestDatabaseConnection:
    """Tests para DatabaseConnection."""
    
    def test_singleton_pattern(self):
        """Probar que DatabaseConnection es Singleton."""
        conn1 = DatabaseConnection()
        conn2 = DatabaseConnection()
        
        assert conn1 is conn2
    
    def test_connection_creation(self):
        """Probar creación de conexión."""
        # Este test requiere una BD configurada
        # Se debe hacer mocking para no depender de BD real
        pass
