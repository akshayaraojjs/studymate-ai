export default function SourceCitation({ citations, open, onToggle, highlightNumber, idPrefix }) {
  if (!citations?.length) return null;

  return (
    <div className="source-list">
      <button
        type="button"
        className="btn btn-link btn-sm p-0 text-decoration-none text-start fw-semibold"
        style={{ fontSize: '0.76rem' }}
        onClick={onToggle}
        aria-expanded={open}
      >
        {open ? '▾' : '▸'} Sources ({citations.length})
      </button>
      {open && (
        <div className="d-flex flex-column gap-2 mt-1">
          {citations.map((citation) => (
            <div
              key={citation.chunk_id}
              id={`${idPrefix}-source-${citation.number}`}
              className={`source-item ${highlightNumber === citation.number ? 'highlight' : ''}`}
            >
              <div className="d-flex justify-content-between gap-2">
                <span className="fw-semibold" style={{ color: 'var(--sm-ink)' }}>
                  [{citation.number}] {citation.document_name}
                </span>
                <span className="text-nowrap">p. {citation.page_number}</span>
              </div>
              {citation.section_title && (
                <div className="fst-italic">{citation.section_title}</div>
              )}
              <div className="source-quote">{citation.snippet}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
