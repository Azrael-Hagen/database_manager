/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19-12.2.2-MariaDB, for Win64 (AMD64)
--
-- Host: localhost    Database: database_manager
-- ------------------------------------------------------
-- Server version	12.2.2-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*M!100616 SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0 */;

--
-- Table structure for table `agente_lada_preferencias`
--

DROP TABLE IF EXISTS `agente_lada_preferencias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `agente_lada_preferencias` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `agente_id` int(11) NOT NULL,
  `lada_id` int(11) NOT NULL,
  `prioridad` int(11) DEFAULT NULL,
  `fecha_creacion` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_agente_lada_preferencias_id` (`id`),
  KEY `ix_agente_lada_preferencias_lada_id` (`lada_id`),
  KEY `ix_agente_lada_preferencias_prioridad` (`prioridad`),
  KEY `ix_agente_lada_preferencias_agente_id` (`agente_id`),
  KEY `ix_agente_lada_preferencias_fecha_creacion` (`fecha_creacion`),
  CONSTRAINT `1` FOREIGN KEY (`agente_id`) REFERENCES `datos_importados` (`id`),
  CONSTRAINT `2` FOREIGN KEY (`lada_id`) REFERENCES `ladas_catalogo` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `agente_lada_preferencias`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `agente_lada_preferencias` WRITE;
