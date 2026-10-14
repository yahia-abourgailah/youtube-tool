import { useEffect, useState, useRef } from 'react';
import { getChunks, reprocessChunks, updateChunkTranscript, deleteChunk } from '../api';
import { Play, Pause, Search, RefreshCw, Scissors, Pencil, Save, X, Trash2 } from 'lucide-react';

const Chunks = () => {
    const [chunks, setChunks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [playingId, setPlayingId] = useState<string | null>(null);
    const [pausedId, setPausedId] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalItems, setTotalItems] = useState(0);
    const [refining, setRefining] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editText, setEditText] = useState('');
    const [saving, setSaving] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [currentTime, setCurrentTime] = useState(0);
    const [audioDuration, setAudioDuration] = useState(0);
    const activeChunkRef = useRef<string | null>(null);
    const audioRef = useRef<HTMLAudioElement>(new Audio());
    const debounceRef = useRef<ReturnType<typeof setTimeout>>();
    const rafRef = useRef<number | null>(null);
    const pageSize = 20;

    useEffect(() => {
        loadChunks();
    }, [page, debouncedSearch]);

    useEffect(() => {
        const audio = audioRef.current;
        audio.preload = 'auto';
        audio.onended = () => {
            setPlayingId(null);
            setPausedId(null);
            setCurrentTime(0);
            setAudioDuration(0);
            activeChunkRef.current = null;
            stopTimeTracking();
        };
        return () => {
            stopTimeTracking();
            audio.pause();
            audio.src = '';
        };
    }, []);

    useEffect(() => {
        clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            setPage(1);
            setDebouncedSearch(searchTerm);
        }, 400);
        return () => clearTimeout(debounceRef.current);
    }, [searchTerm]);

    const loadChunks = () => {
        setLoading(true);
        const params: any = { page, size: pageSize };
        if (debouncedSearch) params.search = debouncedSearch;
        getChunks(params).then(data => {
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

    const stopTimeTracking = () => {
        if (rafRef.current) {
            cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
        }
    };

    const startTimeTracking = () => {
        stopTimeTracking();
        const tick = () => {
            if (audioRef.current) {
                setCurrentTime(audioRef.current.currentTime);
            }
            rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
    };

    const loadAudioForChunk = (id: string): Promise<void> => {
        const audio = audioRef.current;
        const chunk = chunks.find(c => c.chunk_id === id);
        if (activeChunkRef.current === id && audio.src) {
            // Already loaded this chunk — no need to reload
            return Promise.resolve();
        }
        return new Promise((resolve) => {
            audio.pause();
            stopTimeTracking();
            activeChunkRef.current = id;
            setAudioDuration(chunk?.duration || 0);
            audio.src = `/api/chunks/${id}/audio?d=${chunk?.duration || 0}`;
            audio.onloadedmetadata = () => {
                if (audio.duration && isFinite(audio.duration)) {
                    setAudioDuration(audio.duration);
                }
                resolve();
            };
            audio.load();
        });
    };

    const playAudio = async (id: string) => {
        const audio = audioRef.current;

        // Clicking the currently playing chunk → pause it
        if (playingId === id) {
            audio.pause();
            setPlayingId(null);
            setPausedId(id);
            stopTimeTracking();
            return;
        }

        // Paused on same chunk → resume from current position
        if (pausedId === id) {
            audio.play();
            setPlayingId(id);
            setPausedId(null);
            startTimeTracking();
            return;
        }

        // Different chunk or first play — load then play from 0
        await loadAudioForChunk(id);
        audio.currentTime = 0;
        setCurrentTime(0);
        audio.play();
        setPlayingId(id);
        setPausedId(null);
        startTimeTracking();
    };

    const handleSeek = async (chunkId: string, e: React.ChangeEvent<HTMLInputElement>) => {
        const time = parseFloat(e.target.value);
        const audio = audioRef.current;
        setCurrentTime(time);

        // If this chunk is already loaded (playing or paused), seek directly
        if (activeChunkRef.current === chunkId) {
            audio.currentTime = time;
            return;
        }

        // Not loaded — load it first, then seek, leave it paused
        await loadAudioForChunk(chunkId);
        audio.currentTime = time;
        setPausedId(chunkId);
        setPlayingId(null);
    };

    const formatTime = (seconds: number) => {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    const handleDelete = async (chunkId: string) => {
        if (!confirm('Delete this chunk? The audio file and DB record will be permanently removed.')) return;
        try {
            await deleteChunk(chunkId);
            setChunks(prev => prev.filter(c => c.chunk_id !== chunkId));
            setTotalItems(prev => prev - 1);
        } catch (err: any) {
            alert('Failed to delete chunk: ' + err.message);
        }
    };

    const handleSaveTranscript = async () => {
        if (!editingId) return;
        setSaving(true);
        try {
            await updateChunkTranscript(editingId, editText);
            setChunks(prev => prev.map(c => c.chunk_id === editingId ? { ...c, transcript_text: editText } : c));
            setEditingId(null);
            setEditText('');
        } catch (err: any) {
            alert('Failed to save: ' + err.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
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
                            placeholder="Search by transcript or chunk ID..."
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            style={{ width: '100%', padding: '0.6rem 1rem 0.6rem 3rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)', background: 'var(--bg-accent)', color: 'white' }}
                        />
                    </div>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(480px, 1fr))', gap: '1rem' }}>
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
                                {playingId === chunk.chunk_id ? <Pause size={18} fill="white" /> : <Play size={18} fill="white" style={pausedId === chunk.chunk_id ? { color: 'var(--accent-primary)' } : {}} />}
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontWeight: '600', fontSize: '0.9rem' }}>{chunk.chunk_id}</div>
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{chunk.duration.toFixed(2)}s</div>
                            </div>
                            <Trash2
                                size={16}
                                onClick={() => handleDelete(chunk.chunk_id)}
                                style={{ cursor: 'pointer', color: '#ef4444', opacity: 0.6 }}
                                onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
                                onMouseLeave={e => (e.currentTarget.style.opacity = '0.6')}
                            />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', minWidth: '32px' }}>
                                {formatTime((playingId === chunk.chunk_id || pausedId === chunk.chunk_id) ? currentTime : 0)}
                            </span>
                            <input
                                type="range"
                                min={0}
                                max={(playingId === chunk.chunk_id || pausedId === chunk.chunk_id) ? (audioDuration || chunk.duration) : chunk.duration}
                                step={0.1}
                                value={(playingId === chunk.chunk_id || pausedId === chunk.chunk_id) ? currentTime : 0}
                                onChange={(e) => handleSeek(chunk.chunk_id, e)}
                                style={{
                                    flex: 1,
                                    height: '4px',
                                    accentColor: 'var(--accent-primary)',
                                    cursor: 'pointer',
                                }}
                            />
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', minWidth: '32px', textAlign: 'right' }}>
                                {formatTime(chunk.duration)}
                            </span>
                        </div>
                        {editingId === chunk.chunk_id ? (
                            <div>
                                <textarea
                                    value={editText}
                                    onChange={e => setEditText(e.target.value)}
                                    style={{
                                        width: '100%',
                                        minHeight: '120px',
                                        backgroundColor: 'var(--bg-primary)',
                                        padding: '0.8rem',
                                        borderRadius: 'var(--radius-sm)',
                                        fontSize: '0.95rem',
                                        color: 'var(--text-primary)',
                                        direction: 'rtl',
                                        fontFamily: 'serif',
                                        border: '1px solid var(--accent-primary)',
                                        resize: 'vertical'
                                    }}
                                />
                                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                                    <button
                                        className="btn btn-primary"
                                        onClick={handleSaveTranscript}
                                        disabled={saving}
                                        style={{ padding: '0.3rem 0.8rem', fontSize: '0.8rem' }}
                                    >
                                        <Save size={14} /> {saving ? 'Saving...' : 'Save'}
                                    </button>
                                    <button
                                        className="btn"
                                        onClick={() => { setEditingId(null); setEditText(''); }}
                                        disabled={saving}
                                        style={{ padding: '0.3rem 0.8rem', fontSize: '0.8rem' }}
                                    >
                                        <X size={14} /> Cancel
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div style={{ position: 'relative' }}>
                                <div
                                    onClick={() => { setEditingId(chunk.chunk_id); setEditText(chunk.transcript_text || ''); }}
                                    style={{
                                        backgroundColor: 'var(--bg-primary)',
                                        padding: '0.8rem',
                                        borderRadius: 'var(--radius-sm)',
                                        fontSize: '0.95rem',
                                        lineHeight: 1.7,
                                        color: 'var(--text-primary)',
                                        direction: 'rtl',
                                        fontFamily: 'serif',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {chunk.transcript_text}
                                </div>
                                <Pencil
                                    size={14}
                                    onClick={() => { setEditingId(chunk.chunk_id); setEditText(chunk.transcript_text || ''); }}
                                    style={{
                                        position: 'absolute',
                                        top: '0.5rem',
                                        left: '0.5rem',
                                        cursor: 'pointer',
                                        color: 'var(--text-secondary)',
                                        opacity: 0.6
                                    }}
                                />
                            </div>
                        )}
                    </div>
                ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2rem', color: 'var(--text-secondary)', fontSize: '0.9rem', flexWrap: 'wrap', gap: '1rem' }}>
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
