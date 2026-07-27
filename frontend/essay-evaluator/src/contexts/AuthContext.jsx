/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useContext,
} from 'react';
import { useLocation } from 'react-router-dom';

const AuthContext = createContext(null);
let authServicesPromise = null;
const AUTH_BOOTSTRAP_TIMEOUT_MS = 15_000;
const LANDING_AUTH_DEFER_MS = 700;

const getAuthServices = () => {
  if (!authServicesPromise) {
    authServicesPromise = Promise.all([
      import('../firebase'),
      import('firebase/auth'),
    ])
      .then(([firebaseConfig, firebaseAuth]) => ({
        ...firebaseConfig,
        ...firebaseAuth,
      }))
      .catch((error) => {
        authServicesPromise = null;
        throw error;
      });
  }
  return authServicesPromise;
};

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const { pathname } = useLocation();
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initializationError, setInitializationError] = useState('');
  const [initializationRetrying, setInitializationRetrying] = useState(false);
  const initializeAuthRef = useRef(null);
  const completeAuthInitializationRef = useRef(null);
  const landingReadyRef = useRef(false);
  const scheduleLandingAuthRef = useRef(null);

  const markLandingReady = useCallback(() => {
    landingReadyRef.current = true;
    scheduleLandingAuthRef.current?.();
  }, []);

  const syncAuthState = useCallback((user) => {
    if (completeAuthInitializationRef.current) {
      completeAuthInitializationRef.current(user);
      return;
    }
    setCurrentUser(user);
    setInitializationError('');
    setInitializationRetrying(false);
    setLoading(false);
  }, []);

  const signup = useCallback(async (email, password, name) => {
    initializeAuthRef.current?.();
    const {
      auth,
      browserLocalPersistence,
      createUserWithEmailAndPassword,
      setPersistence,
      updateProfile,
    } = await getAuthServices();
    await setPersistence(auth, browserLocalPersistence);
    const cred = await createUserWithEmailAndPassword(auth, email, password);
    if (name) {
      try {
        await updateProfile(cred.user, { displayName: name });
      } catch (profileError) {
        console.error('Account created, but the display name could not be saved.', profileError);
      }
    }
    syncAuthState(cred.user);
    return cred.user;
  }, [syncAuthState]);

  const login = useCallback(async (email, password, remember = true) => {
    initializeAuthRef.current?.();
    const {
      auth,
      browserLocalPersistence,
      browserSessionPersistence,
      setPersistence,
      signInWithEmailAndPassword,
    } = await getAuthServices();
    await setPersistence(
      auth,
      remember ? browserLocalPersistence : browserSessionPersistence,
    );
    const credential = await signInWithEmailAndPassword(auth, email, password);
    syncAuthState(credential.user);
    return credential;
  }, [syncAuthState]);

  const signInWithGoogle = useCallback(async (remember = true) => {
    initializeAuthRef.current?.();
    const {
      auth,
      browserLocalPersistence,
      browserSessionPersistence,
      googleProvider,
      setPersistence,
      signInWithPopup,
    } = await getAuthServices();
    await setPersistence(
      auth,
      remember ? browserLocalPersistence : browserSessionPersistence,
    );
    const credential = await signInWithPopup(auth, googleProvider);
    syncAuthState(credential.user);
    return credential;
  }, [syncAuthState]);

  const logout = useCallback(async () => {
    initializeAuthRef.current?.();
    const { auth, signOut } = await getAuthServices();
    await signOut(auth);
    syncAuthState(null);
  }, [syncAuthState]);
  const resetPassword = useCallback(async (email) => {
    initializeAuthRef.current?.();
    const { auth, sendPasswordResetEmail } = await getAuthServices();
    return sendPasswordResetEmail(auth, email);
  }, []);

  useEffect(() => {
    let active = true;
    let unsubscribe = null;
    let idleCallbackId = null;
    let fallbackTimerId = null;
    let bootstrapTimeoutId = null;
    let initializationStarted = false;
    let attemptVersion = 0;
    let hasFailed = false;

    const clearBootstrapTimeout = () => {
      if (bootstrapTimeoutId !== null) {
        window.clearTimeout(bootstrapTimeoutId);
        bootstrapTimeoutId = null;
      }
    };

    const completeInitialization = (user) => {
      if (!active) return;
      clearBootstrapTimeout();
      initializationStarted = true;
      hasFailed = false;
      setCurrentUser(user);
      setInitializationError('');
      setInitializationRetrying(false);
      setLoading(false);
    };
    completeAuthInitializationRef.current = completeInitialization;

    const failInitialization = (attemptId, message, error) => {
      if (!active || attemptId !== attemptVersion) return;
      if (error) console.error(message, error);
      attemptVersion += 1;
      initializationStarted = false;
      hasFailed = true;
      clearBootstrapTimeout();
      unsubscribe?.();
      unsubscribe = null;
      setCurrentUser(null);
      setInitializationError(
        'Your existing session could not be verified. Retry the session check or sign in again.',
      );
      setInitializationRetrying(false);
      setLoading(false);
    };

    const initializeAuth = () => {
      if (!active || initializationStarted) return;
      const attemptId = attemptVersion + 1;
      attemptVersion = attemptId;
      initializationStarted = true;
      setInitializationRetrying(hasFailed);
      setLoading(true);
      if (idleCallbackId !== null) {
        window.cancelIdleCallback(idleCallbackId);
        idleCallbackId = null;
      }
      if (fallbackTimerId !== null) {
        window.clearTimeout(fallbackTimerId);
        fallbackTimerId = null;
      }
      bootstrapTimeoutId = window.setTimeout(() => {
        failInitialization(
          attemptId,
          'Authentication initialization timed out.',
        );
      }, AUTH_BOOTSTRAP_TIMEOUT_MS);
      getAuthServices()
        .then(({ auth, onAuthStateChanged }) => {
          if (!active || attemptId !== attemptVersion) return;
          unsubscribe = onAuthStateChanged(
            auth,
            (user) => {
              if (!active || attemptId !== attemptVersion) return;
              completeInitialization(user);
            },
            (error) => {
              failInitialization(
                attemptId,
                'Authentication state could not be observed.',
                error,
              );
            },
          );
        })
        .catch((error) => {
          failInitialization(
            attemptId,
            'Authentication could not be initialized.',
            error,
          );
        });
    };
    initializeAuthRef.current = initializeAuth;

    const scheduleLandingInitialization = () => {
      if (
        !active
        || initializationStarted
        || fallbackTimerId !== null
        || idleCallbackId !== null
      ) {
        return;
      }

      fallbackTimerId = window.setTimeout(() => {
        fallbackTimerId = null;
        if ('requestIdleCallback' in window) {
          idleCallbackId = window.requestIdleCallback(initializeAuth, { timeout: 1000 });
        } else {
          initializeAuth();
        }
      }, LANDING_AUTH_DEFER_MS);
    };
    scheduleLandingAuthRef.current = scheduleLandingInitialization;

    const canDeferOnLanding = window.location.pathname === '/';
    if (canDeferOnLanding) {
      if (landingReadyRef.current) scheduleLandingInitialization();
    } else {
      initializeAuth();
    }

    return () => {
      active = false;
      attemptVersion += 1;
      initializeAuthRef.current = null;
      completeAuthInitializationRef.current = null;
      scheduleLandingAuthRef.current = null;
      if (idleCallbackId !== null) window.cancelIdleCallback(idleCallbackId);
      if (fallbackTimerId !== null) window.clearTimeout(fallbackTimerId);
      clearBootstrapTimeout();
      unsubscribe?.();
    };
  }, []);

  useEffect(() => {
    if (pathname !== '/') initializeAuthRef.current?.();
  }, [pathname]);

  const retryInitialization = useCallback(() => {
    initializeAuthRef.current?.();
  }, []);

  const value = useMemo(
    () => ({
      currentUser,
      signup,
      login,
      logout,
      signInWithGoogle,
      resetPassword,
      initializationError,
      initializationRetrying,
      retryInitialization,
      markLandingReady,
      loading,
    }),
    [
      currentUser,
      signup,
      login,
      logout,
      signInWithGoogle,
      resetPassword,
      initializationError,
      initializationRetrying,
      retryInitialization,
      markLandingReady,
      loading,
    ],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
