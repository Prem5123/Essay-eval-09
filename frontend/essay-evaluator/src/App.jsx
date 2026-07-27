import { Component, lazy, Suspense, useEffect } from 'react';
import {
  domAnimation,
  LazyMotion,
  m,
  MotionConfig,
  useReducedMotion,
} from 'framer-motion';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import './App.css';
import Navbar from './components/Navbar';

const LandingPage = lazy(() => import('./pages/LandingPage'));
const Login = lazy(() => import('./pages/Login'));
const Signup = lazy(() => import('./pages/Signup'));
const EssayEvaluator = lazy(() => import('./components/EssayEvaluator'));
const AdminDashboard = import.meta.env.DEV
  ? lazy(() => import('./pages/AdminDashboard'))
  : null;
const ROUTE_FOCUS_TIMEOUT_MS = 20_000;

const PageLoader = () => (
  <div className="page-loader" role="status" aria-live="polite">
    <span className="page-loader__spinner" aria-hidden="true" />
    <span>Loading LitMark…</span>
  </div>
);

class RouteErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('A frontend route could not be rendered.', error, errorInfo);
  }

  componentDidUpdate(previousProps) {
    if (
      previousProps.resetKey !== this.props.resetKey
      && this.state.error
    ) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <section className="page-error" role="alert">
        <h1 tabIndex={-1}>This page could not be loaded</h1>
        <p>
          A temporary browser or network problem interrupted the page.
          Reload to fetch a fresh copy.
        </p>
        <button type="button" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </section>
    );
  }
}

const ProtectedRoute = ({ children }) => {
  const { currentUser, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <PageLoader />;
  }

  if (!currentUser) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
};

const PublicOnlyRoute = ({ children }) => {
  const { currentUser, initializationError, loading } = useAuth();

  if (loading && !initializationError) {
    return <PageLoader />;
  }

  return currentUser ? <Navigate to="/app" replace /> : children;
};

const PageTransition = ({ children }) => {
  const reduceMotion = useReducedMotion();

  return (
    <m.div
      initial={reduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: reduceMotion ? 0 : 0.16, ease: 'easeOut' }}
      className="page-transition"
    >
      {children}
    </m.div>
  );
};

const ScrollToTop = () => {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    const pageTitles = {
      '/': 'LitMark — AI Essay Evaluation',
      '/app': 'Evaluate Essays — LitMark',
      '/login': 'Sign In — LitMark',
      '/signup': 'Create Account — LitMark',
      '/admin': 'Diagnostics — LitMark',
    };
    document.title = pageTitles[pathname] || 'LitMark — AI Essay Evaluation';

    const main = document.getElementById('main-content');
    if (!main) return undefined;

    let focusFrame = null;
    let focusTimeout = null;
    const focusHeading = () => {
      const heading = main.querySelector('h1');
      if (!heading) return false;
      if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1');
      heading.focus({ preventScroll: true });
      return true;
    };

    focusFrame = window.requestAnimationFrame(() => {
      if (focusHeading()) observer.disconnect();
    });
    const observer = new MutationObserver(() => {
      if (focusHeading()) observer.disconnect();
    });
    observer.observe(main, { childList: true, subtree: true });
    focusTimeout = window.setTimeout(() => {
      observer.disconnect();
      if (!main.querySelector('h1')) main.focus({ preventScroll: true });
    }, ROUTE_FOCUS_TIMEOUT_MS);

    return () => {
      observer.disconnect();
      if (focusFrame !== null) window.cancelAnimationFrame(focusFrame);
      if (focusTimeout !== null) window.clearTimeout(focusTimeout);
    };
  }, [pathname]);

  return null;
};

const App = () => {
  const location = useLocation();
  const showNavbar = location.pathname !== '/admin';

  return (
    <LazyMotion features={domAnimation} strict>
      <MotionConfig reducedMotion="user">
        <ScrollToTop />
        <a className="skip-link" href="#main-content">Skip to main content</a>
        {showNavbar && <Navbar />}
        <main id="main-content" tabIndex={-1}>
          <RouteErrorBoundary resetKey={location.key}>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<PageTransition><LandingPage /></PageTransition>} />
                <Route
                  path="/login"
                  element={<PublicOnlyRoute><PageTransition><Login /></PageTransition></PublicOnlyRoute>}
                />
                <Route
                  path="/signup"
                  element={<PublicOnlyRoute><PageTransition><Signup /></PageTransition></PublicOnlyRoute>}
                />
                {import.meta.env.DEV && AdminDashboard && (
                  <Route path="/admin" element={<PageTransition><AdminDashboard /></PageTransition>} />
                )}
                <Route
                  path="/app"
                  element={
                    <ProtectedRoute>
                      <PageTransition><EssayEvaluator /></PageTransition>
                    </ProtectedRoute>
                  }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </RouteErrorBoundary>
        </main>
      </MotionConfig>
    </LazyMotion>
  );
};

export default App;
