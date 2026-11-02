import { useRef, useState } from 'react';

export default function FileUploader({ onUpload, uploading, progress, error }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div>
      <div
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        role="button"
        tabIndex={0}
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click();
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!uploading) handleFiles(event.dataTransfer.files);
        }}
      >
        <div className="small fw-semibold">{uploading ? 'Uploading…' : 'Upload PDF or TXT'}</div>
        <div className="text-secondary" style={{ fontSize: '0.7rem' }}>
          Drag a file here or click to browse · max 15 MB
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,application/pdf,text/plain"
          className="d-none"
          onChange={(event) => {
            handleFiles(event.target.files);
            event.target.value = '';
          }}
        />
      </div>

      {uploading && (
        <div className="progress mt-2" style={{ height: 5 }}>
          <div
            className="progress-bar"
            role="progressbar"
            style={{ width: `${Math.max(8, progress)}%` }}
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      )}

      {error && (
        <div className="alert alert-danger py-1 px-2 small mt-2 mb-0" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
