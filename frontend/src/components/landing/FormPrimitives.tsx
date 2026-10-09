import { EASE, SUBMIT_BUTTON } from "@/components/landing/styles";

/**
 * Form primitives of the access pages, in the landing visual system. They
 * only draw: values, handlers and validation attributes come from the page.
 */

/** Flat card that holds a form: border all the way around. */
export const FORM_CARD =
  "flex flex-col gap-6 rounded-2xl border border-border bg-surface p-6 sm:p-8";

const LABEL = "mb-2 block text-sm font-semibold text-fg";

const INPUT = `w-full rounded-lg border border-fg-muted bg-bg px-3 py-2 text-base text-fg placeholder:text-fg-muted transition-colors duration-700 ${EASE} hover:border-accent focus-visible:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent`;

interface FormFieldProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "id" | "className"> {
  id: string;
  label: React.ReactNode;
  /** Help text under the input, tied to it with `aria-describedby`. */
  hint?: string;
}

/** Labelled text input. The label is bound to the input through `id`. */
export function FormField({ id, label, hint, ...inputProps }: FormFieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <input id={id} aria-describedby={hintId} className={INPUT} {...inputProps} />
      {hint && (
        <p id={hintId} className="mt-2 text-xs text-fg-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

/** Inline form error, announced as soon as it is rendered. */
export function FormError({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <p
      id={id}
      role="alert"
      className="rounded-lg border border-red-700/40 bg-red-600/10 px-4 py-3 text-sm text-pretty text-red-700 dark:border-red-400/40 dark:text-red-300"
    >
      {children}
    </p>
  );
}

interface SubmitButtonProps {
  /** True while the request is in flight: the button is disabled. */
  pending: boolean;
  /** `id` of the rendered form error, if any. */
  describedBy?: string;
  children: React.ReactNode;
}

/** Submit button with hover, active, focus and pending states. */
export function SubmitButton({ pending, describedBy, children }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={pending}
      aria-busy={pending}
      aria-describedby={describedBy}
      className={SUBMIT_BUTTON}
    >
      {children}
    </button>
  );
}
