import client from './client';

export const projectsApi = {
  list: () => client.get('/projects/'),

  create: (data) => client.post('/projects/', data),

  getOne: (uuid) => client.get(`/projects/${uuid}`),

  uploadFiles: (uuid, formData) =>
    client.post(`/projects/${uuid}/files`, formData, {
      timeout: 120000,
    }),

  getFiles: (uuid) => client.get(`/projects/${uuid}/files`),
};
