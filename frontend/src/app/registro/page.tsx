"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { UserPlusIcon } from "@phosphor-icons/react/ssr";
import { registrarMedico } from "@/lib/api";
import AuthShell from "@/components/landing/AuthShell";
import {
  FORM_CARD,
  FormError,
  FormField,
  SubmitButton,
} from "@/components/landing/FormPrimitives";
import { FOCUS_RING, TEXT_LINK } from "@/components/landing/styles";

const ERROR_ID = "registro-error";

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
    <AuthShell
      headerLink={{ href: "/ingresar", label: "Ingresar" }}
      icon={<UserPlusIcon aria-hidden="true" weight="bold" className="size-6" />}
      title="Registro de médicos"
      lead="Tu cuenta queda pendiente hasta que un administrador la revise."
    >
      <form onSubmit={handleSubmit} noValidate className={FORM_CARD}>
        <div className="grid gap-6 sm:grid-cols-2">
          <FormField id="nombre" label="Nombre" required value={form.nombre} onChange={setField("nombre")} autoComplete="given-name" />
          <FormField id="apellido" label="Apellido" required value={form.apellido} onChange={setField("apellido")} autoComplete="family-name" />
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          <FormField id="dni" label="DNI" required value={form.dni} onChange={setField("dni")} inputMode="numeric" />
          <FormField
            id="profesion"
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
          <FormField id="matricula" label="Matrícula" required value={form.matricula} onChange={setField("matricula")} />
          <FormField id="jurisdiccion" label="Jurisdicción de matriculación" required value={form.jurisdiccion} onChange={setField("jurisdiccion")} placeholder="Ej: Córdoba" />
        </div>

        <FormField id="email" label="Email institucional" type="email" required value={form.email} onChange={setField("email")} autoComplete="email" />

        <FormField
          id="password"
          label="Contraseña"
          type="password"
          required
          minLength={8}
          value={form.password}
          onChange={setField("password")}
          autoComplete="new-password"
          hint="Mínimo 8 caracteres."
        />

        <label className="flex cursor-pointer items-start gap-3 text-sm text-pretty text-fg-muted">
          <input
            type="checkbox"
            checked={aceptaTratamientoDatos}
            onChange={(e) => setAceptaTratamientoDatos(e.target.checked)}
            className={`mt-0.5 size-4 shrink-0 cursor-pointer rounded accent-accent ${FOCUS_RING}`}
          />
          <span>
            Acepto el tratamiento de mis datos personales (nombre, DNI, matrícula, email y
            contraseña) con la finalidad de verificar mi habilitación profesional y darme
            acceso al pipeline de NEXUS, conforme a la Ley 25.326.
          </span>
        </label>

        {error && <FormError id={ERROR_ID}>{error}</FormError>}

        <SubmitButton pending={enviando} describedBy={error ? ERROR_ID : undefined}>
          {enviando ? "Enviando..." : "Registrarme"}
        </SubmitButton>

        <p className="text-center text-sm text-fg-muted">
          <Link href="/ingresar" className={TEXT_LINK}>
            Ya tengo cuenta — Ingresar
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
