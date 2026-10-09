import {
  BookOpenTextIcon,
  CompassIcon,
  DnaIcon,
  FileTextIcon,
  ScalesIcon,
  StethoscopeIcon,
} from "@phosphor-icons/react/ssr";
import ScrollReveal from "@/components/ScrollReveal";
import SectionHeading from "@/components/landing/SectionHeading";
import { CARD, CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * The six agents, all implemented and running.
 *
 * Descriptions checked against the code: `backend/agents/agent_0{1..6}_*.py`,
 * `.claude/architecture.md` and `.claude/CLAUDE.md`. Agent 06 writes the
 * executive summary in prose after the structured report is built; it does
 * not replace the deterministic builder (`pipeline/report_builder.py`).
 */
const AGENTS = [
  {
    id: "01",
    name: "Analista de Literatura",
    Icon: BookOpenTextIcon,
    description:
      "Genera hipótesis a partir de literatura médica publicada, con búsqueda semántica sobre PubMed (RAG) como contexto.",
  },
  {
    id: "02",
    name: "Especialista Genómica",
    Icon: DnaIcon,
    description:
      "Analiza el caso desde la genética y la biología molecular, con contexto farmacogenómico de PharmGKB. Una guarda antiinvención degrada cualquier hipótesis que cite un hallazgo genético que no está en el caso.",
  },
  {
    id: "03",
    name: "Consultor Clínico",
    Icon: StethoscopeIcon,
    description:
      "Razona desde la práctica clínica: diagnóstico diferencial, causas tratables a descartar primero y guías de sociedades médicas.",
  },
  {
    id: "04",
    name: "Árbitro Verificador",
    Icon: ScalesIcon,
    description:
      "Verifica cada referencia citada contra PubMed, agrupa las hipótesis equivalentes en un consenso y documenta las objeciones sin resolver. Pide una recitación (Ronda 5) a las hipótesis sin respaldo.",
  },
  {
    id: "05",
    name: "Navegador de Ensayos",
    Icon: CompassIcon,
    description:
      "Busca ensayos clínicos activos en ClinicalTrials.gov y enfermedades raras compatibles en Orphanet, con una compatibilidad orientativa que nunca excluye resultados.",
  },
  {
    id: "06",
    name: "Sintetizador",
    Icon: FileTextIcon,
    description:
      "Redacta el resumen ejecutivo en prosa una vez armado el reporte estructurado. Una guarda antiinvención descarta el resumen si cita un PMID, un ensayo o un gen que no figura en el reporte. No reemplaza al módulo determinista que arma el reporte.",
  },
] as const;

export default function AgentsSection() {
  return (
    <section
      id="agentes"
      aria-labelledby="agentes-heading"
      className={`bg-bg-subtle ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <SectionHeading
            id="agentes-heading"
            eyebrow="Agentes"
            title="Seis agentes especializados, un solo consenso"
          />
        </ScrollReveal>

        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {AGENTS.map((agent, index) => (
            <li key={agent.id} className="flex">
              <ScrollReveal delay={(index % 3) * 120} className="flex w-full">
                <article className={`${CARD} w-full`}>
                  <div className="flex items-center justify-between gap-4">
                    <agent.Icon aria-hidden="true" className="size-8 text-accent" />
                    <span className="font-mono text-sm font-semibold text-fg-muted">
                      <span className="sr-only">Agente </span>
                      {agent.id}
                    </span>
                  </div>
                  <h3 className="mt-4 text-xl font-semibold text-fg">{agent.name}</h3>
                  <p className="mt-2 text-base text-pretty text-fg-muted">
                    {agent.description}
                  </p>
                </article>
              </ScrollReveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
