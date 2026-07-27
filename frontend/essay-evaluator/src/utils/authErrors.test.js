import test from 'node:test';
import assert from 'node:assert/strict';
import { getAuthErrorMessage } from './authErrors.js';

test('returns a friendly message for a known Firebase error', () => {
  assert.equal(
    getAuthErrorMessage(
      { code: 'auth/invalid-credential' },
      'fallback',
    ),
    'The email or password is incorrect.',
  );
});

test('uses the supplied fallback for an unknown error', () => {
  assert.equal(
    getAuthErrorMessage(
      { code: 'auth/unknown' },
      'Please try again.',
    ),
    'Please try again.',
  );
});

test('uses the supplied fallback when authentication throws no Firebase code', () => {
  assert.equal(
    getAuthErrorMessage(new Error('internal details'), 'Sign-in failed.'),
    'Sign-in failed.',
  );
  assert.equal(
    getAuthErrorMessage(null, 'Sign-in failed.'),
    'Sign-in failed.',
  );
});

test('keeps actionable messages for recoverable authentication failures', () => {
  const cases = [
    [
      'auth/network-request-failed',
      'The network request failed. Check your connection and try again.',
    ],
    [
      'auth/popup-blocked',
      'Your browser blocked the sign-in window. Allow pop-ups and try again.',
    ],
    [
      'auth/too-many-requests',
      'Too many attempts were made. Wait a moment and try again.',
    ],
  ];

  cases.forEach(([code, expected]) => {
    assert.equal(getAuthErrorMessage({ code }, 'fallback'), expected);
  });
});
