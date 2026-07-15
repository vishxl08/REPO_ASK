import { useEffect, useRef, useState } from "react";
import "./App.css";
import { deleteRepo, listRepos, syncRepo } from "./api";
import type { IngestResult, Repo } from "./api";
import RepoInput from "./components/RepoInput";
import ChatBox from "./components/ChatBox";
import Toast from "./components/Toast";
import type { ToastMessage } from "./components/Toast";

export default function App() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const nextToastId = useRef(0);

  useEffect(() => {
    refreshRepos();
  }, []);

  function addToast(text: string, variant: ToastMessage["variant"] = "success") {
    const id = nextToastId.current++;
    setToasts((prev) => [...prev, { id, text, variant }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3500);
  }

  async function refreshRepos() {
    try {
      const list = await listRepos();
      setRepos(list);
    } catch {
      // repo list is a convenience, not fatal if the backend isn't reachable yet
    }
  }

  function handleIngested(result: IngestResult) {
    setSelectedRepoId(result.repo_id);
    refreshRepos();
    addToast(`Indexed ${result.repo_name} — ${result.total_chunks} chunks ready to query.`);
  }

  async function handleDelete() {
    if (!selectedRepoId) return;
    const repo = repos.find((r) => r.repo_id === selectedRepoId);
    if (!window.confirm(`Delete "${repo?.name ?? selectedRepoId}" from the index?`)) return;

    try {
      await deleteRepo(selectedRepoId);
      addToast(`Deleted ${repo?.name ?? selectedRepoId}.`);
      setSelectedRepoId(null);
      refreshRepos();
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Delete failed.", "error");
    }
  }

  async function handleSync() {
    if (!selectedRepoId) return;
    setSyncing(true);
    try {
      const result = await syncRepo(selectedRepoId);
      addToast(
        `Synced: ${result.files_changed} changed, ${result.files_removed} removed, ${result.files_unchanged} unchanged.`
      );
      refreshRepos();
    } catch (err) {
      addToast(err instanceof Error ? err.message : "Sync failed.", "error");
    } finally {
      setSyncing(false);
    }
  }

  const selectedRepo = repos.find((r) => r.repo_id === selectedRepoId);

  return (
    <div className="app">
      <Toast toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))} />

      <header className="app__header">
        <div className="app__brand">
          <svg className="app__logo" viewBox="0 0 40 40" width="36" height="36" aria-hidden="true">
            <defs>
              <linearGradient id="logoGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="var(--accent)" />
                <stop offset="100%" stopColor="var(--accent-2)" />
              </linearGradient>
            </defs>
            <rect width="40" height="40" rx="11" fill="url(#logoGrad)" />
            <path
              d="M13 15.5 8.5 20l4.5 4.5M27 15.5l4.5 4.5-4.5 4.5M22.5 12.5l-5 15"
              fill="none"
              stroke="white"
              strokeWidth="2.1"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <div>
            <h1>RepoMind</h1>
            <p>Chat with any codebase in natural language.</p>
          </div>
        </div>
        {repos.length > 0 && <span className="app__repo-count">{repos.length} repo{repos.length === 1 ? "" : "s"} indexed</span>}
      </header>

      <RepoInput onIngested={handleIngested} />

      {repos.length > 0 && (
        <div className="repo-selector">
          <label htmlFor="repo-select">Repo</label>
          <select
            id="repo-select"
            value={selectedRepoId ?? ""}
            onChange={(e) => setSelectedRepoId(e.target.value || null)}
          >
            <option value="">Select a previously ingested repo…</option>
            {repos.map((repo) => (
              <option key={repo.repo_id} value={repo.repo_id}>
                {repo.name} ({repo.total_chunks} chunks)
              </option>
            ))}
          </select>
          {selectedRepoId && selectedRepo?.source_url && (
            <button type="button" className="icon-btn icon-btn--accent" onClick={handleSync} disabled={syncing}>
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" className={syncing ? "spin" : ""}>
                <path
                  fill="currentColor"
                  d="M13.5 8a5.5 5.5 0 0 1-9.6 3.6L2 13.5V9h4.5l-1.8 1.8A4 4 0 0 0 12 8h1.5ZM2.5 8a5.5 5.5 0 0 1 9.6-3.6L14 2.5V7H9.5l1.8-1.8A4 4 0 0 0 4 8H2.5Z"
                />
              </svg>
              {syncing ? "Syncing…" : "Sync"}
            </button>
          )}
          {selectedRepoId && (
            <button type="button" className="icon-btn icon-btn--danger" onClick={handleDelete}>
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <path
                  fill="currentColor"
                  d="M6 2h4a1 1 0 0 1 1 1v1h3v1.5H2V4h3V3a1 1 0 0 1 1-1Zm-1.5 4h7l-.6 8.1a1 1 0 0 1-1 .9H6.1a1 1 0 0 1-1-.9L4.5 6Z"
                />
              </svg>
              Delete
            </button>
          )}
        </div>
      )}

      <ChatBox repoId={selectedRepoId} />
    </div>
  );
}
