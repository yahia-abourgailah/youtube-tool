import { useEffect, useState } from 'react';
import { getVideos, retryVideo, stopVideoTask, resetVideo, retryAllVideos, retryFailedVideos, cleanupStorage, getVideoLogs, refineVideoVad } from '../api';
import { RefreshCw, AlertCircle, CheckCircle, Clock, Square, RotateCcw, Play, Trash2, Filter, X, Mic } from 'lucide-react';

interface Video {
    id: number;
    video_id: string;
    title: string;
    status: string;
    duration: number;
    retry_count: number;
    channel?: {
        id: number;
        name: string;
        url: string;
    };
}

const Videos = () => {
    const [videos, setVideos] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalItems, setTotalItems] = useState(0);
    const [sortBy, setSortBy] = useState('created_at');
    const [sortOrder, setSortOrder] = useState('desc');
    const [filterStatus, setFilterStatus] = useState<string>('');
    const [showLogs, setShowLogs] = useState(false);
    const [selectedVideo, setSelectedVideo] = useState<any>(null);
    const [logs, setLogs] = useState<any[]>([]);
    const [search, setSearch] = useState('');
    const pageSize = 20;

    useEffect(() => {
        loadVideos();
        const interval = setInterval(loadVideos, 5000);
        return () => clearInterval(interval);
    }, [page, sortBy, sortOrder, filterStatus, search]);

    const loadVideos = () => {
        getVideos({
            page,
            size: pageSize,
            sort_by: sortBy,
            sort_order: sortOrder,
            status: filterStatus || undefined,
            search: search || undefined
        }).then(data => {
            setVideos(data.items);
            setTotalPages(data.pages);
            setTotalItems(data.total);
        }).finally(() => setLoading(false));
    };

    const handleFilterChange = (status: string) => {
        setFilterStatus(status);
        setPage(1);
    };

    const toggleSort = (column: string) => {
        if (sortBy === column) {
            setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
        } else {
            setSortBy(column);
            setSortOrder('asc');
        }
        setPage(1); // Reset to first page when sorting changes
    };

    const renderSortIcon = (column: string) => {
        if (sortBy !== column) return null;
        return <span>{sortOrder === 'asc' ? ' ↑' : ' ↓'}</span>;
    };

    const handleRetry = async (id: number) => {
        await retryVideo(id);
        loadVideos();
    };

    const handleStop = async (id: number) => {
        try {
            await stopVideoTask(id);
            loadVideos();
        } catch (err: any) {
            console.error(err);
            alert(`Failed to stop video task: ${err.response?.data?.detail || err.message}`);
        }
    };

    const handleReset = async (id: number) => {
        try {
            if (confirm('Are you sure you want to reset this video?')) {
                await resetVideo(id);
                loadVideos();
            }
        } catch (err: any) {
            console.error(err);
            alert(`Failed to reset video: ${err.response?.data?.detail || err.message}`);
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed': return <CheckCircle size={16} color="var(--success)" />;
            case 'failed': return <AlertCircle size={16} color="var(--error)" />;
            case 'processing':
            case 'downloading': return <RefreshCw size={16} className="spin" color="var(--accent-primary)" />;
            default: return <Clock size={16} color="var(--text-secondary)" />;
        }
    };

    const handleRetryFailed = async () => {
        if (confirm('Are you sure you want to retry all failed and pending videos?')) {
            try {
                await retryFailedVideos();
                loadVideos();
            } catch (err: any) {
                console.error(err);
                alert(`Failed to retry subset: ${err.response?.data?.detail || err.message}`);
            }
        }
    };

    const handleCleanup = async () => {
        if (confirm('Are you sure you want to delete source WAV/MP4 files for all completed videos? This will save storage space and only leave the processed chunks.')) {
            try {
                const result = await cleanupStorage();
                alert(result.message);
                loadVideos();
            } catch (err: any) {
                console.error(err);
                alert(`Failed to cleanup storage: ${err.response?.data?.detail || err.message}`);
            }
        }
    };

    const handleRetryAll = async () => {
        if (confirm('Retry all failed and pending videos? Completed videos will not be affected.')) {
            try {
                await retryAllVideos();
                loadVideos();
            } catch (err: any) {
                console.error(err);
                alert(`Failed to rerun all: ${err.response?.data?.detail || err.message}`);
            }
        }
    };

    const handleViewLogs = async (video: Video) => {
        setSelectedVideo(video);
        setShowLogs(true);
        setLogs([]);
        try {
            const data = await getVideoLogs(video.id);
            setLogs(data);
        } catch (err) {
            console.error(err);
        }
    };

    const handleRefineVad = async (id: number) => {
        if (confirm('Run VAD Refinement? This will check all existing chunks for speech and DELETE those that are just noise/silence. This cannot be undone.')) {
            try {
                await refineVideoVad(id);
                loadVideos();
                alert('VAD refinement task started. Check logs for progress.');
            } catch (err: any) {
                console.error(err);
                alert(`Failed to start VAD refinement: ${err.response?.data?.detail || err.message}`);
            }
        }
    };

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
                    <h2>Video Library</h2>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            background: 'var(--bg-accent)',
                            padding: '0.4rem 0.8rem',
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--border)',
                            minWidth: '300px'
                        }}>
                            <Filter size={16} color="var(--text-secondary)" />
                            <input
                                type="text"
                                placeholder="Search by ID, YouTube ID, or Title..."
                                value={search}
                                onChange={(e) => {
                                    setSearch(e.target.value);
                                    setPage(1);
                                }}
                                style={{
                                    background: 'none',
                                    color: 'var(--text-primary)',
                                    border: 'none',
                                    outline: 'none',
                                    flex: 1,
                                    fontSize: '0.9rem'
                                }}
                            />
                            {search && (
                                <button
                                    onClick={() => setSearch('')}
                                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', color: 'var(--text-secondary)' }}
                                >
                                    <X size={14} />
                                </button>
                            )}
                        </div>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <div style={{ marginRight: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-accent)', padding: '0.4rem 0.8rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                        <Filter size={16} color="var(--text-secondary)" />
                        <select
                            value={filterStatus}
                            onChange={(e) => handleFilterChange(e.target.value)}
                            style={{ background: 'none', color: 'var(--text-primary)', border: 'none', outline: 'none', cursor: 'pointer' }}
                        >
                            <option value="">All Statuses</option>
                            <option value="pending">Pending</option>
                            <option value="downloading">Downloading</option>
                            <option value="processing">Processing</option>
                            <option value="completed">Completed</option>
                            <option value="failed">Failed</option>
                        </select>
                    </div>
                    <button className="btn" onClick={handleCleanup} style={{ color: 'var(--error)', background: 'var(--bg-accent)', border: '1px solid var(--border)' }}>
                        <Trash2 size={18} style={{ marginRight: '0.5rem' }} /> Cleanup Storage
                    </button>
                    <button className="btn" onClick={handleRetryFailed} style={{ background: 'var(--bg-accent)', border: '1px solid var(--border)' }}>
                        <Play size={18} style={{ marginRight: '0.5rem' }} /> Retry Failed/Pending
                    </button>
                    <button className="btn btn-primary" onClick={handleRetryAll}>
                        <RefreshCw size={18} style={{ marginRight: '0.5rem' }} /> Rerun All
                    </button>
                </div>
            </div>

            <div className="card">
                {loading && videos.length === 0 ? <p>Loading videos...</p> : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                                <th style={{ padding: '1rem 0', cursor: 'pointer' }} onClick={() => toggleSort('video_id')}>
                                    Video ID {renderSortIcon('video_id')}
                                </th>
                                <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('title')}>
                                    Title {renderSortIcon('title')}
                                </th>
                                <th>Channel</th>
                                <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('status')}>
                                    Status {renderSortIcon('status')}
                                </th>
                                <th>Progress</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {videos.map((video: Video) => (
                                <tr key={video.id} style={{ borderBottom: '1px solid var(--border)' }}>
                                    <td style={{ padding: '1rem 0', fontFamily: 'monospace', fontSize: '0.8rem' }}>{video.video_id}</td>
                                    <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{video.title}</td>
                                    <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                                        {video.channel?.name || 'Unknown'}
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            {getStatusIcon(video.status)}
                                            <span style={{ fontSize: '0.9rem' }}>{video.status}</span>
                                        </div>
                                    </td>
                                    <td>
                                        <div style={{ width: '100px', height: '6px', background: 'var(--bg-accent)', borderRadius: '3px' }}>
                                            <div style={{
                                                width: video.status === 'completed' ? '100%' : (video.status === 'processing' ? '50%' : '10%'),
                                                height: '100%',
                                                background: 'var(--accent-primary)',
                                                borderRadius: '3px'
                                            }}></div>
                                        </div>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                            {(video.status === 'processing' || video.status === 'downloading') ? (
                                                <button className="btn" style={{ padding: '0.3rem', color: 'var(--danger)' }} onClick={() => handleStop(video.id)} title="Stop">
                                                    <Square size={16} />
                                                </button>
                                            ) : (
                                                <button className="btn" style={{ padding: '0.3rem', color: 'var(--accent-primary)' }} onClick={() => handleRetry(video.id)} title="Start/Retry">
                                                    <RefreshCw size={16} />
                                                </button>
                                            )}

                                            {(video.status === 'completed' || video.status === 'failed') && (
                                                <button className="btn" style={{ padding: '0.3rem' }} onClick={() => handleReset(video.id)} title="Reset">
                                                    <RotateCcw size={16} />
                                                </button>
                                            )}

                                            {video.status === 'completed' && (
                                                <button className="btn" style={{ padding: '0.3rem', color: 'var(--text-primary)' }} onClick={() => handleRefineVad(video.id)} title="Refine VAD (Remove Noise Chunks)">
                                                    <Mic size={16} />
                                                </button>
                                            )}

                                            <button className="btn" style={{ padding: '0.3rem' }} title="View Logs" onClick={() => handleViewLogs(video)}>
                                                <AlertCircle size={16} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                <div>Total: {totalItems} videos</div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <button
                        className="btn"
                        disabled={page === 1}
                        onClick={() => setPage(p => p - 1)}
                        style={{ padding: '0.4rem 0.8rem' }}
                    >
                        Previous
                    </button>
                    <span>Page {page} of {totalPages}</span>
                    <button
                        className="btn"
                        disabled={page === totalPages}
                        onClick={() => setPage(p => p + 1)}
                        style={{ padding: '0.4rem 0.8rem' }}
                    >
                        Next
                    </button>
                </div>
            </div>

            {showLogs && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(0,0,0,0.7)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000,
                    backdropFilter: 'blur(4px)'
                }}>
                    <div className="card" style={{
                        width: '90%',
                        maxWidth: '600px',
                        maxHeight: '80vh',
                        display: 'flex',
                        flexDirection: 'column',
                        padding: '1.5rem',
                        position: 'relative'
                    }}>
                        <button
                            onClick={() => setShowLogs(false)}
                            style={{
                                position: 'absolute',
                                top: '1rem',
                                right: '1rem',
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                color: 'var(--text-secondary)'
                            }}
                        >
                            <X size={24} />
                        </button>

                        <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            Activity Log: <span style={{ color: 'var(--accent-primary)', fontSize: '1rem' }}>{selectedVideo?.title}</span>
                        </h3>

                        <div style={{
                            overflowY: 'auto',
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0.8rem',
                            marginTop: '0.5rem'
                        }}>
                            {logs.length === 0 ? (
                                <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>No detailed logs found for this video.</p>
                            ) : (
                                logs.map((log: any) => (
                                    <div key={log.id} style={{
                                        padding: '1rem',
                                        background: 'var(--bg-accent)',
                                        borderRadius: 'var(--radius-md)',
                                        border: `1px solid ${log.level === 'error' ? 'var(--error)' : (log.level === 'warning' ? 'var(--warning)' : 'var(--border)')}`,
                                        opacity: 0.9
                                    }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                                            <span style={{
                                                fontSize: '0.7rem',
                                                fontWeight: 700,
                                                color: log.level === 'error' ? 'var(--error)' : (log.level === 'warning' ? 'var(--warning)' : 'var(--text-secondary)'),
                                                textTransform: 'uppercase'
                                            }}>
                                                {log.level}
                                            </span>
                                            <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                                {new Date(log.created_at).toLocaleString()}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: '0.9rem', lineHeight: 1.4 }}>{log.message}</div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Videos;
