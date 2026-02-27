import { useCallback, useEffect, useRef } from 'react';
import { useGraphStore } from '../store/graphStore';

const Timeline = () => {
  const currentFrame = useGraphStore((state) => state.currentFrame);
  const frameStart = useGraphStore((state) => state.frameStart);
  const frameEnd = useGraphStore((state) => state.frameEnd);
  const isPlaying = useGraphStore((state) => state.isPlaying);
  const setCurrentFrame = useGraphStore((state) => state.setCurrentFrame);
  const setIsPlaying = useGraphStore((state) => state.setIsPlaying);
  const nextFrame = useGraphStore((state) => state.nextFrame);
  const prevFrame = useGraphStore((state) => state.prevFrame);
  const goToStart = useGraphStore((state) => state.goToStart);
  const goToEnd = useGraphStore((state) => state.goToEnd);

  const scrubberRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  // Playback loop
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      nextFrame();
    }, 1000 / 24); // 24 fps

    return () => clearInterval(interval);
  }, [isPlaying, nextFrame]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if typing in an input
      if (e.target instanceof HTMLInputElement) return;

      switch (e.key) {
        case ' ':
          e.preventDefault();
          setIsPlaying(!isPlaying);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          prevFrame();
          break;
        case 'ArrowRight':
          e.preventDefault();
          nextFrame();
          break;
        case 'Home':
          e.preventDefault();
          goToStart();
          break;
        case 'End':
          e.preventDefault();
          goToEnd();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPlaying, setIsPlaying, nextFrame, prevFrame, goToStart, goToEnd]);

  // Scrubber interaction
  const calculateFrameFromEvent = useCallback((e: MouseEvent | React.MouseEvent) => {
    if (!scrubberRef.current) return currentFrame;
    const rect = scrubberRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const ratio = x / rect.width;
    return Math.round(frameStart + ratio * (frameEnd - frameStart));
  }, [frameStart, frameEnd, currentFrame]);

  const handleScrubberMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    setCurrentFrame(calculateFrameFromEvent(e));

    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging.current) {
        setCurrentFrame(calculateFrameFromEvent(e));
      }
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, [calculateFrameFromEvent, setCurrentFrame]);

  const playheadPosition = ((currentFrame - frameStart) / (frameEnd - frameStart)) * 100;

  return (
    <div className="timeline">
      {/* Transport Controls */}
      <div className="timeline-controls">
        <button
          className="timeline-btn"
          onClick={goToStart}
          title="Go to Start (Home)"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 6h2v12H6V6zm3.5 6l8.5 6V6l-8.5 6z"/>
          </svg>
        </button>
        <button
          className="timeline-btn"
          onClick={prevFrame}
          title="Previous Frame (Left Arrow)"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/>
          </svg>
        </button>
        <button
          className={`timeline-btn timeline-btn-play ${isPlaying ? 'active' : ''}`}
          onClick={() => setIsPlaying(!isPlaying)}
          title="Play/Pause (Space)"
        >
          {isPlaying ? (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          )}
        </button>
        <button
          className="timeline-btn"
          onClick={nextFrame}
          title="Next Frame (Right Arrow)"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
          </svg>
        </button>
        <button
          className="timeline-btn"
          onClick={goToEnd}
          title="Go to End (End)"
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/>
          </svg>
        </button>
      </div>

      {/* Frame Counter */}
      <div className="timeline-frame-info">
        <input
          type="number"
          className="timeline-frame-input"
          value={currentFrame}
          onChange={(e) => setCurrentFrame(parseInt(e.target.value) || frameStart)}
          min={frameStart}
          max={frameEnd}
        />
        <span className="timeline-frame-range">
          / {frameEnd}
        </span>
      </div>

      {/* Scrubber */}
      <div
        className="timeline-scrubber"
        ref={scrubberRef}
        onMouseDown={handleScrubberMouseDown}
      >
        <div className="timeline-scrubber-track">
          <div
            className="timeline-scrubber-progress"
            style={{ width: `${playheadPosition}%` }}
          />
          <div
            className="timeline-playhead"
            style={{ left: `${playheadPosition}%` }}
          />
        </div>
        {/* Frame markers */}
        <div className="timeline-markers">
          <span>{frameStart}</span>
          <span>{Math.round((frameEnd - frameStart) * 0.25 + frameStart)}</span>
          <span>{Math.round((frameEnd - frameStart) * 0.5 + frameStart)}</span>
          <span>{Math.round((frameEnd - frameStart) * 0.75 + frameStart)}</span>
          <span>{frameEnd}</span>
        </div>
      </div>

      {/* Range Info */}
      <div className="timeline-range-info">
        <span className="timeline-fps">24 fps</span>
      </div>
    </div>
  );
};

export default Timeline;
