import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Loader2, X, Plus, Download, Check, RefreshCw, Package, AlertTriangle, Lock, Unlock } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker?url';
import CryptoJS from 'crypto-js';
import { storeApiKey, retrieveApiKey, removeApiKey, hasStoredApiKey } from '../utils/apiKeyStorage';
import { useAuth } from '../contexts/AuthContext';
import presetRubrics from '../utils/presetRubrics';
pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

const navyBlueStyle = {
  "--navy-blue": "#1a365d",
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

const ResultItem = ({ result, onDownload, onRemove }) => {
  const studentName = result.student_name || "Unknown";
  const hasStudentName = studentName !== "Unknown";
  const hasRateLimitError = result.hasError && result.errorType === 'rate_limit';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={`flex items-center justify-between p-4 rounded-lg border transition-colors 
        ${hasRateLimitError 
          ? 'bg-orange-700/30 border-orange-500 hover:border-orange-400' 
          : 'bg-gray-700/50 border-gray-600 hover:border-navy-blue'}`}
    >
      <div className="flex items-center space-x-4">
        <div className={`flex items-center justify-center w-10 h-10 rounded-full 
          ${hasRateLimitError ? 'bg-orange-500/30' : 'bg-navy-blue/30'}`}>
          {hasRateLimitError 
            ? <AlertTriangle className="w-6 h-6 text-orange-500" /> 
            : <FileText className="w-6 h-6 text-navy-blue" />}
        </div>
        <div>
          {hasStudentName ? (
            <>
              <p className="text-white font-semibold text-lg leading-tight">
                {studentName}
              </p>
              <p className="text-gray-400 text-xs">
                {result.filename}
              </p>
              <div className="flex items-center mt-1">
                <p className={`font-bold ${hasRateLimitError ? 'text-orange-400' : 'text-navy-blue'}`}>
                  Score: {result.score}/{result.totalMark || result.maxScore}
                </p>
                {hasRateLimitError && (
                  <span className="ml-2 px-2 py-0.5 bg-orange-500/20 text-orange-400 text-xs rounded-full">
                    API Rate Limited
                  </span>
                )}
              </div>
            </>
          ) : (
            <>
              <p className="text-gray-200 font-medium">
                {result.filename}
              </p>
              <div className="flex items-center mt-1">
                <p className={`font-bold ${hasRateLimitError ? 'text-orange-400' : 'text-navy-blue'}`}>
                  Score: {result.score}/{result.totalMark || result.maxScore}
                </p>
                {hasRateLimitError && (
                  <span className="ml-2 px-2 py-0.5 bg-orange-500/20 text-orange-400 text-xs rounded-full">
                    API Rate Limited
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
      <div className="flex space-x-2">
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={onDownload}
          className={`p-2 rounded-full transition-colors ${
            hasRateLimitError ? 'bg-orange-500/20 hover:bg-orange-500/40 text-orange-400' : 
            'bg-navy-blue/20 hover:bg-navy-blue/40 text-navy-blue'
          }`}
          title="Download report"
        >
          <Download className="w-5 h-5" />
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={onRemove}
          className="p-2 bg-red-500/20 hover:bg-red-500/40 rounded-full transition-colors"
          title="Remove"
        >
          <X className="w-5 h-5 text-red-500" />
        </motion.button>
      </div>
    </motion.div>
  );
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
  const [isRubricLocked, setIsRubricLocked] = useState(false);
  const [lockedRubricText, setLockedRubricText] = useState(''); // Added to store locked rubric content
  const [showApiKey, setShowApiKey] = useState(false);
  const { currentUser } = useAuth();
  const [sessionId, setSessionId] = useState(null);
  const [evaluations, setEvaluations] = useState([]);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [batchProgress, setBatchProgress] = useState(0);

  // Preserve locked rubric text
  useEffect(() => {
    if (isRubricLocked) {
      setLockedRubricText(rubricText);
    }
  }, [isRubricLocked, rubricText]);

  useEffect(() => {
    if (currentUser) {
      const storedApiKey = retrieveApiKey(currentUser.uid);
      if (storedApiKey) {
        setApiKey(storedApiKey);
      }
    }
  }, [currentUser]);

  const handleApiKeyChange = (e) => {
    const key = e.target.value;
    setApiKey(key);
    setIsApiKeyVerified(false);
    if (currentUser) {
      storeApiKey(key, currentUser.uid);
    }
  };

  const handleClearApiKey = () => {
    if (window.confirm('Are you sure you want to clear your API key?')) {
      setApiKey('');
      setIsApiKeyVerified(false);
      if (currentUser) {
        removeApiKey(currentUser.uid);
      }
    }
  };

  const handlePresetRubricChange = (e) => {
    const selectedId = e.target.value;
    if (!isRubricLocked) {
      setSelectedPresetRubric(selectedId);
      if (selectedId) {
        const preset = presetRubrics.find(rubric => rubric.id === selectedId);
        if (preset) {
          setRubricText(preset.content);
          setRubricFile(null);
        }
      } else {
        setRubricText('');
      }
    } else {
      alert("Rubric is locked. Unlock to change.");
    }
  };

  const handleVerifyApiKey = async () => {
    setError(null);
    if (!apiKey.trim()) {
      setError('Please enter an API key to verify.');
      return;
    }
    if (!apiKey.trim().startsWith('AI')) {
      setError('This doesn\'t look like a valid Gemini API key. Gemini API keys typically start with "AI".');
      return;
    }
    let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    if (!baseUrl.startsWith('http')) {
      baseUrl = 'https://' + baseUrl;
    }
    const apiUrl = `${baseUrl}/verify_api_key/`;
    try {
      const formData = new FormData();
      formData.append('api_key', apiKey);
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(10000),
        headers: { 'Accept': 'application/json' }
      });
      if (response.ok) {
        setIsApiKeyVerified(true);
        setError(null);
        alert('API key verified successfully!');
      } else {
        const errorData = await response.json();
        setIsApiKeyVerified(false);
        setError(errorData.detail || 'Invalid API key. Please check and try again.');
      }
    } catch (err) {
      setIsApiKeyVerified(false);
      setError(`Failed to verify API key: ${err.message}.`);
    }
  };

  const handleRubricUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || file.size === 0) {
      setError('Cannot read an empty rubric file.');
      return;
    }
    const fileExt = file.name.split('.').pop().toLowerCase();
    if (fileExt !== 'pdf' && fileExt !== 'txt') {
      setError('Only PDF and TXT files are supported for rubrics.');
      return;
    }
    if (isRubricLocked) {
      alert("Rubric is locked. Unlock to upload a new file.");
      e.target.value = null;
      return;
    }
    setRubricFile(file);
    setSelectedPresetRubric('');
    setRubricText('');
    const formData = new FormData();
    formData.append('file', file);
    try {
      let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      if (!baseUrl.startsWith('http')) {
        baseUrl = 'https://' + baseUrl;
      }
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
      setProcessingStatus(null);
      setBatchProgress(0);
      if (!apiKey.trim()) throw new Error('Please enter your Gemini API key.');
      if (!isApiKeyVerified) throw new Error('Please verify your API key first.');
      if (activeTab === 'upload' && files.length === 0) {
        throw new Error('Please upload at least one essay file.');
      }
      if (activeTab === 'paste' && !essayText.trim()) {
        throw new Error('Please enter your essay text.');
      }
      setResults([]);
      setEvaluations([]);
      setSessionId(null);
      let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      if (!baseUrl.startsWith('http')) {
        baseUrl = 'https://' + baseUrl;
      }

      const processPastedText = async () => {
        setIsLoading(true);
        setProcessingFile('Pasted essay');
        if (essayText.length > 30000) {
          setProcessingStatus('Processing large document...');
        }
        const studentNameMatches = (essayText.match(/Student Name:/gi) || []).length;
        const studentMatches = (essayText.match(/Student:/gi) || []).length;
        const nameMatches = (essayText.match(/Name:/gi) || []).length;
        const totalMatches = studentNameMatches + studentMatches + nameMatches;
        const multipleSectionsIndicator = essayText.split(/\n{3,}/).length > 2;
        if (totalMatches > 1 || (multipleSectionsIndicator && totalMatches > 0)) {
          const estimatedEssayCount = Math.max(1, totalMatches);
          if (estimatedEssayCount > 5) {
            setProcessingStatus(`Processing ${estimatedEssayCount} essays...`);
            const essays = splitEssaysText(essayText);
            if (essays.length > 5) {
              const batchSize = 3;
              const totalBatches = Math.ceil(essays.length / batchSize);
              for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
                const batchStart = batchIndex * batchSize;
                const batchEnd = Math.min(batchStart + batchSize, essays.length);
                const currentBatch = essays.slice(batchStart, batchEnd);
                setBatchProgress(Math.round((batchIndex / totalBatches) * 100));
                setProcessingStatus(`Processing essays (${batchIndex + 1}/${totalBatches})...`);
                const batchText = currentBatch.join("\n\n---\n\n");
                await processEssayBatch(batchText, `Batch ${batchIndex + 1}`);
                if (batchIndex < totalBatches - 1) {
                  const delayTime = 5000 + (Math.random() * 3000);
                  setProcessingStatus(`Preparing next batch...`);
                  await new Promise(resolve => setTimeout(resolve, delayTime));
                }
              }
              setBatchProgress(100);
              setProcessingStatus(`Completing evaluation...`);
              setIsLoading(false);
              setProcessingFile(null);
              setEssayText('');
              return;
            }
          }
          setProcessingStatus(`Processing ${estimatedEssayCount} essays...`);
        } else {
          setProcessingStatus('Processing essay...');
        }
        await processEssayBatch(essayText, 'Pasted essay');
        setEssayText('');
      };

      const processEssayBatch = async (text, batchName) => {
        const formData = new FormData();
        formData.append('api_key', apiKey);
        // Updated rubric handling
        if (isRubricLocked && lockedRubricText) {
          formData.append('rubric_text', lockedRubricText);
          console.log("Appending locked rubric_text to FormData");
        } else if (selectedPresetRubric) {
          const preset = presetRubrics.find(rubric => rubric.id === selectedPresetRubric);
          if (preset) {
            formData.append('rubric_text', preset.content);
            console.log("Appending preset rubric_text to FormData");
          }
        } else if (rubricFile) {
          formData.append('rubric_file', rubricFile);
          console.log("Appending rubric_file to FormData");
        } else if (rubricText && rubricText.trim()) {
          formData.append('rubric_text', rubricText.trim());
          console.log("Appending custom rubric_text to FormData");
        } else {
          console.log("No rubric provided, backend will use default.");
        }
        const essayBlob = new Blob([text], { type: 'text/plain' });
        formData.append('essay', essayBlob, `${batchName}.txt`);
        console.log(`[processEssayBatch] Sending evaluation request for: ${batchName}`);
        console.log(`[processEssayBatch] Rubric File:`, rubricFile);
        console.log(`[processEssayBatch] Rubric Text (Preview):`, rubricText ? rubricText.substring(0, 100) + '...' : 'None');
        const response = await fetch(`${baseUrl}/evaluate/`, {
          method: 'POST',
          body: formData,
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to evaluate essay');
        }
        const data = await response.json();
        if (data.evaluation_status === 'single') {
          await handleSingleEssayResponseJson(data, batchName);
        } else if (data.evaluation_status === 'multiple') {
          await handleMultipleEssaysResponse(data, batchName);
        } else {
          throw new Error(data.detail || 'Unexpected response format');
        }
      };

      const splitEssaysText = (text) => {
        const patterns = [/Student Name:/i, /Student:/i, /Name:/i];
        let essays = [];
        let lines = text.split('\n');
        let currentEssay = '';
        let foundAnyMarker = false;
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          const isMarkerLine = patterns.some(pattern => pattern.test(line));
          if (isMarkerLine && currentEssay.trim().length > 0) {
            essays.push(currentEssay.trim());
            currentEssay = line + '\n';
            foundAnyMarker = true;
          } else {
            currentEssay += line + '\n';
          }
        }
        if (currentEssay.trim().length > 0) {
          essays.push(currentEssay.trim());
        }
        if (!foundAnyMarker || essays.length <= 1) {
          essays = text.split(/\n{3,}/).filter(essay => essay.trim().length > 100);
        }
        if (essays.length <= 1 && text.length > 10000) {
          essays = text.split(/\n---+\n|\n\*\*\*+\n|\n___+\n/)
            .filter(essay => essay.trim().length > 100);
        }
        return essays;
      };

      if (activeTab === 'upload') {
        await processUploadedFiles();
      } else {
        await processPastedText();
      }
    } catch (err) {
      setError(err.message || 'An error occurred.');
      setIsLoading(false);
      setProcessingFile(null);
      setProcessingStatus(null);
    }
  };

  const handleDownload = async (result) => {
    if (!result || !result.sessionId || !result.filename) {
      setError('Cannot download report: Missing session data or filename.');
      return;
    }
    try {
      setIsLoading(true);
      setError(null);
      let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      if (!baseUrl.startsWith('http')) {
        baseUrl = 'https://' + baseUrl;
      }
      const response = await fetch(`${baseUrl}/download-report/${result.sessionId}/${result.filename}`, {
        method: 'GET',
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to download report');
      }
      const blob = await response.blob();
      const downloadUrlObject = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrlObject;
      a.download = result.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrlObject);
    } catch (err) {
      setError(err.message || 'Error downloading report');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemoveResult = (id) => {
    setResults(prev => prev.filter(result => result.id !== id));
  };

  const handleDownloadAll = async () => {
    if (evaluations.length === 0) {
      setError('No evaluations available for download');
      return;
    }
    try {
      setIsLoading(true);
      let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      if (!baseUrl.startsWith('http')) {
        baseUrl = 'https://' + baseUrl;
      }
      const processedEvaluations = evaluations.map((evaluation, index) => ({
        student_name: evaluation.student_name || `Essay ${index + 1}`,
        overall_score: Number(evaluation.overall_score || 0),
        max_score: evaluation.max_score || 10,
        criteria: Array.isArray(evaluation.criteria) && evaluation.criteria.length > 0 ? evaluation.criteria : [{
          name: "Overall Quality",
          score: evaluation.overall_score || 0,
          max_score: evaluation.max_score || 10,
          feedback: "No specific feedback"
        }],
        suggestions: evaluation.suggestions || [],
        highlighted_passages: evaluation.highlighted_passages || [],
        mini_lessons: evaluation.mini_lessons || [] // Include mini-lessons
      }));
      const payload = { session_id: sessionId, evaluations: processedEvaluations };
      const response = await fetch(`${baseUrl}/generate-all-zip/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate zip');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'evaluation_reports.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || 'Error generating zip file');
    } finally {
      setIsLoading(false);
    }
  };

  const processUploadedFiles = async () => {
    const shouldBatchProcess = files.length > 5;
    if (shouldBatchProcess) {
      setProcessingStatus(`Processing ${files.length} files...`);
      const batchSize = 3;
      const totalBatches = Math.ceil(files.length / batchSize);
      for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
        const batchStart = batchIndex * batchSize;
        const batchEnd = Math.min(batchStart + batchSize, files.length);
        const currentBatchFiles = files.slice(batchStart, batchEnd);
        setBatchProgress(Math.round((batchIndex / totalBatches) * 100));
        setProcessingStatus(`Processing files (${batchIndex + 1}/${totalBatches})...`);
        for (const file of currentBatchFiles) {
          setProcessingFile(file.name);
          setIsLoading(true);
          try {
            await processFile(file);
          } catch (err) {
            setError(`Error processing ${file.name}: ${err.message}`);
          }
        }
        if (batchIndex < totalBatches - 1) {
          const delayTime = 5000 + (Math.random() * 3000);
          setProcessingStatus(`Preparing next batch...`);
          await new Promise(resolve => setTimeout(resolve, delayTime));
        }
      }
      setBatchProgress(100);
      setProcessingStatus(`Completing evaluation...`);
    } else {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setProcessingFile(file.name);
        setIsLoading(true);
        setBatchProgress(Math.round((i / files.length) * 100));
        setProcessingStatus(files.length > 1 ? `Processing file ${i+1} of ${files.length}...` : 'Processing file...');
        try {
          await processFile(file);
        } catch (err) {
          setError(`Error processing ${file.name}: ${err.message}`);
        }
      }
    }
    setIsLoading(false);
    setProcessingFile(null);
    setProcessingStatus(null);
    setBatchProgress(100);
  };

  const processFile = async (file) => {
    let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    if (!baseUrl.startsWith('http')) {
      baseUrl = 'https://' + baseUrl;
    }
    const formData = new FormData();
    formData.append('api_key', apiKey);
    if (isRubricLocked && lockedRubricText) {
      formData.append('rubric_text', lockedRubricText);
      console.log("Appending locked rubric_text to FormData");
    } else if (selectedPresetRubric) {
      const preset = presetRubrics.find(rubric => rubric.id === selectedPresetRubric);
      if (preset) {
        formData.append('rubric_text', preset.content);
        console.log("Appending preset rubric_text to FormData");
      }
    } else if (rubricFile) {
      formData.append('rubric_file', rubricFile);
      console.log("Appending rubric_file to FormData");
    } else if (rubricText && rubricText.trim()) {
      formData.append('rubric_text', rubricText.trim());
      console.log("Appending custom rubric_text to FormData");
    } else {
      console.log("No rubric provided, backend will use default.");
    }
    formData.append('essay', file);
    console.log(`[processFile] Sending evaluation request for: ${file.name}`);
    console.log(`[processFile] Rubric File:`, rubricFile);
    console.log(`[processFile] Rubric Text (Preview):`, rubricText ? rubricText.substring(0, 100) + '...' : 'None');
    const response = await fetch(`${baseUrl}/evaluate/`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `Failed to evaluate ${file.name}`);
    }
    const data = await response.json();
    if (data.evaluation_status === 'single') {
      await handleSingleEssayResponseJson(data, file.name);
    } else if (data.evaluation_status === 'multiple') {
      await handleMultipleEssaysResponse(data, file.name);
    } else {
      throw new Error(data.detail || 'Unexpected response format');
    }
  };

  const handleSingleEssayResponseJson = async (data, originalFilename) => {
    const { session_id, filename, student_name, overall_score, max_score, mini_lessons } = data;
    if (!session_id || !filename) {
        throw new Error("Missing session_id or filename.");
    }
    if (!sessionId) {
      setSessionId(session_id);
    }
    const singleEvaluation = {
      student_name: student_name || "Unknown",
      overall_score: overall_score || 0,
      max_score: max_score || 10,
      criteria: data.criteria || [{ name: "Overall", score: overall_score || 0, max_score: max_score || 10, feedback: "N/A" }],
      suggestions: data.suggestions || [],
      highlighted_passages: data.highlighted_passages || [],
      mini_lessons: mini_lessons || [] // Include mini-lessons
    };
    setEvaluations(prev => [...prev, singleEvaluation]);
    if (!singleEvaluation.mini_lessons || singleEvaluation.mini_lessons.length === 0) {
      console.warn("No mini-lessons provided in the evaluation data for", filename);
    }
    setResults((prev) => [
      ...prev,
      {
        id: Date.now() + Math.random(),
        filename,
        student_name: student_name || "Unknown",
        score: overall_score || 0,
        maxScore: max_score || 10,
        sessionId: session_id,
        needsDownload: true
      },
    ]);
  };

  const handleMultipleEssaysResponse = async (jsonData, filename = 'Batch') => {
    if (jsonData.evaluation_status === 'multiple') {
      if (jsonData.session_id && !sessionId) {
        setSessionId(jsonData.session_id);
      }
      const essayCount = jsonData.count || (jsonData.results ? jsonData.results.length : 0);
      if (jsonData.results && jsonData.results.length < essayCount) {
        setProcessingStatus(`Processed ${jsonData.results.length} of ${essayCount} essays`);
      } else if (essayCount > 0) {
        setProcessingStatus(`Finalizing ${essayCount} evaluations...`);
      }
      if (jsonData.results && jsonData.results.length > 0) {
        const normalizedResults = jsonData.results.map(result => ({
          student_name: result.student_name || "Unknown",
          overall_score: result.overall_score || 0,
          max_score: result.max_score || 10,
          criteria: result.criteria || [],
          suggestions: result.suggestions || [],
          highlighted_passages: result.highlighted_passages || [],
          mini_lessons: result.mini_lessons || [] // Include mini-lessons
        }));
        normalizedResults.forEach(result => {
          if (!result.mini_lessons || result.mini_lessons.length === 0) {
            console.warn("No mini-lessons provided in the evaluation data for", result.student_name);
          }
        });
        setEvaluations(prev => [...prev, ...normalizedResults]);
        const newResults = jsonData.results.map((result, index) => ({
          id: (result.id !== undefined ? result.id : index) + Date.now() + Math.random(),
          filename: result.filename || `${filename}_part${(result.id !== undefined ? result.id : index) + 1}`,
          student_name: result.student_name || `Essay ${index + 1}`,
          score: result.overall_score || 0,
          maxScore: result.max_score || 10,
          sessionId: jsonData.session_id,
          needsDownload: true
        }));
        setResults(prev => [...prev, ...newResults]);
      }
    } else if (jsonData.student_name && jsonData.overall_score !== undefined && jsonData.session_id && jsonData.filename) {
      await handleSingleEssayResponseJson(jsonData, filename);
    } else {
      throw new Error('Unexpected response format');
    }
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
                </p>
                {currentUser ? (
                  <p className="text-xs text-gray-400">
                    {hasStoredApiKey(currentUser.uid) ? "Your API key is securely stored" : "Your API key will be securely stored"}
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
                    <div className="flex justify-between items-center mb-4">
                      <h3 className="text-xl font-semibold text-navy-blue">Configure Rubric</h3>
                      <motion.button
                        onClick={() => setIsRubricLocked(!isRubricLocked)}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className={`flex items-center px-3 py-1 rounded-full text-xs transition-colors ${
                          isRubricLocked
                            ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                            : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                        }`}
                        title={isRubricLocked ? "Unlock Rubric" : "Lock Rubric"}
                      >
                        {isRubricLocked ? <Lock className="w-3 h-3 mr-1" /> : <Unlock className="w-3 h-3 mr-1" />}
                        {isRubricLocked ? 'Locked' : 'Unlocked'}
                      </motion.button>
                    </div>
                    <div className={`transition-opacity duration-300 ${isRubricLocked ? 'opacity-60' : 'opacity-100'}`}>
                      <label className="block text-gray-300 mb-2">Select Preset Rubric</label>
                      <select
                        value={selectedPresetRubric}
                        onChange={handlePresetRubricChange}
                        disabled={isRubricLocked}
                        className={`w-full p-2 rounded-lg bg-gray-900/50 border border-gray-700 focus:border-navy-blue text-white ${isRubricLocked ? 'cursor-not-allowed' : ''}`}
                      >
                        <option value="">None (Use Custom/Uploaded Rubric)</option>
                        {presetRubrics.map(rubric => (
                          <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
                        ))}
                      </select>
                      {selectedPresetRubric && (
                        <p className="mt-2 text-sm text-navy-blue">
                          Using preset: {presetRubrics.find(r => r.id === selectedPresetRubric)?.name} {isRubricLocked ? '(Locked)' : ''}
                        </p>
                      )}
                    </div>
                    <div className={`border-t border-gray-700 pt-4 transition-opacity duration-300 ${isRubricLocked ? 'opacity-60' : 'opacity-100'}`}>
                      <label className="block text-gray-300 mb-2">Upload Rubric File</label>
                      <div className="flex items-center space-x-2">
                        <input
                          type="file"
                          id="rubric-file-input"
                          onChange={handleRubricUpload}
                          disabled={isRubricLocked}
                          accept=".pdf,.txt"
                          className={`w-full p-2 rounded-lg bg-gray-900/50 border border-gray-700 text-white file:mr-4 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-navy-blue/20 file:text-navy-blue hover:file:bg-navy-blue/30 ${isRubricLocked ? 'cursor-not-allowed' : ''}`}
                        />
                        <div className="flex space-x-1">
                          <span className="px-2 py-1 bg-gray-700 rounded text-xs text-white">PDF</span>
                          <span className="px-2 py-1 bg-gray-700 rounded text-xs text-white">TXT</span>
                        </div>
                      </div>
                      {rubricFile && <p className="mt-2 text-gray-300">Selected: {rubricFile.name} {isRubricLocked ? '(Locked)' : ''}</p>}
                    </div>
                    <div className={`transition-opacity duration-300 ${isRubricLocked ? 'opacity-60' : 'opacity-100'}`}>
                      <div className="flex justify-between items-center mb-2">
                        <label className="block text-gray-300">Or Paste Custom Rubric Content</label>
                        {rubricText && !isRubricLocked && (
                          <motion.button
                            onClick={() => {
                              if (!isRubricLocked) {
                                setRubricText('');
                                setRubricFile(null);
                                setSelectedPresetRubric('');
                                const fileInput = document.getElementById('rubric-file-input');
                                if (fileInput) fileInput.value = null;
                              }
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
                        disabled={isRubricLocked}
                        onChange={(e) => {
                          if (!isRubricLocked) {
                            setRubricText(e.target.value);
                            setSelectedPresetRubric('');
                            setRubricFile(null);
                            const fileInput = document.getElementById('rubric-file-input');
                            if (fileInput) fileInput.value = null;
                          }
                        }}
                        className={`w-full h-64 p-4 rounded-xl bg-gray-900/50 border border-gray-700 focus:border-navy-blue focus:ring-2 focus:ring-navy-blue/50 transition-all duration-300 resize-none text-white ${isRubricLocked ? 'cursor-not-allowed' : ''}`}
                        placeholder={isRubricLocked ? "Rubric is locked. Unlock to edit." : "Paste your rubric here, upload a file above, or select a preset..."}
                      />
                      {isRubricLocked && (rubricFile || selectedPresetRubric || rubricText) && (
                        <p className="mt-2 text-sm text-green-400">
                          Current rubric selection is locked for evaluation.
                        </p>
                      )}
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
              className={`w-full py-3 rounded-full font-medium text-center transition-all duration-300 relative overflow-hidden ${
                isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim())
                  ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                  : 'bg-navy-blue hover:bg-blue-600 text-white cursor-pointer'
              }`}
            >
              {isLoading && (
                <>
                  <motion.div 
                    initial={{ width: "5%" }}
                    animate={{ width: `${batchProgress || 5}%`, transition: { duration: 0.6, ease: "easeInOut" } }}
                    className="absolute bottom-0 left-0 h-1.5 bg-gradient-to-r from-blue-500 to-navy-blue rounded-r-full z-10"
                  />
                  <motion.div 
                    animate={{ opacity: [0.6, 0.8, 0.6] }}
                    transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
                    className="absolute bottom-0 left-0 h-1.5 bg-gradient-to-r from-blue-400/40 to-blue-600/40 rounded-full"
                    style={{ width: `${Math.min(100, batchProgress + 5 || 10)}%` }}
                  />
                  <motion.div className="absolute bottom-0 left-0 h-1.5 w-full bg-gray-800/50" />
                </>
              )}
              <span className="flex items-center justify-center gap-2">
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>
                      {processingStatus || `Processing ${processingFile ? `"${processingFile}"` : '...'}`}
                      {batchProgress > 0 && ` (${batchProgress}%)`}
                    </span>
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
          <AnimatePresence>
            {results.length > 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className="mt-10"
              >
                <FloatingCard>
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold text-center text-navy-blue">
                      Evaluation Results
                    </h2>
                    {results.length > 1 && (
                      <span className="bg-navy-blue/20 text-navy-blue px-3 py-1 rounded-full text-sm font-medium">
                        {results.length} Essays
                      </span>
                    )}
                  </div>
                  <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
                    <AnimatePresence>
                      {results.map((result) => (
                        <ResultItem
                          key={result.id}
                          result={result}
                          onDownload={() => handleDownload(result)}
                          onRemove={() => handleRemoveResult(result.id)}
                        />
                      ))}
                    </AnimatePresence>
                  </div>
                  {results.length > 1 && (
                    <div className="mt-4 flex justify-center">
                      <motion.button
                        onClick={handleDownloadAll}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="flex items-center px-4 py-2 bg-navy-blue text-white rounded-full shadow-lg"
                        title="Download all evaluations as a zip file"
                        disabled={isLoading}
                      >
                        {isLoading ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Package className="w-4 h-4 mr-2" />
                        )}
                        Download All Reports
                      </motion.button>
                    </div>
                  )}
                </FloatingCard>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default EssayEvaluator;