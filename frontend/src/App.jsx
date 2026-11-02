import { useCallback, useEffect, useState } from 'react';
import { loadStoredAuth, setAuthToken, storeAuth } from './services/api';
import { useTheme } from './hooks/useTheme';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';

export default function App() {
  const [auth, setAuth] = useState(() => loadStoredAuth());
  const { theme, toggleTheme } = useTheme();

  useEffect(() => {
    setAuthToken(auth?.token || null);
  }, [auth]);

  useEffect(() => {
    const handleLogout = () => setAuth(null);
    window.addEventListener('studymate:logout', handleLogout);
    return () => window.removeEventListener('studymate:logout', handleLogout);
  }, []);

  const handleAuthenticated = useCallback((nextAuth) => {
    storeAuth(nextAuth);
    setAuthToken(nextAuth.token);
    setAuth(nextAuth);
  }, []);

  const handleLogout = useCallback(() => {
    storeAuth(null);
    setAuthToken(null);
    setAuth(null);
  }, []);

  if (!auth?.token) {
    return <LoginPage onAuthenticated={handleAuthenticated} />;
  }

  return (
    <DashboardPage
      auth={auth}
      onLogout={handleLogout}
      theme={theme}
      onToggleTheme={toggleTheme}
    />
  );
}
