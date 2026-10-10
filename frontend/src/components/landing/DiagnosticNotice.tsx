import { CONTAINER } from "@/components/landing/styles";

/**
 * Standing notice of the signed in routes: NEXUS does not issue diagnoses.
 * Pass it as the `footer` of `AuthShell` or `ShellFrame`.
 */
export default function DiagnosticNotice() {
  return (
    <footer className={`${CONTAINER} pb-12`}>
      <p className="rounded-2xl border border-border bg-bg-subtle p-4 text-sm text-pretty text-fg-muted">
        <span className="font-semibold text-fg">NEXUS</span> no emite
        diagnósticos clínicos. Las hipótesis generadas son orientativas y
        deben ser evaluadas por el médico responsable.
      </p>
    </footer>
  );
}
