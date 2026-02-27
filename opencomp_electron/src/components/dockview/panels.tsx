import { IDockviewPanelProps } from 'dockview-react';
import NodeCanvas from '../NodeCanvas';
import NodeLibrary from '../NodeLibrary';
import PropertiesPanel from '../PropertiesPanel';
import Viewer from '../Viewer';

// Wrapper for NodeCanvas panel
export const NodeCanvasPanel = (_props: IDockviewPanelProps) => {
  return (
    <div className="dv-panel-content">
      <NodeCanvas />
    </div>
  );
};

// Wrapper for NodeLibrary panel
export const NodeLibraryPanel = (_props: IDockviewPanelProps) => {
  return (
    <div className="dv-panel-content">
      <NodeLibrary />
    </div>
  );
};

// Wrapper for Properties panel
export const PropertiesPanel_ = (_props: IDockviewPanelProps) => {
  return (
    <div className="dv-panel-content">
      <PropertiesPanel />
    </div>
  );
};

// Wrapper for Viewer panel
export const ViewerPanel = (_props: IDockviewPanelProps) => {
  return (
    <div className="dv-panel-content">
      <Viewer />
    </div>
  );
};

// Export all panel components as a map
export const panelComponents = {
  nodeCanvas: NodeCanvasPanel,
  nodeLibrary: NodeLibraryPanel,
  properties: PropertiesPanel_,
  viewer: ViewerPanel,
};
