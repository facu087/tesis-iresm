"""
Demo de verificación — Módulo de ingesta: extracción de PDF nativo (pdfplumber).

Genera (o usa) un PDF clínico real, lo procesa con el extractor y guarda en disco
DOS artefactos tangibles que se pueden abrir y capturar para Trello:
    1. El PDF de entrada      → output/demo_ingesta/informe_clinico.pdf
    2. El texto extraído      → output/demo_ingesta/texto_extraido.txt

La idea es mostrar lado a lado: "este documento entró → este texto salió".

Uso:
    # Genera un PDF de ejemplo realista y lo procesa:
    python scripts/demo_extraccion.py

    # O con un PDF clínico propio:
    python scripts/demo_extraccion.py ruta/al/informe.pdf
"""

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

# Permite importar el paquete backend sin instalar
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ingestion.extractor import extract_from_pdf

_SEP = "═" * 70
_OUT_DIR = Path(__file__).parent.parent / "output" / "demo_ingesta"

# Contenido del informe de ejemplo (caso clínico anonimizado de la tesis).
_INFORME = [
    ("titulo", "INFORME NEUROLÓGICO"),
    ("sub", "Caso clínico anonimizado — Servicio de Neurología"),
    ("espacio", ""),
    ("h", "DATOS DEL PACIENTE"),
    ("p", "Sexo: masculino    Edad: 42 años    Lateralidad: diestro"),
    ("espacio", ""),
    ("h", "MOTIVO DE CONSULTA"),
    ("p", "Debilidad progresiva en miembros inferiores de 18 meses de evolución."),
    ("espacio", ""),
    ("h", "ESTUDIOS COMPLEMENTARIOS"),
    ("p", "Electromiografía (EMG): velocidad de conducción nerviosa disminuida."),
    ("p", "Potenciales de acción sensoriales ausentes en nervio sural bilateral."),
    ("p", "Patrón compatible con neuropatía axonal sensitivomotora."),
    ("p", "Panel genético CMT (Charcot-Marie-Tooth): NEGATIVO."),
    ("espacio", ""),
    ("h", "ANTECEDENTES"),
    ("p", "Diabetes mellitus tipo 2 de 10 años de evolución. HbA1c: 8.2%."),
    ("p", "Sin antecedentes familiares neurológicos relevantes."),
    ("espacio", ""),
    ("h", "TRATAMIENTO ACTUAL"),
    ("p", "Pregabalina 150 mg/día por vía oral."),
]


def _generar_pdf_ejemplo(destino: Path) -> bytes:
    """Genera un PDF clínico realista y lo guarda en disco. Devuelve sus bytes."""
    c = canvas.Canvas(str(destino), pagesize=A4)
    ancho, alto = A4
    y = alto - 2.5 * cm

    for tipo, texto in _INFORME:
        if tipo == "titulo":
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(ancho / 2, y, texto)
            y -= 0.7 * cm
        elif tipo == "sub":
            c.setFont("Helvetica-Oblique", 10)
            c.drawCentredString(ancho / 2, y, texto)
            c.line(2.5 * cm, y - 0.3 * cm, ancho - 2.5 * cm, y - 0.3 * cm)
            y -= 0.9 * cm
        elif tipo == "h":
            c.setFont("Helvetica-Bold", 11)
            c.drawString(2.5 * cm, y, texto)
            y -= 0.55 * cm
        elif tipo == "p":
            c.setFont("Helvetica", 10)
            c.drawString(2.5 * cm, y, texto)
            y -= 0.5 * cm
        else:  # espacio
            y -= 0.3 * cm

    c.save()
    return destino.read_bytes()


def main() -> None:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        pdf_entrada = Path(sys.argv[1])
        pdf_bytes = pdf_entrada.read_bytes()
        origen = str(pdf_entrada)
    else:
        pdf_entrada = _OUT_DIR / "informe_clinico.pdf"
        pdf_bytes = _generar_pdf_ejemplo(pdf_entrada)
        origen = str(pdf_entrada)

    texto = extract_from_pdf(pdf_bytes)

    # Guarda el texto extraído como artefacto tangible
    txt_salida = _OUT_DIR / "texto_extraido.txt"
    txt_salida.write_text(texto, encoding="utf-8")

    print(_SEP)
    print("  DEMO — Extracción de texto de PDF nativo (pdfplumber)")
    print(_SEP)
    print(f"  PDF de entrada     : {origen}")
    print(f"  Tamaño del PDF     : {len(pdf_bytes):,} bytes")
    print(f"  Texto extraído     : {txt_salida}")
    print(_SEP)
    print("  CONTENIDO EXTRAÍDO:")
    print(_SEP)
    print(texto)
    print(_SEP)
    print(f"  ✓ Extracción exitosa — {len(texto):,} caracteres recuperados.")
    print()
    print("  ARTEFACTOS GENERADOS (abrir y capturar para Trello):")
    print(f"    • PDF original  → {pdf_entrada}")
    print(f"    • Texto extraído → {txt_salida}")
    print(_SEP)


if __name__ == "__main__":
    main()
