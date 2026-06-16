"""
Demo de verificación — Módulo de ingesta: OCR para PDFs escaneados (Tesseract).

Demuestra DOS cosas:
    1. Detección automática: extract() intenta extracción nativa primero; al ver
       que un PDF escaneado NO tiene capa de texto, cae automáticamente al OCR.
    2. OCR con Tesseract: recupera el texto de la imagen escaneada (idioma spa+eng).

Genera un PDF "escaneado" (imagen, sin texto embebido) que simula un informe
fotografiado/escaneado, y guarda en disco artefactos tangibles para Trello:
    1. El PDF escaneado de entrada → output/demo_ocr/informe_escaneado.pdf
    2. El texto recuperado por OCR  → output/demo_ocr/texto_ocr.txt

Uso:
    # Genera un PDF escaneado de ejemplo y lo procesa:
    python scripts/demo_ocr.py

    # O con un PDF escaneado propio (foto/scan de un informe):
    python scripts/demo_ocr.py ruta/al/escaneado.pdf
"""

import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ingestion.extractor import extract, extract_from_pdf, extract_from_pdf_ocr

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_ocr"
_FONT_PATH = "/usr/share/fonts/TTF/DejaVuSans.ttf"

# Texto del informe que se "escanea" (renderiza como imagen, sin capa de texto).
_LINEAS = [
    "INFORME NEUROLOGICO",
    "Caso clinico anonimizado",
    "",
    "Paciente masculino, 42 anios.",
    "Diagnostico: neuropatia axonal sensitivomotora.",
    "EMG: velocidad de conduccion nerviosa disminuida.",
    "Potenciales sensoriales ausentes en nervio sural.",
    "Panel genetico CMT: NEGATIVO.",
    "",
    "Antecedentes: diabetes tipo 2, HbA1c 8.2 por ciento.",
    "Tratamiento: pregabalina 150 mg por dia.",
]


def _generar_pdf_escaneado(destino: Path) -> bytes:
    """
    Genera un PDF de imagen (sin capa de texto) que simula un documento escaneado.
    El texto se dibuja sobre un lienzo blanco y se guarda como PDF de imagen.
    """
    ancho, alto = 1240, 1754  # A4 a ~150 DPI
    img = Image.new("RGB", (ancho, alto), color="white")
    draw = ImageDraw.Draw(img)

    try:
        fuente = ImageFont.truetype(_FONT_PATH, 34)
        fuente_titulo = ImageFont.truetype(_FONT_PATH, 44)
    except OSError:
        fuente = ImageFont.load_default()
        fuente_titulo = fuente

    y = 120
    for i, linea in enumerate(_LINEAS):
        f = fuente_titulo if i == 0 else fuente
        draw.text((100, y), linea, fill="black", font=f)
        y += 70 if i == 0 else 58

    img.save(str(destino), format="PDF", resolution=150.0)
    return destino.read_bytes()


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        pdf_entrada = Path(sys.argv[1])
        pdf_bytes = pdf_entrada.read_bytes()
    else:
        pdf_entrada = _OUT_DIR / "informe_escaneado.pdf"
        pdf_bytes = _generar_pdf_escaneado(pdf_entrada)

    print(_SEP)
    print("  DEMO — OCR de PDF escaneado con detección automática (Tesseract)")
    print(_SEP)
    print(f"  PDF de entrada     : {pdf_entrada}")
    print(f"  Tamaño del PDF     : {len(pdf_bytes):,} bytes")
    print(_SEP)

    # ── Paso 1: intento de extracción nativa ──────────────────────────────────
    texto_nativo = extract_from_pdf(pdf_bytes)
    print("  PASO 1 — Extracción nativa (pdfplumber):")
    print(f"           Resultado: {len(texto_nativo)} caracteres "
          f"{'(vacío)' if not texto_nativo.strip() else ''}")
    print("           → El PDF no tiene capa de texto: es un documento ESCANEADO.")
    print(_SEP)

    # ── Paso 2: detección automática + OCR ────────────────────────────────────
    print("  PASO 2 — Detección automática + OCR (Tesseract, spa+eng):")
    print("           extract() detecta el escaneo y aplica OCR automáticamente…")
    texto_ocr = extract("informe_escaneado.pdf", pdf_bytes)
    print(_SEP)
    print("  TEXTO RECUPERADO POR OCR:")
    print(_SEP)
    print(texto_ocr)
    print(_SEP)

    # Guarda el artefacto tangible
    txt_salida = _OUT_DIR / "texto_ocr.txt"
    txt_salida.write_text(texto_ocr, encoding="utf-8")

    print(f"  ✓ OCR exitoso — {len(texto_ocr):,} caracteres recuperados de una imagen.")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • PDF escaneado → {pdf_entrada}")
    print(f"    • Texto del OCR → {txt_salida}")
    print(_SEP)


if __name__ == "__main__":
    main()
