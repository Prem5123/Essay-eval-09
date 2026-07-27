import {
    memo,
    useCallback,
    useEffect,
    useId,
    useLayoutEffect,
    useMemo,
    useRef,
    useState,
} from 'react';
import { m, AnimatePresence } from 'framer-motion';
import {
    Upload, FileText, Loader2, X, Download, AlertTriangle,
    CheckCircle, Settings, Clipboard, Sparkles, ArrowRight, Package, BookOpen, Palette
} from 'lucide-react';
import presetRubrics from '../utils/presetRubrics';
import { useAuth } from '../contexts/AuthContext';
import {
    estimateBatchTransferSize,
    getResponseError,
    mergeImportedRubrics,
    normalizeApiBaseUrl,
    parseSavedRubrics,
    sortEvaluationResults,
} from '../utils/evaluationHelpers';

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_URL);
const MAX_FILES = 10;
const MAX_ESSAY_FILE_SIZE = 15 * 1024 * 1024;
const MAX_TOTAL_ESSAY_FILE_SIZE = 60 * 1024 * 1024;
const MAX_RUBRIC_FILE_SIZE = 5 * 1024 * 1024;
const MAX_PASTED_TEXT_LENGTH = 500_000;
const MAX_RUBRIC_TEXT_LENGTH = 100_000;
const MAX_BATCH_TRANSFER_SIZE = 75 * 1024 * 1024;
const AUTH_TOKEN_TIMEOUT_MS = 20 * 1000;
const EVALUATION_TIMEOUT_MS = 3 * 60 * 1000;
const REPORT_DOWNLOAD_TIMEOUT_MS = 60 * 1000;
const REPORT_URL_REVOKE_DELAY_MS = 10 * 1000;
const EVALUATION_CONCURRENCY = 2;
const TAB_ORDER = ['upload', 'paste', 'rubric'];

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
    <m.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.98 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className={`glass glow-border rounded-2xl p-6 md:p-8 ${className}`}
    >
        {children}
    </m.div>
);

const TabButton = ({ id, label, icon: Icon, activeTab, onClick, onKeyDown }) => (
    <button
        id={`tab-${id}`}
        type="button"
        role="tab"
        aria-selected={activeTab === id}
        aria-controls={`panel-${id}`}
        tabIndex={activeTab === id ? 0 : -1}
        onClick={() => onClick(id)}
        onKeyDown={(event) => onKeyDown(event, id)}
        className="relative flex-1 px-3 sm:px-5 py-2.5 rounded-xl text-sm font-medium transition-colors duration-200 flex items-center justify-center gap-2"
        style={{
            color: activeTab === id ? 'var(--text-primary)' : 'var(--text-secondary)',
        }}
    >
        <span className="relative z-10 flex items-center gap-2">
            <Icon size={15} />
            {label}
        </span>
        {activeTab === id && (
            <m.div
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

const FileUploadCard = memo(({ files, setFiles, onError }) => {
    const [isDragging, setIsDragging] = useState(false);
    const inputId = useId();
    const inputRef = useRef(null);
    const uploadButtonRef = useRef(null);
    const removeButtonRefs = useRef([]);
    const selectionStartedFromUploadButtonRef = useRef(false);
    const descriptionId = `${inputId}-description`;

    const validateFile = useCallback((file) => {
        if (file.size === 0) {
            onError(`Cannot read an empty file: “${file.name}”.`);
            return false;
        }
        if (file.size > MAX_ESSAY_FILE_SIZE) {
            onError(`“${file.name}” is larger than the 15 MB upload limit.`);
            return false;
        }
        const allowedTypes = ['text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/pdf'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|docx|pdf)$/i)) {
            onError(`Unsupported file type: “${file.name}”. Use TXT, DOCX, or PDF.`);
            return false;
        }
        return true;
    }, [onError]);

    const handleFiles = useCallback((newFilesArray, shouldMoveFocus = false) => {
        const validFiles = newFilesArray.filter(validateFile);
        if (validFiles.length === 0) return;
        const seenKeys = new Set(
            files.map(file => `${file.name}-${file.size}-${file.lastModified}`),
        );
        const uniqueFiles = validFiles.filter((file) => {
            const key = `${file.name}-${file.size}-${file.lastModified}`;
            if (seenKeys.has(key)) return false;
            seenKeys.add(key);
            return true;
        });
        const availableSlots = MAX_FILES - files.length;
        const currentTotalSize = files.reduce((total, file) => total + file.size, 0);
        let nextTotalSize = currentTotalSize;
        let skippedForBatchSize = false;
        const filesWithinBatchLimit = [];

        uniqueFiles.forEach((file) => {
            if (nextTotalSize + file.size > MAX_TOTAL_ESSAY_FILE_SIZE) {
                skippedForBatchSize = true;
                return;
            }
            filesWithinBatchLimit.push(file);
            nextTotalSize += file.size;
        });

        const messages = [];
        if (uniqueFiles.length > availableSlots) {
            messages.push(`You can evaluate up to ${MAX_FILES} files at a time.`);
        }
        if (skippedForBatchSize) {
            messages.push('Some files were skipped because a batch can contain up to 60 MB of essays.');
        }
        if (uniqueFiles.length < validFiles.length) {
            messages.push('Duplicate files were skipped.');
        }
        if (messages.length > 0) {
            onError(messages.join(' '));
        } else if (validFiles.length === newFilesArray.length) {
            onError(null);
        }

        const filesToAdd = filesWithinBatchLimit.slice(0, availableSlots);
        const nextFileCount = files.length + filesToAdd.length;
        setFiles(prev => [...prev, ...filesToAdd]);
        if (shouldMoveFocus && nextFileCount >= MAX_FILES) {
            window.requestAnimationFrame(() => {
                removeButtonRefs.current[nextFileCount - 1]?.focus();
            });
        }
    }, [files, onError, setFiles, validateFile]);

    const handleDrop = useCallback((e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(Array.from(e.dataTransfer.files));
    }, [handleFiles]);

    const handleInputChange = useCallback((e) => {
        const shouldMoveFocus = selectionStartedFromUploadButtonRef.current;
        selectionStartedFromUploadButtonRef.current = false;
        handleFiles(Array.from(e.target.files), shouldMoveFocus);
        e.target.value = '';
    }, [handleFiles]);

    const removeFile = useCallback((index) => {
        const nextFiles = files.filter((_, fileIndex) => fileIndex !== index);
        setFiles(nextFiles);
        window.requestAnimationFrame(() => {
            if (nextFiles.length === 0) {
                uploadButtonRef.current?.focus();
                return;
            }
            const nextIndex = Math.min(index, nextFiles.length - 1);
            removeButtonRefs.current[nextIndex]?.focus();
        });
    }, [files, setFiles]);

    return (
        <div className="space-y-5">
            <m.button
                ref={uploadButtonRef}
                type="button"
                disabled={files.length >= MAX_FILES}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
                onDrop={handleDrop}
                whileHover={{ scale: 1.005 }}
                className={`relative w-full border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center transition-all duration-300 cursor-pointer
	          ${isDragging
                        ? 'border-[var(--accent)] bg-[var(--accent-glow)]'
                        : 'border-[var(--border-control)] hover:border-[var(--accent)]'
                    }
	          ${files.length >= MAX_FILES ? 'opacity-50' : ''}`}
                onClick={() => {
                    selectionStartedFromUploadButtonRef.current = true;
                    inputRef.current?.click();
                }}
                aria-describedby={descriptionId}
            >
                {/* Subtle gradient overlay on drag */}
                {isDragging && (
                    <m.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0 rounded-2xl"
                        style={{ background: 'radial-gradient(ellipse at center, var(--accent-glow) 0%, transparent 70%)' }}
                    />
                )}

                <div className="relative flex flex-col items-center space-y-4">
                    <m.div
                        animate={isDragging ? { scale: 1.15, rotate: 5 } : { scale: 1, rotate: 0 }}
                        transition={{ type: 'spring', stiffness: 300 }}
                        className="p-4 rounded-2xl"
                        style={{ background: isDragging ? 'var(--accent-glow)' : 'var(--bg-elevated)' }}
                    >
                        <Upload
                            size={28}
                            style={{ color: isDragging ? 'var(--accent-ink)' : 'var(--text-tertiary)' }}
                        />
                    </m.div>
                    <div className="space-y-1">
                        <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                            {files.length >= MAX_FILES ? 'Maximum files reached' : 'Drag & drop essays here'}
                        </p>
                        <p id={descriptionId} className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                            Supports TXT, DOCX, and PDF — up to {MAX_FILES} files, 15 MB each and 60 MB total
                        </p>
                    </div>
                </div>

            </m.button>

                <input
                    ref={inputRef}
                    id={inputId}
                    type="file"
                    onChange={handleInputChange}
                    className="sr-only"
                    accept=".txt,.docx,.pdf"
                    multiple
                    disabled={files.length >= MAX_FILES}
                    tabIndex={-1}
                    aria-label="Choose essay files"
                    aria-describedby={descriptionId}
                />

            {/* File list */}
            <AnimatePresence>
                {files.length > 0 && (
                    <m.div
                        variants={containerVariants}
                        initial="hidden"
                        animate="visible"
                        exit="hidden"
                        className="space-y-2 max-h-56 overflow-y-auto pr-1"
                    >
                        <AnimatePresence>
                            {files.map((file, index) => (
                                <m.div
                                    key={`${file.name}-${file.size}-${file.lastModified}`}
                                    variants={itemVariants}
                                    initial="hidden"
                                    animate="visible"
                                    exit="exit"
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
                                    <m.button
                                        ref={(node) => {
                                            removeButtonRefs.current[index] = node;
                                        }}
                                        type="button"
                                        whileHover={{ scale: 1.15, rotate: 90 }}
                                        whileTap={{ scale: 0.9 }}
                                        onClick={(e) => { e.stopPropagation(); removeFile(index); }}
                                        className="p-1.5 rounded-full flex-shrink-0 transition-colors"
                                        style={{ color: 'var(--text-tertiary)' }}
                                        title={`Remove ${file.name}`}
                                        aria-label={`Remove ${file.name}`}
                                    >
                                        <X size={14} />
                                    </m.button>
                                </m.div>
                            ))}
                        </AnimatePresence>
                    </m.div>
                )}
            </AnimatePresence>
            <p className="sr-only" role="status" aria-live="polite">
                {files.length === 0
                    ? 'No essay files selected.'
                    : `${files.length} essay ${files.length === 1 ? 'file' : 'files'} selected.`}
            </p>
        </div>
    );
});
FileUploadCard.displayName = 'FileUploadCard';

const ResultItem = memo(({
    result,
    onDownload,
    onRemove,
    registerRemoveButton,
    actionsDisabled,
}) => {
    const studentName = result.student_name || 'Unknown Student';
    const score = typeof result.score === 'number' ? result.score.toFixed(1) : 'N/A';
    const maxScore = typeof result.maxScore === 'number' ? result.maxScore : 'N/A';

    return (
        <m.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between p-4 rounded-xl transition-all duration-200"
            style={{
                background: result.error ? 'var(--error-bg)' : 'var(--bg-elevated)',
                border: `1px solid ${result.error ? 'rgba(248, 113, 113, 0.15)' : 'var(--border-subtle)'}`,
                contentVisibility: 'auto',
                containIntrinsicSize: 'auto 84px',
            }}
        >
            <div className="flex min-w-0 items-center gap-4 overflow-hidden">
                <div
                    className="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{
                        background: result.error ? 'var(--error-bg)' : 'var(--accent-glow)',
                        color: result.error ? 'var(--error)' : 'var(--accent-light)',
                    }}
                >
                    {result.error ? <AlertTriangle size={18} /> : <CheckCircle size={18} />}
                </div>
                <div className="min-w-0 overflow-hidden">
                    <p
                        className="font-semibold text-sm truncate"
                        style={{ color: result.error ? 'var(--error)' : 'var(--text-primary)' }}
                        title={studentName}
                    >
                        {studentName}
                    </p>
                    <p className="text-xs truncate" style={{ color: 'var(--text-secondary)' }} title={result.filename}>
                        {result.filename}
                    </p>
                    {!result.error && (
                        <p className="font-semibold text-xs mt-0.5" style={{ color: 'var(--accent-ink)' }}>
                            Score: {score} / {maxScore}
                        </p>
                    )}
                    {result.error && (
                        <p className="mt-1 text-xs leading-relaxed [overflow-wrap:anywhere]" style={{ color: 'var(--error)' }}>
                            {result.error}
                        </p>
                    )}
                </div>
            </div>
            <div className="flex gap-1 flex-shrink-0 ml-2">
                {!result.error && (
                    <m.button
                        type="button"
                        whileHover={actionsDisabled ? undefined : { scale: 1.1 }}
                        whileTap={actionsDisabled ? undefined : { scale: 0.9 }}
                        onClick={(event) => {
                            void onDownload(result, event.currentTarget);
                        }}
                        disabled={actionsDisabled}
                        className="p-2 rounded-lg transition-colors disabled:cursor-wait disabled:opacity-50"
                        style={{ color: 'var(--text-tertiary)' }}
                        title="Download report"
                        aria-label={`Download report for ${studentName}`}
                    >
                        <Download size={16} />
                    </m.button>
                )}
                <m.button
                    ref={(node) => registerRemoveButton(result.id, node)}
                    type="button"
                    whileHover={actionsDisabled ? undefined : { scale: 1.1 }}
                    whileTap={actionsDisabled ? undefined : { scale: 0.9 }}
                    onClick={() => onRemove(result.id)}
                    disabled={actionsDisabled}
                    className="p-2 rounded-lg transition-colors disabled:cursor-wait disabled:opacity-50"
                    style={{ color: 'var(--text-tertiary)' }}
                    title="Remove result"
                    aria-label={`Remove result for ${studentName}`}
                >
                    <X size={16} />
                </m.button>
            </div>
        </m.div>
    );
});
ResultItem.displayName = 'ResultItem';

