const API_KEY = 'hermes-secret-api-key-2025';

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json',
    },
  });
}