"""
Extracción de texto de documentos clínicos.
Soporta PDF nativos (pdfplumber) y texto plano.
OCR para PDFs escaneados se agrega en Sprint 2.
"""

import io
import pdfplumber


def extract_from_pdf(file_bytes: bytes) -> str:
    """Extrae texto de un PDF nativo. Devuelve string limpio."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())
    return "\n\n".join(text_parts)


def extract_from_text(file_bytes: bytes, encoding: str = "utf-8") -> str:
    return file_bytes.decode(encoding, errors="replace").strip()


def extract(filename: str, file_bytes: bytes) -> str:
    """
    Punto de entrada principal. Detecta el tipo de archivo por extensión
    y delega a la función correspondiente.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        text = extract_from_pdf(file_bytes)
        # Si el PDF no tiene texto extraíble es un escaneado — se maneja en Sprint 2
        if not text.strip():
            raise ValueError(
                f"El archivo '{filename}' parece ser un PDF escaneado. "
                "El soporte OCR se implementa en Sprint 2."
            )
        return text

    if ext in ("txt", "md"):
        return extract_from_text(file_bytes)

    raise ValueError(f"Formato no soportado: .{ext}. Formatos válidos: pdf, txt.")
