"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ClockIcon,
  SealCheckIcon,
  ShieldCheckIcon,
  UserCircleIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react/ssr";
import { logout, obtenerCuenta, reenviarRegistro } from "@/lib/api";
import type { CuentaEstado } from "@/lib/types";
import AuthShell from "@/components/landing/AuthShell";
import {
  FORM_CARD,
  FormError,
  FormField,
  SubmitButton,
} from "@/components/landing/FormPrimitives";
import { NAV_LINK, PRIMARY_BUTTON } from "@/components/landing/styles";

const ERROR_ID = "reenvio-error";

/** Page frame shared by the loading and the loaded states. */
function CuentaShell({ onLogout, children }: { onLogout: () => void; children: React.ReactNode }) {
  return (
    <AuthShell
      headerAction={
        <button type="button" onClick={onLogout} className={`${NAV_LINK} cursor-pointer`}>
          Cerrar sesión
        </button>
      }
      icon={<UserCircleIcon aria-hidden="true" weight="bold" className="size-6" />}
      title="Mi cuenta"
    >
      <div className="flex flex-col gap-6">{children}</div>
    </AuthShell>
  );
}

const STATUS_TONE = {
  neutral: { card: "border-border bg-surface", icon: "border-border bg-bg-subtle text-accent" },
  pending: { card: "border-border bg-surface", icon: "border-border bg-bg-subtle text-ochre" },
  danger: {
    card: "border-red-700/40 bg-red-600/10 dark:border-red-400/40",
    icon: "border-red-700/40 bg-bg text-red-700 dark:border-red-400/40 dark:text-red-300",
  },
} as const;

interface StatusCardProps {
  tone: keyof typeof STATUS_TONE;
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}

/** Account status: icon badge, status name and its explanation. */
function StatusCard({ tone, icon, title, children }: StatusCardProps) {
  const styles = STATUS_TONE[tone];
  return (
    <div className={`flex items-start gap-4 rounded-2xl border p-6 sm:p-8 ${styles.card}`}>
      <span
        className={`inline-flex size-12 shrink-0 items-center justify-center rounded-full border ${styles.icon}`}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-lg font-semibold text-fg">{title}</p>
        {children}
      </div>
    </div>
  );
}

/** Placeholder shaped like a status card, shown while the account loads. */
function StatusSkeleton() {
  return (
    <div className="flex items-start gap-4 rounded-2xl border border-border bg-surface p-6 sm:p-8">
      <span aria-hidden="true" className="landing-skeleton size-12 shrink-0 rounded-full" />
      <div className="min-w-0 flex-1">
        <p role="status" className="text-sm text-fg-muted">
          Cargando...
        </p>
        <div aria-hidden="true" className="mt-3 flex flex-col gap-2">
          <span className="landing-skeleton h-4 w-full rounded-full" />
          <span className="landing-skeleton h-4 w-2/3 rounded-full" />
        </div>
      </div>
    </div>
  );
}

