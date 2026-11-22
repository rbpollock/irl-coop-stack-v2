"use client";

import { useEffect, useId, useRef, useState } from "react";

/**
 * Mermaid — client-side diagram renderer.
 *
 * Wired into the docs renderer at /docs/design/[slug] via a custom react-markdown
 * `code` component. Mermaid is dynamically imported so the ~700 KB bundle is only
 * fetched on a docs page that actually has a mermaid block; pages without diagrams
 * pay nothing.
 *
 * SSR: the component renders an empty `<div>` during server pass; the SVG is drawn
 * after hydration on the client. That's the Option 1 trade — simple, robust, with a
 * brief placeholder before the diagram appears.
 */
export function Mermaid({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  // Stable id per instance for mermaid's render() call (it mutates a global counter
  // unless you supply your own).
  const renderId = useId().replace(/:/g, "_");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "default",
          fontFamily: "inherit",
        });
        const { svg } = await mermaid.render(renderId, chart);
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart, renderId]);

  if (error) {
    return (
      <pre className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive overflow-auto">
        {`mermaid render error: ${error}\n\n${chart}`}
      </pre>
    );
  }
  return (
    <div
      ref={ref}
      className="mermaid my-6 flex justify-center [&_svg]:max-w-full [&_svg]:h-auto"
    />
  );
}
