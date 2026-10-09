"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LockIcon } from "@phosphor-icons/react/ssr";
import { login } from "@/lib/api";
import AuthShell from "@/components/landing/AuthShell";
import {
  FORM_CARD,
  FormError,
  FormField,
  SubmitButton,
} from "@/components/landing/FormPrimitives";
import { TEXT_LINK } from "@/components/landing/styles";

const ERROR_ID = "ingresar-error";

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
    <div className="flex max-w-md flex-col gap-6">
      {recienRegistrado && (
        <p className="rounded-2xl border border-border bg-bg-subtle p-4 text-sm text-pretty text-fg-muted">
          Tu cuenta fue creada y quedó <strong className="font-semibold text-fg">pendiente de revisión</strong>.
          Iniciá sesión para ver su estado.
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate className={FORM_CARD}>
        <FormField
          id="email"
          label="Email institucional"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
        />

        <FormField
          id="password"
          label="Contraseña"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />

        {error && <FormError id={ERROR_ID}>{error}</FormError>}

        <SubmitButton pending={enviando} describedBy={error ? ERROR_ID : undefined}>
          {enviando ? "Ingresando..." : "Ingresar"}
        </SubmitButton>

        <p className="text-center text-sm text-fg-muted">
          ¿No tenés cuenta?{" "}
          <Link href="/registro" className={TEXT_LINK}>
            Registrate
          </Link>
        </p>
      </form>
    </div>
  );
}

export default function IngresarPage() {
  return (
    <AuthShell
      headerLink={{ href: "/registro", label: "Solicitar acceso" }}
      icon={<LockIcon aria-hidden="true" weight="bold" className="size-6" />}
      title="Ingresar"
    >
      <Suspense fallback={null}>
        <IngresarForm />
      </Suspense>
    </AuthShell>
  );
}
