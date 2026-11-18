import { useEffect, useState } from 'react';
import { ShieldCheck, RefreshCw, AlertTriangle, Trash2 } from 'lucide-react';
import { getQaReport, pruneLogs } from '../api';

const QA = () => {
    const [report, setReport] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [pruning, setPruning] = useState(false);

    const load = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await getQaReport();
            setReport(data);
        } catch (err: any) {
            setError(err.response?.data?.detail || err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const handlePrune = async () => {
        if (!confirm('Delete activity logs older than 90 days?')) return;
        setPruning(true);
        try {
            await pruneLogs(90);
            alert('Log pruning started.');
        } catch (err: any) {
            alert(`Failed to prune logs: ${err.response?.data?.detail || err.message}`);
        } finally {
            setPruning(false);
        }
    };

    if (loading) return <div className="card">Scanning dataset...</div>;
    if (error) return <div className="card" style={{ color: 'var(--danger)' }}>Failed to load QA report: {error}</div>;
    if (!report) return null;

    const { summary, issue_counts, issue_labels, issues, duplicates, generated_at } = report;
    const activeIssues = Object.entries(issue_counts as Record<string, number>)
        .filter(([, count]) => count > 0);

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <ShieldCheck size={24} /> Dataset QA
                    </h2>
                    <small style={{ color: 'var(--text-secondary)' }}>
                        Read-only quality scan generated {new Date(generated_at).toLocaleString()}
                    </small>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="btn" onClick={load} disabled={loading}>
                        <RefreshCw size={16} /> Rescan
                    </button>
                    <button className="btn" onClick={handlePrune} disabled={pruning}>
                        <Trash2 size={16} /> {pruning ? 'Pruning...' : 'Prune old logs'}
                    </button>
                </div>
            </div>

            <div className="stats-grid">
                <div className="card">
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Total chunks</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700 }}>{summary.total_chunks}</div>
                </div>
                <div className="card">
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Transcribed</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700 }}>{summary.transcribed_chunks}</div>
                </div>
                <div className="card">
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Untranscribed</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700 }}>{summary.untranscribed_chunks}</div>
                </div>
                <div className="card">
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Missing audio</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: summary.missing_audio_chunks ? 'var(--danger)' : undefined }}>
                        {summary.missing_audio_chunks}
                    </div>
                </div>
                <div className="card">
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Audio hours</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700 }}>{summary.total_duration_hours}</div>
                </div>
                <div className="card">
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Duplicate transcripts</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700 }}>{summary.duplicate_transcripts}</div>
                </div>
            </div>

            <div className="card" style={{ marginTop: '1.5rem' }}>
                <h3 style={{ marginBottom: '1rem' }}>Detected issues</h3>
                {activeIssues.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)' }}>No issues detected.</p>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {activeIssues.map(([code, count]) => (
                            <div key={code}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <AlertTriangle size={16} color="var(--warning, #f59e0b)" />
                                    <strong>{issue_labels[code] || code}</strong>
                                    <span style={{ color: 'var(--text-secondary)' }}>({count})</span>
                                </div>
                                {(issues[code] || []).length > 0 && (
                                    <ul style={{ margin: '0.5rem 0 0 1.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                        {issues[code].slice(0, 3).map((sample: any, index: number) => (
                                            <li key={`${code}-${index}`}>
                                                <code>{sample.chunk_id}</code>
                                                {sample.duration ? ` · ${sample.duration.toFixed(1)}s` : ''}
                                                {sample.transcript ? ` · ${sample.transcript}` : ''}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {duplicates.length > 0 && (
                <div className="card" style={{ marginTop: '1.5rem' }}>
                    <h3 style={{ marginBottom: '1rem' }}>Most repeated transcripts</h3>
                    <ul style={{ marginLeft: '1.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                        {duplicates.slice(0, 10).map((item: any, index: number) => (
                            <li key={index}>
                                ×{item.count} · {item.transcript}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default QA;
