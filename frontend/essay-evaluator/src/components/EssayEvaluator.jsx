import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Loader2, X, Plus, Download } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker?url';
import CryptoJS from 'crypto-js';
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

  useEffect(() => {
    const encryptedKey = localStorage.getItem('geminiApiKey');
    if (encryptedKey) {
      try {
        const bytes = CryptoJS.AES.decrypt(encryptedKey, encryptionKey);
        const decryptedKey = bytes.toString(CryptoJS.enc.Utf8);
        if (decryptedKey) setApiKey(decryptedKey);
      } catch (err) {
        console.error('Failed to decrypt API key:', err);
      }
    }
  }, [encryptionKey]);

  const handleApiKeyChange = (e) => {
    const key = e.target.value;
    setApiKey(key);
    setIsApiKeyVerified(false);
    const encryptedKey = CryptoJS.AES.encrypt(key, encryptionKey).toString();
    localStorage.setItem('geminiApiKey', encryptedKey);
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
    
    // Log the API URL being used
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const apiUrl = `${baseUrl}/verify_api_key/`;
    console.log(`Verifying API key using endpoint: ${apiUrl}`);
    console.log(`Base URL from environment: ${baseUrl}`);
    
    try {
      const formData = new FormData();
      formData.append('api_key', apiKey);
      
      // Use the API utility instead of hardcoded URL
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
      });
      
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
      // Use the new dedicated endpoint for rubric file uploads
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
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
      
      // Get base URL
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      
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
          const score = await extractScoreFromPdf(blob);
          
          setResults((prev) => [
            ...prev,
            { id: Date.now() + i, filename: file.name, url, score },
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
        const score = await extractScoreFromPdf(blob);
        
        setResults((prev) => [
          ...prev,
          { id: Date.now(), filename: 'Pasted essay', url, score },
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

  // Add a function to test API connectivity
  const testApiConnection = async () => {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    setError(null);
    
    // Test URLs with different variations
    const testUrls = [
      `https://${baseUrl.replace('https://', '')}`,
      `http://${baseUrl.replace('https://', '').replace('http://', '')}`,
      `https://${baseUrl.replace('https://', '')}/verify_api_key/`,
      `http://${baseUrl.replace('https://', '').replace('http://', '')}/verify_api_key/`
    ];
    
    console.log("Testing the following URLs:");
    testUrls.forEach(url => console.log(`- ${url}`));
    
    const results = [];
    
    for (const url of testUrls) {
      try {
        console.log(`Testing connection to: ${url}`);
        
        // Add a timeout to the fetch request
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch(url, {
          method: 'GET',
          signal: controller.signal,
          headers: {
            'Accept': 'application/json, text/plain, */*'
          }
        });
        
        clearTimeout(timeoutId);
        
        console.log(`Response from ${url}: Status ${response.status}`);
        
        // Try to get response text for more details
        let responseText = '';
        try {
          responseText = await response.text();
          responseText = responseText.substring(0, 100) + (responseText.length > 100 ? '...' : '');
        } catch (textError) {
          responseText = 'Could not read response text';
        }
        
        results.push(`${url}: Status ${response.status} - ${responseText}`);
        
      } catch (err) {
        console.error(`Failed to connect to ${url}:`, err);
        results.push(`${url}: Error - ${err.message}`);
      }
    }
    
    // Display results
    alert(`API Connection Test Results:\n\n${results.join('\n\n')}`);
    
    // Suggest next steps based on results
    if (results.every(r => r.includes('Error') || r.includes('404'))) {
      alert(`
Troubleshooting suggestions:

1. Check if your Railway app is deployed and running
2. Verify the correct URL in your Railway dashboard
3. Make sure your FastAPI backend is properly configured
4. Check if your Railway service is exposed to the internet
5. Try accessing the Railway URL directly in a browser

Your current API URL is: ${baseUrl}
      `);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden pt-16">
      <AnimatedBackground />
      <div className="relative z-10 p-8">
        <div className="mb-12">
          <AnimatedHeading />
          <motion.p className="text-center text-gray-300 text-xl mt-4">
            Advanced essay analysis powered by AI
          </motion.p>
          {/* API URL Debug Info */}
          <motion.div className="text-center mt-2 p-2 bg-gray-800/80 rounded-lg inline-block mx-auto">
            <p className="text-gray-400 text-xs">
              API URL: <span className="text-green-400 font-mono">{import.meta.env.VITE_API_URL || 'http://localhost:8000'}</span>
              <button 
                onClick={testApiConnection}
                className="ml-2 px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-white"
              >
                Test Connection
              </button>
              <button 
                onClick={() => {
                  const url = prompt("Enter the exact Railway URL to test:", "https://essay-eval-09-production.up.railway.app");
                  if (url) {
                    window.open(url, '_blank');
                  }
                }}
                className="ml-2 px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs text-white"
              >
                Open Railway URL
              </button>
            </p>
          </motion.div>
        </div>
        <div className="max-w-4xl mx-auto space-y-8">
          <FloatingCard>
            <label className="block text-gray-300 mb-2">Gemini API Key</label>
            <div className="flex flex-col space-y-2">
              <div className="flex items-center space-x-4">
                <input
                  type="password"
                  value={apiKey}
                  onChange={handleApiKeyChange}
                  placeholder="Enter your Gemini API key"
                  className="w-full p-2 rounded-lg bg-gray-900/50 border border-gray-700 focus:border-green-400 text-white"
                />
                <motion.button
                  onClick={handleVerifyApiKey}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="px-4 py-2 bg-green-500 rounded-full"
                >
                  Verify
                </motion.button>
              </div>
              <p className="text-xs text-gray-400">
                Get your API key from <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-green-400 hover:underline">Google AI Studio</a>. 
                Make sure to use a valid Gemini API key that starts with "AI".
              </p>
              {isApiKeyVerified && <p className="text-green-400 mt-2">API Key Verified ✓</p>}
            </div>
          </FloatingCard>
          <div className="flex justify-center space-x-4 mb-6">
            <motion.button
              onClick={() => setActiveTab('upload')}
              className={`px-6 py-2 rounded-full transition-colors ${activeTab === 'upload' ? 'bg-green-500 text-white' : 'bg-gray-700/50 text-gray-300'}`}
            >
              Upload Essays
            </motion.button>
            <motion.button
              onClick={() => setActiveTab('paste')}
              className={`px-6 py-2 rounded-full transition-colors ${activeTab === 'paste' ? 'bg-green-500 text-white' : 'bg-gray-700/50 text-gray-300'}`}
            >
              Paste Text
            </motion.button>
            <motion.button
              onClick={() => setActiveTab('rubric')}
              className={`px-6 py-2 rounded-full transition-colors ${activeTab === 'rubric' ? 'bg-green-500 text-white' : 'bg-gray-700/50 text-gray-300'}`}
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
                    className="w-full h-64 p-4 rounded-xl bg-gray-900/50 border border-gray-700 focus:border-green-400 focus:ring-2 focus:ring-green-400/50 transition-all duration-300 resize-none text-white"
                    whileFocus={{ scale: 1.02 }}
                  />
                </FloatingCard>
              </motion.div>
            ) : (
              <motion.div key="rubric" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <FloatingCard>
                  <label className="block text-gray-300 mb-2">Upload Rubric File</label>
                  <div className="space-y-4">
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
                    <div className="mt-2">
                      <label className="block text-gray-300 mb-2">Rubric Content</label>
                      <textarea
                        value={rubricText}
                        onChange={(e) => setRubricText(e.target.value)}
                        className="w-full h-64 p-4 rounded-xl bg-gray-900/50 border border-gray-700 focus:border-green-400 focus:ring-2 focus:ring-green-400/50 transition-all duration-300 resize-none text-white"
                        placeholder="Paste your rubric here or upload a file above..."
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
              disabled={isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim())}
              className={`px-8 py-4 rounded-full font-semibold focus:outline-none ${
                isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim())
                  ? 'bg-gray-600 text-gray-400'
                  : 'bg-gradient-to-r from-green-400 to-emerald-500 text-white'
              }`}
              whileHover={!isLoading && ((activeTab === 'upload' && files.length) || (activeTab === 'paste' && essayText.trim())) ? { scale: 1.05 } : {}}
              whileTap={!isLoading && ((activeTab === 'upload' && files.length) || (activeTab === 'paste' && essayText.trim())) ? { scale: 0.95 } : {}}
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
          {error && <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center text-red-400 mt-4">{error}</motion.p>}
          {results.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} className="mt-12">
              <FloatingCard delay={0.2}>
                <h2 className="text-2xl font-bold mb-6 text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">
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