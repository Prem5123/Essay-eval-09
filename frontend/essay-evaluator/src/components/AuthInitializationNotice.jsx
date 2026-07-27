import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';

const AuthInitializationNotice = ({
  message,
  onRetry,
  retrying = false,
}) => {
  const [retryAttempted, setRetryAttempted] = useState(false);
  const retryButtonRef = useRef(null);
  const retryStatusRef = useRef(null);
  const wasRetryingRef = useRef(false);

  useEffect(() => {
    if (!message) return undefined;
    return () => {
      window.requestAnimationFrame(() => {
        const heading = document.querySelector('#main-content h1');
        if (!heading) return;
        if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
      });
    };
  }, [message]);

  useEffect(() => {
    const retryJustFinished = wasRetryingRef.current && !retrying;
    wasRetryingRef.current = retrying;
    if (
      !retryJustFinished
      || !message
      || document.activeElement !== retryStatusRef.current
    ) {
      return;
    }
    window.requestAnimationFrame(() => retryButtonRef.current?.focus());
  }, [message, retrying]);

  if (!message) return null;

  const handleRetry = () => {
    setRetryAttempted(true);
    onRetry();
    retryStatusRef.current?.focus({ preventScroll: true });
  };

  return (
    <div
      className="mb-6 rounded-xl px-4 py-3 text-sm"
      style={{
        background: 'var(--warning-bg)',
        border: '1px solid var(--warning)',
        color: 'var(--text-primary)',
      }}
      role="alert"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle
          size={17}
          className="mt-0.5 shrink-0"
          style={{ color: 'var(--warning)' }}
          aria-hidden="true"
        />
        <span className="flex-1">{message}</span>
      </div>
      <button
        ref={retryButtonRef}
        type="button"
        onClick={handleRetry}
        disabled={retrying}
        className="mt-3 inline-flex items-center gap-2 rounded-lg px-3 py-2 font-semibold disabled:cursor-wait disabled:opacity-60"
        style={{
          color: 'var(--accent-ink)',
          border: '1px solid var(--border-control)',
        }}
      >
        {retrying ? (
          <Loader2 size={15} className="animate-spin" aria-hidden="true" />
        ) : (
          <RefreshCw size={15} aria-hidden="true" />
        )}
        {retrying ? 'Checking session…' : 'Retry session check'}
      </button>
      <span
        ref={retryStatusRef}
        className="sr-only"
        role="status"
        aria-live="polite"
        tabIndex={-1}
      >
        {retrying
          ? 'Checking your existing session…'
          : retryAttempted
            ? 'The session check did not complete. Retry is available.'
            : ''}
      </span>
    </div>
  );
};

export default AuthInitializationNotice;
