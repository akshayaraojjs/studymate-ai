import { useEffect, useRef, useState } from 'react';

export default function ChatInput({ onSend, onStop, streaming, disabled }) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || streaming || disabled) return;
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="composer">
      <div className="composer-inner">
        <textarea
          ref={textareaRef}
          className="form-control flex-fill"
          rows={1}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            disabled
              ? 'Upload and process a document first…'
              : 'Ask about your documents, request a quiz, or summarise a chapter…'
          }
          maxLength={4000}
          aria-label="Chat message"
        />
        {streaming ? (
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onStop}>
            Stop
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-sm btn-primary"
            onClick={submit}
            disabled={disabled || !value.trim()}
          >
            Send
          </button>
        )}
      </div>
      <div className="text-center text-secondary mt-2" style={{ fontSize: '0.68rem' }}>
        Enter to send · Shift+Enter for a new line · Answers cite the pages they came from
      </div>
    </div>
  );
}
