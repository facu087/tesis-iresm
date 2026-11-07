# Revisión del reporte con un médico o el tutor (tarjeta #60)

## Para qué

Los criterios de calidad automáticos (tarjeta #59, `backend/pipeline/calidad.py`) miden lo que se puede comprobar sin un clínico: si los PMIDs citados existen, si corresponden al artículo que se dice citar y si el nivel de evidencia tiene respaldo. La corrida de verificación del 2026-11-03 (tarjeta #92) los cumple: cobertura 0,91, precisión 1,00 y sobredeclaración 0,45.

Hay tres cosas que esos criterios no pueden responder:

1. Si cada hipótesis es pertinente para este paciente.
2. Si el artículo citado respalda lo que afirma la hipótesis. La verificación confirma que el PMID es ese artículo, no que lo respalde: en esa corrida, 8 artículos sostienen 15 citas y uno se cita 4 veces.
3. Si al reporte le falta una hipótesis que un clínico consideraría obvia.

La sesión responde esas tres preguntas con el juicio de un médico.

## Qué no es

- **No es una evaluación de diagnóstico.** NEXUS no emite diagnósticos: genera hipótesis de investigación para el médico responsable. Lo que se evalúa es si esas propuestas son útiles y están bien fundamentadas, no si aciertan un diagnóstico.
- **No es un estudio clínico.** Es la opinión de una o dos personas sobre un caso. Sirve para detectar problemas, no para afirmar eficacia.

## Participantes y caso

- **Revisor:** un médico (idealmente neurólogo o clínico) o el tutor de la tesis.
- **Conductor:** un integrante del equipo. Explica la consigna, toma el tiempo y no defiende el reporte durante la sesión.
- **Caso:** el caso base de la tesis, una neuropatía axonal sensitivomotora en un varón de 42 años. Es un caso de prueba anonimizado; no hay datos de un paciente real.

## Material

Se genera desde el reporte de una corrida real (el script rechaza los reportes de modo mock):

```bash
python3 scripts/revision_medica.py preparar output/medicion_costos/citas_ancladas_20261103/reporte.json \
    --salida output/revision_medica/corrida_20261103
```

En la carpeta de salida quedan:

| Archivo | Para qué |
|---------|----------|
| `reporte.pdf` | El reporte tal como lo exporta NEXUS. Se le entrega al revisor. |
| `planilla.pdf` | La planilla impresa: un bloque por hipótesis y las preguntas generales. |
| `planilla.csv` | La misma planilla, para cargar las respuestas después de la sesión. |
| `generales.csv` | Las preguntas generales, para cargar sus respuestas. |

`preparar` no pisa una `planilla.csv` que ya existe, porque puede tener respuestas cargadas.

## Desarrollo (45 a 60 minutos)

1. **Consigna (5 min).** El conductor lee la sección "Qué no es" y explica las preguntas de la planilla. Aclara que el reporte se produjo con un modelo de IA, que puede equivocarse, y que lo que se busca son justamente esos errores.
2. **Lectura del reporte (10 a 15 min).** El revisor lee el `reporte.pdf` sin explicaciones del equipo. Si algo no se entiende, se anota: eso responde la pregunta de claridad.
3. **Planilla (25 a 30 min).** El revisor completa `planilla.pdf`, una hipótesis por vez. Para la pregunta de las citas, puede abrir el artículo en PubMed: el PMID figura en la planilla.
4. **Preguntas generales y cierre (5 a 10 min).** Si falta alguna hipótesis obvia, cuál. Comentarios libres.

## Preguntas de la planilla

Por cada hipótesis:

| Pregunta | Opciones (lo que se carga en el CSV) |
|----------|--------------------------------------|
| ¿La hipótesis es pertinente para este caso? | `si`, `parcial`, `no` |
| ¿El artículo citado respalda la hipótesis? | `si`, `parcial`, `no`, `sin_cita` (solo si la hipótesis no cita nada) |
| ¿El nivel de evidencia asignado es razonable? | `si`, `sobreestimado`, `subestimado` |
| ¿Investigaría esta hipótesis en este paciente? | `si`, `no` |
| Estudio que pediría | texto libre |
| Observaciones | texto libre |

Generales: si falta alguna hipótesis obvia (`si`/`no`), si le serviría un reporte así como apoyo (`si`/`quizas`/`no`), si se entiende sin explicación previa (`si`/`parcial`/`no`) y comentarios libres.

## Después de la sesión

1. Cargar las respuestas en `planilla.csv` y `generales.csv`, con la planilla en papel al lado. Se pueden abrir con LibreOffice o Excel; el CSV se lee igual con `,` o con `;`. Las tildes y las mayúsculas no importan: "Sí" y "si" valen lo mismo, y "sin cita" vale lo mismo que `sin_cita`.
2. Tabular:

   ```bash
   python3 scripts/revision_medica.py tabular output/revision_medica/corrida_20261103
   ```

   Sale con código 0 si la planilla está completa y con 1 si falta una respuesta o hay una que no es una de las opciones; en ese caso, lista cuál. Guarda `resumen.json` y `resumen.txt` en la misma carpeta.
3. El resumen informa:
   - la pertinencia;
   - la proporción de citas que respaldan la hipótesis, sin contar las hipótesis sin cita;
   - la proporción de niveles razonables y de hipótesis que el revisor investigaría;
   - las hipótesis con **respaldo verificado sin respaldo clínico**: las que la verificación automática dio por respaldadas pero cuya cita, para el médico, no respalda la hipótesis. Es el número que mide la salvedad principal de la #92.
4. El resumen no copia texto clínico ni los comentarios del revisor: solo posiciones de hipótesis y conteos. Los comentarios quedan en el CSV, que es local (`output/` está ignorada por git).

## Evidencia para Trello

En la tarjeta #60 se adjuntan:

- el `resumen.txt`;
- una foto o escaneo de la planilla firmada, si el revisor está de acuerdo;
- una nota con el nombre y el rol del revisor, si autoriza que figure.

Los hallazgos que impliquen cambios en el sistema se cargan como tarjetas nuevas.
