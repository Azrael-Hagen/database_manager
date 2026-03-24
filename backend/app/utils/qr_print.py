"""Helpers for exporting static agent QR labels to printable PDF layouts."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable


LAYOUTS: dict[str, dict[str, float | int | tuple[float, float]]] = {
    "sheet": {
        "page_size": (612.0, 792.0),  # letter
        "columns": 3,
        "rows": 7,
        "margin_x": 24.0,
        "margin_y": 24.0,
        "cell_w": 180.0,
        "cell_h": 100.0,
        "qr_size": 58.0,
        "title": "Hoja de impresion",
    },
    "labels": {
        "page_size": (612.0, 792.0),  # letter
        "columns": 3,
        "rows": 10,
        "margin_x": 18.0,
        "margin_y": 20.0,
        "cell_w": 188.0,
        "cell_h": 72.0,
        "qr_size": 44.0,
        "title": "Etiquetas adhesivas",
    },
    "oficio": {
        "page_size": (612.0, 936.0),  # oficio 8.5 x 13
        "columns": 3,
        "rows": 8,
        "margin_x": 24.0,
        "margin_y": 24.0,
        "cell_w": 180.0,
        "cell_h": 110.0,
        "qr_size": 62.0,
        "title": "Hoja oficio",
    },
}


def build_agent_qr_pdf(items: Iterable[dict], layout: str = "sheet") -> bytes:
    """Build a printable PDF containing one static QR per agent."""
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

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.setTitle(f"Database Manager - QR {cfg['title']}")

    x_positions = [margin_x + (index * cell_w) for index in range(columns)]
    y_start = page_h - margin_y - cell_h
    per_page = columns * rows

    items_list = list(items)
    for index, item in enumerate(items_list):
        if index > 0 and index % per_page == 0:
            pdf.showPage()

        page_index = index % per_page
        row = page_index // columns
        col = page_index % columns
        x = x_positions[col]
        y = y_start - (row * cell_h)

        pdf.roundRect(x, y, cell_w - 8.0, cell_h - 8.0, 8.0, stroke=1, fill=0)

        qr_path = str(item.get("qr_path") or "").strip()
        if qr_path:
            qr_y = y + cell_h - qr_size - 8.0
            pdf.drawImage(ImageReader(qr_path), x + 8.0, qr_y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto")

        # Etiqueta minima operativa: solo ID y alias.
        text_x = x + 8.0
        text_y = y + 8.0
        alias = str(item.get("alias") or "SIN_ALIAS").strip() or "SIN_ALIAS"
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(text_x, text_y, f"ID {item.get('id')} | {alias[:30]}")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
