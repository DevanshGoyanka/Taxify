import axiosInstance from './axiosInstance';

export const panApi = {
  validate: async (pan: string) => {
    const { data } = await axiosInstance.get(`/pan/${pan}/validate`);
    return data as { pan: string; valid: boolean; message?: string };
  },
  analyze: async (pan: string) => {
    const { data } = await axiosInstance.get(`/pan/${pan}/analyze`);
    return data as {
      pan: string; valid: boolean; entityType: string;
      entityDescription: string; isIndividualOrHUF: boolean;
      eligibleITRForms: string[]; warnings: string[];
    };
  },
};
