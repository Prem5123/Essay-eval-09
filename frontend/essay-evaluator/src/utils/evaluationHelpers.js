export const parseSavedRubrics = (rawValue) => {
  if (!rawValue) return [];

  const parsed = JSON.parse(rawValue);
  if (!Array.isArray(parsed)) return [];

  return parsed.filter(
    rubric => rubric
      && typeof rubric.id === 'string'
      && typeof rubric.name === 'string'
      && typeof rubric.content === 'string',
  );
};

export const normalizeApiBaseUrl = (
  value,
  fallback = 'http://localhost:8000',
) => (value?.trim() || fallback).replace(/\/+$/, '');

export const mergeImportedRubrics = (savedRubrics = [], legacyRubrics = []) => {
  const merged = [...savedRubrics];
  const usedIds = new Set(savedRubrics.map(rubric => rubric.id));
  const usedContent = new Set(
    savedRubrics.map(rubric => `${rubric.name}\u0000${rubric.content}`),
  );

  legacyRubrics.forEach((rubric) => {
    const contentKey = `${rubric.name}\u0000${rubric.content}`;
    if (usedContent.has(contentKey)) return;

    const baseId = rubric.id || 'custom-imported';
    let nextId = baseId;
    let suffix = 1;
    while (usedIds.has(nextId)) {
      nextId = `${baseId}-imported-${suffix}`;
      suffix += 1;
    }

    usedIds.add(nextId);
    usedContent.add(contentKey);
    merged.push({ ...rubric, id: nextId });
  });

  return merged;
};

export const getResponseError = (payload, fallback) => {
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map(item => item?.msg)
      .filter(Boolean);
    if (messages.length > 0) return messages.join(' ');
  }
  return fallback;
};

export const sortEvaluationResults = (results = []) => (
  [...results].sort(
    (left, right) => (
      (left.sourceOrder - right.sourceOrder)
      || (left.resultOrder - right.resultOrder)
    ),
  )
);

const utf8ByteLength = (value) => new TextEncoder().encode(value || '').byteLength;

export const estimateBatchTransferSize = ({
  essayFiles = [],
  pastedText = '',
  rubricFile = null,
  rubricText = '',
}) => {
  const requestCount = essayFiles.length || (pastedText ? 1 : 0);
  const essayBytes = essayFiles.reduce(
    (total, file) => total + (Number(file?.size) || 0),
    utf8ByteLength(pastedText),
  );
  const rubricBytes = rubricFile
    ? Number(rubricFile.size) || 0
    : utf8ByteLength(rubricText);

  return essayBytes + (rubricBytes * requestCount);
};
