import ScrollReveal from "@/components/ScrollReveal";
import ReportDemo, { ANNOTATION_DOT, REPORT_ANNOTATIONS } from "@/components/ReportDemo";
import SectionHeading from "@/components/landing/SectionHeading";
import { CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/**
 * The report: what the physician receives, shown as the example report with
 * four numbered annotations. Each number in the legend matches a mark placed
 * on the part of the report it refers to (`REPORT_ANNOTATIONS`).
 */
export default function ReportSection() {
  return (
    <section
      id="reporte"
      aria-labelledby="reporte-heading"
      className={`bg-bg-subtle ${SECTION_PADDING}`}
    >
      <div className={CONTAINER}>
        <ScrollReveal>
          <SectionHeading
            id="reporte-heading"
            eyebrow="El reporte"
            title="Lo que recibe el médico"
          />
          <ol className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {REPORT_ANNOTATIONS.map((label, index) => (
              <li key={label} className="flex items-center gap-2 text-base font-semibold text-fg">
                <span aria-hidden="true" className={ANNOTATION_DOT}>
                  {index + 1}
                </span>
                {label}
              </li>
            ))}
          </ol>
        </ScrollReveal>
        <ScrollReveal className="mt-8">
          <ReportDemo />
        </ScrollReveal>
      </div>
    </section>
  );
}
