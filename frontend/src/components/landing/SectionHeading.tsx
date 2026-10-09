/**
 * Heading block shared by the landing sections: an optional short eyebrow in
 * sentence case and the section title. Width is capped like the hero (680 px)
 * so lines break where the thought breaks.
 */

interface SectionHeadingProps {
  /** `id` of the `<h2>`, referenced by the section's `aria-labelledby`. */
  id: string;
  eyebrow?: string;
  title: string;
}

export default function SectionHeading({ id, eyebrow, title }: SectionHeadingProps) {
  return (
    <div className="max-w-[680px]">
      {eyebrow && <p className="mb-3 text-sm font-semibold text-ochre">{eyebrow}</p>}
      <h2 id={id} className="text-3xl font-semibold text-balance text-fg sm:text-4xl">
        {title}
      </h2>
    </div>
  );
}
