import { useCallback, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  MiniMap,
  BackgroundVariant,
  useReactFlow,
  ConnectionMode,
  ConnectionLineType,
} from '@xyflow/react';
import { useGraphStore } from '../store/graphStore';
import OpenCompNode from './OpenCompNode';
import NodeMenu from './NodeMenu';

// Supported image formats for drag-drop
const IMAGE_EXTENSIONS = ['.exr', '.dpx', '.tif', '.tiff', '.png', '.jpg', '.jpeg', '.hdr'];

// Menu state type
interface MenuState {
  screenPosition: { x: number; y: number };
  flowPosition: { x: number; y: number };
}

const NodeCanvas = () => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();
  const [menuState, setMenuState] = useState<MenuState | null>(null);

  const nodes = useGraphStore((state) => state.nodes);
  const edges = useGraphStore((state) => state.edges);
  const onNodesChange = useGraphStore((state) => state.onNodesChange);
  const onEdgesChange = useGraphStore((state) => state.onEdgesChange);
  const onConnect = useGraphStore((state) => state.onConnect);
  const addNode = useGraphStore((state) => state.addNode);
  const addReadNode = useGraphStore((state) => state.addReadNode);
  const selectNode = useGraphStore((state) => state.selectNode);
  const deleteNode = useGraphStore((state) => state.deleteNode);

  // Custom node types
  const nodeTypes = useMemo(
    () => ({
      opencompNode: OpenCompNode,
    }),
    []
  );

  // Handle node selection
  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes }: { nodes: Array<{ id: string }> }) => {
      if (selectedNodes.length === 1) {
        selectNode(selectedNodes[0].id);
      } else {
        selectNode(null);
      }
    },
    [selectNode]
  );

  // Handle keyboard shortcuts
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      // Tab key opens node menu (Nuke-style)
      if (event.key === 'Tab') {
        event.preventDefault();
        // Get center of viewport for menu position
        const wrapper = reactFlowWrapper.current;
        if (wrapper) {
          const rect = wrapper.getBoundingClientRect();
          const centerX = rect.left + rect.width / 2;
          const centerY = rect.top + rect.height / 2;
          const flowPos = screenToFlowPosition({ x: centerX, y: centerY });
          setMenuState({
            screenPosition: { x: centerX - 140, y: centerY - 100 },
            flowPosition: flowPos,
          });
        }
        return;
      }

      if (event.key === 'Delete' || event.key === 'Backspace') {
        const selectedNodeId = useGraphStore.getState().selectedNodeId;
        if (selectedNodeId) {
          deleteNode(selectedNodeId);
        }
      }

      // Escape closes menu
      if (event.key === 'Escape' && menuState) {
        setMenuState(null);
      }
    },
    [deleteNode, screenToFlowPosition, menuState]
  );

  // Handle right-click context menu
  const onContextMenu = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      const flowPos = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      setMenuState({
        screenPosition: { x: event.clientX, y: event.clientY },
        flowPosition: flowPos,
      });
    },
    [screenToFlowPosition]
  );

  // Close menu
  const closeMenu = useCallback(() => {
    setMenuState(null);
  }, []);

  // Handle drag and drop from node library OR files
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      // Check for node type from library
      const nodeType = event.dataTransfer.getData('application/opencomp-node-type');
      if (nodeType) {
        addNode(nodeType, position.x, position.y);
        return;
      }

      // Check for dropped files (images/sequences)
      // In Electron, File objects have a 'path' property
      const files = Array.from(event.dataTransfer.files) as Array<File & { path: string }>;
      if (files.length > 0) {
        let offsetY = 0;
        for (const file of files) {
          const ext = '.' + file.name.split('.').pop()?.toLowerCase();
          if (IMAGE_EXTENSIONS.includes(ext) && file.path) {
            // Create a Read node for each dropped image
            addReadNode(file.path, position.x, position.y + offsetY);
            offsetY += 120; // Stack multiple nodes vertically
          }
        }
      }
    },
    [screenToFlowPosition, addNode, addReadNode]
  );

  return (
    <div
      ref={reactFlowWrapper}
      className="node-canvas"
      onKeyDown={onKeyDown}
      onContextMenu={onContextMenu}
      tabIndex={0}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onSelectionChange={onSelectionChange}
        onDragOver={onDragOver}
        onDrop={onDrop}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        snapToGrid
        snapGrid={[15, 15]}
        defaultEdgeOptions={{
          type: 'smoothstep',
          style: { stroke: 'var(--socket-image)', strokeWidth: 2 },
          animated: false,
        }}
        connectionLineType={ConnectionLineType.SmoothStep}
        connectionLineStyle={{ stroke: 'var(--brand-primary)', strokeWidth: 2 }}
        onConnectStart={() => console.log('[ReactFlow] Connection started')}
        onConnectEnd={() => console.log('[ReactFlow] Connection ended')}
        proOptions={{ hideAttribution: true }}
        minZoom={0.1}
        maxZoom={4}
        fitView
        fitViewOptions={{ padding: 0.2 }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#333"
        />
        <MiniMap
          nodeColor={(node) => {
            const data = node.data as { nodeType?: string } | undefined;
            const nodeType = data?.nodeType;
            if (!nodeType) return '#444';
            if (nodeType.includes('viewer')) return 'var(--brand-primary)';
            if (nodeType.includes('read')) return 'var(--socket-image)';
            if (nodeType.includes('write')) return '#4488ff';
            if (nodeType.includes('grade') || nodeType.includes('cdl')) return '#4488ff';
            if (nodeType.includes('merge') || nodeType.includes('over')) return '#66ffaa';
            return '#555';
          }}
          maskColor="rgba(0, 0, 0, 0.85)"
          position="bottom-right"
          pannable
          zoomable
        />
      </ReactFlow>

      {/* Nuke-style Tab Menu */}
      {menuState && (
        <NodeMenu
          position={menuState.screenPosition}
          flowPosition={menuState.flowPosition}
          onClose={closeMenu}
        />
      )}
    </div>
  );
};

export default NodeCanvas;
