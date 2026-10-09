import ScrollReveal from "@/components/ScrollReveal";
import SectionHeading from "@/components/landing/SectionHeading";
import { CARD, CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * Frequently asked questions, in plain question and answer form.
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
    // Scope notice of the product (current landing, `.claude/CLAUDE.md`).
    question: "¿NEXUS emite diagnósticos?",
    answer:
      "No. NEXUS genera hipótesis de investigación para que las evalúe el médico responsable. Las hipótesis son orientativas.",
  },
  {
    // `backend/api/router.py` (protected endpoints), `app/cuenta/page.tsx`.
    question: "¿Quién puede usar NEXUS?",
    answer:
      "Médicos registrados con su matrícula. Un administrador revisa cada solicitud y, mientras la cuenta está pendiente de revisión, no se pueden analizar casos.",
  },
  {
    // `app/registro/page.tsx`: required fields and the consent text.
    question: "¿Qué datos pide el registro?",
    answer:
      "Nombre y apellido, DNI, matrícula, jurisdicción de matriculación, email y una contraseña. El formulario pide además el consentimiento para tratar esos datos con el fin de verificar la habilitación profesional, conforme a la Ley 25.326.",
  },
  {
    // `components/UploadForm.tsx` (file and text modes), `ingestion/extractor.py`.
    question: "¿Qué documentos se pueden analizar?",
    answer:
      "Un archivo PDF, nativo o escaneado, del que se extrae el texto con OCR cuando hace falta. También se puede pegar el texto del caso clínico.",
  },
  {
    // `backend/pipeline/verification.py`, `components/BeforeAfter.tsx`.
    question: "¿Cómo se verifica una cita?",
    answer:
      "Cada PMID citado por un agente se consulta en PubMed y el título real del artículo se compara con el título citado. Si no coinciden, la referencia no cuenta como respaldo de la hipótesis.",
  },
  {
    // `backend/pipeline/recitation.py`, `backend/pipeline/evidence.py`.
    question: "¿Qué pasa con una hipótesis que queda sin respaldo?",
    answer:
      "Vuelve a su autor en una ronda de recitación, una sola vez, para que cite sobre la literatura recuperada. Si sigue sin respaldo no se descarta: queda marcada como especulativa, con nivel de evidencia III.",
  },
  {
    // Current landing copy ("Es un caso medido, no una tasa general").
    question: "¿La cifra de 14 de 18 citas es una tasa general?",
    answer:
      "No. Es el resultado de una corrida real del caso de prueba, del 22 de septiembre de 2026: 14 citas no coincidieron con PubMed, 3 coincidieron y 1 no traía PMID. Es un caso medido, no una tasa general.",
  },
  {
    // `backend/pipeline/pdf_exporter.py`, `app/report/page.tsx` (download).
    question: "¿El reporte se puede exportar?",
    answer:
      "Sí. El reporte se puede descargar en PDF, con las hipótesis, sus fuentes y el estado de verificación de cada una.",
  },
];

export default function FaqSection() {
  return (
    <section
      id="preguntas"
      aria-labelledby="preguntas-heading"
      className={`bg-bg ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <SectionHeading
            id="preguntas-heading"
            eyebrow="Preguntas frecuentes"
            title="Lo que conviene saber antes de solicitar acceso"
          />
        </ScrollReveal>

        <dl className="mt-12 grid gap-4 lg:grid-cols-2">
          {FAQ_ITEMS.map((item, index) => (
            // The reveal wrapper is the `<div>` group a `<dl>` allows around
            // each `<dt>`/`<dd>` pair, so it carries the card styles itself.
            <ScrollReveal key={item.question} delay={(index % 2) * 120} className={CARD}>
              <dt className="text-lg font-semibold text-balance text-fg">
                {item.question}
              </dt>
              <dd className="mt-2 text-base text-pretty text-fg-muted">{item.answer}</dd>
            </ScrollReveal>
          ))}
        </dl>
      </div>
    </section>
  );
}
