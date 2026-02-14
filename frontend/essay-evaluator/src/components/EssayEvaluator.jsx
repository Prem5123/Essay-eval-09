import React, { useState, useCallback, useEffect, useId } from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import {
    Upload, FileText, Loader2, X, Download, AlertTriangle,
    CheckCircle, Settings, Clipboard, Sparkles, ArrowRight, Package
} from 'lucide-react';
import presetRubrics from '../utils/presetRubrics';
import AnimatedBackground from './AnimatedBackground';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ═══════════════════════════════════════════════
// ANIMATION VARIANTS
// ═══════════════════════════════════════════════

const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { staggerChildren: 0.08, delayChildren: 0.1 },
    },
};

const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    visible: {
        opacity: 1, y: 0,
        transition: { duration: 0.3, ease: 'easeOut' },
    },
    exit: { opacity: 0, x: 10, height: 0, transition: { duration: 0.2 } },
};

const tabContentVariants = {
    hidden: { opacity: 0, y: 12 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
    exit: { opacity: 0, y: -12, transition: { duration: 0.2 } },
};

// ═══════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════

const GlassCard = ({ children, className = '' }) => (
    <motion.div
        layout
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.98 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className={`glass glow-border rounded-2xl p-6 md:p-8 ${className}`}
    >
        {children}
    </motion.div>
);

const TabButton = ({ id, label, icon: Icon, activeTab, onClick }) => (
    <button
        onClick={() => onClick(id)}
        className="relative px-5 py-2.5 rounded-xl text-sm font-medium transition-colors duration-200 flex items-center gap-2"
        style={{
            color: activeTab === id ? 'var(--text-primary)' : 'var(--text-secondary)',
        }}
    >
        <span className="relative z-10 flex items-center gap-2">
            <Icon size={15} />
            {label}
        </span>
        {activeTab === id && (
            <motion.div
                layoutId="active-tab-pill"
                className="absolute inset-0 rounded-xl"
                style={{
                    background: 'var(--accent-glow)',
                    border: '1px solid var(--border-accent)',
                }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            />
        )}
    </button>
);

const FileUploadCard = ({ files, setFiles }) => {
    const [isDragging, setIsDragging] = useState(false);
    const MAX_FILES = 10;
    const inputId = useId();

    const validateFile = useCallback((file) => {
        if (file.size === 0) {
            alert(`Cannot read an empty file: "${file.name}".`);
            return false;
        }
        const allowedTypes = ['text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/pdf'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|doc|docx|pdf)$/i)) {
            alert(`Unsupported file type: "${file.name}".`);
            return false;
        }
        return true;
    }, []);

    const handleFiles = useCallback((newFilesArray) => {
        const validFiles = newFilesArray.filter(validateFile);
        if (validFiles.length === 0) return;
        setFiles(prev => {
            const allFiles = [...prev, ...validFiles];
            const pdfFiles = allFiles.filter(f => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
            if (pdfFiles.length > 1) {
                alert('Only one PDF at a time.');
                const firstPdf = pdfFiles[0];
                const nonPdfs = allFiles.filter(f => f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf'));
                return [...nonPdfs, firstPdf].slice(0, MAX_FILES);
            }
            return allFiles.slice(0, MAX_FILES);
        });
    }, [setFiles, validateFile]);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(Array.from(e.dataTransfer.files));
    }, [handleFiles]);

    const handleInputChange = useCallback((e) => {
        handleFiles(Array.from(e.target.files));
        e.target.value = '';
    }, [handleFiles]);

    const removeFile = useCallback((index) => {
        setFiles(prev => prev.filter((_, i) => i !== index));
    }, [setFiles]);

    return (
        <div className="space-y-5">
            <motion.div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
                onDrop={handleDrop}
                whileHover={{ scale: 1.005 }}
                className={`relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 cursor-pointer
          ${isDragging
                        ? 'border-accent-light bg-accent/5'
                        : 'border-[rgba(255,255,255,0.08)] hover:border-accent/30'
                    }
          ${files.length >= MAX_FILES ? 'opacity-50 pointer-events-none' : ''}`}
                onClick={() => document.getElementById(inputId)?.click()}
            >
                {/* Subtle gradient overlay on drag */}
                {isDragging && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0 rounded-2xl"
                        style={{ background: 'radial-gradient(ellipse at center, var(--accent-glow) 0%, transparent 70%)' }}
                    />
                )}

                <div className="relative flex flex-col items-center space-y-4">
                    <motion.div
                        animate={isDragging ? { scale: 1.15, rotate: 5 } : { scale: 1, rotate: 0 }}
                        transition={{ type: 'spring', stiffness: 300 }}
                        className="p-4 rounded-2xl"
                        style={{ background: isDragging ? 'var(--accent-glow)' : 'var(--bg-elevated)' }}
                    >
                        <Upload
                            size={28}
                            style={{ color: isDragging ? 'var(--accent-light)' : 'var(--text-tertiary)' }}
                        />
                    </motion.div>
                    <div className="space-y-1">
                        <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                            {files.length >= MAX_FILES ? 'Maximum files reached' : 'Drag & drop essays here'}
                        </p>
                        <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                            Supports TXT, DOC, DOCX, PDF — up to {MAX_FILES} files
                        </p>
                    </div>
                </div>

                <input
                    id={inputId}
                    type="file"
                    onChange={handleInputChange}
                    className="hidden"
                    accept=".txt,.doc,.docx,.pdf"
                    multiple
                    disabled={files.length >= MAX_FILES}
                />
            </motion.div>

            {/* File list */}
            <AnimatePresence>
                {files.length > 0 && (
                    <motion.div
                        variants={containerVariants}
                        initial="hidden"
                        animate="visible"
                        exit="hidden"
                        className="space-y-2 max-h-56 overflow-y-auto pr-1"
                    >
                        <AnimatePresence>
                            {files.map((file, index) => (
                                <motion.div
                                    key={file.name + index}
                                    variants={itemVariants}
                                    initial="hidden"
                                    animate="visible"
                                    exit="exit"
                                    layout
                                    className="flex items-center justify-between p-3 rounded-xl transition-colors duration-200"
                                    style={{
                                        background: 'var(--bg-elevated)',
                                        border: '1px solid var(--border-subtle)',
                                    }}
                                >
                                    <div className="flex items-center gap-3 overflow-hidden">
                                        <div className="flex-shrink-0 p-1.5 rounded-lg" style={{ background: 'var(--accent-glow)' }}>
                                            <FileText size={14} style={{ color: 'var(--accent-light)' }} />
                                        </div>
                                        <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }} title={file.name}>
                                            {file.name}
                                        </span>
                                    </div>
                                    <motion.button
                                        whileHover={{ scale: 1.15, rotate: 90 }}
                                        whileTap={{ scale: 0.9 }}
                                        onClick={(e) => { e.stopPropagation(); removeFile(index); }}
                                        className="p-1.5 rounded-full flex-shrink-0 transition-colors"
                                        style={{ color: 'var(--text-tertiary)' }}
                                        title={`Remove ${file.name}`}
                                    >
                                        <X size={14} />
                                    </motion.button>
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

const ResultItem = React.memo(({ result, onDownload, onRemove }) => {
    const studentName = result.student_name || 'Unknown Student';
    const score = typeof result.score === 'number' ? result.score.toFixed(1) : 'N/A';
    const maxScore = typeof result.maxScore === 'number' ? result.maxScore : 'N/A';

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            transition={{ duration: 0.3 }}
            className="flex items-center justify-between p-4 rounded-xl transition-all duration-200"
            style={{
                background: result.error ? 'var(--error-bg)' : 'var(--bg-elevated)',
                border: `1px solid ${result.error ? 'rgba(248, 113, 113, 0.15)' : 'var(--border-subtle)'}`,
            }}
        >
            <div className="flex items-center gap-4 overflow-hidden">
                <div
                    className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{
                        background: result.error ? 'var(--error-bg)' : 'var(--accent-glow)',
                        color: result.error ? 'var(--error)' : 'var(--accent-light)',
                    }}
                >
                    {result.error ? <AlertTriangle size={18} /> : <CheckCircle size={18} />}
                </div>
                <div className="overflow-hidden">
                    <p
                        className="font-semibold text-sm truncate"
                        style={{ color: result.error ? 'var(--error)' : 'var(--text-primary)' }}
                        title={studentName}
                    >
                        {studentName}
                    </p>
                    <p className="text-xs truncate" style={{ color: 'var(--text-tertiary)' }} title={result.filename}>
                        {result.filename}
                    </p>
                    {!result.error && (
                        <p className="font-semibold text-xs mt-0.5" style={{ color: 'var(--accent-light)' }}>
                            Score: {score} / {maxScore}
                        </p>
                    )}
                </div>
            </div>
            <div className="flex gap-1 flex-shrink-0 ml-2">
                {!result.error && (
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={onDownload}
                        className="p-2 rounded-lg transition-colors"
                        style={{ color: 'var(--text-tertiary)' }}
                        title="Download report"
                    >
                        <Download size={16} />
                    </motion.button>
                )}
                <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={onRemove}
                    className="p-2 rounded-lg transition-colors"
                    style={{ color: 'var(--text-tertiary)' }}
                    title="Remove result"
                >
                    <X size={16} />
                </motion.button>
            </div>
        </motion.div>
    );
});

// ═══════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════

const EssayEvaluator = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [files, setFiles] = useState([]);
    const [essayText, setEssayText] = useState('');
    const [results, setResults] = useState([]);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('upload');
    const [processingMessage, setProcessingMessage] = useState('');
    const [rubricText, setRubricText] = useState('');
    const [rubricFile, setRubricFile] = useState(null);
    const [selectedPresetRubric, setSelectedPresetRubric] = useState('');
    const [sessionId, setSessionId] = useState(null);
    const [includeCriteria, setIncludeCriteria] = useState(true);
    const [includeSuggestions, setIncludeSuggestions] = useState(true);
    const [includeHighlights, setIncludeHighlights] = useState(true);
    const [includeMiniLessons, setIncludeMiniLessons] = useState(true);
    const [generosity, setGenerosity] = useState('standard');

    const essayPasteAreaId = useId();
    const presetRubricId = useId();
    const rubricFileUploadId = useId();
    const rubricPasteAreaId = useId();
    const generosityId = useId();

    useEffect(() => {
        if (error) {
            const timer = setTimeout(() => setError(null), 6000);
            return () => clearTimeout(timer);
        }
    }, [error]);

    const handlePresetRubricChange = useCallback((e) => {
        const selectedId = e.target.value;
        setSelectedPresetRubric(selectedId);
        const preset = presetRubrics.find(r => r.id === selectedId);
        if (preset) {
            setRubricText(preset.content);
            setRubricFile(null);
        } else {
            if (!rubricFile) setRubricText('');
        }
    }, [rubricFile]);

    const handleRubricTextChange = useCallback((e) => {
        setRubricText(e.target.value);
        if (e.target.value.trim() !== '') {
            setSelectedPresetRubric('');
            setRubricFile(null);
            const fileInput = document.getElementById(rubricFileUploadId);
            if (fileInput) fileInput.value = '';
        }
    }, [rubricFileUploadId]);

    const handleRubricFileUpload = useCallback((e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size === 0) { setError('Cannot use an empty rubric file.'); e.target.value = ''; return; }
        const allowedTypes = ['text/plain', 'application/pdf'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|pdf)$/i)) {
            setError('Invalid rubric file type. Please use .txt or .pdf');
            e.target.value = '';
            return;
        }
        setRubricFile(file);
        setRubricText('');
        setSelectedPresetRubric('');
        setError(null);
    }, []);

    const handleSubmit = useCallback(async () => {
        if (activeTab === 'upload' && files.length === 0) { setError('Please upload at least one essay file.'); return; }
        if (activeTab === 'paste' && !essayText.trim()) { setError('Please paste your essay text.'); return; }

        setError(null);
        setResults([]);
        setSessionId(null);
        setIsLoading(true);

        const processItem = async (item, identifier) => {
            setProcessingMessage(`Evaluating "${identifier}"...`);
            const formData = new FormData();
            if (rubricFile) formData.append('rubric_file', rubricFile);
            else if (rubricText.trim()) formData.append('rubric_text', rubricText.trim());
            formData.append('include_criteria', String(includeCriteria));
            formData.append('include_suggestions', String(includeSuggestions));
            formData.append('include_highlights', String(includeHighlights));
            formData.append('include_mini_lessons', String(includeMiniLessons));
            formData.append('generosity', generosity);

            if (activeTab === 'upload') formData.append('essay', item, identifier);
            else formData.append('essay', new Blob([item], { type: 'text/plain' }), identifier);

            try {
                const response = await fetch(`${API_BASE_URL}/evaluate/`, { method: 'POST', body: formData });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: 'Unknown evaluation error' }));
                    throw new Error(errorData.detail || `Evaluation failed for "${identifier}"`);
                }
                const data = await response.json();
                if (!sessionId) setSessionId(data.session_id);

                let newResults = [];
                if (data.evaluation_status === 'empty') {
                    setError(`No valid essay content found in "${identifier}".`);
                } else if (data.results && Array.isArray(data.results)) {
                    newResults = data.results.map((r, i) => ({
                        id: `${data.session_id}-${r.filename || i}-${Math.random()}`,
                        filename: r.filename,
                        student_name: r.student_name,
                        score: r.overall_score,
                        maxScore: r.max_score,
                        error: r.error,
                        sessionId: data.session_id,
                    }));
                } else {
                    setError(`Received an unexpected response format for "${identifier}".`);
                }
                setResults(prev => [...prev, ...newResults]);
            } catch (err) {
                setResults(prev => [...prev, {
                    id: `error-${identifier}-${Date.now()}`,
                    filename: identifier,
                    student_name: 'Evaluation Failed',
                    error: err.message || 'Network error or server issue.',
                    sessionId: sessionId,
                }]);
                setError(err.message || `Failed to process "${identifier}".`);
            }
        };

        try {
            if (activeTab === 'upload') {
                const pdfFiles = files.filter(f => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
                if (pdfFiles.length > 1) throw new Error('Only one PDF file can be evaluated at a time.');
                if (pdfFiles.length === 1) {
                    await processItem(pdfFiles[0], pdfFiles[0].name);
                } else if (files.length > 0) {
                    await processItem(files[0], files[0].name);
                    if (files.length > 1) alert('Multiple non-PDF files selected — only the first will be processed.');
                }
            } else {
                await processItem(essayText, 'pasted-essay.txt');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
            setProcessingMessage('');
        }
    }, [activeTab, files, essayText, rubricFile, rubricText, includeCriteria, includeSuggestions, includeHighlights, includeMiniLessons, generosity, sessionId]);

    const handleDownload = useCallback(async (result) => {
        if (!result.sessionId || !result.filename) { setError('Cannot download: missing data.'); return; }
        const downloadUrl = `${API_BASE_URL}/download-report/${result.sessionId}/${encodeURIComponent(result.filename)}`;
        setIsLoading(true);
        setProcessingMessage(`Downloading ${result.filename}...`);
        try {
            const response = await fetch(downloadUrl);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Download failed' }));
                throw new Error(errorData.detail || 'Download failed');
            }
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = result.filename.replace(/[^a-z0-9._-\s]/gi, '_').replace(/_{2,}/g, '_');
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setError(err.message || 'Download error');
        } finally {
            setIsLoading(false);
            setProcessingMessage('');
        }
    }, []);

    const handleDownloadAll = useCallback(() => {
        const validResults = results.filter(r => !r.error && r.sessionId && r.filename);
        if (validResults.length === 0) return;
        validResults.forEach((result, index) => {
            setTimeout(() => handleDownload(result), index * 200);
        });
    }, [results, handleDownload]);

    const handleRemoveResult = useCallback((idToRemove) => {
        setResults(prev => prev.filter(r => r.id !== idToRemove));
    }, []);

    // ─── Input classes ───
    const inputClass = "w-full p-3 rounded-xl text-sm transition-all duration-200"
        + " bg-[var(--bg-deep)] border border-[var(--border-subtle)]"
        + " text-[var(--text-primary)] placeholder-[var(--text-tertiary)]"
        + " focus:border-[var(--accent)] focus:shadow-[0_0_0_3px_var(--accent-glow)] focus:outline-none";

    const selectClass = inputClass + " cursor-pointer";

    // ═══════════════════════════════════════════════
    // RENDER
    // ═══════════════════════════════════════════════

    return (
        <div className="min-h-screen relative overflow-hidden" style={{ background: 'var(--bg-deep)' }}>
            <AnimatedBackground intensity="subtle" />

            <div className="relative z-10 pt-24 pb-20 px-4 md:px-8 max-w-4xl mx-auto">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-12"
                >
                    <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-gradient mb-3">
                        LitMark
                    </h1>
                    <p className="text-base max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                        AI-powered feedback on your writing. Simple, fast, and effective.
                    </p>
                </motion.div>

                <div className="space-y-8">
                    {/* Tab Bar */}
                    <LayoutGroup>
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2 }}
                            className="flex justify-center"
                        >
                            <div className="glass rounded-2xl p-1.5 flex gap-1">
                                <TabButton id="upload" label="Upload" icon={Upload} activeTab={activeTab} onClick={setActiveTab} />
                                <TabButton id="paste" label="Paste" icon={Clipboard} activeTab={activeTab} onClick={setActiveTab} />
                                <TabButton id="rubric" label="Rubric" icon={Settings} activeTab={activeTab} onClick={setActiveTab} />
                            </div>
                        </motion.div>
                    </LayoutGroup>

                    {/* Tab Content */}
                    <AnimatePresence mode="wait">
                        {activeTab === 'upload' ? (
                            <motion.div key="upload" variants={tabContentVariants} initial="hidden" animate="visible" exit="exit">
                                <GlassCard>
                                    <FileUploadCard files={files} setFiles={setFiles} />
                                </GlassCard>
                            </motion.div>
                        ) : activeTab === 'paste' ? (
                            <motion.div key="paste" variants={tabContentVariants} initial="hidden" animate="visible" exit="exit">
                                <GlassCard>
                                    <textarea
                                        id={essayPasteAreaId}
                                        value={essayText}
                                        onChange={(e) => setEssayText(e.target.value)}
                                        placeholder="Paste your essay text here..."
                                        className={`${inputClass} h-80 resize-none leading-relaxed`}
                                    />
                                </GlassCard>
                            </motion.div>
                        ) : (
                            <motion.div key="rubric" variants={tabContentVariants} initial="hidden" animate="visible" exit="exit">
                                <GlassCard>
                                    <div className="space-y-8">
                                        <div>
                                            <h3
                                                className="text-lg font-semibold pb-3 mb-6 border-b"
                                                style={{ color: 'var(--text-primary)', borderColor: 'var(--border-subtle)' }}
                                            >
                                                Rubric Configuration
                                            </h3>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                <div className="space-y-5">
                                                    <div>
                                                        <label htmlFor={presetRubricId} className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                                                            Preset Rubric
                                                        </label>
                                                        <select
                                                            id={presetRubricId}
                                                            value={selectedPresetRubric}
                                                            onChange={handlePresetRubricChange}
                                                            className={selectClass}
                                                        >
                                                            <option value="">-- Custom / Default --</option>
                                                            {presetRubrics.map(rubric => (
                                                                <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
                                                            ))}
                                                        </select>
                                                    </div>
                                                    <div>
                                                        <label htmlFor={rubricFileUploadId} className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                                                            Upload Rubric (.txt, .pdf)
                                                        </label>
                                                        <input
                                                            id={rubricFileUploadId}
                                                            type="file"
                                                            onChange={handleRubricFileUpload}
                                                            accept=".txt,.pdf"
                                                            className="w-full text-sm cursor-pointer file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold transition-all"
                                                            style={{
                                                                color: 'var(--text-tertiary)',
                                                            }}
                                                        />
                                                        {rubricFile && (
                                                            <p className="mt-2 text-xs" style={{ color: 'var(--success)' }}>
                                                                Selected: {rubricFile.name}
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                                <div>
                                                    <label htmlFor={rubricPasteAreaId} className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                                                        Custom Rubric Text
                                                    </label>
                                                    <textarea
                                                        id={rubricPasteAreaId}
                                                        value={rubricText}
                                                        onChange={handleRubricTextChange}
                                                        className={`${inputClass} h-48 resize-none`}
                                                        placeholder="Paste criteria here..."
                                                        disabled={!!rubricFile || !!selectedPresetRubric}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </GlassCard>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Submit Button */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="flex justify-center"
                    >
                        <motion.button
                            whileHover={{ scale: isLoading ? 1 : 1.02 }}
                            whileTap={{ scale: isLoading ? 1 : 0.98 }}
                            onClick={handleSubmit}
                            disabled={isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim())}
                            className="group w-full max-w-md py-3.5 px-8 rounded-2xl font-semibold text-base transition-all duration-300 flex items-center justify-center gap-3 disabled:opacity-40 disabled:cursor-not-allowed"
                            style={{
                                background: isLoading
                                    ? 'var(--bg-elevated)'
                                    : 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                                color: isLoading ? 'var(--text-tertiary)' : 'white',
                                boxShadow: isLoading ? 'none' : '0 0 30px -5px rgba(99, 102, 241, 0.3)',
                            }}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 size={18} className="animate-spin" />
                                    <span>{processingMessage || 'Processing...'}</span>
                                </>
                            ) : (
                                <>
                                    <Sparkles size={18} />
                                    Evaluate Essays
                                    <ArrowRight size={16} className="transition-transform duration-300 group-hover:translate-x-1" />
                                </>
                            )}
                        </motion.button>
                    </motion.div>

                    {/* Error */}
                    <AnimatePresence>
                        {error && (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="max-w-xl mx-auto p-4 rounded-xl text-sm flex items-center gap-3"
                                style={{
                                    background: 'var(--error-bg)',
                                    border: '1px solid rgba(248, 113, 113, 0.15)',
                                    color: 'var(--error)',
                                }}
                            >
                                <AlertTriangle size={16} />
                                {error}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Results */}
                    <AnimatePresence>
                        {results.length > 0 && (
                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="mt-8"
                            >
                                <GlassCard>
                                    <div className="flex items-center justify-between mb-6 pb-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                                        <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                                            Evaluation Results
                                        </h2>
                                        <span className="text-sm px-3 py-1 rounded-full glass" style={{ color: 'var(--accent-light)' }}>
                                            {results.filter(r => !r.error).length} completed
                                        </span>
                                    </div>
                                    <div className="space-y-3">
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
                                    {results.filter(r => !r.error).length > 1 && (
                                        <div className="mt-6 flex justify-center pt-5 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                                            <motion.button
                                                whileHover={{ scale: 1.03 }}
                                                whileTap={{ scale: 0.97 }}
                                                onClick={handleDownloadAll}
                                                className="px-6 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2 glass transition-colors"
                                                style={{ color: 'var(--text-secondary)' }}
                                            >
                                                {isLoading && processingMessage.startsWith('Downloading')
                                                    ? <Loader2 size={14} className="animate-spin" />
                                                    : <Download size={14} />
                                                }
                                                Download All Reports
                                            </motion.button>
                                        </div>
                                    )}
                                </GlassCard>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Footer */}
                <footer className="text-center mt-20">
                    <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                        © {new Date().getFullYear()} LitMark. AI Evaluation Tool.
                    </p>
                </footer>
            </div>
        </div>
    );
};

export default EssayEvaluator;