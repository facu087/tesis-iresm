"""
Clase base para todos los agentes de análisis de NEXUS.

Cada agente especializado hereda de BaseAgent y solo necesita definir:
  - AGENT_ID      → identificador único (ej: "01")
  - AGENT_NAME    → nombre legible (ej: "Analista de Literatura")
  - MODEL         → modelo de LLM a usar
  - SYSTEM_PROMPT → prompt de sistema especializado

La lógica común (llamada al LLM, parseo de JSON, validación de hipótesis)
está implementada aquí y es heredada por todos los agentes.
"""

import json
import os
import re
import sys
import time
from abc import ABC, abstractmethod

from ..mock.mode import ENV_VAR, is_mock_active
from ..mock.responses import get_mock_response
from ..models.hypothesis import EvidenceLevel, Hypothesis, Priority, Source
from ..models.report import AgentOutput, Critique
from ..telemetry import usage as usage_telemetry
from . import model_tasks
# GROQ_MAIN/GROQ_FAST viven en model_tasks.py junto con el mapa tarea → (modelo,
# techo) que las usa; se re-exportan acá porque `agents/__init__.py` y varios
# agentes ya las importan desde `base_agent`.
from .model_tasks import GROQ_FAST, GROQ_MAIN


def call_provider(
    *,
    system_prompt: str,
    user_message: str,
    model: str,
    max_tokens: int,
    task: str,
    agent_id: str | None = None,
    agent_name: str | None = None,
    temperature: float = 0.3,
) -> str:
    """
    Punto único de llamada al proveedor del modelo de lenguaje (control de
    costos, Sprint 4 — D1).

    Antes de este cambio, tres lugares instanciaban el cliente de Groq por su
    cuenta: `BaseAgent._call_llm()`, `pipeline/pico.py` y
    `ingestion/biomarker_extractor.py`. Cada uno repetía su propio reintento y
    su propio manejo de errores, y el swap de proveedor había que hacerlo tres
    veces. Ahora los tres delegan acá: es el único lugar del sistema que
    instancia el cliente del proveedor, así que es también el único lugar que
    hay que tocar para contar el consumo de una llamada o para cambiar de
    proveedor.

    Args:
        system_prompt: Prompt de sistema del agente o del módulo que llama.
        user_message:  Mensaje de usuario ya armado para esta tarea.
        model:         Modelo del proveedor a usar (p. ej. GROQ_MAIN o
                       GROQ_FAST).
        max_tokens:    Techo de tokens de la respuesta, propio de la tarea que
                       llama: no hay un valor único para todo el sistema.
        task:          Etiqueta de la tarea que originó la llamada (p. ej.
                       "agente01_hipotesis", "pico_sintesis"). Identifica el
                       paso de origen para quien lea los logs.
        agent_id:      ID del agente que llama, si corresponde. `None` para
                       llamadas que no vienen de un agente (PICO,
                       biomarcadores).
        agent_name:    Nombre legible del agente que llama, si corresponde.
        temperature:   Temperatura de muestreo del modelo.

    Returns:
        Texto crudo de la respuesta del modelo.

    Reintenta hasta 3 veces con backoff incremental ante errores 429 (rate
    limit del tier gratuito de Groq). Agota los reintentos y relanza la
    última excepción si el proveedor sigue devolviendo 429.

    Cada intento —falle o no— queda contabilizado en el registro de
    telemetría activo (control de costos, Sprint 4 — D2), para que el costo
    de los reintentos también sea visible. Sin un registro abierto (un script
    de demo, un test) esto no hace nada: la telemetría nunca es condición
    para que una llamada funcione.

    En modo mock (S4 — D7, variable `NEXUS_MOCK_LLM`), devuelve una respuesta
    grabada para `task` sin tocar la red ni instanciar el proveedor. Es la
    intercepción, no un endpoint alternativo: la respuesta grabada atraviesa
    después el mismo parseo que una real, porque quien llamó a `_call_llm()`
    no se entera de la diferencia.

    Sin modo mock, `GROQ_API_KEY` faltante falla con un mensaje claro antes de
    intentar nada: un fallo de configuración tiene que fallar, no caer en
    silencio a una respuesta grabada.
    """
    if is_mock_active():
        inicio = time.perf_counter()
        contenido = get_mock_response(task)
        usage_telemetry.record_call(
            task=task, model=model, agent_id=agent_id, agent_name=agent_name,
            ok=True, latency_seconds=time.perf_counter() - inicio,
            prompt_tokens=0, completion_tokens=0, mock=True,
        )
        return contenido

    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY no está configurada y el modo mock está desactivado. "
            "Configurá GROQ_API_KEY en el .env, o activá el modo mock "
            f"({ENV_VAR}=1) para desarrollo sin cuota."
        )

    from groq import Groq, RateLimitError

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    delays = [8, 20, 40]  # segundos de espera entre reintentos
    last_exc: Exception | None = None

    for attempt, delay in enumerate(delays + [None], start=1):
        inicio = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except RateLimitError as exc:
            usage_telemetry.record_call(
                task=task, model=model, agent_id=agent_id, agent_name=agent_name,
                ok=False, latency_seconds=time.perf_counter() - inicio,
            )
            last_exc = exc
            if delay is None:
                break
            print(
                f"[NEXUS] {task}: rate limit (intento {attempt}/3). "
                f"Reintentando en {delay}s…",
                file=sys.stderr,
            )
            time.sleep(delay)
            continue
        except Exception:
            # Cualquier otra falla (auth, red, error del proveedor) también
            # queda contabilizada, aunque acá no se reintenta: solo el 429
            # tiene backoff propio.
            usage_telemetry.record_call(
                task=task, model=model, agent_id=agent_id, agent_name=agent_name,
                ok=False, latency_seconds=time.perf_counter() - inicio,
            )
            raise

        latencia = time.perf_counter() - inicio
        choice = response.choices[0]
        consumo = getattr(response, "usage", None)
        usage_telemetry.record_call(
            task=task, model=model, agent_id=agent_id, agent_name=agent_name,
            ok=True, latency_seconds=latencia,
            prompt_tokens=getattr(consumo, "prompt_tokens", None) if consumo else None,
            completion_tokens=getattr(consumo, "completion_tokens", None) if consumo else None,
            truncated=getattr(choice, "finish_reason", None) == "length",
        )
        return choice.message.content

    raise last_exc  # type: ignore[misc]


