import { ImageResponse } from "next/og";
import { HERO_HEADLINE_LINES, SCOPE_NOTICE } from "@/components/landing/copy";

/**
 * Sharing image of NEXUS, generated from text: the wordmark, the hero
 * headline and an ochre rule on the navy brand colour. It replaces the static
 * illustration and stays in sync with the page through the shared copy.
 *
 * Statically generated at build time (no request time API is used). Rendered
 * with the default font of `next/og`: only flexbox layouts are supported.
 */

export const alt =
  "NEXUS: hipótesis de investigación con cada cita contrastada contra PubMed.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const NAVY = "#1e3a5f";
const OCHRE = "#e3b25a";
const INK = "#ffffff";
const INK_MUTED = "#c5d3e6";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 80,
          backgroundColor: NAVY,
          color: INK,
        }}
      >
        <div style={{ display: "flex", fontSize: 40, fontWeight: 700, letterSpacing: 4 }}>
          NEXUS
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", width: 96, height: 8, backgroundColor: OCHRE }} />
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              marginTop: 40,
              fontSize: 72,
              fontWeight: 700,
              lineHeight: 1.1,
            }}
          >
            {HERO_HEADLINE_LINES.map((line) => (
              <div key={line} style={{ display: "flex" }}>
                {line}
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", fontSize: 28, color: INK_MUTED }}>{SCOPE_NOTICE}</div>
      </div>
    ),
    size,
  );
}
