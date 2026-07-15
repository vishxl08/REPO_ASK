import { useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent } from "react";
import { ingestUrl, ingestZip } from "../api";
import type { IngestResult } from "../api";
import IngestionStatus from "./IngestionStatus";

interface Props {
  onIngested: (result: IngestResult) => void;
}

type Status = "idle" | "loading" | "success" | "error";

export default function RepoInput({ onIngested }: Props) {
  const [githubUrl, setGithubUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<IngestResult | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const [dragActive, setDragActive] = useState(false);

  const canSubmit = (githubUrl.trim() !== "" || file !== null) && status !== "loading";

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setFile(e.target.files?.[0] ?? null);
  }

  function handleDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped && dropped.name.endsWith(".zip")) {
      setFile(dropped);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setStatus("loading");
    setError(undefined);
    setResult(undefined);

    try {
      const ingestResult = file ? await ingestZip(file) : await ingestUrl(githubUrl.trim());
      setResult(ingestResult);
      setStatus("success");
      onIngested(ingestResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingestion failed.");
      setStatus("error");
    }
  }

  return (
    <div className="repo-input">
      <form onSubmit={handleSubmit} className="repo-input__form">
        <div className="repo-input__field">
          <svg className="repo-input__field-icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
            <path
              fill="currentColor"
              d="M8 0a8 8 0 0 0-2.53 15.59c.4.07.55-.17.55-.38v-1.5c-2.23.48-2.7-1.07-2.7-1.07-.36-.93-.89-1.17-.89-1.17-.72-.5.06-.49.06-.49.8.06 1.22.82 1.22.82.71 1.22 1.86.87 2.32.66.07-.52.28-.87.5-1.07-1.78-.2-3.65-.89-3.65-3.96 0-.88.31-1.59.83-2.15-.08-.2-.36-1.02.08-2.13 0 0 .68-.22 2.2.83a7.6 7.6 0 0 1 4 0c1.52-1.05 2.2-.83 2.2-.83.44 1.11.16 1.93.08 2.13.52.56.83 1.27.83 2.15 0 3.08-1.88 3.76-3.66 3.96.29.25.54.73.54 1.48v2.2c0 .21.15.46.55.38A8 8 0 0 0 8 0Z"
            />
          </svg>
          <input
            type="text"
            placeholder="https://github.com/owner/repo"
            value={githubUrl}
            disabled={status === "loading" || file !== null}
            onChange={(e) => setGithubUrl(e.target.value)}
          />
        </div>

        <div className="repo-input__divider">
          <span>or</span>
        </div>

        <label
          className={`repo-input__upload${dragActive ? " repo-input__upload--active" : ""}${file ? " repo-input__upload--filled" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
        >
          <input
            type="file"
            accept=".zip"
            disabled={status === "loading" || githubUrl.trim() !== ""}
            onChange={handleFileChange}
          />
          <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
            <path
              fill="currentColor"
              d="M8 1.5a.75.75 0 0 1 .75.75v6.19l1.72-1.72a.75.75 0 1 1 1.06 1.06l-3 3a.75.75 0 0 1-1.06 0l-3-3a.75.75 0 1 1 1.06-1.06l1.72 1.72V2.25A.75.75 0 0 1 8 1.5ZM2.5 10.5a.75.75 0 0 1 .75.75v1.5c0 .41.34.75.75.75h8a.75.75 0 0 0 .75-.75v-1.5a.75.75 0 0 1 1.5 0v1.5A2.25 2.25 0 0 1 12 15H4a2.25 2.25 0 0 1-2.25-2.25v-1.5a.75.75 0 0 1 .75-.75Z"
            />
          </svg>
          <span>{file ? file.name : "Drop a .zip or click to upload"}</span>
        </label>

        <button type="submit" disabled={!canSubmit}>
          {status === "loading" ? (
            <>
              <span className="btn-spinner" aria-hidden="true" />
              Ingesting…
            </>
          ) : (
            "Ingest"
          )}
        </button>
      </form>

      {status !== "idle" && <IngestionStatus status={status} result={result} error={error} />}
    </div>
  );
}
