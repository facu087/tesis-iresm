"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowSquareOutIcon, ShieldCheckIcon } from "@phosphor-icons/react/ssr";
import { aprobarCuenta, listarPendientes, logout, obtenerCuenta, rechazarCuenta } from "@/lib/api";
import type { CuentaPendiente } from "@/lib/types";
import AuthShell from "@/components/landing/AuthShell";
import DiagnosticNotice from "@/components/landing/DiagnosticNotice";
import { FormError, FormField } from "@/components/landing/FormPrimitives";
import {
  CARD,
  NAV_LINK,
  SECONDARY_SUBMIT_BUTTON,
  SUBMIT_BUTTON,
  TEXT_LINK,
} from "@/components/landing/styles";

const LIST_ERROR_ID = "pendientes-error";

/** Inner card of one decision (approve or reject): a field and its button. */
const DECISION_FORM = "flex flex-col gap-4 rounded-xl border border-border bg-bg-subtle p-4";

/** External licence lookup link: opens in a new tab, marked with an icon. */
const LOOKUP_LINK = `inline-flex items-center gap-1 text-sm ${TEXT_LINK}`;

/** One labelled datum of the account under review. */
function Dato({
  label,
  mono = false,
  children,
}: {
  label: string;
  /** Identifiers (DNI, licence number) are set in Geist Mono. */
  mono?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold text-fg-muted">{label}</dt>
      <dd className={`mt-0.5 text-sm wrap-anywhere text-fg ${mono ? "font-mono" : ""}`}>
        {children}
      </dd>
    </div>
  );
}

