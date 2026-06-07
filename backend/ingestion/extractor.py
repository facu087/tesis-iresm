"""
Extracción de texto de documentos clínicos.
Soporta PDF nativos (pdfplumber), PDFs escaneados (Tesseract OCR) y texto plano.
Compatible con Linux, macOS y Windows.
"""

import io
import os
import platform
import sys

import pdfplumber
import pypdfium2 as pdfium
import pytesseract
from PIL import Image

# Directorio de modelos de idioma de Tesseract (relativo al proyecto).
# Permite usar paquetes locales sin requerir instalación global con sudo.
_TESSDATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".tessdata")
_TESSDATA_DIR = os.path.abspath(_TESSDATA_DIR)

# Idiomas a usar en OCR: español + inglés (terminología médica mixta).
_OCR_LANG = "spa+eng"

# ── Detección del binario Tesseract por plataforma ────────────────────────────
# En Linux el binario está en PATH. En macOS (Homebrew) y Windows hay rutas
# específicas que pytesseract no detecta automáticamente.
def _configure_tesseract() -> None:
    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in candidates:
            if os.path.isfile(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return
        print(
            "[NEXUS] Advertencia: no se encontró Tesseract en la ruta por defecto "
            "de Windows. Instalalo desde https://github.com/UB-Mannheim/tesseract/wiki "
            "y asegurate de que esté en PATH.",
            file=sys.stderr,
        )
    elif system == "Darwin":
        candidates = [
            "/opt/homebrew/bin/tesseract",   # Apple Silicon
            "/usr/local/bin/tesseract",       # Intel Mac
        ]
        for path in candidates:
            if os.path.isfile(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return

_configure_tesseract()

# DPI de renderizado: 300 es el mínimo recomendado para OCR médico.
_RENDER_DPI = 300


def extract_from_pdf(file_bytes: bytes) -> str:
    """Extrae texto de un PDF nativo con pdfplumber. Devuelve string limpio."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())
    return "\n\n".join(text_parts)


def extract_from_pdf_ocr(file_bytes: bytes) -> str:
    """
    Extrae texto de un PDF escaneado mediante OCR (Tesseract).
    Renderiza cada página a imagen a 300 DPI y aplica OCR con idioma spa+eng.
    """
    scale = _RENDER_DPI / 72  # pypdfium2 trabaja en puntos (72 ppp base)
    pdf = pdfium.PdfDocument(file_bytes)
    text_parts = []

    tessdata_env = {"TESSDATA_PREFIX": _TESSDATA_DIR}
    original_env = {k: os.environ.get(k) for k in tessdata_env}
    os.environ.update(tessdata_env)

    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            bitmap = page.render(scale=scale, rotation=0)
            pil_image: Image.Image = bitmap.to_pil()
            page_text = pytesseract.image_to_string(pil_image, lang=_OCR_LANG)
            if page_text.strip():
                text_parts.append(page_text.strip())
    finally:
        for k, v in original_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        pdf.close()

    return "\n\n".join(text_parts)


def extract_from_text(file_bytes: bytes, encoding: str = "utf-8") -> str:
    """Decodifica un archivo de texto plano."""
    return file_bytes.decode(encoding, errors="replace").strip()


def extract(filename: str, file_bytes: bytes) -> str:
    """
    Punto de entrada principal. Detecta el tipo de archivo por extensión
    y delega a la función correspondiente.
    Para PDFs intenta extracción nativa primero; si no hay texto usa OCR.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        text = extract_from_pdf(file_bytes)
        if text.strip():
            return text
        # Sin texto extraíble → PDF escaneado, aplicar OCR
        return extract_from_pdf_ocr(file_bytes)

    if ext in ("txt", "md"):
        return extract_from_text(file_bytes)

    raise ValueError(f"Formato no soportado: .{ext}. Formatos válidos: pdf, txt.")
