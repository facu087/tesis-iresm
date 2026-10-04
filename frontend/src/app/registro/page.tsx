"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { registrarMedico } from "@/lib/api";
import { UserPlusIcon } from "@/components/icons";

const inputClass =
  "w-full rounded-lg border border-border bg-bg px-3.5 py-2.5 text-sm text-fg placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-fg-muted";
const labelClass = "mb-1.5 block text-sm font-medium text-fg";

export default function RegistroPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    nombre: "",
    apellido: "",
    dni: "",
    matricula: "",
    jurisdiccion: "",
    profesion: "",
    email: "",
    password: "",
  });
  const [aceptaTratamientoDatos, setAceptaTratamientoDatos] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const setField = (campo: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [campo]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!aceptaTratamientoDatos) {
      setError("Debés aceptar el tratamiento de tus datos personales para continuar.");
      return;
    }

    setEnviando(true);
    try {
      await registrarMedico({
        ...form,
        profesion: form.profesion.trim() || undefined,
        acepta_tratamiento_datos: aceptaTratamientoDatos,
      });
      router.push("/ingresar?registrado=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar el registro.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="cursor-pointer rounded-sm text-sm font-semibold tracking-tight transition-colors duration-200 hover:text-fg-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            NEXUS
          </Link>
          <Link
            href="/ingresar"
            className="cursor-pointer rounded-sm text-sm text-fg-muted transition-colors duration-200 hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg"
          >
            Ya tengo cuenta — Ingresar
          </Link>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-2xl px-6 py-14">
          <div className="mb-8 flex items-center gap-3">
            <UserPlusIcon className="h-7 w-7" />
            <div>
              <h1 className="text-xl font-semibold">Registro de médicos</h1>
              <p className="text-sm text-fg-muted">
                Tu cuenta queda pendiente hasta que un administrador la revise.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-5 rounded-2xl border border-border bg-bg-subtle p-8">
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="nombre" className={labelClass}>Nombre</label>
                <input id="nombre" required value={form.nombre} onChange={setField("nombre")} className={inputClass} autoComplete="given-name" />
              </div>
              <div>
                <label htmlFor="apellido" className={labelClass}>Apellido</label>
                <input id="apellido" required value={form.apellido} onChange={setField("apellido")} className={inputClass} autoComplete="family-name" />
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="dni" className={labelClass}>DNI</label>
                <input id="dni" required value={form.dni} onChange={setField("dni")} className={inputClass} inputMode="numeric" />
              </div>
              <div>
                <label htmlFor="profesion" className={labelClass}>
                  Profesión / especialidad <span className="text-fg-muted">(opcional)</span>
                </label>
                <input id="profesion" value={form.profesion} onChange={setField("profesion")} className={inputClass} />
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="matricula" className={labelClass}>Matrícula</label>
                <input id="matricula" required value={form.matricula} onChange={setField("matricula")} className={inputClass} />
              </div>
              <div>
                <label htmlFor="jurisdiccion" className={labelClass}>Jurisdicción de matriculación</label>
                <input id="jurisdiccion" required value={form.jurisdiccion} onChange={setField("jurisdiccion")} className={inputClass} placeholder="Ej: Córdoba" />
              </div>
            </div>

            <div>
              <label htmlFor="email" className={labelClass}>Email institucional</label>
              <input id="email" type="email" required value={form.email} onChange={setField("email")} className={inputClass} autoComplete="email" />
            </div>

            <div>
              <label htmlFor="password" className={labelClass}>Contraseña</label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={setField("password")}
                className={inputClass}
                autoComplete="new-password"
              />
              <p className="mt-1 text-xs text-fg-muted">Mínimo 8 caracteres.</p>
            </div>

            <label className="flex items-start gap-3 text-sm text-fg-muted">
              <input
                type="checkbox"
                checked={aceptaTratamientoDatos}
                onChange={(e) => setAceptaTratamientoDatos(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fg"
              />
              <span>
                Acepto el tratamiento de mis datos personales (nombre, DNI, matrícula, email y
                contraseña) con la finalidad de verificar mi habilitación profesional y darme
                acceso al pipeline de NEXUS, conforme a la Ley 25.326.
              </span>
            </label>

            {error && (
              <p role="alert" className="rounded-lg border border-red-600/30 bg-red-600/10 px-4 py-2 text-sm text-red-700 dark:text-red-400">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="w-full cursor-pointer rounded-xl bg-fg py-3 font-semibold text-bg transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-fg disabled:cursor-not-allowed disabled:opacity-60"
            >
              {enviando ? "Enviando..." : "Registrarme"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
