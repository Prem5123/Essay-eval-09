import CryptoJS from 'crypto-js';

// The secret key used for encryption - in a real app, this would be more secure
// For this implementation, we'll use a fixed string combined with a user-specific value
const BASE_SECRET = 'essay-evaluator-secret-key';

/**
 * Generate a user-specific encryption key
 * @param {string} userId - The Firebase user ID
 * @returns {string} - The encryption key
 */
const generateEncryptionKey = (userId) => {
  return `${BASE_SECRET}-${userId}`;
};

/**
 * Store the API key securely in localStorage
 * @param {string} apiKey - The API key to store
 * @param {string} userId - The Firebase user ID
 */
export const storeApiKey = (apiKey, userId) => {
  if (!apiKey || !userId) return;
  
  try {
    const encryptionKey = generateEncryptionKey(userId);
    const encryptedKey = CryptoJS.AES.encrypt(apiKey, encryptionKey).toString();
    localStorage.setItem(`geminiApiKey-${userId}`, encryptedKey);
    return true;
  } catch (error) {
    console.error('Failed to store API key:', error);
    return false;
  }
};

/**
 * Retrieve the API key from localStorage
 * @param {string} userId - The Firebase user ID
 * @returns {string|null} - The decrypted API key or null if not found
 */
export const retrieveApiKey = (userId) => {
  if (!userId) return null;
  
  try {
    const encryptedKey = localStorage.getItem(`geminiApiKey-${userId}`);
    if (!encryptedKey) return null;
    
    const encryptionKey = generateEncryptionKey(userId);
    const bytes = CryptoJS.AES.decrypt(encryptedKey, encryptionKey);
    const decryptedKey = bytes.toString(CryptoJS.enc.Utf8);
    
    return decryptedKey || null;
  } catch (error) {
    console.error('Failed to retrieve API key:', error);
    return null;
  }
};

/**
 * Remove the stored API key
 * @param {string} userId - The Firebase user ID
 */
export const removeApiKey = (userId) => {
  if (!userId) return;
  
  try {
    localStorage.removeItem(`geminiApiKey-${userId}`);
    return true;
  } catch (error) {
    console.error('Failed to remove API key:', error);
    return false;
  }
};

/**
 * Check if an API key is stored for the user
 * @param {string} userId - The Firebase user ID
 * @returns {boolean} - True if an API key is stored
 */
export const hasStoredApiKey = (userId) => {
  if (!userId) return false;
  return localStorage.getItem(`geminiApiKey-${userId}`) !== null;
}; 