function FilaPendiente({
  cuenta,
  onDecidida,
}: {
  cuenta: CuentaPendiente;
  onDecidida: (id: number) => void;
}) {
  const [fuenteConsultada, setFuenteConsultada] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<"aprobar" | "rechazar" | null>(null);

  const errorId = `decision-error-${cuenta.id}`;
  const describedBy = error ? errorId : undefined;

  const handleAprobar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEnviando("aprobar");
    try {
      await aprobarCuenta(cuenta.id, fuenteConsultada);
      onDecidida(cuenta.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo aprobar la cuenta.");
    } finally {
      setEnviando(null);
    }
  };

  const handleRechazar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEnviando("rechazar");
    try {
      await rechazarCuenta(cuenta.id, motivo);
      onDecidida(cuenta.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo rechazar la cuenta.");
    } finally {
      setEnviando(null);
    }
  };

  return (
    <li className={`${CARD} flex flex-col gap-6 sm:p-8`}>
      <div>
        <p className="text-lg font-semibold wrap-anywhere text-fg">
          {cuenta.nombre} {cuenta.apellido}
        </p>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          <Dato label="Email">{cuenta.email}</Dato>
          <Dato label="DNI" mono>
            {cuenta.dni}
          </Dato>
          <Dato label="Matrícula">
            <span className="font-mono">{cuenta.matricula}</span> ({cuenta.jurisdiccion})
          </Dato>
          {cuenta.profesion && <Dato label="Profesión">{cuenta.profesion}</Dato>}
          <Dato label="Registrada">{new Date(cuenta.creada_en).toLocaleString("es-AR")}</Dato>
        </dl>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-2">
        <a href={cuenta.enlace_refeps} target="_blank" rel="noreferrer" className={LOOKUP_LINK}>
          Buscador Nacional REFEPS
          <ArrowSquareOutIcon aria-hidden="true" weight="bold" className="size-4 shrink-0" />
          <span className="sr-only">(se abre en una pestaña nueva)</span>
        </a>
        {cuenta.enlace_provincial && (
          <a
            href={cuenta.enlace_provincial}
            target="_blank"
            rel="noreferrer"
            className={LOOKUP_LINK}
          >
            Buscador provincial
            <ArrowSquareOutIcon aria-hidden="true" weight="bold" className="size-4 shrink-0" />
            <span className="sr-only">(se abre en una pestaña nueva)</span>
          </a>
        )}
      </div>

      {/* Side by side while each form keeps a usable width: the main column
          of the shell is narrower at `lg` than on a tablet. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        <form onSubmit={handleAprobar} className={DECISION_FORM}>
          <FormField
            id={`fuente-${cuenta.id}`}
            label="Fuente consultada (obligatoria para aprobar)"
            required
            value={fuenteConsultada}
            onChange={(e) => setFuenteConsultada(e.target.value)}
            placeholder="Ej: Buscador Nacional REFEPS"
          />
          <button
            type="submit"
            disabled={enviando !== null}
            aria-busy={enviando === "aprobar"}
            aria-describedby={describedBy}
            className={`mt-auto ${SUBMIT_BUTTON}`}
          >
            {enviando === "aprobar" ? "Aprobando..." : "Aprobar"}
          </button>
        </form>

        <form onSubmit={handleRechazar} className={DECISION_FORM}>
          <FormField
            id={`motivo-${cuenta.id}`}
            label="Motivo (obligatorio para rechazar)"
            required
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ej: los datos no coinciden con el buscador"
          />
          <button
            type="submit"
            disabled={enviando !== null}
            aria-busy={enviando === "rechazar"}
            aria-describedby={describedBy}
            className={`mt-auto ${SECONDARY_SUBMIT_BUTTON}`}
          >
            {enviando === "rechazar" ? "Rechazando..." : "Rechazar"}
          </button>
        </form>
      </div>

      {error && <FormError id={errorId}>{error}</FormError>}
    </li>
  );
}

/** Placeholder shaped like an account card, shown while the list loads. */
function PendientesSkeleton() {
  return (
    <div className={`${CARD} sm:p-8`}>
      <p role="status" className="text-sm text-fg-muted">
        Cargando...
      </p>
      <div aria-hidden="true" className="mt-4 flex flex-col gap-4">
        <span className="landing-skeleton h-6 w-1/2 rounded-full" />
        <span className="landing-skeleton h-4 w-full rounded-full" />
        <span className="landing-skeleton h-4 w-2/3 rounded-full" />
        <span className="landing-skeleton h-24 w-full rounded-xl" />
      </div>
    </div>
  );
}

export default function AdminPendientesPage() {
  const router = useRouter();
  const [pendientes, setPendientes] = useState<CuentaPendiente[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    obtenerCuenta()
      .then((cuenta) => {
        if (cuenta === null) {
          router.push("/ingresar");
          return;
        }
        if (cuenta.rol !== "admin") {
          router.push("/");
          return;
        }
        return listarPendientes()
          .then(setPendientes)
          .catch(() => setError("No se pudo cargar el listado de cuentas pendientes."));
      })
      .catch(() => setError("No se pudo verificar la sesión."));
  }, [router]);

  const handleLogout = async () => {
    await logout().catch(() => {});
    router.push("/");
  };

  const quitarDeLaLista = (id: number) => setPendientes((p) => (p ? p.filter((c) => c.id !== id) : p));

  return (
    <AuthShell
      headerAction={
        <button type="button" onClick={handleLogout} className={`${NAV_LINK} cursor-pointer`}>
          Cerrar sesión
        </button>
      }
      icon={<ShieldCheckIcon aria-hidden="true" weight="bold" className="size-6" />}
      title="Cuentas pendientes"
      lead="Revisá cada matrícula contra los buscadores públicos antes de decidir."
      footer={<DiagnosticNotice />}
    >
      <div className="flex flex-col gap-6">
        {error && <FormError id={LIST_ERROR_ID}>{error}</FormError>}

        {pendientes === null && !error && <PendientesSkeleton />}

        {pendientes !== null && pendientes.length === 0 && (
          <p className={`${CARD} text-sm text-pretty text-fg-muted sm:p-8`}>
            No hay cuentas pendientes de revisión.
          </p>
        )}

        {pendientes !== null && pendientes.length > 0 && (
          <ul className="flex flex-col gap-6">
            {pendientes.map((cuenta) => (
              <FilaPendiente key={cuenta.id} cuenta={cuenta} onDecidida={quitarDeLaLista} />
            ))}
          </ul>
        )}
      </div>
    </AuthShell>
  );
}
