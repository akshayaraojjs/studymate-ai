import { useCallback, useRef, useState } from 'react';
import { streamChat } from '../services/chatService';

const makeId = () => `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function useChatStream({ token, onConversationCreated, onQuiz, onFinished }) {
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [activity, setActivity] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const assistantIdRef = useRef(null);
  const lastRequestRef = useRef(null);
  const streamingRef = useRef(false);

  const patchAssistant = useCallback((patch) => {
    const id = assistantIdRef.current;
    if (!id) return;
    setMessages((prev) =>
      prev.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    );
  }, []);

  const appendAssistantContent = useCallback((chunk) => {
    const id = assistantIdRef.current;
    if (!id) return;
    setMessages((prev) =>
      prev.map((message) =>
        message.id === id ? { ...message, content: message.content + chunk } : message,
      ),
    );
  }, []);

  const runStream = useCallback(
    async ({ message, documentIds = [], conversationId = null, appendUser = true }) => {
      if (streamingRef.current) return;
      streamingRef.current = true;
      setStreaming(true);
      setError(null);
      lastRequestRef.current = { message, documentIds, conversationId };

      const assistantId = makeId();
      assistantIdRef.current = assistantId;
      setMessages((prev) => [
        ...prev,
        ...(appendUser ? [{ id: makeId(), role: 'user', content: message }] : []),
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          citations: [],
          externalSources: [],
          streaming: true,
        },
      ]);
      setActivity({ label: 'Thinking', status: 'running' });

      const controller = new AbortController();
      abortRef.current = controller;
      let finishedPayload = null;

      try {
        await streamChat({
          message,
          documentIds,
          conversationId,
          token,
          signal: controller.signal,
          onEvent: (event) => {
            switch (event.type) {
              case 'meta':
                if (event.conversation_id) onConversationCreated?.(event.conversation_id);
                break;
              case 'activity':
                if (event.status === 'running') {
                  setActivity({ label: event.label || 'Working', status: 'running' });
                } else {
                  setActivity(null);
                }
                break;
              case 'sources':
                patchAssistant({ citations: event.citations || [] });
                break;
              case 'quiz':
                patchAssistant({ hasQuiz: true });
                onQuiz?.(event.quiz);
                break;
              case 'token':
                appendAssistantContent(event.content || '');
                break;
              case 'error':
                setError(event.message || 'The assistant could not finish this response.');
                patchAssistant({ failed: true });
                break;
              case 'done':
                finishedPayload = event;
                patchAssistant({
                  content: event.text ?? undefined,
                  citations: event.citations || [],
                  externalSources: event.external_sources || [],
                  toolName: event.tool_name || null,
                  streaming: false,
                });
                break;
              default:
                break;
            }
          },
        });
      } catch (streamError) {
        if (streamError.name === 'AbortError') {
          patchAssistant({ stopped: true });
        } else {
          setError(streamError.message || 'Unable to start the response stream.');
          patchAssistant({ failed: true });
        }
      } finally {
        streamingRef.current = false;
        abortRef.current = null;
        setStreaming(false);
        setActivity(null);
        patchAssistant({ streaming: false });
        if (finishedPayload) onFinished?.(finishedPayload);
      }
    },
    [appendAssistantContent, onConversationCreated, onFinished, onQuiz, patchAssistant, token],
  );

  const send = useCallback(
    ({ message, documentIds, conversationId }) =>
      runStream({ message, documentIds, conversationId, appendUser: true }),
    [runStream],
  );

  const retry = useCallback(() => {
    const last = lastRequestRef.current;
    if (!last || streamingRef.current) return;
    setMessages((prev) => {
      const copy = [...prev];
      for (let index = copy.length - 1; index >= 0; index -= 1) {
        if (copy[index].role === 'assistant') {
          copy.splice(index, 1);
          break;
        }
      }
      return copy;
    });
    runStream({ ...last, appendUser: false });
  }, [runStream]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    lastRequestRef.current = null;
    assistantIdRef.current = null;
    setMessages([]);
    setActivity(null);
    setError(null);
    setStreaming(false);
    streamingRef.current = false;
  }, []);

  const hydrate = useCallback((history) => {
    abortRef.current?.abort();
    lastRequestRef.current = null;
    assistantIdRef.current = null;
    setMessages(
      (history || []).map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        citations: message.citations || [],
        externalSources: [],
        toolName: message.tool_name || null,
        streaming: false,
      })),
    );
    setActivity(null);
    setError(null);
    setStreaming(false);
    streamingRef.current = false;
  }, []);

  return { messages, streaming, activity, error, send, retry, stop, reset, hydrate, setError };
}
