import { useEffect, useRef, useState } from 'react';

export default function AppHeader({
  user,
  conversations,
  conversationId,
  onSelectConversation,
  onNewChat,
  onLogout,
  onToggleSidebar,
  onTogglePanel,
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
              className="position-absolute end-0 mt-1 bg-white border rounded-3 shadow-sm p-2"
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
                    conversation.id === conversationId ? 'btn-outline-primary' : 'btn-light'
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
