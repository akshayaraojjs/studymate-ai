import { useEffect, useMemo, useState } from 'react';

export default function QuizPanel({ quiz, loading, error, onGenerate, hasDocuments }) {
  const [answers, setAnswers] = useState({});
  const [checked, setChecked] = useState(false);
  const [topic, setTopic] = useState('');
  const [count, setCount] = useState(5);

  useEffect(() => {
    setAnswers({});
    setChecked(false);
  }, [quiz?.attempt_id, quiz?.topic]);

  const questions = quiz?.questions || [];
  const answeredCount = Object.keys(answers).length;
  const score = useMemo(
    () =>
      questions.reduce(
        (total, question) =>
          total + (answers[question.id] === question.correct_option ? 1 : 0),
        0,
      ),
    [answers, questions],
  );

  return (
    <div className="d-flex flex-column gap-3">
      <div className="section-card">
        <label className="form-label small fw-semibold" htmlFor="quiz-topic">
          Quiz topic
        </label>
        <div className="d-flex gap-2">
          <input
            id="quiz-topic"
            className="form-control form-control-sm"
            placeholder="e.g. SQL joins"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            maxLength={200}
          />
          <select
            className="form-select form-select-sm"
            style={{ width: 84 }}
            value={count}
            onChange={(event) => setCount(Number(event.target.value))}
            aria-label="Number of questions"
          >
            {[3, 4, 5, 6, 7, 8].map((value) => (
              <option key={value} value={value}>
                {value} Q
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="btn btn-sm btn-primary w-100 mt-2"
          disabled={loading || !topic.trim() || !hasDocuments}
          onClick={() => onGenerate({ topic: topic.trim(), numQuestions: count })}
        >
          {loading ? 'Generating…' : 'Generate quiz'}
        </button>
        {!hasDocuments && (
          <div className="form-text">Upload and process a document to generate a quiz.</div>
        )}
        {error && (
          <div className="alert alert-warning py-1 px-2 small mt-2 mb-0" role="alert">
            {error}
          </div>
        )}
      </div>

      {!quiz && !loading && (
        <p className="empty-hint mb-0">
          Quizzes are grounded in retrieved passages from your documents. Ask in chat (for example
          “create five questions on joins”) or generate one here.
        </p>
      )}

      {quiz && (
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-center justify-content-between">
            <div>
              <div className="section-label">Quiz</div>
              <div className="fw-semibold small">{quiz.topic || 'Practice quiz'}</div>
            </div>
            <span className="badge text-bg-light">{questions.length} questions</span>
          </div>

          {questions.map((question, index) => {
            const chosen = answers[question.id];
            return (
              <div key={question.id} className="section-card">
                <div className="fw-semibold mb-2" style={{ fontSize: '0.83rem' }}>
                  {index + 1}. {question.question}
                </div>
                {question.options.map((option, optionIndex) => {
                  let variant = '';
                  if (checked) {
                    if (optionIndex === question.correct_option) variant = 'correct';
                    else if (chosen === optionIndex) variant = 'wrong';
                  } else if (chosen === optionIndex) {
                    variant = 'selected';
                  }
                  return (
                    <button
                      key={`${question.id}-${optionIndex}`}
                      type="button"
                      className={`quiz-option ${variant}`}
                      disabled={checked}
                      onClick={() =>
                        setAnswers((prev) => ({ ...prev, [question.id]: optionIndex }))
                      }
                    >
                      {String.fromCharCode(65 + optionIndex)}. {option}
                    </button>
                  );
                })}
                {checked && (
                  <div className="quiz-explanation">
                    {chosen === question.correct_option ? '✅ Correct. ' : '❌ Not quite. '}
                    {question.explanation}
                    {question.source_numbers?.length > 0 && (
                      <span className="ms-1 text-secondary">
                        Sources: {question.source_numbers.map((n) => `[${n}]`).join(' ')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          <div className="d-flex gap-2">
            {!checked ? (
              <button
                type="button"
                className="btn btn-sm btn-success flex-fill"
                disabled={answeredCount !== questions.length}
                onClick={() => setChecked(true)}
              >
                Check answers ({answeredCount}/{questions.length})
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-sm btn-outline-primary flex-fill"
                onClick={() => {
                  setAnswers({});
                  setChecked(false);
                }}
              >
                Try again
              </button>
            )}
          </div>

          {checked && (
            <div className="alert alert-primary py-2 small mb-0">
              Score: <strong>{score}</strong> / {questions.length} ·{' '}
              {Math.round((score / questions.length) * 100)}%
            </div>
          )}
        </div>
      )}
    </div>
  );
}
