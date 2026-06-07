"""
Tests del módulo de ingesta (backend/ingestion/extractor.py).
Los tests de OCR usan imágenes generadas localmente — no llaman APIs externas.
"""

import io
import pytest
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

from backend.ingestion.extractor import (
    extract,
    extract_from_pdf,
    extract_from_pdf_ocr,
    extract_from_text,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_native_pdf(text: str) -> bytes:
    """Genera un PDF nativo con texto embebido usando reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(50, 750, text)
    c.save()
    return buf.getvalue()


def _make_image_pdf(text: str) -> bytes:
    """
    Genera un PDF de imagen (simula escaneado) guardando una imagen PIL como PDF.
    El texto se renderiza con la fuente por defecto de Pillow.
    """
    img = Image.new("RGB", (1200, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((50, 70), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


# ── Tests: extract_from_pdf (nativo) ──────────────────────────────────────────

def test_extract_from_pdf_retorna_texto():
    pdf = _make_native_pdf("Neuropatia axonal, paciente 42 anios.")
    text = extract_from_pdf(pdf)
    assert "Neuropatia" in text


def test_extract_from_pdf_vacio_retorna_string_vacio():
    buf = io.BytesIO()
    canvas.Canvas(buf).save()
    text = extract_from_pdf(buf.getvalue())
    assert text == ""


# ── Tests: extract_from_pdf_ocr ────────────────────────────────────────────────

def test_extract_from_pdf_ocr_detecta_texto():
    pdf = _make_image_pdf("Panel CMT negativo")
    text = extract_from_pdf_ocr(pdf)
    # OCR puede tener pequeñas variaciones; verificamos palabras clave
    assert "Panel" in text or "CMT" in text or "negativo" in text


def test_extract_from_pdf_ocr_retorna_string():
    pdf = _make_image_pdf("LCR normal")
    text = extract_from_pdf_ocr(pdf)
    assert isinstance(text, str)


# ── Tests: extract_from_text ───────────────────────────────────────────────────

def test_extract_from_text_utf8():
    content = "Diagnóstico: neuropatía axonal."
    text = extract_from_text(content.encode("utf-8"))
    assert text == content


def test_extract_from_text_strip():
    text = extract_from_text(b"  texto con espacios  ")
    assert text == "texto con espacios"


# ── Tests: extract (punto de entrada principal) ────────────────────────────────

def test_extract_pdf_nativo():
    pdf = _make_native_pdf("Caso clinico base.")
    text = extract("informe.pdf", pdf)
    assert "Caso" in text


def test_extract_pdf_escaneado_usa_ocr():
    pdf = _make_image_pdf("Hipotension ortostatica")
    text = extract("escaneado.pdf", pdf)
    assert isinstance(text, str)
    assert len(text) > 0


def test_extract_txt():
    text = extract("nota.txt", b"Texto plano de prueba.")
    assert text == "Texto plano de prueba."


def test_extract_md():
    text = extract("notas.md", b"# Caso\nNeuropatia axonal.")
    assert "Neuropatia" in text


def test_extract_formato_no_soportado():
    with pytest.raises(ValueError, match="Formato no soportado"):
        extract("imagen.jpg", b"\xff\xd8\xff")
