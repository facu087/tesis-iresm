## Why

El Agente 02 (Especialista Genómica) recibe las variantes del caso tal como las escribió el
médico, pero no tiene forma de saber qué dice ClinVar de ellas: la significancia clínica
("patogénica", "VUS", "benigna") queda librada a lo que el LLM recuerde. La tarjeta #71 se
separó de la #51 justamente para cubrir esto, y es la última API externa del Sprint 4 sin cliente.

## What Changes

- Cliente nuevo `backend/external/clinvar.py` sobre NCBI E-utilities (`db=clinvar`,
  `esearch` + `esummary`): dada una variante y su gen, devuelve la clasificación germinal,
  el estado de revisión, la fecha de última evaluación y el accession `VCV` verificable.
- **Coincidencia verificada**: el cliente solo acepta un registro cuyo título contiene la
  notación consultada. Medido el 2026-10-06: `TTR[gene] AND Val30Met` (numeración clásica)
  devuelve 5 registros y uno es otra variante (`p.Phe53Leu`); `c.148G>A` y `p.Val50Met`
  devuelven el registro exacto (`VCV000013417`, Pathogenic). Ante varios candidatos sin
  coincidencia exacta el resultado es `ambigua`, nunca el primero de la lista.
- Resultado con estado explícito por variante: `encontrada`, `sin_resultados`, `ambigua`,
  `no_disponible`. Un error de la API nunca se confunde con "sin resultados".
- ClinVar comparte el limitador de NCBI con PubMed (`pubmed_limiter` en
  `external/rate_limiter.py`): son el mismo servicio y el mismo cupo de 3 req/s sin key.
- `pipeline/genomic_context.enrich()` consulta ClinVar cuando el caso trae variantes, agrega
  las clasificaciones a `GenomicContext` y una fuente `ClinVar` a `sources`; el bloque del
  prompt del Agente 02 las muestra. Sin variantes, ClinVar queda `no_consultada`.
- `scripts/demo_clinvar.py` con consulta real (evidencia para Trello) y tests con la API mockeada.

## Capabilities

### New Capabilities
- `clinvar-variantes`: consulta de la significancia clínica de las variantes del caso en
  ClinVar, con coincidencia verificada, estados explícitos y su incorporación al contexto
  genómico del Agente 02.

### Modified Capabilities
<!-- Ninguna: el contexto genómico del Agente 02 no tiene spec vigente en openspec/specs/
     (el cambio agente-02-genomica no se archivó). Su uso de ClinVar se especifica dentro
     de la capacidad nueva. -->

## Impact

- **Código nuevo**: `backend/external/clinvar.py`, `tests/test_clinvar.py`,
  `scripts/demo_clinvar.py`.
- **Código modificado**: `backend/models/genomics.py` (modelo de clasificación y campo en
  `GenomicContext`, bloque del prompt), `backend/pipeline/genomic_context.py` (`enrich()`).
- **Privacidad**: a NCBI solo viajan el símbolo del gen y la notación de la variante; nunca
  texto clínico, edad ni sexo.
- **Cuota**: ninguna llamada al LLM nueva. Las consultas a NCBI suman al cupo que ya usa la
  verificación de PMIDs; el caso base no trae variantes, así que no agrega ninguna.
- **Fuera de alcance**: convertir numeración clásica a HGVS (p. ej. TTR Val30Met → p.Val50Met,
  desfase de 20 por el péptido señal); se documenta como limitación.
