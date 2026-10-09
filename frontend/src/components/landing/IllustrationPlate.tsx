import Image from "next/image";

/**
 * Rounded plate for the landing illustrations.
 *
 * The images are AI generated illustrations on a solid navy background, so a
 * framed plate reads the same in the light and the dark theme. They are never
 * presented as captures of the system: the caption says what they are.
 *
 * Nested radius: outer 24 px (`rounded-3xl`) minus the 8 px gap gives the
 * image 16 px (`rounded-2xl`).
 */

interface IllustrationPlateProps {
  src: string;
  alt: string;
  width: number;
  height: number;
  /** Responsive `sizes` hint for the image. */
  sizes: string;
  /** Load eagerly with high priority: only for the hero illustration. */
  eager?: boolean;
  className?: string;
}

export default function IllustrationPlate({
  src,
  alt,
  width,
  height,
  sizes,
  eager = false,
  className = "",
}: IllustrationPlateProps) {
  return (
    <figure className={`m-0 rounded-3xl border border-border bg-surface p-2 ${className}`}>
      <Image
        src={src}
        alt={alt}
        width={width}
        height={height}
        sizes={sizes}
        loading={eager ? "eager" : "lazy"}
        fetchPriority={eager ? "high" : "auto"}
        className="h-auto w-full rounded-2xl"
      />
      <figcaption className="px-2 pt-3 pb-1 text-xs text-fg-muted">
        Ilustración generada con IA. No es una captura del sistema.
      </figcaption>
    </figure>
  );
}
