import React, { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import AOS from 'aos';
import 'aos/dist/aos.css';

const LandingPage = () => {
  const { currentUser, signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    AOS.init({
      duration: 800,
      once: false,
      mirror: true,
      easing: 'ease-out-cubic',
    });
  }, []);

  const handleGoogleSignIn = async () => {
    try {
      await signInWithGoogle();
      navigate('/app');
    } catch (error) {
      console.error("Google sign-in error:", error);
    }
  };

  const features = [
    {
      title: "AI-Powered Evaluation",
      description: "Get detailed feedback on your essays using advanced AI technology.",
      icon: "🤖",
      color: "bg-gradient-to-r from-violet-500 to-indigo-500",
      hoverColor: "hover:from-violet-600 hover:to-indigo-600",
    },
    {
      title: "Custom Rubrics",
      description: "Create and save your own evaluation rubrics or use our pre-defined templates.",
      icon: "📝",
      color: "bg-gradient-to-r from-sky-500 to-cyan-500",
      hoverColor: "hover:from-sky-600 hover:to-cyan-600",
    },
    {
      title: "Detailed PDF Reports",
      description: "Receive comprehensive PDF reports with scores and improvement suggestions.",
      icon: "📊",
      color: "bg-gradient-to-r from-emerald-500 to-teal-500",
      hoverColor: "hover:from-emerald-600 hover:to-teal-600",
    },
    {
      title: "Multiple File Formats",
      description: "Upload essays in PDF, TXT, or DOCX formats for evaluation.",
      icon: "📄",
      color: "bg-gradient-to-r from-amber-500 to-orange-500",
      hoverColor: "hover:from-amber-600 hover:to-orange-600",
    },
  ];

  const testimonials = [
    {
      name: "Sarah Johnson",
      role: "English Teacher",
      content: "This tool has revolutionized how I grade essays. It saves me hours of work while providing consistent feedback to my students.",
      avatar: "https://randomuser.me/api/portraits/women/32.jpg",
    },
    {
      name: "Michael Chen",
      role: "University Student",
      content: "I've improved my writing significantly since using this tool. The detailed feedback helps me understand my weaknesses and work on them.",
      avatar: "https://randomuser.me/api/portraits/men/46.jpg",
    },
    {
      name: "Dr. Emily Rodriguez",
      role: "Professor of Literature",
      content: "The customizable rubrics are perfect for different types of assignments. My students appreciate the detailed feedback they receive.",
      avatar: "https://randomuser.me/api/portraits/women/65.jpg",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white overflow-hidden">
      {/* Animated background - simplified and more subtle */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-violet-600 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob"></div>
        <div className="absolute top-40 -left-20 w-80 h-80 bg-sky-600 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-40 left-20 w-80 h-80 bg-emerald-600 rounded-full mix-blend-multiply filter blur-3xl opacity-10 animate-blob animation-delay-4000"></div>
      </div>

      {/* Hero Section - more minimal and centered */}
      <header className="relative z-10 pt-28 pb-16 md:pt-36 md:pb-24">
        <div className="container mx-auto px-4 text-center">
          <div 
            className="inline-block bg-slate-900/60 backdrop-blur-md px-10 py-8 rounded-2xl mb-8 shadow-xl border border-slate-800/50"
            data-aos="zoom-in"
          >
            <h1 className="text-4xl md:text-6xl font-bold leading-tight">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                LitMark
              </span>
            </h1>
            <p className="text-xl md:text-3xl font-medium mt-4 bg-clip-text text-transparent bg-gradient-to-r from-sky-300 to-emerald-300 drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]">
              AI based essay evaluator
            </p>
          </div>
          <p 
            className="text-lg md:text-xl max-w-xl mx-auto mb-12 text-slate-300 leading-relaxed"
            data-aos="fade-up"
            data-aos-delay="200"
          >
            Reduce your time and maintain the quality of feedback with our advanced AI evaluation system.
          </p>
          <div 
            className="flex flex-col sm:flex-row justify-center gap-6"
            data-aos="fade-up"
            data-aos-delay="400"
          >
            {currentUser ? (
              <Link 
                to="/app" 
                className="px-8 py-3 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-lg hover:shadow-lg hover:shadow-violet-500/30 transition-all duration-300 transform hover:-translate-y-1 hover:from-violet-700 hover:to-indigo-700 shadow-md"
              >
                <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]">Go to Dashboard</span>
              </Link>
            ) : (
              <>
                <Link 
                  to="/login" 
                  className="px-8 py-3 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-lg hover:shadow-lg hover:shadow-violet-500/30 transition-all duration-300 transform hover:-translate-y-1 hover:from-violet-700 hover:to-indigo-700 shadow-md"
                >
                  <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]">Get Started</span>
                </Link>
                <Link 
                  to="/signup" 
                  className="px-8 py-3 rounded-lg bg-transparent border-2 border-violet-500 text-white font-bold text-lg hover:bg-violet-500/20 transition-all duration-300 transform hover:-translate-y-1 shadow-md"
                >
                  <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]">Sign Up</span>
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Features Section - simplified with more whitespace */}
      <section className="relative z-10 py-20 md:py-28 bg-slate-900/30 backdrop-blur-sm">
        <div className="container mx-auto px-4">
          <h2 
            className="text-2xl md:text-3xl font-bold text-center mb-20 bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]"
            data-aos="fade-up"
          >
            Key Features
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10">
            {features.map((feature, index) => (
              <div 
                key={index}
                className="bg-slate-800/30 backdrop-blur-sm rounded-xl p-8 border border-slate-700/50 hover:border-violet-500/30 transition-all duration-300 hover:shadow-lg hover:shadow-violet-500/5 group hover:translate-y-[-8px]"
                data-aos="fade-up"
                data-aos-delay={100 * index}
              >
                <div className={`${feature.color} ${feature.hoverColor} w-16 h-16 rounded-full flex items-center justify-center text-2xl mb-6 group-hover:scale-110 transition-all duration-300`}>
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold mb-4 text-white group-hover:text-violet-400 transition-colors duration-300">{feature.title}</h3>
                <p className="text-slate-400 group-hover:text-slate-300 transition-colors duration-300">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section - simplified and more focused */}
      <section className="relative z-10 py-20 md:py-28">
        <div 
          className="container mx-auto px-4 text-center"
          data-aos="zoom-in"
        >
          <div className="max-w-2xl mx-auto bg-gradient-to-r from-slate-800/60 to-slate-900/60 backdrop-blur-md p-10 rounded-2xl border border-slate-700/50 shadow-xl">
            <h2 className="text-2xl md:text-3xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
              Ready to Save Time on Essay Marking?
            </h2>
            <p className="text-lg max-w-xl mx-auto mb-8 text-slate-300">
              Join thousands of educators who are already using LitMark's AI-powered essay evaluation tool.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              {currentUser ? (
                <Link 
                  to="/app" 
                  className="px-8 py-3 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-lg hover:shadow-lg hover:shadow-violet-500/30 transition-all duration-300 transform hover:-translate-y-1 hover:from-violet-700 hover:to-indigo-700 shadow-md"
                >
                  <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]">Go to Dashboard</span>
                </Link>
              ) : (
                <Link 
                  to="/login" 
                  className="px-8 py-3 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-lg hover:shadow-lg hover:shadow-violet-500/30 transition-all duration-300 transform hover:-translate-y-1 hover:from-violet-700 hover:to-indigo-700 shadow-md"
                >
                  <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]">Get Started</span>
                </Link>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Footer - simplified */}
      <footer className="relative z-10 py-8 border-t border-slate-800/50">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="mb-4 md:mb-0">
              <h3 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-sky-400 to-violet-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                LitMark
              </h3>
            </div>
            <div className="flex space-x-6">
              <a href="#" className="text-slate-400 hover:text-white transition-colors duration-300">
                Terms
              </a>
              <a href="#" className="text-slate-400 hover:text-white transition-colors duration-300">
                Privacy
              </a>
              <a href="#" className="text-slate-400 hover:text-white transition-colors duration-300">
                Contact
              </a>
            </div>
            <div className="mt-4 md:mt-0 text-slate-500">
              &copy; {new Date().getFullYear()} LitMark. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage; 