# INSTALACIÓN DE MARIADB LOCAL (WINDOWS)
# Solución open source completa sin Docker

## PASO 1: Descargar MariaDB
# Ve a: https://mariadb.org/download/
# Descarga "MSI Package" para Windows

## PASO 2: Instalar
# Ejecuta el MSI
# Selecciona:
# - "Typical" installation
# - Puerto: 3306 (default)
# - Contraseña root: (deja vacío para desarrollo)

## PASO 3: Verificar instalación
# Abre PowerShell y ejecuta:
```
mysql --version
```
# Deberías ver: mysql  Ver 15.x.x for Win64

## PASO 4: Crear base de datos
# Abre MySQL Command Line Client
# O desde PowerShell:
```
mysql -u root -p
CREATE DATABASE database_manager;
exit;
```

## PASO 5: Ejecutar el proyecto
# Una vez instalado MariaDB:
```
.\start-local.bat
```

## ALTERNATIVAS SI MARIA NO FUNCIONA

### Opción A: XAMPP (Recomendado)
1. Descarga: https://www.apachefriends.org/
2. Instala XAMPP
3. Inicia "MySQL" desde el panel de control
4. La base de datos estará en puerto 3306

### Opción B: WAMP Server
1. Descarga: https://www.wampserver.com/
2. Instala WAMP
3. Inicia WAMP y MySQL
4. Puerto 3306 por defecto

### Opción C: Laragon (Más ligero)
1. Descarga: https://laragon.org/
2. Instala Laragon
3. Inicia MySQL desde el menú

## VERIFICACIÓN FINAL

Después de instalar cualquiera de las opciones:

```powershell
# Verificar MySQL
mysql --version

# Probar conexión
mysql -u root -p -e "SELECT VERSION();"

# Ejecutar proyecto
.\start-local.bat
```

¡El proyecto funcionará completamente local sin Docker!