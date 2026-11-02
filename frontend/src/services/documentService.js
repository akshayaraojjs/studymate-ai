import { api } from './api';

export async function listDocuments() {
  const { data } = await api.get('/documents');
  return data;
}

export async function uploadDocument(file, onProgress) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (!onProgress || !event.total) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    },
  });
  return data;
}

export async function deleteDocument(id) {
  await api.delete(`/documents/${id}`);
}

export async function searchDocument(id, query) {
  const { data } = await api.post(`/documents/${id}/search`, { query });
  return data;
}

export async function listConversations() {
  const { data } = await api.get('/conversations');
  return data;
}

export async function getConversationMessages(conversationId) {
  const { data } = await api.get(`/conversations/${conversationId}/messages`);
  return data;
}

export async function generateQuiz({ topic, documentIds = [], numQuestions = 5 }) {
  const { data } = await api.post('/study/quiz', {
    topic,
    document_ids: documentIds,
    num_questions: numQuestions,
  });
  return data;
}

export async function generateSummary({ chapter, documentIds = [], pageStart, pageEnd }) {
  const { data } = await api.post('/study/summary', {
    chapter: chapter || null,
    document_ids: documentIds,
    page_start: pageStart || null,
    page_end: pageEnd || null,
  });
  return data;
}