class BaseAgent(ABC):
    """
    Interfaz común para todos los agentes de análisis clínico.

    Subclases deben definir los atributos de clase:
        AGENT_ID, AGENT_NAME, MODEL, SYSTEM_PROMPT
    """

    AGENT_ID: str = ""
    AGENT_NAME: str = ""
    MODEL: str = GROQ_MAIN
    SYSTEM_PROMPT: str = ""

    # ── Utilidades de parseo ──────────────────────────────────────

    @staticmethod
    def extract_json(raw: str) -> dict:
        """
        Extrae el primer bloque JSON válido de un string.
        Maneja respuestas con texto libre, markdown fences y JSON puro.
        """
        # 1. Parsear directamente
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 2. Remover fences de markdown (```json ... ``` o ``` ... ```)
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
            stripped = re.sub(r'\s*```\s*$', '', stripped.strip())
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # 3. Buscar el bloque { ... } más grande
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"La respuesta del modelo no contiene JSON válido.\n"
            f"Primeros 500 chars: {raw[:500]}"
        )

    @staticmethod
    def _build_source(declared: object) -> Source | None:
        """
        Construye una Source con los campos que al agente le corresponde declarar.

        El estado de verificación, el título real y los tipos de publicación son
        **salida** de la verificación bibliográfica contra PubMed
        (`pipeline/verification.py`), nunca entrada del modelo: un LLM que escribe
        `verified: true` en su JSON no verificó nada. Antes se hacía `Source(**s)`
        y esos campos autodeclarados viajaban en el Report interno hasta que
        `evidence.py` y `report_builder._annotate_source()` los ignoraban aguas
        abajo. Acá se descartan en el origen.

        Tampoco falla ante un campo con el tipo equivocado: el PMID escrito como
        número se convierte a texto, y un año, una revista o una URL inválidos
        quedan vacíos. Devuelve `None` cuando la fuente no trae un título
        utilizable, que es lo único sin lo cual no se puede contrastar contra
        PubMed. En la corrida real del 2026-10-04 una sola fuente con
        `title: null` levantó un error de validación y dejó al Agente 03 fuera
        de la Ronda 1 completa: una cita inservible no puede costar un agente.
        """
        if not isinstance(declared, dict):
            return None

        title = declared.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        return Source(
            pmid=BaseAgent._as_pmid(declared.get("pmid")),
            title=title,
            journal=BaseAgent._as_text(declared.get("journal")),
            year=BaseAgent._as_year(declared.get("year")),
            url=BaseAgent._as_text(declared.get("url")),
        )

    @staticmethod
    def _as_text(value: object) -> str | None:
        """Devuelve el valor si es texto no vacío; cualquier otra cosa es `None`."""
        return value if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _as_pmid(value: object) -> str | None:
        """Acepta el PMID como texto o como entero, que es como suele escribirlo el modelo."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return str(value)
        return BaseAgent._as_text(value)

    @staticmethod
    def _as_year(value: object) -> int | None:
        """Acepta el año como entero o como texto numérico; cualquier otra cosa es `None`."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    @staticmethod
    def _as_priority(value: object) -> Priority | None:
        """Prioridad declarada, sin distinguir mayúsculas; `None` si no es una de las tres."""
        if not isinstance(value, str):
            return None
        try:
            return Priority(value.strip().upper())
        except ValueError:
            return None

    @staticmethod
    def _as_evidence_level(value: object) -> EvidenceLevel | None:
        """
        Nivel de evidencia declarado. Acepta el número romano sin distinguir
        mayúsculas y también 1, 2 o 3, que es como a veces lo escribe el modelo.
        """
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            value = str(value)
        if not isinstance(value, str):
            return None
        normalized = value.strip().upper()
        normalized = {"1": "I", "2": "II", "3": "III"}.get(normalized, normalized)
        try:
            return EvidenceLevel(normalized)
        except ValueError:
            return None

    @staticmethod
    def parse_hypotheses(raw: str) -> list[Hypothesis]:
        """
        Parsea y valida la lista de hipótesis del JSON de respuesta.
        Espera un objeto con clave "hypotheses": [...].

        Un campo malformado no invalida la respuesta completa: antes, una sola
        hipótesis con una prioridad desconocida dejaba al agente fuera de la
        ronda. Solo se descarta la hipótesis que no trae enunciado, porque no
        hay nada que mostrar. Para el resto se aplica el valor más conservador:
        prioridad `LOW`, nivel de evidencia `III` (la regla del proyecto ante
        una hipótesis sin respaldo defendible) y fundamento vacío. Las fuentes
        se sanean en `_build_source()`.

        Levanta `ValueError` si no queda ninguna hipótesis utilizable.
        """
        data = BaseAgent.extract_json(raw)
        declared = data.get("hypotheses", [])
        if not isinstance(declared, list):
            declared = []

        hypotheses: list[Hypothesis] = []
        discarded = 0
        priority_defaults = 0
        level_defaults = 0
        discarded_sources = 0

        for h in declared:
            if not isinstance(h, dict):
                discarded += 1
                continue

            text = h.get("text")
            if not isinstance(text, str) or not text.strip():
                discarded += 1
                continue

            priority = BaseAgent._as_priority(h.get("priority"))
            if priority is None:
                priority = Priority.LOW
                priority_defaults += 1

            evidence_level = BaseAgent._as_evidence_level(h.get("evidence_level"))
            if evidence_level is None:
                evidence_level = EvidenceLevel.III
                level_defaults += 1

            declared_sources = h.get("sources", [])
            if not isinstance(declared_sources, list):
                declared_sources = []
            built = [BaseAgent._build_source(s) for s in declared_sources]
            sources = [s for s in built if s is not None]
            discarded_sources += len(built) - len(sources)

            hypotheses.append(Hypothesis(
                text=text,
                priority=priority,
                evidence_level=evidence_level,
                rationale=BaseAgent._as_text(h.get("rationale")) or "",
                sources=sources,
            ))

        if not hypotheses:
            raise ValueError("El modelo no devolvió ninguna hipótesis.")

        # Solo cantidades: el contenido de una hipótesis o de una cita no se registra.
        adjustments = [
            (discarded, "hipótesis descartada(s) por no traer enunciado"),
            (priority_defaults, "prioridad(es) inválida(s) llevada(s) a LOW"),
            (level_defaults, "nivel(es) de evidencia inválido(s) llevado(s) a III"),
            (discarded_sources, "fuente(s) descartada(s) por no traer un título utilizable"),
        ]
        notes = [f"{count} {label}" for count, label in adjustments if count]
        if notes:
            print(f"[NEXUS] Respuesta del modelo saneada: {'; '.join(notes)}.", file=sys.stderr)

        return hypotheses

    # ── Llamada al LLM ────────────────────────────────────────────

    def _call_llm(self, user_message: str, *, task: str) -> str:
        """
        Llama al proveedor vía `call_provider()`, con el modelo y el techo de
        tokens de `task` (control de costos, S4 — D6). Devuelve el texto
        crudo de la respuesta.

        `task` reemplaza a `self.MODEL` para decidir el modelo real de la
        llamada: `self.MODEL` sigue siendo un atributo obligatorio de cada
        agente (documentación de qué modelo usa "por defecto"), pero la
        política vigente vive en `model_tasks.TASK_BUDGETS`, consultable sin
        recorrer los agentes.
        """
        budget = model_tasks.get_budget(task)
        return call_provider(
            system_prompt=self.SYSTEM_PROMPT,
            user_message=user_message,
            model=budget.model,
            max_tokens=budget.max_tokens,
            task=task,
            agent_id=self.AGENT_ID,
            agent_name=self.AGENT_NAME,
        )

    # ── Interfaz pública ──────────────────────────────────────────

    @abstractmethod
    def run(self, clinical_context: str) -> AgentOutput:
        """
        Ejecuta el agente sobre el contexto clínico dado.

        Args:
            clinical_context: texto clínico estructurado (salida de format_for_agents)

        Returns:
            AgentOutput con las hipótesis generadas por este agente
        """

    def _build_output(self, hypotheses: list[Hypothesis], raw: str) -> AgentOutput:
        """Construye el AgentOutput estándar."""
        return AgentOutput(
            agent_id=self.AGENT_ID,
            agent_name=self.AGENT_NAME,
            hypotheses=hypotheses,
            raw_response=raw,
        )

    # ── Debate adversarial ────────────────────────────────────────

    def critique(
        self,
        context: str,
        own_output: AgentOutput,
        other_outputs: list[AgentOutput],
    ) -> list[Critique]:
        """
        Ronda 2: genera críticas sobre las hipótesis de los otros agentes.
        Devuelve una lista de Critique con severidad y alternativa opcional.
        """
        own_text = _format_output(own_output, label="TUS HIPÓTESIS (Ronda 1)")
        others_text = _format_outputs(other_outputs, label="HIPÓTESIS DE OTROS AGENTES")

        prompt = (
            f"Sos {self.AGENT_NAME}. Participás en un debate adversarial de análisis clínico.\n\n"
            f"CONTEXTO CLÍNICO:\n{context}\n\n"
            f"{own_text}\n\n"
            f"{others_text}\n\n"
            "Analizá críticamente las hipótesis de los otros agentes desde tu perspectiva.\n"
            "Identificá inconsistencias, sobre-estimaciones o falta de evidencia.\n\n"
            "Respondé ÚNICAMENTE con JSON válido:\n"
            '{\n  "critiques": [\n    {\n'
            '      "target_agent_id": "ID del agente",\n'
            '      "target_hypothesis": "texto exacto de la hipótesis criticada",\n'
            '      "critique_text": "crítica específica y fundamentada",\n'
            '      "severity": "HIGH" | "MEDIUM" | "LOW",\n'
            '      "alternative": "alternativa sugerida o null"\n'
            "    }\n  ]\n}"
        )
        raw = self._call_llm(prompt, task="debate_critica")
        return self._parse_critiques(raw)

    def revise(
        self,
        context: str,
        own_output: AgentOutput,
        critiques_received: list[Critique],
    ) -> AgentOutput:
        """
        Rondas 3-4: revisa o defiende hipótesis propias en respuesta a críticas.
        Devuelve un AgentOutput con hipótesis ajustadas o defendidas.
        """
        own_text = _format_output(own_output, label="TUS HIPÓTESIS PREVIAS")
        critiques_text = _format_critiques(critiques_received)

        prompt = (
            f"Sos {self.AGENT_NAME}. Participás en un debate adversarial de análisis clínico.\n\n"
            f"CONTEXTO CLÍNICO:\n{context}\n\n"
            f"{own_text}\n\n"
            f"{critiques_text}\n\n"
            "Respondé a cada crítica recibida: ajustá tu hipótesis si la crítica es válida,\n"
            "o defendela con argumentación adicional. Podés agregar hipótesis nuevas si\n"
            "el debate reveló perspectivas no consideradas.\n\n"
            "Respondé ÚNICAMENTE con JSON en el formato estándar de hipótesis:\n"
            '{\n  "hypotheses": [...]\n}'
        )
        raw = self._call_llm(prompt, task="debate_revision")
        hypotheses = self.parse_hypotheses(raw)
        return self._build_output(hypotheses, raw)

    # ── Ronda 5: recitación ───────────────────────────────────────

    def recite(
        self,
        hypotheses_with_reasons: list[tuple[str, list[str]]],
        articles: list[str],
    ) -> dict[int, list[Source]]:
        """
        Ronda 5: vuelve a citar las hipótesis propias que quedaron sin respaldo.

        La verificación bibliográfica mostró que los agentes inventan PMIDs en
        lugar de usar la literatura que el RAG les recupera. Acá se les devuelve
        el motivo concreto por el que falló cada cita —no es lo mismo haber
        inventado un número que haber citado un artículo real con el título
        equivocado— junto con los artículos reales, y se les pide citar sobre
        esos.

        Args:
            hypotheses_with_reasons: (texto de la hipótesis, motivos de fallo),
                                     en el orden en que se numeran en el prompt.
            articles:                Bloques ya formateados de los artículos que
                                     el RAG recuperó, con su PMID real.

        Returns:
            Dict {índice de hipótesis (0-based) → fuentes propuestas}. El índice
            sale del número que devolvió el modelo; los fuera de rango se
            descartan. Quien valida que los PMID pertenezcan al conjunto
            ofrecido es `pipeline/recitation.validate_recited()`.
        """
        prompt = self._build_recitation_prompt(hypotheses_with_reasons, articles)
        raw = self._call_llm(prompt, task="debate_recitacion")
        return self._parse_recitation(raw, total=len(hypotheses_with_reasons))

    def _build_recitation_prompt(
        self,
        hypotheses_with_reasons: list[tuple[str, list[str]]],
        articles: list[str],
    ) -> str:
        """Arma el pedido de recitación. Sobreescribible para sumar contexto."""
        lineas = [
            f"Sos {self.AGENT_NAME}. Las referencias que citaste para estas hipótesis "
            "no resistieron la verificación contra PubMed.",
            "",
        ]
        for numero, (texto, motivos) in enumerate(hypotheses_with_reasons, 1):
            lineas.append(f"{numero}. {texto}")
            for motivo in motivos:
                lineas.append(f"   - {motivo}")

        lineas += [
            "",
            "Estos son los artículos REALES recuperados de PubMed para este caso:",
            "",
        ]
        lineas.extend(articles)

        lineas += [
            "",
            "Volvé a citar cada hipótesis usando ÚNICAMENTE los PMIDs de la lista de "
            "arriba, con el título exacto tal como figura. Si para una hipótesis no "
            "hay ningún artículo pertinente en esa lista, no la incluyas en tu "
            "respuesta: es preferible que quede sin respaldo a que cites algo que no "
            "corresponde. NO inventes PMIDs ni cites artículos que no estén listados.",
            "",
            "Respondé ÚNICAMENTE con JSON válido:",
            '{"recitations": [{"hypothesis": 1, "sources": '
            '[{"pmid": "12345678", "title": "Título exacto del artículo"}]}]}',
        ]
        return "\n".join(lineas)

    def _parse_recitation(self, raw: str, total: int) -> dict[int, list[Source]]:
        """Parsea la respuesta de recitación, descartando índices fuera de rango."""
        data = self.extract_json(raw)
        recitaciones: dict[int, list[Source]] = {}

        for item in data.get("recitations", []):
            if not isinstance(item, dict):
                continue
            numero = item.get("hypothesis")
            if isinstance(numero, bool) or not isinstance(numero, int):
                continue
            if not 1 <= numero <= total:
                continue
            fuentes = [
                BaseAgent._build_source(s)
                for s in item.get("sources", [])
                if isinstance(s, dict) and s.get("title")
            ]
            if fuentes:
                recitaciones[numero - 1] = fuentes

        return recitaciones

    def _parse_critiques(self, raw: str) -> list[Critique]:
        """Parsea el JSON de críticas devuelto por el modelo."""
        data = self.extract_json(raw)
        critiques = []
        for c in data.get("critiques", []):
            severity = c.get("severity", "MEDIUM").upper()
            if severity not in ("HIGH", "MEDIUM", "LOW"):
                severity = "MEDIUM"
            critiques.append(Critique(
                from_agent_id=self.AGENT_ID,
                from_agent_name=self.AGENT_NAME,
                target_agent_id=str(c.get("target_agent_id", "")),
                target_hypothesis=c.get("target_hypothesis", ""),
                critique_text=c.get("critique_text", ""),
                severity=severity,
                alternative=c.get("alternative") or None,
            ))
        return critiques


