## 1. Modelo

- [x] 1.1 Agregar `ClinVarStatus` (`encontrada`, `sin_resultados`, `ambigua`, `no_disponible`) y
  `VariantClassification` a `backend/models/genomics.py`, y el campo
  `clinvar: list[VariantClassification] = []` a `GenomicContext` (aditivo). Verificar con
  `pytest tests/test_agent_02_genomics.py` sin cambios en esos tests.

## 2. Cliente ClinVar

- [x] 2.1 Crear `backend/external/clinvar.py` con `ClinVarClient` (contexto async, `httpx`,
  `PUBMED_API_KEY` opcional) y `classify(gene, variant) -> VariantClassification`: `esearch`
  con `"{gen}"[gene] AND "{notación}"` (retmax 5) + `esummary`, usando `pubmed_limiter` y
  `pubmed_breaker` (D1, D2). Nunca propaga: cualquier error → `no_disponible`.
- [x] 2.2 Implementar la coincidencia verificada por título y gen (D3): `encontrada`,
  `sin_resultados`, `ambigua` con cantidad de candidatos; nunca el primer id por defecto.
  Respuesta sin `germline_classification` → `no_disponible`.
- [x] 2.3 Crear `tests/test_clinvar.py` con `httpx` mockeado (sin red): registro exacto
  (`TTR c.148G>A` → `VCV000013417`, Pathogenic, URL de la ficha); `Val30Met` con 5 registros sin
  coincidencia → `ambigua` con 5 candidatos; registro de otro gen → no `encontrada`; 0 ids →
  `sin_resultados`; HTTP 500 y timeout → `no_disponible`; respuesta sin
  `germline_classification` → `no_disponible`; los parámetros enviados contienen solo gen,
  notación y parámetros técnicos. Verificar con `pytest tests/test_clinvar.py`.

## 3. Integración en el contexto genómico

- [x] 3.1 Implementar el emparejamiento variante → gen (D4) en `pipeline/genomic_context.py`,
  con tope de 5 variantes (D6). Tests: variante dentro de una frase de `genetic_findings` con su
  gen; gen único en el caso; varios genes sin frase que los vincule → sin consultar.
- [x] 3.2 Hacer que `enrich()` consulte PharmGKB y ClinVar en paralelo y acumule ambas fuentes en
  `sources` con el estado agregado de D5; sin variantes, `ClinVar` queda `no_consultada` y no se
  instancia el cliente. Tests: el caso base no hace ninguna solicitud; PharmGKB se conserva
  cuando ClinVar falla y viceversa.
- [x] 3.3 Mostrar ClinVar en `GenomicContext.to_prompt_block()`: clasificación, estado de
  revisión y accession de cada `encontrada`; estado de las demás (`ambigua`, `sin_resultados`,
  `no_disponible`). Test sobre el texto del bloque con la variante TTR.

## 4. Evidencia y documentación

- [x] 4.1 Crear `scripts/demo_clinvar.py` con consultas reales a ClinVar: `TTR c.148G>A`
  (encontrada), `TTR Val30Met` (ambigua), una variante inexistente (sin resultados), y el bloque
  del Agente 02 para un caso con la variante TTR. Guarda `output/demo_clinvar/clinvar.json` y
  `resumen.txt`. `--sin-red` simula la caída de NCBI. Verificar corriéndolo.
- [x] 4.2 Correr `pytest tests/` completo y confirmar que no hay fallas nuevas respecto de
  `develop` (las 3 de OCR por falta de Tesseract son preexistentes).
- [x] 4.3 Actualizar `.claude/CLAUDE.md` (cliente en el árbol de `external/`, ítem en Sprint 4,
  `demo_clinvar.py` en la lista de scripts), `.claude/backlog.md` (tarjeta #71 hecha, limitación
  de la numeración clásica) y `.claude/architecture.md` (herramientas del Agente 02: "PharmGKB;
  ClinVar"). Verificar leyendo las secciones.
