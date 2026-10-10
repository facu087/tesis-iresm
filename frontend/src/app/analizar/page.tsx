"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileArrowUpIcon } from "@phosphor-icons/react/ssr";
import UploadForm from "@/components/UploadForm";
import AuthShell from "@/components/landing/AuthShell";
import { FORM_CARD } from "@/components/landing/FormPrimitives";
import { CONTAINER, NAV_LINK } from "@/components/landing/styles";
import { inputStore } from "@/lib/inputStore";
import type { AnalysisInput } from "@/lib/inputStore";
import { PIPELINE_STEPS } from "@/lib/pipelineSteps";
import { obtenerCuenta } from "@/lib/api";

/** Page frame shared by the session check and the upload view. */
function AnalizarShell({ aside, children }: { aside: React.ReactNode; children: React.ReactNode }) {
  return (
    <AuthShell
      headerAction={
        <Link href="/" className={NAV_LINK}>
          ← Volver al inicio
        </Link>
      }
      icon={<FileArrowUpIcon aria-hidden="true" weight="bold" className="size-6" />}
      title="Cargar caso clínico"
      lead="Subí la historia clínica en PDF o pegá el texto directamente."
      aside={aside}
      footer={
        <footer className={`${CONTAINER} pb-12`}>
          <p className="rounded-2xl border border-border bg-bg-subtle p-4 text-sm text-pretty text-fg-muted">
            <span className="font-semibold text-fg">NEXUS</span> no emite
            diagnósticos clínicos. Las hipótesis generadas son orientativas y
            deben ser evaluadas por el médico responsable.
          </p>
        </footer>
      }
    >
      {children}
    </AuthShell>
  );
}

const STEP_BADGE =
  "inline-flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-bg-subtle";

/** Static explanation of the pipeline, driven by `pipelineSteps.ts`. */
function PipelineSteps() {
  return (
    <section aria-labelledby="pipeline-heading">
      <h2 id="pipeline-heading" className="text-sm font-semibold text-ochre">
        Pipeline de análisis
      </h2>
      <ol className="mt-4 flex flex-col gap-4">
        {PIPELINE_STEPS.map((step) => (
          <li key={step.id} className="flex items-start gap-3">
            <span className={`${STEP_BADGE} font-mono text-xs font-semibold text-accent`}>
              {step.id}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-fg">{step.label}</p>
              <p className="text-sm text-pretty text-fg-muted">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Placeholders shaped like the upload card and the steps list. */
function PipelineStepsSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-4">
      <span className="landing-skeleton h-4 w-40 rounded-full" />
      {PIPELINE_STEPS.map((step) => (
        <div key={step.id} className="flex items-start gap-3">
          <span className="landing-skeleton size-8 shrink-0 rounded-full" />
          <div className="flex flex-1 flex-col gap-2 py-1">
            <span className="landing-skeleton h-4 w-1/3 rounded-full" />
            <span className="landing-skeleton h-4 w-full rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

function UploadSkeleton() {
  return (
    <div className={FORM_CARD}>
      <p role="status" className="text-sm text-fg-muted">
        Verificando sesión...
      </p>
      <div aria-hidden="true" className="flex flex-col gap-6">
        <span className="landing-skeleton h-12 w-full rounded-xl" />
        <span className="landing-skeleton h-48 w-full rounded-xl" />
        <span className="landing-skeleton h-10 w-full rounded-full" />
      </div>
    </div>
  );
}

export default function AnalizarPage() {
  const router = useRouter();
  const [autorizado, setAutorizado] = useState(false);

  // Protección de UX, no de seguridad (proteccion-analisis-clinico —
  // Requirement: La aplicación no es el límite de seguridad): el backend ya
  // rechaza con 401/403 igual, sin sesión de médico verificado. Esto solo
  // evita que alguien sin cuenta cargue un caso para nada.
  useEffect(() => {
    let cancelado = false;
    obtenerCuenta()
      .then((cuenta) => {
        if (cancelado) return;
        if (cuenta === null) {
          router.push("/ingresar");
        } else if (cuenta.rol !== "medico" || cuenta.estado !== "verificado") {
          router.push("/cuenta");
        } else {
          setAutorizado(true);
        }
      })
      .catch(() => {
        if (!cancelado) router.push("/ingresar");
      });
    return () => {
      cancelado = true;
    };
  }, [router]);

  const handleReady = (input: AnalysisInput) => {
    inputStore.set(input);
    router.push("/analyzing");
  };

  if (!autorizado) {
    return (
      <AnalizarShell aside={<PipelineStepsSkeleton />}>
        <UploadSkeleton />
      </AnalizarShell>
    );
  }

  return (
    <AnalizarShell aside={<PipelineSteps />}>
      <div className={FORM_CARD}>
        <UploadForm onReady={handleReady} />
      </div>
    </AnalizarShell>
  );
}
