"""Helpers for exporting static agent QR labels to printable PDF layouts."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable


# Layout definitions.
# Each layout drives how many QR cards fit per page and how large each QR is.
#
# sheet  - Hoja carta:   3 cols x 9 rows  = 27 QRs/page  (was 21)
# labels - Etiquetas:    4 cols x 11 rows = 44 QRs/page  (was 30)
# oficio - Hoja oficio:  3 cols x 10 rows = 30 QRs/page  (was 24)
#
# Units: PostScript points (1 pt = 1/72 inch).
# Letter page: 612 x 792 pt.  Oficio/Legal: 612 x 936 pt.
LAYOUTS: dict[str, dict] = {
    "sheet": {
        "page_size": (612.0, 792.0),  # letter 8.5" x 11"
        "columns": 3,
        "rows": 9,
        "margin_x": 18.0,
        "margin_y": 12.0,
        "cell_w": 192.0,   # (612 - 36) / 3 = 192
        "cell_h": 84.0,    # (792 - 24) / 9 = 85.3 -> 84 leaves a small buffer
        "qr_size": 62.0,
        "font_size": 8,
        "pad_bottom": 5.0,
        "pad_side": 5.0,
        "border_gap": 3.0,
        "title": "Hoja carta (27 QR)",
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
        "pad_bottom": 4.0,
        "pad_side": 4.0,
        "border_gap": 2.0,
        "title": "Etiquetas (44 QR)",
    },
    "oficio": {
        "page_size": (612.0, 936.0),  # oficio/legal 8.5" x 13"
        "columns": 3,
        "rows": 10,
        "margin_x": 18.0,
        "margin_y": 12.0,
        "cell_w": 192.0,
        "cell_h": 91.0,    # (936 - 24) / 10 = 91.2 -> 91
        "qr_size": 68.0,
        "font_size": 8,
        "pad_bottom": 5.0,
        "pad_side": 5.0,
        "border_gap": 3.0,
        "title": "Hoja oficio (30 QR)",
    },
}


def build_agent_qr_pdf(items: Iterable[dict], layout: str = "sheet") -> bytes:
    """Build a printable PDF containing one static QR per agent.

    Each card contains:
    - A rounded-rectangle border
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

        # Card border - shrunk by border_gap on all sides so adjacent cards don't touch
        card_x = x + border_gap
        card_y = y + border_gap
        card_w = cell_w - border_gap * 2
        card_h = cell_h - border_gap * 2
        pdf.roundRect(card_x, card_y, card_w, card_h, 5.0, stroke=1, fill=0)

        # Label row at the bottom of the card
        alias = str(item.get("alias") or item.get("nombre") or "SIN_ALIAS").strip() or "SIN_ALIAS"
        max_chars = max(10, int((card_w - pad_side * 2) / (font_size * 0.58)))
        label = f"ID {item.get('id')} | {alias[:max_chars]}"
        pdf.setFont("Helvetica-Bold", font_size)
        pdf.drawString(card_x + pad_side, card_y + pad_bottom, label)

        # QR image - centred horizontally, filling the space above the label
        label_zone_h = font_size + pad_bottom + 3.0   # label height + bottom pad + gap
        avail_h = card_h - label_zone_h - 4.0         # 4 pt top padding inside card
        avail_w = card_w - pad_side * 2
        draw_size = min(qr_size, avail_h, avail_w)

        qr_path = str(item.get("qr_path") or "").strip()
        if qr_path and draw_size > 20:
            qr_x = card_x + (card_w - draw_size) / 2
            qr_y_base = card_y + label_zone_h
            qr_y = qr_y_base + (avail_h - draw_size) / 2
            pdf.drawImage(
                ImageReader(qr_path),
                qr_x, qr_y,
                width=draw_size, height=draw_size,
                preserveAspectRatio=True, mask="auto",
            )

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()