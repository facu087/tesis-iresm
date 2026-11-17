# Modelos vigentes por agente

## Objetivo
Reemplazar GPT-4o (deprecado) por un modelo vigente de gama media para el Agente 02,
manteniendo el último Opus para los Agentes 01, 04 y 06 y Gemini 3.1 Pro para el 03.

## Por qué
El equipo quiere que la exposición corra con modelos actuales y buenos, sin elegir el más caro.
GPT-6.1 Sol (USD 2 / 10 por millón) razona: rechaza `temperature` y necesita `reasoning_effort`
y un techo mayor que 4.096 tokens.

## Alcance
- Claude: `claude-opus-5-5` (último Opus; Fable 5.2 a USD 8 / 40 queda descartado por costo).
- OpenAI: `gpt-4o` → `gpt-6.1-sol`.
- Google: `gemini-3.1-pro-preview` → `gemini-4-argon` (3.1 Pro devuelve 404 con la clave del equipo; Argon verificado con una llamada real el 2026-11-17).

## Tareas
- [x] T1 — Adaptador de OpenAI, modelos por defecto (02 y 03), techo del Agente 02, tarifas, tests y docs. Ruta: delegada (2+ archivos no triviales). Evidencia: RED en 9 tests nuevos/ajustados → GREEN; suite completa 1929 ok y 5 fallas previas (2 de separador de ruta en Windows, confirmadas en develop; 3 de OCR sin Tesseract local).
- [ ] T2 — Corrida real con las tres claves. Llamada mínima OK a los tres proveedores el 2026-11-17; falta el análisis completo.

## Verificación
- `pytest tests/test_proveedor_por_agente.py tests/test_telemetry.py tests/test_pdf_exporter.py`
- `pytest` completo.
