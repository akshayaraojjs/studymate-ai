import { useEffect, useRef } from 'react';
import ChatMessage from './ChatMessage.jsx';

const SUGGESTIONS = [
  'Explain the main concept in my uploaded notes.',
  'Create five questions on the first chapter.',
  'Summarize Chapter 1.',
  'Calculate the accuracy if 85 of 100 predictions are correct.',
];

export default function ChatWindow({
  messages,
  streaming,
  activity,
  error,
  hasDocuments,
  onSuggestion,
  onRetry,
}) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, streaming, activity]);

  return (
    <div className="chat-scroll">
      <div className="chat-inner">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div
              className="brand-mark mx-auto mb-3"
              style={{ width: 46, height: 46, fontSize: '1.05rem' }}
            >
              SM
            </div>
            <h2 className="fs-5 fw-bold mb-2">
              {hasDocuments ? 'Ask about your study material' : 'Upload a document to begin'}
            </h2>
            <p className="text-secondary small mb-4">
              {hasDocuments
                ? 'Answers cite the page they came from. Ask a question, request a quiz, or ask for a chapter summary.'
                : 'Add a PDF or TXT file in the sidebar. Once it is processed you can ask questions grounded in it, with page-level citations.'}
            </p>
            {hasDocuments && (
              <div className="d-flex flex-column gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="suggestion-chip"
                    onClick={() => onSuggestion(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((message, index) => (
          <ChatMessage
            key={message.id}
            message={message}
            isLast={index === messages.length - 1}
            onRetry={onRetry}
          />
        ))}

        {activity && (
          <div className="activity-pill">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
            {activity.label}
          </div>
        )}

        {error && (
          <div className="alert alert-warning py-2 small mb-0" role="alert">
            {error}
          </div>
        )}

        <div ref={endRef} />
      </div>
    </div>
  );
}
