import { AlertIcon, CheckIcon, ClockIcon, VerifiedIcon } from "@/components/icons";

/**
 * Vista del reporte de NEXUS a todo el ancho (variante /v2).
 *
 * Muestra lo que tiene el reporte real: hipótesis de consenso con nivel de
 * evidencia y estado (respaldada, pendiente, especulativa), los agentes que
 * las sostienen, sus fuentes con el estado de verificación y un ensayo
 * clínico con compatibilidad orientativa. Todo es texto real, no una imagen:
 * los lectores de pantalla lo leen completo. Las hipótesis son un ejemplo
 * ilustrativo; el PMID 22439958 es el que ya usan los tests del proyecto y
 * el ensayo es un registro público que apareció en una corrida real.
 */

const badge =
  "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-bold";

function Level({ level }: { level: "II" | "III" }) {
  return (
    <span
      className={`rounded-md px-2.5 py-1 text-xs font-bold ${
        level === "II"
          ? "bg-accent text-accent-fg"
          : "border border-fg-muted text-fg-muted"
      }`}
    >
      Nivel {level}
    </span>
  );
}

export default function ReportDemo() {
  return (
    <figure
      aria-labelledby="reportdemo-caption"
      className="m-0 overflow-hidden rounded-lg border border-border bg-surface"
    >
      {/* Barra del reporte */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-bg-subtle px-5 py-3 sm:px-7">
        <div className="flex items-center gap-3">
          <span className="font-serif text-lg font-semibold text-accent">
            Reporte de análisis
          </span>
          <span className="rounded-full border border-ochre px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-widest text-ochre">
            Ejemplo ilustrativo
          </span>
        </div>
        <p className="text-sm text-fg-muted">
          Hipótesis: <strong className="text-fg">3</strong> · Ensayos:{" "}
          <strong className="text-fg">1</strong> · Fuentes verificadas:{" "}
          <strong className="text-fg">1 de 1</strong>
        </p>
      </div>

      <div className="grid lg:grid-cols-12">
        {/* Hipótesis */}
        <div className="divide-y divide-border lg:col-span-7">
          <p className="px-5 pt-5 text-xs font-bold uppercase tracking-widest text-fg-muted sm:px-7">
            Hipótesis de investigación · no son diagnósticos
          </p>

          <article className="px-5 py-6 sm:px-7">
            <p className="font-serif text-2xl text-fg-muted">H1</p>
            <p className="mt-1 font-serif text-xl leading-snug text-balance sm:text-2xl">
              El déficit de vitamina B12 asociado al uso crónico de metformina
              podría contribuir a la neuropatía axonal sensitivomotora del
              paciente.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Level level="II" />
              <span className={`${badge} border-accent text-accent`}>
                <CheckIcon className="h-4 w-4" />
                Respaldada
              </span>
            </div>
            <div className="mt-4 rounded-md bg-bg-subtle px-4 py-3">
              <p className="text-sm font-bold">
                Metformin-associated vitamin B12 deficiency
              </p>
              <p className="mt-0.5 text-sm text-fg-muted">PMID 22439958</p>
              <p className="mt-2 inline-flex items-center gap-1.5 text-sm font-bold text-accent">
                <VerifiedIcon className="h-4 w-4" />
                Título verificado contra PubMed
              </p>
            </div>
            <p className="mt-4 text-sm text-fg-muted">
              <strong className="text-fg">Sostenida por:</strong> Agente 01 ·
              Analista de Literatura, Agente 03 · Consultor Clínico
            </p>
          </article>

          <article className="px-5 py-5 sm:px-7">
            <p className="font-serif text-xl text-fg-muted">H2</p>
            <p className="mt-1 font-serif text-lg leading-snug">
              Posible neuropatía asociada a deficiencia de cobre.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Level level="II" />
              <span className={`${badge} border-ochre text-ochre`}>
                <ClockIcon className="h-4 w-4" />
                Pendiente
              </span>
            </div>
            <p className="mt-3 text-sm text-fg-muted">
              La cita no pudo verificarse: PubMed no respondió. Se mantiene
              hasta poder contrastarla.
            </p>
          </article>

          <article className="px-5 py-5 sm:px-7">
            <p className="font-serif text-xl text-fg-muted">H3</p>
            <p className="mt-1 font-serif text-lg leading-snug">
              Origen autoinmune de la neuropatía.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Level level="III" />
              <span className={`${badge} border-dashed border-fg-muted text-fg-muted`}>
                <AlertIcon className="h-4 w-4" />
                Especulativa
              </span>
            </div>
            <p className="mt-3 text-sm text-fg-muted">
              Sin referencia verificable: se conserva, con el nivel de
              evidencia más bajo.
            </p>
          </article>
        </div>

        {/* Ensayo y lectura de estados */}
        <aside className="divide-y divide-border border-t border-border lg:col-span-5 lg:border-t-0 lg:border-l">
          <div className="px-5 py-6 sm:px-7">
            <p className="text-xs font-bold uppercase tracking-widest text-fg-muted">
              Ensayo clínico compatible
            </p>
            <p className="mt-3 font-serif text-lg leading-snug">
              Natural History Study for Charcot Marie Tooth Disease
            </p>
            <p className="mt-1 text-sm text-fg-muted">
              NCT05902351 · Reclutando · ClinicalTrials.gov
            </p>
            <p className="mt-3 inline-flex rounded-md border border-accent px-2.5 py-1 text-xs font-bold text-accent">
              Compatibilidad orientativa: alta
            </p>
            <p className="mt-3 text-sm text-fg-muted">
              A verificar por el médico: diagnóstico clínico o sospecha de
              neuropatía hereditaria; consentimiento informado.
            </p>
          </div>

          <div className="px-5 py-6 sm:px-7">
            <p className="text-xs font-bold uppercase tracking-widest text-fg-muted">
              Cómo leer los estados
            </p>
            <dl className="mt-3 space-y-3 text-sm">
              <div>
                <dt className="font-bold text-accent">Respaldada</dt>
                <dd className="text-fg-muted">
                  Al menos una fuente cuyo título coincide con PubMed.
                </dd>
              </div>
              <div>
                <dt className="font-bold text-ochre">Pendiente</dt>
                <dd className="text-fg-muted">
                  No se pudo verificar todavía.
                </dd>
              </div>
              <div>
                <dt className="font-bold text-fg-muted">Especulativa</dt>
                <dd className="text-fg-muted">
                  Sin fuente verificable; nunca supera el nivel III.
                </dd>
              </div>
            </dl>
          </div>
        </aside>
      </div>

      <figcaption
        id="reportdemo-caption"
        className="border-t border-border bg-bg-subtle px-5 py-3 text-xs text-fg-muted sm:px-7"
      >
        Ejemplo ilustrativo: las hipótesis y su contenido son inventados para
        mostrar cómo se presenta el reporte. El registro del ensayo es un
        registro público de ClinicalTrials.gov.
      </figcaption>
    </figure>
  );
}
