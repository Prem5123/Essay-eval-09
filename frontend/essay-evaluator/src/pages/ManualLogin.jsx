import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const ManualLogin = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [customId, setCustomId] = useState('');
  const { createManualUser } = useAuth();
  const navigate = useNavigate();

  const handleCreateUser = (e) => {
    e.preventDefault();
    
    // Create a user object with the provided details
    const userData = {
      id: customId || Date.now().toString(),
      name: name || 'Test User',
      email: email || 'test@example.com'
    };
    
    // Create the user and store in localStorage
    createManualUser(userData);
    
    // Navigate to the app
    navigate('/app');
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-black flex items-center justify-center px-4 pt-16">
      <div className="max-w-md w-full bg-gray-800/50 backdrop-blur-sm p-8 rounded-2xl shadow-xl border border-gray-700">
        <h1 className="text-2xl font-bold text-center mb-6 text-white">Create Manual User</h1>
        <p className="text-gray-400 mb-6 text-center">
          This page is for development purposes only. Create a user manually to bypass the authentication flow.
        </p>
        
        <form onSubmit={handleCreateUser} className="space-y-6">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-2">
              Name (optional)
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-gray-700/50 border border-gray-600 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="Your Name"
            />
          </div>
          
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
              Email (optional)
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-gray-700/50 border border-gray-600 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="your@email.com"
            />
          </div>
          
          <div>
            <label htmlFor="custom-id" className="block text-sm font-medium text-gray-300 mb-2">
              Custom ID (optional)
            </label>
            <input
              id="custom-id"
              type="text"
              value={customId}
              onChange={(e) => setCustomId(e.target.value)}
              className="w-full px-4 py-3 rounded-lg bg-gray-700/50 border border-gray-600 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              placeholder="user123"
            />
            <p className="text-xs text-gray-500 mt-1">
              If left empty, a timestamp-based ID will be generated.
            </p>
          </div>
          
          <button
            type="submit"
            className="w-full py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-all duration-300"
          >
            Create User & Login
          </button>
        </form>
        
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-400">
            Default values will be used for any empty fields.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ManualLogin; 