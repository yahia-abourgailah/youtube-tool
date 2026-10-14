import { useEffect, useState } from 'react';
import { triggerTranscription, transcribeAllUntranscribed, getJobs, getChannels, getVideos } from '../api';
import { Mic, CheckCircle, RefreshCw, Layers, Film, Search, Zap } from 'lucide-react';

type Mode = 'channel' | 'video';

const Transcription = () => {
    const [jobs, setJobs] = useState<any[]>([]);
    const [channels, setChannels] = useState<any[]>([]);
    const [selectedChannels, setSelectedChannels] = useState<number[]>([]);
    const [forceRetranscribe, setForceRetranscribe] = useState(false);
    const [loading, setLoading] = useState(false);

    const [mode, setMode] = useState<Mode>('channel');
    const [videos, setVideos] = useState<any[]>([]);
    const [selectedVideos, setSelectedVideos] = useState<number[]>([]);
    const [videoSearch, setVideoSearch] = useState('');
    const [videosLoading, setVideosLoading] = useState(false);

    useEffect(() => {
        loadJobs();
        loadChannels();
        const interval = setInterval(loadJobs, 5000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (mode === 'video' && videos.length === 0) {
            loadVideos();
        }
    }, [mode]);

    const loadJobs = () => {
        getJobs().then(data => {
            setJobs(data.filter((j: any) => j.job_type === 'transcription'));
        });
    };

    const loadChannels = () => {
        getChannels().then(data => {
            setChannels(data);
        });
    };

    const loadVideos = () => {
        setVideosLoading(true);
        getVideos({ size: 1000 }).then(data => {
            setVideos(data.items || []);
        }).finally(() => setVideosLoading(false));
    };

    const toggleChannel = (id: number) => {
        if (selectedChannels.includes(id)) {
            setSelectedChannels(selectedChannels.filter(c => c !== id));
        } else {
            setSelectedChannels([...selectedChannels, id]);
        }
    };

    const toggleVideo = (id: number) => {
        if (selectedVideos.includes(id)) {
            setSelectedVideos(selectedVideos.filter(v => v !== id));
        } else {
            setSelectedVideos([...selectedVideos, id]);
        }
    };

    const handleSelectAllChannels = () => {
        if (selectedChannels.length === channels.length) {
            setSelectedChannels([]);
        } else {
            setSelectedChannels(channels.map(c => c.id));
        }
    };

    const filteredVideos = videos.filter(v => {
        const query = videoSearch.toLowerCase();
        return (v.title || '').toLowerCase().includes(query) || (v.video_id || '').toLowerCase().includes(query);
    });

    const handleSelectAllVideos = () => {
        const filteredIds = filteredVideos.map(v => v.id);
        const allSelected = filteredIds.every(id => selectedVideos.includes(id));
        if (allSelected) {
            setSelectedVideos(selectedVideos.filter(id => !filteredIds.includes(id)));
        } else {
            setSelectedVideos([...new Set([...selectedVideos, ...filteredIds])]);
        }
    };

    const handleTranscribe = async () => {
        if (mode === 'channel' && selectedChannels.length === 0) {
            alert("Please select at least one channel to transcribe.");
            return;
        }
        if (mode === 'video' && selectedVideos.length === 0) {
            alert("Please select at least one video to transcribe.");
            return;
        }

        setLoading(true);
        try {
            const payload = mode === 'video'
                ? { video_ids: selectedVideos, force_retranscribe: forceRetranscribe }
                : { channel_ids: selectedChannels, force_retranscribe: forceRetranscribe };
            await triggerTranscription(payload);
            loadJobs();
            alert("Transcription job started!");
        } catch (err: any) {
            console.error(err);
            alert("Failed to start transcription: " + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    const isDisabled = loading || (mode === 'channel' ? selectedChannels.length === 0 : selectedVideos.length === 0);

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
                <h2 style={{ margin: 0 }}>Gemini Transcription</h2>
                <button
                    className="btn btn-primary"
                    disabled={loading}
                    onClick={async () => {
                        setLoading(true);
                        try {
                            const res = await transcribeAllUntranscribed();
                            loadJobs();
                            alert(res.message);
                        } catch (err: any) {
                            alert('Failed: ' + (err.response?.data?.detail || err.message));
                        } finally {
                            setLoading(false);
                        }
                    }}
                >
                    <Zap size={18} /> Transcribe All Untranscribed
                </button>
            </div>

            <div className="stats-grid">
                <div className="card">
                    <h3 style={{ marginBottom: '1.5rem' }}>Transcription Configuration</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

                        {/* Mode Toggle */}
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                                className={`btn ${mode === 'channel' ? 'btn-primary' : ''}`}
                                onClick={() => setMode('channel')}
                                style={{ flex: 1 }}
                            >
                                <Layers size={16} /> By Channel
                            </button>
                            <button
                                className={`btn ${mode === 'video' ? 'btn-primary' : ''}`}
                                onClick={() => setMode('video')}
                                style={{ flex: 1 }}
                            >
                                <Film size={16} /> By Video
                            </button>
                        </div>

                        {/* Channel Selection */}
                        {mode === 'channel' && (
                            <div style={{ marginBottom: '1rem', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                                    <label style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <Layers size={16} /> Select Channels ({selectedChannels.length}/{channels.length})
                                    </label>
                                    <button
                                        className="btn"
                                        style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', height: 'auto' }}
                                        onClick={handleSelectAllChannels}
                                    >
                                        {selectedChannels.length === channels.length ? 'Deselect All' : 'Select All'}
                                    </button>
                                </div>
                                <div style={{
                                    maxHeight: '250px',
                                    overflowY: 'auto',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '0.5rem',
                                    paddingRight: '0.5rem'
                                }}>
                                    {channels.map(channel => (
                                        <label key={channel.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                                            <input
                                                type="checkbox"
                                                checked={selectedChannels.includes(channel.id)}
                                                onChange={() => toggleChannel(channel.id)}
                                            />
                                            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {channel.name || channel.url}
                                            </span>
                                        </label>
                                    ))}
                                    {channels.length === 0 && <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>No channels found.</span>}
                                </div>
                            </div>
                        )}

                        {/* Video Selection */}
                        {mode === 'video' && (
                            <div style={{ marginBottom: '1rem', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                                    <label style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <Film size={16} /> Select Videos ({selectedVideos.length}/{videos.length})
                                    </label>
                                    <button
                                        className="btn"
                                        style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', height: 'auto' }}
                                        onClick={handleSelectAllVideos}
                                    >
                                        {filteredVideos.length > 0 && filteredVideos.every(v => selectedVideos.includes(v.id)) ? 'Deselect All' : 'Select All'}
                                    </button>
                                </div>
                                {/* Search */}
                                <div style={{ position: 'relative', marginBottom: '0.5rem' }}>
                                    <Search size={14} style={{ position: 'absolute', left: '0.5rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                                    <input
                                        type="text"
                                        placeholder="Search videos by title or ID..."
                                        value={videoSearch}
                                        onChange={e => setVideoSearch(e.target.value)}
                                        style={{
                                            width: '100%',
                                            padding: '0.4rem 0.5rem 0.4rem 1.8rem',
                                            border: '1px solid var(--border)',
                                            borderRadius: 'var(--radius-md)',
                                            fontSize: '0.85rem',
                                            background: 'var(--bg)',
                                            color: 'var(--text)',
                                            boxSizing: 'border-box',
                                        }}
                                    />
                                </div>
                                <div style={{
                                    maxHeight: '300px',
                                    overflowY: 'auto',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '0.5rem',
                                    paddingRight: '0.5rem'
                                }}>
                                    {videosLoading ? (
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>Loading videos...</span>
                                    ) : filteredVideos.length === 0 ? (
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                                            {videos.length === 0 ? 'No videos found.' : 'No videos match your search.'}
                                        </span>
                                    ) : (
                                        filteredVideos.map(video => (
                                            <label key={video.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedVideos.includes(video.id)}
                                                    onChange={() => toggleVideo(video.id)}
                                                />
                                                <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                    {video.title || video.video_id}
                                                </span>
                                                {video.channel?.name && (
                                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', flexShrink: 0 }}>
                                                        [{video.channel.name}]
                                                    </span>
                                                )}
                                            </label>
                                        ))
                                    )}
                                </div>
                            </div>
                        )}

                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                            <input
                                type="checkbox"
                                checked={forceRetranscribe}
                                onChange={(e) => setForceRetranscribe(e.target.checked)}
                            />
                            Force Retranscribe (Overwrite existing)
                        </label>
                        <button className="btn btn-primary" onClick={handleTranscribe} disabled={isDisabled}>
                            {loading ? <RefreshCw size={18} className="spin" /> : <Mic size={18} />}
                            Start Transcription
                        </button>
                    </div>
                </div>

                <div className="card">
                    <h3 style={{ marginBottom: '1rem' }}>Transcription History</h3>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                                <th style={{ padding: '1rem 0' }}>Job ID</th>
                                <th>Status</th>
                                <th>Progress</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {jobs.map(job => (
                                <tr key={job.id} style={{ borderBottom: '1px solid var(--border)' }}>
                                    <td style={{ padding: '1rem 0' }}>#{job.id}</td>
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            {job.status === 'completed' ? <CheckCircle size={16} color="var(--success)" /> : <RefreshCw size={16} className="spin" />}
                                            {job.status}
                                        </div>
                                    </td>
                                    <td>{job.progress}%</td>
                                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{new Date(job.created_at).toLocaleString()}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default Transcription;
