const LABELS = {
  ready: 'Ready',
  processing: 'Processing',
  failed: 'Failed',
  uploading: 'Uploading',
  pending: 'Pending',
};

export default function DocumentStatus({ status }) {
  const key = LABELS[status] ? status : 'processing';
  return <span className={`badge-status ${key}`}>{LABELS[status] || status}</span>;
}
