import { useState } from 'react';
import { api, getErrorMessage } from '../services/api';

const initialForm = { name: '', email: '', password: '', confirmPassword: '' };

function EyeIcon({ open }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12S18 18.5 12 18.5 2.5 12 2.5 12Z" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3.1" />
      {!open && <path d="M4 20 20 4" strokeLinecap="round" />}
    </svg>
  );
}

export default function LoginPage({ onAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const isRegister = mode === 'register';

  const switchMode = (next) => {
    if (next === mode) return;
    setMode(next);
    setError('');
    setShowPassword(false);
    setShowConfirm(false);
    setForm((prev) => ({ ...prev, password: '', confirmPassword: '' }));
  };

  const handleChange = (event) => {
    setForm((prev) => ({ ...prev, [event.target.name]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (isRegister && form.password !== form.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
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
    <div className="auth-page">
      <main className="auth-panel">
        <header className="auth-brand">
          <span className="brand-mark">SM</span>
          <span className="auth-brand-name">StudyMate AI</span>
        </header>

        <div className="auth-mode" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            role="tab"
            aria-selected={!isRegister}
            className={`auth-mode-btn ${!isRegister ? 'active' : ''}`}
            onClick={() => switchMode('login')}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isRegister}
            className={`auth-mode-btn ${isRegister ? 'active' : ''}`}
            onClick={() => switchMode('register')}
          >
            Create account
          </button>
        </div>

        <h1 className="auth-title">{isRegister ? 'Create your account' : 'Welcome back'}</h1>
        <p className="auth-sub">
          {isRegister
            ? 'Your documents stay private to you.'
            : 'Sign in to reach your library and chats.'}
        </p>

        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {isRegister && (
            <div className="auth-field">
              <label className="auth-label" htmlFor="name">
                Name
              </label>
              <input
                id="name"
                name="name"
                className="auth-input"
                value={form.name}
                onChange={handleChange}
                required
                minLength={2}
                autoComplete="name"
                placeholder="Ada Lovelace"
              />
            </div>
          )}

          <div className="auth-field">
            <label className="auth-label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              className="auth-input"
              value={form.email}
              onChange={handleChange}
              required
              autoComplete="email"
              autoFocus
              placeholder="you@university.edu"
            />
          </div>

          <div className="auth-field">
            <label className="auth-label" htmlFor="password">
              Password
            </label>
            <div className="auth-input-wrap">
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                className="auth-input has-icon"
                value={form.password}
                onChange={handleChange}
                required
                minLength={isRegister ? 8 : 1}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                placeholder={isRegister ? 'At least 8 characters' : '••••••••'}
              />
              <button
                type="button"
                className="auth-eye"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                tabIndex={-1}
              >
                <EyeIcon open={showPassword} />
              </button>
            </div>
          </div>

          {isRegister && (
            <div className="auth-field">
              <label className="auth-label" htmlFor="confirmPassword">
                Confirm password
              </label>
              <div className="auth-input-wrap">
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showConfirm ? 'text' : 'password'}
                  className="auth-input has-icon"
                  value={form.confirmPassword}
                  onChange={handleChange}
                  required
                  minLength={8}
                  autoComplete="new-password"
                  placeholder="Re-enter your password"
                />
                <button
                  type="button"
                  className="auth-eye"
                  onClick={() => setShowConfirm((prev) => !prev)}
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                  aria-pressed={showConfirm}
                  tabIndex={-1}
                >
                  <EyeIcon open={showConfirm} />
                </button>
              </div>
            </div>
          )}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? (
              <>
                <span className="auth-spinner" aria-hidden="true" />
                Please wait…
              </>
            ) : isRegister ? (
              'Create account'
            ) : (
              'Sign in'
            )}
          </button>
        </form>

        <p className="auth-foot">
          {isRegister ? 'Already have an account? ' : 'New to StudyMate? '}
          <button type="button" className="auth-link" onClick={() => switchMode(isRegister ? 'login' : 'register')}>
            {isRegister ? 'Sign in' : 'Create one'}
          </button>
        </p>
      </main>
    </div>
  );
}
