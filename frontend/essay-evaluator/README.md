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

### Firebase Setup

#### Authentication
1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Create a new project
3. Add a web app to your project
4. Enable Authentication in the Firebase console
   - Go to "Authentication" > "Sign-in method"
   - Enable "Email/Password" and "Google" providers
5. Get your Firebase configuration:
   - Go to Project Settings > General > Your Apps > Firebase SDK snippet
   - Select "Config" and copy the configuration object
6. Update the Firebase configuration in `src/firebase.js` with your own credentials

#### Storage Setup
1. In the Firebase Console, go to "Storage"
2. Click "Get Started" and follow the setup wizard
3. Set up security rules for your storage bucket:
   ```
   rules_version = '2';
   service firebase.storage {
     match /b/{bucket}/o {
       match /{allPaths=**} {
         allow read, write: if request.auth != null;
       }
     }
   }
   ```
4. Make sure your Firebase configuration in `src/firebase.js` includes the correct `storageBucket` value

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

### Frontend (Vercel)
1. Push your code to GitHub
2. Create a new project on Vercel
3. Connect your GitHub repository
4. Set the root directory to `frontend/essay-evaluator`
5. Add environment variables:
   - `VITE_API_URL`: Your Railway backend URL
   - All Firebase configuration variables (API key, auth domain, etc.)
6. Deploy the project

### Backend (Railway)
1. Push your code to GitHub
2. Create a new project on Railway
3. Connect your GitHub repository
4. Railway will automatically detect the `railway.json` file and configure the deployment
5. Add environment variables:
   - `ALLOWED_ORIGINS`: Your Vercel frontend URL (comma-separated if multiple)
6. Deploy the service

Railway provides persistent storage out of the box, so your uploaded files and rubrics will be preserved between deployments.

## How It Works

This application uses a modern architecture with:

1. **React Frontend**: Built with React and Vite for a fast, responsive user interface
2. **FastAPI Backend**: Python-based API for essay evaluation and rubric management
3. **Railway Deployment**: Provides persistent storage for uploaded files and rubrics
4. **Firebase Authentication**: Secure user authentication with email/password and Google Sign-In

The workflow is:
1. Users upload essays and rubrics through the frontend
2. Files are sent to the backend for processing
3. The backend uses Google's Generative AI to evaluate essays
4. Results are returned to the frontend and can be downloaded as PDF reports

Railway's persistent storage ensures that uploaded files and saved rubrics are preserved between deployments, providing a seamless experience for users.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