function FormularioReenvio({ cuenta, onReenviado }: { cuenta: CuentaEstado; onReenviado: (c: CuentaEstado) => void }) {
  const [form, setForm] = useState({
    nombre: cuenta.nombre ?? "",
    apellido: cuenta.apellido ?? "",
    dni: cuenta.dni ?? "",
    matricula: cuenta.matricula ?? "",
    jurisdiccion: cuenta.jurisdiccion ?? "",
    profesion: cuenta.profesion ?? "",
    email: cuenta.email,
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const setField = (campo: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [campo]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const actualizada = await reenviarRegistro({
        ...form,
        profesion: form.profesion.trim() || undefined,
        acepta_tratamiento_datos: true,
      });
      onReenviado(actualizada);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo reenviar el registro.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className={FORM_CARD}>
      <p className="text-base font-semibold text-fg">Corregí tus datos y reenviá la solicitud</p>

      <div className="grid gap-6 sm:grid-cols-2">
        <FormField id="r-nombre" label="Nombre" required value={form.nombre} onChange={setField("nombre")} />
        <FormField id="r-apellido" label="Apellido" required value={form.apellido} onChange={setField("apellido")} />
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <FormField id="r-dni" label="DNI" required value={form.dni} onChange={setField("dni")} />
        <FormField
          id="r-profesion"
          label={
            <>
              Profesión / especialidad <span className="font-normal text-fg-muted">(opcional)</span>
            </>
          }
          value={form.profesion}
          onChange={setField("profesion")}
        />
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <FormField id="r-matricula" label="Matrícula" required value={form.matricula} onChange={setField("matricula")} />
        <FormField id="r-jurisdiccion" label="Jurisdicción" required value={form.jurisdiccion} onChange={setField("jurisdiccion")} />
      </div>

      <FormField id="r-email" label="Email institucional" type="email" required value={form.email} onChange={setField("email")} />

      <FormField
        id="r-password"
        label="Contraseña"
        type="password"
        required
        minLength={8}
        value={form.password}
        onChange={setField("password")}
        autoComplete="new-password"
        hint="Volvé a definirla al reenviar (mínimo 8 caracteres)."
      />

      {error && <FormError id={ERROR_ID}>{error}</FormError>}

      <SubmitButton pending={enviando} describedBy={error ? ERROR_ID : undefined}>
        {enviando ? "Reenviando..." : "Reenviar solicitud"}
      </SubmitButton>
    </form>
  );
}

export default function CuentaPage() {
  const router = useRouter();
  const [cuenta, setCuenta] = useState<CuentaEstado | null | undefined>(undefined);

  useEffect(() => {
    obtenerCuenta()
      .then((c) => {
        if (c === null) {
          router.push("/ingresar");
        } else {
          setCuenta(c);
        }
      })
      .catch(() => setCuenta(null));
  }, [router]);

  const handleLogout = async () => {
    await logout().catch(() => {});
    router.push("/");
  };

  if (cuenta === undefined) {
    return (
      <CuentaShell onLogout={handleLogout}>
        <StatusSkeleton />
      </CuentaShell>
    );
  }

  if (cuenta === null) return null;

  // An admin has no licence under review and cannot analyse cases (the
  // backend only accepts the analysis from a verified physician): the account
  // page leads to the review of registrations instead.
  if (cuenta.rol === "admin") {
    return (
      <CuentaShell onLogout={handleLogout}>
        <StatusCard
          tone="neutral"
          icon={<ShieldCheckIcon aria-hidden="true" weight="bold" className="size-6" />}
          title="Cuenta de administrador"
        >
          <p className="mt-2 text-sm text-pretty text-fg-muted">
            Revisá las solicitudes de registro y decidí cada matrícula.
          </p>
          <Link href="/admin/pendientes" className={`mt-4 ${PRIMARY_BUTTON}`}>
            Cuentas pendientes →
          </Link>
        </StatusCard>
      </CuentaShell>
    );
  }

  return (
    <CuentaShell onLogout={handleLogout}>
      {cuenta.estado === "pendiente" && (
        <StatusCard
          tone="pending"
          icon={<ClockIcon aria-hidden="true" weight="bold" className="size-6" />}
          title="Pendiente de revisión"
        >
          <p className="mt-2 text-sm text-pretty text-fg-muted">
            Un administrador va a revisar tu matrícula contra los buscadores públicos. Vas a
            poder analizar casos clínicos una vez que tu cuenta quede verificada.
          </p>
        </StatusCard>
      )}

      {cuenta.estado === "rechazado" && (
        <>
          <StatusCard
            tone="danger"
            icon={<WarningCircleIcon aria-hidden="true" weight="bold" className="size-6" />}
            title="Solicitud rechazada"
          >
            <p className="mt-2 text-sm text-pretty wrap-anywhere text-fg">
              {cuenta.motivo_rechazo || "El administrador no dejó un motivo registrado."}
            </p>
          </StatusCard>
          <FormularioReenvio cuenta={cuenta} onReenviado={setCuenta} />
        </>
      )}

      {cuenta.estado === "verificado" && (
        <StatusCard
          tone="neutral"
          icon={<SealCheckIcon aria-hidden="true" weight="bold" className="size-6" />}
          title="Cuenta verificada"
        >
          <p className="mt-2 text-sm text-pretty text-fg-muted">
            Ya podés analizar casos clínicos con el pipeline de NEXUS.
          </p>
          <Link href="/analizar" className={`mt-4 ${PRIMARY_BUTTON}`}>
            Analizar un caso →
          </Link>
        </StatusCard>
      )}
    </CuentaShell>
  );
}