/*!40000 ALTER TABLE `agente_lada_preferencias` DISABLE KEYS */;
INSERT INTO `agente_lada_preferencias` VALUES
(1,16,1,1,'2026-03-22 01:23:56');
/*!40000 ALTER TABLE `agente_lada_preferencias` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `agente_linea_asignaciones`
--

DROP TABLE IF EXISTS `agente_linea_asignaciones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `agente_linea_asignaciones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `agente_id` int(11) NOT NULL,
  `linea_id` int(11) NOT NULL,
  `es_activa` tinyint(1) DEFAULT NULL,
  `fecha_asignacion` datetime DEFAULT NULL,
  `fecha_liberacion` datetime DEFAULT NULL,
  `observaciones` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_agente_linea_asignaciones_agente_id` (`agente_id`),
  KEY `ix_agente_linea_asignaciones_fecha_asignacion` (`fecha_asignacion`),
  KEY `ix_agente_linea_asignaciones_id` (`id`),
  KEY `ix_agente_linea_asignaciones_linea_id` (`linea_id`),
  KEY `ix_agente_linea_asignaciones_es_activa` (`es_activa`),
  CONSTRAINT `1` FOREIGN KEY (`agente_id`) REFERENCES `datos_importados` (`id`),
  CONSTRAINT `2` FOREIGN KEY (`linea_id`) REFERENCES `lineas_telefonicas` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `agente_linea_asignaciones`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `agente_linea_asignaciones` WRITE;
/*!40000 ALTER TABLE `agente_linea_asignaciones` DISABLE KEYS */;
INSERT INTO `agente_linea_asignaciones` VALUES
(1,13,1,1,'2026-03-22 00:46:16',NULL,NULL),
(2,14,2,0,'2026-03-22 00:46:35','2026-03-22 00:46:35',NULL),
(3,15,3,0,'2026-03-22 00:46:59','2026-03-22 00:47:00',NULL),
(4,16,4,0,'2026-03-22 01:23:56','2026-03-22 01:23:56',NULL);
/*!40000 ALTER TABLE `agente_linea_asignaciones` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `alertas_pago`
--

DROP TABLE IF EXISTS `alertas_pago`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `alertas_pago` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `agente_id` int(11) NOT NULL,
  `semana_inicio` date NOT NULL,
  `fecha_alerta` datetime DEFAULT NULL,
  `motivo` varchar(255) DEFAULT NULL,
  `atendida` tinyint(1) DEFAULT NULL,
  `fecha_atendida` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_alertas_pago_semana_inicio` (`semana_inicio`),
  KEY `ix_alertas_pago_atendida` (`atendida`),
  KEY `ix_alertas_pago_agente_id` (`agente_id`),
  KEY `ix_alertas_pago_fecha_alerta` (`fecha_alerta`),
  KEY `ix_alertas_pago_id` (`id`),
  CONSTRAINT `1` FOREIGN KEY (`agente_id`) REFERENCES `datos_importados` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alertas_pago`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `alertas_pago` WRITE;
/*!40000 ALTER TABLE `alertas_pago` DISABLE KEYS */;
/*!40000 ALTER TABLE `alertas_pago` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `auditoria_acciones`
--

DROP TABLE IF EXISTS `auditoria_acciones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `auditoria_acciones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `usuario_id` int(11) DEFAULT NULL,
  `tipo_accion` varchar(20) NOT NULL,
  `tabla` varchar(50) NOT NULL,
  `registro_id` int(11) DEFAULT NULL,
  `descripcion` text DEFAULT NULL,
  `datos_anteriores` text DEFAULT NULL,
  `datos_nuevos` text DEFAULT NULL,
  `resultado` varchar(20) DEFAULT NULL,
  `ip_origen` varchar(45) DEFAULT NULL,
  `user_agent` varchar(255) DEFAULT NULL,
  `fecha` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `usuario_id` (`usuario_id`),
  KEY `ix_auditoria_acciones_registro_id` (`registro_id`),
  KEY `ix_auditoria_acciones_id` (`id`),
  KEY `ix_auditoria_acciones_tabla` (`tabla`),
  KEY `ix_auditoria_acciones_fecha` (`fecha`),
  KEY `ix_auditoria_acciones_tipo_accion` (`tipo_accion`),
  CONSTRAINT `1` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=93 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auditoria_acciones`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `auditoria_acciones` WRITE;
/*!40000 ALTER TABLE `auditoria_acciones` DISABLE KEYS */;
INSERT INTO `auditoria_acciones` VALUES
(1,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 20:12:26'),
(2,NULL,'LOGIN','usuarios',NULL,'Intento de login fallido: admin',NULL,NULL,'FAILED','127.0.0.1',NULL,'2026-03-21 20:29:32'),
(3,NULL,'LOGIN','usuarios',NULL,'Intento de login fallido: admin',NULL,NULL,'FAILED','127.0.0.1',NULL,'2026-03-21 20:29:50'),
(4,NULL,'LOGIN','usuarios',NULL,'Intento de login fallido: admin',NULL,NULL,'FAILED','127.0.0.1',NULL,'2026-03-21 20:30:08'),
(5,NULL,'LOGIN','usuarios',NULL,'Intento de login fallido: admin',NULL,NULL,'FAILED','127.0.0.1',NULL,'2026-03-21 20:30:40'),
(6,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 20:32:15'),
(7,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:07:47'),
(8,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:08:20'),
(9,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:17:21'),
(10,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:33:04'),
(11,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:34:16'),
(12,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:36:04'),
(13,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:37:10'),
(14,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:38:15'),
(15,1,'IMPORTAR','datos_importados',NULL,'Importación completada: 1 registros',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 21:38:15'),
(16,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:38:27'),
(17,1,'ACTUALIZAR','usuarios',1,'Contraseña cambiada: admin',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 21:38:27'),
(18,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 21:38:27'),
(19,1,'ACTUALIZAR','usuarios',1,'Contraseña cambiada: admin',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 21:38:28'),
(20,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 22:05:24'),
(21,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 22:17:54'),
(22,NULL,'LOGIN','usuarios',NULL,'Intento de login fallido: admin',NULL,NULL,'FAILED','127.0.0.1',NULL,'2026-03-21 22:45:45'),
(23,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 22:45:56'),
(24,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:10:48'),
(25,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:11:01'),
(26,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:11:23'),
(27,1,'CREAR','datos_importados',2,'Dato creado: Agente Prueba QR',NULL,'{\"nombre\": \"Agente Prueba QR\", \"email\": null, \"telefono\": \"523325051104\", \"empresa\": \"Testing\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:11:23'),
(28,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:12:07'),
(29,1,'CREAR','datos_importados',3,'Dato creado: Agente Prueba QR',NULL,'{\"nombre\": \"Agente Prueba QR\", \"email\": null, \"telefono\": \"523325051104\", \"empresa\": \"Testing\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:12:07'),
(30,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:12:53'),
(31,1,'CREAR','datos_importados',4,'Dato creado: Agente Prueba QR',NULL,'{\"nombre\": \"Agente Prueba QR\", \"email\": null, \"telefono\": \"523325051104\", \"empresa\": \"Testing\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:12:53'),
(32,1,'ELIMINAR','datos_importados',4,'Dato eliminado: Agente Prueba QR',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 23:12:54'),
(33,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:13:52'),
(34,NULL,'LOGIN','usuarios',NULL,'Intento de login fallido: admin',NULL,NULL,'FAILED','127.0.0.1',NULL,'2026-03-21 23:20:17'),
(35,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:21:29'),
(36,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:21:44'),
(37,1,'CREAR','datos_importados',5,'Dato creado: Filtro Recibo QA',NULL,'{\"nombre\": \"Filtro Recibo QA\", \"email\": \"filtro.recibo.qa@example.com\", \"telefono\": \"5550009999\", \"empresa\": \"Empresa QA\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:21:44'),
(38,1,'ELIMINAR','datos_importados',5,'Dato eliminado: Filtro Recibo QA',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 23:21:44'),
(39,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:22:39'),
(40,1,'CREAR','datos_importados',6,'Dato creado: Filtro Recibo QA',NULL,'{\"nombre\": \"Filtro Recibo QA\", \"email\": \"filtro.recibo.qa@example.com\", \"telefono\": \"5550009999\", \"empresa\": \"Empresa QA\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:22:39'),
(41,1,'ELIMINAR','datos_importados',6,'Dato eliminado: Filtro Recibo QA',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 23:22:39'),
(42,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:27:39'),
(43,1,'CREAR','datos_importados',7,'Dato creado: TMP Remote QA',NULL,'{\"nombre\": \"TMP Remote QA\", \"email\": \"tmp.remote.qa@example.com\", \"telefono\": \"5551112222\", \"empresa\": \"TMP QA\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:27:39'),
(44,1,'ELIMINAR','datos_importados',7,'Dato eliminado: TMP Remote QA',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 23:27:39'),
(45,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:30:48'),
(46,1,'CREAR','datos_importados',8,'Dato creado: TMP Host QA',NULL,'{\"nombre\": \"TMP Host QA\", \"email\": \"tmp.host.qa@example.com\", \"telefono\": \"5553334444\", \"empresa\": \"TMP HOST\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:30:48'),
(47,1,'ELIMINAR','datos_importados',8,'Dato eliminado: TMP Host QA',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 23:30:48'),
(48,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:32:25'),
(49,1,'CREAR','datos_importados',9,'Dato creado: TMP Hostname QA',NULL,'{\"nombre\": \"TMP Hostname QA\", \"email\": \"tmp.hostname.qa@example.com\", \"telefono\": \"5556667777\", \"empresa\": \"TMP HOSTNAME\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:32:25'),
(50,1,'ELIMINAR','datos_importados',9,'Dato eliminado: TMP Hostname QA',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 23:32:25'),
(51,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:57:01'),
(52,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:58:45'),
(53,1,'CREAR','datos_importados',10,'Dato creado: TMP FINAL QA',NULL,'{\"nombre\": \"TMP FINAL QA\", \"email\": \"tmp.final.qa@example.com\", \"telefono\": \"5557778888\", \"empresa\": \"TMP FINAL\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:58:45'),
(54,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-21 23:59:04'),
(55,1,'CREAR','datos_importados',11,'Dato creado: TMP FINAL QA',NULL,'{\"nombre\": \"TMP FINAL QA\", \"email\": \"tmp.final.qa@example.com\", \"telefono\": \"5557778888\", \"empresa\": \"TMP FINAL\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-21 23:59:04'),
(56,1,'ELIMINAR','datos_importados',11,'Dato eliminado: TMP FINAL QA',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-21 23:59:04'),
(57,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:00:04'),
(58,1,'CREAR','usuarios',2,'Usuario creado: Filemon',NULL,'{\"username\": \"Filemon\", \"email\": \"admon666777@outlook.com\"}','SUCCESS',NULL,NULL,'2026-03-22 00:00:48'),
(59,2,'LOGIN','usuarios',NULL,'Login exitoso: Filemon',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:04:51'),
(60,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:05:26'),
(61,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:06:33'),
(62,2,'LOGIN','usuarios',NULL,'Login exitoso: Filemon',NULL,NULL,'SUCCESS','192.168.1.188',NULL,'2026-03-22 00:07:15'),
(63,1,'CREAR','usuarios',3,'Usuario creado: Moyejas',NULL,'{\"username\": \"Moyejas\", \"email\": \"moyejas@moyejas.com\"}','SUCCESS',NULL,NULL,'2026-03-22 00:15:08'),
(64,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:19:38'),
(65,1,'CREAR','datos_importados',12,'Dato creado: E2E Scan User',NULL,'{\"nombre\": \"E2E Scan User\", \"email\": \"e2e.scan@example.com\", \"telefono\": \"5512345678\", \"empresa\": \"E2E\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-22 00:19:38'),
(66,1,'ELIMINAR','datos_importados',12,'Dato eliminado: E2E Scan User',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-22 00:19:38'),
(67,1,'ACTUALIZAR','usuarios',3,'Contraseña cambiada: Moyejas',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-22 00:26:51'),
(68,3,'LOGIN','usuarios',NULL,'Login exitoso: Moyejas',NULL,NULL,'SUCCESS','192.168.1.248',NULL,'2026-03-22 00:27:10'),
(69,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:36:50'),
(70,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:46:16'),
(71,1,'CREAR','datos_importados',13,'Dato creado: E2E Line Agent',NULL,'{\"nombre\": \"E2E Line Agent\", \"email\": \"e2e.line@example.com\", \"telefono\": \"5588800011\", \"empresa\": \"E2E\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-22 00:46:16'),
(72,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:46:35'),
(73,1,'CREAR','datos_importados',14,'Dato creado: E2E Line Agent',NULL,'{\"nombre\": \"E2E Line Agent\", \"email\": \"e2e.line@example.com\", \"telefono\": \"5588800011\", \"empresa\": \"E2E\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-22 00:46:35'),
(74,1,'ELIMINAR','datos_importados',14,'Dato eliminado: E2E Line Agent',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-22 00:46:35'),
(75,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 00:46:59'),
(76,1,'CREAR','datos_importados',15,'Dato creado: E2E Line Agent',NULL,'{\"nombre\": \"E2E Line Agent\", \"email\": \"e2e.line@example.com\", \"telefono\": \"5588800011\", \"empresa\": \"E2E\", \"ciudad\": null, \"pais\": null, \"datos_adicionales\": null}','SUCCESS',NULL,NULL,'2026-03-22 00:46:59'),
(77,1,'ELIMINAR','datos_importados',15,'Dato eliminado: E2E Line Agent',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-22 00:47:00'),
(78,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 01:11:07'),
(79,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 01:23:56'),
(80,1,'ELIMINAR','datos_importados',16,'Dato eliminado: Agente Manual E2E',NULL,NULL,'SUCCESS',NULL,NULL,'2026-03-22 01:23:56'),
(81,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 01:46:38'),
(82,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 01:56:44'),
(83,3,'LOGIN','usuarios',NULL,'Login exitoso: Moyejas',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 01:59:28'),
(84,3,'LOGIN','usuarios',NULL,'Login exitoso: Moyejas',NULL,NULL,'SUCCESS','192.168.1.248',NULL,'2026-03-22 02:01:15'),
(85,3,'LOGIN','usuarios',NULL,'Login exitoso: Moyejas',NULL,NULL,'SUCCESS','192.168.1.248',NULL,'2026-03-22 02:01:29'),
(86,3,'LOGIN','usuarios',NULL,'Login exitoso: Moyejas',NULL,NULL,'SUCCESS','192.168.1.248',NULL,'2026-03-22 02:01:38'),
(87,3,'LOGIN','usuarios',NULL,'Login exitoso: Moyejas',NULL,NULL,'SUCCESS','192.168.1.248',NULL,'2026-03-22 02:08:28'),
(88,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 02:13:38'),
(89,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 02:18:48'),
(90,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 02:21:21'),
(91,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 02:22:00'),
(92,1,'LOGIN','usuarios',NULL,'Login exitoso: admin',NULL,NULL,'SUCCESS','127.0.0.1',NULL,'2026-03-22 02:23:46');
/*!40000 ALTER TABLE `auditoria_acciones` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `config_sistema`
--

DROP TABLE IF EXISTS `config_sistema`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `config_sistema` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `clave` varchar(100) NOT NULL,
  `valor` varchar(500) NOT NULL,
  `fecha_actualizacion` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_config_sistema_clave` (`clave`),
  KEY `ix_config_sistema_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `config_sistema`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `config_sistema` WRITE;
/*!40000 ALTER TABLE `config_sistema` DISABLE KEYS */;
INSERT INTO `config_sistema` VALUES
(1,'LAST_ALERT_CHECK_DATE','2026-03-21','2026-03-21 23:10:04'),
(2,'LAST_BACKUP_WEEK','2026-W12','2026-03-21 23:10:05'),
(3,'CUOTA_SEMANAL','300.0','2026-03-21 23:10:48'),
(4,'BACKUP_DIR_PATH','C:\\Users\\Azrael\\OneDrive\\Documentos\\Herramientas\\database_manager\\tmp\\chosen_backups','2026-03-22 02:22:00');
/*!40000 ALTER TABLE `config_sistema` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `datos_importados`
--

DROP TABLE IF EXISTS `datos_importados`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `datos_importados` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) DEFAULT NULL,
  `nombre` varchar(255) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `telefono` varchar(20) DEFAULT NULL,
  `empresa` varchar(255) DEFAULT NULL,
  `ciudad` varchar(100) DEFAULT NULL,
  `pais` varchar(100) DEFAULT NULL,
  `datos_adicionales` text DEFAULT NULL,
  `qr_code` blob DEFAULT NULL,
  `qr_filename` varchar(255) DEFAULT NULL,
  `contenido_qr` text DEFAULT NULL,
  `creado_por` int(11) DEFAULT NULL,
  `fecha_creacion` datetime DEFAULT NULL,
  `fecha_modificacion` datetime DEFAULT NULL,
  `fecha_eliminacion` datetime DEFAULT NULL,
  `es_activo` tinyint(1) DEFAULT NULL,
  `importacion_id` int(11) DEFAULT NULL,
  `campo_nuevo_demo` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `creado_por` (`creado_por`),
  KEY `importacion_id` (`importacion_id`),
  KEY `ix_datos_importados_id` (`id`),
  KEY `ix_datos_importados_es_activo` (`es_activo`),
  KEY `ix_datos_importados_nombre` (`nombre`),
  KEY `ix_datos_importados_empresa` (`empresa`),
  KEY `ix_datos_importados_fecha_creacion` (`fecha_creacion`),
  KEY `ix_datos_importados_email` (`email`),
  CONSTRAINT `1` FOREIGN KEY (`creado_por`) REFERENCES `usuarios` (`id`),
  CONSTRAINT `2` FOREIGN KEY (`importacion_id`) REFERENCES `import_logs` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `datos_importados`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `datos_importados` WRITE;
/*!40000 ALTER TABLE `datos_importados` DISABLE KEYS */;
INSERT INTO `datos_importados` VALUES
(1,NULL,'E2E User','e2e@example.com',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'valor-demo'),
(12,'7c920c12-d4b4-47ba-b64e-f7fb03099bcb','E2E Scan User','e2e.scan@example.com','5512345678','E2E',NULL,NULL,NULL,NULL,'agente_12_7c920c12-d4b4-47ba-b64e-f7fb03099bcb.png','{\"agente_id\": 12, \"uuid\": \"7c920c12-d4b4-47ba-b64e-f7fb03099bcb\", \"nombre\": \"E2E Scan User\", \"telefono\": \"5512345678\", \"numero_voip\": null, \"tiene_asignacion\": true, \"public_url\": \"http://phantom.database.local/api/qr/public/verify/7c920c12-d4b4-47ba-b64e-f7fb03099bcb\"}',NULL,'2026-03-22 00:19:38','2026-03-22 00:19:38','2026-03-22 00:19:38',0,NULL,NULL),
(13,'936625fc-565c-41a3-98b7-0fb7e4de07e8','E2E Line Agent','e2e.line@example.com','5588800011','E2E',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-03-22 00:46:16','2026-03-22 00:46:16',NULL,1,NULL,NULL),
(14,'0c358c03-a7aa-47e2-a29a-deabe6717040','E2E Line Agent','e2e.line@example.com','5588800011','E2E',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-03-22 00:46:35','2026-03-22 00:46:35','2026-03-22 00:46:35',0,NULL,NULL),
(15,'51971f85-87e0-4205-86c8-fece3122233c','E2E Line Agent','e2e.line@example.com','5588800011','E2E',NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-03-22 00:46:59','2026-03-22 00:47:00','2026-03-22 00:47:00',0,NULL,NULL),
(16,'607198bb-a37e-4e1f-aa2d-2d9c351bf875','Agente Manual E2E',NULL,'523321110680','Testing',NULL,NULL,'{\"alias\": \"A0680\", \"ubicacion\": \"GDL\", \"fp\": \"F0680\", \"fc\": \"C0680\", \"grupo\": \"7\"}',NULL,NULL,NULL,1,'2026-03-22 01:23:56','2026-03-22 01:23:56','2026-03-22 01:23:56',0,NULL,NULL);
/*!40000 ALTER TABLE `datos_importados` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `import_logs`
--

DROP TABLE IF EXISTS `import_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `import_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) DEFAULT NULL,
  `archivo_nombre` varchar(255) NOT NULL,
  `archivo_tamanio` int(11) DEFAULT NULL,
  `tipo_archivo` varchar(20) NOT NULL,
  `tabla_destino` varchar(255) NOT NULL,
  `delimitador` varchar(10) DEFAULT NULL,
  `registros_totales` int(11) DEFAULT NULL,
  `registros_importados` int(11) DEFAULT NULL,
  `registros_fallidos` int(11) DEFAULT NULL,
  `estado` varchar(20) NOT NULL,
  `mensaje_error` text DEFAULT NULL,
  `usuario_id` int(11) NOT NULL,
  `fecha_inicio` datetime DEFAULT NULL,
  `fecha_fin` datetime DEFAULT NULL,
  `duracion_segundos` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `usuario_id` (`usuario_id`),
  KEY `ix_import_logs_tabla_destino` (`tabla_destino`),
  KEY `ix_import_logs_id` (`id`),
  CONSTRAINT `1` FOREIGN KEY (`usuario_id`) REFERENCES `usuarios` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `import_logs`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `import_logs` WRITE;
/*!40000 ALTER TABLE `import_logs` DISABLE KEYS */;
INSERT INTO `import_logs` VALUES
(1,'c65b9089-6553-45c7-83f6-1797d15d12e4','e2e_import.csv',68,'CSV','datos_importados',',',0,1,0,'SUCCESS',NULL,1,'2026-03-21 21:38:15','2026-03-21 21:38:15',0);
/*!40000 ALTER TABLE `import_logs` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `ladas_catalogo`
--

DROP TABLE IF EXISTS `ladas_catalogo`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `ladas_catalogo` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `codigo` varchar(10) NOT NULL,
  `nombre_region` varchar(120) DEFAULT NULL,
  `es_activa` tinyint(1) DEFAULT NULL,
  `fecha_creacion` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_ladas_catalogo_codigo` (`codigo`),
  KEY `ix_ladas_catalogo_es_activa` (`es_activa`),
  KEY `ix_ladas_catalogo_id` (`id`),
  KEY `ix_ladas_catalogo_fecha_creacion` (`fecha_creacion`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ladas_catalogo`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `ladas_catalogo` WRITE;
/*!40000 ALTER TABLE `ladas_catalogo` DISABLE KEYS */;
INSERT INTO `ladas_catalogo` VALUES
(1,'332','Guadalajara',1,'2026-03-22 01:23:56');
/*!40000 ALTER TABLE `ladas_catalogo` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `lineas_telefonicas`
--

DROP TABLE IF EXISTS `lineas_telefonicas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `lineas_telefonicas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `numero` varchar(50) NOT NULL,
  `tipo` varchar(30) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `es_activa` tinyint(1) DEFAULT NULL,
  `fecha_creacion` datetime DEFAULT NULL,
  `fecha_actualizacion` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_lineas_telefonicas_numero` (`numero`),
  KEY `ix_lineas_telefonicas_es_activa` (`es_activa`),
  KEY `ix_lineas_telefonicas_fecha_creacion` (`fecha_creacion`),
  KEY `ix_lineas_telefonicas_tipo` (`tipo`),
  KEY `ix_lineas_telefonicas_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lineas_telefonicas`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `lineas_telefonicas` WRITE;
/*!40000 ALTER TABLE `lineas_telefonicas` DISABLE KEYS */;
INSERT INTO `lineas_telefonicas` VALUES
(1,'L9001E2E','VOIP','temp e2e',1,'2026-03-22 00:46:16','2026-03-22 00:46:16'),
(2,'L1774140395','VOIP','temp e2e',0,'2026-03-22 00:46:35','2026-03-22 00:46:35'),
(3,'7700140419','VOIP','temp e2e',0,'2026-03-22 00:46:59','2026-03-22 00:47:00'),
(4,'3329000680','VOIP','e2e-lada',0,'2026-03-22 01:23:56','2026-03-22 01:23:56');
/*!40000 ALTER TABLE `lineas_telefonicas` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `pagos_semanales`
--

DROP TABLE IF EXISTS `pagos_semanales`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `pagos_semanales` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `agente_id` int(11) NOT NULL,
  `telefono` varchar(20) NOT NULL,
  `numero_voip` varchar(50) DEFAULT NULL,
  `semana_inicio` date NOT NULL,
  `monto` float DEFAULT NULL,
  `pagado` tinyint(1) DEFAULT NULL,
  `fecha_pago` datetime DEFAULT NULL,
  `observaciones` text DEFAULT NULL,
  `fecha_creacion` datetime DEFAULT NULL,
  `fecha_actualizacion` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_pagos_semanales_semana_inicio` (`semana_inicio`),
  KEY `ix_pagos_semanales_telefono` (`telefono`),
  KEY `ix_pagos_semanales_numero_voip` (`numero_voip`),
  KEY `ix_pagos_semanales_pagado` (`pagado`),
  KEY `ix_pagos_semanales_id` (`id`),
  KEY `ix_pagos_semanales_fecha_creacion` (`fecha_creacion`),
  KEY `ix_pagos_semanales_agente_id` (`agente_id`),
  CONSTRAINT `1` FOREIGN KEY (`agente_id`) REFERENCES `datos_importados` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pagos_semanales`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `pagos_semanales` WRITE;
/*!40000 ALTER TABLE `pagos_semanales` DISABLE KEYS */;
/*!40000 ALTER TABLE `pagos_semanales` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;

--
-- Table structure for table `usuarios`
--

DROP TABLE IF EXISTS `usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `email` varchar(255) NOT NULL,
  `hashed_password` varchar(255) NOT NULL,
  `nombre_completo` varchar(255) DEFAULT NULL,
  `es_activo` tinyint(1) DEFAULT NULL,
  `es_admin` tinyint(1) DEFAULT NULL,
  `fecha_creacion` datetime DEFAULT NULL,
  `fecha_ultima_sesion` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_usuarios_username` (`username`),
  UNIQUE KEY `ix_usuarios_email` (`email`),
  KEY `ix_usuarios_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usuarios`
--

SET @OLD_AUTOCOMMIT=@@AUTOCOMMIT, @@AUTOCOMMIT=0;
LOCK TABLES `usuarios` WRITE;
/*!40000 ALTER TABLE `usuarios` DISABLE KEYS */;
INSERT INTO `usuarios` VALUES
(1,'admin','admin@example.com','$2b$12$PSfdxFvcJmwPKigPVXMUr.9o35IylRbWHftCGhHLu8U49yI8mz2mG','Administrador',1,1,'2026-03-21 20:07:19','2026-03-22 02:23:46'),
(2,'Filemon','admon666777@outlook.com','$2b$12$8EPLJQ.TSCmmgiAEJc1P3e.QitjkjaF9Nqkwv.fQ.vHT0vhAom0je','Filemón Chupa Nepe',1,0,'2026-03-22 00:00:48','2026-03-22 00:07:15'),
(3,'Moyejas','moyejas@moyejas.com','$2b$12$j804vEx2K7NZ02kAoC20pubfC7o6RIBQ6Q.N3jLr2QAB5OrPVrFSq','Romerito González',1,0,'2026-03-22 00:15:08','2026-03-22 02:08:28');
/*!40000 ALTER TABLE `usuarios` ENABLE KEYS */;
UNLOCK TABLES;
COMMIT;
SET AUTOCOMMIT=@OLD_AUTOCOMMIT;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*M!100616 SET NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY */;

-- Dump completed on 2026-03-21 20:23:47
