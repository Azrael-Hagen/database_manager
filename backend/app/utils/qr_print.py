"""Helpers for exporting static agent QR labels to printable PDF layouts."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable, Mapping


# Layout definitions.
# Each layout drives how many QR cards fit per page and how large each QR is.
#
# sheet  - Hoja carta:   3 cols x 10 rows = 30 QRs/page
# labels - Etiquetas:    4 cols x 11 rows = 44 QRs/page  (was 30)
# oficio - Hoja oficio:  3 cols x 10 rows = 30 QRs/page
#
# Units: PostScript points (1 pt = 1/72 inch).
# Letter page: 612 x 792 pt.  Oficio/Legal: 612 x 936 pt.
LAYOUTS: dict[str, dict] = {
    "sheet": {
        "page_size": (612.0, 792.0),  # letter 8.5" x 11"
        "columns": 3,
        "rows": 10,
        "margin_x": 18.0,
        "margin_y": 12.0,
        "cell_w": 192.0,
        "cell_h": 76.8,
        "qr_size": 62.0,
        "font_size": 8,
        "pad_bottom": 2.0,
        "pad_side": 5.0,
        "border_gap": 1.0,
        "draw_border": True,
        "title": "Hoja carta (30 QR)",
    },
    "labels": {
        "page_size": (612.0, 792.0),  # letter
        "columns": 4,
        "rows": 11,
        "margin_x": 14.0,
        "margin_y": 12.0,
        "cell_w": 146.0,   # (612 - 28) / 4 = 146
        "cell_h": 69.0,    # (792 - 24) / 11 = 69.8 -> 69
        "qr_size": 50.0,
        "font_size": 7,
        "pad_bottom": 1.5,
        "pad_side": 4.0,
        "border_gap": 0.8,
        "draw_border": True,
        "title": "Etiquetas (44 QR)",
    },
    "oficio": {
        "page_size": (612.0, 936.0),  # oficio/legal 8.5" x 13"
        "columns": 3,
        "rows": 10,
        "margin_x": 18.0,
        "margin_y": 10.5,
        "cell_w": 192.0,
        "cell_h": 91.5,
        "qr_size": 84.0,
        "font_size": 8,
        "pad_bottom": 2.0,
        "pad_side": 5.0,
        "border_gap": 1.0,
        "draw_border": True,
        "title": "Hoja oficio (30 QR compacto)",
    },
}


def _apply_layout_overrides(base_cfg: dict, overrides: Mapping[str, Any] | None) -> dict:
    cfg = dict(base_cfg)
    numeric_limits = {
        "qr_size": (28.0, 140.0),
        "border_gap": (0.0, 12.0),
        "pad_bottom": (0.0, 12.0),
        "pad_side": (1.0, 16.0),
        "margin_x": (0.0, 60.0),
        "margin_y": (0.0, 60.0),
        "cell_h": (40.0, 180.0),
        "cell_w": (72.0, 260.0),
    }
    int_limits = {
        "rows": (6, 16),
        "columns": (2, 6),
    }

    overrides = overrides or {}
    explicit_cell_h = "cell_h" in overrides
    explicit_cell_w = "cell_w" in overrides

    for key, limits in int_limits.items():
        if key not in overrides:
            continue
        raw = overrides.get(key)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        low, high = limits
        cfg[key] = max(low, min(high, value))

    for key, limits in numeric_limits.items():
        if key not in overrides:
            continue
        raw = overrides.get(key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        low, high = limits
        cfg[key] = max(low, min(high, value))

    if "draw_border" in overrides:
        cfg["draw_border"] = bool(overrides.get("draw_border"))

    page_w, page_h = cfg["page_size"]
    margin_x = float(cfg["margin_x"])
    margin_y = float(cfg["margin_y"])
    columns = max(1, int(cfg["columns"]))
    rows = max(1, int(cfg["rows"]))

    if not explicit_cell_w:
        cfg["cell_w"] = max(72.0, (float(page_w) - (margin_x * 2.0)) / float(columns))
    if not explicit_cell_h:
        cfg["cell_h"] = max(40.0, (float(page_h) - (margin_y * 2.0)) / float(rows))

    return cfg


def build_agent_qr_pdf(items: Iterable[dict], layout: str = "sheet", layout_overrides: Mapping[str, Any] | None = None) -> bytes:
    """Build a printable PDF containing one static QR per agent.

    Each card contains:
    - The QR image centred in the card, as large as possible
    - A compact label (ID | alias) at the bottom of the card
    """
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise ValueError("La exportacion PDF requiere reportlab") from exc

    cfg = LAYOUTS.get(layout)
    if not cfg:
        raise ValueError(f"Layout no soportado: {layout}")
    cfg = _apply_layout_overrides(cfg, layout_overrides)

    page_w, page_h = cfg["page_size"]
    columns = int(cfg["columns"])
    rows = int(cfg["rows"])
    margin_x = float(cfg["margin_x"])
    margin_y = float(cfg["margin_y"])
    cell_w = float(cfg["cell_w"])
    cell_h = float(cfg["cell_h"])
    qr_size = float(cfg["qr_size"])
    font_size = int(cfg.get("font_size", 8))
    pad_bottom = float(cfg.get("pad_bottom", 5.0))
    pad_side = float(cfg.get("pad_side", 5.0))
    border_gap = float(cfg.get("border_gap", 3.0))
    draw_border = bool(cfg.get("draw_border", False))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.setTitle(f"Database Manager - QR {cfg['title']}")

    x_positions = [margin_x + col_idx * cell_w for col_idx in range(columns)]
    y_start = page_h - margin_y - cell_h
    per_page = columns * rows

    for index, item in enumerate(items):
        if index > 0 and index % per_page == 0:
            pdf.showPage()

        page_index = index % per_page
        row = page_index // columns
        col = page_index % columns
        x = x_positions[col]
        y = y_start - row * cell_h

        # Card geometry
        card_x = x + border_gap
        card_y = y + border_gap
        card_w = cell_w - border_gap * 2
        card_h = cell_h - border_gap * 2

        # Compact label rows at the bottom of the card
        alias = str(item.get("alias") or item.get("nombre") or "SIN_ALIAS").strip() or "SIN_ALIAS"
        ubicacion = str(item.get("ubicacion") or "").strip()
        line1_max_chars = max(10, int((card_w - pad_side * 2) / (font_size * 0.56)))
        line1 = f"ID {item.get('id')} | {alias[:line1_max_chars]}"

        line2_fs = max(6, font_size - 1)
        line2_gap = 0.8
        line2 = ""
        if ubicacion:
            line2_max_chars = max(8, int((card_w - pad_side * 2) / (line2_fs * 0.56)))
            line2 = f"Ubic: {ubicacion[:line2_max_chars]}"

        line1_y = card_y + pad_bottom + (line2_fs + line2_gap if line2 else 0)

        # QR image - centred horizontally, placed just above labels to save vertical space
        text_block_h = (line1_y - card_y) + font_size * 0.5
        label_gap = 1.2
        top_pad = 1.2
        avail_h = card_h - text_block_h - label_gap - top_pad
        avail_w = card_w - pad_side * 2
        draw_size = min(qr_size, avail_h, avail_w)

        # Build a compact content box around QR + text so lateral lines are tight.
        pdf.setFont("Helvetica-Bold", font_size)
        line1_w = pdf.stringWidth(line1, "Helvetica-Bold", font_size)
        line2_w = 0.0
        if line2:
            line2_w = pdf.stringWidth(line2, "Helvetica", line2_fs)

        content_pad_x = 4.0
        content_w = min(card_w, max(draw_size, line1_w, line2_w) + content_pad_x * 2)
        content_x = card_x + (card_w - content_w) / 2
        center_x = content_x + (content_w / 2)

        qr_path = str(item.get("qr_path") or "").strip()
        qr_y = card_y + text_block_h + label_gap
        if qr_path and draw_size > 20:
            qr_x = content_x + (content_w - draw_size) / 2
            pdf.drawImage(
                ImageReader(qr_path),
                qr_x, qr_y,
                width=draw_size, height=draw_size,
                preserveAspectRatio=True, mask="auto",
            )

        # Draw labels after QR using compact centered alignment.
        pdf.setFont("Helvetica-Bold", font_size)
        pdf.drawCentredString(center_x, line1_y, line1)
        if line2:
            pdf.setFont("Helvetica", line2_fs)
            pdf.drawCentredString(center_x, card_y + pad_bottom, line2)

        if draw_border:
            box_bottom = card_y + 0.5
            box_top = min(card_y + card_h - 0.5, qr_y + draw_size + top_pad)
            box_h = max(10.0, box_top - box_bottom)
            pdf.setLineWidth(0.6)
            pdf.roundRect(content_x, box_bottom, content_w, box_h, 2.0, stroke=1, fill=0)

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()