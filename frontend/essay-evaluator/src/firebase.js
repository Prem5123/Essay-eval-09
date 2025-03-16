// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyD7ba6qOXPM35PK3Q-zHBHEmVS4HLdnoGY",
  authDomain: "essay-eval-38859.firebaseapp.com",
  projectId: "essay-eval-38859",
  storageBucket: "essay-eval-38859.firebasestorage.app",
  messagingSenderId: "550132665996",
  appId: "1:550132665996:web:4a0891d0cf3981fbaaf5a9",
  measurementId: "G-TN6K4VW53J"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

// Configure Google provider
googleProvider.setCustomParameters({
  prompt: 'select_account'
});

export { auth, googleProvider }; 