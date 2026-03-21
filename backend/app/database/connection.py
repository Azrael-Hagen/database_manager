"""Gestión de conexión a la base de datos."""

import mysql.connector
from mysql.connector import Error
from app.config import config
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Gestor de conexión a MariaDB/MySQL."""
    
    _instance = None
    _connection = None
    
    def __new__(cls):
        """Singleton pattern para la conexión."""
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
        return cls._instance
    
    def connect(self):
        """Establecer conexión a la base de datos."""
        try:
            if self._connection is None or not self._connection.is_connected():
                self._connection = mysql.connector.connect(
                    host=config.DB_HOST,
                    user=config.DB_USER,
                    password=config.DB_PASSWORD,
                    database=config.DB_NAME,
                    port=config.DB_PORT
                )
                logger.info(f"Conectado a {config.DB_NAME} en {config.DB_HOST}")
            return self._connection
        except Error as e:
            logger.error(f"Error al conectar a BD: {e}")
            raise
    
    def disconnect(self):
        """Cerrar conexión a la base de datos."""
        if self._connection and self._connection.is_connected():
            self._connection.close()
            logger.info("Desconectado de la base de datos")
    
    def execute_query(self, query, params=None):
        """Ejecutar una consulta SQL."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            conn.commit()
            logger.info(f"Query ejecutada: {query}")
            return True
        except Error as e:
            logger.error(f"Error ejecutando query: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def fetch_all(self, query, params=None):
        """Obtener todos los resultados de una consulta."""
        try:
            conn = self.connect()
            cursor = conn.cursor(dictionary=True)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            return results
        except Error as e:
            logger.error(f"Error fetching data: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def fetch_one(self, query, params=None):
        """Obtener un resultado de una consulta."""
        try:
            conn = self.connect()
            cursor = conn.cursor(dictionary=True)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchone()
            return result
        except Error as e:
            logger.error(f"Error fetching one: {e}")
            return None
        finally:
            if cursor:
                cursor.close()


def get_connection():
    """Función auxiliar para obtener la conexión."""
    return DatabaseConnection()