// ═══════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════

const EssayEvaluator = () => {
    const { currentUser } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [files, setFiles] = useState([]);
    const [hasEssayText, setHasEssayText] = useState(false);
    const [results, setResults] = useState([]);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('upload');
    const [processingMessage, setProcessingMessage] = useState('');
    const [isDownloadingReports, setIsDownloadingReports] = useState(false);
    const [downloadStatus, setDownloadStatus] = useState('');
    const [rubricFile, setRubricFile] = useState(null);
    const [hasRubricText, setHasRubricText] = useState(false);
    const [selectedPresetRubric, setSelectedPresetRubric] = useState('');
    const [includeCriteria, setIncludeCriteria] = useState(true);
    const [includeSuggestions, setIncludeSuggestions] = useState(true);
    const [includeHighlights, setIncludeHighlights] = useState(true);
    const [includeMiniLessons, setIncludeMiniLessons] = useState(true);
    const [generosity, setGenerosity] = useState('standard');
    const [paperMode, setPaperMode] = useState('organization');
    const [pdfReportPreset, setPdfReportPreset] = useState('classic');
    const [accentColor, setAccentColor] = useState('');
    const [accentColorError, setAccentColorError] = useState('');
    const [savedRubrics, setSavedRubrics] = useState([]);
    const [legacyRubrics, setLegacyRubrics] = useState([]);
    const [rubricStatus, setRubricStatus] = useState('');
    const essayTextValueRef = useRef('');
    const rubricTextValueRef = useRef('');
    const essayTextAreaRef = useRef(null);
    const rubricTextAreaRef = useRef(null);
    const presetRubricSelectRef = useRef(null);
    const rubricFileInputRef = useRef(null);
    const accentColorInputRef = useRef(null);
    const evaluateButtonRef = useRef(null);
    const cancelButtonRef = useRef(null);
    const downloadStatusRef = useRef(null);
    const pageHeadingRef = useRef(null);
    const resultRemoveButtonRefs = useRef(new Map());
    const downloadInProgressRef = useRef(false);
    const activeControllersRef = useRef(new Set());
    const cancelTokenWaitRef = useRef(null);
    const isMountedRef = useRef(true);
    const cancelledByUserRef = useRef(false);
    const activeUserIdRef = useRef(currentUser?.uid || null);
    const evaluationRunIdRef = useRef(0);

    const essayPasteAreaId = useId();
    const presetRubricId = useId();
    const rubricFileUploadId = useId();
    const rubricPasteAreaId = useId();
    const generosityId = useId();
    const accentColorId = useId();
    const accentColorHelpId = `${accentColorId}-help`;
    const rubricStorageKey = useMemo(
        () => currentUser?.uid ? `customRubrics:${currentUser.uid}` : null,
        [currentUser?.uid],
    );

    useEffect(() => {
        if (!rubricStorageKey) {
            setSavedRubrics([]);
            setLegacyRubrics([]);
            return;
        }

        try {
            const scopedValue = localStorage.getItem(rubricStorageKey);
            setSavedRubrics(parseSavedRubrics(scopedValue));
        } catch (storageError) {
            console.error('Failed to load saved rubrics', storageError);
            setSavedRubrics([]);
            setError('Saved rubrics could not be loaded from this browser.');
        }

        try {
            setLegacyRubrics(parseSavedRubrics(localStorage.getItem('customRubrics')));
        } catch (storageError) {
            console.error('Failed to load legacy rubrics', storageError);
            setLegacyRubrics([]);
        }
    }, [rubricStorageKey]);

    useEffect(() => {
        isMountedRef.current = true;
        const activeControllers = activeControllersRef.current;
        return () => {
            isMountedRef.current = false;
            cancelledByUserRef.current = true;
            cancelTokenWaitRef.current?.();
            cancelTokenWaitRef.current = null;
            activeControllers.forEach(controller => controller.abort());
            activeControllers.clear();
        };
    }, []);

    useLayoutEffect(() => {
        const nextUserId = currentUser?.uid || null;
        const previousUserId = activeUserIdRef.current;
        activeUserIdRef.current = nextUserId;

        if (!previousUserId || previousUserId === nextUserId) return;

        evaluationRunIdRef.current += 1;
        cancelledByUserRef.current = true;
        cancelTokenWaitRef.current?.();
        cancelTokenWaitRef.current = null;
        activeControllersRef.current.forEach(controller => controller.abort());
        activeControllersRef.current.clear();
        downloadInProgressRef.current = false;

        essayTextValueRef.current = '';
        rubricTextValueRef.current = '';
        if (essayTextAreaRef.current) essayTextAreaRef.current.value = '';
        if (rubricTextAreaRef.current) rubricTextAreaRef.current.value = '';
        if (rubricFileInputRef.current) rubricFileInputRef.current.value = '';

        setIsLoading(false);
        setFiles([]);
        setHasEssayText(false);
        setResults([]);
        setError(null);
        setActiveTab('upload');
        setProcessingMessage('');
        setIsDownloadingReports(false);
        setDownloadStatus('');
        setRubricFile(null);
        setHasRubricText(false);
        setSelectedPresetRubric('');
        setRubricStatus('');
        setIncludeCriteria(true);
        setIncludeSuggestions(true);
        setIncludeHighlights(true);
        setIncludeMiniLessons(true);
        setGenerosity('standard');
        setPaperMode('organization');
        setPdfReportPreset('classic');
        setAccentColor('');
        setAccentColorError('');
    }, [currentUser?.uid]);

    const persistSavedRubrics = useCallback((nextRubrics) => {
        if (!rubricStorageKey) return false;
        try {
            localStorage.setItem(rubricStorageKey, JSON.stringify(nextRubrics));
            setSavedRubrics(nextRubrics);
            return true;
        } catch (storageError) {
            console.error('Failed to save custom rubrics', storageError);
            setError('This rubric could not be saved in your browser.');
            return false;
        }
    }, [rubricStorageKey]);

    const saveCustomRubric = useCallback(() => {
        const rubricText = rubricTextValueRef.current;
        if (!rubricText.trim()) { setError("Cannot save an empty rubric."); return; }
        const name = window.prompt('Enter a name for this rubric:')?.trim();
        if (!name) return;

        const newRubric = { id: `custom-${Date.now()}`, name: `(Custom) ${name}`, content: rubricText, isCustom: true };
        const updatedRubrics = [...savedRubrics, newRubric];
        if (persistSavedRubrics(updatedRubrics)) {
            setSelectedPresetRubric(newRubric.id);
            setError(null);
            setRubricStatus(`Rubric “${newRubric.name}” was saved.`);
            window.requestAnimationFrame(() => presetRubricSelectRef.current?.focus());
        }
    }, [persistSavedRubrics, savedRubrics]);

    const deleteCustomRubric = useCallback((id) => {
        if (window.confirm("Are you sure you want to delete this custom rubric?")) {
            const updated = savedRubrics.filter(r => r.id !== id);
            if (persistSavedRubrics(updated) && selectedPresetRubric === id) {
                setSelectedPresetRubric('');
                rubricTextValueRef.current = '';
                setHasRubricText(false);
                if (rubricTextAreaRef.current) rubricTextAreaRef.current.value = '';
                setRubricStatus('The custom rubric was deleted.');
                window.requestAnimationFrame(() => presetRubricSelectRef.current?.focus());
            }
        }
    }, [persistSavedRubrics, savedRubrics, selectedPresetRubric]);

    const importLegacyRubrics = useCallback(() => {
        if (legacyRubrics.length === 0 || !rubricStorageKey) return;
        const confirmed = window.confirm(
            'These rubrics were saved before browser data was separated by account. '
            + 'On a shared browser, they may belong to another person. Import them into your current account?',
        );
        if (!confirmed) return;

        let latestSavedRubrics = [];
        let latestLegacyRubrics = [];
        try {
            latestSavedRubrics = parseSavedRubrics(localStorage.getItem(rubricStorageKey));
            latestLegacyRubrics = parseSavedRubrics(localStorage.getItem('customRubrics'));
        } catch (storageError) {
            console.error('Failed to refresh rubrics before import', storageError);
            setError('Rubrics changed in another browser tab and could not be refreshed. Reload and try again.');
            return;
        }

        const mergedRubrics = mergeImportedRubrics(latestSavedRubrics, latestLegacyRubrics);
        const importedCount = mergedRubrics.length - latestSavedRubrics.length;
        if (!persistSavedRubrics(mergedRubrics)) return;

        try {
            localStorage.removeItem('customRubrics');
            setLegacyRubrics([]);
            setError(null);
            setRubricStatus(importedCount > 0
                ? `${importedCount} ${importedCount === 1 ? 'rubric was' : 'rubrics were'} imported.`
                : 'No new rubrics needed to be imported.');
        } catch (storageError) {
            console.error('Failed to remove legacy rubrics after import', storageError);
            setLegacyRubrics([]);
            setError('Rubrics were imported, but the old unassigned browser copy could not be removed.');
            setRubricStatus(importedCount > 0
                ? `${importedCount} ${importedCount === 1 ? 'rubric was' : 'rubrics were'} imported.`
                : 'No new rubrics needed to be imported.');
        }
        window.requestAnimationFrame(() => presetRubricSelectRef.current?.focus());
    }, [legacyRubrics, persistSavedRubrics, rubricStorageKey]);

    const handleTabKeyDown = useCallback((event, currentTab) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();

        const currentIndex = TAB_ORDER.indexOf(currentTab);
        let nextIndex = currentIndex;
        if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % TAB_ORDER.length;
        if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + TAB_ORDER.length) % TAB_ORDER.length;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = TAB_ORDER.length - 1;

        const nextTab = TAB_ORDER[nextIndex];
        setActiveTab(nextTab);
        window.requestAnimationFrame(() => document.getElementById(`tab-${nextTab}`)?.focus());
    }, []);

    const handleEssayTextChange = useCallback((event) => {
        const nextText = event.target.value;
        essayTextValueRef.current = nextText;
        const nextHasText = Boolean(nextText.trim());
        setHasEssayText(current => current === nextHasText ? current : nextHasText);
    }, []);

    const handlePresetRubricChange = useCallback((e) => {
        const selectedId = e.target.value;
        setSelectedPresetRubric(selectedId);

        // Check built-in presets first
        let preset = presetRubrics.find(r => r.id === selectedId);
        // Then check custom saved rubrics
        if (!preset) {
            preset = savedRubrics.find(r => r.id === selectedId);
        }

        if (preset) {
            rubricTextValueRef.current = preset.content;
            setHasRubricText(Boolean(preset.content.trim()));
            if (rubricTextAreaRef.current) rubricTextAreaRef.current.value = preset.content;
            setRubricFile(null);
            if (rubricFileInputRef.current) rubricFileInputRef.current.value = '';
        } else {
            if (!rubricFile) {
                rubricTextValueRef.current = '';
                setHasRubricText(false);
                if (rubricTextAreaRef.current) rubricTextAreaRef.current.value = '';
            }
        }
    }, [rubricFile, savedRubrics]);

    const handleRubricTextChange = useCallback((e) => {
        const nextText = e.target.value;
        rubricTextValueRef.current = nextText;
        const nextHasText = Boolean(nextText.trim());
        if (nextHasText !== hasRubricText) setHasRubricText(nextHasText);
    }, [hasRubricText]);

    const handleRubricFileUpload = useCallback((e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size === 0) { setError('Cannot use an empty rubric file.'); e.target.value = ''; return; }
        if (file.size > MAX_RUBRIC_FILE_SIZE) {
            setError('The rubric file is larger than the 5 MB limit.');
            e.target.value = '';
            return;
        }
        const allowedTypes = ['text/plain', 'application/pdf'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|pdf)$/i)) {
            setError('Invalid rubric file type. Please use .txt or .pdf');
            e.target.value = '';
            return;
        }
        setRubricFile(file);
        rubricTextValueRef.current = '';
        setHasRubricText(false);
        if (rubricTextAreaRef.current) rubricTextAreaRef.current.value = '';
        setSelectedPresetRubric('');
        setError(null);
    }, []);

    const clearRubricFile = useCallback(() => {
        setRubricFile(null);
        if (rubricFileInputRef.current) rubricFileInputRef.current.value = '';
        setRubricStatus('The uploaded rubric file was removed.');
        window.requestAnimationFrame(() => rubricFileInputRef.current?.focus());
    }, []);

    const handleSubmit = useCallback(async () => {
        const essayText = essayTextValueRef.current;
        const rubricText = rubricTextValueRef.current;
        let mode = '';
        if (files.length > 0 && essayText.trim()) {
            if (window.confirm("You have both uploaded files and pasted text.\n\nClick OK to evaluate the UPLOADED FILES.\nClick Cancel to evaluate the PASTED TEXT.")) {
                mode = 'upload';
            } else {
                mode = 'paste';
            }
        } else if (files.length > 0) {
            mode = 'upload';
        } else if (essayText.trim()) {
            mode = 'paste';
        } else {
            setError('Please upload at least one essay file or paste your essay text.');
            return;
        }

        if (mode === 'paste' && essayText.length > MAX_PASTED_TEXT_LENGTH) {
            setError('Pasted text is too long. Keep it under 500,000 characters.');
            return;
        }
        if (rubricText.length > MAX_RUBRIC_TEXT_LENGTH) {
            setError('Custom rubric text is too long. Keep it under 100,000 characters.');
            setActiveTab('rubric');
            return;
        }
        if (accentColor && !/^#[0-9a-fA-F]{6}$/.test(accentColor)) {
            const message = 'Enter a complete six-digit accent color, such as #FA8112.';
            setError(message);
            setAccentColorError(message);
            setActiveTab('rubric');
            window.requestAnimationFrame(() => accentColorInputRef.current?.focus());
            return;
        }
        setAccentColorError('');
        const estimatedTransferSize = estimateBatchTransferSize({
            essayFiles: mode === 'upload' ? files : [],
            pastedText: mode === 'paste' ? essayText : '',
            rubricFile,
            rubricText,
        });
        if (estimatedTransferSize > MAX_BATCH_TRANSFER_SIZE) {
            setError('This batch would upload more than 75 MB after repeating the rubric for each essay. Remove files or use a smaller rubric.');
            return;
        }

        setError(null);
        setResults([]);
        setIsLoading(true);
        setProcessingMessage('Verifying your session…');
        window.requestAnimationFrame(() => cancelButtonRef.current?.focus());
        cancelledByUserRef.current = false;
        const runId = evaluationRunIdRef.current + 1;
        const submittingUserId = currentUser?.uid || null;
        evaluationRunIdRef.current = runId;
        const isCurrentRun = () => isMountedRef.current
            && evaluationRunIdRef.current === runId
            && activeUserIdRef.current === submittingUserId;

        let authToken = '';
        let tokenTimedOut = false;
        let tokenTimeoutId = null;
        let cancelTokenWait = null;
        try {
            const tokenWaitGate = new Promise((_, reject) => {
                cancelTokenWait = () => {
                    const cancelError = new Error('Token verification cancelled.');
                    cancelError.name = 'AbortError';
                    reject(cancelError);
                };
                cancelTokenWaitRef.current = cancelTokenWait;
                tokenTimeoutId = window.setTimeout(() => {
                    tokenTimedOut = true;
                    const timeoutError = new Error('Token verification timed out.');
                    timeoutError.name = 'TimeoutError';
                    reject(timeoutError);
                }, AUTH_TOKEN_TIMEOUT_MS);
            });
            authToken = await Promise.race([
                currentUser?.getIdToken(),
                tokenWaitGate,
            ]);
        } catch (authError) {
            if (isCurrentRun()) {
                if (!cancelledByUserRef.current) {
                    console.error('Could not refresh the authentication token', authError);
                    setError(tokenTimedOut
                        ? 'Session verification timed out. Check your connection and retry.'
                        : 'Your session could not be verified. Sign in again and retry.');
                }
                setIsLoading(false);
                setProcessingMessage('');
                window.requestAnimationFrame(() => evaluateButtonRef.current?.focus());
            }
            return;
        } finally {
            if (tokenTimeoutId !== null) window.clearTimeout(tokenTimeoutId);
            if (cancelTokenWaitRef.current === cancelTokenWait) {
                cancelTokenWaitRef.current = null;
            }
        }

        const processItem = async (item, identifier, sourceOrder) => {
            const formData = new FormData();
            if (rubricFile) formData.append('rubric_file', rubricFile);
            else if (rubricText.trim()) formData.append('rubric_text', rubricText.trim());
            formData.append('include_criteria', String(includeCriteria));
            formData.append('include_suggestions', String(includeSuggestions));
            formData.append('include_highlights', String(includeHighlights));
            formData.append('include_mini_lessons', String(includeMiniLessons));
            formData.append('generosity', generosity);
            formData.append('paper_mode', paperMode);
            formData.append('pdf_report_preset', pdfReportPreset);
            if (accentColor) formData.append('accent_color', accentColor);

            if (mode === 'upload') formData.append('essay', item, identifier);
            else formData.append('essay', new Blob([item], { type: 'text/plain' }), identifier);

            const controller = new AbortController();
            activeControllersRef.current.add(controller);
            let timedOut = false;
            const timeoutId = window.setTimeout(() => {
                timedOut = true;
                controller.abort();
            }, EVALUATION_TIMEOUT_MS);

            try {
                const response = await fetch(`${API_BASE_URL}/evaluate/`, {
                    method: 'POST',
                    body: formData,
                    headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
                    signal: controller.signal,
                });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => null);
                    throw new Error(
                        getResponseError(
                            errorData,
                            `Evaluation failed for “${identifier}” with status ${response.status}.`,
                        ),
                    );
                }
                const data = await response.json().catch(() => {
                    throw new Error(
                        `The evaluation service returned invalid data for “${identifier}”.`,
                    );
                });

                let newResults = [];
                if (data.evaluation_status === 'empty') {
                    throw new Error(`No valid essay content was found in “${identifier}”.`);
                } else if (Array.isArray(data.results) && data.results.length > 0) {
                    newResults = data.results.map((r, i) => {
                        const resultError = typeof r.error === 'string'
                            ? r.error
                            : r.error
                                ? 'The server could not evaluate this essay.'
                                : null;
                        return {
                            id: `${data.session_id}-${r.filename || identifier}-${i}`,
                            filename: r.filename || identifier,
                            student_name: r.student_name,
                            score: r.overall_score,
                            maxScore: r.max_score,
                            error: resultError,
                            sessionId: data.session_id,
                            sourceOrder,
                            resultOrder: i,
                        };
                    });
                } else {
                    throw new Error(`The server returned an unexpected response for “${identifier}”.`);
                }
                if (isCurrentRun()) {
                    setResults(prev => sortEvaluationResults([...prev, ...newResults]));
                }
            } catch (err) {
                if ((err.name !== 'AbortError' || timedOut) && isCurrentRun()) {
                    const message = timedOut
                        ? `Evaluation timed out for “${identifier}”. Try a smaller file or retry later.`
                        : err instanceof TypeError
                            ? `Could not reach the evaluation service for “${identifier}”. Check your connection and retry.`
                            : err.message || 'A network or server error interrupted the evaluation.';
                    setResults(prev => sortEvaluationResults([...prev, {
                        id: `error-${identifier}-${Date.now()}`,
                        filename: identifier,
                        student_name: 'Evaluation failed',
                        error: message,
                        sessionId: null,
                        sourceOrder,
                        resultOrder: 0,
                    }]));
                    setError(message);
                }
            } finally {
                window.clearTimeout(timeoutId);
                activeControllersRef.current.delete(controller);
            }
        };

        try {
            const workItems = mode === 'upload'
                ? files.map(file => ({ item: file, identifier: file.name }))
                : [{ item: essayText, identifier: 'pasted-essay.txt' }];
            let nextIndex = 0;
            let completed = 0;

            const runWorker = async () => {
                while (
                    nextIndex < workItems.length
                    && !cancelledByUserRef.current
                    && isCurrentRun()
                ) {
                    const workIndex = nextIndex;
                    nextIndex += 1;
                    const work = workItems[workIndex];
                    setProcessingMessage(`Evaluating ${workIndex + 1} of ${workItems.length}: ${work.identifier}`);
                    await processItem(work.item, work.identifier, workIndex);
                    if (cancelledByUserRef.current || !isCurrentRun()) return;
                    completed += 1;
                    setProcessingMessage(`Completed ${completed} of ${workItems.length}`);
                }
            };

            const workerCount = Math.min(EVALUATION_CONCURRENCY, workItems.length);
            await Promise.allSettled(
                Array.from({ length: workerCount }, () => runWorker()),
            );
        } catch (err) {
            if (isCurrentRun()) {
                setError(err.message || 'The evaluation could not be completed.');
            }
        } finally {
            if (isCurrentRun()) {
                const shouldRestoreFocus = document.activeElement === cancelButtonRef.current;
                setIsLoading(false);
                setProcessingMessage('');
                if (shouldRestoreFocus) {
                    window.requestAnimationFrame(() => evaluateButtonRef.current?.focus());
                }
            }
        }
    }, [files, rubricFile, includeCriteria, includeSuggestions, includeHighlights, includeMiniLessons, generosity, paperMode, pdfReportPreset, accentColor, currentUser]);

    const cancelEvaluation = useCallback(() => {
        evaluationRunIdRef.current += 1;
        cancelledByUserRef.current = true;
        cancelTokenWaitRef.current?.();
        cancelTokenWaitRef.current = null;
        activeControllersRef.current.forEach(controller => controller.abort());
        activeControllersRef.current.clear();
        downloadInProgressRef.current = false;
        setIsLoading(false);
        setIsDownloadingReports(false);
        setProcessingMessage('');
        setError('Evaluation cancelled. Completed results are still available below.');
        window.requestAnimationFrame(() => evaluateButtonRef.current?.focus());
    }, []);

    const downloadReport = useCallback(async (result) => {
        if (!result.sessionId || !result.filename) {
            throw new Error('Cannot download this report because its session data is missing.');
        }
        const downloadUrl = `${API_BASE_URL}/download-report/${result.sessionId}/${encodeURIComponent(result.filename)}`;
        const controller = new AbortController();
        activeControllersRef.current.add(controller);
        let timeoutId = null;
        const timeoutGate = new Promise((_, reject) => {
            timeoutId = window.setTimeout(() => {
                controller.abort();
                const timeoutError = new Error('Report download timed out.');
                timeoutError.name = 'AbortError';
                reject(timeoutError);
            }, REPORT_DOWNLOAD_TIMEOUT_MS);
        });

        try {
            const authToken = await Promise.race([
                currentUser?.getIdToken(),
                timeoutGate,
            ]);
            const response = await Promise.race([
                fetch(downloadUrl, {
                    headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
                    signal: controller.signal,
                }),
                timeoutGate,
            ]);
            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                throw new Error(
                    getResponseError(payload, `Report download failed with status ${response.status}.`),
                );
            }

            const reportBlob = await response.blob();
            if (reportBlob.size === 0) {
                throw new Error('The server returned an empty report.');
            }
            const reportHeader = await reportBlob.slice(0, 1024).text();
            if (!reportHeader.includes('%PDF-')) {
                throw new Error('The server returned an invalid PDF report.');
            }

            const reportUrl = URL.createObjectURL(reportBlob);
            const a = document.createElement('a');
            try {
                a.href = reportUrl;
                a.download = result.filename;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
            } finally {
                a.remove();
                window.setTimeout(
                    () => URL.revokeObjectURL(reportUrl),
                    REPORT_URL_REVOKE_DELAY_MS,
                );
            }
        } finally {
            if (timeoutId !== null) window.clearTimeout(timeoutId);
            activeControllersRef.current.delete(controller);
        }
    }, [currentUser]);

    const restoreDownloadFocus = useCallback((focusTarget) => {
        if (document.activeElement !== downloadStatusRef.current) return;
        window.requestAnimationFrame(() => {
            if (focusTarget?.isConnected && !focusTarget.disabled) {
                focusTarget.focus();
                return;
            }
            evaluateButtonRef.current?.focus();
        });
    }, []);

    const handleDownload = useCallback(async (result, focusTarget) => {
        if (downloadInProgressRef.current) return;
        const downloadUserId = currentUser?.uid || null;
        const isCurrentDownload = () => isMountedRef.current
            && activeUserIdRef.current === downloadUserId;
        downloadInProgressRef.current = true;
        setIsDownloadingReports(true);
        setDownloadStatus('Preparing report download.');
        setError(null);
        window.requestAnimationFrame(() => downloadStatusRef.current?.focus());
        try {
            await downloadReport(result);
            if (isCurrentDownload()) {
                setDownloadStatus('Report download started.');
            }
        } catch (downloadError) {
            console.error('Report download failed', downloadError);
            if (isCurrentDownload()) {
                setDownloadStatus('Report download failed.');
                setError(
                    downloadError.name === 'AbortError'
                        ? 'The report download timed out. Try again.'
                        : downloadError instanceof TypeError
                            ? 'Could not reach the report service. Check your connection and try again.'
                        : downloadError.message || 'The report download could not be completed.',
                );
            }
        } finally {
            downloadInProgressRef.current = false;
            if (isCurrentDownload()) {
                setIsDownloadingReports(false);
                restoreDownloadFocus(focusTarget);
            }
        }
    }, [currentUser?.uid, downloadReport, restoreDownloadFocus]);

    const handleDownloadAll = useCallback(async (focusTarget) => {
        if (downloadInProgressRef.current) return;
        const downloadUserId = currentUser?.uid || null;
        const isCurrentDownload = () => isMountedRef.current
            && activeUserIdRef.current === downloadUserId;
        const validResults = results.filter(r => !r.error && r.sessionId && r.filename);
        if (validResults.length === 0) return;
        downloadInProgressRef.current = true;
        setIsDownloadingReports(true);
        setDownloadStatus(`Preparing ${validResults.length} report downloads.`);
        setError(null);
        window.requestAnimationFrame(() => downloadStatusRef.current?.focus());
        try {
            for (const [index, result] of validResults.entries()) {
                if (isCurrentDownload()) {
                    setDownloadStatus(
                        `Preparing report ${index + 1} of ${validResults.length}.`,
                    );
                }
                await downloadReport(result);
            }
            if (isCurrentDownload()) {
                setDownloadStatus(`${validResults.length} report downloads started.`);
            }
        } catch (downloadError) {
            console.error('Batch report download failed', downloadError);
            if (isCurrentDownload()) {
                setDownloadStatus('Report downloads stopped before the batch completed.');
                setError(
                    downloadError.name === 'AbortError'
                        ? 'The report download timed out. Try again.'
                        : downloadError instanceof TypeError
                            ? 'Could not reach the report service. Check your connection and try again.'
                        : downloadError.message || 'One or more reports could not be downloaded.',
                );
            }
        } finally {
            downloadInProgressRef.current = false;
            if (isCurrentDownload()) {
                setIsDownloadingReports(false);
                restoreDownloadFocus(focusTarget);
            }
        }
    }, [currentUser?.uid, downloadReport, restoreDownloadFocus, results]);

    const registerResultRemoveButton = useCallback((resultId, node) => {
        if (node) resultRemoveButtonRefs.current.set(resultId, node);
        else resultRemoveButtonRefs.current.delete(resultId);
    }, []);

    const handleRemoveResult = useCallback((idToRemove) => {
        const removedIndex = results.findIndex(result => result.id === idToRemove);
        const nextResults = results.filter(result => result.id !== idToRemove);
        setResults(nextResults);
        window.requestAnimationFrame(() => {
            if (nextResults.length === 0) {
                evaluateButtonRef.current?.focus();
                return;
            }
            const nextIndex = Math.min(
                Math.max(removedIndex, 0),
                nextResults.length - 1,
            );
            resultRemoveButtonRefs.current.get(nextResults[nextIndex].id)?.focus();
        });
    }, [results]);

    const dismissError = useCallback(() => {
        setError(null);
        window.requestAnimationFrame(() => pageHeadingRef.current?.focus());
    }, []);

    // ─── Input classes ───
    const inputClass = "w-full p-3 rounded-xl text-sm transition-all duration-200"
        + " bg-[var(--bg-deep)] border border-[var(--border-control)]"
        + " text-[var(--text-primary)] placeholder-[var(--text-tertiary)]"
        + " focus:border-[var(--accent-ink)] focus:shadow-[0_0_0_3px_var(--accent-glow)] focus:outline-none";

    const selectClass = inputClass + " cursor-pointer";

    // ═══════════════════════════════════════════════
    // RENDER
    // ═══════════════════════════════════════════════

    return (
        <div className="min-h-screen relative overflow-x-clip" style={{ background: 'var(--bg-deep)' }}>

            <div className="relative z-10 pt-24 pb-20 px-4 md:px-8 max-w-4xl mx-auto">
                {/* Header */}
                <m.div
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-12"
                >
                    <h1
                        ref={pageHeadingRef}
                        tabIndex={-1}
                        className="text-4xl md:text-5xl font-extrabold tracking-tight text-gradient mb-3"
                    >
                        Evaluate essays
                    </h1>
                    <p className="text-base max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                        AI-powered feedback on your writing. Simple, fast, and effective.
                    </p>
                </m.div>

                <div className="space-y-8">
                    <fieldset
                        disabled={isLoading}
                        aria-busy={isLoading}
                        className="m-0 min-w-0 space-y-8 border-0 p-0 transition-opacity disabled:opacity-70"
                    >
                        <legend className="sr-only">Essay and report settings</legend>
                    {/* Tab Bar */}
                        <m.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2 }}
                            className="flex justify-center"
                        >
                            <div className="glass rounded-2xl p-1.5 flex gap-1 w-full max-w-md" role="tablist" aria-label="Essay setup">
                                <TabButton id="upload" label="Upload" icon={Upload} activeTab={activeTab} onClick={setActiveTab} onKeyDown={handleTabKeyDown} />
                                <TabButton id="paste" label="Paste" icon={Clipboard} activeTab={activeTab} onClick={setActiveTab} onKeyDown={handleTabKeyDown} />
                                <TabButton id="rubric" label="Rubric" icon={Settings} activeTab={activeTab} onClick={setActiveTab} onKeyDown={handleTabKeyDown} />
                            </div>
                        </m.div>

                    {/* Tab Content */}
                    <AnimatePresence mode="sync">
                        {activeTab === 'upload' ? (
                            <m.div
                                id="panel-upload"
                                role="tabpanel"
                                aria-labelledby="tab-upload"
                                key="upload"
                                variants={tabContentVariants}
                                initial="hidden"
                                animate="visible"
                                exit="exit"
                            >
                                <GlassCard>
                                    <FileUploadCard files={files} setFiles={setFiles} onError={setError} />
                                </GlassCard>
                            </m.div>
                        ) : activeTab === 'paste' ? (
                            <m.div
                                id="panel-paste"
                                role="tabpanel"
                                aria-labelledby="tab-paste"
                                key="paste"
                                variants={tabContentVariants}
                                initial="hidden"
                                animate="visible"
                                exit="exit"
                            >
                                <GlassCard>
                                    <label htmlFor={essayPasteAreaId} className="sr-only">Essay text</label>
                                    <textarea
                                        ref={essayTextAreaRef}
                                        id={essayPasteAreaId}
                                        defaultValue={essayTextValueRef.current}
                                        onChange={handleEssayTextChange}
                                        placeholder="Paste your essay text here..."
                                        className={`${inputClass} h-80 resize-none leading-relaxed`}
                                        maxLength={MAX_PASTED_TEXT_LENGTH}
                                    />
                                </GlassCard>
                            </m.div>
                        ) : (
                            <m.div
                                id="panel-rubric"
                                role="tabpanel"
                                aria-labelledby="tab-rubric"
                                key="rubric"
                                variants={tabContentVariants}
                                initial="hidden"
                                animate="visible"
                                exit="exit"
                            >
                                <GlassCard>
                                    <div className="space-y-8">
                                        <div>
                                            <h2
                                                className="text-lg font-semibold pb-3 mb-6 border-b"
                                                style={{ color: 'var(--text-primary)', borderColor: 'var(--border-subtle)' }}
                                            >
                                                Rubric Configuration
                                            </h2>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                <div className="space-y-5">
                                                    <div>
                                                        <label htmlFor={presetRubricId} className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                                                            Preset Rubric
                                                        </label>
                                                        <select
                                                            ref={presetRubricSelectRef}
                                                            id={presetRubricId}
                                                            value={selectedPresetRubric}
                                                            onChange={handlePresetRubricChange}
                                                            className={selectClass}
                                                        >
                                                            <option value="">-- Choose a Preset or Custom Rubric --</option>
                                                            <optgroup label="Standard Presets">
                                                                {presetRubrics.map(rubric => (
                                                                    <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
                                                                ))}
                                                            </optgroup>
                                                            {savedRubrics.length > 0 && (
                                                                <optgroup label="My Custom Rubrics">
                                                                    {savedRubrics.map(rubric => (
                                                                        <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
                                                                    ))}
                                                                </optgroup>
                                                            )}
                                                        </select>
                                                        {/* Show delete button if a custom rubric is selected */}
                                                        {selectedPresetRubric && savedRubrics.find(r => r.id === selectedPresetRubric) && (
                                                            <button
                                                                type="button"
                                                                onClick={() => deleteCustomRubric(selectedPresetRubric)}
                                                                className="mt-2 text-xs underline"
                                                                style={{ color: 'var(--error)' }}
                                                            >
                                                                Delete this custom rubric
                                                            </button>
                                                        )}
                                                        {legacyRubrics.length > 0 && (
                                                            <button
                                                                type="button"
                                                                onClick={importLegacyRubrics}
                                                                className="mt-2 block text-left text-xs underline"
                                                                style={{ color: 'var(--accent-ink)' }}
                                                            >
                                                                Import {legacyRubrics.length} unassigned browser {legacyRubrics.length === 1 ? 'rubric' : 'rubrics'}
                                                            </button>
                                                        )}
                                                        <span className="sr-only" role="status" aria-live="polite">
                                                            {rubricStatus}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <label htmlFor={rubricFileUploadId} className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                                                            Upload Rubric (.txt, .pdf)
                                                        </label>
                                                        <input
                                                            id={rubricFileUploadId}
                                                            ref={rubricFileInputRef}
                                                            type="file"
                                                            onChange={handleRubricFileUpload}
                                                            accept=".txt,.pdf"
                                                            className="w-full text-sm cursor-pointer file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold transition-all"
                                                            style={{
                                                                color: 'var(--text-tertiary)',
                                                            }}
                                                        />
                                                        {rubricFile && (
                                                            <div className="mt-2 flex min-w-0 items-start justify-between gap-3">
                                                                <p
                                                                    className="min-w-0 text-xs [overflow-wrap:anywhere]"
                                                                    style={{ color: 'var(--success)' }}
                                                                >
                                                                    Selected: {rubricFile.name}
                                                                </p>
                                                                <button
                                                                    type="button"
                                                                    onClick={clearRubricFile}
                                                                    className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold"
                                                                    style={{
                                                                        color: 'var(--error)',
                                                                        border: '1px solid var(--border-control)',
                                                                    }}
                                                                >
                                                                    Remove
                                                                </button>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                                <div>
                                                    <div className="flex justify-between items-center mb-2">
                                                        <label htmlFor={rubricPasteAreaId} className="block text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                                                            Custom Rubric Text
                                                        </label>
                                                        {hasRubricText && !selectedPresetRubric && (
                                                            <button
                                                                type="button"
                                                                onClick={saveCustomRubric}
                                                                className="text-xs px-2 py-1 rounded transition-colors"
                                                                style={{ background: 'var(--accent-glow)', color: 'var(--accent-ink)' }}
                                                            >
                                                                Save as Preset
                                                            </button>
                                                        )}
                                                    </div>
                                                    <textarea
                                                        id={rubricPasteAreaId}
                                                        ref={rubricTextAreaRef}
                                                        defaultValue={rubricTextValueRef.current}
                                                        onChange={handleRubricTextChange}
                                                        className={`${inputClass} h-48 resize-none`}
                                                        placeholder="Paste criteria here..."
                                                        maxLength={MAX_RUBRIC_TEXT_LENGTH}
                                                        disabled={!!rubricFile || !!selectedPresetRubric}
                                                    />
                                                </div>
                                            </div>
                                        </div>

                                        {/* Paper Mode + Generosity row */}
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                                            <fieldset>
                                                <legend className="block text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>
                                                    Document Type
                                                </legend>
                                                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                                    {[
                                                        { id: 'organization', label: 'Organization', icon: Package },
                                                        { id: 'general', label: 'General Paper', icon: BookOpen },
                                                    ].map(({ id, label, icon: Icon }) => (
                                                        <label
                                                            key={id}
                                                            className="choice-control relative flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200"
                                                            style={{
                                                                background: paperMode === id ? 'var(--accent-glow)' : 'var(--bg-deep)',
                                                                border: `1px solid ${paperMode === id ? 'var(--border-accent)' : 'var(--border-control)'}`,
                                                                color: paperMode === id ? 'var(--accent-ink)' : 'var(--text-secondary)',
                                                            }}
                                                        >
                                                            <input
                                                                type="radio"
                                                                name="document-type"
                                                                value={id}
                                                                checked={paperMode === id}
                                                                onChange={(event) => setPaperMode(event.target.value)}
                                                                className="sr-only"
                                                            />
                                                            <Icon size={14} aria-hidden="true" />
                                                            {label}
                                                        </label>
                                                    ))}
                                                </div>
                                                <p className="mt-2 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                                                    {paperMode === 'organization'
                                                        ? 'Splits multi-student uploads, detects "Student Name:" headers'
                                                        : 'Treats entire document as one paper, detects author names'
                                                    }
                                                </p>
                                            </fieldset>
                                            <fieldset>
                                                <legend className="block text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>
                                                    PDF Report Style <Palette size={14} className="inline ml-1" style={{ color: 'var(--accent-ink)' }} aria-hidden="true" />
                                                </legend>
                                                <div className="grid grid-cols-2 gap-2">
                                                    {[
                                                        { id: 'classic', label: 'Classic', desc: 'Modern' },
                                                        { id: 'academic', label: 'Academic', desc: 'Formal' },
                                                        { id: 'supportive', label: 'Supportive', desc: 'Friendly' },
                                                        { id: 'minimalist', label: 'Minimalist', desc: 'Clean' },
                                                        { id: 'super_annotated', label: 'Super Report', desc: 'Annotated + Full Text' }
                                                    ].map((preset) => (
                                                        <label
                                                            key={preset.id}
                                                            className={`choice-control relative cursor-pointer rounded-xl border px-3 py-2 text-left transition-all duration-200 ${preset.id === 'super_annotated' ? 'col-span-2' : ''}`}
                                                            style={{
                                                                background: pdfReportPreset === preset.id ? 'var(--accent-glow)' : 'var(--bg-deep)',
                                                                borderColor: pdfReportPreset === preset.id ? 'var(--border-accent)' : 'var(--border-control)',
                                                            }}
                                                        >
                                                            <input
                                                                type="radio"
                                                                name="pdf-report-style"
                                                                value={preset.id}
                                                                checked={pdfReportPreset === preset.id}
                                                                onChange={(event) => setPdfReportPreset(event.target.value)}
                                                                className="sr-only"
                                                            />
                                                            <div className="flex items-center justify-between mb-0.5">
                                                                <span className="font-medium text-sm flex items-center gap-1" style={{ color: pdfReportPreset === preset.id ? 'var(--accent-ink)' : 'var(--text-secondary)' }}>
                                                                    {preset.label}
                                                                    {preset.id === 'super_annotated' && <Sparkles size={10} className="text-yellow-400" />}
                                                                </span>
                                                                {pdfReportPreset === preset.id && <CheckCircle size={12} style={{ color: 'var(--accent-ink)' }} aria-hidden="true" />}
                                                            </div>
                                                            <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>{preset.desc}</div>
                                                        </label>
                                                    ))}
                                                </div>
                                            </fieldset>

                                            {/* Accent Color Picker */}
                                            <fieldset>
                                                <legend className="block text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>
                                                    Report Accent Color
                                                </legend>
                                                <div className="flex flex-wrap gap-2 items-center">
                                                    {[
                                                        { hex: '', label: 'Default' },
                                                        { hex: '#7c3aed', label: 'Purple' },
                                                        { hex: '#2563eb', label: 'Blue' },
                                                        { hex: '#0d9488', label: 'Teal' },
                                                        { hex: '#059669', label: 'Green' },
                                                        { hex: '#dc2626', label: 'Red' },
                                                        { hex: '#ea580c', label: 'Orange' },
                                                        { hex: '#be185d', label: 'Pink' },
                                                    ].map((c) => (
                                                        <label
                                                            key={c.hex || 'default'}
                                                            title={c.label}
                                                            className="choice-control relative flex cursor-pointer items-center justify-center rounded-full transition-all duration-200"
                                                            style={{
                                                                width: 28,
                                                                height: 28,
                                                                background: c.hex || 'linear-gradient(135deg, #7c3aed, #2563eb, #059669)',
                                                                border: accentColor === c.hex
                                                                    ? '2.5px solid var(--text-primary)'
                                                                    : '2px solid var(--border-control)',
                                                                boxShadow: accentColor === c.hex ? '0 0 0 2px var(--accent-glow)' : 'none',
                                                                transform: accentColor === c.hex ? 'scale(1.2)' : 'scale(1)',
                                                            }}
                                                        >
                                                            <input
                                                                type="radio"
                                                                name="report-accent-color"
                                                                value={c.hex}
                                                                checked={accentColor === c.hex}
                                                                onChange={(event) => {
                                                                    setAccentColor(event.target.value);
                                                                    setAccentColorError('');
                                                                }}
                                                                className="sr-only"
                                                                aria-label={`${c.label} report color`}
                                                            />
                                                            {accentColor === c.hex && (
                                                                <CheckCircle size={12} style={{ color: c.hex ? 'white' : 'var(--text-primary)' }} aria-hidden="true" />
                                                            )}
                                                        </label>
                                                    ))}
                                                    <label
                                                        className="choice-control inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-xs"
                                                        style={{
                                                            color: 'var(--text-secondary)',
                                                            border: '1px solid var(--border-control)',
                                                        }}
                                                    >
                                                        <input
                                                            type="radio"
                                                            name="report-accent-color"
                                                            value="custom"
                                                            checked={
                                                                Boolean(accentColor)
                                                                && ![
                                                                    '#7c3aed', '#2563eb', '#0d9488', '#059669',
                                                                    '#dc2626', '#ea580c', '#be185d',
                                                                ].includes(accentColor)
                                                            }
                                                            onChange={() => {
                                                                setAccentColor('#7A3600');
                                                                setAccentColorError('');
                                                            }}
                                                            className="sr-only"
                                                        />
                                                        Custom
                                                    </label>
                                                    <input
                                                        ref={accentColorInputRef}
                                                        id={accentColorId}
                                                        type="text"
                                                        aria-label="Custom report accent hex color"
                                                        aria-invalid={Boolean(accentColorError)}
                                                        aria-describedby={accentColorHelpId}
                                                        placeholder="#hex"
                                                        value={accentColor}
                                                        onChange={(e) => {
                                                            const val = e.target.value;
                                                            if (val === '' || /^#[0-9a-fA-F]{0,6}$/.test(val)) {
                                                                setAccentColor(val);
                                                                if (val === '' || /^#[0-9a-fA-F]{6}$/.test(val)) {
                                                                    setAccentColorError('');
                                                                }
                                                            }
                                                        }}
                                                        className="w-20 px-2 py-1 rounded-lg text-xs text-center"
                                                        maxLength={7}
                                                        style={{
                                                            background: 'var(--bg-deep)',
                                                            border: '1px solid var(--border-control)',
                                                            color: 'var(--text-primary)',
                                                        }}
                                                    />
                                                </div>
                                                <p
                                                    id={accentColorHelpId}
                                                    className="mt-2 text-xs"
                                                    style={{ color: accentColorError ? 'var(--error)' : 'var(--text-tertiary)' }}
                                                >
                                                    {accentColorError || 'Choose a six-digit hex color for PDF report headers and styling.'}
                                                </p>
                                            </fieldset>
                                            <div className="space-y-5">
                                                <div>
                                                    <label htmlFor={generosityId} className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                                                        Grading Approach
                                                    </label>
                                                    <select
                                                        id={generosityId}
                                                        value={generosity}
                                                        onChange={(event) => setGenerosity(event.target.value)}
                                                        className={selectClass}
                                                    >
                                                        <option value="strict">Strict</option>
                                                        <option value="standard">Standard</option>
                                                        <option value="generous">Supportive</option>
                                                    </select>
                                                </div>
                                                <fieldset>
                                                    <legend className="block text-sm font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>
                                                        Include in Report
                                                    </legend>
                                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                        {[
                                                            ['Criteria scores', includeCriteria, setIncludeCriteria],
                                                            ['Suggestions', includeSuggestions, setIncludeSuggestions],
                                                            ['Highlights', includeHighlights, setIncludeHighlights],
                                                            ['Mini lessons', includeMiniLessons, setIncludeMiniLessons],
                                                        ].map(([label, checked, setter]) => (
                                                            <label key={label} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm" style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
                                                                <input
                                                                    type="checkbox"
                                                                    checked={checked}
                                                                    onChange={(event) => setter(event.target.checked)}
                                                                    style={{ accentColor: 'var(--accent)' }}
                                                                />
                                                                {label}
                                                            </label>
                                                        ))}
                                                    </div>
                                                </fieldset>
                                            </div>
                                        </div>
                                    </div>
                                </GlassCard>
                            </m.div>
                        )}
                    </AnimatePresence>
                    </fieldset>

                    {/* Submit Button */}
                    <m.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="flex flex-col items-center justify-center gap-3"
                    >
                        <m.button
                            ref={evaluateButtonRef}
                            type="button"
                            whileHover={{ scale: isLoading || isDownloadingReports ? 1 : 1.02 }}
                            whileTap={{ scale: isLoading || isDownloadingReports ? 1 : 0.98 }}
                            onClick={handleSubmit}
                            disabled={isLoading || isDownloadingReports || (files.length === 0 && !hasEssayText)}
                            className="group w-full max-w-md py-3.5 px-8 rounded-2xl font-semibold text-base transition-all duration-300 flex items-center justify-center gap-3 disabled:opacity-40 disabled:cursor-not-allowed"
                            style={{
                                background: isLoading
                                    ? 'var(--bg-elevated)'
                                    : 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                                color: isLoading ? 'var(--text-tertiary)' : 'var(--dark-text-primary)',
                                boxShadow: isLoading ? 'none' : '0 0 30px -5px rgba(250, 129, 18, 0.3)',
                            }}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 size={18} className="animate-spin" />
                                    <span className="min-w-0 [overflow-wrap:anywhere]">
                                        {processingMessage || 'Processing...'}
                                    </span>
                                </>
                            ) : (
                                <>
                                    <Sparkles size={18} />
                                    Evaluate Essays
                                    <ArrowRight size={16} className="transition-transform duration-300 group-hover:translate-x-1" />
                                </>
                            )}
                        </m.button>
                        {isLoading && (
                            <button
                                ref={cancelButtonRef}
                                type="button"
                                onClick={cancelEvaluation}
                                className="rounded-lg px-4 py-2 text-sm font-semibold"
                                style={{ color: 'var(--error)', border: '1px solid var(--border-medium)' }}
                            >
                                Cancel evaluation
                            </button>
                        )}
                        <span className="sr-only" role="status" aria-live="polite">
                            {processingMessage}
                        </span>
                    </m.div>

                    {/* Error */}
                    <AnimatePresence>
                        {error && (
                            <m.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="max-w-xl mx-auto p-4 rounded-xl text-sm flex items-center gap-3"
                                style={{
                                    background: 'var(--error-bg)',
                                    border: '1px solid rgba(248, 113, 113, 0.15)',
                                    color: 'var(--error)',
                                }}
                                role="alert"
                            >
                                <AlertTriangle size={16} className="shrink-0" aria-hidden="true" />
                                <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{error}</span>
                                <button
                                    type="button"
                                    onClick={dismissError}
                                    className="rounded-md p-1"
                                    aria-label="Dismiss message"
                                >
                                    <X size={15} aria-hidden="true" />
                                </button>
                            </m.div>
                        )}
                    </AnimatePresence>

                    {/* Results */}
                    <span className="sr-only" role="status" aria-live="polite">
                        {results.length > 0
                            ? `${results.length} evaluation ${results.length === 1 ? 'result' : 'results'} available; ${results.filter(result => !result.error).length} completed successfully.`
                            : ''}
                    </span>
                    <span
                        ref={downloadStatusRef}
                        className="sr-only"
                        role="status"
                        aria-live="polite"
                        tabIndex={-1}
                    >
                        {downloadStatus}
                    </span>
                    <AnimatePresence>
                        {results.length > 0 && (
                            <m.div
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="mt-8"
                            >
                                <GlassCard>
                                    <div
                                        className="mb-6 flex flex-col items-start gap-3 border-b pb-4 sm:flex-row sm:items-center sm:justify-between"
                                        style={{ borderColor: 'var(--border-subtle)' }}
                                    >
                                        <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                                            Evaluation Results
                                        </h2>
                                        <span
                                            className="max-w-full rounded-full px-3 py-1 text-sm [overflow-wrap:anywhere]"
                                            style={{
                                                color: 'var(--accent-ink)',
                                                background: 'var(--bg-card)',
                                                border: '1px solid var(--border-subtle)',
                                            }}
                                        >
                                            {isDownloadingReports
                                                ? downloadStatus || 'Preparing download…'
                                                : `${results.filter(r => !r.error).length} completed`}
                                        </span>
                                    </div>
                                    <div className="space-y-3">
                                        <AnimatePresence>
                                            {results.map((result) => (
                                                <ResultItem
                                                    key={result.id}
                                                    result={result}
                                                    onDownload={handleDownload}
                                                    onRemove={handleRemoveResult}
                                                    registerRemoveButton={registerResultRemoveButton}
                                                    actionsDisabled={isLoading || isDownloadingReports}
                                                />
                                            ))}
                                        </AnimatePresence>
                                    </div>
                                    {results.filter(r => !r.error).length > 1 && (
                                        <div className="mt-6 flex justify-center pt-5 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
                                            <m.button
                                                type="button"
                                                whileHover={isLoading || isDownloadingReports
                                                    ? undefined
                                                    : { scale: 1.03 }}
                                                whileTap={isLoading || isDownloadingReports
                                                    ? undefined
                                                    : { scale: 0.97 }}
                                                onClick={(event) => {
                                                    void handleDownloadAll(event.currentTarget);
                                                }}
                                                disabled={isLoading || isDownloadingReports}
                                                className="px-6 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2 glass transition-colors disabled:cursor-wait disabled:opacity-50"
                                                style={{ color: 'var(--text-secondary)' }}
                                            >
                                                {isDownloadingReports
                                                    ? <Loader2 size={14} className="animate-spin" aria-hidden="true" />
                                                    : <Download size={14} aria-hidden="true" />}
                                                {isDownloadingReports ? 'Preparing reports…' : 'Download All Reports'}
                                            </m.button>
                                        </div>
                                    )}
                                </GlassCard>
                            </m.div>
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
