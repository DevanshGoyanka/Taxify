import axiosInstance from './axiosInstance';

export const dashboardApi = {
  getStats: async (assessmentYear?: string) => {
    const { data } = await axiosInstance.get('/dashboard/stats', {
      params: assessmentYear ? { ay: assessmentYear } : undefined,
    });
    return data as {
      total: number; filed: number; inProgress: number;
      docPending: number; watchList: number; totalMismatches: number; totalNotices: number;
    };
  },
};
