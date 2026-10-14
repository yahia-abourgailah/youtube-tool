import { useEffect, useState, useRef } from 'react';
import { getChunks } from '../api';
import { Play, Pause, Search, Scissors, ChevronLeft, ChevronRight } from 'lucide-react';
import WaveformTrimmer from '../components/WaveformTrimmer';

const Trimming = () => {
    const [chunks, setChunks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalItems, setTotalItems] = useState(0);
    const [searchTerm, setSearchTerm] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [playingId, setPlayingId] = useState<string | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const debounceRef = useRef<ReturnType<typeof setTimeout>>();
    const pageSize = 20;

    useEffect(() => {
        loadChunks();
    }, [page, debouncedSearch]);

    useEffect(() => {
        clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            setPage(1);
            setDebouncedSearch(searchTerm);
        }, 400);
        return () => clearTimeout(debounceRef.current);
    }, [searchTerm]);

    useEffect(() => {
        return () => {
            audioRef.current?.pause();
            audioRef.current = null;
        };
    }, []);

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

    const selectedChunk = chunks.find(c => c.chunk_id === selectedId) || null;

    const playAudio = (id: string) => {
        if (playingId === id) {
            audioRef.current?.pause();
            audioRef.current = null;
            setPlayingId(null);
            return;
        }
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
        }
        const chunk = chunks.find(c => c.chunk_id === id);
        const audio = new Audio(`/api/chunks/${id}/audio?d=${chunk?.duration || 0}`);
        audioRef.current = audio;
        setPlayingId(id);
        audio.play();
        audio.onended = () => {
            audioRef.current = null;
            setPlayingId(null);
        };
    };

    return (
        <div style={{ display: 'flex', height: 'calc(100vh - 3rem)', gap: '1rem' }}>
            {/* Left panel — chunk list */}
            <div style={{
                width: 380,
                minWidth: 380,
                display: 'flex',
                flexDirection: 'column',
                background: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
            }}>
                {/* Search */}
                <div style={{ padding: '0.75rem', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ position: 'relative' }}>
                        <Search size={16} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
                        <input
                            type="text"
                            placeholder="Search chunks..."
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            style={{
                                width: '100%',
                                padding: '0.5rem 0.75rem 0.5rem 2.25rem',
                                borderRadius: 'var(--radius-sm)',
                                border: '1px solid var(--border)',
                                background: 'var(--bg-accent)',
                                color: 'white',
                                fontSize: '0.85rem',
                            }}
                        />
                    </div>
                </div>

                {/* Scrollable list */}
                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {loading ? (
                        <div style={{ padding: '1.5rem', color: 'var(--text-secondary)', textAlign: 'center' }}>Loading...</div>
                    ) : chunks.length === 0 ? (
                        <div style={{ padding: '1.5rem', color: 'var(--text-secondary)', textAlign: 'center' }}>No chunks found</div>
                    ) : chunks.map(chunk => {
                        const isSelected = selectedId === chunk.chunk_id;
                        return (
                            <div
                                key={chunk.chunk_id}
                                onClick={() => setSelectedId(chunk.chunk_id)}
                                style={{
                                    padding: '0.75rem 0.75rem 0.75rem 1rem',
                                    cursor: 'pointer',
                                    borderBottom: '1px solid var(--border)',
                                    background: isSelected ? 'var(--bg-accent)' : 'transparent',
                                    borderLeft: isSelected ? '3px solid var(--accent-primary)' : '3px solid transparent',
                                    transition: 'background 0.15s',
                                }}
                                onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                                onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                                    <span style={{ fontWeight: 600, fontSize: '0.8rem', color: 'var(--text-primary)' }}>{chunk.chunk_id}</span>
                                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{chunk.duration.toFixed(2)}s</span>
                                </div>
                                <div style={{
                                    fontSize: '0.8rem',
                                    color: 'var(--text-secondary)',
                                    direction: 'rtl',
                                    fontFamily: 'serif',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}>
                                    {chunk.transcript_text || '—'}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Pagination footer */}
                <div style={{
                    padding: '0.5rem 0.75rem',
                    borderTop: '1px solid var(--border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '0.75rem',
                    color: 'var(--text-secondary)',
                }}>
                    <span>{totalItems} chunks</span>
                    <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                        <button
                            className="btn"
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem' }}
                        >
                            <ChevronLeft size={14} />
                        </button>
                        <span>{page}/{totalPages}</span>
                        <button
                            className="btn"
                            disabled={page === totalPages}
                            onClick={() => setPage(p => p + 1)}
                            style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem' }}
                        >
                            <ChevronRight size={14} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Right panel — detail */}
            <div style={{
                flex: 1,
                background: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)',
                overflow: 'auto',
                display: 'flex',
                flexDirection: 'column',
            }}>
                {!selectedChunk ? (
                    <div style={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--text-secondary)',
                        gap: '1rem',
                    }}>
                        <Scissors size={48} strokeWidth={1.2} />
                        <span style={{ fontSize: '1rem' }}>Select a chunk to trim</span>
                    </div>
                ) : (
                    <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        {/* Header row */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            <div
                                onClick={() => playAudio(selectedChunk.chunk_id)}
                                style={{
                                    width: 44,
                                    height: 44,
                                    borderRadius: '50%',
                                    background: playingId === selectedChunk.chunk_id ? 'var(--accent-primary)' : 'var(--bg-accent)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer',
                                    flexShrink: 0,
                                }}
                            >
                                {playingId === selectedChunk.chunk_id
                                    ? <Pause size={20} fill="white" />
                                    : <Play size={20} fill="white" />}
                            </div>
                            <div>
                                <div style={{ fontWeight: 700, fontSize: '1rem' }}>{selectedChunk.chunk_id}</div>
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                    {selectedChunk.duration.toFixed(2)}s &nbsp;·&nbsp; {selectedChunk.start_time?.toFixed(2) ?? '?'}s – {selectedChunk.end_time?.toFixed(2) ?? '?'}s
                                </div>
                            </div>
                        </div>

                        {/* Waveform trimmer */}
                        <WaveformTrimmer
                            key={selectedChunk.chunk_id + '-' + selectedChunk.duration}
                            chunkId={selectedChunk.chunk_id}
                            duration={selectedChunk.duration}
                            onSave={(updated) => {
                                setChunks(prev => prev.map(c => c.chunk_id === updated.chunk_id ? updated : c));
                            }}
                            onCancel={() => {}}
                        />

                        {/* Read-only transcript */}
                        {selectedChunk.transcript_text && (
                            <div style={{
                                background: 'var(--bg-primary)',
                                padding: '1rem',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '1rem',
                                lineHeight: 1.8,
                                color: 'var(--text-primary)',
                                direction: 'rtl',
                                fontFamily: 'serif',
                            }}>
                                {selectedChunk.transcript_text}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Trimming;
