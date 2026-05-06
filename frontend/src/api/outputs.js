import client from './client';

const apiRoot = () => {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
  return base.replace(/\/api\/?$/, '');
};

const encodePath = (path) =>
  path
    .split('/')
    .map((part) => encodeURIComponent(part))
    .join('/');

export const outputsApi = {
  listFiles: (uuid) => client.get(`/outputs/${uuid}/files`),

  downloadUrl: (uuid, relativePath) =>
    `${apiRoot()}/api/outputs/${uuid}/download/${encodePath(relativePath)}`,

  reportUrl: (uuid, format) =>
    `${apiRoot()}/api/outputs/${uuid}/report/${format}`,

  getAgentFiles: (uuid, agentCode) =>
    client.get(`/outputs/${uuid}/files/${agentCode}`),

  processedExportUrl: (uuid, filename, format = 'pdf') =>
    `${apiRoot()}/api/outputs/${uuid}/processed/export/${filename}/${format}`,
};

