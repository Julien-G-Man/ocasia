import djangoApi from './api';

export const dashboardService = {
  // User stats
  getStats: async () => {
    const res = await djangoApi.get('/dashboard/stats/');
    return res.data;
  },

  getQuizFeedbackSummary: async (source = 'quiz_results') => {
    const res = await djangoApi.get(`/dashboard/quiz-feedback/?source=${encodeURIComponent(source)}`);
    return res.data;
  },

  submitQuizFeedback: async ({ rating, source = 'quiz_results' }) => {
    const res = await djangoApi.post('/dashboard/quiz-feedback/', { rating, source });
    return res.data;
  },

  // History
  getQuizHistory: async () => {
    const res = await djangoApi.get('/quiz/history/');
    return res.data.history;
  },

  getQuizReplay: async (sessionId) => {
    const res = await djangoApi.get(`/quiz/sessions/${sessionId}/`);
    return res.data.quiz_data;
  },

  getFlashcardHistory: async () => {
    const res = await djangoApi.get('/flashcards/history/');
    return res.data.history;
  },

  getClashHistory: async () => {
    const res = await djangoApi.get('/clash/my/');
    return res.data.clashes;
  },

  getChatHistory: async () => {
    const res = await djangoApi.get('/tutor/sessions/');
    return res.data.history;
  },

  // Admin
  getAdminStats: async () => {
    const res = await djangoApi.get('/dashboard/admin/stats/');
    return res.data;
  },

  getAdminQuizFeedback: async (limit = 100) => {
    const res = await djangoApi.get(`/dashboard/admin/quiz-feedback/?limit=${limit}`);
    return res.data;
  },
  
  getAdminUsageTrends: async (days = 14) => {
    const res = await djangoApi.get(`/dashboard/admin/usage-trends/?days=${days}`);
    return res.data;
  },

  getAdminActivity: async ({ period = 'day', limit = 50, offset = 0, customDays } = {}) => {
    const params = new URLSearchParams();
    params.set('period', period);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (customDays != null) params.set('custom_days', String(customDays));

    const res = await djangoApi.get(`/dashboard/admin/activity/?${params.toString()}`);
    return res.data;
  },

  getAdminAnonymousUsage: async (limit = 200) => {
    const res = await djangoApi.get(`/dashboard/admin/anonymous-usage/?limit=${limit}`);
    return res.data;
  },

  getAdminUsers: async () => {
    const res = await djangoApi.get('/dashboard/admin/users/');
    return res.data.users;
  },

  getAdminUserDetails: async (userId) => {
    const res = await djangoApi.get(`/dashboard/admin/users/${userId}/`);
    return res.data;
  },

  removeUser: async (userId) => {
    const res = await djangoApi.delete(`/dashboard/admin/users/${userId}/`);
    return res.data;
  },

  // System Settings
  getSystemSettings: async () => {
    const res = await djangoApi.get('/dashboard/admin/settings/');
    return res.data;
  },

  updateSystemSettings: async (settingsData) => {
    const res = await djangoApi.put('/dashboard/admin/settings/', settingsData);
    return res.data;
  },
};
