import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  Loader2,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { normalizeApiBaseUrl } from '../utils/evaluationHelpers';

const REQUEST_TIMEOUT_MS = 7000;

const requestWithTimeout = async (url) => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS,
  );

  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
};

const statusStyles = {
  success: 'text-green-400',
  warning: 'text-yellow-300',
  error: 'text-red-400',
};

const StatusIcon = ({ status }) => {
  if (status === 'success') {
    return <CheckCircle className="h-6 w-6 text-green-400" aria-hidden="true" />;
  }
  if (status === 'warning') {
    return <AlertTriangle className="h-6 w-6 text-yellow-300" aria-hidden="true" />;
  }
  return <XCircle className="h-6 w-6 text-red-400" aria-hidden="true" />;
};

const AdminDashboard = () => {
  const [diagnosticResults, setDiagnosticResults] = useState({});
  const [isRunningTests, setIsRunningTests] = useState(false);
  const navigate = useNavigate();
  const { currentUser } = useAuth();

  const runDiagnostics = async () => {
    setIsRunningTests(true);
    const results = {};
    const apiUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_URL);

    try {
      const response = await requestWithTimeout(`${apiUrl}/openapi.json`);
      if (!response.ok) {
        throw new Error(`Backend responded with status ${response.status}`);
      }

      const schema = await response.json();
      const paths = schema.paths || {};
      const hasEvaluation = Boolean(paths['/evaluate/']?.post);
      const hasDownload = Boolean(
        paths['/download-report/{session_id}/{filename}']?.get,
      );

      results.backendConnectivity = {
        status: 'success',
        message: 'Backend API schema loaded successfully.',
        details: `URL: ${apiUrl}`,
      };
      results.coreEndpoints = {
        status: hasEvaluation && hasDownload ? 'success' : 'error',
        message: hasEvaluation && hasDownload
          ? 'Evaluation and report-download endpoints are available.'
          : 'One or more core endpoints are missing.',
        details: `Evaluate: ${hasEvaluation ? 'available' : 'missing'} · Download: ${hasDownload ? 'available' : 'missing'}`,
      };
    } catch (error) {
      results.backendConnectivity = {
        status: error.name === 'AbortError' ? 'warning' : 'error',
        message: error.name === 'AbortError'
          ? `Backend did not respond within ${REQUEST_TIMEOUT_MS / 1000} seconds.`
          : `Could not load the backend API schema: ${error.message}`,
        details: `URL: ${apiUrl}`,
      };
    }

    results.environment = {
      status: import.meta.env.VITE_API_URL ? 'success' : 'warning',
      message: import.meta.env.VITE_API_URL
        ? 'VITE_API_URL is configured.'
        : 'Using the local development API URL.',
      details: apiUrl,
    };
    results.authentication = {
      status: currentUser ? 'success' : 'warning',
      message: currentUser
        ? `Signed in as ${currentUser.email || currentUser.displayName || 'a Firebase user'}.`
        : 'No Firebase user is signed in.',
      details: currentUser
        ? `User ID: ${currentUser.uid}`
        : 'Authentication is optional for this development-only diagnostics page.',
    };

    setDiagnosticResults(results);
    setIsRunningTests(false);
  };

  return (
    <div className="min-h-screen bg-[#171717] px-4 py-8 text-white sm:px-6">
      <div className="mx-auto max-w-5xl">
        <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="mb-1 text-sm font-semibold uppercase tracking-widest text-orange-300">
              Development only
            </p>
            <h1 className="text-3xl font-bold text-white">LitMark diagnostics</h1>
          </div>
          <button
            type="button"
            onClick={() => navigate('/')}
            className="diagnostics-button inline-flex w-fit items-center gap-2 rounded-lg border border-white/15 px-4 py-2 text-sm text-white hover:bg-white/10"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Return home
          </button>
        </header>

        <section className="rounded-2xl border border-white/10 bg-white/[0.06] p-5 shadow-xl sm:p-7">
          <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-bold text-white">System checks</h2>
              <p className="mt-1 text-sm text-gray-300">
                Confirms the configured backend and core API routes without running an AI evaluation.
              </p>
            </div>
            <button
              type="button"
              onClick={runDiagnostics}
              disabled={isRunningTests}
              className="diagnostics-button inline-flex items-center justify-center gap-2 rounded-lg bg-[#984600] px-4 py-2.5 font-semibold text-white hover:bg-[#7A3600] disabled:cursor-wait disabled:opacity-60"
            >
              {isRunningTests ? (
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="h-5 w-5" aria-hidden="true" />
              )}
              {isRunningTests ? 'Running checks…' : 'Run diagnostics'}
            </button>
          </div>

          <div aria-live="polite">
            {Object.keys(diagnosticResults).length === 0 ? (
              <p className="rounded-xl bg-black/20 p-4 text-gray-300">
                Run diagnostics to check the current development environment.
              </p>
            ) : (
              <div className="space-y-3">
                {Object.entries(diagnosticResults).map(([key, result]) => (
                  <article key={key} className="rounded-xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-start gap-3">
                      <StatusIcon status={result.status} />
                      <div className="min-w-0">
                        <h3 className="font-semibold capitalize text-white">
                          {key.replace(/([A-Z])/g, ' $1').trim()}
                        </h3>
                        <p className={statusStyles[result.status]}>
                          {result.message}
                        </p>
                        <p className="mt-1 break-words text-sm text-gray-400">
                          {result.details}
                        </p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default AdminDashboard;
