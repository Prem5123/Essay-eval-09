import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X, LogOut, User } from 'lucide-react';
import logoSvg from '../assets/images/Litmark.png';

const NavLink = ({ to, children, isActive, onClick }) => (
  <Link
    to={to}
    onClick={onClick}
    className="relative px-4 py-2 text-sm font-medium transition-colors duration-200"
    style={{ color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)' }}
  >
    {children}
    {isActive && (
      <motion.div
        layoutId="nav-indicator"
        className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
        style={{ background: 'var(--accent)' }}
        transition={{ type: 'spring', stiffness: 500, damping: 35 }}
      />
    )}
  </Link>
);

const Navbar = () => {
  const { currentUser, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/');
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ type: 'spring', stiffness: 200, damping: 30 }}
      className={`fixed w-full z-50 transition-all duration-500 ${scrolled
          ? 'glass-strong shadow-glow'
          : 'bg-transparent'
        }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link
            to="/"
            className="flex-shrink-0 group flex items-center gap-2"
          >
            <motion.img
              src={logoSvg}
              alt="LitMark"
              className="h-8 md:h-9 w-auto"
              whileHover={{ scale: 1.05 }}
              transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            />
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex items-center gap-1">
            <NavLink to="/" isActive={location.pathname === '/'}>
              Home
            </NavLink>
            {currentUser && (
              <NavLink to="/app" isActive={location.pathname === '/app'}>
                Dashboard
              </NavLink>
            )}
          </div>

          {/* Desktop Actions */}
          <div className="hidden md:flex items-center gap-3">
            {currentUser ? (
              <>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full glass text-sm">
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                    style={{ background: 'var(--accent)', color: 'white' }}
                  >
                    {currentUser.displayName
                      ? currentUser.displayName.charAt(0).toUpperCase()
                      : 'U'}
                  </div>
                  <span style={{ color: 'var(--text-secondary)' }} className="text-sm font-medium">
                    {currentUser.displayName || 'User'}
                  </span>
                </div>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleLogout}
                  className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all"
                  style={{
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <LogOut size={14} />
                  Logout
                </motion.button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-4 py-2 rounded-full text-sm font-medium transition-all duration-200"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Sign in
                </Link>
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Link
                    to="/signup"
                    className="px-5 py-2 rounded-full text-sm font-semibold text-white transition-all duration-200"
                    style={{ background: 'var(--accent)' }}
                  >
                    Get Started
                  </Link>
                </motion.div>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden p-2 rounded-lg"
            style={{ color: 'var(--text-secondary)' }}
          >
            {isOpen ? <X size={22} /> : <Menu size={22} />}
          </motion.button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="md:hidden glass-strong border-t"
            style={{ borderColor: 'var(--border-subtle)' }}
          >
            <div className="px-4 py-4 space-y-2">
              <Link
                to="/"
                onClick={() => setIsOpen(false)}
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
                  onClick={() => setIsOpen(false)}
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
                {currentUser ? (
                  <button
                    onClick={() => { handleLogout(); setIsOpen(false); }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium"
                    style={{ color: 'var(--error)' }}
                  >
                    <LogOut size={14} />
                    Logout
                  </button>
                ) : (
                  <div className="space-y-2">
                    <Link
                      to="/login"
                      onClick={() => setIsOpen(false)}
                      className="block px-4 py-2.5 rounded-lg text-sm font-medium text-center"
                      style={{ color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
                    >
                      Sign in
                    </Link>
                    <Link
                      to="/signup"
                      onClick={() => setIsOpen(false)}
                      className="block px-4 py-2.5 rounded-lg text-sm font-semibold text-white text-center"
                      style={{ background: 'var(--accent)' }}
                    >
                      Get Started
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
};

export default Navbar;