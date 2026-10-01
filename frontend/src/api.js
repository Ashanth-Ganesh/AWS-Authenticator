export async function api(path, { csrfToken, ...options } = {}) {
  const headers = new Headers(options.headers);
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: 'same-origin',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}

export function validateFile(file) {
  if (!file || !file.name) return;
  if (!file.name.toLowerCase().endsWith('.txt')) throw new Error('Please choose a .txt file.');
  if (file.size > 1024 * 1024) throw new Error('Choose a text file of 1 MB or less.');
}
