import { useCallback, useState } from 'react';
import { useGraphStore } from '../store/graphStore';
import './Toolbar.css';

const Toolbar = () => {
  const [evaluating, setEvaluating] = useState(false);
  const activeViewerId = useGraphStore((state) => state.activeViewerId);

  const handleNew = useCallback(async () => {
    if (!window.opencomp) return;

    const confirmed = window.confirm('Create a new project? Unsaved changes will be lost.');
    if (confirmed) {
      try {
        await window.opencomp.newProject();
        // Reload graph state
        const state = await window.opencomp.getGraphState();
        useGraphStore.getState().loadGraphState(state);
      } catch (err) {
        console.error('[Toolbar] New project failed:', err);
      }
    }
  }, []);

  const handleClearReload = useCallback(() => {
    // Clear localStorage (layout, etc)
    localStorage.clear();
    // Clear graph state
    useGraphStore.getState().setNodes([]);
    useGraphStore.getState().setEdges([]);
    // Reload the page
    window.location.reload();
  }, []);

  const handleOpen = useCallback(async () => {
    if (!window.opencomp) return;

    try {
      const result = await window.opencomp.openProject();
      if (result.status === 'ok') {
        // Reload graph state
        const state = await window.opencomp.getGraphState();
        useGraphStore.getState().loadGraphState(state);
      }
    } catch (err) {
      console.error('[Toolbar] Open project failed:', err);
    }
  }, []);

  const handleSave = useCallback(async () => {
    if (!window.opencomp) return;

    try {
      await window.opencomp.saveProject();
    } catch (err) {
      console.error('[Toolbar] Save project failed:', err);
    }
  }, []);

  const handleEvaluate = useCallback(async () => {
    if (!window.opencomp || !activeViewerId) return;

    setEvaluating(true);
    try {
      await window.opencomp.evaluate(activeViewerId);
    } catch (err) {
      console.error('[Toolbar] Evaluate failed:', err);
    } finally {
      setEvaluating(false);
    }
  }, [activeViewerId]);

  return (
    <div className="toolbar">
      <div className="toolbar-group">
        <button className="btn" onClick={handleNew} title="New Project">
          New
        </button>
        <button className="btn" onClick={handleOpen} title="Open Project">
          Open
        </button>
        <button className="btn" onClick={handleSave} title="Save Project">
          Save
        </button>
        <button className="btn" onClick={handleClearReload} title="Clear Cache & Reload">
          ⟳ Reset
        </button>
      </div>

      <div className="toolbar-separator" />

      <div className="toolbar-group">
        <button
          className="btn btn-primary"
          onClick={handleEvaluate}
          disabled={!activeViewerId || evaluating}
          title="Evaluate Graph (F5)"
        >
          {evaluating ? 'Evaluating...' : 'Evaluate'}
        </button>
      </div>

      <div className="toolbar-spacer" />

      <div className="toolbar-group">
        <span className="toolbar-status">
          {activeViewerId ? 'Viewer active' : 'No viewer'}
        </span>
      </div>
    </div>
  );
};

export default Toolbar;
