import { useState } from 'react';
import MarkdownContent from '../common/MarkdownContent.jsx';
import SourceCitation from './SourceCitation.jsx';

export default function ChatMessage({ message, isLast, onRetry }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [highlight, setHighlight] = useState(null);
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCitationClick = (number) => {
    setSourcesOpen(true);
    setHighlight(number);
    window.setTimeout(() => {
      document
        .getElementById(`${message.id}-source-${number}`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 60);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content || '');
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  if (isUser) {
    return (
      <div className="msg-row user">
        <span className="avatar">You</span>
        <div className="bubble" style={{ whiteSpace: 'pre-wrap' }}>
          {message.content}
        </div>
      </div>
    );
  }

  const externalSources = message.externalSources || [];
  const hasContent = Boolean(message.content && message.content.trim());

  return (
    <div className="msg-row">
      <span className="avatar">AI</span>
      <div className="bubble flex-fill">
        {hasContent ? (
          <MarkdownContent
            content={message.content}
            citations={message.citations || []}
            onCitationClick={handleCitationClick}
          />
        ) : message.streaming ? (
          <div className="d-flex gap-1 align-items-center py-1">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        ) : null}

        {message.hasQuiz && (
          <div className="alert alert-primary py-1 px-2 small mt-2 mb-1">
            Quiz generated — open the Study tools panel to take it.
          </div>
        )}

        {externalSources.length > 0 && (
          <div className="mt-2 small">
            <div className="section-label mb-1">External sources</div>
            <ul className="mb-0 ps-3">
              {externalSources.map((source) => (
                <li key={source.url}>
                  <a href={source.url} target="_blank" rel="noreferrer noopener">
                    {source.title || source.url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <SourceCitation
          citations={message.citations || []}
          open={sourcesOpen}
          onToggle={() => setSourcesOpen((value) => !value)}
          highlightNumber={highlight}
          idPrefix={message.id}
        />

        <div className="d-flex gap-3 mt-2 align-items-center">
          {hasContent && (
            <button
              type="button"
              className="btn btn-link btn-sm p-0 text-decoration-none"
              style={{ fontSize: '0.74rem' }}
              onClick={handleCopy}
            >
              {copied ? 'Copied' : 'Copy answer'}
            </button>
          )}
          {message.toolName && (
            <span className="text-secondary" style={{ fontSize: '0.72rem' }}>
              Tools: {message.toolName}
            </span>
          )}
          {isLast && !message.streaming && (message.failed || message.stopped) && (
            <button
              type="button"
              className="btn btn-link btn-sm p-0 text-decoration-none"
              style={{ fontSize: '0.74rem' }}
              onClick={onRetry}
            >
              Retry
            </button>
          )}
          {message.stopped && !message.failed && (
            <span className="text-secondary" style={{ fontSize: '0.72rem' }}>
              Stopped
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
