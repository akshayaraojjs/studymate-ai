import { useState } from 'react';
import { api, getErrorMessage } from '../services/api';

const initialForm = { name: '', email: '', password: '' };

export default function LoginPage({ onAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const isRegister = mode === 'register';

  const handleChange = (event) => {
    setForm((prev) => ({ ...prev, [event.target.name]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const endpoint = isRegister ? '/auth/register' : '/auth/login';
      const payload = isRegister
        ? { name: form.name.trim(), email: form.email.trim(), password: form.password }
        : { email: form.email.trim(), password: form.password };
      const { data } = await api.post(endpoint, payload);
      onAuthenticated({ token: data.access_token, user: data.user });
    } catch (submitError) {
      setError(getErrorMessage(submitError, 'Could not sign in. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <section className="auth-hero">
        <div className="d-flex align-items-center gap-2 mb-2">
          <span className="brand-mark">SM</span>
          <span className="fs-5 fw-semibold">StudyMate AI</span>
        </div>
        <h1>Your course material, turned into a study companion.</h1>
        <p className="mb-0" style={{ color: 'rgba(255,255,255,0.82)', maxWidth: 460 }}>
          Upload a PDF or TXT file, then ask questions, generate quizzes and summarise chapters —
          with every answer traceable to the exact page it came from.
        </p>
        <ul className="mt-2 mb-0">
          <li>Answers grounded in your own documents with clickable citations</li>
          <li>An agent that picks document search, web search, or a calculator per request</li>
          <li>Five-question quizzes and chapter summaries from your material</li>
          <li>Explicit handling of missing evidence and prompt-injection attempts</li>
        </ul>
      </section>

      <section className="auth-card-wrap">
        <div className="auth-card">
          <div className="d-flex gap-2 mb-4">
            <button
              type="button"
              className={`btn btn-sm flex-fill ${!isRegister ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => {
                setMode('login');
                setError('');
              }}
            >
              Sign in
            </button>
            <button
              type="button"
              className={`btn btn-sm flex-fill ${isRegister ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => {
                setMode('register');
                setError('');
              }}
            >
              Create account
            </button>
          </div>

          <h2 className="fs-5 fw-bold mb-1">
            {isRegister ? 'Start studying your own material' : 'Welcome back'}
          </h2>
          <p className="text-secondary small mb-4">
            {isRegister
              ? 'Accounts keep your documents private to you.'
              : 'Sign in to reach your document library and chats.'}
          </p>

          {error && (
            <div className="alert alert-danger py-2 small" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="d-flex flex-column gap-3">
            {isRegister && (
              <div>
                <label className="form-label small fw-semibold" htmlFor="name">
                  Name
                </label>
                <input
                  id="name"
                  name="name"
                  className="form-control"
                  value={form.name}
                  onChange={handleChange}
                  required
                  minLength={2}
                  autoComplete="name"
                />
              </div>
            )}
            <div>
              <label className="form-label small fw-semibold" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                className="form-control"
                value={form.email}
                onChange={handleChange}
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label className="form-label small fw-semibold" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                className="form-control"
                value={form.password}
                onChange={handleChange}
                required
                minLength={isRegister ? 8 : 1}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
              />
              {isRegister && (
                <div className="form-text">At least 8 characters.</div>
              )}
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Please wait…' : isRegister ? 'Create account' : 'Sign in'}
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}
