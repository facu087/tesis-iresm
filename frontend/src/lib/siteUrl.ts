/**
 * Public origin of the deployment, used as `metadataBase` in the root layout
 * so URL based metadata of every route (the generated sharing card of
 * `app/opengraph-image.tsx`, canonical links) resolves to absolute URLs.
 *
 * There is no production domain yet: set NEXT_PUBLIC_SITE_URL when there is
 * one. An empty or malformed value falls back to the local origin instead of
 * throwing while the layout module is evaluated.
 */

const LOCAL_ORIGIN = "http://localhost:3000";

export function resolveSiteUrl(): URL {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (configured) {
    try {
      const url = new URL(configured);
      if (url.protocol === "http:" || url.protocol === "https:") return url;
    } catch {
      // Not an absolute URL: fall through to the local origin.
    }
    console.warn(
      `NEXT_PUBLIC_SITE_URL is not a valid http(s) URL; using ${LOCAL_ORIGIN} for sharing metadata.`,
    );
  }
  return new URL(LOCAL_ORIGIN);
}
