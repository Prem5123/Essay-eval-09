import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Loader2, X, Plus, Download } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker?url';
import CryptoJS from 'crypto-js';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';

// Pages
import LandingPage from './pages/LandingPage';
import Login from './pages/Login';
import Signup from './pages/Signup';
import ManualLogin from './pages/ManualLogin';
import Navbar from './components/Navbar';

// Original App component renamed to EssayEvaluator
import EssayEvaluator from './components/EssayEvaluator';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

const AnimatedBackground = () => (
  <div className="absolute inset-0 bg-gradient-to-br from-gray-900 to-black" />
);

const FloatingCard = ({ children, delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 50 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5, delay }}
    className="bg-gray-800/80 backdrop-blur-lg rounded-xl shadow-xl p-6 border border-gray-700/50"
  >
    {children}
  </motion.div>
);

const AnimatedHeading = () => (
  <motion.h1
    initial={{ opacity: 0, y: -50 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.8 }}
    className="text-5xl md:text-6xl font-bold text-center text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500"
  >
    Essay Evaluator
  </motion.h1>
);

const FileUploadCard = ({ files, setFiles }) => {
  const [isDragging, setIsDragging] = useState(false);
  const MAX_FILES = 10;

  const validateFile = (file) => {
    if (file.size === 0) {
      alert(`Cannot read an empty file: "${file.name}". Please upload a file with content.`);
      return false;
    }
    return true;
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const newFiles = Array.from(e.dataTransfer.files).filter(validateFile);
    if (newFiles.length === 0) return;
    if (newFiles.some((f) => f.type === 'application/pdf')) {
      alert('For PDFs, only one file is allowed.');
      setFiles([newFiles[0]]);
    } else if (files.length < MAX_FILES) {
      const availableSlots = MAX_FILES - files.length;
      const filesToAdd = newFiles.slice(0, availableSlots);
      setFiles([...files, ...filesToAdd]);
    }
  };

  const addFiles = (e) => {
    const newFiles = Array.from(e.target.files).filter(validateFile);
    if (newFiles.length === 0) return;
    if (newFiles.some((f) => f.type === 'application/pdf')) {
      alert('For PDFs, only one file is allowed.');
      setFiles([newFiles[0]]);
    } else if (files.length < MAX_FILES) {
      const availableSlots = MAX_FILES - files.length;
      const filesToAdd = newFiles.slice(0, availableSlots);
      setFiles([...files, ...filesToAdd]);
    }
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <motion.div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-8 transition-all duration-300
          ${isDragging ? 'border-green-400 bg-green-400/10' : 'border-gray-600'}
          ${files.length > 0 ? 'bg-green-500/10 border-green-500' : ''}
          ${files.length >= MAX_FILES ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <div className="flex flex-col items-center space-y-4">
          <motion.div whileHover={{ rotate: 180, scale: 1.1 }} transition={{ duration: 0.3 }}>
            <Upload className="w-16 h-16 text-green-400" />
          </motion.div>
          <p className="text-gray-300">
            {files.length >= MAX_FILES
              ? `Maximum number of files (${MAX_FILES}) reached`
              : `Drag and drop your essay files here, or click to select (${files.length}/${MAX_FILES})`}
          </p>
          <motion.label
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`px-4 py-2 bg-green-500 rounded-full cursor-pointer ${files.length >= MAX_FILES ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <input
              type="file"
              onChange={addFiles}
              className="hidden"
              accept=".txt,.doc,.docx,.pdf"
              multiple
              disabled={files.length >= MAX_FILES}
            />
            <Plus className="inline w-5 h-5 mr-2" /> Add Essays
          </motion.label>
        </div>
      </motion.div>
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2 max-h-64 overflow-y-auto pr-2"
          >
            {files.map((file, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg"
              >
                <div className="flex items-center space-x-2">
                  <FileText className="w-5 h-5 text-green-400" />
                  <span className="text-gray-200 truncate max-w-xs">{file.name}</span>
                </div>
                <motion.button
                  whileHover={{ scale: 1.1, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => removeFile(index)}
                  className="p-1 hover:bg-red-500/20 rounded-full"
                >
                  <X className="w-5 h-5 text-red-400" />
                </motion.button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const ResultItem = ({ result, onDownload }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -20 }}
    className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg border border-gray-600"
  >
    <div className="flex items-center space-x-4">
      <FileText className="w-6 h-6 text-green-400" />
      <div>
        <p className="text-gray-200 font-medium">{result.filename}</p>
        <p className="text-green-400 font-bold">Score: {result.score}/30</p>
      </div>
    </div>
    <motion.button
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      onClick={onDownload}
      className="p-2 bg-green-500/20 hover:bg-green-500/40 rounded-full"
    >
      <Download className="w-5 h-5 text-green-400" />
    </motion.button>
  </motion.div>
);

const extractScoreFromPdf = async (blob) => {
  const url = URL.createObjectURL(blob);
  const pdf = await pdfjsLib.getDocument(url).promise;
  const page = await pdf.getPage(1);
  const textContent = await page.getTextContent();
  const text = textContent.items.map((item) => item.str).join(' ');
  const scoreMatch = text.match(/Score: (\d+)\/30/);
  URL.revokeObjectURL(url);
  return scoreMatch ? parseInt(scoreMatch[1]) : 0;
};

// Protected route component
const ProtectedRoute = ({ children }) => {
  const { currentUser } = useAuth();
  
  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

const App = () => {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/manual-login" element={<ManualLogin />} />
        <Route 
          path="/app" 
          element={
            <ProtectedRoute>
              <EssayEvaluator />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </>
  );
};

export default App;