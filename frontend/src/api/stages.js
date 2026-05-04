import client from './client';

export const stagesApi = {
  getStatus: (uuid) => client.get(`/stages/${uuid}/status`),

  getPipelineStatus: (uuid) => client.get(`/stages/${uuid}/pipeline/status`),

  runPipeline: (uuid, fromStage = null) =>
    client.post(`/stages/${uuid}/pipeline/run`, fromStage ? { from_stage: fromStage } : {}),

  runStage: (uuid, stageCode) =>
    client.post(`/stages/${uuid}/pipeline/run/${stageCode}`),

  getDependencyReadiness: () => client.get('/stages/dependencies/readiness'),
};
