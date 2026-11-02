import DocumentStatus from './DocumentStatus.jsx';

function formatSize(bytes) {
  if (!bytes) return '0 KB';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentList({ documents, selectedIds, onToggle, onDelete }) {
  if (!documents.length) {
    return (
      <p className="empty-hint mb-0">
        No documents yet. Upload your course notes, a textbook chapter, or any study guide to get
        grounded answers with citations.
      </p>
    );
  }

  return (
    <div className="d-flex flex-column gap-2">
      {documents.map((document) => {
        const selected = selectedIds.includes(document.id);
        return (
          <div
            key={document.id}
            className={`doc-item ${selected ? 'selected' : ''}`}
            onClick={() => document.status === 'ready' && onToggle(document.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && document.status === 'ready') onToggle(document.id);
            }}
          >
            <div className="pt-1" aria-hidden="true">
              {document.file_type === 'pdf' ? '📄' : '📝'}
            </div>
            <div className="flex-grow-1 min-w-0">
              <div className="doc-name" title={document.filename}>
                {document.filename}
              </div>
              <div className="doc-meta d-flex align-items-center gap-1 flex-wrap mt-1">
                <DocumentStatus status={document.status} />
                <span>·</span>
                <span>{formatSize(document.size_bytes)}</span>
                {document.status === 'ready' && (
                  <>
                    <span>·</span>
                    <span>{document.page_count} p.</span>
                    <span>·</span>
                    <span>{document.chunk_count} chunks</span>
                  </>
                )}
              </div>
              {document.status === 'failed' && document.error_message && (
                <div className="text-danger mt-1" style={{ fontSize: '0.7rem' }}>
                  {document.error_message}
                </div>
              )}
            </div>
            <button
              type="button"
              className="btn btn-sm btn-link text-secondary p-0"
              title="Delete document"
              aria-label={`Delete ${document.filename}`}
              onClick={(event) => {
                event.stopPropagation();
                onDelete(document);
              }}
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
}
