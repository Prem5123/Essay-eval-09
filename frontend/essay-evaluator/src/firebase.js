// Import the functions you need from the SDKs you need
import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyD7ba6qOXPM35PK3Q-zHBHEmVS4HLdnoGY",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "essay-eval-38859.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "essay-eval-38859",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "essay-eval-38859.appspot.com",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "550132665996",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:550132665996:web:4a0891d0cf3981fbaaf5a9",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-TN6K4VW53J"
};

// Initialize Firebase
const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

// Configure Google provider
googleProvider.setCustomParameters({
  prompt: 'select_account'
});

export { auth, googleProvider };
