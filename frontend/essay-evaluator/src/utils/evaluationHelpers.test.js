import test from 'node:test';
import assert from 'node:assert/strict';
import {
  estimateBatchTransferSize,
  getResponseError,
  mergeImportedRubrics,
  normalizeApiBaseUrl,
  parseSavedRubrics,
  sortEvaluationResults,
} from './evaluationHelpers.js';

test('filters malformed rubrics loaded from browser storage', () => {
  const validRubric = { id: 'one', name: 'One', content: 'Criteria' };
  assert.deepEqual(
    parseSavedRubrics(JSON.stringify([
      validRubric,
      null,
      { id: 'missing-content', name: 'Broken' },
    ])),
    [validRubric],
  );
});

test('treats absent or non-array rubric storage values as empty', () => {
  assert.deepEqual(parseSavedRubrics(null), []);
  assert.deepEqual(parseSavedRubrics(JSON.stringify({ rubrics: [] })), []);
});

test('imports legacy rubrics without duplicating content or colliding ids', () => {
  const saved = [{ id: 'one', name: 'One', content: 'Existing' }];
  assert.deepEqual(
    mergeImportedRubrics(saved, [
      { id: 'one', name: 'One', content: 'Existing' },
      { id: 'one', name: 'Two', content: 'Imported' },
    ]),
    [
      ...saved,
      { id: 'one-imported-1', name: 'Two', content: 'Imported' },
    ],
  );
});

test('finds the next available id and removes duplicate legacy imports', () => {
  const saved = [
    { id: 'custom', name: 'Saved', content: 'Current' },
    { id: 'custom-imported-1', name: 'Earlier import', content: 'Earlier' },
  ];

  assert.deepEqual(
    mergeImportedRubrics(saved, [
      { id: 'custom', name: 'Legacy', content: 'Criteria' },
      { id: 'another-id', name: 'Legacy', content: 'Criteria' },
    ]),
    [
      ...saved,
      {
        id: 'custom-imported-2',
        name: 'Legacy',
        content: 'Criteria',
      },
    ],
  );
});

test('normalizes configured API base URLs before endpoint paths are appended', () => {
  assert.equal(
    normalizeApiBaseUrl(' https://api.example.com/// '),
    'https://api.example.com',
  );
  assert.equal(normalizeApiBaseUrl(''), 'http://localhost:8000');
});

test('normalizes same-origin and blank API base URL configurations', () => {
  assert.equal(normalizeApiBaseUrl('/api///'), '/api');
  assert.equal(normalizeApiBaseUrl('/'), '');
  assert.equal(normalizeApiBaseUrl('   '), 'http://localhost:8000');
});

test('normalizes validation details from an API error', () => {
  assert.equal(
    getResponseError(
      { detail: [{ msg: 'Essay is required.' }, { msg: 'Rubric is invalid.' }] },
      'fallback',
    ),
    'Essay is required. Rubric is invalid.',
  );
});

test('falls back when the API response has no useful detail', () => {
  assert.equal(getResponseError({}, 'Evaluation failed.'), 'Evaluation failed.');
  assert.equal(
    getResponseError({ detail: '   ' }, 'Evaluation failed.'),
    'Evaluation failed.',
  );
  assert.equal(
    getResponseError({ detail: [{ msg: '' }, null] }, 'Evaluation failed.'),
    'Evaluation failed.',
  );
});

test('keeps concurrent evaluation results in upload and split-document order', () => {
  const secondUpload = { id: 'second', sourceOrder: 1, resultOrder: 0 };
  const firstUploadSecondStudent = {
    id: 'first-b',
    sourceOrder: 0,
    resultOrder: 1,
  };
  const firstUploadFirstStudent = {
    id: 'first-a',
    sourceOrder: 0,
    resultOrder: 0,
  };

  assert.deepEqual(
    sortEvaluationResults([
      secondUpload,
      firstUploadSecondStudent,
      firstUploadFirstStudent,
    ]).map(result => result.id),
    ['first-a', 'first-b', 'second'],
  );
});

test('estimates repeated rubric transfer across an uploaded batch', () => {
  assert.equal(
    estimateBatchTransferSize({
      essayFiles: [{ size: 1_000 }, { size: 2_000 }],
      rubricFile: { size: 500 },
    }),
    4_000,
  );
});

test('measures pasted text and rubric text as UTF-8 bytes', () => {
  assert.equal(
    estimateBatchTransferSize({
      pastedText: 'Résumé',
      rubricText: '✓',
    }),
    11,
  );
});

test('preserves the exact batch transfer boundary and repeated-rubric byte', () => {
  const limit = 75 * 1024 * 1024;
  const essays = [{ size: limit - 2 }, { size: 0 }];

  assert.equal(
    estimateBatchTransferSize({
      essayFiles: essays,
      rubricFile: { size: 1 },
    }),
    limit,
  );
  assert.equal(
    estimateBatchTransferSize({
      essayFiles: essays,
      rubricFile: { size: 2 },
    }),
    limit + 2,
  );
});

test('does not count a rubric when there is no essay request', () => {
  assert.equal(
    estimateBatchTransferSize({
      rubricFile: { size: 5 * 1024 * 1024 },
    }),
    0,
  );
});
