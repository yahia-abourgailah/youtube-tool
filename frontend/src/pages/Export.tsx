import { useEffect, useState } from 'react';
import { triggerExport, getJobs, getChannels, apiUrl } from '../api';
import { Download, Share2, CheckCircle, RefreshCw, Layers, Edit3 } from 'lucide-react';

const Export = () => {
    const [jobs, setJobs] = useState<any[]>([]);
    const [channels, setChannels] = useState<any[]>([]);
    const [selectedChannels, setSelectedChannels] = useState<number[]>([]);
    const [customNames, setCustomNames] = useState<{ [key: number]: string }>({});
    const [repoId, setRepoId] = useState('');
    const [token, setToken] = useState('');
    const [isPrivate, setIsPrivate] = useState(true);
    const [split, setSplit] = useState(false);
    const [valRatio, setValRatio] = useState(0.05);
    const [testRatio, setTestRatio] = useState(0.05);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadJobs();
        loadChannels();
        const interval = setInterval(loadJobs, 5000);
        return () => clearInterval(interval);
    }, []);

    const loadJobs = () => {
        getJobs().then(data => {
            setJobs(data.filter((j: any) => j.job_type === 'export'));
        });
    };

    const loadChannels = () => {
        getChannels().then(data => {
            setChannels(data);
            // Default to selecting all channels
            setSelectedChannels(data.map((c: any) => c.id));
        });
    };

    const toggleChannel = (id: number) => {
        if (selectedChannels.includes(id)) {
            setSelectedChannels(selectedChannels.filter(c => c !== id));
        } else {
            setSelectedChannels([...selectedChannels, id]);
        }
    };

    const handleNameChange = (id: number, name: string) => {
        setCustomNames({
            ...customNames,
            [id]: name
        });
    };

    const handleSelectAll = () => {
        if (selectedChannels.length === channels.length) {
            setSelectedChannels([]);
        } else {
            setSelectedChannels(channels.map(c => c.id));
        }
    };

    const handleExport = async () => {
        if (selectedChannels.length === 0) {
            alert("Please select at least one channel to export.");
            return;
        }

        setLoading(true);
        try {
            // Convert customNames keys to strings for API
            const channelNamesStr: { [key: string]: string } = {};
            selectedChannels.forEach(id => {
                if (customNames[id]) {
                    channelNamesStr[id.toString()] = customNames[id];
                }
            });

            await triggerExport({
                repo_id: repoId,
                hf_token: token,
                private: isPrivate,
                channel_ids: selectedChannels,
                channel_names: channelNamesStr,
                split,
                val_ratio: valRatio,
                test_ratio: testRatio
            });
            loadJobs();
            alert("Export job started!");
        } catch (err: any) {
            console.error(err);
            alert("Failed to start export: " + (err.response?.data?.detail || err.message));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div>
            <h2 style={{ marginBottom: '2rem' }}>HuggingFace Export</h2>

            <div className="stats-grid">
                <div className="card">
                    <h3 style={{ marginBottom: '1.5rem' }}>Dataset Configuration</h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>

                        {/* Channel Selection */}
                        <div style={{ marginBottom: '1rem', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                                <label style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Layers size={16} /> Select Channels ({selectedChannels.length}/{channels.length})
                                </label>
                                <button
                                    className="btn"
                                    style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', height: 'auto' }}
                                    onClick={handleSelectAll}
                                >
                                    {selectedChannels.length === channels.length ? 'Deselect All' : 'Select All'}
                                </button>
                            </div>
                            <div style={{
                                maxHeight: '150px',
                                overflowY: 'auto',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.5rem',
                                paddingRight: '0.5rem'
                            }}>
                                {channels.map(channel => (
                                    <div key={channel.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'space-between' }}>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem', flex: 1, overflow: 'hidden' }}>
                                            <input
                                                type="checkbox"
                                                checked={selectedChannels.includes(channel.id)}
                                                onChange={() => toggleChannel(channel.id)}
                                            />
                                            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                {channel.name || channel.url}
                                            </span>
                                        </label>

                                        {/* Custom Name Input */}
                                        {selectedChannels.includes(channel.id) && (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                                <Edit3 size={14} color="var(--text-secondary)" />
                                                <input
                                                    type="text"
                                                    placeholder="Subset Name (optional)"
                                                    value={customNames[channel.id] || ''}
                                                    onChange={(e) => handleNameChange(channel.id, e.target.value)}
                                                    onClick={(e) => e.stopPropagation()}
                                                    style={{
                                                        padding: '0.2rem 0.4rem',
                                                        fontSize: '0.8rem',
                                                        borderRadius: 'var(--radius-sm)',
                                                        border: '1px solid var(--border)',
                                                        background: 'var(--bg-main)',
                                                        color: 'white',
                                                        width: '140px'
                                                    }}
                                                />
                                            </div>
                                        )}
                                    </div>
                                ))}
                                {channels.length === 0 && <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>No channels found.</span>}
                            </div>
                        </div>

                        <input
                            type="text"
                            placeholder="Repo ID (e.g., username/egyptian-asr)"
                            value={repoId}
                            onChange={(e) => setRepoId(e.target.value)}
                            style={{ width: '100%', padding: '0.6rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--bg-accent)', color: 'white' }}
                        />
                        <input
                            type="password"
                            placeholder="HuggingFace Token (optional)"
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            style={{ width: '100%', padding: '0.6rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--bg-accent)', color: 'white' }}
                        />
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                            <input
                                type="checkbox"
                                checked={isPrivate}
                                onChange={(e) => setIsPrivate(e.target.checked)}
                            />
                            Private Dataset
                        </label>

                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.9rem' }}>
                            <input
                                type="checkbox"
                                checked={split}
                                onChange={(e) => setSplit(e.target.checked)}
                            />
                            Create train / validation / test splits
                        </label>
                        {split && (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    Validation ratio
                                    <input
                                        type="number"
                                        min="0"
                                        max="0.5"
                                        step="0.01"
                                        value={valRatio}
                                        onChange={(e) => setValRatio(parseFloat(e.target.value) || 0)}
                                        style={{ width: '100%', marginTop: '0.3rem', padding: '0.4rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--bg-accent)', color: 'white' }}
                                    />
                                </label>
                                <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    Test ratio
                                    <input
                                        type="number"
                                        min="0"
                                        max="0.5"
                                        step="0.01"
                                        value={testRatio}
                                        onChange={(e) => setTestRatio(parseFloat(e.target.value) || 0)}
                                        style={{ width: '100%', marginTop: '0.3rem', padding: '0.4rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--bg-accent)', color: 'white' }}
                                    />
                                </label>
                            </div>
                        )}
                        <button className="btn btn-primary" onClick={handleExport} disabled={loading || selectedChannels.length === 0}>
                            {loading ? <RefreshCw size={18} className="spin" /> : <Share2 size={18} />}
                            Generate Dataset
                        </button>
                    </div>
                </div>

                <div className="card">
                    <h3 style={{ marginBottom: '1.5rem' }}>Local Download</h3>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.9rem' }}>
                        Generate the dataset locally and download the Parquet files (plus manifest).
                        A HuggingFace token is only needed to also push to the Hub.
                    </p>
                    <a href={apiUrl('/api/export/download')} className="btn btn-primary" style={{ width: 'fit-content' }}>
                        <Download size={18} /> Download Dataset
                    </a>
                    <a href={apiUrl('/api/export/csv')} className="btn" style={{ width: 'fit-content', marginTop: '0.5rem' }}>
                        <Download size={18} /> Download Transcripts CSV
                    </a>
                </div>
            </div>

            <div className="card">
                <h3 style={{ marginBottom: '1rem' }}>Export History</h3>
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
    );
};

export default Export;
