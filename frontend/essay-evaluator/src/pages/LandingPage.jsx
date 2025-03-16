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
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-violet-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
        <div className="absolute top-40 -left-20 w-80 h-80 bg-sky-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-40 left-20 w-80 h-80 bg-emerald-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      {/* Hero Section */}
      <header className="relative z-10 pt-24 pb-16 md:pt-32 md:pb-24">
        <div className="container mx-auto px-4 text-center">
          <div 
            className="inline-block bg-slate-900/80 backdrop-blur-md px-8 py-6 rounded-xl mb-6 shadow-xl border border-slate-700"
            data-aos="zoom-in"
          >
            <h1 className="text-3xl md:text-5xl font-bold leading-tight">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                LitMark
              </span>
            </h1>
            <p className="text-xl md:text-2xl font-medium mt-3 bg-clip-text text-transparent bg-gradient-to-r from-sky-300 to-emerald-300 drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]">
              AI-based essay marker
            </p>
          </div>
          <p 
            className="text-lg md:text-xl max-w-2xl mx-auto mb-10 text-slate-300 leading-relaxed"
            data-aos="fade-up"
            data-aos-delay="200"
          >
            Reduce your time and maintain the quality of feedback with our advanced AI evaluation system.
          </p>
          <div 
            className="flex flex-col sm:flex-row justify-center gap-4"
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
                <button 
                  onClick={handleGoogleSignIn}
                  className="px-8 py-3 rounded-lg bg-white text-slate-800 font-bold text-lg hover:bg-gray-100 transition-all duration-300 transform hover:-translate-y-1 shadow-md flex items-center justify-center gap-2 border border-gray-200"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="24px" height="24px">
                    <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
                    <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
                    <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
                    <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
                  </svg>
                  <span>Sign in with Google</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Features Section */}
      <section className="relative z-10 py-16 md:py-24 bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4">
          <h2 
            className="text-2xl md:text-3xl font-bold text-center mb-16 bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]"
            data-aos="fade-up"
          >
            Powerful Features
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => (
              <div 
                key={index}
                className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700 hover:border-violet-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-violet-500/10 group hover:translate-y-[-8px]"
                data-aos="fade-up"
                data-aos-delay={100 * index}
              >
                <div className={`${feature.color} ${feature.hoverColor} w-14 h-14 rounded-full flex items-center justify-center text-2xl mb-4 group-hover:scale-110 transition-all duration-300`}>
                  {feature.icon}
                </div>
                <h3 className="text-xl font-bold mb-3 text-white group-hover:text-violet-400 transition-colors duration-300">{feature.title}</h3>
                <p className="text-slate-400 group-hover:text-slate-300 transition-colors duration-300">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="relative z-10 py-16 md:py-24">
        <div className="container mx-auto px-4">
          <h2 
            className="text-2xl md:text-3xl font-bold text-center mb-16 bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]"
            data-aos="fade-up"
          >
            How It Works
          </h2>
          <div className="max-w-4xl mx-auto">
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-0 md:left-1/2 transform md:-translate-x-1/2 h-full w-1 bg-gradient-to-b from-sky-600 via-violet-600 to-emerald-600"></div>
              
              {/* Steps */}
              <div className="space-y-16 md:space-y-24">
                <div className="relative flex flex-col md:flex-row items-center">
                  <div 
                    className="md:w-1/2 md:pr-12 mb-6 md:mb-0 text-right md:order-1 order-2"
                    data-aos="fade-right"
                  >
                    <h3 className="text-xl font-bold mb-2 text-sky-400">Upload Your Essay</h3>
                    <p className="text-slate-400">Upload your essay in PDF, TXT, or DOCX format to get started.</p>
                  </div>
                  <div className="z-10 order-1 md:order-2 group">
                    <div className="w-14 h-14 rounded-full bg-sky-600 flex items-center justify-center text-xl font-bold group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-sky-600/20">1</div>
                  </div>
                </div>
                
                <div className="relative flex flex-col md:flex-row items-center">
                  <div 
                    className="md:w-1/2 md:pl-12 mb-6 md:mb-0 text-left order-2"
                    data-aos="fade-left"
                  >
                    <h3 className="text-xl font-bold mb-2 text-violet-400">Select or Create a Rubric</h3>
                    <p className="text-slate-400">Choose from our pre-defined rubrics or create your own custom evaluation criteria.</p>
                  </div>
                  <div className="z-10 md:order-1 order-1 md:ml-auto group">
                    <div className="w-14 h-14 rounded-full bg-violet-600 flex items-center justify-center text-xl font-bold group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-violet-600/20">2</div>
                  </div>
                </div>
                
                <div className="relative flex flex-col md:flex-row items-center">
                  <div 
                    className="md:w-1/2 md:pr-12 mb-6 md:mb-0 text-right md:order-1 order-2"
                    data-aos="fade-right"
                  >
                    <h3 className="text-xl font-bold mb-2 text-indigo-400">AI Evaluation</h3>
                    <p className="text-slate-400">Our AI analyzes your essay based on the selected rubric and generates detailed feedback.</p>
                  </div>
                  <div className="z-10 order-1 md:order-2 group">
                    <div className="w-14 h-14 rounded-full bg-indigo-600 flex items-center justify-center text-xl font-bold group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-indigo-600/20">3</div>
                  </div>
                </div>
                
                <div className="relative flex flex-col md:flex-row items-center">
                  <div 
                    className="md:w-1/2 md:pl-12 mb-6 md:mb-0 text-left order-2"
                    data-aos="fade-left"
                  >
                    <h3 className="text-xl font-bold mb-2 text-emerald-400">Get Your Report</h3>
                    <p className="text-slate-400">Receive a comprehensive PDF report with scores, feedback, and suggestions for improvement.</p>
                  </div>
                  <div className="z-10 md:order-1 order-1 md:ml-auto group">
                    <div className="w-14 h-14 rounded-full bg-emerald-600 flex items-center justify-center text-xl font-bold group-hover:scale-110 transition-transform duration-300 shadow-lg shadow-emerald-600/20">4</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="relative z-10 py-16 md:py-24 bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4">
          <h2 
            className="text-2xl md:text-3xl font-bold text-center mb-16 bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]"
            data-aos="fade-up"
          >
            What Our Users Say
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map((testimonial, index) => (
              <div 
                key={index}
                className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border border-slate-700 hover:border-violet-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-violet-500/10 hover:translate-y-[-8px]"
                data-aos="fade-up"
                data-aos-delay={100 * index}
              >
                <div className="flex items-center mb-4">
                  <div className="relative">
                    <div className="absolute inset-0 bg-gradient-to-r from-sky-500 to-violet-500 rounded-full blur-sm opacity-70"></div>
                    <img 
                      src={testimonial.avatar} 
                      alt={testimonial.name} 
                      className="w-14 h-14 rounded-full relative border-2 border-white"
                    />
                  </div>
                  <div className="ml-4">
                    <h3 className="text-lg font-bold text-white">{testimonial.name}</h3>
                    <p className="text-violet-400">{testimonial.role}</p>
                  </div>
                </div>
                <p className="text-slate-300 italic leading-relaxed">"{testimonial.content}"</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 py-16 md:py-24">
        <div 
          className="container mx-auto px-4 text-center"
          data-aos="zoom-in"
        >
          <div className="max-w-3xl mx-auto bg-gradient-to-r from-slate-800/80 to-slate-900/80 backdrop-blur-md p-10 rounded-2xl border border-slate-700 shadow-xl">
            <h2 className="text-2xl md:text-3xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-sky-400 via-violet-400 to-emerald-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
              Ready to Save Time on Essay Marking?
            </h2>
            <p className="text-lg max-w-2xl mx-auto mb-10 text-slate-300">
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
                  <button 
                    onClick={handleGoogleSignIn}
                    className="px-8 py-3 rounded-lg bg-white text-slate-800 font-bold text-lg hover:bg-gray-100 transition-all duration-300 transform hover:-translate-y-1 shadow-md flex items-center justify-center gap-2 border border-gray-200"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="24px" height="24px">
                      <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z"/>
                      <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z"/>
                      <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z"/>
                      <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z"/>
                    </svg>
                    <span>Sign in with Google</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 py-8 border-t border-slate-800">
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