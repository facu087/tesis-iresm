import {
  ProhibitIcon,
  ScalesIcon,
  SealCheckIcon,
  WarningCircleIcon,
  WarningIcon,
} from "@phosphor-icons/react/ssr";
import type { ArbitrationSummary, VerificationSummary } from "@/lib/types";
import { Notice } from "@/components/report/primitives";

/**
 * Aviso de modo mock (control de costos, S4 — D7).
 *
 * Un reporte de modo mock MUST ser distinguible de uno real sin inspeccionar
 * código ni logs (spec `modo-mock-pipeline`): va primero, antes que
 * cualquier otro aviso, porque si el reporte es de modo mock ninguna otra
 * afirmación de la vista es real tampoco.
 *
 * It is the only filled block of the view: the danger ink as the background,
 * so it outweighs every other notice in both themes.
 */
export function MockBanner() {
  return (
    <div className="flex items-start gap-3 rounded-2xl bg-(--landing-danger) p-4 text-sm font-semibold text-pretty text-bg">
      <ProhibitIcon aria-hidden="true" weight="bold" className="mt-0.5 size-5 shrink-0" />
      <p className="min-w-0 flex-1">
        Reporte de modo mock: las hipótesis, el consenso y los ensayos NO provienen de un
        análisis real. Son respuestas grabadas para desarrollo — no corresponden a ningún
        paciente ni deben usarse para ninguna decisión clínica.
      </p>
    </div>
  );
}

/** Disclaimer que trae el propio reporte (`metadata.disclaimer`). */
export function DisclaimerNotice({ text }: { text: string }) {
  return (
    <Notice tone="warning" Icon={WarningIcon}>
      {text}
    </Notice>
  );
}

/**
 * Resumen del arbitraje (Agente 04), con la advertencia de que el consenso es
 * entre agentes de inteligencia artificial.
 */
export function ArbitrationBanner({ a }: { a: ArbitrationSummary }) {
  if (a.status === "sin_hipotesis") return null;

  const degradado = a.status === "degradado";
  const consolido = a.consensus_hypotheses < a.input_hypotheses;
  const r = a.recitation;

  return (
    <Notice
      tone={degradado ? "warning" : "neutral"}
      Icon={degradado ? WarningIcon : ScalesIcon}
      label="Árbitro:"
    >
      {degradado ? (
        <>
          el arbitraje no se pudo completar: las {a.input_hypotheses} hipótesis se
          muestran sin consolidar, como las entregó el debate.
        </>
      ) : (
        <>
          {consolido ? (
            <>
              las {a.input_hypotheses} hipótesis del debate se consolidaron en{" "}
              {a.consensus_hypotheses}.
            </>
          ) : (
            <>las {a.consensus_hypotheses} hipótesis del debate son distintas entre sí.</>
          )}
          {a.contradictions > 0 && (
            <>
              {" "}
              {a.contradictions === 1
                ? "Una objeción quedó sin resolver."
                : `${a.contradictions} objeciones quedaron sin resolver.`}
            </>
          )}
        </>
      )}
      {a.cited_sources > 0 && a.retrieved_articles > 0 && (
        <>
          {" "}
          {a.rag_overlap === 0
            ? `Ninguna de las ${a.cited_sources} referencias citadas salió de los ${a.retrieved_articles} artículos que se les recuperó de PubMed.`
            : `Solo ${a.rag_overlap} de las ${a.cited_sources} referencias citadas salieron de los ${a.retrieved_articles} artículos que se les recuperó de PubMed.`}
        </>
      )}
      {r?.executed && (
        <>
          {" "}Se les pidió volver a citar {r.recited}{" "}
          {r.recited === 1 ? "hipótesis" : "hipótesis"} sobre literatura real:{" "}
          {r.improved === 1 ? "1 consiguió" : `${r.improved} consiguieron`} respaldo
          verificable.
          {r.rejected_pmids > 0 && (
            <> Se descartaron {r.rejected_pmids} referencias que volvieron a inventar.</>
          )}
        </>
      )}
      {/* The AI consensus warning: its own line, in the ink of the body text. */}
      <span className="mt-2 block font-semibold">
        El consenso es entre agentes de inteligencia artificial: no es un diagnóstico
        ni una recomendación clínica.
      </span>
    </Notice>
  );
}

/**
 * Aviso de cabecera con el resultado de la verificación.
 *
 * Sin esto, un lector ve la referencia citada y asume que es buena: la
 * contradicción queda en el dato y no llega a la pantalla.
 */
export function VerificationBanner({ v }: { v: VerificationSummary }) {
  if (!v.total_fuentes) return null;

  const sospechosas = v.discordantes + v.inexistentes;
  const hayProblema = sospechosas > 0;
  const pendientes = v.hipotesis_pendientes ?? 0;
  const topeadas = v.hipotesis_topeadas ?? 0;
  const totalHipotesis = v.hipotesis_respaldadas + pendientes + v.hipotesis_especulativas;

  return (
    <Notice
      tone={hayProblema ? "danger" : "positive"}
      Icon={hayProblema ? WarningCircleIcon : SealCheckIcon}
      label="Verificación bibliográfica:"
    >
      {hayProblema ? (
        <>
          {sospechosas} de {v.total_fuentes} referencias citadas no se pudieron confirmar
          contra PubMed{v.discordantes > 0 && <> ({v.discordantes} apuntan a otro artículo)</>}.
          {" "}{v.hipotesis_especulativas} de {totalHipotesis} hipótesis quedan como especulativas.
        </>
      ) : (
        <>
          {v.verificadas} de {v.total_fuentes} referencias confirmadas contra PubMed.
        </>
      )}
      {v.no_verificables > 0 && (
        <> {v.no_verificables} no se pudieron consultar (fallo de red): no se invalidan.</>
      )}
      {pendientes > 0 && (
        <> {pendientes} de {totalHipotesis} hipótesis quedan pendientes de verificación.</>
      )}
      {topeadas > 0 && (
        <> A {topeadas} hipótesis se les bajó el nivel de evidencia declarado por el agente.</>
      )}
    </Notice>
  );
}
