import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import AOS from 'aos';
import 'aos/dist/aos.css';
import logoSvg from '../assets/images/logo.svg';

const LandingPage = () => {
  const { currentUser, signInWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [typedText, setTypedText] = useState('');
  const [isTyping, setIsTyping] = useState(true);
  const fullText = "AI based essay evaluator";

  useEffect(() => {
    AOS.init({
      duration: 800,
      once: false,
      mirror: true,
      easing: 'ease-out-cubic',
    });
  }, []);

  useEffect(() => {
    if (isTyping) {
      if (typedText.length < fullText.length) {
        const timeout = setTimeout(() => {
          setTypedText(fullText.slice(0, typedText.length + 1));
        }, 100);
        return () => clearTimeout(timeout);
      } else {
        const timeout = setTimeout(() => {
          setIsTyping(false);
        }, 1000);
        return () => clearTimeout(timeout);
      }
    } else {
      const timeout = setTimeout(() => {
        setTypedText('');
        setIsTyping(true);
      }, 3000);
      return () => clearTimeout(timeout);
    }
  }, [typedText, isTyping]);

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
      color: "bg-[#0C2340]",
      hoverColor: "hover:bg-[#0D2A4D]",
    },
    {
      title: "Custom Rubrics",
      description: "Create and save your own evaluation rubrics or use our pre-defined templates.",
      icon: "📝",
      color: "bg-[#0C2340]",
      hoverColor: "hover:bg-[#0D2A4D]",
    },
    {
      title: "Detailed PDF Reports",
      description: "Receive comprehensive PDF reports with scores and improvement suggestions.",
      icon: "📊",
      color: "bg-[#0C2340]",
      hoverColor: "hover:bg-[#0D2A4D]",
    },
    {
      title: "Multiple File Formats",
      description: "Upload essays in PDF, TXT, or DOCX formats for evaluation.",
      icon: "📄",
      color: "bg-[#0C2340]",
      hoverColor: "hover:bg-[#0D2A4D]",
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
    <div className="min-h-screen bg-black text-white overflow-hidden font-sans">
      {/* Animated background - elegant, subtle, navy-based */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute top-1/3 -left-20 w-96 h-96 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-40 right-20 w-80 h-80 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-25 animate-blob animation-delay-4000"></div>
        <div className="absolute -bottom-20 left-1/4 w-72 h-72 bg-[#0C2340] rounded-full mix-blend-screen filter blur-3xl opacity-25 animate-blob animation-delay-6000"></div>
      </div>

      {/* Hero Section - elegant and minimal */}
      <header className="relative z-10 pt-28 pb-16 md:pt-36 md:pb-24">
        <div className="container mx-auto px-4 text-center">
          <div 
            className="inline-block p-10 rounded-2xl mb-8"
            data-aos="zoom-in"
          >
            <div className="flex flex-col items-center justify-center">
              <h1 className="text-5xl md:text-7xl font-bold leading-tight tracking-tight">
                <span className="text-white">
                  LitMark
                </span>
              </h1>
            </div>
            <p className="text-xl md:text-3xl font-light mt-6 text-white h-10 flex items-center justify-center">
              {typedText}
              <span className={`inline-block w-0.5 h-8 ml-1 bg-white ${isTyping ? 'animate-blink' : ''}`}></span>
            </p>
          </div>
          <p 
            className="text-lg md:text-xl max-w-2xl mx-auto mb-12 text-white leading-relaxed font-light"
            data-aos="fade-up"
            data-aos-delay="200"
          >
            Reduce your grading time and enhance feedback quality with our advanced AI evaluation system.
          </p>
          <div 
            className="flex flex-col sm:flex-row justify-center gap-6"
            data-aos="fade-up"
            data-aos-delay="400"
          >
            {currentUser ? (
              <Link 
                to="/app" 
                className="px-8 py-3 rounded-lg bg-[#0C2340] text-white font-medium text-lg hover:shadow-lg hover:shadow-[#0C2340]/40 transition-all duration-300 transform hover:-translate-y-1 hover:bg-[#0D2A4D]"
              >
                Go to Dashboard
              </Link>
            ) : (
              <>
                <Link 
                  to="/login" 
                  className="px-8 py-3 rounded-lg bg-[#0C2340] text-white font-medium text-lg hover:shadow-lg hover:shadow-[#0C2340]/40 transition-all duration-300 transform hover:-translate-y-1 hover:bg-[#0D2A4D]"
                >
                  Get Started
                </Link>
                <Link 
                  to="/signup" 
                  className="px-8 py-3 rounded-lg bg-transparent border border-[#0C2340] text-white font-medium text-lg hover:bg-[#0C2340]/20 transition-all duration-300 transform hover:-translate-y-1"
                >
                  Sign Up
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Features Section - clean and sophisticated with black theme */}
      <section className="relative z-10 py-20 md:py-28 bg-black/90">
        <div className="container mx-auto px-4">
          <h2 
            className="text-2xl md:text-3xl font-bold text-center mb-20 text-white"
            data-aos="fade-up"
          >
            Key Features
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div 
                key={index}
                className="bg-black/80 rounded-xl p-8 border border-[#0C2340] transition-all duration-300 hover:shadow-xl hover:shadow-[#0C2340]/30 group hover:translate-y-[-8px]"
                data-aos="fade-up"
                data-aos-delay={100 * index}
              >
                <div className={`${feature.color} ${feature.hoverColor} w-16 h-16 rounded-xl flex items-center justify-center text-2xl mb-6 group-hover:scale-110 transition-all duration-300 shadow-lg`}>
                  {feature.icon}
                </div>
                <h3 className="text-xl font-medium mb-4 text-white group-hover:text-[#6E9CDE] transition-colors duration-300">{feature.title}</h3>
                <p className="text-gray-300 group-hover:text-white transition-colors duration-300 font-light">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials Section - refined and focused */}
      <section className="relative z-10 py-20 md:py-28 bg-black">
        <div className="container mx-auto px-4">
          <h2 
            className="text-2xl md:text-3xl font-bold text-center mb-16 text-white"
            data-aos="fade-up"
          >
            What People Are Saying
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map((testimonial, index) => (
              <div 
                key={index}
                className="bg-black/90 rounded-xl p-8 border border-[#0C2340] hover:shadow-2xl transition-all duration-300 hover:translate-y-[-8px]"
                data-aos="fade-up"
                data-aos-delay={100 * index}
              >
                <div className="mb-6 relative">
                  <svg className="absolute -top-4 -left-4 text-[#6E9CDE] w-8 h-8 opacity-80" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
                  </svg>
                  <p className="text-white italic relative">{testimonial.content}</p>
                </div>
                <div className="flex items-center">
                  <img src={testimonial.avatar} alt={testimonial.name} className="w-12 h-12 rounded-full mr-4" />
                  <div>
                    <h4 className="text-white font-medium">{testimonial.name}</h4>
                    <p className="text-[#6E9CDE] text-sm">{testimonial.role}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section - elegant with black theme */}
      <section className="relative z-10 py-20 md:py-28">
        <div 
          className="container mx-auto px-4 text-center"
          data-aos="zoom-in"
        >
          <div className="max-w-3xl mx-auto bg-gradient-to-b from-black/90 to-black p-12 rounded-2xl border border-[#0C2340] shadow-2xl">
            <h2 className="text-2xl md:text-3xl font-bold mb-6 text-white">
              Ready to Save Time on Essay Marking?
            </h2>
            <p className="text-lg max-w-xl mx-auto mb-8 text-white font-light">
              Join thousands of educators who are already using LitMark's AI-powered essay evaluation tool.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              {currentUser ? (
                <Link 
                  to="/app" 
                  className="px-8 py-3 rounded-lg bg-[#0C2340] text-white font-medium text-lg hover:shadow-lg hover:shadow-[#0C2340]/40 transition-all duration-300 transform hover:-translate-y-1 hover:bg-[#0D2A4D]"
                >
                  Go to Dashboard
                </Link>
              ) : (
                <Link 
                  to="/login" 
                  className="px-8 py-3 rounded-lg bg-[#0C2340] text-white font-medium text-lg hover:shadow-lg hover:shadow-[#0C2340]/40 transition-all duration-300 transform hover:-translate-y-1 hover:bg-[#0D2A4D]"
                >
                  Get Started
                </Link>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Footer - elegant and minimal */}
      <footer className="relative z-10 py-10 border-t border-[#0C2340]">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="mb-4 md:mb-0">
              <h3 className="text-xl font-bold text-white">
                LitMark
              </h3>
              <p className="text-gray-400 text-sm mt-1">© {new Date().getFullYear()} LitMark. All rights reserved.</p>
            </div>
            <div className="flex space-x-8">
              <a href="#" className="text-gray-400 hover:text-white transition-colors duration-300 text-sm">
                Terms
              </a>
              <a href="#" className="text-gray-400 hover:text-white transition-colors duration-300 text-sm">
                Privacy
              </a>
              <a href="#" className="text-gray-400 hover:text-white transition-colors duration-300 text-sm">
                Contact
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage; 