import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useGraphStore } from '../store/graphStore';
import './Viewer.css';

interface ImageData {
  dataUrl?: string;
  rgbaData?: Uint8ClampedArray;
  format?: string;
  width: number;
  height: number;
  needsConversion?: boolean;
  error?: string;
  fromBackend?: boolean;
}

const Viewer = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [imageData, setImageData] = useState<ImageData | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const lastPanPos = useRef({ x: 0, y: 0 });
  const imageRef = useRef<HTMLImageElement | null>(null);

  const activeViewerId = useGraphStore((state) => state.activeViewerId);
  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const currentFrame = useGraphStore((state) => state.currentFrame);

  // Find the active viewer node
  const viewerNode = useMemo(
    () => nodes.find((n) => n.id === activeViewerId),
    [nodes, activeViewerId]
  );

  // Trace back from viewer to find connected Read node
  const connectedReadNode = useMemo(() => {
    if (!activeViewerId) return null;

    // Find edge connected to the viewer's input
    const incomingEdge = edges.find((e) => e.target === activeViewerId);
    if (!incomingEdge) return null;

    // Find the source node
    const sourceNode = nodes.find((n) => n.id === incomingEdge.source);
    if (!sourceNode) return null;

    // If it's a Read node, return it
    if (sourceNode.data.nodeType === 'OC_N_read') {
      return sourceNode;
    }

    // For intermediate nodes, trace further back
    const nextEdge = edges.find((e) => e.target === sourceNode.id);
    if (nextEdge) {
      const nextSource = nodes.find((n) => n.id === nextEdge.source);
      if (nextSource?.data.nodeType === 'OC_N_read') {
        return nextSource;
      }
    }

    return null;
  }, [activeViewerId, nodes, edges]);

  // Subscribe to viewer updates from backend
  useEffect(() => {
    if (!window.opencomp?.onViewerUpdated) return;

    const unsubscribe = window.opencomp.onViewerUpdated(async (event) => {
      if (event.viewer_node_id === activeViewerId) {
        console.log('[Viewer] Backend updated, reading shared memory...');
        // Read from shared memory
        if (window.opencomp?.readViewerShm) {
          try {
            const result = await window.opencomp.readViewerShm();
            if (result.status === 'ok' && result.rgba_base64) {
              // Decode base64 to Uint8Array
              const binaryString = atob(result.rgba_base64);
              const bytes = new Uint8ClampedArray(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              setImageData({
                rgbaData: bytes,
                width: result.width,
                height: result.height,
                fromBackend: true,
              });
            }
          } catch (err) {
            console.error('[Viewer] Failed to read SHM:', err);
          }
        }
      }
    });

    return unsubscribe;
  }, [activeViewerId]);

  // Load image when connected Read node changes or frame changes
  useEffect(() => {
    if (!connectedReadNode) {
      setImageData(null);
      return;
    }

    const filePath = connectedReadNode.data.params?.filepath as string | undefined;
    if (!filePath) {
      setImageData({ width: 1920, height: 1080, error: 'No file path set' });
      return;
    }

    const ext = filePath.split('.').pop()?.toLowerCase() || '';
    const isEXR = ['exr', 'dpx', 'hdr', 'tif', 'tiff'].includes(ext);

    // For EXR/HDR formats, try to read from shared memory first (backend processed)
    if (isEXR && window.opencomp?.readViewerShm) {
      window.opencomp.readViewerShm()
        .then((result) => {
          if (result.status === 'ok' && result.rgba_base64 && result.width > 0) {
            // Decode base64 to Uint8Array
            const binaryString = atob(result.rgba_base64);
            const bytes = new Uint8ClampedArray(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }
            setImageData({
              rgbaData: bytes,
              width: result.width,
              height: result.height,
              fromBackend: true,
            });
          } else {
            // No data yet - show waiting message
            setImageData({
              width: 1920,
              height: 1080,
              format: ext.toUpperCase(),
              needsConversion: true,
              error: 'Waiting for backend evaluation...',
            });
          }
        })
        .catch(() => {
          setImageData({
            width: 1920,
            height: 1080,
            format: ext.toUpperCase(),
            needsConversion: true,
            error: 'Backend not ready',
          });
        });
      return;
    }

    // For browser-native formats, load directly
    if (!window.opencomp?.readImageFile) {
      if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(ext)) {
        const img = new Image();
        img.onload = () => {
          imageRef.current = img;
          setImageData({
            dataUrl: `file://${filePath}`,
            width: img.width,
            height: img.height,
          });
        };
        img.onerror = () => {
          setImageData({ width: 1920, height: 1080, error: `Failed to load: ${filePath}` });
        };
        img.src = `file://${filePath}`;
        return;
      }
      setImageData({ width: 1920, height: 1080, error: 'readImageFile API not available' });
      return;
    }

    // Load the image via IPC
    window.opencomp.readImageFile(filePath, currentFrame)
      .then((result) => {
        if (result.status === 'error') {
          setImageData({ width: 1920, height: 1080, error: result.message });
          return;
        }

        if (result.type === 'dataUrl' && result.dataUrl) {
          const img = new Image();
          img.onload = () => {
            imageRef.current = img;
            setImageData({
              dataUrl: result.dataUrl,
              width: img.width,
              height: img.height,
            });
          };
          img.onerror = () => {
            setImageData({ width: 1920, height: 1080, error: 'Failed to decode image' });
          };
          img.src = result.dataUrl;
        } else if (result.type === 'rawFormat') {
          setImageData({
            width: 1920,
            height: 1080,
            format: result.format,
            needsConversion: true,
            error: `${result.format} - Evaluating...`,
          });
        }
      })
      .catch((err) => {
        console.error('[Viewer] Failed to load image:', err);
        setImageData({ width: 1920, height: 1080, error: err.message });
      });
  }, [connectedReadNode, currentFrame]);

  // Handle zoom with scroll wheel
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom((z) => Math.min(Math.max(z * delta, 0.1), 10));
  }, []);

  // Handle panning
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      setIsPanning(true);
      lastPanPos.current = { x: e.clientX, y: e.clientY };
    }
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isPanning) {
        const dx = e.clientX - lastPanPos.current.x;
        const dy = e.clientY - lastPanPos.current.y;
        setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
        lastPanPos.current = { x: e.clientX, y: e.clientY };
      }
    },
    [isPanning]
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const fitView = useCallback(() => {
    if (!imageData || !canvasRef.current) return;
    const container = canvasRef.current.parentElement;
    if (!container) return;

    const containerWidth = container.clientWidth - 40;
    const containerHeight = container.clientHeight - 40;

    const scaleX = containerWidth / imageData.width;
    const scaleY = containerHeight / imageData.height;
    const scale = Math.min(scaleX, scaleY, 1);

    setZoom(scale);
    setPan({ x: 0, y: 0 });
  }, [imageData]);

  // Draw image or placeholder on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = imageData?.width || 1920;
    const height = imageData?.height || 1080;
    canvas.width = width;
    canvas.height = height;

    // Draw checkerboard background
    const tileSize = 16;
    for (let y = 0; y < height; y += tileSize) {
      for (let x = 0; x < width; x += tileSize) {
        const isLight = ((x / tileSize) + (y / tileSize)) % 2 === 0;
        ctx.fillStyle = isLight ? '#3a3a3a' : '#2a2a2a';
        ctx.fillRect(x, y, tileSize, tileSize);
      }
    }

    // Draw from backend RGBA data
    if (imageData?.rgbaData && imageData.fromBackend) {
      const imgData = new ImageData(imageData.rgbaData, width, height);
      ctx.putImageData(imgData, 0, 0);
    }
    // Draw from Image element (browser-native formats)
    else if (imageRef.current && imageData?.dataUrl && !imageData.error) {
      ctx.drawImage(imageRef.current, 0, 0, width, height);
    }
    // Show placeholder or error
    else {
      ctx.fillStyle = imageData?.error ? 'rgba(255, 100, 100, 0.1)' : 'rgba(76, 204, 115, 0.1)';
      ctx.fillRect(0, 0, width, height);

      ctx.fillStyle = '#666';
      ctx.font = '24px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      if (imageData?.error) {
        ctx.fillStyle = '#ff6666';
        ctx.fillText(imageData.error, width / 2, height / 2);
      } else if (imageData?.needsConversion) {
        ctx.fillText(`${imageData.format} - Processing...`, width / 2, height / 2);
        ctx.font = '14px sans-serif';
        ctx.fillText('Backend is evaluating the graph', width / 2, height / 2 + 30);
      } else if (!connectedReadNode) {
        ctx.fillText('No Input Connected', width / 2, height / 2);
        ctx.font = '14px sans-serif';
        ctx.fillText('Connect a Read node to the Viewer', width / 2, height / 2 + 30);
      } else {
        ctx.fillText('Loading...', width / 2, height / 2);
      }
    }
  }, [imageData, connectedReadNode]);

  const getFooterInfo = () => {
    if (imageData?.fromBackend) {
      const fileName = connectedReadNode?.data.params?.filepath as string;
      const shortName = fileName?.split('/').pop() || 'Backend';
      return `${shortName} • ${imageData.width} × ${imageData.height} • GPU`;
    }
    if (imageData?.dataUrl && !imageData.error) {
      const fileName = connectedReadNode?.data.params?.filepath as string;
      const shortName = fileName?.split('/').pop() || 'Image';
      return `${shortName} • ${imageData.width} × ${imageData.height}`;
    }
    if (imageData?.needsConversion) {
      return `${imageData.format} • Processing`;
    }
    if (!connectedReadNode) {
      return 'No input connected';
    }
    return 'Loading...';
  };

  return (
    <div className="viewer">
      <div className="viewer-header">
        <span className="viewer-title">
          {viewerNode ? viewerNode.data.label : 'Viewer'}
        </span>
        <div className="viewer-controls">
          <button className="btn" onClick={fitView} title="Fit to view">
            ⊡
          </button>
          <button className="btn" onClick={resetView} title="Reset view">
            1:1
          </button>
          <span className="viewer-zoom">{Math.round(zoom * 100)}%</span>
        </div>
      </div>
      <div
        className="viewer-canvas-container"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isPanning ? 'grabbing' : 'default' }}
      >
        <div
          className="viewer-canvas-wrapper"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          }}
        >
          <canvas ref={canvasRef} className="viewer-canvas" />
        </div>
      </div>
      <div className="viewer-footer">
        <span>{getFooterInfo()}</span>
        {connectedReadNode && (
          <span className="viewer-frame">Frame {currentFrame}</span>
        )}
      </div>
    </div>
  );
};

export default Viewer;
