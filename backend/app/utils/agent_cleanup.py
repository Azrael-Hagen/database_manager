"""Utilidades para depuración segura de agentes redundantes o de prueba."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


TEST_REGEX = r"(^|[^a-z])(test|e2e|fix|demo|tmp|temporal|prueba)([^a-z]|$)"
TEST_REGEX_SOFT = r"(test|e2e|fix|demo|tmp|temporal|prueba)"


def _candidate_test_ids(db: Session) -> list[int]:
    rows = db.execute(
        text(
            """
            SELECT d.id
            FROM datos_importados d
            WHERE COALESCE(d.es_activo, 1) = 1
              AND (
                    LOWER(COALESCE(d.nombre, '')) REGEXP :regex_name
                 OR LOWER(COALESCE(d.email, '')) REGEXP :regex_soft
                 OR LOWER(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(d.datos_adicionales, '$.alias')), '')) REGEXP :regex_soft
              )
              AND NOT EXISTS (SELECT 1 FROM agente_linea_asignaciones a WHERE a.agente_id = d.id)
              AND NOT EXISTS (SELECT 1 FROM pagos_semanales p WHERE p.agente_id = d.id)
              AND NOT EXISTS (SELECT 1 FROM recibos_pago rp WHERE rp.agente_id = d.id)
            ORDER BY d.id
            """
        ),
        {"regex_name": TEST_REGEX, "regex_soft": TEST_REGEX_SOFT},
    ).all()
    return [int(row[0]) for row in rows]


def _candidate_duplicate_ids(db: Session) -> list[int]:
    rows = db.execute(
        text(
            """
            WITH ranked AS (
              SELECT
                id,
                ROW_NUMBER() OVER (
                  PARTITION BY
                    LOWER(TRIM(COALESCE(nombre, ''))),
                    LOWER(TRIM(COALESCE(telefono, ''))),
                    LOWER(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(datos_adicionales, '$.alias')), ''))),
                    LOWER(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(datos_adicionales, '$.ubicacion')), ''))),
                    LOWER(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(datos_adicionales, '$.fp')), ''))),
                    LOWER(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(datos_adicionales, '$.fc')), ''))),
                    LOWER(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(datos_adicionales, '$.grupo')), ''))),
                    LOWER(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(datos_adicionales, '$.numero_voip')), '')))
                  ORDER BY id ASC
                ) AS rn
              FROM datos_importados
              WHERE COALESCE(es_activo, 1) = 1
            )
            SELECT r.id
            FROM ranked r
            WHERE r.rn > 1
              AND NOT EXISTS (SELECT 1 FROM agente_linea_asignaciones a WHERE a.agente_id = r.id)
              AND NOT EXISTS (SELECT 1 FROM pagos_semanales p WHERE p.agente_id = r.id)
              AND NOT EXISTS (SELECT 1 FROM recibos_pago rp WHERE rp.agente_id = r.id)
            ORDER BY r.id
            """
        )
    ).all()
    return [int(row[0]) for row in rows]


def _candidate_name_alias_duplicate_ids(db: Session) -> list[int]:
        rows = db.execute(
                text(
                        """
                        WITH ranked AS (
                            SELECT
                                id,
                                ROW_NUMBER() OVER (
                                    PARTITION BY
                                        LOWER(TRIM(COALESCE(nombre, ''))),
                                        LOWER(TRIM(COALESCE(JSON_UNQUOTE(JSON_EXTRACT(datos_adicionales, '$.alias')), '')))
                                    ORDER BY id ASC
                                ) AS rn
                            FROM datos_importados
                            WHERE COALESCE(es_activo, 1) = 1
                        )
                        SELECT r.id
                        FROM ranked r
                        WHERE r.rn > 1
                            AND NOT EXISTS (SELECT 1 FROM agente_linea_asignaciones a WHERE a.agente_id = r.id)
                            AND NOT EXISTS (SELECT 1 FROM pagos_semanales p WHERE p.agente_id = r.id)
                            AND NOT EXISTS (SELECT 1 FROM recibos_pago rp WHERE rp.agente_id = r.id)
                        ORDER BY r.id
                        """
                )
        ).all()
        return [int(row[0]) for row in rows]


def _active_agents_count(db: Session) -> int:
    return int(
        db.execute(
            text("SELECT COUNT(*) FROM datos_importados WHERE COALESCE(es_activo, 1) = 1")
        ).scalar()
        or 0
    )


def cleanup_redundant_agents(
    db: Session,
    *,
    apply_changes: bool,
    sync_legacy: bool = True,
) -> dict:
    """Detecta y elimina (opcionalmente) agentes test/duplicados sin referencias operativas."""

    before_active = _active_agents_count(db)
    test_ids = _candidate_test_ids(db)
    duplicate_ids = _candidate_duplicate_ids(db)
    name_alias_duplicate_ids = _candidate_name_alias_duplicate_ids(db)
    candidate_ids = sorted(set(test_ids + duplicate_ids + name_alias_duplicate_ids))

    if not apply_changes or not candidate_ids:
        return {
            "before_active": before_active,
            "after_active": before_active,
            "deleted": 0,
            "test_like_candidates": len(test_ids),
            "duplicate_candidates": len(duplicate_ids),
            "name_alias_duplicate_candidates": len(name_alias_duplicate_ids),
            "candidate_ids": candidate_ids,
            "legacy_deleted": 0,
            "applied": False,
        }

    ids_csv = ",".join(str(i) for i in candidate_ids)
    deleted = db.execute(
        text(f"DELETE FROM datos_importados WHERE id IN ({ids_csv})")
    ).rowcount or 0

    legacy_deleted = 0
    if sync_legacy:
        try:
            legacy_deleted = (
                db.execute(text(f"DELETE FROM registro_agentes.agentes WHERE ID IN ({ids_csv})")).rowcount
                or 0
            )
        except Exception:
            legacy_deleted = 0

    after_active = _active_agents_count(db)
    return {
        "before_active": before_active,
        "after_active": after_active,
        "deleted": int(deleted),
        "test_like_candidates": len(test_ids),
        "duplicate_candidates": len(duplicate_ids),
        "name_alias_duplicate_candidates": len(name_alias_duplicate_ids),
        "candidate_ids": candidate_ids,
        "legacy_deleted": int(legacy_deleted),
        "applied": True,
    }
