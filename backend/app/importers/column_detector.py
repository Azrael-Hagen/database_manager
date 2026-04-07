"""
Advanced column detection engine for the Smart Importer.

Provides:
  - Value-pattern inference   (infer_from_values)
  - Header-row auto-detection (detect_header_row)
  - Multi-table region finder (detect_table_regions)
  - Combined mapping scorer   (suggest_mapping_advanced)
  - Lightweight profile cache (ProfileStore / get_profile_store)

Design goals
  - Zero new dependencies: stdlib + pandas (already in requirements).
  - Deterministic and testable: all public functions are pure or use
    injected dependencies.
  - Failure-safe: profile I/O errors are silently swallowed; the system
    always falls back to synonym/fuzzy matching.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Value-pattern inference rules
# Each entry: (compiled_regex, canonical_field, per-match confidence)
# Rules are evaluated in order; the FIRST matching rule wins per value.
# ---------------------------------------------------------------------------

_VALUE_RULES: list[tuple[re.Pattern, str, float]] = [
    # Email
    (re.compile(r'^[\w.+\-]+@[\w\-]+\.[a-z]{2,7}$', re.I), "email", 0.97),
    # Full E.164-style Mexican phone (52 + 10 digits = 12)
    (re.compile(r'^52[1-9]\d{9}$'), "telefono", 0.92),
    # Generic 10–13 consecutive digits → phone
    (re.compile(r'^[0-9]{10,13}$'), "telefono", 0.88),
    # Phone with common formatting chars
    (re.compile(r'^\+?[0-9][\d\s\-\.]{9,16}$'), "telefono", 0.75),
    # Currency "$NNN" or "$NNN,NNN.NN"
    (re.compile(r'^\$\s?[\d,]+(?:\.\d{1,2})?$'), "deuda", 0.94),
    # IMEI: 15 digits optionally followed by "/" + suffix
    (re.compile(r'^[0-9]{15}(?:/[0-9]{1,4})?$'), "imei", 0.91),
    # IMEI-like: 12-15 digits, slash, 1-4 digits
    (re.compile(r'^[0-9]{12,15}/[0-9]{1,4}$'), "imei", 0.85),
    # Ubicación code: 3–4 digits + letter (e.g. "001 C", "004A")
    (re.compile(r'^[0-9]{3,4}\s*[A-Za-z]$'), "ubicacion", 0.80),
    # 4-digit internal numeric code → fc (fecha cobro) at low confidence
    (re.compile(r'^[0-9]{4}$'), "fc", 0.38),
    # 3-digit number → fp (first payment) at low confidence
    (re.compile(r'^[0-9]{3}$'), "fp", 0.35),
    # Full name: 3+ capitalized words (handles accented chars)
    (
        re.compile(
            r'^[A-ZÁÉÍÓÚÑ\u00C0-\u00FF][^\s]{1,30}'
            r'(?:\s+[A-ZÁÉÍÓÚÑ\u00C0-\u00FF][^\s]{1,30}){2,}$'
        ),
        "nombre",
        0.78,
    ),
    # Short uppercase alias: 2–15 uppercase ASCII/accented chars, single word
    (re.compile(r'^[A-ZÁÉÍÓÚÑ]{2,15}$'), "alias", 0.52),
]

# Minimum fraction of sample values that must match for a field to "win"
_MIN_MATCH_RATIO: float = 0.40


def infer_from_values(sample_values: list[Any]) -> tuple[str | None, float, str]:
    """
    Analyse up to 20 non-empty sample values and return the inferred
    (canonical_field, confidence, evidence_label).

    Scoring: score = mean_confidence × sqrt(match_ratio).
    This rewards both high per-value confidence AND consistency.

    Returns (None, 0.0, "vacio") when the input is empty.
    Returns (None, 0.0, "sin_patron") when no rule matches adequately.
    """
    values = [str(v).strip() for v in sample_values if str(v).strip() not in ("", "None")][:20]
    if not values:
        return (None, 0.0, "vacio")

    votes: dict[str, list[float]] = {}
    for v in values:
        for pattern, field, conf in _VALUE_RULES:
            if pattern.fullmatch(v):
                votes.setdefault(field, []).append(conf)
                break  # first matching rule wins per value

    if not votes:
        return (None, 0.0, "sin_patron")

    best_field: str | None = None
    best_score: float = 0.0
    for field, confs in votes.items():
        match_ratio = len(confs) / len(values)
        if match_ratio < _MIN_MATCH_RATIO:
            continue
        score = (sum(confs) / len(confs)) * (match_ratio ** 0.5)
        if score > best_score:
            best_score = score
            best_field = field

    if best_field:
        return (best_field, round(min(best_score, 0.97), 3), "valor_patron")
    return (None, 0.0, "sin_patron")


# ---------------------------------------------------------------------------
# Header-row detector
# ---------------------------------------------------------------------------

# Tokens (lowercased, non-alphanumeric stripped) that strongly suggest a
# cell contains a column header rather than a data value.
_STRONG_HEADER_TOKENS: frozenset[str] = frozenset({
    "alias", "nombre", "nombrecompleto", "fullname", "name", "agente", "agent",
    "email", "correo", "mail",
    "telefono", "phone", "cel", "celular", "extension", "ext",
    "empresa", "company", "ciudad", "city", "pais", "country",
    "ubicacion", "location", "sede",
    "fp", "fc", "fcc", "fpc", "fcobro", "fpago",
    "grupo", "group", "team",
    "voip", "numerovoip", "linea", "numlinea",
    "imei", "device", "equipo",
    "deuda", "saldo", "debe", "balance",
    "password", "contrasena", "contraseña", "pass",
    "fecha", "date", "cobro", "pago",
    "numero", "numext", "numericext",
})


def _cell_header_score(raw: Any) -> float:
    """Return a score for how 'column-header-like' a single cell value is."""
    s = str(raw).strip() if raw is not None else ""
    if not s:
        return 0.0

    # Normalise: strip all non-alphanumeric, lowercase
    norm = re.sub(r"[^a-z0-9áéíóúñ]", "", s.lower())
    if not norm:
        return 0.0

    # Strong match
    if norm in _STRONG_HEADER_TOKENS:
        return 3.0

    # Partial match: token of ≥4 chars appears inside norm or vice-versa
    for token in _STRONG_HEADER_TOKENS:
        if len(token) >= 4 and (norm.startswith(token) or token in norm):
            return 2.0

    # Short label-like string (not only digits/currency)
    if len(s) <= 30 and re.search(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]", s):
        if re.fullmatch(r"\d{8,}", s):   # long number → penalise
            return -0.8
        if re.match(r"^\$", s):          # currency → penalise
            return -0.8
        return 0.6

    # Large / purely numeric → likely data
    return -0.3


def detect_header_row(df: Any, max_scan: int = 10) -> int:
    """
    Scan the first *max_scan* rows of a DataFrame and return the 0-based
    index of the row most likely to contain column headers.

    Returns 0 when the first row already looks best *or* when the margin
    between the winner and row-0 is not large enough to be reliable.
    This ensures no regression for well-formed files.
    """
    limit = min(max_scan, len(df))
    if limit <= 1:
        return 0

    scores: list[float] = []
    for i in range(limit):
        row = df.iloc[i].tolist()
        non_null = [v for v in row if v is not None and str(v).strip()]
        if not non_null:
            scores.append(-999.0)  # blank rows score very low
            continue
        row_score = sum(_cell_header_score(v) for v in row)
        # Bonus proportional to fill rate (header rows tend to be fully filled)
        fill_rate = len(non_null) / len(row) if row else 0
        row_score += fill_rate * 0.5
        scores.append(row_score)

    best_idx = max(range(len(scores)), key=lambda i: scores[i])

    # Only deviate from row 0 if the winner is clearly better.
    # Condition: winner score > 1.5× row-0 score  OR  row-0 score is ≤ 0.
    if best_idx > 0:
        s0 = scores[0]
        s_best = scores[best_idx]
        if s0 <= 0 or s_best > s0 * 1.5:
            return best_idx

    return 0


# ---------------------------------------------------------------------------
# Multi-table region detection
# ---------------------------------------------------------------------------


def detect_table_regions(df: Any) -> list[dict]:
    """
    Detect logical table regions within a sheet separated by near-empty rows.

    Returns a list of {inicio_fila, fin_fila} dicts (1-based row numbers,
    matching Excel/human convention) **only when more than one region is
    found**.  Returns an empty list for single-table sheets.
    """
    if df is None or len(df) == 0:
        return []

    n_cols = len(df.columns)
    if n_cols == 0:
        return []

    regions: list[dict] = []
    start = 0

    for i in range(len(df)):
        row = df.iloc[i].tolist()
        non_empty = sum(1 for v in row if v is not None and str(v).strip())
        empty_ratio = 1.0 - (non_empty / n_cols)

        if empty_ratio >= 0.85 and i > start:
            # +1 converts 0-based to 1-based (human / Excel row numbers)
            regions.append({"inicio_fila": start + 1, "fin_fila": i})
            start = i + 1

    if start < len(df):
        regions.append({"inicio_fila": start + 1, "fin_fila": len(df)})

    return regions if len(regions) > 1 else []


# ---------------------------------------------------------------------------
# Profile store – lightweight learned mapping cache
# ---------------------------------------------------------------------------

_PROFILES_PATH = Path(__file__).parent / "mapping_profiles.json"


class ProfileStore:
    """
    JSON-backed persistent store for column-name → canonical-field mappings
    learned from successful import operations.

    Key: SHA-1 of the sorted, normalised set of column headers.
    Value: {original_header: canonical_field, ...}

    Thread-safety: not required (single-process FastAPI).
    Failure-safe: all I/O errors are silently swallowed.
    """

    def __init__(self, path: Path = _PROFILES_PATH) -> None:
        self._path = path
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict:
        try:
            if self._path.exists():
                return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _commit(self) -> None:
        try:
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # best-effort; never crash on cache write

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(headers: list[str]) -> str:
        tokens = sorted(
            re.sub(r"[^a-z0-9]", "", h.lower()) for h in headers if h
        )
        return hashlib.sha1("|".join(tokens).encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, headers: list[str]) -> dict | None:
        """Return saved mapping dict, or None if not seen before."""
        return self._data.get(self._make_key(headers))

    def save(self, headers: list[str], mapping: dict[str, str]) -> None:
        """
        Persist a successful header → canonical-field mapping.
        Merges with any previously saved mapping for the same header set;
        empty/ignore values do not overwrite saved entries.
        """
        key = self._make_key(headers)
        existing = self._data.get(key, {})
        merged = dict(existing)
        for h, f in mapping.items():
            if f:  # skip "ignore" (empty-string) entries
                merged[h] = f
        self._data[key] = merged
        self._commit()


_default_store: ProfileStore | None = None


def get_profile_store() -> ProfileStore:
    """Return the process-level singleton ProfileStore."""
    global _default_store
    if _default_store is None:
        _default_store = ProfileStore()
    return _default_store


# ---------------------------------------------------------------------------
# Normalise helper (mirrors smart_importer._normalize_header)
# ---------------------------------------------------------------------------


def _norm(h: str) -> str:
    s = re.sub(r"[\s\-\.]+", "_", (h or "").strip().lower())
    return re.sub(r"[^a-z0-9_áéíóúñ]+", "", s)


# ---------------------------------------------------------------------------
# Combined advanced mapping suggestion
# ---------------------------------------------------------------------------


def suggest_mapping_advanced(
    header: str,
    sample_values: list[Any],
    profile_mapping: dict | None = None,
    _suggest_fn: Any = None,
) -> dict:
    """
    Return an enhanced column mapping combining four signal sources:

    1. Profile cache     – highest priority; exact recall of a prior import
    2. Header synonym    – exact / synonym / fuzzy match on the column name
    3. Value-pattern     – regex analysis of sampled data values
    4. Combined blend    – weighted merge when both (2) and (3) are available

    Parameters
    ----------
    header        : Original column header text.
    sample_values : Up to 20 data values from that column.
    profile_mapping: Optional previously learned {header: field} dict.
    _suggest_fn   : Injection hook for testing; defaults to
                    ``app.importers.smart_importer.suggest_mapping``.

    Returns
    -------
    dict with keys: header, normalized, campo, confianza, tipo, evidencia.
    The ``evidencia`` list contains human-readable reasoning strings.
    """
    # Lazy import avoids circular dependency at module load time
    if _suggest_fn is None:
        from app.importers.smart_importer import suggest_mapping as _sf
        _suggest_fn = _sf

    # ── 1. Profile cache ────────────────────────────────────────────
    if profile_mapping:
        cached = profile_mapping.get(header)
        if cached:
            return {
                "header": header,
                "normalized": _norm(header),
                "campo": cached,
                "confianza": 0.95,
                "tipo": "perfil_guardado",
                "evidencia": ["Mapeado desde perfil aprendido en importación anterior."],
            }

    # ── 2. Header-based suggestion ──────────────────────────────────
    h_result = _suggest_fn(header)
    h_field: str | None = h_result["campo"]
    h_conf: float = h_result["confianza"]
    h_tipo: str = h_result["tipo"]

    # ── 3. Value-pattern inference ──────────────────────────────────
    vp_field, vp_conf, _ = infer_from_values(sample_values)

    # ── 4. Decision logic ───────────────────────────────────────────

    # Is this an auto-generated unnamed column? ("Unnamed: N", "col_3", …)
    is_unnamed = bool(re.match(r"^(unnamed[_:\s]*\d+|col_\d+|field\d+)$", header.strip().lower()))

    if is_unnamed:
        if vp_field and vp_conf >= 0.45:
            return {
                "header": header,
                "normalized": _norm(header),
                "campo": vp_field,
                "confianza": vp_conf,
                "tipo": "valor_patron",
                "evidencia": [
                    "Columna sin nombre propio.",
                    f"Campo inferido por análisis de valores ({int(vp_conf * 100)}% de consistencia).",
                ],
            }
        return {
            "header": header,
            "normalized": _norm(header),
            "campo": None,
            "confianza": 0.0,
            "tipo": "desconocido",
            "evidencia": ["Nombre genérico de columna sin patrón de valores reconocible."],
        }

    # Both header and value agree → boost via weighted combination
    if h_field and vp_field and h_field == vp_field:
        combined = round(min(0.99, h_conf * 0.6 + vp_conf * 0.4), 3)
        return {
            "header": header,
            "normalized": _norm(header),
            "campo": h_field,
            "confianza": combined,
            "tipo": "combinado",
            "evidencia": [
                f"Nombre de columna ({h_tipo}, {int(h_conf * 100)}%) y "
                f"valores ({int(vp_conf * 100)}%) coinciden → campo '{h_field}'.",
            ],
        }

    # Header dominant (≥ 0.75) → trust it
    if h_field and h_conf >= 0.75:
        evidencia = [f"Nombre de columna '{header}' → campo '{h_field}' ({h_tipo}, {int(h_conf * 100)}%)."]
        if vp_field and vp_field != h_field:
            evidencia.append(
                f"Nota: valores sugieren '{vp_field}' ({int(vp_conf * 100)}%); "
                "se prioriza nombre de columna."
            )
        return {
            "header": header,
            "normalized": _norm(header),
            "campo": h_field,
            "confianza": h_conf,
            "tipo": h_tipo,
            "evidencia": evidencia,
        }

    # Value pattern dominant (≥ 0.65) → use it
    if vp_field and vp_conf >= 0.65:
        evidencia = [
            f"Patrón de valores → campo '{vp_field}' ({int(vp_conf * 100)}% de los datos muestreados)."
        ]
        if h_field and h_conf >= 0.40:
            evidencia.append(
                f"Nombre '{header}' también sugería '{h_field}' con {int(h_conf * 100)}%."
            )
        return {
            "header": header,
            "normalized": _norm(header),
            "campo": vp_field,
            "confianza": vp_conf,
            "tipo": "valor_patron",
            "evidencia": evidencia,
        }

    # Both weak → blend and pick the stronger signal's field
    if h_field and vp_field:
        if h_conf >= vp_conf:
            campo, conf = h_field, round(h_conf * 0.7 + vp_conf * 0.3, 3)
        else:
            campo, conf = vp_field, round(vp_conf * 0.7 + h_conf * 0.3, 3)
        return {
            "header": header,
            "normalized": _norm(header),
            "campo": campo,
            "confianza": conf,
            "tipo": "combinado",
            "evidencia": [
                f"Señales débiles: nombre sugiere '{h_field}' ({int(h_conf * 100)}%), "
                f"valores sugieren '{vp_field}' ({int(vp_conf * 100)}%).",
            ],
        }

    # Only header signal
    if h_field:
        return {
            **h_result,
            "evidencia": [f"Solo coincidencia por nombre de columna ({h_tipo}, {int(h_conf * 100)}%)."],
        }

    # Only value-pattern signal
    if vp_field:
        return {
            "header": header,
            "normalized": _norm(header),
            "campo": vp_field,
            "confianza": vp_conf,
            "tipo": "valor_patron",
            "evidencia": [
                f"Sin coincidencia de nombre; campo inferido por patrón de valores ({int(vp_conf * 100)}%)."
            ],
        }

    # No match at all
    return {
        "header": header,
        "normalized": _norm(header),
        "campo": None,
        "confianza": 0.0,
        "tipo": "desconocido",
        "evidencia": ["Sin coincidencia por nombre de columna ni por patrón de valores."],
    }
