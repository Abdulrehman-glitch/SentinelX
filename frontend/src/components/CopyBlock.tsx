import { useState } from "react";

type CopyBlockProps = {
  title: string;
  value: string;
};

export function CopyBlock({ title, value }: CopyBlockProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);

    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <section className="rounded-2xl border border-white/[0.056] bg-black/30 p-4">
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-sm font-bold text-slate-100">{title}</h3>

        <button
          type="button"
          onClick={handleCopy}
          className="sx-button-secondary rounded-lg px-3 py-2 text-xs font-semibold"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <pre className="mt-3 overflow-x-auto rounded-xl border border-white/[0.056] bg-black/40 p-4 font-mono text-xs leading-6 text-amber-100">
        {value}
      </pre>
    </section>
  );
}