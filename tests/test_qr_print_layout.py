"""Tests for QR PDF layout compaction rules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.utils.qr_print import LAYOUTS, _apply_layout_overrides


def test_layout_overrides_accept_rows_and_columns_with_recomputed_cells():
    base = LAYOUTS["sheet"]
    updated = _apply_layout_overrides(base, {"rows": 10, "columns": 3})

    assert updated["rows"] == 10
    assert updated["columns"] == 3

    page_w, page_h = updated["page_size"]
    expected_cell_w = (page_w - (2 * updated["margin_x"])) / updated["columns"]
    expected_cell_h = (page_h - (2 * updated["margin_y"])) / updated["rows"]
    assert updated["cell_w"] == expected_cell_w
    assert updated["cell_h"] == expected_cell_h


def test_layout_overrides_keep_explicit_cell_sizes_if_provided():
    base = LAYOUTS["oficio"]
    updated = _apply_layout_overrides(base, {"rows": 10, "cell_h": 88.0})

    assert updated["rows"] == 10
    assert updated["cell_h"] == 88.0


def test_layout_overrides_clamp_rows_and_columns_limits():
    base = LAYOUTS["labels"]
    updated = _apply_layout_overrides(base, {"rows": 999, "columns": 99})

    assert updated["rows"] == 16
    assert updated["columns"] == 6


def test_layout_overrides_ignore_invalid_rows_and_columns_types():
    base = LAYOUTS["sheet"]
    updated = _apply_layout_overrides(base, {"rows": "abc", "columns": None})

    assert updated["rows"] == base["rows"]
    assert updated["columns"] == base["columns"]


def test_default_sheet_density_is_4x9():
    cfg = LAYOUTS["sheet"]
    assert cfg["columns"] == 4
    assert cfg["rows"] == 9


def test_default_oficio_density_is_4x10():
    cfg = LAYOUTS["oficio"]
    assert cfg["columns"] == 4
    assert cfg["rows"] == 10
