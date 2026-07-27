import { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { m, AnimatePresence } from 'framer-motion';
import { Menu, X, LogOut } from 'lucide-react';
import BrandLogo from './BrandLogo';

const NavLink = ({ to, children, isActive, onClick, scrolled }) => (
  <Link
    to={to}
    onClick={onClick}
    className="relative px-4 py-2 text-sm font-medium transition-colors duration-200"
    style={{ color: isActive ? (scrolled ? 'var(--dark-text-primary)' : 'var(--text-primary)') : (scrolled ? 'var(--dark-text-secondary)' : 'var(--text-secondary)') }}
    aria-current={isActive ? 'page' : undefined}
  >
    {children}
    {isActive && (
      <m.div
        className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
        style={{ background: scrolled ? 'var(--accent-light)' : 'var(--accent)' }}
        transition={{ type: 'spring', stiffness: 500, damping: 35 }}
      />
    )}
  </Link>
);

const Navbar = () => {
  const { currentUser, loading, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const scrollFrame = useRef(null);
  const menuToggleRef = useRef(null);
  const logoutFocusTargetRef = useRef(null);
  const logoutStatusRef = useRef(null);
  const displayName = currentUser?.displayName?.trim() || '';
  const userInitial = displayName
    ? Array.from(displayName)[0].toLocaleUpperCase()
    : 'U';

  useEffect(() => {
    const updateScrolled = () => {
      scrollFrame.current = null;
      const nextScrolled = window.scrollY > 20;
      setScrolled((current) => current === nextScrolled ? current : nextScrolled);
    };
    const onScroll = () => {
      if (scrollFrame.current === null) {
        scrollFrame.current = window.requestAnimationFrame(updateScrolled);
      }
    };

    updateScrolled();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (scrollFrame.current !== null) {
        window.cancelAnimationFrame(scrollFrame.current);
      }
    };
  }, []);

  useEffect(() => {
    setIsOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
        window.requestAnimationFrame(() => menuToggleRef.current?.focus());
      }
    };

    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [isOpen]);

  const handleLogout = async (focusTarget = null) => {
    if (isLoggingOut) return;
    const wasOnLandingPage = location.pathname === '/';
    logoutFocusTargetRef.current = focusTarget;
    setLogoutError('');
    setIsLoggingOut(true);
    logoutStatusRef.current?.focus({ preventScroll: true });
    try {
      await logout();
      navigate('/');
      if (wasOnLandingPage) {
        window.requestAnimationFrame(() => {
          const heading = document.querySelector('#main-content h1');
          if (!heading) return;
          if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1');
          heading.focus({ preventScroll: true });
        });
      }
    } catch (err) {
      console.error('Logout failed:', err);
      setLogoutError('Could not sign you out. Check your connection and try again.');
      if (document.activeElement === logoutStatusRef.current) {
        window.requestAnimationFrame(() => logoutFocusTargetRef.current?.focus());
      }
    } finally {
      setIsLoggingOut(false);
    }
  };

  const dismissLogoutError = () => {
    setLogoutError('');
    window.requestAnimationFrame(() => logoutFocusTargetRef.current?.focus());
  };

  const handleMobileLogout = (event) => {
    event.preventDefault();
    const focusTarget = menuToggleRef.current;
    setIsOpen(false);
    void handleLogout(focusTarget);
  };

  const closeMobileNavigation = (targetPath) => {
    const staysOnCurrentPage = location.pathname === targetPath;
    setIsOpen(false);
    if (staysOnCurrentPage) {
      window.requestAnimationFrame(() => menuToggleRef.current?.focus());
    }
  };

  return (
    <m.nav
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.18 }}
      aria-label="Primary navigation"
      className={`fixed w-full z-50 transition-all duration-500 ${scrolled
        ? 'section-dark shadow-lg'
        : 'navbar-at-top'
        }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <BrandLogo
            className="flex-shrink-0"
            tone={scrolled ? 'dark' : 'light'}
          />

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            <NavLink to="/" isActive={location.pathname === '/'} scrolled={scrolled}>
              Home
            </NavLink>
            {currentUser && (
              <NavLink to="/app" isActive={location.pathname === '/app'} scrolled={scrolled}>
                Dashboard
              </NavLink>
            )}
          </div>

          {/* Desktop Actions */}
          <div className="hidden md:flex items-center gap-3">
            {loading ? (
              <div
                className="h-9 w-40 rounded-full glass"
                role="status"
                aria-label="Checking account session"
              />
            ) : currentUser ? (
              <>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full glass text-sm">
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                    style={{ background: 'var(--accent)', color: '#FAF3E1' }}
                  >
                    {userInitial}
                  </div>
                  <span
                    style={{
                      color: scrolled ? 'var(--dark-text-secondary)' : 'var(--text-secondary)',
                      maxWidth: '7rem',
                    }}
                    className="truncate text-sm font-medium"
                    title={displayName || 'User'}
                  >
                    {displayName || 'User'}
                  </span>
                </div>
                <m.button
                  type="button"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={(event) => { void handleLogout(event.currentTarget); }}
                  disabled={isLoggingOut}
                  className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all"
                  style={{
                    color: scrolled ? 'var(--dark-text-secondary)' : 'var(--text-secondary)',
                    border: `1px solid ${scrolled ? 'var(--dark-border-subtle)' : 'var(--border-subtle)'}`,
                  }}
                >
                  <LogOut size={14} />
                  {isLoggingOut ? 'Signing out…' : 'Logout'}
                </m.button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-4 py-2 rounded-full text-sm font-medium transition-all duration-200"
                  style={{ color: scrolled ? 'var(--dark-text-secondary)' : 'var(--text-secondary)' }}
                >
                  Sign in
                </Link>
                <m.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Link
                    to="/signup"
                    className="px-5 py-2 rounded-full text-sm font-semibold text-white transition-all duration-200"
                    style={{ background: 'var(--accent)', color: 'var(--dark-text-primary)' }}
                  >
                    Get Started
                  </Link>
                </m.div>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <m.button
            ref={menuToggleRef}
            type="button"
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden p-2 rounded-lg"
            style={{ color: scrolled ? 'var(--dark-text-primary)' : 'var(--text-primary)' }}
            aria-expanded={isOpen}
            aria-controls="mobile-navigation"
            aria-label={isOpen ? 'Close navigation menu' : 'Open navigation menu'}
          >
            {isOpen ? <X size={22} /> : <Menu size={22} />}
          </m.button>
        </div>
      </div>

      <span
        ref={logoutStatusRef}
        className="sr-only"
        role="status"
        aria-live="polite"
        tabIndex={-1}
      >
        {isLoggingOut ? 'Signing you out…' : ''}
      </span>

      <AnimatePresence>
        {logoutError && (
          <m.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            role="alert"
            className="absolute left-4 right-4 top-full mt-2 flex items-start gap-3 rounded-xl p-3 text-sm shadow-xl glass-strong sm:left-auto sm:w-96"
            style={{ color: 'var(--error)', border: '1px solid var(--error)' }}
          >
            <span className="flex-1">{logoutError}</span>
            <button
              type="button"
              onClick={dismissLogoutError}
              className="shrink-0 rounded-md p-1"
              aria-label="Dismiss sign-out error"
            >
              <X size={15} aria-hidden="true" />
            </button>
          </m.div>
        )}
      </AnimatePresence>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isOpen && (
          <m.div
            id="mobile-navigation"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="md:hidden glass-strong border-t"
            style={{ borderColor: 'var(--border-subtle)' }}
          >
            <div className="px-4 py-4 space-y-2">
              <Link
                to="/"
                onClick={() => closeMobileNavigation('/')}
                aria-current={location.pathname === '/' ? 'page' : undefined}
                className="block px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
                style={{
                  color: location.pathname === '/' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: location.pathname === '/' ? 'var(--accent-glow)' : 'transparent',
                }}
              >
                Home
              </Link>
              {currentUser && (
                <Link
                  to="/app"
                  onClick={() => closeMobileNavigation('/app')}
                  aria-current={location.pathname === '/app' ? 'page' : undefined}
                  className="block px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
                  style={{
                    color: location.pathname === '/app' ? 'var(--text-primary)' : 'var(--text-secondary)',
                    background: location.pathname === '/app' ? 'var(--accent-glow)' : 'transparent',
                  }}
                >
                  Dashboard
                </Link>
              )}
              <div className="pt-2 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                {loading ? (
                  <p className="px-4 py-2.5 text-sm" role="status" style={{ color: 'var(--text-secondary)' }}>
                    Checking account…
                  </p>
                ) : currentUser ? (
                  <button
                    type="button"
                    onClick={handleMobileLogout}
                    disabled={isLoggingOut}
                    className="w-full flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium"
                    style={{ color: 'var(--error)' }}
                  >
                    <LogOut size={14} />
                    {isLoggingOut ? 'Signing out…' : 'Logout'}
                  </button>
                ) : (
                  <div className="space-y-2">
                    <Link
                      to="/login"
                      onClick={() => closeMobileNavigation('/login')}
                      className="block px-4 py-2.5 rounded-lg text-sm font-medium text-center"
                      style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
                    >
                      Sign in
                    </Link>
                    <Link
                      to="/signup"
                      onClick={() => closeMobileNavigation('/signup')}
                      className="block px-4 py-2.5 rounded-lg text-sm font-semibold text-white text-center"
                      style={{ background: 'var(--accent)', color: 'var(--dark-text-primary)' }}
                    >
                      Get Started
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </m.div>
        )}
      </AnimatePresence>
    </m.nav>
  );
};

export default Navbar;
