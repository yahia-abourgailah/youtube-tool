import { useEffect, useState } from 'react';
import { getChunks, reprocessChunks } from '../api';
import { Play, Search, RefreshCw, Scissors } from 'lucide-react';

const Chunks = () => {
    const [chunks, setChunks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [playingId, setPlayingId] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalItems, setTotalItems] = useState(0);
    const [refining, setRefining] = useState(false);
    const pageSize = 20;

    useEffect(() => {
        loadChunks();
    }, [page]);

    const loadChunks = () => {
        setLoading(true);
        getChunks({ page, size: pageSize }).then(data => {
            setChunks(data.items);
            setTotalPages(data.pages);
            setTotalItems(data.total);
        }).finally(() => setLoading(false));
    };

    const handleRefine = async () => {
        if (!confirm('This will find any chunks longer than your current settings and split them into smaller pieces. Continue?')) return;
        setRefining(true);
        try {
            await reprocessChunks();
            alert('Maintenance task started! You can track progress in the Dashboard.');
        } catch (err: any) {
            alert('Failed to start refinement: ' + err.message);
        } finally {
            setRefining(false);
        }
    };

    const playAudio = (id: string) => {
        if (playingId === id) {
            setPlayingId(null);
            return;
        }
        setPlayingId(id);
        const audio = new Audio(`/api/chunks/${id}/audio`);
        audio.play();
        audio.onended = () => setPlayingId(null);
    };

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <h2 style={{ margin: 0 }}>Audio Chunks</h2>
                <button
                    className="btn btn-primary"
                    onClick={handleRefine}
                    disabled={refining}
                    title="Find and split chunks that are too long"
                >
                    {refining ? <RefreshCw className="animate-spin" size={18} /> : <Scissors size={18} />}
                    {refining ? ' Starting...' : ' Refine Lengthy Chunks'}
                </button>
            </div>

            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <div style={{ flex: 1, position: 'relative' }}>
                        <Search size={18} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input
                            type="text"
                            placeholder="Search by transcript or video ID..."
                            style={{ width: '100%', padding: '0.6rem 1rem 0.6rem 3rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--bg-accent)', color: 'white' }}
                        />
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
                {loading ? <p>Loading chunks...</p> : chunks.map(chunk => (
                    <div key={chunk.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            <div
                                onClick={() => playAudio(chunk.chunk_id)}
                                style={{
                                    width: '40px',
                                    height: '40px',
                                    borderRadius: '50%',
                                    background: playingId === chunk.chunk_id ? 'var(--accent-primary)' : 'var(--bg-accent)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer'
                                }}
                            >
                                {playingId === chunk.chunk_id ? <div className="playing-bars" /> : <Play size={18} fill="white" />}
                            </div>
                            <div>
                                <div style={{ fontWeight: '600', fontSize: '0.9rem' }}>{chunk.chunk_id}</div>
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{chunk.duration.toFixed(2)}s</div>
                            </div>
                        </div>
                        <div style={{
                            backgroundColor: 'var(--bg-primary)',
                            padding: '0.8rem',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.85rem',
                            color: 'var(--text-primary)',
                            direction: 'rtl',
                            fontFamily: 'serif'
                        }}>
                            {chunk.transcript_text}
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                <div>Total: {totalItems} chunks</div>
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
        </div>
    );
};

export default Chunks;
