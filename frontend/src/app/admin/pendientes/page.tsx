"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { useRouter } from "next/navigation";
import { aprobarCuenta, listarPendientes, logout, obtenerCuenta, rechazarCuenta } from "@/lib/api";
import type { CuentaPendiente } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-fg-muted bg-bg px-3 py-2 text-sm text-fg placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-accent";

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
    <li className="rounded-2xl border border-border bg-bg-subtle p-6">
      <div className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
        <p><span className="text-fg-muted">Nombre: </span>{cuenta.nombre} {cuenta.apellido}</p>
        <p><span className="text-fg-muted">Email: </span>{cuenta.email}</p>
        <p><span className="text-fg-muted">DNI: </span>{cuenta.dni}</p>
        <p><span className="text-fg-muted">Matrícula: </span>{cuenta.matricula} ({cuenta.jurisdiccion})</p>
        {cuenta.profesion && <p><span className="text-fg-muted">Profesión: </span>{cuenta.profesion}</p>}
        <p><span className="text-fg-muted">Registrada: </span>{new Date(cuenta.creada_en).toLocaleString("es-AR")}</p>
      </div>

      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        <a
          href={cuenta.enlace_refeps}
          target="_blank"
          rel="noreferrer"
          className="cursor-pointer font-medium text-fg underline underline-offset-2"
        >
          Buscador Nacional REFEPS ↗
        </a>
        {cuenta.enlace_provincial && (
          <a
            href={cuenta.enlace_provincial}
            target="_blank"
            rel="noreferrer"
            className="cursor-pointer font-medium text-fg underline underline-offset-2"
          >
            Buscador provincial ↗
          </a>
        )}
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <form onSubmit={handleAprobar} className="space-y-2 rounded-xl border border-border bg-bg p-4">
          <label htmlFor={`fuente-${cuenta.id}`} className="block text-xs font-medium text-fg-muted">
            Fuente consultada (obligatoria para aprobar)
          </label>
          <input
            id={`fuente-${cuenta.id}`}
            required
            value={fuenteConsultada}
            onChange={(e) => setFuenteConsultada(e.target.value)}
            placeholder="Ej: Buscador Nacional REFEPS"
            className={inputClass}
          />
          <button
            type="submit"
            disabled={enviando !== null}
            className="w-full cursor-pointer rounded-lg bg-accent py-2 text-sm font-semibold text-accent-fg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
          >
            {enviando === "aprobar" ? "Aprobando..." : "Aprobar"}
          </button>
        </form>

        <form onSubmit={handleRechazar} className="space-y-2 rounded-xl border border-border bg-bg p-4">
          <label htmlFor={`motivo-${cuenta.id}`} className="block text-xs font-medium text-fg-muted">
            Motivo (obligatorio para rechazar)
          </label>
          <input
            id={`motivo-${cuenta.id}`}
            required
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ej: los datos no coinciden con el buscador"
            className={inputClass}
          />
          <button
            type="submit"
            disabled={enviando !== null}
            className="w-full cursor-pointer rounded-lg border border-border py-2 text-sm font-semibold text-fg transition-colors duration-200 hover:bg-bg-subtle focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-60"
          >
            {enviando === "rechazar" ? "Rechazando..." : "Rechazar"}
          </button>
        </form>
      </div>

      {error && (
        <p role="alert" className="mt-3 rounded-lg border border-red-600/30 bg-red-600/10 px-4 py-2 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}
    </li>
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
    <div className="flex min-h-screen font-body flex-col bg-bg text-fg">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-5">
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
              onClick={handleLogout}
              className="cursor-pointer rounded-sm text-sm text-fg-muted transition-colors duration-200 hover:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-3xl px-6 py-14">
          <h1 className="mb-1 font-serif text-2xl font-semibold">Cuentas pendientes</h1>
          <p className="mb-8 text-sm text-fg-muted">
            Revisá cada matrícula contra los buscadores públicos antes de decidir.
          </p>

          {error && (
            <p role="alert" className="mb-6 rounded-lg border border-red-600/30 bg-red-600/10 px-4 py-2 text-sm text-red-700 dark:text-red-400">
              {error}
            </p>
          )}

          {pendientes === null && !error && (
            <p className="text-sm text-fg-muted">Cargando...</p>
          )}

          {pendientes !== null && pendientes.length === 0 && (
            <p className="rounded-2xl border border-border bg-bg-subtle p-8 text-sm text-fg-muted">
              No hay cuentas pendientes de revisión.
            </p>
          )}

          {pendientes !== null && pendientes.length > 0 && (
            <ul className="space-y-5">
              {pendientes.map((cuenta) => (
                <FilaPendiente key={cuenta.id} cuenta={cuenta} onDecidida={quitarDeLaLista} />
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
