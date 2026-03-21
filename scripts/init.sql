-- Inicialización de base de datos para Database Manager
-- Ejecutado automáticamente al iniciar el contenedor MariaDB

-- Crear base de datos si no existe (aunque docker-compose ya la crea)
CREATE DATABASE IF NOT EXISTS database_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE database_manager;

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(255),
    es_activo BOOLEAN DEFAULT TRUE,
    es_admin BOOLEAN DEFAULT FALSE,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_ultima_sesion DATETIME NULL,
    INDEX idx_username (username),
    INDEX idx_email (email)
);

-- Tabla de logs de importación
CREATE TABLE IF NOT EXISTS import_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    archivo_nombre VARCHAR(255) NOT NULL,
    archivo_tamanio INT,
    tipo_archivo VARCHAR(20) NOT NULL,
    tabla_destino VARCHAR(255) NOT NULL,
    delimitador VARCHAR(10),
    registros_totales INT DEFAULT 0,
    registros_importados INT DEFAULT 0,
    registros_fallidos INT DEFAULT 0,
    estado VARCHAR(20) NOT NULL,
    mensaje_error TEXT,
    usuario_id INT NOT NULL,
    fecha_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_fin DATETIME NULL,
    duracion_segundos INT,
    INDEX idx_tabla_destino (tabla_destino),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Tabla de datos importados
CREATE TABLE IF NOT EXISTS datos_importados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    nombre VARCHAR(255),
    email VARCHAR(255),
    telefono VARCHAR(20),
    empresa VARCHAR(255),
    ciudad VARCHAR(100),
    pais VARCHAR(100),
    datos_adicionales TEXT,
    qr_code LONGBLOB,
    qr_filename VARCHAR(255),
    contenido_qr TEXT,
    creado_por INT,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_modificacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    fecha_eliminacion DATETIME NULL,
    es_activo BOOLEAN DEFAULT TRUE,
    importacion_id INT,
    INDEX idx_nombre (nombre),
    INDEX idx_email (email),
    INDEX idx_empresa (empresa),
    INDEX idx_fecha_creacion (fecha_creacion),
    INDEX idx_es_activo (es_activo),
    FOREIGN KEY (creado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    FOREIGN KEY (importacion_id) REFERENCES import_logs(id) ON DELETE CASCADE
);

-- Usuario administrador inicial
-- Contraseña: SecurePassword123! (cambiar en producción)
INSERT IGNORE INTO usuarios (username, email, hashed_password, nombre_completo, es_admin)
VALUES (
    'admin',
    'admin@database-manager.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6fM/v7QH8e', -- SecurePassword123!
    'Administrador',
    TRUE
);