"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { useRouter } from "next/navigation";
import { logout, obtenerCuenta, reenviarRegistro } from "@/lib/api";
import type { CuentaEstado } from "@/lib/types";
import { AlertIcon, ClockIcon, VerifiedIcon } from "@/components/icons";

const inputClass =
  "w-full rounded-lg border border-border bg-bg px-3.5 py-2.5 text-sm text-fg placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-accent";
const labelClass = "mb-1.5 block text-sm font-medium text-fg";

function Header({ onLogout }: { onLogout: () => void }) {
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-2xl items-center justify-between px-6 py-5">
        <Link
          href="/"
          className="cursor-pointer rounded-sm font-serif text-lg font-semibold tracking-tight text-accent transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
        >
          NEXUS
        </Link>
        <div className="flex items-center gap-2 sm:gap-4">
          <ThemeToggle />
          <button
            type="button"
            onClick={onLogout}
            className="cursor-pointer rounded-sm text-sm text-fg-muted transition-colors duration-200 hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    </header>
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
    <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5 rounded-2xl border border-border bg-bg-subtle p-8">
      <p className="text-sm font-medium text-fg">Corregí tus datos y reenviá la solicitud</p>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="r-nombre" className={labelClass}>Nombre</label>
          <input id="r-nombre" required value={form.nombre} onChange={setField("nombre")} className={inputClass} />
        </div>
        <div>
          <label htmlFor="r-apellido" className={labelClass}>Apellido</label>
          <input id="r-apellido" required value={form.apellido} onChange={setField("apellido")} className={inputClass} />
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="r-dni" className={labelClass}>DNI</label>
          <input id="r-dni" required value={form.dni} onChange={setField("dni")} className={inputClass} />
        </div>
        <div>
          <label htmlFor="r-profesion" className={labelClass}>
            Profesión / especialidad <span className="text-fg-muted">(opcional)</span>
          </label>
          <input id="r-profesion" value={form.profesion} onChange={setField("profesion")} className={inputClass} />
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="r-matricula" className={labelClass}>Matrícula</label>
          <input id="r-matricula" required value={form.matricula} onChange={setField("matricula")} className={inputClass} />
        </div>
        <div>
          <label htmlFor="r-jurisdiccion" className={labelClass}>Jurisdicción</label>
          <input id="r-jurisdiccion" required value={form.jurisdiccion} onChange={setField("jurisdiccion")} className={inputClass} />
        </div>
      </div>

      <div>
        <label htmlFor="r-email" className={labelClass}>Email institucional</label>
        <input id="r-email" type="email" required value={form.email} onChange={setField("email")} className={inputClass} />
      </div>

      <div>
        <label htmlFor="r-password" className={labelClass}>Contraseña</label>
        <input
          id="r-password"
          type="password"
          required
          minLength={8}
          value={form.password}
          onChange={setField("password")}
          className={inputClass}
          autoComplete="new-password"
        />
        <p className="mt-1 text-xs text-fg-muted">Volvé a definirla al reenviar (mínimo 8 caracteres).</p>
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-red-600/30 bg-red-600/10 px-4 py-2 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={enviando}
        className="w-full cursor-pointer rounded-xl bg-accent py-3 font-semibold text-accent-fg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
      >
        {enviando ? "Reenviando..." : "Reenviar solicitud"}
      </button>
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
      <div className="flex min-h-screen flex-col bg-bg text-fg">
        <Header onLogout={handleLogout} />
        <main className="flex-1 px-6 py-14 text-center text-sm text-fg-muted">Cargando...</main>
      </div>
    );
  }

  if (cuenta === null) return null;

  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <Header onLogout={handleLogout} />
      <main className="flex-1">
        <div className="mx-auto max-w-2xl px-6 py-14">
          <h1 className="mb-6 font-serif text-2xl font-semibold">Mi cuenta</h1>

          {cuenta.estado === "pendiente" && (
            <div className="flex items-start gap-4 rounded-2xl border border-border bg-bg-subtle p-8">
              <ClockIcon className="h-7 w-7 shrink-0 text-fg-muted" />
              <div>
                <p className="font-medium text-fg">Pendiente de revisión</p>
                <p className="mt-1 text-sm text-fg-muted">
                  Un administrador va a revisar tu matrícula contra los buscadores públicos. Vas a
                  poder analizar casos clínicos una vez que tu cuenta quede verificada.
                </p>
              </div>
            </div>
          )}

          {cuenta.estado === "rechazado" && (
            <>
              <div className="flex items-start gap-4 rounded-2xl border border-red-600/30 bg-red-600/10 p-8">
                <AlertIcon className="h-7 w-7 shrink-0 text-red-700 dark:text-red-400" />
                <div>
                  <p className="font-medium text-fg">Solicitud rechazada</p>
                  <p className="mt-1 text-sm text-fg-muted">
                    {cuenta.motivo_rechazo || "El administrador no dejó un motivo registrado."}
                  </p>
                </div>
              </div>
              <FormularioReenvio cuenta={cuenta} onReenviado={setCuenta} />
            </>
          )}

          {cuenta.estado === "verificado" && (
            <div className="flex items-start gap-4 rounded-2xl border border-border bg-bg-subtle p-8">
              <VerifiedIcon className="h-7 w-7 shrink-0 text-fg" />
              <div>
                <p className="font-medium text-fg">Cuenta verificada</p>
                <p className="mt-1 text-sm text-fg-muted">
                  Ya podés analizar casos clínicos con el pipeline de NEXUS.
                </p>
                <Link
                  href="/analizar"
                  className="mt-4 inline-block cursor-pointer rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
                >
                  Analizar un caso →
                </Link>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
