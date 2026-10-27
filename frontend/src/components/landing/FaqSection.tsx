import { CaretDownIcon } from "@phosphor-icons/react/ssr";
import ScrollReveal from "@/components/ScrollReveal";
import SectionHeading from "@/components/landing/SectionHeading";
import { CONTAINER, FOCUS_RING, SECTION_PADDING, TRANSITION } from "@/components/landing/styles";

/**
 * Frequently asked questions as an accordion, every item closed by default.
 *
 * Native `<details>`/`<summary>`: operable with the keyboard and without
 * JavaScript, and the answers stay in the document for search engines.
 *
 * Every answer is verifiable in this repository; the source is noted beside
 * each entry. The same list feeds the FAQ structured data emitted by the
 * page, so the visible text and the JSON-LD cannot diverge.
 */
export interface FaqItem {
  question: string;
  answer: string;
}

export const FAQ_ITEMS: readonly FaqItem[] = [
  {
    // Scope notice of the product (`.claude/CLAUDE.md`).
    question: "¿NEXUS emite diagnósticos?",
    answer:
      "No. Genera hipótesis de investigación para que las evalúe el médico responsable.",
  },
  {
    // `backend/api/router.py` (protected endpoints), `app/cuenta/page.tsx`.
    question: "¿Quién puede usar NEXUS?",
    answer:
      "Médicos registrados con su matrícula. Un administrador revisa cada solicitud.",
  },
  {
    // `backend/pipeline/verification.py`, `recitation.py`, `evidence.py`.
    question: "¿Qué pasa con una cita que no se puede verificar?",
    answer:
      "No cuenta como respaldo. La hipótesis vuelve a su autor en una ronda de recitación, una sola vez, y si sigue sin respaldo no se descarta: queda marcada como especulativa, con nivel de evidencia III.",
  },
  {
    // `components/UploadForm.tsx` (file and text modes), `ingestion/extractor.py`.
    question: "¿Qué documentos se pueden analizar?",
    answer:
      "Un archivo PDF, nativo o escaneado. También se puede pegar el texto del caso clínico.",
  },
  {
    // `backend/pipeline/report_builder.py`, `pdf_exporter.py`, `app/report/page.tsx`.
    question: "¿Qué contiene el reporte?",
    answer:
      "Hipótesis de consenso con su nivel de evidencia, el estado de verificación de cada fuente, las objeciones sin resolver y los ensayos clínicos compatibles. Se puede descargar en PDF.",
  },
];

export default function FaqSection() {
  return (
    <section
      id="preguntas"
      aria-labelledby="preguntas-heading"
      className={`bg-bg ${SECTION_PADDING}`}
    >
      <div className={`${CONTAINER} grid gap-12 lg:grid-cols-12 lg:items-start`}>
        <div className="lg:col-span-5">
          <ScrollReveal>
            <SectionHeading id="preguntas-heading" title="Preguntas frecuentes" />
          </ScrollReveal>
        </div>

        <ul className="grid gap-3 lg:col-span-7">
          {FAQ_ITEMS.map((item) => (
            <li key={item.question}>
              <details className="group rounded-2xl border border-border bg-surface">
                <summary
                  className={`flex cursor-pointer list-none items-center justify-between gap-4 rounded-2xl p-6 text-lg font-semibold text-fg ${TRANSITION} hover:text-accent [&::-webkit-details-marker]:hidden ${FOCUS_RING}`}
                >
                  {item.question}
                  <CaretDownIcon
                    aria-hidden="true"
                    weight="bold"
                    className={`size-5 shrink-0 text-fg-muted ${TRANSITION} group-open:rotate-180`}
                  />
                </summary>
                <p className="px-6 pb-6 text-base text-pretty text-fg-muted">{item.answer}</p>
              </details>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
