const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Generic CRUD API
export const api = {
  listItems: () => request<any[]>('/items'),
  getItem: (id: string) => request<any>(`/items/${id}`),
  createItem: (data: { name: string; description?: string }) =>
    request<any>('/items', { method: 'POST', body: JSON.stringify(data) }),
  updateItem: (id: string, data: { name: string; description?: string }) =>
    request<any>(`/items/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteItem: (id: string) =>
    request<void>(`/items/${id}`, { method: 'DELETE' }),
};
