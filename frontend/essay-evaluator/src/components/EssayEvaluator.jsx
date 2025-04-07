import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Loader2, X, Plus, Download, Package } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker?url';
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
      alert(`Cannot read an empty file: "${file.name}".`);
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
      setFiles([...files, ...newFiles.slice(0, MAX_FILES - files.length)]);
    }
  };

  const addFiles = (e) => {
    const newFiles = Array.from(e.target.files).filter(validateFile);
    if (newFiles.length === 0) return;
    if (newFiles.some((f) => f.type === 'application/pdf')) {
      alert('For PDFs, only one file is allowed.');
      setFiles([newFiles[0]]);
    } else if (files.length < MAX_FILES) {
      setFiles([...files, ...newFiles.slice(0, MAX_FILES - files.length)]);
    }
  };

  const removeFile = (index) => setFiles(files.filter((_, i) => i !== index));

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
              : `Drag and drop your essays or click to select (${files.length}/${MAX_FILES})`}
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
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="flex items-center justify-between p-4 rounded-lg border bg-gray-700/50 border-gray-600 hover:border-navy-blue"
    >
      <div className="flex items-center space-x-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-navy-blue/30">
          <FileText className="w-6 h-6 text-navy-blue" />
        </div>
        <div>
          <p className="text-white font-semibold text-lg">{studentName}</p>
          <p className="text-gray-400 text-xs">{result.filename}</p>
          <p className="font-bold text-navy-blue">Score: {result.score}/{result.maxScore}</p>
        </div>
      </div>
      <div className="flex space-x-2">
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={onDownload}
          className="p-2 bg-navy-blue/20 hover:bg-navy-blue/40 rounded-full"
          title="Download report"
        >
          <Download className="w-5 h-5 text-navy-blue" />
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={onRemove}
          className="p-2 bg-red-500/20 hover:bg-red-500/40 rounded-full"
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
  const [rubricText, setRubricText] = useState('');
  const [rubricFile, setRubricFile] = useState(null);
  const [selectedPresetRubric, setSelectedPresetRubric] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [includeCriteria, setIncludeCriteria] = useState(true);
  const [includeSuggestions, setIncludeSuggestions] = useState(true);
  const [includeHighlights, setIncludeHighlights] = useState(true);
  const [includeMiniLessons, setIncludeMiniLessons] = useState(true);

  const handleRubricUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || file.size === 0) {
      setError('Cannot read an empty rubric file.');
      return;
    }
    const fileExt = file.name.split('.').pop().toLowerCase();
    if (fileExt !== 'pdf' && fileExt !== 'txt') {
      setError('Only PDF and TXT files are supported.');
      return;
    }
    setRubricFile(file);
    setSelectedPresetRubric('');
    setRubricText('');
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/upload-rubric-file/`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) throw new Error((await response.json()).detail || 'Failed to extract rubric text');
      const data = await response.json();
      setRubricText(data.text);
    } catch (err) {
      setError(err.message || 'Failed to process rubric file');
    }
  };

  const handleSubmit = async () => {
    try {
      setError(null);
      setResults([]);
      setSessionId(null);
      if (activeTab === 'upload' && files.length === 0) throw new Error('Please upload at least one essay file.');
      if (activeTab === 'paste' && !essayText.trim()) throw new Error('Please enter your essay text.');

       const baseUrl =  'http://localhost:8000'; // import.meta.env.VITE_API_URL
      const processFile = async (fileOrText, filename) => {
        const formData = new FormData();
        if (rubricFile) formData.append('rubric_file', rubricFile);
        else if (rubricText.trim()) formData.append('rubric_text', rubricText.trim());
        formData.append('include_criteria', includeCriteria);
        formData.append('include_suggestions', includeSuggestions);
        formData.append('include_highlights', includeHighlights);
        formData.append('include_mini_lessons', includeMiniLessons);
        formData.append('essay', activeTab === 'upload' ? fileOrText : new Blob([fileOrText], { type: 'text/plain' }), filename);

        const response = await fetch(`${baseUrl}/evaluate/`, { method: 'POST', body: formData });
        if (!response.ok) throw new Error((await response.json()).detail || 'Evaluation failed');
        const data = await response.json();

        if (data.evaluation_status === 'single') {
          setSessionId(data.session_id);
          setResults(prev => [...prev, {
            id: Date.now(),
            filename: data.filename,
            student_name: data.student_name,
            score: data.overall_score,
            maxScore: data.max_score,
            sessionId: data.session_id
          }]);
        } else if (data.evaluation_status === 'multiple') {
          setSessionId(data.session_id);
          setResults(prev => [...prev, ...data.results.map((r, i) => ({
            id: i + Date.now(),
            filename: r.filename,
            student_name: r.student_name,
            score: r.overall_score,
            maxScore: r.max_score,
            sessionId: data.session_id
          }))]);
        }
      };

      setIsLoading(true);
      if (activeTab === 'upload') {
        for (const file of files) {
          setProcessingFile(file.name);
          await processFile(file, file.name);
        }
      } else {
        setProcessingFile('Pasted essay');
        await processFile(essayText, 'essay.txt');
        setEssayText('');
      }
    } catch (err) {
      setError(err.message || 'Evaluation error');
    } finally {
      setIsLoading(false);
      setProcessingFile(null);
    }
  };

  const handleDownload = async (result) => {
    try {
      setIsLoading(true);
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/download-report/${result.sessionId}/${result.filename}`);
      if (!response.ok) throw new Error('Download failed');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || 'Download error');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemoveResult = (id) => setResults(prev => prev.filter(r => r.id !== id));

  return (
    <div className="min-h-screen relative overflow-hidden pt-16" style={navyBlueStyle}>
      <AnimatedBackground />
      <div className="relative z-10 p-8">
        <div className="mb-12">
          <AnimatedHeading />
          <motion.p className="text-center text-white text-xl mt-4">AI-based essay evaluator</motion.p>
        </div>
        <div className="max-w-4xl mx-auto space-y-8">
          <div className="flex justify-center space-x-4 mb-6">
            <motion.button onClick={() => setActiveTab('upload')} className={`px-6 py-2 rounded-full ${activeTab === 'upload' ? 'bg-navy-blue text-white' : 'bg-gray-700/50 text-gray-300'}`}>Upload Essays</motion.button>
            <motion.button onClick={() => setActiveTab('paste')} className={`px-6 py-2 rounded-full ${activeTab === 'paste' ? 'bg-navy-blue text-white' : 'bg-gray-700/50 text-gray-300'}`}>Paste Text</motion.button>
            <motion.button onClick={() => setActiveTab('rubric')} className={`px-6 py-2 rounded-full ${activeTab === 'rubric' ? 'bg-navy-blue text-white' : 'bg-gray-700/50 text-gray-300'}`}>Rubric</motion.button>
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
                    className="w-full h-64 p-4 rounded-xl bg-gray-900/50 border border-gray-700 focus:border-navy-blue text-white"
                  />
                </FloatingCard>
              </motion.div>
            ) : (
              <motion.div key="rubric" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <FloatingCard>
                  <div className="space-y-6">
                    <h3 className="text-xl font-semibold text-navy-blue">Configure Rubric</h3>
                    <div>
                      <label className="block text-gray-300 mb-2">Select Preset Rubric</label>
                      <select
                        value={selectedPresetRubric}
                        onChange={(e) => {
                          setSelectedPresetRubric(e.target.value);
                          const preset = presetRubrics.find(r => r.id === e.target.value);
                          if (preset) {
                            setRubricText(preset.content);
                            setRubricFile(null);
                          } else {
                            setRubricText('');
                          }
                        }}
                        className="w-full p-2 rounded-lg bg-gray-900/50 border border-gray-700 text-white"
                      >
                        <option value="">None</option>
                        {presetRubrics.map(rubric => (
                          <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-gray-300 mb-2">Upload Rubric File</label>
                      <input
                        type="file"
                        onChange={handleRubricUpload}
                        accept=".pdf,.txt"
                        className="w-full p-2 rounded-lg bg-gray-900/50 border border-gray-700 text-white"
                      />
                      {rubricFile && <p className="mt-2 text-gray-300">Selected: {rubricFile.name}</p>}
                    </div>
                    <div>
                      <label className="block text-gray-300 mb-2">Or Paste Custom Rubric</label>
                      <textarea
                        value={rubricText}
                        onChange={(e) => {
                          setRubricText(e.target.value);
                          setSelectedPresetRubric('');
                          setRubricFile(null);
                        }}
                        className="w-full h-64 p-4 rounded-xl bg-gray-900/50 border border-gray-700 text-white"
                        placeholder="Paste your rubric here..."
                      />
                    </div>
                    <div className="mt-4">
                      <h3 className="text-lg font-semibold text-white mb-2">Feedback Options</h3>
                      <div className="space-y-2">
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={includeCriteria}
                            onChange={(e) => setIncludeCriteria(e.target.checked)}
                            className="form-checkbox h-5 w-5 text-navy-blue"
                          />
                          <span className="text-white">Include Criteria Feedback</span>
                        </label>
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={includeSuggestions}
                            onChange={(e) => setIncludeSuggestions(e.target.checked)}
                            className="form-checkbox h-5 w-5 text-navy-blue"
                          />
                          <span className="text-white">Include Overall Suggestions</span>
                        </label>
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={includeHighlights}
                            onChange={(e) => setIncludeHighlights(e.target.checked)}
                            className="form-checkbox h-5 w-5 text-navy-blue"
                          />
                          <span className="text-white">Include Highlighted Passages</span>
                        </label>
                        <label className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={includeMiniLessons}
                            onChange={(e) => setIncludeMiniLessons(e.target.checked)}
                            className="form-checkbox h-5 w-5 text-navy-blue"
                          />
                          <span className="text-white">Include Mini Lessons</span>
                        </label>
                      </div>
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
              className={`w-full py-3 rounded-full font-medium ${isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim()) ? 'bg-gray-600 text-gray-400' : 'bg-navy-blue text-white hover:bg-blue-600'}`}
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Processing {processingFile ? `"${processingFile}"` : '...'}
                </span>
              ) : (
                'Evaluate Essays'
              )}
            </motion.button>
          </motion.div>
          {error && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-md mx-auto mt-4 p-4 bg-red-500/20 border border-red-500 rounded-lg text-white">
              {error}
            </motion.div>
          )}
          <AnimatePresence>
            {results.length > 0 && (
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }} className="mt-10">
                <FloatingCard>
                  <h2 className="text-2xl font-bold text-center text-navy-blue mb-6">Evaluation Results</h2>
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
                        onClick={() => results.forEach(handleDownload)}
                        className="flex items-center px-4 py-2 bg-navy-blue text-white rounded-full"
                        disabled={isLoading}
                      >
                        {isLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Package className="w-4 h-4 mr-2" />}
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