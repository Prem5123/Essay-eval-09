import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView, useScroll, useTransform } from 'framer-motion';
import {
  Upload, FileText, Sparkles, Zap, Shield, BarChart3,
  ArrowRight, CheckCircle, ChevronRight, Gift, Heart
} from 'lucide-react';
import AnimatedBackground from '../components/AnimatedBackground';

// ═══════════════════════════════════════════════
// ANIMATION VARIANTS
// ═══════════════════════════════════════════════

const fadeUp = {
  hidden: { opacity: 0, y: 40 },
  visible: (delay = 0) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.7, delay, ease: [0.25, 0.46, 0.45, 0.94] }
  }),
};

const stagger = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.12, delayChildren: 0.2 },
  },
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: (delay = 0) => ({
    opacity: 1, scale: 1,
    transition: { duration: 0.5, delay, ease: 'easeOut' }
  }),
};

// ═══════════════════════════════════════════════
// TEXT REVEAL — Letters slide up with mask
// ═══════════════════════════════════════════════

const TextReveal = ({ children, className = '', delay = 0 }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  // Split by words
  const words = typeof children === 'string' ? children.split(' ') : [children];

  return (
    <span ref={ref} className={`inline-flex flex-wrap gap-x-[0.3em] ${className}`}>
      {words.map((word, i) => (
        <span key={i} className="text-reveal-line">
          <motion.span
            initial={{ y: '110%' }}
            animate={isInView ? { y: '0%' } : { y: '110%' }}
            transition={{
              duration: 0.6,
              delay: delay + i * 0.04,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            {word}
          </motion.span>
        </span>
      ))}
    </span>
  );
};

// ═══════════════════════════════════════════════
// TYPEWRITER
// ═══════════════════════════════════════════════

const TypewriterText = ({ words, className }) => {
  const [index, setIndex] = useState(0);
  const [text, setText] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const current = words[index];
    const speed = isDeleting ? 40 : 80;

    const timeout = setTimeout(() => {
      if (!isDeleting && text === current) {
        setTimeout(() => setIsDeleting(true), 2000);
      } else if (isDeleting && text === '') {
        setIsDeleting(false);
        setIndex((prev) => (prev + 1) % words.length);
      } else {
        setText(isDeleting ? current.slice(0, text.length - 1) : current.slice(0, text.length + 1));
      }
    }, speed);
    return () => clearTimeout(timeout);
  }, [text, isDeleting, index, words]);

  return (
    <span className={className}>
      {text}
      <span className="animate-blink" style={{ color: 'var(--accent-light)' }}>|</span>
    </span>
  );
};

// ═══════════════════════════════════════════════
// MAGNETIC BUTTON — shifts toward cursor on hover
// ═══════════════════════════════════════════════

