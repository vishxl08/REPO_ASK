import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import type { Citation, Timings } from "../api";
import CodeBlock from "./CodeBlock";
import PipelineTrace from "./PipelineTrace";

interface Props {
  question: string;
  answer?: string;
  citations?: Citation[];
  timings?: Timings;
  loading?: boolean;
  streaming?: boolean;
  error?: string;
}

const markdownComponents: Components = {
  pre({ children }) {
    return <>{children}</>;
  },
  code({ className, children, ...rest }) {
    const match = /language-(\w+)/.exec(className ?? "");
    const text = String(children).replace(/\n$/, "");
    if (match) {
      return <CodeBlock code={text} language={match[1]} />;
    }
    return (
      <code className="markdown-inline-code" {...rest}>
        {children}
      </code>
    );
  },
};

export default function AnswerCard({ question, answer, citations, timings, loading, streaming, error }: Props) {
  return (
    <div className="answer-card">
      <div className="answer-card__row answer-card__row--question">
        <span className="avatar avatar--user" aria-hidden="true">
          Q
        </span>
        <div className="answer-card__question">{question}</div>
      </div>

      <div className="answer-card__row answer-card__row--answer">
        <span className="avatar avatar--assistant" aria-hidden="true">
          ✦
        </span>
        <div className="answer-card__body">
          {loading && (
            <div className="answer-card__loading">
              <span className="dot-pulse" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
              <span>Rewriting query, retrieving code, reranking…</span>
            </div>
          )}

          {error && <div className="answer-card__error">{error}</div>}

          {answer && (
            <div className="answer-card__answer markdown">
              <ReactMarkdown components={markdownComponents}>{answer}</ReactMarkdown>
              {streaming && <span className="stream-cursor" aria-hidden="true" />}
            </div>
          )}

          {citations && citations.length > 0 && (
            <div className="answer-card__citations">
              {citations.map((c, i) => (
                <details key={i} className="citation">
                  <summary>
                    <svg className="citation__file-icon" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                      <path
                        fill="currentColor"
                        d="M9.5 1.5H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V5l-3.5-3.5Z"
                        opacity="0.15"
                      />
                      <path
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.1"
                        d="M9.5 1.5H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V5l-3.5-3.5Z"
                      />
                      <path fill="none" stroke="currentColor" strokeWidth="1.1" d="M9.3 1.5V5h3.5" />
                    </svg>
                    <span className="citation__path">{c.file_path}</span>
                    <span className="citation__lines">
                      lines {c.start_line}-{c.end_line}
                    </span>
                    {c.symbol_name && <span className="citation__symbol">{c.symbol_name}</span>}
                  </summary>
                  <CodeBlock code={c.content} language={c.language} />
                </details>
              ))}
            </div>
          )}

          {timings && <PipelineTrace timings={timings} />}
        </div>
      </div>
    </div>
  );
}
