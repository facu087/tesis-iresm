"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { login } from "@/lib/api";
import { LockIcon } from "@/components/icons";

const inputClass =
  "w-full rounded-lg border border-border bg-bg px-3.5 py-2.5 text-sm text-fg placeholder:text-fg-muted focus:outline-none focus:ring-2 focus:ring-accent";
const labelClass = "mb-1.5 block text-sm font-medium text-fg";

function IngresarForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const recienRegistrado = searchParams.get("registrado") === "1";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await login(email, password);
      router.push("/cuenta");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="mx-auto max-w-md px-6 py-14">
      <div className="mb-8 flex items-center gap-3">
        <LockIcon className="h-7 w-7" />
        <h1 className="font-serif text-2xl font-semibold">Ingresar</h1>
      </div>

      {recienRegistrado && (
        <p className="mb-6 rounded-lg border border-border bg-bg-subtle px-4 py-3 text-sm text-fg-muted">
          Tu cuenta fue creada y quedó <strong className="text-fg">pendiente de revisión</strong>.
          Iniciá sesión para ver su estado.
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-5 rounded-2xl border border-border bg-bg-subtle p-8">
        <div>
          <label htmlFor="email" className={labelClass}>Email institucional</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
            autoComplete="email"
          />
        </div>

        <div>
          <label htmlFor="password" className={labelClass}>Contraseña</label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
            autoComplete="current-password"
          />
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
          {enviando ? "Ingresando..." : "Ingresar"}
        </button>

        <p className="text-center text-sm text-fg-muted">
          ¿No tenés cuenta?{" "}
          <Link href="/registro" className="cursor-pointer font-medium text-fg underline underline-offset-2">
            Registrate
          </Link>
        </p>
      </form>
    </div>
  );
}

export default function IngresarPage() {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-fg">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-md items-center px-6 py-5">
          <Link
            href="/"
            className="cursor-pointer rounded-sm font-serif text-lg font-semibold tracking-tight text-accent transition-opacity duration-200 hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
          >
            NEXUS
          </Link>
        </div>
      </header>
      <main className="flex-1">
        <Suspense fallback={null}>
          <IngresarForm />
        </Suspense>
      </main>
    </div>
  );
}
