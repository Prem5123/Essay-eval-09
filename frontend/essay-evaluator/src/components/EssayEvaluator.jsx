import React, { useState, useCallback, useEffect, useId } from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import { Upload, FileText, Loader2, X, Plus, Download, Package, AlertTriangle, CheckCircle, Settings, Clipboard } from 'lucide-react';
import presetRubrics from '../utils/presetRubrics'; // Assuming this path is correct

// Define API base URL using environment variable or default
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// --- Framer Motion Variants ---
// (Keep existing variants, maybe slightly adjust durations/easing if needed)
const cardVariants = {
    hidden: { opacity: 0, y: 30, scale: 0.98 },
    visible: (delay = 0) => ({
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { type: 'spring', stiffness: 100, damping: 20, delay }
        // transition: { duration: 0.6, ease: [0.25, 1, 0.5, 1], delay } // Alternative easing
    }),
    exit: { opacity: 0, y: -10, transition: { duration: 0.2 } }
};

const tabContentVariants = {
    hidden: { opacity: 0, x: -15 },
    visible: { opacity: 1, x: 0, transition: { duration: 0.4, ease: "easeOut" } },
    exit: { opacity: 0, x: 15, transition: { duration: 0.2 } },
};

const fileItemVariants = {
    hidden: { opacity: 0, x: -10, height: 0 },
    visible: { opacity: 1, x: 0, height: 'auto', transition: { duration: 0.3, ease: "easeOut" } },
    exit: { opacity: 0, x: 10, height: 0, transition: { duration: 0.2 } },
};

const listContainerVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.07, // Slightly faster stagger
            delayChildren: 0.1,
        },
    },
};

// --- Reusable Enhanced Components ---

// More dynamic background
const AnimatedBackground = React.memo(() => {
  // Configuration for stardust particles
  const numStars = 50; // Adjust number of stars
  const stars = Array.from({ length: numStars }).map((_, i) => ({
      id: i,
      // Random initial positions (percentage)
      x: `${Math.random() * 100}%`,
      y: `${Math.random() * 100}%`,
      // Random size
      size: Math.random() * 2 + 0.5, // size between 0.5px and 2.5px
      // Random animation duration for variation
      duration: Math.random() * 15 + 15, // duration between 15s and 30s
      // Random delay
      delay: Math.random() * 5,
  }));

  return (
      <div className="absolute inset-0 bg-gradient-to-br from-gray-950 via-black to-gray-950 overflow-hidden -z-10">

          {/* Layer 1: Gradient Blobs (with mix-blend) */}
          <div className="absolute inset-0 opacity-15 mix-blend-soft-light">
              {/* Blob 1 (Blue/Indigo) */}
              <motion.div
                  className="absolute top-[-25%] -left-1/4 w-3/5 h-3/5 md:w-3/5 md:h-3/5 bg-gradient-to-br from-blue-700 via-indigo-800 to-transparent rounded-full filter blur-3xl"
                  animate={{
                      scale: [1, 1.15, 1], // Slightly more scale variation
                      rotate: [0, 10, 0], // Slightly more rotation
                      x: ['-5%', '5%', '-5%'], // Add subtle horizontal movement
                      transition: { duration: 28, repeat: Infinity, repeatType: "mirror", ease: "easeInOut" }
                  }}
              />
              {/* Blob 2 (Purple/Fuchsia) */}
              <motion.div
                  className="absolute bottom-[-25%] -right-1/4 w-3/5 h-3/5 md:w-3/5 md:h-3/5 bg-gradient-to-tl from-purple-700 via-fuchsia-800 to-transparent rounded-full filter blur-3xl"
                  animate={{
                      scale: [1, 1.1, 1],
                      rotate: [0, -8, 0], // Slightly less rotation
                      y: ['-5%', '5%', '-5%'], // Add subtle vertical movement
                      transition: { duration: 32, repeat: Infinity, repeatType: "mirror", ease: "easeInOut", delay: 3 } // Slightly different duration/delay
                  }}
               />
               {/* Blob 3 (Teal/Cyan - New) */}
               <motion.div
                  className="absolute top-[10%] -right-[15%] w-1/2 h-1/2 md:w-2/5 md:h-2/5 bg-gradient-to-tr from-teal-600 via-cyan-700 to-transparent rounded-full filter blur-[60px]" // Slightly less blur?
                  animate={{
                      scale: [1, 1.08, 1],
                      rotate: [15, -5, 15], // Different rotation
                      x: ['0%', '-10%', '0%'], // Different movement
                      y: ['10%', '-5%', '10%'],
                      transition: { duration: 25, repeat: Infinity, repeatType: "mirror", ease: "linear", delay: 1 } // Linear ease for variety
                  }}
               />
          </div>

          {/* Layer 2: Stardust Particles (rendered on top of blobs, low opacity) */}
          <div className="absolute inset-0 opacity-50"> {/* Container for stars, adjust opacity as needed */}
               {stars.map((star) => (
                  <motion.div
                      key={star.id}
                      className="absolute rounded-full bg-white/50" // Faint white color
                      style={{
                          left: star.x,
                          top: star.y,
                          width: `${star.size}px`,
                          height: `${star.size}px`,
                      }}
                      animate={{
                          // Subtle drift animation
                          x: [0, (Math.random() - 0.5) * 80], // Random horizontal drift +/- 40px
                          y: [0, (Math.random() - 0.5) * 80], // Random vertical drift +/- 40px
                          // Fade in and out effect
                          opacity: [0, 0.8, 0], // Fade in, stay visible briefly, fade out
                      }}
                      transition={{
                          duration: star.duration,
                          repeat: Infinity,
                          repeatType: "loop", // Loop the fade/drift
                          ease: "linear",
                          delay: star.delay,
                      }}
                  />
              ))}
          </div>

          {/* Optional Layer 3: Subtle Grid Pattern (static or animated) */}
          {/*
          <div className="absolute inset-0 opacity-[0.03]" style={{
              backgroundImage: 'linear-gradient(rgba(255, 255, 255, 0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.5) 1px, transparent 1px)',
              backgroundSize: '40px 40px', // Adjust grid size
              // Optional animation:
              // animation: 'panGrid 60s linear infinite',
          }}></div>
          // Add @keyframes panGrid { 0% { background-position: 0 0; } 100% { background-position: 40px 40px; } } to your CSS
          */}
      </div>
  );
});

