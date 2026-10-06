## Context

- `GenomicContext` (`backend/models/genomics.py`) ya trae `variants` (notaciones sueltas, p. ej.
  `p.Val30Met`, `c.148G>A`), `genetic_findings` (frases como
  `TTR p.Val30Met (c.148G>A) heterocigota`), `genes` saneados y `sources: list[GenomicSource]`.
  Las variantes **no traen su gen**: el emparejamiento es parte de este cambio.
- `pipeline/genomic_context.enrich()` consulta PharmGKB y hoy **reemplaza** `sources` con una sola
  fuente. Agregar ClinVar obliga a que las fuentes se acumulen.
- El cliente de PubMed (`external/pubmed.py`) ya usa E-utilities con `httpx.AsyncClient`, clave
  opcional `PUBMED_API_KEY`, y `pubmed_limiter`/`pubmed_breaker` de `external/rate_limiter.py`.
- Medición del 2026-10-06 sobre la API real: `esummary` de `db=clinvar` trae `title`
  (`NM_000371.4(TTR):c.148G>A (p.Val50Met)`), `accession` (`VCV000013417`),
  `germline_classification.{description, review_status, last_evaluated}` y `genes[].symbol`.
  La notación clásica `Val30Met` trae 5 registros, uno de otra variante.

## Goals / Non-Goals

**Goals:**
- Cliente ClinVar con coincidencia verificada y estados explícitos por variante.
- Integración en `enrich()` sin tocar el prompt de sistema ni el código del Agente 02.
- Evidencia reproducible: demo con consulta real y tests sin red.

**Non-Goals:**
- Convertir numeración clásica a HGVS (TTR Val30Met → p.Val50Met). Sin esa conversión la
  variante queda `ambigua`, que es la respuesta honesta.
- Clasificaciones somáticas/oncogénicas: solo `germline_classification`.
- Usar ClinVar en otros agentes o en el reporte del frontend/PDF (el Agente 02 lo traslada a sus
  hipótesis).

## Decisions

### D1. Cliente propio en `external/clinvar.py`, no un método de `PubMedClient`
Mismo servicio, pero otra base y otro contrato de salida. Reutiliza la URL base de E-utilities, la
clave `PUBMED_API_KEY` y el **mismo** `pubmed_limiter` y `pubmed_breaker`: ClinVar y PubMed
comparten cupo, y un NCBI caído tiene que abrir el circuito para los dos.
- *Alternativa descartada — limitador propio para ClinVar.* Dos limitadores de 3 req/s sobre el
  mismo cupo permitirían 6 req/s reales y NCBI respondería 429.

### D2. Consulta: `"{gen}"[gene] AND "{notación}"`, luego `esummary` de hasta 5 ids
Entrecomillar evita que E-utilities interprete `>` u otros caracteres de la notación. Se piden
como máximo 5 identificadores: si hay más, ya es `ambigua` salvo coincidencia exacta entre ellos.

### D3. Coincidencia verificada por título y gen
Un registro coincide si `notación` aparece en `title` (comparación sin distinguir mayúsculas,
aceptando la notación con o sin el prefijo `p.`/`c.` que trae el título entre paréntesis) y el gen
consultado está en `genes[].symbol`. Resultado:
- 0 ids → `sin_resultados`; 1+ coincidencias con la misma clasificación → `encontrada` (la de
  revisión más reciente); coincidencias con clasificaciones distintas o 0 coincidencias entre
  1+ ids → `ambigua` con la cantidad de candidatos.
- *Alternativa descartada — tomar el primer id de `esearch`.* Con `Val30Met` devolvería
  `p.Phe53Leu` en algunas búsquedas: una clasificación de otra variante presentada como propia.

### D4. Emparejamiento variante → gen, determinista
Para cada variante: (1) si alguna frase de `genetic_findings` contiene la variante y un gen de
`ctx.genes`, se usa ese gen; (2) si `ctx.genes` tiene un único gen, se usa ese; (3) si no, la
variante queda sin consultar con el detalle "gen no identificable". Nunca se le pide el gen al LLM.

### D5. Modelo y fuentes acumulativas
`VariantClassification` en `models/genomics.py` (`gene`, `variant`, `status`, `classification`,
`review_status`, `last_evaluated`, `accession`, `url`, `title`, `candidates`) y
`GenomicContext.clinvar: list[VariantClassification]`. `enrich()` consulta PharmGKB y ClinVar en
paralelo (`asyncio.gather`) y arma `sources` con ambas fuentes. El estado agregado de la fuente
ClinVar: `consultada` si alguna variante quedó `encontrada`; `no_disponible` si todas fallaron;
`sin_resultados` en el resto; `no_consultada` sin variantes consultables.

### D6. Máximo 5 variantes por análisis
Cada variante cuesta 2 solicitudes (`esearch` + `esummary`); 5 variantes = 10 solicitudes, unos
3,5 s a 3 req/s compartidos con la verificación de PMIDs. Las sobrantes se informan en el detalle.

## Risks / Trade-offs

- **Notación clásica ambigua** (Val30Met y similares, muy frecuentes en informes de laboratorio
  viejos): queda `ambigua`. Aceptado: es preferible a una clasificación equivocada. Se documenta
  como limitación en la tesis.
- **Contienda por el cupo de NCBI** con la verificación de PMIDs: ClinVar corre en la Ronda 1
  (`enrich()`), la verificación después del debate; no se pisan en el tiempo.
- **Cambios en el formato de `esummary`** (ClinVar migró `clinical_significance` →
  `germline_classification`): si falta el campo, la respuesta se trata como malformada →
  `no_disponible`, nunca como "sin clasificación".
