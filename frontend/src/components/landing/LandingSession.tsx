"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { obtenerCuenta } from "@/lib/api";
import type { CuentaEstado } from "@/lib/types";

/**
 * Session of the landing: who, if anyone, is signed in.
 *
 * The provider asks the backend once per mount, so the navigation, the hero
 * and the closing section share a single request. There is no module level
 * cache on purpose: after a logout followed by a client side navigation back
 * to `/` the provider mounts again and asks again, so a stale session is never
 * shown. The account lives in memory only, never in web storage.
 *
 * A failed request and a missing session resolve to `anonymous`, which is also
 * what the server renders and what the page shows without JavaScript. A slow
 * backend does too, after a timeout, so the page is not left waiting; if the
 * account still arrives later it is applied, so a signed in user never stays
 * shown as a visitor.
 */

export interface LandingSessionState {
  status: "loading" | "anonymous" | "authenticated";
  cuenta: CuentaEstado | null;
}

/** Longest the landing waits for the session before showing it as absent. */
const SESSION_TIMEOUT_MS = 4000;

const LOADING: LandingSessionState = { status: "loading", cuenta: null };
const ANONYMOUS: LandingSessionState = { status: "anonymous", cuenta: null };

/** Outside a provider the landing behaves as it does without a session. */
const LandingSessionContext = createContext<LandingSessionState>(ANONYMOUS);

export function LandingSessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<LandingSessionState>(LOADING);

  useEffect(() => {
    let mounted = true;
    // The timeout only stops the wait: it never overrides an answer.
    const timer = setTimeout(() => {
      if (mounted) setSession((current) => (current.status === "loading" ? ANONYMOUS : current));
    }, SESSION_TIMEOUT_MS);

    obtenerCuenta()
      .catch(() => null)
      .then((cuenta) => {
        clearTimeout(timer);
        if (!mounted) return;
        setSession(cuenta ? { status: "authenticated", cuenta } : ANONYMOUS);
      });

    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, []);

  return (
    <LandingSessionContext.Provider value={session}>{children}</LandingSessionContext.Provider>
  );
}

export function useLandingSession(): LandingSessionState {
  return useContext(LandingSessionContext);
}

export interface PrimaryAction {
  label: string;
  href: string;
  /** Whether the licence requirement is stated next to the action. */
  showHint: boolean;
}

/** Licence requirement shown with the action of a visitor without a session. */
export const ACCESS_HINT = "Requiere matrícula médica. Un administrador revisa cada solicitud.";

/**
 * The one primary action of the landing for a given account. Every consumer
 * (navigation pill, mobile menu, hero, closing section) goes through this
 * helper, so they cannot drift apart.
 *
 * An admin is never offered the analysis: the backend only accepts it from a
 * verified physician.
 */
export function primaryActionFor(cuenta: CuentaEstado | null): PrimaryAction {
  if (cuenta === null) {
    return { label: "Solicitar acceso", href: "/registro", showHint: true };
  }
  if (cuenta.rol === "admin") {
    return { label: "Cuentas pendientes", href: "/admin/pendientes", showHint: false };
  }
  if (cuenta.rol === "medico" && cuenta.estado === "verificado") {
    return { label: "Analizar un caso", href: "/analizar", showHint: false };
  }
  return { label: "Ver mi cuenta", href: "/cuenta", showHint: false };
}
