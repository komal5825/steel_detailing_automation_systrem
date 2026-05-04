import client from './client';

export const handoffsApi = {
  getPackage: (uuid) => client.get(`/handoffs/${uuid}`),

  list: (uuid) => client.get(`/handoffs/${uuid}/list`),

  approve: (uuid, handoffId, approvedBy, decision) =>
    client.post(`/handoffs/${uuid}/approve`, {
      handoff_id: handoffId,
      approved_by: approvedBy,
      decision,
    }),
};
