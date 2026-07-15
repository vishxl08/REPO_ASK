import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface IngestResult {
  repo_id: string;
  repo_name: string;
  total_files: number;
  total_chunks: number;
  languages: string[];
  time_taken_seconds: number;
}

export interface Citation {
  file_path: string;
  start_line: number;
  end_line: number;
  language: string;
  symbol_name: string;
  content: string;
}

export interface Timings {
  contextualize_ms?: number;
  rewrite_ms?: number;
  retrieve_ms?: number;
  rerank_ms?: number;
  generate_ms?: number;
  total_ms?: number;
}

export interface QueryResult {
  answer: string;
  citations: Citation[];
  rewritten_queries: string[];
  standalone_question: string;
  timings: Timings;
}

export interface ChatTurn {
  question: string;
  answer: string;
}

export interface SyncResult extends IngestResult {
  files_changed: number;
  files_removed: number;
  files_unchanged: number;
}

export interface Repo {
  repo_id: string;
  name: string;
  source_url: string;
  total_files: number;
  total_chunks: number;
  languages: string[];
  created_at: string;
}

function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (err.message) return err.message;
  }
  return "Something went wrong. Please try again.";
}

export async function ingestUrl(githubUrl: string): Promise<IngestResult> {
  try {
    const res = await axios.post<IngestResult>(`${BASE}/ingest/url`, { github_url: githubUrl });
    return res.data;
  } catch (err) {
    throw new Error(extractErrorMessage(err));
  }
}

export async function ingestZip(file: File): Promise<IngestResult> {
  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await axios.post<IngestResult>(`${BASE}/ingest/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  } catch (err) {
    throw new Error(extractErrorMessage(err));
  }
}

interface StreamCallbacks {
  onToken: (text: string) => void;
  onDone: (data: {
    citations: Citation[];
    rewritten_queries: string[];
    standalone_question: string;
    timings: Timings;
  }) => void;
  onError: (message: string) => void;
}

export async function queryRepoStream(
  question: string,
  repoId: string,
  history: ChatTurn[],
  callbacks: StreamCallbacks
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${BASE}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, repo_id: repoId, history }),
    });
  } catch {
    callbacks.onError("Could not reach the backend. Is it running?");
    return;
  }

  if (!response.ok || !response.body) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (data?.detail) message = data.detail;
    } catch {
      // no JSON body to read the detail from — fall back to the generic message
    }
    callbacks.onError(message);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const line = rawEvent.trim();
      if (!line.startsWith("data:")) continue;
      const jsonStr = line.slice(5).trim();
      if (!jsonStr) continue;

      const parsed = JSON.parse(jsonStr);
      if (parsed.type === "token") {
        callbacks.onToken(parsed.text);
      } else if (parsed.type === "done") {
        callbacks.onDone(parsed);
      } else if (parsed.type === "error") {
        callbacks.onError(parsed.message);
      }
    }
  }
}

export async function listRepos(): Promise<Repo[]> {
  try {
    const res = await axios.get<Repo[]>(`${BASE}/repos`);
    return res.data;
  } catch (err) {
    throw new Error(extractErrorMessage(err));
  }
}

export async function deleteRepo(repoId: string): Promise<void> {
  try {
    await axios.delete(`${BASE}/repos/${repoId}`);
  } catch (err) {
    throw new Error(extractErrorMessage(err));
  }
}

export async function syncRepo(repoId: string): Promise<SyncResult> {
  try {
    const res = await axios.post<SyncResult>(`${BASE}/repos/${repoId}/sync`);
    return res.data;
  } catch (err) {
    throw new Error(extractErrorMessage(err));
  }
}