# ── Helpers de formateo para el debate ────────────────────────────────────────

def _format_output(output: AgentOutput, label: str) -> str:
    lines = [f"=== {label} ({output.agent_name}) ==="]
    for i, h in enumerate(output.hypotheses, 1):
        lines.append(f"#{i} [{h.priority.value}] Evidencia {h.evidence_level.value}: {h.text}")
        lines.append(f"   Fundamento: {h.rationale[:300]}")
    return "\n".join(lines)


def _format_outputs(outputs: list[AgentOutput], label: str) -> str:
    lines = [f"=== {label} ==="]
    for output in outputs:
        lines.append(f"\n--- {output.agent_name} (Agente {output.agent_id}) ---")
        for i, h in enumerate(output.hypotheses, 1):
            lines.append(f"#{i} [{h.priority.value}] Evidencia {h.evidence_level.value}: {h.text}")
            lines.append(f"   Fundamento: {h.rationale[:300]}")
    return "\n".join(lines)


def _format_critiques(critiques: list[Critique]) -> str:
    if not critiques:
        return "=== CRÍTICAS RECIBIDAS ===\nNinguna crítica recibida."
    lines = ["=== CRÍTICAS RECIBIDAS ==="]
    for c in critiques:
        lines.append(f"\n- De: {c.from_agent_name} [{c.severity}]")
        lines.append(f"  Hipótesis criticada: {c.target_hypothesis[:150]}")
        lines.append(f"  Crítica: {c.critique_text}")
        if c.alternative:
            lines.append(f"  Alternativa sugerida: {c.alternative}")
    return "\n".join(lines)
