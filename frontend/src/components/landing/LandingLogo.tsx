import { NexusMark } from "@/components/NexusLogo";

/**
 * Brand lockup for the landing pill and the 404: mark plus wordmark.
 *
 * The shared mark fades from `--color-accent` to `--color-brand-line`. Inside
 * the landing that second token is a border grey in the dark theme, which
 * makes half of the mark disappear, so `.landing-logo` rebinds it (see
 * `globals.css`) instead of changing the shared component.
 */
export default function LandingLogo() {
  return (
    <span className="landing-logo inline-flex items-center gap-2">
      <NexusMark className="h-8 w-auto" />
      <span>NEXUS</span>
    </span>
  );
}
