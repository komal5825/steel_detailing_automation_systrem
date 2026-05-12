import client from './client';

export const projectsApi = {
  list: () => client.get('/projects/'),

  create: (data) => client.post('/projects/', data),

  getOne: (uuid) => client.get(`/projects/${uuid}`),

  uploadFiles: (uuid, formData, config = {}) =>
    client.post(`/projects/${uuid}/files`, formData, {
      timeout: 120000,
      ...config
    }),


  getFiles: (uuid) => client.get(`/projects/${uuid}/files`),

  deleteFile: (uuid, fileUuid) => client.delete(`/projects/${uuid}/files/${fileUuid}`),
};
