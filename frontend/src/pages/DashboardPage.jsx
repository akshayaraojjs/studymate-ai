import { useCallback, useEffect, useMemo, useState } from 'react';
import AppHeader from '../components/layout/AppHeader.jsx';
import AppSidebar from '../components/layout/AppSidebar.jsx';
import ChatInput from '../components/chat/ChatInput.jsx';
import ChatWindow from '../components/chat/ChatWindow.jsx';
import QuizPanel from '../components/study/QuizPanel.jsx';
import SummaryPanel from '../components/study/SummaryPanel.jsx';
import { useChatStream } from '../hooks/useChatStream.js';
import { getErrorMessage } from '../services/api';
import {
  deleteDocument,
  generateQuiz,
  generateSummary,
  getConversationMessages,
  listConversations,
  listDocuments,
  uploadDocument,
} from '../services/documentService';

const MAX_UPLOAD_BYTES = 15 * 1024 * 1024;

export default function DashboardPage({ auth, onLogout, theme, onToggleTheme }) {
  const [documents, setDocuments] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [quiz, setQuiz] = useState(null);
  const [summary, setSummary] = useState(null);
  const [quizLoading, setQuizLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [quizError, setQuizError] = useState('');
  const [summaryError, setSummaryError] = useState('');
  const [panelTab, setPanelTab] = useState('quiz');
  const [panelOpen, setPanelOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState('');
  const [notice, setNotice] = useState('');

  const refreshConversations = useCallback(() => {
    listConversations()
      .then(setConversations)
      .catch(() => {});
  }, []);

  const handleQuizFromChat = useCallback((nextQuiz) => {
    setQuiz(nextQuiz);
    setPanelTab('quiz');
    setPanelOpen(true);
  }, []);

  const handleFinished = useCallback(() => {
    refreshConversations();
  }, [refreshConversations]);

  const chat = useChatStream({
    token: auth.token,
    onConversationCreated: setConversationId,
    onQuiz: handleQuizFromChat,
    onFinished: handleFinished,
  });

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch (error) {
      setNotice(getErrorMessage(error, 'Could not load your documents.'));
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    refreshConversations();
  }, [loadDocuments, refreshConversations]);

  useEffect(() => {
    const processing = documents.some((document) => document.status === 'processing');
    if (!processing) return undefined;
    const timer = setInterval(loadDocuments, 2500);
    return () => clearInterval(timer);
  }, [documents, loadDocuments]);

  useEffect(() => {
    setSelectedIds((prev) =>
      prev.filter((id) => documents.some((doc) => doc.id === id && doc.status === 'ready')),
    );
  }, [documents]);

  const readyDocuments = useMemo(
    () => documents.filter((document) => document.status === 'ready'),
    [documents],
  );

  const handleUpload = async (file) => {
    setUploadError('');
    setNotice('');
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'txt'].includes(extension)) {
      setUploadError('Only PDF and TXT files are supported.');
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadError('File exceeds the 15 MB upload limit.');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    try {
      const document = await uploadDocument(file, setUploadProgress);
      setDocuments((prev) => [document, ...prev]);
    } catch (error) {
      setUploadError(getErrorMessage(error, 'Upload failed.'));
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDelete = async (document) => {
    if (!window.confirm(`Delete "${document.filename}" and its indexed passages?`)) return;
    try {
      await deleteDocument(document.id);
      setDocuments((prev) => prev.filter((item) => item.id !== document.id));
      setSelectedIds((prev) => prev.filter((id) => id !== document.id));
    } catch (error) {
      setNotice(getErrorMessage(error, 'Could not delete the document.'));
    }
  };

  const toggleDocument = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    );
  };

  const handleSend = (text) => {
    chat.send({
      message: text,
      documentIds: selectedIds,
      conversationId,
    });
  };

  const handleNewChat = () => {
    chat.reset();
    setConversationId(null);
    setPanelOpen(false);
  };

  const toggleSidebar = () => {
    // Opening a panel means leaving the maximised chat view.
    if (!sidebarOpen) setFocusMode(false);
    setSidebarOpen(!sidebarOpen);
  };

  const togglePanel = () => {
    if (!panelOpen) setFocusMode(false);
    setPanelOpen(!panelOpen);
  };

  const toggleFocusMode = () => {
    setFocusMode((value) => {
      if (!value) {
        // Give the chat the whole viewport: dismiss the mobile drawers too.
        setSidebarOpen(false);
        setPanelOpen(false);
      }
      return !value;
    });
  };

  const handleSelectConversation = async (id) => {
    try {
      const history = await getConversationMessages(id);
      chat.hydrate(history);
      setConversationId(id);
      setSidebarOpen(false);
    } catch (error) {
      setNotice(getErrorMessage(error, 'Could not load that conversation.'));
    }
  };

  const handleGenerateQuiz = async ({ topic, numQuestions }) => {
    setQuizError('');
    setQuizLoading(true);
    try {
      const data = await generateQuiz({
        topic,
        documentIds: selectedIds,
        numQuestions,
      });
      setQuiz(data);
      setPanelTab('quiz');
      setPanelOpen(true);
    } catch (error) {
      setQuizError(getErrorMessage(error, 'Quiz generation failed.'));
    } finally {
      setQuizLoading(false);
    }
  };

  const handleGenerateSummary = async ({ chapter, pageStart, pageEnd }) => {
    setSummaryError('');
    setSummaryLoading(true);
    try {
      const data = await generateSummary({
        chapter,
        documentIds: selectedIds,
        pageStart,
        pageEnd,
      });
      setSummary(data);
      setPanelTab('summary');
      setPanelOpen(true);
    } catch (error) {
      setSummaryError(getErrorMessage(error, 'Summary generation failed.'));
    } finally {
      setSummaryLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <AppHeader
        user={auth.user}
        conversations={conversations}
        conversationId={conversationId}
        onSelectConversation={handleSelectConversation}
        onNewChat={handleNewChat}
        onLogout={onLogout}
        onToggleSidebar={toggleSidebar}
        onTogglePanel={togglePanel}
        theme={theme}
        onToggleTheme={onToggleTheme}
        focusMode={focusMode}
        onToggleFocus={toggleFocusMode}
      />

      <div className={`app-body ${focusMode ? 'focus-mode' : ''}`}>
        <AppSidebar
          documents={documents}
          selectedIds={selectedIds}
          onToggleDocument={toggleDocument}
          onClearSelection={() => setSelectedIds([])}
          onUpload={handleUpload}
          onDelete={handleDelete}
          uploading={uploading}
          progress={uploadProgress}
          uploadError={uploadError}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        {sidebarOpen && (
          <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
        )}

        <main className="chat-column">
          {notice && (
            <div className="alert alert-warning m-2 mb-0 py-2 small d-flex justify-content-between">
              <span>{notice}</span>
              <button
                type="button"
                className="btn btn-sm btn-link p-0"
                onClick={() => setNotice('')}
              >
                Dismiss
              </button>
            </div>
          )}

          <ChatWindow
            messages={chat.messages}
            streaming={chat.streaming}
            activity={chat.activity}
            error={chat.error}
            hasDocuments={readyDocuments.length > 0}
            onSuggestion={handleSend}
            onRetry={chat.retry}
          />

          <ChatInput
            onSend={handleSend}
            onStop={chat.stop}
            streaming={chat.streaming}
            disabled={readyDocuments.length === 0}
          />
        </main>

        <aside className={`study-column ${panelOpen ? 'open' : ''}`}>
          <div className="panel-tabs align-items-center">
            <button
              type="button"
              className={`btn ${panelTab === 'quiz' ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => setPanelTab('quiz')}
            >
              Quiz
            </button>
            <button
              type="button"
              className={`btn ${panelTab === 'summary' ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => setPanelTab('summary')}
            >
              Summary
            </button>
            <button
              type="button"
              className="btn btn-outline-secondary ms-auto d-xl-none"
              onClick={() => setPanelOpen(false)}
              aria-label="Close study tools"
            >
              ✕
            </button>
          </div>

          <div className="panel-body">
            {panelTab === 'quiz' ? (
              <QuizPanel
                quiz={quiz}
                loading={quizLoading}
                error={quizError}
                onGenerate={handleGenerateQuiz}
                hasDocuments={readyDocuments.length > 0}
              />
            ) : (
              <SummaryPanel
                summary={summary}
                loading={summaryLoading}
                error={summaryError}
                onGenerate={handleGenerateSummary}
                hasDocuments={readyDocuments.length > 0}
              />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
