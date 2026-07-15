import type { Timings } from "../api";

interface Props {
  timings: Timings;
}

const STAGE_ORDER = ["contextualize_ms", "rewrite_ms", "retrieve_ms", "rerank_ms", "generate_ms"] as const;

const STAGE_META: Record<(typeof STAGE_ORDER)[number], { label: string; color: string }> = {
  contextualize_ms: { label: "Contextualize", color: "#8b5cf6" },
  rewrite_ms: { label: "Rewrite query", color: "#6366f1" },
  retrieve_ms: { label: "Retrieve", color: "#0ea5e9" },
  rerank_ms: { label: "Rerank", color: "#14b8a6" },
  generate_ms: { label: "Generate", color: "#f59e0b" },
};

export default function PipelineTrace({ timings }: Props) {
  const stages = STAGE_ORDER.filter((key) => typeof timings[key] === "number" && timings[key]! > 0).map((key) => ({
    key,
    ms: timings[key] as number,
    ...STAGE_META[key],
  }));

  const total = timings.total_ms ?? stages.reduce((sum, s) => sum + s.ms, 0);
  if (stages.length === 0 || total <= 0) return null;

  return (
    <details className="pipeline-trace">
      <summary>
        <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
          <path
            fill="currentColor"
            d="M8 1.5A6.5 6.5 0 1 0 14.5 8 6.5 6.5 0 0 0 8 1.5Zm.6 3.1v3.8l3.1 1.9-.6 1L7 9.4V4.6h1.6Z"
          />
        </svg>
        <span>Pipeline trace</span>
        <span className="pipeline-trace__total">{(total / 1000).toFixed(2)}s</span>
      </summary>
      <div className="pipeline-trace__bar">
        {stages.map((s) => (
          <div
            key={s.key}
            className="pipeline-trace__seg"
            style={{ width: `${(s.ms / total) * 100}%`, backgroundColor: s.color }}
            title={`${s.label}: ${s.ms}ms`}
          />
        ))}
      </div>
      <ul className="pipeline-trace__list">
        {stages.map((s) => (
          <li key={s.key}>
            <span className="pipeline-trace__dot" style={{ backgroundColor: s.color }} aria-hidden="true" />
            <span className="pipeline-trace__label">{s.label}</span>
            <span className="pipeline-trace__ms">{s.ms}ms</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
