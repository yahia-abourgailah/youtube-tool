import { useEffect, useState } from 'react';
import { getChunkStats } from '../api';
import { BarChart3, Clock, Hash, Maximize2, Minimize2, TrendingUp } from 'lucide-react';

const Statistics = () => {
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        getChunkStats().then(setStats).finally(() => setLoading(false));
    }, []);

    if (loading) return <div className="card">Loading statistics...</div>;
    if (!stats) return <div className="card">No data available.</div>;

    const formatDuration = (seconds: number) => {
        if (seconds < 60) return `${seconds.toFixed(2)}s`;
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}m ${secs.toFixed(0)}s`;
    };

    const statCards = [
        { title: 'Total Chunks', value: stats.count.toLocaleString(), icon: Hash, color: '#3B82F6' },
        { title: 'Total Duration', value: formatDuration(stats.total_duration), icon: TrendingUp, color: '#10B981' },
        { title: 'Average Size', value: `${stats.avg_duration.toFixed(2)}s`, icon: BarChart3, color: '#8B5CF6' },
        { title: 'Smallest Chunk', value: `${stats.min_duration.toFixed(2)}s`, icon: Minimize2, color: '#F59E0B' },
        { title: 'Largest Chunk', value: `${stats.max_duration.toFixed(2)}s`, icon: Maximize2, color: '#EF4444' },
    ];

    return (
        <div>
            <h2 style={{ marginBottom: '2rem' }}>Dataset Statistics</h2>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '3rem' }}>
                {statCards.map((card, i) => (
                    <div key={i} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{card.title}</span>
                            <card.icon size={20} style={{ color: card.color }} />
                        </div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{card.value}</div>
                    </div>
                ))}
            </div>

            <div className="card" style={{ maxWidth: '600px' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem' }}>
                    <Clock size={20} style={{ color: 'var(--accent-primary)' }} />
                    Duration Percentiles
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <div style={{ fontWeight: '600' }}>90% Percentile</div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>90% of chunks are shorter than this</div>
                        </div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: 'var(--accent-primary)' }}>
                            {stats.p90_duration.toFixed(2)}s
                        </div>
                    </div>

                    <div style={{ height: '1px', background: 'var(--border)' }} />

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                            <div style={{ fontWeight: '600' }}>95% Percentile</div>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>95% of chunks are shorter than this</div>
                        </div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: 'var(--accent-primary)' }}>
                            {stats.p95_duration.toFixed(2)}s
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Statistics;
