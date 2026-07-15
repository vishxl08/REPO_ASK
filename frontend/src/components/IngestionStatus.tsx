import type { ReactElement } from "react";
import type { IngestResult } from "../api";

interface Props {
  status: "loading" | "success" | "error";
  result?: IngestResult;
  error?: string;
}

const ICONS: Record<string, ReactElement> = {
  files: (
    <path
      fill="currentColor"
      d="M9.5 1.5H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V5l-3.5-3.5Zm0 1.1L11.9 5H9.5V2.6Z"
    />
  ),
  chunks: (
    <path
      fill="currentColor"
      d="M8 1 2 4.2v7.6L8 15l6-3.2V4.2L8 1Zm0 1.7 4 2.15L8 7l-4-2.15L8 2.7ZM3.5 5.9l4 2.15v5.05l-4-2.15V5.9Zm9 0v5.05l-4 2.15V8.05l4-2.15Z"
    />
  ),
  languages: (
    <path
      fill="currentColor"
      d="M2 3.5A1.5 1.5 0 0 1 3.5 2H8v1.5H3.5v9H8V14H3.5A1.5 1.5 0 0 1 2 12.5v-9ZM9.5 2H12.5A1.5 1.5 0 0 1 14 3.5v9a1.5 1.5 0 0 1-1.5 1.5H9.5v-1.5h3v-9h-3V2ZM6.4 5.3 8.2 8l-1.8 2.7h1.6L9 9l1 1.7h1.6L9.8 8l1.8-2.7H10L9 6.9 8 5.3H6.4Z"
    />
  ),
  time: (
    <path
      fill="currentColor"
      d="M8 1.5A6.5 6.5 0 1 0 14.5 8 6.5 6.5 0 0 0 8 1.5Zm0 11.7A5.2 5.2 0 1 1 13.2 8 5.2 5.2 0 0 1 8 13.2ZM8.6 4.6H7.4v3.8l3.1 1.9.6-1-2.5-1.5V4.6Z"
    />
  ),
};

function StatIcon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
      {ICONS[name]}
    </svg>
  );
}

export default function IngestionStatus({ status, result, error }: Props) {
  if (status === "loading") {
    return (
      <div className="ingestion-status ingestion-status--loading">
        <span className="spinner" aria-hidden="true" />
        <span>Ingesting repository… cloning, chunking, and embedding code.</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="ingestion-status ingestion-status--error">
        <span aria-hidden="true">✕</span>
        <span>{error ?? "Ingestion failed."}</span>
      </div>
    );
  }

  if (!result) return null;

  return (
    <div className="ingestion-status ingestion-status--success">
      <div className="ingestion-status__header">
        <span className="ingestion-status__check" aria-hidden="true">
          ✓
        </span>
        <span>Indexed {result.repo_name}</span>
      </div>
      <div className="ingestion-status__stats">
        <div className="stat-card">
          <StatIcon name="files" />
          <div>
            <div className="stat-card__value">{result.total_files}</div>
            <div className="stat-card__label">Files</div>
          </div>
        </div>
        <div className="stat-card">
          <StatIcon name="chunks" />
          <div>
            <div className="stat-card__value">{result.total_chunks}</div>
            <div className="stat-card__label">Chunks</div>
          </div>
        </div>
        <div className="stat-card">
          <StatIcon name="languages" />
          <div>
            <div className="stat-card__value">{result.languages.length || "—"}</div>
            <div className="stat-card__label">{result.languages.length ? result.languages.join(", ") : "Languages"}</div>
          </div>
        </div>
        <div className="stat-card">
          <StatIcon name="time" />
          <div>
            <div className="stat-card__value">{result.time_taken_seconds}s</div>
            <div className="stat-card__label">Time</div>
          </div>
        </div>
      </div>
    </div>
  );
}
