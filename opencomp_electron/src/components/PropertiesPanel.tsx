import { useCallback } from 'react';
import { useGraphStore } from '../store/graphStore';
import './PropertiesPanel.css';

const PropertiesPanel = () => {
  const selectedNode = useGraphStore((state) => state.selectedNode);
  const setNodeParam = useGraphStore((state) => state.setNodeParam);

  const handleParamChange = useCallback(
    (param: string, value: any) => {
      if (selectedNode) {
        setNodeParam(selectedNode.id, param, value);
      }
    },
    [selectedNode, setNodeParam]
  );

  // Handle file browse - must be defined before any early returns (Rules of Hooks)
  const handleBrowseFile = useCallback(async (paramKey: string, isSequence: boolean = false) => {
    if (!window.opencomp?.showOpenDialog) return;

    try {
      // Use Electron's file dialog via our preload API
      const result = await window.opencomp.showOpenDialog({
        properties: ['openFile'],
        filters: isSequence
          ? [{ name: 'Images', extensions: ['exr', 'dpx', 'tif', 'tiff', 'png', 'jpg', 'jpeg', 'hdr'] }]
          : [{ name: 'All Files', extensions: ['*'] }]
      });

      if (result && !result.canceled && result.filePaths?.[0]) {
        handleParamChange(paramKey, result.filePaths[0]);
      }
    } catch (err) {
      console.error('File dialog error:', err);
    }
  }, [handleParamChange]);

  if (!selectedNode) {
    return (
      <div className="properties-panel">
        <div className="panel-header">Properties</div>
        <div className="properties-panel-empty">
          Select a node to view its properties
        </div>
      </div>
    );
  }

  const { label, nodeType, params } = selectedNode.data;
  const isReadNode = nodeType === 'OC_N_read';
  const isWriteNode = nodeType === 'OC_N_write';

  // Ensure Read/Write nodes always show filepath
  const displayParams = { ...params };
  if ((isReadNode || isWriteNode) && !('filepath' in displayParams)) {
    displayParams.filepath = '';
  }
  if (isReadNode) {
    if (!('first_frame' in displayParams)) displayParams.first_frame = 1;
    if (!('last_frame' in displayParams)) displayParams.last_frame = 100;
  }

  return (
    <div className="properties-panel">
      <div className="panel-header">Properties</div>
      <div className="properties-panel-content">
        {/* Node info */}
        <div className="properties-section">
          <div className="properties-section-header">Node</div>
          <div className="properties-row">
            <span className="properties-label">Name</span>
            <span className="properties-value">{selectedNode.id}</span>
          </div>
          <div className="properties-row">
            <span className="properties-label">Type</span>
            <span className="properties-value">{label}</span>
          </div>
        </div>

        {/* File path for Read/Write nodes */}
        {(isReadNode || isWriteNode) && (
          <div className="properties-section">
            <div className="properties-section-header">File</div>
            <div className="properties-row properties-row-file">
              <span className="properties-label">Path</span>
              <div className="properties-file-input">
                <input
                  type="text"
                  className="input"
                  value={(displayParams.filepath as string) || ''}
                  onChange={(e) => handleParamChange('filepath', e.target.value)}
                  placeholder="Enter file path or drag & drop..."
                />
                <button
                  className="btn btn-small"
                  onClick={() => handleBrowseFile('filepath', isReadNode)}
                  title="Browse..."
                >
                  ...
                </button>
              </div>
            </div>
            {isReadNode && (
              <>
                <div className="properties-row">
                  <span className="properties-label">First Frame</span>
                  <input
                    type="number"
                    className="input"
                    value={(displayParams.first_frame as number) || 1}
                    onChange={(e) => handleParamChange('first_frame', parseInt(e.target.value, 10))}
                    style={{ width: '80px' }}
                  />
                </div>
                <div className="properties-row">
                  <span className="properties-label">Last Frame</span>
                  <input
                    type="number"
                    className="input"
                    value={(displayParams.last_frame as number) || 100}
                    onChange={(e) => handleParamChange('last_frame', parseInt(e.target.value, 10))}
                    style={{ width: '80px' }}
                  />
                </div>
              </>
            )}
          </div>
        )}

        {/* Other Parameters */}
        {Object.keys(displayParams).filter(k =>
          !['filepath', 'first_frame', 'last_frame'].includes(k) || (!isReadNode && !isWriteNode)
        ).length > 0 && (
          <div className="properties-section">
            <div className="properties-section-header">Parameters</div>
            {Object.entries(displayParams)
              .filter(([key]) => !['filepath', 'first_frame', 'last_frame'].includes(key) || (!isReadNode && !isWriteNode))
              .map(([key, value]) => (
              <div key={key} className="properties-row">
                <span className="properties-label">{formatParamName(key)}</span>
                <div className="properties-input">
                  {renderParamInput(key, value, handleParamChange)}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Position */}
        <div className="properties-section">
          <div className="properties-section-header">Position</div>
          <div className="properties-row">
            <span className="properties-label">X</span>
            <span className="properties-value">
              {Math.round(selectedNode.position.x)}
            </span>
          </div>
          <div className="properties-row">
            <span className="properties-label">Y</span>
            <span className="properties-value">
              {Math.round(selectedNode.position.y)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

// Format parameter name (snake_case to Title Case)
function formatParamName(name: string): string {
  return name
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Render appropriate input based on value type
function renderParamInput(
  key: string,
  value: any,
  onChange: (key: string, value: any) => void
) {
  if (typeof value === 'boolean') {
    return (
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(key, e.target.checked)}
      />
    );
  }

  if (typeof value === 'number') {
    // Check if it's likely a float (has decimal or specific param names)
    const isFloat =
      !Number.isInteger(value) ||
      key.includes('gain') ||
      key.includes('offset') ||
      key.includes('gamma') ||
      key.includes('factor') ||
      key.includes('intensity');

    return (
      <input
        type="number"
        className="input"
        value={value}
        step={isFloat ? 0.01 : 1}
        onChange={(e) => {
          const newValue = isFloat
            ? parseFloat(e.target.value)
            : parseInt(e.target.value, 10);
          onChange(key, newValue);
        }}
        style={{ width: '80px' }}
      />
    );
  }

  if (typeof value === 'string') {
    return (
      <input
        type="text"
        className="input"
        value={value}
        onChange={(e) => onChange(key, e.target.value)}
        style={{ width: '100%' }}
      />
    );
  }

  if (Array.isArray(value) && value.length <= 4) {
    // Vector input (RGB, RGBA, XY, XYZ, etc.)
    return (
      <div className="properties-vector">
        {value.map((v, i) => (
          <input
            key={i}
            type="number"
            className="input"
            value={v}
            step={0.01}
            onChange={(e) => {
              const newValue = [...value];
              newValue[i] = parseFloat(e.target.value);
              onChange(key, newValue);
            }}
            style={{ width: '50px' }}
          />
        ))}
      </div>
    );
  }

  // Fallback: show as read-only
  return <span className="properties-value">{JSON.stringify(value)}</span>;
}

export default PropertiesPanel;
