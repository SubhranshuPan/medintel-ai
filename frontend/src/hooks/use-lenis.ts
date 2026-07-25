import { useEffect, useRef } from "react";
import Lenis from "lenis";

/**
 * Initialise Lenis smooth-scroll for the given wrapper element.
 *
 * Uses `autoRaf: true` so Lenis manages its own requestAnimationFrame loop —
 * no manual RAF dance needed.  Returns the instance ref so callers can
 * imperatively scroll-to if needed (e.g. scroll-to-top on route change).
 */
export function useLenis(wrapperRef: React.RefObject<HTMLElement | null>) {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const lenis = new Lenis({
      wrapper,
      content: wrapper,
      autoRaf: true,
      lerp: 0.1,         // smooth interpolation factor
      duration: 1.2,      // scroll momentum duration (seconds)
      smoothWheel: true,
    });
    lenisRef.current = lenis;

    return () => {
      lenis.destroy();
      lenisRef.current = null;
    };
  }, [wrapperRef]);

  return lenisRef;
}
