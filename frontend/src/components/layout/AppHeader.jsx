import { useEffect, useRef, useState } from 'react';

function ExpandIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M4 9V4h5M20 15v5h-5M20 9V4h-5M4 15v5h5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CollapseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M9 4v5H4M15 20v-5h5M15 4v5h5M9 20v-5H4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path
        d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path
        d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function AppHeader({
  user,
  conversations,
  conversationId,
  onSelectConversation,
  onNewChat,
  onLogout,
  onToggleSidebar,
  onTogglePanel,
  theme,
  onToggleTheme,
  focusMode,
  onToggleFocus,
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClick = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setHistoryOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const isDark = theme === 'dark';

  return (
    <header className="app-header">
      <button
        type="button"
        className="btn btn-sm btn-outline-secondary d-md-none"
        onClick={onToggleSidebar}
        aria-label="Toggle documents"
      >
        ☰
      </button>

      <div className="d-flex align-items-center gap-2">
        <span className="brand-mark">SM</span>
        <div className="lh-sm">
          <div className="fw-bold" style={{ fontSize: '0.95rem' }}>
            StudyMate AI
          </div>
          <div className="text-secondary d-none d-sm-block" style={{ fontSize: '0.68rem' }}>
            Grounded answers from your own material
          </div>
        </div>
      </div>

      <div className="ms-auto d-flex align-items-center gap-2" ref={dropdownRef}>
        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onNewChat}>
          New chat
        </button>

        <div className="position-relative">
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={() => setHistoryOpen((value) => !value)}
            aria-expanded={historyOpen}
          >
            History
          </button>
          {historyOpen && (
            <div
              className="position-absolute end-0 mt-1 bg-body border rounded-3 shadow-sm p-2"
              style={{ width: 280, zIndex: 40, maxHeight: 320, overflowY: 'auto' }}
            >
              {conversations.length === 0 && (
                <div className="text-secondary small px-2 py-1">No conversations yet.</div>
              )}
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  className={`btn btn-sm w-100 text-start ${
                    conversation.id === conversationId ? 'btn-outline-primary' : 'btn-outline-secondary'
                  } mb-1`}
                  style={{ whiteSpace: 'normal', fontSize: '0.78rem' }}
                  onClick={() => {
                    setHistoryOpen(false);
                    onSelectConversation(conversation.id);
                  }}
                >
                  {conversation.title || 'Untitled conversation'}
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          type="button"
          className="btn btn-sm btn-outline-secondary d-xl-none"
          onClick={onTogglePanel}
        >
          Study tools
        </button>

        <button
          type="button"
          className="icon-btn"
          onClick={onToggleFocus}
          aria-pressed={focusMode}
          aria-label={focusMode ? 'Show side panels' : 'Expand chat and hide side panels'}
          title={focusMode ? 'Show side panels' : 'Expand chat'}
        >
          {focusMode ? <CollapseIcon /> : <ExpandIcon />}
        </button>

        <button
          type="button"
          className="icon-btn"
          onClick={onToggleTheme}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          title={isDark ? 'Light mode' : 'Dark mode'}
        >
          {isDark ? <SunIcon /> : <MoonIcon />}
        </button>

        <div className="d-flex align-items-center gap-2 ps-1 border-start">
          <span className="avatar" title={user?.email}>
            {(user?.name || '?').trim().charAt(0).toUpperCase()}
          </span>
          <div className="d-none d-lg-block lh-sm">
            <div className="fw-semibold" style={{ fontSize: '0.8rem' }}>
              {user?.name}
            </div>
            <div className="text-secondary" style={{ fontSize: '0.68rem' }}>
              {user?.email}
            </div>
          </div>
          <button type="button" className="btn btn-sm btn-link text-secondary" onClick={onLogout}>
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
