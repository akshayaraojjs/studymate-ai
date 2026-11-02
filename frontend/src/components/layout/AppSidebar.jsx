import DocumentList from '../documents/DocumentList.jsx';
import FileUploader from '../documents/FileUploader.jsx';

export default function AppSidebar({
  documents,
  selectedIds,
  onToggleDocument,
  onClearSelection,
  onUpload,
  onDelete,
  uploading,
  progress,
  uploadError,
  open,
  onClose,
}) {
  const readyCount = documents.filter((document) => document.status === 'ready').length;
  const scopeLabel =
    selectedIds.length === 0
      ? `All ready documents (${readyCount})`
      : `${selectedIds.length} selected document${selectedIds.length === 1 ? '' : 's'}`;

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="d-flex align-items-center justify-content-between p-3 border-bottom">
        <div>
          <div className="section-label">Document library</div>
          <div className="text-secondary" style={{ fontSize: '0.72rem' }}>
            {scopeLabel}
          </div>
        </div>
        <button
          type="button"
          className="btn btn-sm btn-link text-secondary d-md-none p-0"
          onClick={onClose}
          aria-label="Close documents"
        >
          ✕
        </button>
      </div>

      <div className="sidebar-scroll">
        <FileUploader
          onUpload={onUpload}
          uploading={uploading}
          progress={progress}
          error={uploadError}
        />

        <div>
          <div className="d-flex align-items-center justify-content-between mb-2">
            <span className="section-label">Study scope</span>
            {selectedIds.length > 0 && (
              <button
                type="button"
                className="btn btn-link btn-sm p-0 text-decoration-none"
                style={{ fontSize: '0.72rem' }}
                onClick={onClearSelection}
              >
                Use all
              </button>
            )}
          </div>
          <DocumentList
            documents={documents}
            selectedIds={selectedIds}
            onToggle={onToggleDocument}
            onDelete={onDelete}
          />
        </div>

        <div className="mt-auto pt-2 border-top">
          <div className="section-label mb-1">How it works</div>
          <p className="empty-hint mb-0">
            Files are parsed, chunked and embedded on the server. Questions retrieve the closest
            passages, and the agent picks document search, web search, or the calculator depending
            on what you ask.
          </p>
        </div>
      </div>
    </aside>
  );
}
