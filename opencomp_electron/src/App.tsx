import { useEffect, useCallback, useRef } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { DockviewApi } from 'dockview-react';
import { DockviewLayout, panelComponents } from './components/dockview';
import Toolbar from './components/Toolbar';
import Timeline from './components/Timeline';
import { useGraphStore } from './store/graphStore';
import '@xyflow/react/dist/style.css';

// Type declaration for the preload API
declare global {
  interface Window {
    opencomp: {
      getGraphState: () => Promise<any>;
      getNodeTypes: () => Promise<any>;
      createNode: (nodeType: string, x: number, y: number) => Promise<any>;
      deleteNode: (nodeId: string) => Promise<any>;
      moveNode: (nodeId: string, x: number, y: number) => Promise<any>;
      setNodeParam: (nodeId: string, param: string, value: any) => Promise<any>;
      connect: (fromNode: string, fromPort: string, toNode: string, toPort: string) => Promise<any>;
      disconnect: (fromNode: string, fromPort: string, toNode: string, toPort: string) => Promise<any>;
      evaluate: (viewerNodeId: string) => Promise<any>;
      getViewerBuffer: (viewerNodeId: string) => Promise<any>;
      newProject: () => Promise<any>;
      openProject: () => Promise<any>;
      saveProject: () => Promise<any>;
      ping: () => Promise<any>;
      showOpenDialog: (options?: {
        properties?: string[];
        filters?: Array<{ name: string; extensions: string[] }>;
      }) => Promise<{ canceled: boolean; filePaths: string[] }>;
      showSaveDialog: (options?: {
        filters?: Array<{ name: string; extensions: string[] }>;
      }) => Promise<{ canceled: boolean; filePath?: string }>;
      readImageFile: (filePath: string, frame?: number) => Promise<{
        status: string;
        type?: 'dataUrl' | 'rawFormat';
        dataUrl?: string;
        format?: string;
        filePath?: string;
        size?: number;
        needsConversion?: boolean;
        message?: string;
      }>;
      readViewerShm: () => Promise<{
        status: string;
        width?: number;
        height?: number;
        frameCounter?: number;
        rgba_base64?: string;
        message?: string;
      }>;
      onBackendReady: (callback: () => void) => () => void;
      onBackendEvent: (callback: (event: any) => void) => () => void;
      onViewerUpdated: (callback: (event: any) => void) => () => void;
    };
    platform: {
      isElectron: boolean;
      platform: string;
      arch: string;
    };
  }
}

function App() {
  const loadGraphState = useGraphStore((state) => state.loadGraphState);
  const loadNodeTypes = useGraphStore((state) => state.loadNodeTypes);
  const dockviewApiRef = useRef<DockviewApi | null>(null);

  useEffect(() => {
    // Skip if not in Electron
    if (!window.opencomp) return;

    // Function to load state from backend
    const loadFromBackend = () => {
      Promise.all([
        window.opencomp.getGraphState(),
        window.opencomp.getNodeTypes(),
      ])
        .then(([graphState, nodeTypes]) => {
          loadGraphState(graphState);
          loadNodeTypes(nodeTypes.categories);
        })
        .catch((err) => {
          console.error('[App] Failed to load state:', err);
        });
    };

    // Listen for backend ready event
    const unsubscribe = window.opencomp.onBackendReady(() => {
      console.log('[App] Backend ready');
      loadFromBackend();
    });

    // Try immediately in case backend is already ready
    window.opencomp.ping()
      .then(() => loadFromBackend())
      .catch(() => {}); // Backend not ready yet, wait for event

    return unsubscribe;
  }, [loadGraphState, loadNodeTypes]);

  const handleDockviewReady = useCallback((api: DockviewApi) => {
    dockviewApiRef.current = api;
    console.log('[App] Dockview ready');
  }, []);

  return (
    <ReactFlowProvider>
      <div className="app">
        {/* Header with toolbar */}
        <header className="app-header">
          <div className="logo">
            <svg className="logo-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
            OpenComp
          </div>
          <Toolbar />
        </header>

        {/* Main dockview layout */}
        <div className="app-dockview">
          <DockviewLayout
            components={panelComponents}
            onReady={handleDockviewReady}
          />
        </div>

        {/* Timeline at bottom */}
        <Timeline />
      </div>
    </ReactFlowProvider>
  );
}

export default App;
