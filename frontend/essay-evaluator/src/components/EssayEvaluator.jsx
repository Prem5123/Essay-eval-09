import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Loader2, X, Plus, Download, Check, RefreshCw } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker?url';
import CryptoJS from 'crypto-js';
import { storeApiKey, retrieveApiKey, removeApiKey, hasStoredApiKey } from '../utils/apiKeyStorage';
import { useAuth } from '../contexts/AuthContext';
import presetRubrics from '../utils/presetRubrics';
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

// Define a CSS variable for navy-blue color if it's not already defined in your tailwind config
// This ensures the color is available throughout this component
const navyBlueStyle = {
  "--navy-blue": "#1a365d", // Deep navy blue color
  "--navy-blue-light": "#2a4a7f"
};

const AnimatedBackground = () => (
  <div className="absolute inset-0 bg-black">
    <div className="absolute inset-0 opacity-20">
      <div className="absolute top-0 -left-4 w-96 h-96 bg-navy-blue/30 rounded-full filter blur-3xl"></div>
      <div className="absolute bottom-0 right-10 w-96 h-96 bg-navy-blue/40 rounded-full filter blur-3xl"></div>
    </div>
  </div>
);

const FloatingCard = ({ children, delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 50 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5, delay }}
    className="bg-black/70 backdrop-blur-lg rounded-xl shadow-xl p-6 border border-navy-blue/50"
  >
    {children}
  </motion.div>
);

const AnimatedHeading = () => (
  <motion.h1
    initial={{ opacity: 0, y: -50 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.8 }}
    className="text-5xl md:text-6xl font-bold text-center text-transparent bg-clip-text bg-gradient-to-r from-navy-blue to-blue-400"
  >
    LitMark
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
          ${isDragging ? 'border-navy-blue bg-navy-blue/10' : 'border-gray-600'}
          ${files.length > 0 ? 'bg-navy-blue/10 border-navy-blue' : ''}
          ${files.length >= MAX_FILES ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <div className="flex flex-col items-center space-y-4">
          <motion.div whileHover={{ rotate: 180, scale: 1.1 }} transition={{ duration: 0.3 }}>
            <Upload className="w-16 h-16 text-navy-blue" />
          </motion.div>
          <p className="text-white">
            {files.length >= MAX_FILES
              ? `Maximum number of files (${MAX_FILES}) reached`
              : `Drag and drop your essay files here, or click to select (${files.length}/${MAX_FILES})`}
          </p>
          <motion.label
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`px-4 py-2 bg-navy-blue rounded-full cursor-pointer ${files.length >= MAX_FILES ? 'opacity-50 pointer-events-none' : ''}`}
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
                  <FileText className="w-5 h-5 text-navy-blue" />
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
      <FileText className="w-6 h-6 text-navy-blue" />
      <div>
        <p className="text-gray-200 font-medium">{result.filename}</p>
        <p className="text-navy-blue font-bold">Score: {result.score}/{result.totalMark}</p>
      </div>
    </div>
    <motion.button
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      onClick={onDownload}
      className="p-2 bg-navy-blue/20 hover:bg-navy-blue/40 rounded-full"
    >
      <Download className="w-5 h-5 text-navy-blue" />
    </motion.button>
  </motion.div>
);

const extractScoreFromPdf = async (blob) => {
  const url = URL.createObjectURL(blob);
  const pdf = await pdfjsLib.getDocument(url).promise;
  const page = await pdf.getPage(1);
  const textContent = await page.getTextContent();
  const text = textContent.items.map((item) => item.str).join(' ');
  
  // Extract both score and total mark from the PDF
  const scoreMatch = text.match(/Overall Score: (\d+\.?\d*)\/(\d+)/);
  URL.revokeObjectURL(url);
  
  if (scoreMatch) {
    return {
      score: parseFloat(scoreMatch[1]),
      totalMark: parseInt(scoreMatch[2])
    };
  }
  
  // Fallback to old pattern if new pattern not found
  const oldScoreMatch = text.match(/Score: (\d+\.?\d*)\/(\d+)/);
  if (oldScoreMatch) {
    return {
      score: parseFloat(oldScoreMatch[1]),
      totalMark: parseInt(oldScoreMatch[2])
    };
  }
  
  return { score: 0, totalMark: 30 }; // Default fallback
};

