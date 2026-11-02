import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SourceCitation from '../chat/SourceCitation.jsx';

export default function SummaryPanel({ summary, loading, error, onGenerate, hasDocuments }) {
  const [chapter, setChapter] = useState('');
  const [pageStart, setPageStart] = useState('');
  const [pageEnd, setPageEnd] = useState('');
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const submit = () => {
    onGenerate({
      chapter: chapter.trim() || null,
      pageStart: pageStart ? Number(pageStart) : null,
      pageEnd: pageEnd ? Number(pageEnd) : null,
    });
  };

  const canSubmit = Boolean(chapter.trim() || pageStart || pageEnd) && hasDocuments;

  return (
    <div className="d-flex flex-column gap-3">
      <div className="section-card">
        <label className="form-label small fw-semibold" htmlFor="summary-chapter">
          Chapter, heading or topic
        </label>
        <input
          id="summary-chapter"
          className="form-control form-control-sm"
          placeholder="e.g. Chapter 3 or Normalization"
          value={chapter}
          onChange={(event) => setChapter(event.target.value)}
          maxLength={200}
        />
        <div className="d-flex gap-2 mt-2">
          <input
            className="form-control form-control-sm"
            type="number"
            min={1}
            placeholder="From page"
            value={pageStart}
            onChange={(event) => setPageStart(event.target.value)}
            aria-label="First page"
          />
          <input
            className="form-control form-control-sm"
            type="number"
            min={1}
            placeholder="To page"
            value={pageEnd}
            onChange={(event) => setPageEnd(event.target.value)}
            aria-label="Last page"
          />
        </div>
        <button
          type="button"
          className="btn btn-sm btn-primary w-100 mt-2"
          disabled={loading || !canSubmit}
          onClick={submit}
        >
          {loading ? 'Summarising…' : 'Summarize section'}
        </button>
        {!hasDocuments && (
          <div className="form-text">Upload and process a document to summarize it.</div>
        )}
        {error && (
          <div className="alert alert-warning py-1 px-2 small mt-2 mb-0" role="alert">
            {error}
          </div>
        )}
      </div>

      {!summary && !loading && (
        <p className="empty-hint mb-0">
          A summary is built only from the section that matches your heading or page range, so it
          will not blend unrelated chapters. If the section cannot be found, you will be asked to
          pick a heading or page range.
        </p>
      )}

      {summary && (
        <div className="section-card">
          <div className="section-label mb-1">Summary</div>
          <div className="fw-semibold small mb-2">{summary.chapter}</div>
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.markdown || ''}</ReactMarkdown>
          </div>
          <SourceCitation
            citations={summary.citations || []}
            open={sourcesOpen}
            onToggle={() => setSourcesOpen((value) => !value)}
            idPrefix="summary"
          />
        </div>
      )}
    </div>
  );
}
