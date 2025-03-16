import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { currentUser, logout } = useAuth();
  const location = useLocation();

  // Handle scroll effect
  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 10) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu when route changes
  useEffect(() => {
    setIsOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Failed to log out', error);
    }
  };

  return (
    <nav 
      className={`fixed w-full z-50 transition-all duration-300 ${
        scrolled 
          ? 'bg-gray-900/90 backdrop-blur-md shadow-lg' 
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="flex-shrink-0">
              <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">
                LitMark
              </h1>
            </Link>
          </div>
          
          {/* Desktop menu */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-center space-x-4">
              <Link
                to="/"
                className={`px-3 py-2 rounded-md text-sm font-medium ${
                  location.pathname === '/' 
                    ? 'text-white bg-gray-800/50' 
                    : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
                } transition-colors duration-300`}
              >
                Home
              </Link>
              
              {currentUser ? (
                <>
                  <Link
                    to="/app"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      location.pathname === '/app' 
                        ? 'text-white bg-gray-800/50' 
                        : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
                    } transition-colors duration-300`}
                  >
                    Dashboard
                  </Link>
                  
                  <button
                    onClick={handleLogout}
                    className="px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors duration-300"
                  >
                    Logout
                  </button>
                  
                  <div className="flex items-center ml-3">
                    <div className="bg-gradient-to-r from-blue-500 to-purple-500 p-0.5 rounded-full">
                      <div className="bg-gray-800 rounded-full p-0.5">
                        <span className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-gray-800 text-white">
                          {currentUser.name ? currentUser.name.charAt(0).toUpperCase() : 'U'}
                        </span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <Link
                    to="/login"
                    className="px-3 py-2 rounded-md text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors duration-300"
                  >
                    Login
                  </Link>
                  
                  <Link
                    to="/signup"
                    className="px-4 py-2 rounded-md text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 transition-colors duration-300"
                  >
                    Sign Up
                  </Link>
                </>
              )}
            </div>
          </div>
          
          {/* Mobile menu button */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-white hover:bg-gray-700/50 focus:outline-none"
              aria-expanded="false"
            >
              <span className="sr-only">Open main menu</span>
              {isOpen ? (
                <svg
                  className="block h-6 w-6"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              ) : (
                <svg
                  className="block h-6 w-6"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <div
        className={`${
          isOpen ? 'block' : 'hidden'
        } md:hidden bg-gray-900/95 backdrop-blur-md shadow-lg transition-all duration-300`}
      >
        <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
          <Link
            to="/"
            className={`block px-3 py-2 rounded-md text-base font-medium ${
              location.pathname === '/' 
                ? 'text-white bg-gray-800/50' 
                : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
            } transition-colors duration-300`}
          >
            Home
          </Link>
          
          {currentUser ? (
            <>
              <Link
                to="/app"
                className={`block px-3 py-2 rounded-md text-base font-medium ${
                  location.pathname === '/app' 
                    ? 'text-white bg-gray-800/50' 
                    : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
                } transition-colors duration-300`}
              >
                Dashboard
              </Link>
              
              <button
                onClick={handleLogout}
                className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors duration-300"
              >
                Logout
              </button>
              
              <div className="px-3 py-2 flex items-center">
                <div className="bg-gradient-to-r from-blue-500 to-purple-500 p-0.5 rounded-full">
                  <div className="bg-gray-800 rounded-full p-0.5">
                    <span className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-gray-800 text-white">
                      {currentUser.name ? currentUser.name.charAt(0).toUpperCase() : 'U'}
                    </span>
                  </div>
                </div>
                <span className="ml-3 text-gray-300">{currentUser.name || currentUser.email}</span>
              </div>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="block px-3 py-2 rounded-md text-base font-medium text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors duration-300"
              >
                Login
              </Link>
              
              <Link
                to="/signup"
                className="block px-3 py-2 rounded-md text-base font-medium text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 transition-colors duration-300"
              >
                Sign Up
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar; 