const MagneticButton = ({ children, className = '', strength = 0.3, ...props }) => {
  const ref = useRef(null);

  const handleMouseMove = useCallback((e) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    el.style.transform = `translate(${x * strength}px, ${y * strength}px)`;
  }, [strength]);

  const handleMouseLeave = useCallback(() => {
    if (ref.current) {
      ref.current.style.transform = 'translate(0px, 0px)';
    }
  }, []);

  return (
    <div
      ref={ref}
      className={`transition-transform duration-200 ease-out ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      {children}
    </div>
  );
};

// ═══════════════════════════════════════════════
// ANIMATED COUNTER — counts up when scrolled into view
// ═══════════════════════════════════════════════

const AnimatedCounter = ({ target, suffix = '', prefix = '', duration = 2 }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const end = target;
    const step = Math.ceil(end / (duration * 60)); // ~60fps
    const timer = setInterval(() => {
      start += step;
      if (start >= end) {
        setCount(end);
        clearInterval(timer);
      } else {
        setCount(start);
      }
    }, 1000 / 60);
    return () => clearInterval(timer);
  }, [isInView, target, duration]);

  return (
    <span ref={ref} className="tabular-nums">
      {prefix}{count}{suffix}
    </span>
  );
};

// ═══════════════════════════════════════════════
// PARALLAX WRAPPER
// ═══════════════════════════════════════════════

const ParallaxLayer = ({ children, speed = 0.5, className = '' }) => {
  const ref = useRef(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });
  const y = useTransform(scrollYProgress, [0, 1], [speed * -60, speed * 60]);

  return (
    <motion.div ref={ref} style={{ y }} className={className}>
      {children}
    </motion.div>
  );
};

// ═══════════════════════════════════════════════
// TILT CARD — 3D perspective card with shine highlight
// ═══════════════════════════════════════════════

const TiltCard = ({ children, className = '' }) => {
  const ref = useRef(null);

  const handleMouseMove = useCallback((e) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    const rotateX = (y - 0.5) * -8;  // subtle tilt
    const rotateY = (x - 0.5) * 8;
    el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
    // Update shine position
    el.style.setProperty('--shine-x', `${x * 100}%`);
    el.style.setProperty('--shine-y', `${y * 100}%`);
  }, []);

  const handleMouseLeave = useCallback(() => {
    if (ref.current) {
      ref.current.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
    }
  }, []);

  return (
    <div
      ref={ref}
      className={`tilt-card ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <div className="tilt-card-inner relative">
        <div className="tilt-card-shine" />
        {children}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════
// FEATURE CARD — Tilt + Icon Animation
// ═══════════════════════════════════════════════

const iconAnimations = ['icon-animate-bounce', 'icon-animate-pulse', 'icon-animate-spin',
  'icon-animate-bounce', 'icon-animate-pulse', 'icon-animate-spin'];

const FeatureCard = ({ icon: Icon, title, description, delay, index }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <motion.div
      ref={ref}
      custom={delay}
      initial="hidden"
      animate={isInView ? 'visible' : 'hidden'}
      variants={scaleIn}
    >
      <TiltCard
        className="group glass glow-border rounded-2xl p-6 md:p-8 transition-colors duration-500 hover:bg-[var(--bg-elevated)] h-full"
      >
        <div className="relative">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center mb-5 transition-all duration-300 group-hover:scale-110 ${iconAnimations[index] || 'icon-animate-bounce'}`}
            style={{ background: 'var(--accent-glow)', color: 'var(--accent-light)' }}
          >
            <Icon size={22} strokeWidth={1.8} />
          </div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            {title}
          </h3>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            {description}
          </p>
        </div>
      </TiltCard>
    </motion.div>
  );
};

// ═══════════════════════════════════════════════
// STEP CARD with counter
// ═══════════════════════════════════════════════

const StepCard = ({ number, title, description, delay }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });

  return (
    <motion.div
      ref={ref}
      custom={delay}
      initial="hidden"
      animate={isInView ? 'visible' : 'hidden'}
      variants={fadeUp}
      className="relative flex flex-col items-center text-center"
    >
      <div
        className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold mb-5 glow-border"
        style={{ background: 'var(--accent-glow)', color: 'var(--accent-light)' }}
      >
        {number}
      </div>
      <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
        {title}
      </h3>
      <p className="text-sm max-w-xs" style={{ color: 'var(--text-secondary)' }}>
        {description}
      </p>
    </motion.div>
  );
};

// ═══════════════════════════════════════════════
// STATS ROW — Animated Counters
// ═══════════════════════════════════════════════

const StatsRow = () => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-60px' });

  const stats = [
    { target: 10, suffix: '+', label: 'File formats' },
    { target: 0, prefix: '$', suffix: '', label: 'Cost, forever' },
    { target: 30, suffix: 's', label: 'Avg. grading time' },
    { target: 10, suffix: '', label: 'Files per batch' },
  ];

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6 }}
      className="grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-8 max-w-3xl mx-auto"
    >
      {stats.map((stat, i) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 15 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: i * 0.1, duration: 0.5 }}
          className="text-center"
        >
          <div className="text-3xl md:text-4xl font-extrabold text-gradient mb-1">
            <AnimatedCounter
              target={stat.target}
              suffix={stat.suffix}
              prefix={stat.prefix}
              duration={1.5}
            />
          </div>
          <div className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
            {stat.label}
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
};

// ═══════════════════════════════════════════════
// PRICING SECTION — Rotating gradient border
// ═══════════════════════════════════════════════

const PricingSection = () => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-80px' });

  const freeFeatures = [
    'Unlimited essay evaluations',
    'All rubric presets included',
    'PDF report downloads',
    'Batch processing (up to 10 files)',
    'Custom rubric support',
    'Detailed score breakdowns',
    'No credit card required',
    'No usage limits, ever',
  ];

  return (
    <section ref={ref} className="relative py-32 px-4">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial="hidden"
          animate={isInView ? 'visible' : 'hidden'}
          variants={stagger}
          className="text-center mb-16"
        >
          <motion.p
            variants={fadeUp}
            className="text-sm font-semibold uppercase tracking-widest mb-3"
            style={{ color: 'var(--accent)' }}
          >
            Pricing
          </motion.p>
          <motion.h2
            variants={fadeUp}
            className="text-3xl md:text-5xl font-bold mb-4"
            style={{ color: 'var(--text-primary)' }}
          >
            <TextReveal delay={0.1}>100% Free.</TextReveal>{' '}
            <span className="text-gradient"><TextReveal delay={0.3}>No catches.</TextReveal></span>
          </motion.h2>
          <motion.p
            variants={fadeUp}
            className="text-base max-w-xl mx-auto"
            style={{ color: 'var(--text-secondary)' }}
          >
            We believe every educator deserves access to great tools. That's why LitMark is completely free — forever.
          </motion.p>
        </motion.div>

        <ParallaxLayer speed={0.15}>
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.97 }}
            animate={isInView ? { opacity: 1, y: 0, scale: 1 } : {}}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="relative max-w-lg mx-auto"
          >
            {/* Glow behind card */}
            <div
              className="absolute -inset-4 rounded-3xl opacity-40 blur-2xl"
              style={{ background: 'radial-gradient(ellipse at center, var(--accent-glow-strong) 0%, transparent 70%)' }}
            />

            {/* Rotating gradient border card */}
            <div className="relative glass rotating-border rounded-3xl p-8 md:p-10 overflow-hidden">
              {/* Header */}
              <div className="flex justify-between items-start mb-8">
                <div>
                  <div
                    className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold mb-4"
                    style={{ background: 'rgba(52, 211, 153, 0.12)', color: 'var(--success)' }}
                  >
                    <Gift size={12} />
                    Forever Free
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-5xl md:text-6xl font-extrabold text-gradient">$0</span>
                    <span className="text-lg" style={{ color: 'var(--text-tertiary)' }}>/forever</span>
                  </div>
                </div>
                <motion.div
                  animate={{ rotate: [0, 10, -10, 0] }}
                  transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <Heart size={32} className="animate-pulse-glow" style={{ color: 'var(--accent-light)' }} />
                </motion.div>
              </div>

              <p className="text-sm mb-8" style={{ color: 'var(--text-secondary)' }}>
                Every feature. Every tool. No paywalls, no freemium tricks, no hidden limits.
              </p>

              <ul className="space-y-3 mb-8">
                {freeFeatures.map((feature, i) => (
                  <motion.li
                    key={feature}
                    initial={{ opacity: 0, x: -10 }}
                    animate={isInView ? { opacity: 1, x: 0 } : {}}
                    transition={{ delay: 0.4 + i * 0.06 }}
                    className="flex items-center gap-3 text-sm"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    <CheckCircle size={16} style={{ color: 'var(--success)' }} className="flex-shrink-0" />
                    {feature}
                  </motion.li>
                ))}
              </ul>

              <MagneticButton>
                <Link
                  to="/app"
                  className="group flex items-center justify-center gap-2 w-full py-3.5 rounded-xl text-white font-semibold text-base transition-all duration-300"
                  style={{
                    background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                    boxShadow: '0 0 30px -5px rgba(99, 102, 241, 0.4)',
                  }}
                >
                  Start Using for Free
                  <ArrowRight size={18} className="transition-transform duration-300 group-hover:translate-x-1" />
                </Link>
              </MagneticButton>

              {/* Bottom accent line */}
              <div
                className="absolute bottom-0 left-[10%] right-[10%] h-px"
                style={{
                  background: 'linear-gradient(90deg, transparent, var(--accent), transparent)',
                }}
              />
            </div>
          </motion.div>
        </ParallaxLayer>
      </div>
    </section>
  );
};

// ═══════════════════════════════════════════════
// MAIN LANDING PAGE
// ═══════════════════════════════════════════════

const LandingPage = () => {
  const heroRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: heroRef,
    offset: ['start start', 'end start'],
  });
  const heroOpacity = useTransform(scrollYProgress, [0, 1], [1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 1], [1, 0.95]);
  const heroY = useTransform(scrollYProgress, [0, 1], [0, 80]);

  const features = [
    {
      icon: Sparkles,
      title: 'AI-Powered Grading',
      description: 'Advanced AI analyzes essays against your rubric criteria with nuanced understanding of writing quality.',
    },
    {
      icon: Zap,
      title: 'Instant Results',
      description: 'Grade entire batches of essays in seconds. Upload up to 10 files and get detailed feedback immediately.',
    },
    {
      icon: Shield,
      title: 'Consistent & Fair',
      description: 'Eliminates grading bias with standardized evaluation. Every essay is assessed with the same rigorous criteria.',
    },
    {
      icon: BarChart3,
      title: 'Detailed Analytics',
      description: 'Get comprehensive score breakdowns with specific feedback on each rubric dimension.',
    },
    {
      icon: FileText,
      title: 'Multiple Formats',
      description: 'Supports TXT, DOC, DOCX, and PDF files. Paste text directly or upload files — your choice.',
    },
    {
      icon: Upload,
      title: 'Batch Processing',
      description: 'Upload multiple essays at once and download individual or batch evaluation reports as PDFs.',
    },
  ];

  const steps = [
    { number: '01', title: 'Upload Essays', description: 'Drag and drop your essay files or paste text directly into the editor.' },
    { number: '02', title: 'Set Your Rubric', description: 'Choose from presets or customize your own rubric with specific criteria and weights.' },
    { number: '03', title: 'Get Results', description: 'Receive instant AI-generated evaluations with detailed scores and actionable feedback.' },
  ];

  return (
    <div className="min-h-screen overflow-hidden" style={{ background: 'var(--bg-deep)' }}>
      <AnimatedBackground intensity="normal" />

      {/* ═══ HERO ═══ */}
      <motion.section
        ref={heroRef}
        style={{ opacity: heroOpacity, scale: heroScale }}
        className="relative min-h-screen flex items-center justify-center px-4"
      >
        <motion.div style={{ y: heroY }} className="max-w-4xl mx-auto text-center pt-20">
          {/* Badge */}
          <ParallaxLayer speed={-0.2}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass text-xs font-medium mb-8"
              style={{ color: 'var(--accent-light)' }}
            >
              <Sparkles size={12} />
              AI-Powered Essay Evaluation
              <ChevronRight size={12} />
            </motion.div>
          </ParallaxLayer>

          {/* Main Heading — Text Reveal */}
          <ParallaxLayer speed={-0.1}>
            <h1 className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-extrabold tracking-tight leading-[0.95] mb-6">
              <span className="text-gradient">
                <TextReveal delay={0.3}>Grade smarter.</TextReveal>
              </span>
              <br />
              <span style={{ color: 'var(--text-primary)' }}>
                <TextReveal delay={0.5}>Not harder.</TextReveal>
              </span>
            </h1>
          </ParallaxLayer>

          {/* Subtitle with Typewriter */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.7 }}
            className="text-lg md:text-xl max-w-2xl mx-auto mb-10"
            style={{ color: 'var(--text-secondary)' }}
          >
            Professional essay evaluation for{' '}
            <TypewriterText
              words={['teachers', 'professors', 'students', 'institutions']}
              className="font-semibold"
            />
          </motion.p>

          {/* CTA Buttons — Magnetic */}
          <ParallaxLayer speed={0.1}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.9 }}
              className="flex flex-col sm:flex-row items-center justify-center gap-4"
            >
              <MagneticButton strength={0.2}>
                <Link
                  to="/app"
                  className="group inline-flex items-center gap-2 px-8 py-3.5 rounded-full text-white font-semibold text-base transition-all duration-300"
                  style={{
                    background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                    boxShadow: '0 0 30px -5px rgba(99, 102, 241, 0.4)',
                  }}
                >
                  Start Evaluating
                  <ArrowRight size={18} className="transition-transform duration-300 group-hover:translate-x-1" />
                </Link>
              </MagneticButton>
              <MagneticButton strength={0.15}>
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 px-8 py-3.5 rounded-full text-sm font-medium transition-all duration-200 glass"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Sign In
                </Link>
              </MagneticButton>
            </motion.div>
          </ParallaxLayer>

          {/* Trust indicators */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 1.2 }}
            className="mt-16 flex items-center justify-center gap-6 flex-wrap"
          >
            {['Instant Grading', 'Multiple Rubrics', 'PDF Reports', '100% Free'].map((item) => (
              <div key={item} className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-tertiary)' }}>
                <CheckCircle size={14} style={{ color: 'var(--accent)' }} />
                {item}
              </div>
            ))}
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2"
        >
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="w-5 h-8 rounded-full border-2 flex items-start justify-center pt-1.5"
            style={{ borderColor: 'var(--border-medium)' }}
          >
            <div className="w-1 h-1.5 rounded-full" style={{ background: 'var(--accent-light)' }} />
          </motion.div>
        </motion.div>
      </motion.section>

      {/* ═══ STATS ═══ */}
      <section className="relative py-20 px-4">
        <StatsRow />
      </section>

      {/* ═══ FEATURES — Tilt Cards + Icon Animations ═══ */}
      <section className="relative py-32 px-4">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-100px' }}
            variants={stagger}
            className="text-center mb-16"
          >
            <motion.p
              variants={fadeUp}
              className="text-sm font-semibold uppercase tracking-widest mb-3"
              style={{ color: 'var(--accent)' }}
            >
              Features
            </motion.p>
            <motion.h2
              variants={fadeUp}
              className="text-3xl md:text-5xl font-bold mb-4"
              style={{ color: 'var(--text-primary)' }}
            >
              <TextReveal>Everything you need to grade</TextReveal>
              <br />
              <span className="text-gradient"><TextReveal delay={0.2}>with confidence</TextReveal></span>
            </motion.h2>
            <motion.p
              variants={fadeUp}
              className="text-base max-w-xl mx-auto"
              style={{ color: 'var(--text-secondary)' }}
            >
              Built for educators who value precision, speed, and fairness in essay evaluation.
            </motion.p>
          </motion.div>

          <ParallaxLayer speed={0.08}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {features.map((feature, i) => (
                <FeatureCard key={feature.title} {...feature} delay={i * 0.1} index={i} />
              ))}
            </div>
          </ParallaxLayer>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="relative py-32 px-4">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: '-100px' }}
            variants={stagger}
            className="text-center mb-20"
          >
            <motion.p
              variants={fadeUp}
              className="text-sm font-semibold uppercase tracking-widest mb-3"
              style={{ color: 'var(--accent)' }}
            >
              How It Works
            </motion.p>
            <motion.h2
              variants={fadeUp}
              className="text-3xl md:text-5xl font-bold"
              style={{ color: 'var(--text-primary)' }}
            >
              <TextReveal>Three simple steps</TextReveal>
            </motion.h2>
          </motion.div>

          <ParallaxLayer speed={0.1}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8 relative">
              {/* Connecting line */}
              <div
                className="hidden md:block absolute top-7 left-[20%] right-[20%] h-px"
                style={{ background: 'linear-gradient(90deg, transparent, var(--border-medium), var(--border-medium), transparent)' }}
              />
              {steps.map((step, i) => (
                <StepCard key={step.number} {...step} delay={i * 0.15} />
              ))}
            </div>
          </ParallaxLayer>
        </div>
      </section>

      {/* ═══ PRICING ═══ */}
      <PricingSection />

      {/* ═══ CTA ═══ */}
      <section className="relative py-32 px-4">
        <div className="max-w-3xl mx-auto">
          <ParallaxLayer speed={0.12}>
            <motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              variants={fadeUp}
              className="relative glass glow-border rounded-3xl p-10 md:p-16 text-center overflow-hidden"
            >
              <div
                className="absolute inset-0 opacity-30"
                style={{
                  background: 'radial-gradient(ellipse at center, var(--accent-glow) 0%, transparent 70%)',
                }}
              />
              <div className="relative">
                <h2 className="text-3xl md:text-4xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>
                  <TextReveal>Ready to transform your</TextReveal>
                  <br />
                  <span className="text-gradient"><TextReveal delay={0.2}>grading workflow?</TextReveal></span>
                </h2>
                <p className="text-base mb-8 max-w-md mx-auto" style={{ color: 'var(--text-secondary)' }}>
                  Join educators who save hours every week with AI-powered essay evaluation.
                </p>
                <MagneticButton>
                  <Link
                    to="/app"
                    className="group inline-flex items-center gap-2 px-8 py-3.5 rounded-full text-white font-semibold transition-all duration-300"
                    style={{
                      background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                      boxShadow: '0 0 30px -5px rgba(99, 102, 241, 0.4)',
                    }}
                  >
                    Get Started Free
                    <ArrowRight size={18} className="transition-transform duration-300 group-hover:translate-x-1" />
                  </Link>
                </MagneticButton>
              </div>
            </motion.div>
          </ParallaxLayer>
        </div>
      </section>

      {/* ═══ FOOTER ═══ */}
      <footer className="py-12 px-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-gradient">LitMark</span>
          </div>
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            © {new Date().getFullYear()} LitMark. Built for educators, by educators.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;