// Enhanced Card with subtle hover/focus effects
const FloatingCard = React.memo(({ children, delay = 0, className = "" }) => (
    <motion.div
        variants={cardVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        custom={delay}
        className={`bg-black/60 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/10 overflow-hidden relative transition-all duration-300 hover:border-white/20 ${className}`}
        // Add a subtle inner glow on hover maybe?
        // whileHover={{ boxShadow: "0 0 15px 5px rgba(79, 70, 229, 0.2)" }} // Example: Indigo glow
    >
         {/* Optional subtle top highlight */}
         {/* <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-blue-500/50 to-transparent opacity-50"></div> */}
        <div className="p-6 md:p-8"> {/* Padding applied inside */}
            {children}
        </div>
    </motion.div>
));

// Heading with slight animation tweak
const AnimatedHeading = React.memo(() => (
    <motion.h1
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: "easeOut", delay: 0.1 }}
        className="text-5xl md:text-6xl font-bold text-center text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-fuchsia-400 tracking-tight"
    >
        LitMark
    </motion.h1>
));

// Enhanced File Upload Card
const FileUploadCard = ({ files, setFiles }) => {
    const [isDragging, setIsDragging] = useState(false);
    const MAX_FILES = 10;
    const inputId = useId(); // Unique ID for label association

    const validateFile = useCallback((file) => {
        // ... (validation logic remains the same)
        if (file.size === 0) {
          alert(`Cannot read an empty file: "${file.name}".`);
          return false;
        }
        const allowedTypes = ['text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/pdf'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|doc|docx|pdf)$/i)) {
            alert(`Unsupported file type: "${file.name}". Please upload TXT, DOC, DOCX, or PDF files.`);
            return false;
        }
        return true;
    }, []);

    const handleFiles = useCallback((newFilesArray) => {
        // ... (file handling logic remains the same)
        const validFiles = newFilesArray.filter(validateFile);
        if (validFiles.length === 0) return;

        setFiles(prevFiles => {
            const allFiles = [...prevFiles, ...validFiles];
            const pdfFiles = allFiles.filter(f => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));

            if (pdfFiles.length > 1) {
                alert('Only one PDF file can be processed at a time. Please upload other file types or only one PDF.');
                const firstPdf = pdfFiles[0];
                const nonPdfs = allFiles.filter(f => f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf'));
                return [...nonPdfs, firstPdf].slice(0, MAX_FILES);
            }

            const combined = [...prevFiles, ...validFiles];
            return combined.slice(0, MAX_FILES);
        });
    }, [setFiles, validateFile]); // Added validateFile dependency

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

    const dragOverHandler = useCallback((e) => { e.preventDefault(); setIsDragging(true); }, []);
    const dragLeaveHandler = useCallback((e) => { e.preventDefault(); setIsDragging(false); }, []);

    return (
        <div className="space-y-6"> {/* Increased spacing */}
            <motion.div
                onDragOver={dragOverHandler}
                onDragLeave={dragLeaveHandler}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 relative overflow-hidden
                    ${isDragging ? 'border-blue-500 bg-blue-900/30 scale-[1.02]' : 'border-gray-600/70 hover:border-gray-500'}
                    ${files.length > 0 ? 'bg-blue-900/10 border-blue-700/50' : ''}
                    ${files.length >= MAX_FILES ? 'opacity-60 pointer-events-none' : ''}`}
                aria-live="polite"
                 whileHover={!isDragging && files.length < MAX_FILES ? { scale: 1.01 } : {}}
            >
                 {/* Subtle background pattern on drag */}
                 <AnimatePresence>
                    {isDragging && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent z-0"
                        />
                    )}
                </AnimatePresence>

                <div className="flex flex-col items-center space-y-5 relative z-10"> {/* Increased spacing */}
                    <motion.div
                        whileHover={files.length < MAX_FILES ? { scale: 1.1, rotate: 10 } : {}}
                        transition={{ type: "spring", stiffness: 300 }}
                        className="p-3 bg-gradient-to-br from-blue-600/20 to-purple-600/20 rounded-full"
                    >
                        <Upload className="w-12 h-12 md:w-16 md:h-16 text-blue-300" />
                    </motion.div>
                    <p className="text-gray-300 text-base"> {/* Slightly larger text */}
                        {files.length >= MAX_FILES
                            ? `Maximum files (${MAX_FILES}) reached`
                            : <>Drag & drop essays or <label htmlFor={inputId} className="text-blue-400 hover:text-blue-300 underline cursor-pointer">click to browse</label> ({files.length}/{MAX_FILES})</>
                        }
                    </p>
                    {/* Hidden actual input, triggered by label above or button below */}
                    <input
                        id={inputId}
                        type="file"
                        onChange={handleInputChange}
                        className="hidden"
                        accept=".txt,.doc,.docx,.pdf"
                        multiple
                        disabled={files.length >= MAX_FILES}
                        aria-label="Add essay files"
                    />
                    {/* Button is an alternative way to open file dialog */}
                     <motion.label
                        htmlFor={inputId} // Link to the hidden input
                        whileHover={{ scale: 1.05, transition: {duration: 0.2} }}
                        whileTap={{ scale: 0.95 }}
                        className={`inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-full cursor-pointer transition-all shadow-md hover:shadow-lg ${files.length >= MAX_FILES ? 'opacity-50 pointer-events-none !shadow-none' : ''}`}
                     >
                        <Plus className="w-5 h-5" /> Add Essays
                     </motion.label>
                </div>
            </motion.div>

            {/* Files List */}
            <AnimatePresence>
                {files.length > 0 && (
                    <motion.div
                        variants={listContainerVariants}
                        initial="hidden"
                        animate="visible"
                        exit="hidden"
                        className="space-y-3 max-h-60 overflow-y-auto pr-2 custom-scrollbar"
                    >
                        <AnimatePresence> {/* AnimatePresence for individual item removal */}
                        {files.map((file, index) => (
                            <motion.div
                                key={file.name + index}
                                variants={fileItemVariants}
                                initial="hidden" // Apply variants directly here
                                animate="visible"
                                exit="exit"
                                layout // Smooth reordering
                                className="flex items-center justify-between p-3 bg-gray-800/70 rounded-lg border border-gray-700/80 hover:border-blue-600/50 transition-colors duration-200"
                            >
                                <div className="flex items-center space-x-3 overflow-hidden"> {/* Increased spacing */}
                                    <FileText className="w-5 h-5 text-blue-400 flex-shrink-0" />
                                    <span className="text-gray-200 text-sm truncate" title={file.name}>{file.name}</span>
                                </div>
                                <motion.button
                                    whileHover={{ scale: 1.15, rotate: 90, backgroundColor: 'rgba(239, 68, 68, 0.2)' }}
                                    whileTap={{ scale: 0.9 }}
                                    onClick={() => removeFile(index)}
                                    className="p-1.5 rounded-full transition-colors flex-shrink-0 text-red-400 hover:text-red-300" // Added base text color
                                    aria-label={`Remove ${file.name}`}
                                    title={`Remove ${file.name}`}
                                >
                                    <X className="w-4 h-4" /> {/* Slightly smaller X */}
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


// Enhanced Result Item
const ResultItem = React.memo(({ result, onDownload, onRemove }) => {
    const studentName = result.student_name || "Unknown Student";
    const score = typeof result.score === 'number' ? result.score.toFixed(1) : 'N/A';
    const maxScore = typeof result.maxScore === 'number' ? result.maxScore : 'N/A'; // Don't fix decimal if not needed

    return (
        <motion.div
            variants={fileItemVariants} // Reusing variant
            layout // Smooth reordering on remove
            className={`flex items-center justify-between p-4 rounded-lg border transition-all duration-300 ${
                result.error
                ? 'bg-red-900/30 border-red-500/40 hover:border-red-500/70'
                : 'bg-gray-800/60 border-gray-700/80 hover:border-blue-600/60 hover:bg-gray-800/80'
            }`}
        >
            <div className="flex items-center space-x-4 overflow-hidden"> {/* Increased spacing */}
                <div className={`flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full border ${
                    result.error
                    ? 'bg-red-800/50 border-red-600/70'
                    : 'bg-blue-900/50 border-blue-700/80'
                }`}>
                    {result.error ? (
                         <AlertTriangle className="w-5 h-5 text-red-300" />
                    ) : (
                         <CheckCircle className="w-5 h-5 text-blue-300" />
                    )}
                </div>
                <div className="overflow-hidden">
                    <p className={`font-semibold text-base truncate ${result.error ? 'text-red-200' : 'text-white'}`} title={studentName}>
                        {studentName}
                    </p>
                    <p className="text-gray-400 text-xs truncate" title={result.filename}>{result.filename}</p>
                    {result.error ? (
                        <p className="text-red-300 text-sm font-medium mt-0.5">Error: {result.error}</p>
                    ) : (
                        <p className={`font-bold text-sm mt-0.5 ${score === 'N/A' ? 'text-gray-500' : 'text-blue-400'}`}>
                           Score: {score} / {maxScore}
                        </p>
                    )}
                </div>
            </div>
            <div className="flex space-x-2 flex-shrink-0 ml-2"> {/* Added ml-2 for spacing */}
                {!result.error && (
                    <motion.button
                        whileHover={{ scale: 1.1, backgroundColor: 'rgba(59, 130, 246, 0.4)' }} // Use rgba for background hover
                        whileTap={{ scale: 0.9 }}
                        onClick={onDownload}
                        className="p-2 bg-blue-600/20 rounded-full transition-colors text-blue-300 hover:text-blue-200"
                        title="Download report"
                        aria-label={`Download report for ${studentName}`}
                    >
                        <Download className="w-5 h-5" />
                    </motion.button>
                )}
                <motion.button
                    whileHover={{ scale: 1.1, backgroundColor: 'rgba(239, 68, 68, 0.3)' }} // Use rgba for background hover
                    whileTap={{ scale: 0.9 }}
                    onClick={onRemove}
                    className="p-2 bg-red-500/20 rounded-full transition-colors text-red-300 hover:text-red-200"
                    title="Remove result"
                    aria-label={`Remove result for ${studentName}`}
                >
                    <X className="w-5 h-5" />
                </motion.button>
            </div>
        </motion.div>
    );
});


// --- Main Component ---

const EssayEvaluator = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [files, setFiles] = useState([]);
    const [essayText, setEssayText] = useState('');
    const [results, setResults] = useState([]);
    const [error, setError] = useState(null);
    const [activeTab, setActiveTab] = useState('upload'); // 'upload', 'paste', 'rubric'
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

    // Unique IDs for form elements
    const essayPasteAreaId = useId();
    const presetRubricId = useId();
    const rubricFileUploadId = useId();
    const rubricPasteAreaId = useId();
    const generosityId = useId();

    // Clear error after a delay
    useEffect(() => {
        if (error) {
            const timer = setTimeout(() => setError(null), 6000); // Slightly longer timeout
            return () => clearTimeout(timer);
        }
    }, [error]);

    // --- Rubric Handling (Callbacks remain largely the same) ---
     const handlePresetRubricChange = useCallback((e) => {
        const selectedId = e.target.value;
        setSelectedPresetRubric(selectedId);
        const preset = presetRubrics.find(r => r.id === selectedId);
        if (preset) {
            setRubricText(preset.content);
            setRubricFile(null); // Clear file if preset is chosen
        } else {
            if (!rubricFile) { // Only clear text if no file is selected
               setRubricText('');
            }
        }
    }, [rubricFile]); // Added rubricFile dependency

    const handleRubricTextChange = useCallback((e) => {
        setRubricText(e.target.value);
        // Only clear preset/file if user actually types something
        if (e.target.value.trim() !== '') {
             setSelectedPresetRubric('');
             setRubricFile(null);
             // Clear file input visually if needed
             const fileInput = document.getElementById(rubricFileUploadId);
             if(fileInput) fileInput.value = '';
        }
    }, [rubricFileUploadId]); // Added ID dependency

    const handleRubricFileUpload = useCallback((e) => {
        const file = e.target.files[0];
        if (!file) return;

        if (file.size === 0) {
            setError('Cannot use an empty rubric file.');
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
        setRubricText('');
        setSelectedPresetRubric('');
        setError(null);
    }, []);


    // --- Evaluation Logic (Remains the same) ---
     const handleSubmit = useCallback(async () => {
        if (activeTab === 'upload' && files.length === 0) {
            setError('Please upload at least one essay file.'); return;
        }
        if (activeTab === 'paste' && !essayText.trim()) {
            setError('Please paste your essay text.'); return;
        }

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

             if (activeTab === 'upload') {
                 formData.append('essay', item, identifier);
             } else {
                 formData.append('essay', new Blob([item], { type: 'text/plain' }), identifier);
             }

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
                         id: `${data.session_id}-${r.filename || i}-${Math.random()}`, // More robust unique ID
                         filename: r.filename,
                         student_name: r.student_name,
                         score: r.overall_score,
                         maxScore: r.max_score,
                         error: r.error,
                         sessionId: data.session_id
                     }));
                 } else {
                     console.warn("Unexpected response format from /evaluate/", data);
                     setError(`Received an unexpected response format for "${identifier}".`);
                 }
                 setResults(prev => [...prev, ...newResults]);

             } catch (err) {
                 console.error("Evaluation error:", err);
                 setResults(prev => [...prev, {
                     id: `error-${identifier}-${Date.now()}`,
                     filename: identifier,
                     student_name: "Evaluation Failed",
                     error: err.message || 'Network error or server issue.',
                     sessionId: sessionId // Use existing session ID if available
                 }]);
                 setError(err.message || `Failed to process "${identifier}".`);
             }
        };

        try {
            if (activeTab === 'upload') {
                 const pdfFiles = files.filter(f => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'));
                 if (pdfFiles.length > 1) {
                     throw new Error("Processing stopped: Only one PDF file can be evaluated at a time.");
                 }
                 if (pdfFiles.length === 1) {
                     await processItem(pdfFiles[0], pdfFiles[0].name);
                 } else if (files.length > 0) {
                     await processItem(files[0], files[0].name);
                     if(files.length > 1) {
                          alert("Multiple non-PDF files were selected, but only the first file will be processed by the backend for potential splitting. For individual reports per file, please upload them one by one (or use the paste option).");
                     }
                 }
            } else {
                 await processItem(essayText, 'pasted-essay.txt');
                 // Optionally clear pasted text: setEssayText('');
            }
        } catch (err) {
             setError(err.message);
        } finally {
             setIsLoading(false);
             setProcessingMessage('');
        }
     }, [activeTab, files, essayText, rubricFile, rubricText, includeCriteria, includeSuggestions, includeHighlights, includeMiniLessons, generosity, sessionId]); // Removed sessionId from deps as it's set within


    // --- Download Logic (Remains the same) ---
     const handleDownload = useCallback(async (result) => {
         if (!result.sessionId || !result.filename) {
             setError("Cannot download report: Missing session ID or filename.");
             return;
         }
         const downloadUrl = `${API_BASE_URL}/download-report/${result.sessionId}/${encodeURIComponent(result.filename)}`;
         const tempLoadingId = `downloading-${result.id}`; // ID for temporary state if needed
         setIsLoading(true); // Or a dedicated download loading state
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
             // Sanitize filename slightly for download attribute
             a.download = result.filename.replace(/[^a-z0-9._-\s]/gi, '_').replace(/_{2,}/g, '_');
             document.body.appendChild(a);
             a.click();
             document.body.removeChild(a);
             window.URL.revokeObjectURL(url);
         } catch (err) {
             setError(err.message || 'Download error');
         } finally {
             setIsLoading(false); // Reset global loading or specific download state
             setProcessingMessage('');
         }
     }, []); // Removed API_BASE_URL from deps as it's constant within render

    const handleDownloadAll = useCallback(() => {
        const validResults = results.filter(r => !r.error && r.sessionId && r.filename);
        if (validResults.length === 0) return;
        // Basic sequential download - could be improved with Promise.all for parallel requests,
        // but might hit browser limits or look less smooth without progress feedback.
        validResults.forEach((result, index) => {
             // Optional: Add a small delay between downloads if needed
             setTimeout(() => handleDownload(result), index * 200);
        });
    }, [results, handleDownload]);

    const handleRemoveResult = useCallback((idToRemove) => {
        setResults(prev => prev.filter(r => r.id !== idToRemove));
    }, []);


    // --- JSX ---
    return (
        <div className="min-h-screen relative overflow-hidden pt-20 pb-16 bg-gray-950 text-white isolate"> {/* Use isolate */}
            <AnimatedBackground /> {/* Now behind content */}

            <div className="relative z-10 p-4 md:p-8">
                <div className="mb-10 md:mb-14"> {/* Increased margin */}
                    <AnimatedHeading />
                    <motion.p
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3, duration: 0.5 }}
                        className="text-center text-gray-300/90 text-lg md:text-xl mt-4 max-w-2xl mx-auto leading-relaxed"
                    >
                        Get AI-powered feedback on your writing. Upload essays, paste text, and configure your rubric.
                    </motion.p>
                </div>

                <div className="max-w-4xl mx-auto space-y-10"> {/* Increased spacing */}
                    {/* Tabs with Animated Indicator */}
                    <div className="flex justify-center mb-8 relative">
                         <LayoutGroup id="tabs"> {/* Group for layout animation */}
                            <div className="flex space-x-2 bg-black/30 backdrop-blur-sm border border-white/10 rounded-full p-1.5">
                                {[{id: 'upload', label: 'Upload Essays', icon: Upload},
                                {id: 'paste', label: 'Paste Text', icon: Clipboard},
                                {id: 'rubric', label: 'Rubric & Options', icon: Settings}].map((tab) => (
                                    <motion.button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`relative px-4 py-2 md:px-5 md:py-2.5 rounded-full text-sm md:text-base font-medium transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 flex items-center gap-2 ${
                                            activeTab === tab.id ? 'text-white' : 'text-gray-400 hover:text-gray-200'
                                        }`}
                                        whileHover={{ scale: activeTab === tab.id ? 1 : 1.03 }}
                                        whileTap={{ scale: 0.97 }}
                                        aria-current={activeTab === tab.id ? 'page' : undefined}
                                    >
                                        <tab.icon className={`w-4 h-4 transition-colors ${activeTab === tab.id ? 'text-blue-300' : 'text-gray-500'}`} />
                                        {tab.label}
                                        {activeTab === tab.id && (
                                            <motion.div
                                                className="absolute inset-0 bg-gradient-to-r from-blue-600/70 to-purple-600/70 rounded-full -z-10"
                                                layoutId="active-tab-indicator" // Match layoutId
                                                transition={{ type: 'spring', stiffness: 200, damping: 25 }}
                                            />
                                        )}
                                    </motion.button>
                                ))}
                            </div>
                         </LayoutGroup>
                    </div>

                    {/* Tab Content */}
                    <AnimatePresence mode="wait">
                        {activeTab === 'upload' ? (
                            <motion.div key="upload" variants={tabContentVariants} initial="hidden" animate="visible" exit="exit">
                                <FloatingCard delay={0.1}><FileUploadCard files={files} setFiles={setFiles} /></FloatingCard>
                            </motion.div>
                        ) : activeTab === 'paste' ? (
                            <motion.div key="paste" variants={tabContentVariants} initial="hidden" animate="visible" exit="exit">
                                <FloatingCard delay={0.1}>
                                    <label htmlFor={essayPasteAreaId} className="sr-only">Paste Essay Text</label>
                                    <motion.textarea
                                        id={essayPasteAreaId}
                                        value={essayText}
                                        onChange={(e) => setEssayText(e.target.value)}
                                        placeholder="Paste your essay text here..."
                                        className="w-full h-60 md:h-72 p-4 rounded-xl bg-gray-900/80 border border-gray-700/80 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/50 focus:outline-none text-gray-200 placeholder-gray-500 transition-colors duration-200 text-sm leading-relaxed custom-scrollbar resize-none" // Added resize-none
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.2 }}
                                    />
                                </FloatingCard>
                            </motion.div>
                        ) : ( // Rubric Tab
                            <motion.div key="rubric" variants={tabContentVariants} initial="hidden" animate="visible" exit="exit">
                                <FloatingCard delay={0.1}>
                                    <div className="space-y-8"> {/* Increased spacing */}
                                        <div>
                                            <h3 className="text-xl font-semibold text-blue-300 border-b border-blue-800/50 pb-3 mb-5 flex items-center gap-2">
                                                 <Settings className="w-5 h-5"/> Configure Rubric & Feedback
                                             </h3>
                                             {/* Rubric Selection */}
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6"> {/* Grid layout */}
                                                <div className="space-y-4">
                                                     <div>
                                                          <label htmlFor={presetRubricId} className="block text-sm font-medium text-gray-300 mb-1.5">Select Preset Rubric</label>
                                                          <select
                                                              id={presetRubricId}
                                                              value={selectedPresetRubric}
                                                              onChange={handlePresetRubricChange}
                                                              className="w-full p-2.5 rounded-lg bg-gray-800/80 border border-gray-600/70 text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 focus:outline-none transition-colors text-sm appearance-none custom-select" // Added appearance-none and custom class
                                                          >
                                                              <option value="">-- Use Custom or Default --</option>
                                                              {presetRubrics.map(rubric => (
                                                                  <option key={rubric.id} value={rubric.id}>{rubric.name}</option>
                                                              ))}
                                                          </select>
                                                     </div>
                                                     <div>
                                                          <label htmlFor={rubricFileUploadId} className="block text-sm font-medium text-gray-300 mb-1.5">Upload Rubric File <span className="text-gray-500">(.txt, .pdf)</span></label>
                                                          <input
                                                              id={rubricFileUploadId}
                                                              type="file"
                                                              onChange={handleRubricFileUpload}
                                                              accept=".txt,.pdf"
                                                              className="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-600/20 file:text-blue-300 hover:file:bg-blue-600/40 cursor-pointer file:transition-colors"
                                                          />
                                                          {rubricFile && <p className="mt-2 text-xs text-green-400">Selected File: {rubricFile.name}</p>}
                                                     </div>
                                                 </div>
                                                 <div>
                                                      <label htmlFor={rubricPasteAreaId} className="block text-sm font-medium text-gray-300 mb-1.5">Or Paste Custom Rubric</label>
                                                      <textarea
                                                          id={rubricPasteAreaId}
                                                          value={rubricText}
                                                          onChange={handleRubricTextChange}
                                                          className="w-full h-48 p-3 rounded-lg bg-gray-900/70 border border-gray-700/80 text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 focus:outline-none transition-colors text-sm leading-relaxed custom-scrollbar resize-none" // Added resize-none
                                                          placeholder="Paste your custom rubric here..."
                                                          disabled={!!rubricFile || !!selectedPresetRubric} // Disable if file or preset is chosen
                                                      />
                                                      {(rubricFile || selectedPresetRubric) && <p className="mt-1 text-xs text-gray-500">Using {rubricFile ? 'uploaded file' : 'preset rubric'}. Clear selection to paste.</p>}
                                                 </div>
                                             </div>
                                         </div>

                                        {/* Feedback Options */}
                                        <div className="pt-6 border-t border-blue-800/50">
                                            <h4 className="text-lg font-semibold text-gray-200 mb-4">Feedback Options</h4>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
                                                {[
                                                    { state: includeCriteria, setState: setIncludeCriteria, label: 'Criteria Feedback' },
                                                    { state: includeSuggestions, setState: setIncludeSuggestions, label: 'Overall Suggestions' },
                                                    { state: includeHighlights, setState: setIncludeHighlights, label: 'Highlighted Passages' },
                                                    { state: includeMiniLessons, setState: setIncludeMiniLessons, label: 'Mini Lessons' },
                                                ].map(option => (
                                                    <label key={option.label} className="flex items-center space-x-3 cursor-pointer group">
                                                        <input
                                                            type="checkbox"
                                                            checked={option.state}
                                                            onChange={(e) => option.setState(e.target.checked)}
                                                            className="form-checkbox h-4 w-4 rounded text-blue-500 bg-gray-700 border-gray-600 focus:ring-blue-600/50 focus:ring-offset-gray-800 focus:outline-none transition duration-150 ease-in-out cursor-pointer"
                                                        />
                                                        <span className="text-gray-300 group-hover:text-white text-sm transition-colors">{option.label}</span>
                                                    </label>
                                                ))}

                                                {/* Generosity Dropdown - spanning both columns on small screens or as last item */}
                                                <div className="sm:col-span-2 flex items-center space-x-3 pt-2">
                                                    <label htmlFor={generosityId} className="block text-sm font-medium text-gray-300 flex-shrink-0">Evaluation Generosity:</label>
                                                    <select
                                                        id={generosityId}
                                                        value={generosity}
                                                        onChange={(e) => setGenerosity(e.target.value)}
                                                        className="flex-grow p-2 rounded-lg bg-gray-800/80 border border-gray-600/70 text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 focus:outline-none transition-colors text-sm appearance-none custom-select" // Added appearance-none and custom class
                                                    >
                                                        <option value="strict">Strict</option>
                                                        <option value="standard">Standard</option>
                                                        <option value="generous">Generous</option>
                                                    </select>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </FloatingCard>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Submit Button */}
                    <motion.div
                        className="flex justify-center mt-10" // Increased margin
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3, duration: 0.5 }} // Sync with heading paragraph
                    >
                        <motion.button
                            onClick={handleSubmit}
                            disabled={isLoading || (activeTab === 'upload' && !files.length) || (activeTab === 'paste' && !essayText.trim())}
                            className={`w-full max-w-lg py-3.5 px-8 rounded-full text-lg font-semibold transition-all duration-300 flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 ${
                                isLoading
                                ? 'bg-gray-600 text-gray-400 shadow-inner'
                                : 'bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:from-blue-500 hover:to-purple-500 focus-visible:ring-blue-500'
                            }`}
                            whileHover={!isLoading ? { scale: 1.03, y: -2, transition:{ duration: 0.2 } } : {}}
                            whileTap={!isLoading ? { scale: 0.98 } : {}}
                            aria-live="assertive" // Announce loading state changes
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    <span>{processingMessage || 'Processing...'}</span>
                                </>
                            ) : (
                                'Evaluate Essays'
                            )}
                        </motion.button>
                    </motion.div>

                    {/* Error Display */}
                    <AnimatePresence>
                        {error && (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -5, transition: { duration: 0.2 } }}
                                className="max-w-xl mx-auto mt-6 p-4 bg-red-900/40 border border-red-500/60 rounded-lg text-red-200 text-center text-sm flex items-center justify-center gap-2 shadow-md"
                                role="alert"
                            >
                                 <AlertTriangle className="w-4 h-4 flex-shrink-0"/>
                                {error}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Results Display */}
                    <AnimatePresence>
                        {results.length > 0 && (
                            <motion.div
                                initial={{ opacity: 0, scale: 0.98, y: 20 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95 }}
                                transition={{ delay: 0.1, duration: 0.4 }} // Smooth appearance
                                className="mt-12" // Increased margin
                            >
                                <FloatingCard className="!p-0"> {/* Remove padding from card, apply inside */}
                                    <div className="p-6 md:p-8">
                                        <h2 className="text-2xl font-bold text-center text-blue-300 mb-6">Evaluation Results</h2>
                                        <motion.div
                                            variants={listContainerVariants}
                                            initial="hidden"
                                            animate="visible"
                                            className="space-y-3 max-h-[65vh] overflow-y-auto pr-3 custom-scrollbar" // Increased max-height slightly
                                        >
                                            <AnimatePresence>
                                                {results.map((result) => (
                                                    <ResultItem
                                                        key={result.id} // Use the unique ID generated
                                                        result={result}
                                                        onDownload={() => handleDownload(result)}
                                                        onRemove={() => handleRemoveResult(result.id)}
                                                    />
                                                ))}
                                            </AnimatePresence>
                                        </motion.div>
                                    </div>
                                    {/* Download All Button - Improved styling */}
                                    {results.filter(r => !r.error).length > 1 && (
                                        <div className="mt-4 px-6 pb-6 pt-4 border-t border-white/10 bg-black/20 flex justify-center">
                                            <motion.button
                                                onClick={handleDownloadAll}
                                                className="flex items-center gap-2 px-6 py-2.5 bg-blue-600/80 hover:bg-blue-600 text-white rounded-full text-sm font-medium transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed shadow-md hover:shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
                                                disabled={isLoading}
                                                whileHover={{ scale: 1.05, transition: { duration: 0.2 } }}
                                                whileTap={{ scale: 0.95 }}
                                            >
                                                {isLoading && processingMessage.startsWith("Downloading") ? <Loader2 className="w-4 h-4 animate-spin" /> : <Package className="w-4 h-4" />}
                                                Download All ({results.filter(r => !r.error).length})
                                            </motion.button>
                                        </div>
                                    )}
                                </FloatingCard>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Simple Footer */}
            <footer className="relative z-10 text-center py-6 mt-12"> {/* Increased margin */}
                <p className="text-xs text-gray-500/80">&copy; {new Date().getFullYear()} LitMark. AI Evaluation Tool.</p>
            </footer>
        </div>
    );
};

export default EssayEvaluator;

// --- Add CSS for Custom Scrollbar & Select ---
/* In your global CSS (e.g., index.css or App.css):

.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(59, 130, 246, 0.5); // Blue-500 with alpha
  border-radius: 10px;
  border: 2px solid transparent;
  background-clip: content-box;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(59, 130, 246, 0.7);
}
.custom-scrollbar {
  scrollbar-width: thin; // For Firefox
  scrollbar-color: rgba(59, 130, 246, 0.5) rgba(255, 255, 255, 0.05); // For Firefox
}

// Style the select dropdown arrow
.custom-select {
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e"); // Gray-400 arrow
  background-position: right 0.75rem center;
  background-repeat: no-repeat;
  background-size: 1.25em 1.25em;
  padding-right: 2.5rem; // Make space for the arrow
}

// Style checkboxes for better visual consistency (using Tailwind plugin is better, but this works)
// Requires @tailwindcss/forms plugin usually, or manual styling:
input[type='checkbox']:checked {
  background-color: #3b82f6; // blue-500
  border-color: #3b82f6; // blue-500
}
input[type='checkbox']:focus {
   --tw-ring-color: rgba(59, 130, 246, 0.5); // blue-500 alpha for ring
   --tw-ring-offset-color: #1f2937; // gray-800 offset
}

*/