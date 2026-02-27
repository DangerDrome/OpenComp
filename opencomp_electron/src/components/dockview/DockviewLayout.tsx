import { useCallback, useRef, useEffect, FunctionComponent } from 'react';
import {
  DockviewReact,
  DockviewReadyEvent,
  IDockviewPanelProps,
  DockviewApi,
  IDockviewPanelHeaderProps,
  SerializedDockview,
} from 'dockview-react';
import 'dockview-react/dist/styles/dockview.css';
import './DockviewLayout.css';

// Panel components type matching dockview's expected format
type PanelComponents = Record<string, FunctionComponent<IDockviewPanelProps>>;

interface DockviewLayoutProps {
  components: PanelComponents;
  onReady?: (api: DockviewApi) => void;
}

const LAYOUT_STORAGE_KEY = 'opencomp-dockview-layout';

// Save layout to localStorage
const saveLayout = (api: DockviewApi) => {
  try {
    const layout = api.toJSON();
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
    console.log('[Dockview] Layout saved');
  } catch (e) {
    console.warn('[Dockview] Failed to save layout:', e);
  }
};

// Load layout from localStorage
const loadLayout = (): SerializedDockview | null => {
  try {
    const saved = localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (saved) {
      console.log('[Dockview] Found saved layout');
      return JSON.parse(saved);
    }
    console.log('[Dockview] No saved layout found');
  } catch (e) {
    console.warn('[Dockview] Failed to load layout:', e);
  }
  return null;
};

// Custom tab header component (Obsidian-style)
const CustomTab = (props: IDockviewPanelHeaderProps) => {
  const { api, containerApi } = props;
  const panelId = api.id;
  const title = api.title || panelId;

  const onClose = useCallback(() => {
    const panel = containerApi.getPanel(panelId);
    if (panel) {
      panel.api.close();
    }
  }, [containerApi, panelId]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1) {
      // Middle click to close
      e.preventDefault();
      onClose();
    }
  }, [onClose]);

  return (
    <div
      className="dv-tab-custom"
      onMouseDown={onMouseDown}
    >
      <span className="dv-tab-title">{title}</span>
      <button
        className="dv-tab-close"
        onClick={onClose}
        title="Close"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};

const DockviewLayout = ({ components, onReady }: DockviewLayoutProps) => {
  const apiRef = useRef<DockviewApi | null>(null);

  // Create default layout when no saved layout exists
  const createDefaultLayout = useCallback((api: DockviewApi) => {
    // Left panel group - Node Library
    const leftGroup = api.addGroup();
    api.addPanel({
      id: 'nodeLibrary',
      component: 'nodeLibrary',
      title: 'Nodes',
      position: { referenceGroup: leftGroup },
    });

    // Main center panel - Node Canvas
    const centerPanel = api.addPanel({
      id: 'nodeCanvas',
      component: 'nodeCanvas',
      title: 'Graph',
      position: { direction: 'right' },
    });

    // Right panel group - Properties and Viewer
    const rightPanel = api.addPanel({
      id: 'properties',
      component: 'properties',
      title: 'Properties',
      position: {
        direction: 'right',
        referencePanel: centerPanel,
      },
    });

    api.addPanel({
      id: 'viewer',
      component: 'viewer',
      title: 'Viewer',
      position: {
        referencePanel: rightPanel,
      },
    });
  }, []);

  const handleReady = useCallback((event: DockviewReadyEvent) => {
    apiRef.current = event.api;

    // Try to load saved layout
    const savedLayout = loadLayout();
    if (savedLayout) {
      try {
        event.api.fromJSON(savedLayout);
      } catch (e) {
        console.warn('Failed to restore layout, using default:', e);
        createDefaultLayout(event.api);
      }
    } else {
      createDefaultLayout(event.api);
    }

    // Save layout on any changes
    event.api.onDidLayoutChange(() => {
      saveLayout(event.api);
    });

    onReady?.(event.api);
  }, [onReady, createDefaultLayout]);

  // Save layout before window closes
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (apiRef.current) {
        saveLayout(apiRef.current);
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  return (
    <DockviewReact
      className="dockview-theme-obsidian"
      onReady={handleReady}
      components={components}
      defaultTabComponent={CustomTab}
      watermarkComponent={() => (
        <div className="dv-watermark">
          <span>Drop panel here</span>
        </div>
      )}
      disableFloatingGroups={false}
      floatingGroupBounds="boundedWithinViewport"
    />
  );
};

export default DockviewLayout;

// Export a hook to access the dockview API
export const useDockviewApi = () => {
  return useRef<DockviewApi | null>(null);
};
