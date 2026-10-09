/**
 * Heading block shared by the landing sections: a short eyebrow in sentence
 * case, the section title and an optional lead paragraph. Width is capped
 * like the hero (680 px) so lines break where the thought breaks.
 */

interface SectionHeadingProps {
  /** `id` of the `<h2>`, referenced by the section's `aria-labelledby`. */
  id: string;
  eyebrow: string;
  title: string;
  lead?: string;
}

export default function SectionHeading({ id, eyebrow, title, lead }: SectionHeadingProps) {
  return (
    <div className="max-w-[680px]">
      <p className="text-sm font-semibold text-ochre">{eyebrow}</p>
      <h2
        id={id}
        className="mt-3 text-3xl font-semibold text-balance text-fg sm:text-4xl"
      >
        {title}
      </h2>
      {lead && <p className="mt-4 text-lg text-pretty text-fg-muted">{lead}</p>}
    </div>
  );
}