const EssayEvaluator = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [files, setFiles] = useState([]);
  const [essayText, setEssayText] = useState('');
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');
  const [processingFile, setProcessingFile] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [isApiKeyVerified, setIsApiKeyVerified] = useState(false);
  const [encryptionKey] = useState(CryptoJS.lib.WordArray.random(16).toString());
  const [rubricText, setRubricText] = useState('');
  const [rubricFile, setRubricFile] = useState(null);
  const [selectedPresetRubric, setSelectedPresetRubric] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const { currentUser } = useAuth();

  // Load API key from storage when component mounts or user changes
  useEffect(() => {
    if (currentUser) {
      const storedApiKey = retrieveApiKey(currentUser.uid);
      if (storedApiKey) {
        setApiKey(storedApiKey);
        // We don't automatically set isApiKeyVerified to true
        // The user should verify the key explicitly
      }
    }
  }, [currentUser]);

  const handleApiKeyChange = (e) => {
    const key = e.target.value;
    setApiKey(key);
    setIsApiKeyVerified(false);
    
    // Store the API key if the user is logged in
    if (currentUser) {
      storeApiKey(key, currentUser.uid);
    }
  };

  const handleClearApiKey = () => {
    if (window.confirm('Are you sure you want to clear your API key?')) {
      setApiKey('');
      setIsApiKeyVerified(false);
      
      // Remove the API key from storage if the user is logged in
      if (currentUser) {
        removeApiKey(currentUser.uid);
      }
    }
  };

  const handlePresetRubricChange = (e) => {
    const selectedId = e.target.value;
    setSelectedPresetRubric(selectedId);
    
    if (selectedId) {
      const preset = presetRubrics.find(rubric => rubric.id === selectedId);
      if (preset) {
        setRubricText(preset.content);
        setRubricFile(null); // Clear any uploaded file
      }
    } else {
      // If "None" is selected, clear the rubric text
      setRubricText('');
    }
  };

  const handleVerifyApiKey = async () => {
    setError(null);
    
    // Basic validation
    if (!apiKey.trim()) {
      setError('Please enter an API key to verify.');
      return;
    }
    
    // Check if it looks like a Gemini API key
    if (!apiKey.trim().startsWith('AI')) {
      setError('This doesn\'t look like a valid Gemini API key. Gemini API keys typically start with "AI".');
      return;
    }
    
    // Ensure we have the correct URL format
    let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    
    // Make sure the URL has the https:// prefix
    if (!baseUrl.startsWith('http')) {
      baseUrl = 'https://' + baseUrl;
    }
    
    const apiUrl = `${baseUrl}/verify_api_key/`;
    console.log(`Verifying API key using endpoint: ${apiUrl}`);
    
    try {
      const formData = new FormData();
      formData.append('api_key', apiKey);
      
      // Add a timeout to the fetch request
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
      
      // Use the API utility instead of hardcoded URL
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
        signal: controller.signal,
        headers: {
          'Accept': 'application/json'
        }
      });
      
      clearTimeout(timeoutId);
      console.log(`Response status: ${response.status}`);
      
      if (response.ok) {
        const data = await response.json();
        console.log('API key verification successful:', data);
        setIsApiKeyVerified(true);
        setError(null);
        alert('API key verified successfully!');
      } else {
        let errorMessage = 'Invalid API key. Please check and try again.';
        
        // Handle 404 errors specifically
        if (response.status === 404) {
          errorMessage = `API endpoint not found (404). Please check your backend URL configuration: ${baseUrl}`;
          console.error('404 error - API endpoint not found');
        } else if (response.status === 405) {
          errorMessage = `Method not allowed (405). The API endpoint exists but doesn't accept this request method.`;
          console.error('405 error - Method not allowed');
        } else {
          // For other errors, try to parse the JSON response
          try {
            // Clone the response before reading it
            const clonedResponse = response.clone();
            const errorData = await clonedResponse.json();
            errorMessage = errorData.detail || errorMessage;
            console.error('API key verification failed:', errorData);
            
            // Provide more helpful guidance based on error
            if (errorMessage.includes('invalid API key') || errorMessage.includes('Invalid API key')) {
              errorMessage += ' Make sure you\'re using a key from Google AI Studio (https://aistudio.google.com/app/apikey).';
            }
          } catch (parseError) {
            console.error('Failed to parse error response as JSON:', parseError);
            
            // Only try to read as text if JSON parsing failed
            try {
              const textResponse = response.clone();
              const errorText = await textResponse.text();
              console.error('Error response text:', errorText);
            } catch (textError) {
              console.error('Failed to get error response text:', textError);
            }
          }
        }
        
        setIsApiKeyVerified(false);
        setError(errorMessage);
      }
    } catch (err) {
      console.error('Network error during API key verification:', err);
      setIsApiKeyVerified(false);
      setError(`Failed to verify API key: ${err.message}. Please check your internet connection and backend URL configuration.`);
    }
  };

  const handleRubricUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || file.size === 0) {
      setError('Cannot read an empty rubric file. Please upload a valid file.');
      return;
    }
    
    // Check if file is PDF or TXT
    const fileExt = file.name.split('.').pop().toLowerCase();
    if (fileExt !== 'pdf' && fileExt !== 'txt') {
      setError('Only PDF and TXT files are supported for rubrics.');
      return;
    }
    
    setRubricFile(file);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      // Ensure we have the correct URL format
      let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      
      // Make sure the URL has the https:// prefix
      if (!baseUrl.startsWith('http')) {
        baseUrl = 'https://' + baseUrl;
      }
      
      // Use the new dedicated endpoint for rubric file uploads
      const response = await fetch(`${baseUrl}/upload-rubric-file/`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to extract rubric text');
      }
      
      const data = await response.json();
      setRubricText(data.text);
    } catch (err) {
      setError(err.message || 'Failed to process rubric file');
    }
  };

  const handleSubmit = async () => {
    try {
      setError(null);
      if (!apiKey.trim()) throw new Error('Please enter your Gemini API key.');
      if (!isApiKeyVerified) throw new Error('Please verify your API key first.');
      if (activeTab === 'upload' && files.length === 0) {
        throw new Error('Please upload at least one essay file.');
      }
      if (activeTab === 'paste' && !essayText.trim()) {
        throw new Error('Please enter your essay text.');
      }
      
      // Ensure we have the correct URL format
      let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      
      // Make sure the URL has the https:// prefix
      if (!baseUrl.startsWith('http')) {
        baseUrl = 'https://' + baseUrl;
      }
      
      // Prepare common form data
      const prepareFormData = () => {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        
        // Handle rubric - either use text or rubric file
        if (rubricText && rubricText.trim()) {
          formData.append('rubric_text', rubricText.trim());
        }
        
        return formData;
      };
      
      if (activeTab === 'upload') {
        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          setProcessingFile(file.name);
          setIsLoading(true);
          
          const formData = prepareFormData();
          formData.append('essay', file);
          
          const response = await fetch(`${baseUrl}/evaluate/`, {
            method: 'POST',
            body: formData,
          });
          
          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Failed to evaluate ${file.name}`);
          }
          
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const scoreData = await extractScoreFromPdf(blob);
          
          setResults((prev) => [
            ...prev,
            { 
              id: Date.now() + i, 
              filename: file.name, 
              url, 
              score: scoreData.score,
              totalMark: scoreData.totalMark 
            },
          ]);
        }
      } else {
        setIsLoading(true);
        setProcessingFile('Pasted essay');
        
        const formData = prepareFormData();
        const essayBlob = new Blob([essayText], { type: 'text/plain' });
        formData.append('essay', essayBlob, 'essay.txt');
        
        const response = await fetch(`${baseUrl}/evaluate/`, {
          method: 'POST',
          body: formData,
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to evaluate essay');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const scoreData = await extractScoreFromPdf(blob);
        
        setResults((prev) => [
          ...prev,
          { 
            id: Date.now(), 
            filename: 'Pasted essay', 
            url, 
            score: scoreData.score,
            totalMark: scoreData.totalMark 
          },
        ]);
        
        setEssayText('');
      }
    } catch (err) {
      setError(err.message || 'An error occurred while evaluating the essay.');
    } finally {
      setIsLoading(false);
      setProcessingFile(null);
    }
  };

  const handleDownload = (url, filename) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename.split('.')[0]}_evaluation.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="min-h-screen relative overflow-hidden pt-16" style={navyBlueStyle}>
      <AnimatedBackground />
      <div className="relative z-10 p-8">
        <div className="mb-12">
          <AnimatedHeading />
          <motion.p className="text-center text-white text-xl mt-4">
            AI based essay evaluator
          </motion.p>
        </div>
        <div className="max-w-4xl mx-auto space-y-8">
          <FloatingCard>
            <label className="block text-white mb-2">Gemini API Key</label>
            <div className="flex flex-col space-y-2">
              <div className="flex items-center space-x-4">
                <div className="relative flex-grow">
                  <input
                    type={showApiKey ? "text" : "password"}
                    value={apiKey}
                    onChange={handleApiKeyChange}
                    placeholder="Enter your Gemini API key"
                    className="w-full p-2 rounded-lg bg-black/80 border border-navy-blue focus:border-blue-400 text-white pr-10"
                  />
                  {apiKey && (
                    <button
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white"
                      title={showApiKey ? "Hide API key" : "Show API key"}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        {showApiKey ? (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        ) : (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        )}
                      </svg>
                    </button>
                  )}
                </div>
                <div className="flex space-x-2">
                  <motion.button
                    onClick={handleVerifyApiKey}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className="px-4 py-2 bg-navy-blue rounded-full flex items-center"
                    title="Verify API key"
                  >
                    {isApiKeyVerified ? <Check className="w-4 h-4 mr-1" /> : <RefreshCw className="w-4 h-4 mr-1" />}
                    Verify
                  </motion.button>
                  {apiKey && (
                    <motion.button
                      onClick={handleClearApiKey}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      className="px-4 py-2 bg-red-500 rounded-full"
                      title="Clear API key"
                    >
                      <X className="w-4 h-4" />
                    </motion.button>
                  )}
                </div>
              </div>
              <div className="flex justify-between items-center">
                <p className="text-xs text-gray-400">
                  Get your API key from <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-navy-blue hover:underline">Google AI Studio</a>. 
                  Make sure to use a valid Gemini API key that starts with "AI".
                </p>
                {currentUser ? (
                  <p className="text-xs text-gray-400">
                    {hasStoredApiKey(currentUser.uid) ? 
                      "Your API key is securely stored" : 
                      "Your API key will be securely stored"}
                  </p>
                ) : (
                  <p className="text-xs text-gray-400">
                    <a href="/login" className="text-navy-blue hover:underline">Log in</a> to securely store your API key
                  </p>
                )}
              </div>
              {isApiKeyVerified && <p className="text-navy-blue mt-2">API Key Verified ✓</p>}
            </div>
          </FloatingCard>
          <div className="flex justify-center space-x-4 mb-6">
            <motion.button
              onClick={() => setActiveTab('upload')}
              className={`px-6 py-2 rounded-full transition-colors ${activeTab === 'upload' ? 'bg-navy-blue text-white' : 'bg-gray-700/50 text-gray-300'}`}
            >
              Upload Essays
            </motion.button>
            <motion.button
              onClick={() => setActiveTab('paste')}
              className={`px-6 py-2 rounded-full transition-colors ${activeTab === 'paste' ? 'bg-navy-blue text-white' : 'bg-gray-700/50 text-gray-300'}`}
            >
              Paste Text
            </motion.button>
            <motion.button
              onClick={() => setActiveTab('rubric')}
              className={`px-6 py-2 rounded-full transition-colors ${activeTab === 'rubric' ? 'bg-navy-blue text-white' : 'bg-gray-700/50 text-gray-300'}`}
            >
              Rubric
            </motion.button>
          </div>
          <AnimatePresence mode="wait">
            {activeTab === 'upload' ? (
              <motion.div key="upload" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
                <FloatingCard><FileUploadCard files={files} setFiles={setFiles} /></FloatingCard>
              </motion.div>
            ) : activeTab === 'paste' ? (
              <motion.div key="paste" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <FloatingCard>
                  <motion.textarea
                    value={essayText}
                    onChange={(e) => setEssayText(e.target.value)}
                    placeholder="Paste your essay here..."
                    className="w-full h-64 p-4 rounded-xl bg-gray-900/50 border border-gray-700 focus:border-navy-blue focus:ring-2 focus:ring-navy-blue/50 transition-all duration-300 resize-none text-white"
                    whileFocus={{ scale: 1.02 }}
                  />
                </FloatingCard>
              </motion.div>
            ) : (
              <motion.div key="rubric" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <FloatingCard>
                  <div className="space-y-6">
                    <div>
                      <label className="block text-gray-300 mb-2">Select Preset Rubric</label>
                      <select
                        value={selectedPresetRubric}
                        onChange={handlePresetRubricChange}
                        className="w-full p-2 rounded-lg bg-gray-900/50 border border-gray-700 focus:border-navy-blue text-white"
                      >
                        <option value="">None (Custom Rubric)</option>
                        {presetRubrics.map(rubric => (
                          <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
                        ))}
                      </select>
                      {selectedPresetRubric && (
                        <p className="mt-2 text-sm text-navy-blue">
                          Using preset: {presetRubrics.find(r => r.id === selectedPresetRubric)?.name}
                        </p>
                      )}
                    </div>
                    
                    <div className="border-t border-gray-700 pt-4">
                      <label className="block text-gray-300 mb-2">Upload Rubric File</label>
                      <div className="flex items-center space-x-2">
                        <input
                          type="file"
                          onChange={handleRubricUpload}
                          accept=".pdf,.txt"
                          className="w-full p-2 rounded-lg bg-gray-900/50 border border-gray-700 text-white"
                        />
                        <div className="flex space-x-1">
                          <span className="px-2 py-1 bg-gray-700 rounded text-xs text-white">PDF</span>
                          <span className="px-2 py-1 bg-gray-700 rounded text-xs text-white">TXT</span>
                        </div>
                      </div>
                      {rubricFile && <p className="mt-2 text-gray-300">Selected: {rubricFile.name}</p>}
                    </div>
                    
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <label className="block text-gray-300">Rubric Content</label>
                        {rubricText && (
                          <motion.button
                            onClick={() => {
                              setRubricText('');
                              setRubricFile(null);
                              setSelectedPresetRubric('');
                            }}
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            className="text-xs px-2 py-1 bg-red-500/20 hover:bg-red-500/40 text-red-400 rounded-full"
                          >
                            Clear
                          </motion.button>
                        )}
                      </div>
                      <textarea
                        value={rubricText}
                        onChange={(e) => {
                          setRubricText(e.target.value);
                          // If user manually edits the text, clear the preset selection
                          if (selectedPresetRubric) {
                            const preset = presetRubrics.find(r => r.id === selectedPresetRubric);
                            if (preset && e.target.value !== preset.content) {
                              setSelectedPresetRubric('');
                            }
                          }
                        }}
                        className="w-full h-64 p-4 rounded-xl bg-gray-900/50 border border-gray-700 focus:border-navy-blue focus:ring-2 focus:ring-navy-blue/50 transition-all duration-300 resize-none text-white"
                        placeholder="Paste your rubric here, upload a file above, or select a preset..."
                      />
                    </div>
                  </div>
                </FloatingCard>
              </motion.div>
            )}
          </AnimatePresence>
          <motion.div className="flex justify-center" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 }}>
            <motion.button
              onClick={handleSubmit}
              disabled={
                isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim())
              }
              className={`w-full py-3 rounded-full font-medium text-center transition-all duration-300 ${
                isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim())
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-navy-blue hover:bg-blue-600 text-white cursor-pointer'
              }`}
            >
              <span className="flex items-center gap-2">
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Processing {processingFile ? `"${processingFile}"` : '...'}</span>
                  </>
                ) : (
                  'Evaluate Essays'
                )}
              </span>
            </motion.button>
          </motion.div>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="max-w-md mx-auto mt-4 p-4 bg-red-500/20 border border-red-500 rounded-lg text-white"
            >
              {error}
            </motion.div>
          )}
          {results.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="mt-12">
              <FloatingCard delay={0.2}>
                <h2 className="text-2xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-navy-blue to-blue-400">
                  Evaluation Results
                </h2>
                <div className="space-y-4">
                  <AnimatePresence>
                    {results.map((result) => (
                      <ResultItem
                        key={result.id}
                        result={result}
                        onDownload={() => handleDownload(result.url, result.filename)}
                      />
                    ))}
                  </AnimatePresence>
                </div>
              </FloatingCard>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EssayEvaluator; 