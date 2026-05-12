import client from './client';

export const stagesApi = {
  getStatus: (uuid) => client.get(`/stages/${uuid}/status`),

  getPipelineStatus: (uuid) => client.get(`/stages/${uuid}/pipeline/status`),

  runPipeline: (uuid, fromStage = null) =>
    client.post(`/stages/${uuid}/pipeline/run`, fromStage ? { from_stage: fromStage } : {}),

  runStage: (uuid, stageCode) =>
    client.post(`/stages/${uuid}/pipeline/run/${stageCode}`),

  getDependencyReadiness: () => client.get('/stages/dependencies/readiness'),

  resetIntake: (uuid) => client.post(`/stages/${uuid}/reset-intake`),

  getFields: (uuid, stageCode = null) =>
    client.get(`/stages/${uuid}/fields${stageCode ? `?stage_code=${stageCode}` : ''}`),

  overrideFields: (uuid, overrides) =>
    client.post(`/stages/${uuid}/fields/override`, overrides),

  approveStage: (uuid, stageCode) =>
    client.post(`/stages/${uuid}/approve?stage_code=${stageCode}`),

  getCheckpoints: (uuid) => client.get(`/stages/${uuid}/checkpoints`),

  getExecutionLogs: (uuid, limit = 200) => client.get(`/stages/${uuid}/execution-logs?limit=${limit}`),
};
