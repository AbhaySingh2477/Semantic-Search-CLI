/**
 * Notebook Service
 * Handles API communication for notebook management.
 */

import { api } from '@core/api.js';

/**
 * List all notebooks.
 * @returns {Promise<{ok: boolean, data?: Array, error?: string}>}
 */
export async function listNotebooks() {
  return await api.get('/notebooks');
}

/**
 * Get a specific notebook by ID.
 * @param {string} notebookId
 * @returns {Promise<{ok: boolean, data?: Object, error?: string}>}
 */
export async function getNotebook(notebookId) {
  return await api.get(`/notebooks/${notebookId}`);
}

/**
 * Create a new notebook.
 * @param {string} name
 * @param {string} description
 * @param {string} color
 * @param {string} icon
 * @returns {Promise<{ok: boolean, data?: Object, error?: string}>}
 */
export async function createNotebook(name, description = '', color = '#7c6bf5', icon = 'book-open') {
  return await api.post('/notebooks', {
    name,
    description,
    color,
    icon
  });
}

/**
 * Delete a notebook.
 * @param {string} notebookId
 * @returns {Promise<{ok: boolean, data?: Object, error?: string}>}
 */
export async function deleteNotebook(notebookId) {
  return await api.delete(`/notebooks/${notebookId}`);
}
