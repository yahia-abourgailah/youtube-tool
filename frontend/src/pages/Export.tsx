import React, { useEffect, useState } from 'react';
import { triggerExport, getJobs } from '../api';
import { Download, Share2, CheckCircle, RefreshCw } from 'lucide-react';

const Export = () => {
    const [jobs, setJobs] = useState<any[]>([]);
    const [repoId, setRepoId] = useState('');
    const [token, setToken] = useState('');
    const [isPrivate, setIsPrivate] = useState(true);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadJobs();
        const interval = setInterval(loadJobs, 5000);
        return () => clearInterval(interval);
    }, []);

    const loadJobs = () => {
        getJobs().then(data => {
            setJobs(data.filter((j: any) => j.job_type === 'export'));
        });
    };

    const handleExport = async () => {
        setLoading(true);
        try {
            await triggerExport({ repo_id: repoId, hf_token: token, private: isPrivate });
            loadJobs();
        } catch (err) {
            console.error(err);
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
                        <button className="btn btn-primary" onClick={handleExport} disabled={loading}>
                            {loading ? <RefreshCw size={18} className="spin" /> : <Share2 size={18} />}
                            Generate & Push to Hub
                        </button>
                    </div>
                </div>

                <div className="card">
                    <h3 style={{ marginBottom: '1.5rem' }}>Local Download</h3>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.9rem' }}>
                        Generate the dataset locally and download it as a Parquet file.
                    </p>
                    <a href="/api/export/download" className="btn btn-primary" style={{ width: 'fit-content' }}>
                        <Download size={18} /> Download Parquet
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
