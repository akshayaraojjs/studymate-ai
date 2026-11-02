import { API_BASE } from './api';

/**
 * POST the chat message and parse the Server-Sent Events stream.
 *
 * SSE events can be split across network chunks, so the raw text is buffered and
 * only complete `data:` frames (terminated by a blank line) are dispatched.
 */
export async function streamChat({ message, conversationId, documentIds, token, signal, onEvent }) {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId || null,
      document_ids: documentIds || [],
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    let detail = '';
    try {
      const payload = await response.json();
      detail = typeof payload?.detail === 'string' ? payload.detail : '';
    } catch {
      detail = '';
    }
    throw new Error(detail || `Unable to start the response stream (HTTP ${response.status}).`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const dispatch = (frame) => {
    const dataLines = frame
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart());
    if (!dataLines.length) return;
    const payload = dataLines.join('\n');
    if (!payload) return;
    try {
      onEvent(JSON.parse(payload));
    } catch {
      // Ignore malformed frames rather than breaking the stream.
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        dispatch(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) dispatch(buffer);
  } finally {
    reader.releaseLock?.();
  }
}
