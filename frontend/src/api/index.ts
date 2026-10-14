import axios from 'axios';

const api = axios.create({
    baseURL: '/api',
});

export const getStats = () => api.get('/stats').then(res => res.data);

export const getChannels = () => api.get('/channels/').then(res => res.data);
export const createChannel = (url: string) => api.post('/channels/', { url }).then(res => res.data);
export const uploadChannelsFile = (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/channels/upload', formData).then(res => res.data);
};
export const triggerChannelProcess = (id: number) => api.post(`/channels/${id}/process`).then(res => res.data);
export const stopChannelProcess = (id: number) => api.post(`/channels/${id}/stop`).then(res => res.data);
export const resetChannel = (id: number) => api.post(`/channels/${id}/reset`).then(res => res.data);

export const getVideos = (params?: any) => api.get('/videos/', { params }).then(res => res.data);
export const retryVideo = (id: number) => api.post(`/videos/${id}/retry`).then(res => res.data);
export const retryAllVideos = () => api.post('/videos/retry-all').then(res => res.data);
export const retryFailedVideos = () => api.post('/videos/retry-failed').then(res => res.data);
export const cleanupStorage = () => api.post('/videos/cleanup').then(res => res.data);
export const stopVideoTask = (id: number) => api.post(`/videos/${id}/stop`).then(res => res.data);
export const resetVideo = (id: number) => api.post(`/videos/${id}/reset`).then(res => res.data);
export const refineVideoVad = (id: number) => api.post(`/videos/${id}/refine-vad`).then(res => res.data);

export const getChunks = (params?: any) => api.get('/chunks/', { params }).then(res => res.data);
export const reprocessChunks = () => api.post('/chunks/reprocess-lengthy').then(res => res.data);
export const getChunkStats = () => api.get('/chunks/stats').then(res => res.data);
export const updateChunkTranscript = (chunkId: string, transcript_text: string) => api.put(`/chunks/${chunkId}/transcript`, { transcript_text }).then(res => res.data);
export const deleteChunk = (chunkId: string) => api.delete(`/chunks/${chunkId}`).then(res => res.data);
export const trimChunk = (chunkId: string, trim_start: number, trim_end: number) =>
    api.put(`/chunks/${chunkId}/trim`, { trim_start, trim_end }).then(res => res.data);

export const getJobs = () => api.get('/jobs/').then(res => res.data);
export const getVideoLogs = (id: number) => api.get(`/videos/${id}/logs`).then(res => res.data);

export const getSettings = () => api.get('/settings/').then(res => res.data);
export const updateSettings = (data: any) => api.post('/settings/', data).then(res => res.data);

export const triggerExport = (data?: any) => api.post('/export/', data).then(res => res.data);

export const triggerTranscription = (data: any) => api.post('/transcribe/', data).then(res => res.data);
export const transcribeAllUntranscribed = () => api.post('/transcribe/all-untranscribed').then(res => res.data);

export default api;
