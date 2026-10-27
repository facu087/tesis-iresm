import ScrollReveal from "@/components/ScrollReveal";
import AgentTiles from "@/components/landing/AgentTiles";
import SectionHeading from "@/components/landing/SectionHeading";
import { CONTAINER, SECTION_PADDING } from "@/components/landing/styles";

/** The six agents, all implemented and running, as compact tiles. */
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
            title="Seis agentes, un consenso"
          />
        </ScrollReveal>
        <ScrollReveal className="mt-12">
          <AgentTiles />
        </ScrollReveal>
      </div>
    </section>
  );
}
