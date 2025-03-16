# Essay Evaluator

A modern web application for evaluating essays using AI, with custom rubrics and detailed feedback.

## Features

- AI-powered essay evaluation
- Custom rubric creation and management
- Detailed PDF reports
- Multiple file format support (PDF, TXT, DOCX)
- User authentication with email/password and Google Sign-In

## Setup

### Prerequisites

- Node.js (v16 or higher)
- npm or yarn

### Installation

1. Clone the repository
2. Navigate to the frontend directory:
   ```
   cd frontend/essay-evaluator
   ```
3. Install dependencies:
   ```
   npm install
   ```

### Firebase Setup for Authentication

To enable Google Sign-In, you need to set up Firebase:

1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Create a new project
3. Add a web app to your project
4. Enable Authentication in the Firebase console
   - Go to "Authentication" > "Sign-in method"
   - Enable "Email/Password" and "Google" providers
5. Get your Firebase configuration:
   - Go to Project Settings > General > Your Apps > Firebase SDK snippet
   - Select "Config" and copy the configuration object
6. Update the Firebase configuration in `src/firebase.js` with your own credentials:

```javascript
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_AUTH_DOMAIN",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_STORAGE_BUCKET",
  messagingSenderId: "YOUR_MESSAGING_SENDER_ID",
  appId: "YOUR_APP_ID",
  measurementId: "YOUR_MEASUREMENT_ID" // optional
};
```

### Running the Application

Start the development server:

```
npm run dev
```

The application will be available at `http://localhost:5173` (or another port if 5173 is in use).

## Backend Setup

The backend is built with Python. Follow these steps to set up the backend:

1. Navigate to the Backend directory
2. Install the required Python packages
3. Run the backend server

Detailed backend setup instructions can be found in the Backend directory's README.

## Deployment

Instructions for deploying the application to production will be added soon.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
