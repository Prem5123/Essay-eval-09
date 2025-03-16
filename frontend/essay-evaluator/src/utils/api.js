import axios from 'axios';

// Get the API URL from environment variables or use a default
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Create an axios instance with the base URL
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});

// API functions for essay evaluation
export const evaluateEssay = async (formData) => {
  try {
    const response = await api.post('/evaluate/', formData);
    return response.data;
  } catch (error) {
    console.error('Error evaluating essay:', error);
    throw error;
  }
};

// API functions for text extraction
export const extractText = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await api.post('/extract_text/', formData);
    return response.data;
  } catch (error) {
    console.error('Error extracting text:', error);
    throw error;
  }
};

// API functions for rubric management
export const getRubrics = async () => {
  try {
    const response = await api.get('/rubrics/');
    return response.data;
  } catch (error) {
    console.error('Error getting rubrics:', error);
    throw error;
  }
};

export const getRubricById = async (id) => {
  try {
    const response = await api.get(`/rubrics/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error getting rubric ${id}:`, error);
    throw error;
  }
};

export const createRubric = async (content, name) => {
  const formData = new FormData();
  formData.append('content', content);
  if (name) formData.append('name', name);
  
  try {
    const response = await api.post('/rubrics/', formData);
    return response.data;
  } catch (error) {
    console.error('Error creating rubric:', error);
    throw error;
  }
};

export const updateRubric = async (id, content, name) => {
  const formData = new FormData();
  formData.append('content', content);
  if (name) formData.append('name', name);
  
  try {
    const response = await api.put(`/rubrics/${id}`, formData);
    return response.data;
  } catch (error) {
    console.error(`Error updating rubric ${id}:`, error);
    throw error;
  }
};

export const deleteRubric = async (id) => {
  try {
    const response = await api.delete(`/rubrics/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error deleting rubric ${id}:`, error);
    throw error;
  }
};

export const getDefaultRubric = async () => {
  try {
    const response = await api.get('/default-rubric/');
    return response.data;
  } catch (error) {
    console.error('Error getting default rubric:', error);
    throw error;
  }
};

export const generateRubric = async (subject, level, criteriaCount, apiKey) => {
  const formData = new FormData();
  formData.append('subject', subject);
  formData.append('level', level);
  formData.append('criteria_count', criteriaCount);
  formData.append('api_key', apiKey);
  
  try {
    const response = await api.post('/generate-rubric/', formData);
    return response.data;
  } catch (error) {
    console.error('Error generating rubric:', error);
    throw error;
  }
};

export const uploadRubricFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await api.post('/upload-rubric-file/', formData);
    return response.data;
  } catch (error) {
    console.error('Error uploading rubric file:', error);
    throw error;
  }
};

export const verifyApiKey = async (apiKey) => {
  const formData = new FormData();
  formData.append('api_key', apiKey);
  
  try {
    const response = await api.post('/verify_api_key/', formData);
    return response.data;
  } catch (error) {
    console.error('Error verifying API key:', error);
    throw error;
  }
};

export default api; 