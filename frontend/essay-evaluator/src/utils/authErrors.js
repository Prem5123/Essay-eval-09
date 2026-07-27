const AUTH_ERROR_MESSAGES = {
  'auth/email-already-in-use': 'An account already exists for this email address.',
  'auth/invalid-credential': 'The email or password is incorrect.',
  'auth/invalid-email': 'Enter a valid email address.',
  'auth/network-request-failed': 'The network request failed. Check your connection and try again.',
  'auth/popup-blocked': 'Your browser blocked the sign-in window. Allow pop-ups and try again.',
  'auth/popup-closed-by-user': 'The sign-in window was closed before authentication finished.',
  'auth/too-many-requests': 'Too many attempts were made. Wait a moment and try again.',
  'auth/user-disabled': 'This account has been disabled.',
  'auth/weak-password': 'Choose a stronger password with at least six characters.',
};

export const getAuthErrorMessage = (error, fallback) => (
  AUTH_ERROR_MESSAGES[error?.code] || fallback
);
