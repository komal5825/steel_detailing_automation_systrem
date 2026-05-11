import client from './client';

export const reportsApi = {
  generateDaily: (projectId, reportDate) => {
    const params = reportDate ? { report_date: reportDate } : {};
    return client.post(`/reports/${projectId}/daily`, null, { params });
  },

  generateWeekly: (projectId, weekDate) => {
    const params = weekDate ? { week_date: weekDate } : {};
    return client.post(`/reports/${projectId}/weekly`, null, { params });
  },

  generateMonthly: (projectId, year, month) => {
    const params = {};
    if (year)  params.year  = year;
    if (month) params.month = month;
    return client.post(`/reports/${projectId}/monthly`, null, { params });
  },

  list: (projectId, reportType) => {
    const params = reportType ? { report_type: reportType } : {};
    return client.get(`/reports/${projectId}/list`, { params });
  },

  get: (projectId, reportId) =>
    client.get(`/reports/${projectId}/${reportId}/detail`),

  signOff: (projectId, reportId, signedBy) =>
    client.post(`/reports/${projectId}/${reportId}/signoff`, null, { params: { signed_by: signedBy } }),

  reject: (projectId, reportId, rejectedBy, reason) =>
    client.post(`/reports/${projectId}/${reportId}/reject`, null, {
      params: { rejected_by: rejectedBy, reason },
    }),

  latestDaily: (projectId) =>
    client.get(`/reports/${projectId}/latest/daily`),

  exportUrl: (projectId, reportId, fmt) =>
    `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'}/reports/${projectId}/${reportId}/export/${fmt}`,

  schedulerStatus: () =>
    client.get('/reports/admin/scheduler/status'),

  triggerNow: (jobType) =>
    client.post(`/reports/admin/trigger/${jobType}`),
};
