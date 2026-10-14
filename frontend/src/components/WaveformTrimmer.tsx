import { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin, { type Region } from 'wavesurfer.js/dist/plugins/regions.esm.js';
import { trimChunk } from '../api';
import { Play, Save, X } from 'lucide-react';

interface WaveformTrimmerProps {
    chunkId: string;
    duration: number;
    onSave: (updatedChunk: any) => void;
    onCancel: () => void;
}

const WaveformTrimmer = ({ chunkId, duration, onSave, onCancel }: WaveformTrimmerProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WaveSurfer | null>(null);
    const regionRef = useRef<Region | null>(null);
    const [trimStart, setTrimStart] = useState(0);
    const [trimEnd, setTrimEnd] = useState(duration);
    const [saving, setSaving] = useState(false);
    const [previewing, setPreviewing] = useState(false);
    const [ready, setReady] = useState(false);

    const updateRegionTimes = useCallback((region: Region) => {
        setTrimStart(Math.round(region.start * 100) / 100);
        setTrimEnd(Math.round(region.end * 100) / 100);
    }, []);

    useEffect(() => {
        if (!containerRef.current) return;

        const regions = RegionsPlugin.create();

        const ws = WaveSurfer.create({
            container: containerRef.current,
            waveColor: '#6366f1',
            progressColor: '#818cf8',
            cursorColor: '#f0f0f2',
            barWidth: 2,
            barGap: 1,
            barRadius: 2,
            height: 80,
            url: `/api/chunks/${chunkId}/audio?d=${duration}`,
            plugins: [regions],
        });

        wsRef.current = ws;

        ws.on('ready', () => {
            setReady(true);
            const region = regions.addRegion({
                start: 0,
                end: ws.getDuration(),
                color: 'rgba(99, 102, 241, 0.2)',
                drag: false,
                resize: true,
                minLength: 0.1,
            });
            regionRef.current = region;
            setTrimEnd(Math.round(ws.getDuration() * 100) / 100);
        });

        regions.on('region-updated', (region) => {
            updateRegionTimes(region);
        });

        ws.on('finish', () => {
            setPreviewing(false);
        });

        return () => {
            ws.destroy();
            wsRef.current = null;
            regionRef.current = null;
        };
    }, [chunkId, updateRegionTimes]);

    const handlePreview = () => {
        if (!wsRef.current || !regionRef.current) return;
        setPreviewing(true);
        regionRef.current.play(true);
    };

    const handleSave = async () => {
        if (trimStart === 0 && Math.abs(trimEnd - duration) < 0.01) {
            onCancel();
            return;
        }
        setSaving(true);
        try {
            const updated = await trimChunk(chunkId, trimStart, trimEnd);
            onSave(updated);
        } catch (err: any) {
            alert('Failed to trim: ' + (err.response?.data?.detail || err.message));
        } finally {
            setSaving(false);
        }
    };

    const handleCancel = () => {
        if (wsRef.current) {
            wsRef.current.stop();
        }
        onCancel();
    };

    return (
        <div style={{ padding: '0.8rem', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)' }}>
            <div
                ref={containerRef}
                style={{
                    borderRadius: 'var(--radius-sm)',
                    overflow: 'hidden',
                    marginBottom: '0.6rem',
                    opacity: ready ? 1 : 0.4,
                }}
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.6rem' }}>
                <span>Keep: {trimStart.toFixed(2)}s – {trimEnd.toFixed(2)}s</span>
                <span>Duration: {(trimEnd - trimStart).toFixed(2)}s (was {duration.toFixed(2)}s)</span>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                    className="btn"
                    onClick={handlePreview}
                    disabled={!ready || saving}
                    style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }}
                >
                    <Play size={14} /> {previewing ? 'Playing...' : 'Preview'}
                </button>
                <button
                    className="btn btn-primary"
                    onClick={handleSave}
                    disabled={!ready || saving}
                    style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }}
                >
                    <Save size={14} /> {saving ? 'Saving...' : 'Save Trim'}
                </button>
                <button
                    className="btn"
                    onClick={handleCancel}
                    disabled={saving}
                    style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }}
                >
                    <X size={14} /> Cancel
                </button>
            </div>
        </div>
    );
};

export default WaveformTrimmer;
