import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Loader2, CheckCircle, XCircle, AlertTriangle, RefreshCw } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker?url';
import { useAuth } from '../contexts/AuthContext';
import api from '../utils/api';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

// Admin credentials - in a real app, these would be stored securely
// and validated on the server side
const ADMIN_EMAIL = "admin@litmark.com";
const ADMIN_PASSWORD = "LitMark@Admin2024";

const AdminDashboard = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [diagnosticResults, setDiagnosticResults] = useState({});
  const [isRunningTests, setIsRunningTests] = useState(false);
  const navigate = useNavigate();
  const { currentUser } = useAuth();

  // Check if user is already authenticated
  useEffect(() => {
    const adminAuth = localStorage.getItem('adminAuth');
    if (adminAuth === 'true') {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = (e) => {
    e.preventDefault();
    setAuthError('');
    setIsLoading(true);

    // Simple admin authentication
    if (email === ADMIN_EMAIL && password === ADMIN_PASSWORD) {
      localStorage.setItem('adminAuth', 'true');
      setIsAuthenticated(true);
      setAuthError('');
    } else {
      setAuthError('Invalid credentials. Access denied.');
    }
    
    setIsLoading(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('adminAuth');
    setIsAuthenticated(false);
  };

  const runDiagnostics = async () => {
    setIsRunningTests(true);
    const results = {};
    
    // Get the API URL from environment variables or use a default
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const apiUrl = baseUrl.startsWith('http') ? baseUrl : `https://${baseUrl}`;
    
    // Test 1: Basic connectivity to the backend
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(apiUrl, {
        method: 'GET',
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      results.backendConnectivity = {
        status: response.status >= 200 && response.status < 500 ? 'success' : 'error',
        message: `Backend responded with status ${response.status}`,
        details: `URL: ${apiUrl}`
      };
    } catch (err) {
      results.backendConnectivity = {
        status: 'error',
        message: `Failed to connect to backend: ${err.message}`,
        details: `URL: ${apiUrl}`
      };
    }
    
    // Test 2: API Key verification endpoint
    try {
      const formData = new FormData();
      formData.append('api_key', 'TEST_KEY_FOR_DIAGNOSTICS');
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${apiUrl}/verify_api_key/`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      // We expect a 400 error because the API key is invalid, but the endpoint should exist
      results.apiKeyEndpoint = {
        status: response.status === 400 || response.status === 200 ? 'success' : 'error',
        message: `API key endpoint responded with status ${response.status}`,
        details: `Endpoint: ${apiUrl}/verify_api_key/`
      };
    } catch (err) {
      results.apiKeyEndpoint = {
        status: 'error',
        message: `Failed to connect to API key endpoint: ${err.message}`,
        details: `Endpoint: ${apiUrl}/verify_api_key/`
      };
    }
    
    // Test 3: Evaluation endpoint
    try {
      const formData = new FormData();
      formData.append('api_key', 'TEST_KEY_FOR_DIAGNOSTICS');
      const essayBlob = new Blob(['This is a test essay'], { type: 'text/plain' });
      formData.append('essay', essayBlob, 'test_essay.txt');
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${apiUrl}/evaluate/`, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      // We expect a 400 error because the API key is invalid, but the endpoint should exist
      results.evaluationEndpoint = {
        status: response.status === 400 || response.status === 200 ? 'success' : 'error',
        message: `Evaluation endpoint responded with status ${response.status}`,
        details: `Endpoint: ${apiUrl}/evaluate/`
      };
    } catch (err) {
      results.evaluationEndpoint = {
        status: 'error',
        message: `Failed to connect to evaluation endpoint: ${err.message}`,
        details: `Endpoint: ${apiUrl}/evaluate/`
      };
    }
    
    // Test 4: PDF.js library
    try {
      const testPdf = await pdfjsLib.getDocument({
        data: new Uint8Array([
          '%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 21 >>\nstream\nBT /F1 12 Tf 100 700 Td (Test PDF) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000010 00000 n\n0000000059 00000 n\n0000000118 00000 n\n0000000217 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n287\n%%EOF'
        ].join('\n'))
      }).promise;
      
      results.pdfLibrary = {
        status: 'success',
        message: 'PDF.js library is working correctly',
        details: `PDF.js version: ${pdfjsLib.version}`
      };
    } catch (err) {
      results.pdfLibrary = {
        status: 'error',
        message: `PDF.js library error: ${err.message}`,
        details: `PDF.js version: ${pdfjsLib.version}`
      };
    }
    
    // Test 5: Environment variables
    results.environmentVariables = {
      status: import.meta.env.VITE_API_URL ? 'success' : 'warning',
      message: import.meta.env.VITE_API_URL 
        ? `VITE_API_URL is set to: ${import.meta.env.VITE_API_URL}` 
        : 'VITE_API_URL is not set, using default: http://localhost:8000',
      details: 'Check your .env file or deployment environment variables'
    };
    
    // Test 6: Authentication status
    results.authentication = {
      status: currentUser ? 'success' : 'warning',
      message: currentUser 
        ? `Authenticated as: ${currentUser.email}` 
        : 'Not authenticated with Firebase',
      details: currentUser 
        ? `User ID: ${currentUser.uid}, Display Name: ${currentUser.displayName || 'N/A'}` 
        : 'Firebase authentication is available but no user is logged in'
    };
    
    setDiagnosticResults(results);
    setIsRunningTests(false);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-6 h-6 text-green-500" />;
      case 'error':
        return <XCircle className="w-6 h-6 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="w-6 h-6 text-yellow-500" />;
      default:
        return null;
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center p-4">
        {/* Animated background */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-20 animate-blob"></div>
          <div className="absolute top-40 -left-20 w-80 h-80 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        </div>
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-black/90 backdrop-blur-sm rounded-xl shadow-xl p-8 max-w-md w-full border border-[#0C2340]/50 relative z-10"
        >
          <h1 className="text-2xl font-bold text-center text-white mb-6">Admin Dashboard</h1>
          <p className="text-gray-400 mb-6 text-center">This area is restricted to administrators only.</p>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-gray-300 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full p-2 rounded-lg bg-black border border-[#0C2340] text-white focus:outline-none focus:ring-2 focus:ring-[#0C2340] focus:border-transparent"
                required
              />
            </div>
            <div>
              <label className="block text-gray-300 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full p-2 rounded-lg bg-black border border-[#0C2340] text-white focus:outline-none focus:ring-2 focus:ring-[#0C2340] focus:border-transparent"
                required
              />
            </div>
            
            {authError && (
              <p className="text-red-500 text-sm">{authError}</p>
            )}
            
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2 bg-[#0C2340] hover:bg-[#0D2A4D] rounded-lg text-white font-medium transition-colors"
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  Authenticating...
                </span>
              ) : (
                'Access Dashboard'
              )}
            </button>
          </form>
          
          <div className="mt-6 text-center">
            <button
              onClick={() => navigate('/')}
              className="text-gray-400 hover:text-white text-sm"
            >
              Return to Home
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black p-6">
      {/* Subtle animated background for the dashboard */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-10 animate-blob"></div>
        <div className="absolute bottom-40 left-20 w-80 h-80 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-10 animate-blob animation-delay-4000"></div>
      </div>
      
      <div className="max-w-6xl mx-auto relative z-10">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-white">LitMark Admin Dashboard</h1>
          <button
            onClick={handleLogout}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white"
          >
            Logout
          </button>
        </div>
        
        <div className="bg-black/80 backdrop-blur-sm rounded-xl shadow-xl p-6 border border-[#0C2340]/50 mb-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-white">System Diagnostics</h2>
            <button
              onClick={runDiagnostics}
              disabled={isRunningTests}
              className="px-4 py-2 bg-[#0C2340] hover:bg-[#0D2A4D] rounded-lg text-white flex items-center"
            >
              {isRunningTests ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                  Running Tests...
                </>
              ) : (
                <>
                  <RefreshCw className="w-5 h-5 mr-2" />
                  Run Diagnostics
                </>
              )}
            </button>
          </div>
          
          {Object.keys(diagnosticResults).length === 0 ? (
            <p className="text-gray-400">Click "Run Diagnostics" to check system status.</p>
          ) : (
            <div className="space-y-4">
              {Object.entries(diagnosticResults).map(([key, result]) => (
                <div key={key} className="bg-gray-700/50 rounded-lg p-4">
                  <div className="flex items-start">
                    <div className="mr-3 mt-1">
                      {getStatusIcon(result.status)}
                    </div>
                    <div>
                      <h3 className="text-white font-medium capitalize">
                        {key.replace(/([A-Z])/g, ' $1').trim()}
                      </h3>
                      <p className={`text-${result.status === 'success' ? 'green' : result.status === 'warning' ? 'yellow' : 'red'}-400`}>
                        {result.message}
                      </p>
                      <p className="text-gray-400 text-sm mt-1">{result.details}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        <div className="bg-black/80 backdrop-blur-sm rounded-xl shadow-xl p-6 border border-[#0C2340]/50">
          <h2 className="text-xl font-bold text-white mb-4">System Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-700/50 rounded-lg p-4">
              <h3 className="text-white font-medium">API URL</h3>
              <p className="text-blue-400 font-mono break-all">
                {import.meta.env.VITE_API_URL || 'http://localhost:8000'}
              </p>
            </div>
            <div className="bg-gray-700/50 rounded-lg p-4">
              <h3 className="text-white font-medium">Environment</h3>
              <p className="text-blue-400">
                {import.meta.env.MODE || 'development'}
              </p>
            </div>
            <div className="bg-gray-700/50 rounded-lg p-4">
              <h3 className="text-white font-medium">Build Time</h3>
              <p className="text-blue-400">
                {new Date().toLocaleString()}
              </p>
            </div>
            <div className="bg-gray-700/50 rounded-lg p-4">
              <h3 className="text-white font-medium">Browser</h3>
              <p className="text-blue-400">
                {navigator.userAgent}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard; 