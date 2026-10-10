import { ArrowSquareOutIcon } from "@phosphor-icons/react/ssr";
import type { Icon } from "@phosphor-icons/react";
import { BADGE } from "@/components/landing/reportExample";

/**
 * Shared pieces of the report view (`/report`), in the landing visual system.
 *
 * Every colour resolves through the `.landing` tokens, so the view follows the
 * light and the dark theme. A state is never told by colour alone: each badge
 * and notice carries its text, and an icon where the state matters.
 */

/**
 * Tones of a badge. The ramp is the one the landing report card uses: filled
 * accent, outlined accent, ochre and dashed muted. `danger` is the only ink
 * the landing did not have (`--landing-danger` in `globals.css`).
 */
export const TONE = {
  solid: "border-accent bg-accent text-accent-fg",
  positive: "border-accent text-accent",
  warningSolid: "border-ochre bg-ochre text-bg",
  warning: "border-ochre text-ochre",
  danger: "border-(color:--landing-danger) text-(color:--landing-danger)",
  muted: "border-fg-muted text-fg-muted",
  dashed: "border-dashed border-fg-muted text-fg-muted",
  neutral: "border-border bg-bg-subtle text-fg-muted",
} as const;

export type Tone = keyof typeof TONE;

/** Ink of the danger tone, for text and icons outside a badge. */
export const DANGER_INK = "text-(color:--landing-danger)";

/** Small label above a block of the report. */
export const SECTION_LABEL = "text-xs font-semibold text-fg-muted";

/** Inner block of a card: flat, subtle background, its own small radius. */
export const INNER_BLOCK = "rounded-lg bg-bg-subtle p-4";

interface BadgeProps {
  tone: Tone;
  Icon?: Icon;
  /** Native tooltip with the longer explanation, where the view has one. */
  title?: string;
  children: React.ReactNode;
}

/** Badge of the report card: the landing badge with one of the tones. */
export function Badge({ tone, Icon, title, children }: BadgeProps) {
  return (
    <span title={title} className={`${BADGE} ${TONE[tone]}`}>
      {Icon && <Icon aria-hidden="true" weight="bold" className="size-4 shrink-0" />}
      <span className="min-w-0 wrap-anywhere">{children}</span>
    </span>
  );
}

const NOTICE_TONE = {
  positive: { box: "border-accent/40 bg-accent/10", ink: "text-accent" },
  warning: { box: "border-ochre/40 bg-ochre/10", ink: "text-ochre" },
  danger: {
    box: "border-(color:--landing-danger)/40 bg-(--landing-danger)/10",
    ink: DANGER_INK,
  },
  neutral: { box: "border-border bg-bg-subtle", ink: "text-accent" },
} as const;

export type NoticeTone = keyof typeof NOTICE_TONE;

interface NoticeProps {
  tone: NoticeTone;
  Icon: Icon;
  /** Bold lead of the notice (e.g. "Árbitro:"), in the ink of its tone. */
  label?: string;
  /** Announces the notice when it appears (errors raised by a user action). */
  role?: "alert";
  children: React.ReactNode;
}

/** Standing notice above the report: an icon, an optional lead and the text. */
export function Notice({ tone, Icon, label, role, children }: NoticeProps) {
  const { box, ink } = NOTICE_TONE[tone];
  return (
    <div role={role} className={`flex items-start gap-3 rounded-2xl border p-4 ${box}`}>
      <Icon aria-hidden="true" weight="bold" className={`mt-0.5 size-5 shrink-0 ${ink}`} />
      <div className="min-w-0 flex-1 text-sm text-pretty wrap-anywhere text-fg">
        {label && <span className={`font-semibold ${ink}`}>{label} </span>}
        {children}
      </div>
    </div>
  );
}

/** Mark of a link that leaves the site: an icon plus its meaning in text. */
export function NewTabMark() {
  return (
    <>
      <ArrowSquareOutIcon aria-hidden="true" weight="bold" className="size-4 shrink-0" />
      <span className="sr-only">(se abre en una pestaña nueva)</span>
    </>
  );
}

/** Bulleted list of plain strings, as the case and the trial cards use it. */
export function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-fg">
          <span aria-hidden="true" className="mt-2 size-1 shrink-0 rounded-full bg-fg-muted" />
          <span className="min-w-0 wrap-anywhere">{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-fg-muted bg-surface px-6 py-16 text-center">
      <p className="text-sm text-pretty text-fg-muted">{message}</p>
    </div>
  );
}
