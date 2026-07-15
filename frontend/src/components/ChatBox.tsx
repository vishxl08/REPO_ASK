import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { queryRepoStream } from "../api";
import type { ChatTurn, Citation, Timings } from "../api";
import AnswerCard from "./AnswerCard";

interface QAEntry {
  id: number;
  question: string;
  answer: string;
  citations?: Citation[];
  timings?: Timings;
  loading: boolean;
  streaming: boolean;
  error?: string;
}

interface Props {
  repoId: string | null;
}

const MAX_HISTORY_TURNS = 4;

const EXAMPLE_QUESTIONS = [
  "How does authentication work?",
  "What are the main entry points?",
  "Where is the database configured?",
  "What does the main class do?",
];

export default function ChatBox({ repoId }: Props) {
  const [question, setQuestion] = useState("");
  const [entries, setEntries] = useState<QAEntry[]>([]);
  const nextId = useRef(0);

  // conversation history is scoped to one repo — don't carry it across a repo switch
  useEffect(() => {
    setEntries([]);
  }, [repoId]);

  function updateEntry(id: number, patch: Partial<QAEntry> | ((entry: QAEntry) => Partial<QAEntry>)) {
    setEntries((prev) =>
      prev.map((entry) => (entry.id === id ? { ...entry, ...(typeof patch === "function" ? patch(entry) : patch) } : entry))
    );
  }

  async function submitQuestion(text: string) {
    const trimmed = text.trim();
    if (!trimmed || !repoId) return;

    const history: ChatTurn[] = entries
      .filter((entry) => entry.answer && !entry.error)
      .slice(-MAX_HISTORY_TURNS)
      .map((entry) => ({ question: entry.question, answer: entry.answer }));

    const id = nextId.current++;
    setEntries((prev) => [...prev, { id, question: trimmed, answer: "", loading: true, streaming: false }]);
    setQuestion("");

    await queryRepoStream(trimmed, repoId, history, {
      onToken: (token) => {
        updateEntry(id, (entry) => ({ loading: false, streaming: true, answer: entry.answer + token }));
      },
      onDone: ({ citations, timings }) => {
        updateEntry(id, { loading: false, streaming: false, citations, timings });
      },
      onError: (message) => {
        updateEntry(id, { loading: false, streaming: false, error: message });
      },
    });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    submitQuestion(question);
  }

  return (
    <div className="chat-box">
      <div className="chat-box__history">
        {entries.length === 0 && repoId && (
          <div className="chat-box__welcome">
            <p className="chat-box__empty">Ask a question about this repo, or try an example:</p>
            <div className="chat-box__chips">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button key={q} type="button" className="chip" onClick={() => submitQuestion(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {entries.length === 0 && !repoId && (
          <div className="chat-box__welcome">
            <p className="chat-box__empty">Ingest a repo above to start chatting.</p>
          </div>
        )}
        {entries.map((entry) => (
          <AnswerCard
            key={entry.id}
            question={entry.question}
            answer={entry.answer}
            citations={entry.citations}
            timings={entry.timings}
            loading={entry.loading}
            streaming={entry.streaming}
            error={entry.error}
          />
        ))}
      </div>

      <form onSubmit={handleSubmit} className="chat-box__form">
        <input
          type="text"
          placeholder="How does authentication work?"
          value={question}
          disabled={!repoId}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" disabled={!repoId || !question.trim()}>
          <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
            <path fill="currentColor" d="M1.5 8 14 2l-3.6 12-3-5.4L1.5 8Zm5.9 1 2 3.6L12.4 4 3.9 8l3.5.9Z" />
          </svg>
          Ask
        </button>
      </form>
    </div>
  );
}
