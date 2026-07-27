import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { m } from 'framer-motion';
import { ArrowRight, Loader2 } from 'lucide-react';
import { getAuthErrorMessage } from '../utils/authErrors';
import AuthInitializationNotice from '../components/AuthInitializationNotice';
import BrandLogo from '../components/BrandLogo';

const Signup = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [acceptedUse, setAcceptedUse] = useState(false);
  const [error, setError] = useState('');
  const [loadingAction, setLoadingAction] = useState(null);
  const actionStatusRef = useRef(null);
  const signupButtonRef = useRef(null);
  const googleButtonRef = useRef(null);
  const {
    initializationError,
    initializationRetrying,
    retryInitialization,
    signup,
    signInWithGoogle,
  } = useAuth();
  const navigate = useNavigate();
  const loading = loadingAction !== null;
  const actionStatus = loadingAction === 'google'
    ? 'Opening Google sign-up…'
    : loadingAction === 'signup'
      ? 'Creating your account…'
      : '';

  const beginAction = (action) => {
    setLoadingAction(action);
    actionStatusRef.current?.focus({ preventScroll: true });
  };

  const restoreActionFocus = (targetRef) => {
    if (document.activeElement !== actionStatusRef.current) return;
    window.requestAnimationFrame(() => targetRef.current?.focus());
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !password || !confirmPassword) {
      setError('Complete every field before creating your account.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least six characters.');
      return;
    }
    if (!acceptedUse) {
      setError('Confirm that you have permission to evaluate the work you upload.');
      return;
    }
    try {
      setError('');
      beginAction('signup');
      await signup(email.trim(), password, name.trim());
      navigate('/app', { replace: true });
    } catch (err) {
      setError(getAuthErrorMessage(err, 'Could not create your account. Please try again.'));
      console.error(err);
      restoreActionFocus(signupButtonRef);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleGoogleSignIn = async () => {
    if (!acceptedUse) {
      setError('Confirm that you have permission to evaluate the work you upload.');
      return;
    }

    try {
      setError('');
      beginAction('google');
      await signInWithGoogle();
      navigate('/app', { replace: true });
    } catch (err) {
      setError(getAuthErrorMessage(err, 'Google sign-up failed. Please try again.'));
      console.error(err);
      restoreActionFocus(googleButtonRef);
    } finally {
      setLoadingAction(null);
    }
  };

  const inputClass = "w-full px-4 py-3 rounded-xl text-sm transition-all duration-200"
    + " bg-[var(--bg-deep)] border border-[var(--border-control)]"
    + " text-[var(--text-primary)] placeholder-[var(--text-tertiary)]"
    + " focus:border-[var(--accent-ink)] focus:shadow-[0_0_0_3px_var(--accent-glow)] focus:outline-none";

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-20" style={{ background: 'var(--bg-deep)' }}>


      <m.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="max-w-md w-full glass glow-border rounded-2xl p-8 md:p-10 relative z-10"
      >
        {/* Header */}
        <div className="text-center mb-8">
          <BrandLogo className="justify-center" />
          <h1 className="mt-4 text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>
            Create account
          </h1>
          <p className="mt-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
            Set up your evaluation workspace
          </p>
        </div>

        {/* Error */}
        {error && (
          <m.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            id="signup-error"
            className="mb-6 px-4 py-3 rounded-xl text-sm"
            style={{ background: 'var(--error-bg)', border: '1px solid rgba(212,74,74,0.15)', color: 'var(--error)' }}
            role="alert"
          >
            {error}
          </m.div>
        )}
        <AuthInitializationNotice
          message={initializationError}
          onRetry={retryInitialization}
          retrying={initializationRetrying}
        />
        <div
          ref={actionStatusRef}
          className="sr-only"
          role="status"
          aria-live="polite"
          tabIndex={-1}
        >
          {actionStatus}
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="space-y-4"
          aria-describedby={error ? 'signup-error' : undefined}
        >
          <div>
            <label htmlFor="name" className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
              Full Name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputClass}
              placeholder="John Doe"
              autoComplete="name"
              maxLength={80}
              required
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
              Email Address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder="••••••••"
              autoComplete="new-password"
              aria-describedby="password-help"
              minLength={6}
              required
            />
            <p id="password-help" className="mt-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Use at least 6 characters.
            </p>
          </div>

          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
              Confirm Password
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={inputClass}
              placeholder="••••••••"
              autoComplete="new-password"
              minLength={6}
              required
            />
          </div>

          <div className="flex items-start gap-2 pt-1">
            <input
              id="terms"
              type="checkbox"
              checked={acceptedUse}
              onChange={(event) => setAcceptedUse(event.target.checked)}
              className="h-4 w-4 mt-0.5 rounded"
              style={{ accentColor: 'var(--accent)' }}
              required
            />
            <label htmlFor="terms" className="text-sm leading-tight" style={{ color: 'var(--text-tertiary)' }}>
              I confirm that I have permission to evaluate the work I upload and understand that it will be processed by an AI service.
            </label>
          </div>

          <m.button
            ref={signupButtonRef}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            type="submit"
            disabled={loading}
            className="w-full flex justify-center items-center gap-2 py-3 px-4 rounded-xl text-sm font-bold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
              boxShadow: '0 0 20px -5px rgba(250, 129, 18, 0.3)',
              color: 'var(--dark-text-primary)',
            }}
          >
            {loadingAction === 'signup' ? (
              <><Loader2 size={16} className="animate-spin" aria-hidden="true" /> Creating account…</>
            ) : (
              <>Create account <ArrowRight size={16} /></>
            )}
          </m.button>
        </form>

        {/* Footer */}
        <div className="mt-6 text-center">
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            Already have an account?{' '}
            <Link to="/login" className="font-semibold transition-colors" style={{ color: 'var(--accent-ink)' }}>
              Sign in
            </Link>
          </p>
        </div>

        {/* Divider */}
        <div className="mt-6 relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t" style={{ borderColor: 'var(--border-subtle)' }} />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-3" style={{ background: 'var(--bg-card)', color: 'var(--text-tertiary)' }}>
              Or continue with
            </span>
          </div>
        </div>

        {/* Google */}
        <div className="mt-6">
          <m.button
            ref={googleButtonRef}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            type="button"
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="w-full inline-flex justify-center items-center gap-3 py-3 px-4 rounded-xl text-sm font-medium transition-all duration-200 glass disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ color: 'var(--text-primary)' }}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 48 48"
              width="20px"
              height="20px"
              aria-hidden="true"
              focusable="false"
            >
              <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z" />
              <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z" />
              <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z" />
              <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z" />
            </svg>
            {loadingAction === 'google' ? 'Opening Google…' : 'Continue with Google'}
          </m.button>
        </div>
      </m.div>
    </div>
  );
};

export default Signup;
