import { create } from 'zustand';
import {
  Node,
  Edge,
  NodeChange,
  EdgeChange,
  Connection,
  applyNodeChanges,
  applyEdgeChanges,
} from '@xyflow/react';

// Node type definition from backend
interface NodeTypeInfo {
  type: string;
  label: string;
  icon: string;
}

interface NodeCategories {
  [category: string]: NodeTypeInfo[];
}

// Custom node data - must extend Record<string, unknown>
interface OpenCompNodeData extends Record<string, unknown> {
  label: string;
  nodeType: string;
  inputs: { name: string; type: string }[];
  outputs: { name: string; type: string }[];
  params: Record<string, unknown>;
}

// Type alias for our nodes
type OpenCompNode = Node<OpenCompNodeData>;

interface GraphState {
  // React Flow state
  nodes: OpenCompNode[];
  edges: Edge[];

  // Node types from backend
  nodeTypes: NodeCategories;

  // Selection state
  selectedNodeId: string | null;
  selectedNode: OpenCompNode | null;

  // Viewer state
  activeViewerId: string | null;

  // Timeline state
  currentFrame: number;
  frameStart: number;
  frameEnd: number;
  isPlaying: boolean;

  // Actions
  setNodes: (nodes: OpenCompNode[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: (changes: NodeChange<OpenCompNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;

  loadGraphState: (state: unknown) => void;
  loadNodeTypes: (categories: NodeCategories) => void;

  addNode: (nodeType: string, x: number, y: number) => Promise<void>;
  addReadNode: (filePath: string, x: number, y: number) => Promise<void>;
  deleteNode: (nodeId: string) => Promise<void>;
  updateNodePosition: (nodeId: string, x: number, y: number) => Promise<void>;
  setNodeParam: (nodeId: string, param: string, value: unknown) => Promise<void>;

  selectNode: (nodeId: string | null) => void;
  setActiveViewer: (viewerId: string | null) => void;

  // Timeline actions
  setCurrentFrame: (frame: number) => void;
  setFrameRange: (start: number, end: number) => void;
  setIsPlaying: (playing: boolean) => void;
  nextFrame: () => void;
  prevFrame: () => void;
  goToStart: () => void;
  goToEnd: () => void;
}

// Default node types available immediately (before backend connects)
const defaultNodeTypes: NodeCategories = {
  'Input/Output': [
    { type: 'OC_N_read', label: 'Read', icon: 'FILE_IMAGE' },
    { type: 'OC_N_write', label: 'Write', icon: 'FILE_TICK' },
    { type: 'OC_N_viewer', label: 'Viewer', icon: 'RESTRICT_VIEW_OFF' },
  ],
  'Color': [
    { type: 'OC_N_grade', label: 'Grade', icon: 'COLOR' },
    { type: 'OC_N_cdl', label: 'CDL', icon: 'COLORSET_03_VEC' },
    { type: 'OC_N_constant', label: 'Constant', icon: 'IMAGE_RGB' },
  ],
  'Filter': [
    { type: 'OC_N_blur', label: 'Blur', icon: 'SMOOTHCURVE' },
    { type: 'OC_N_sharpen', label: 'Sharpen', icon: 'SHARPCURVE' },
  ],
  'Merge': [
    { type: 'OC_N_over', label: 'Over', icon: 'SELECT_SUBTRACT' },
    { type: 'OC_N_merge', label: 'Merge', icon: 'SELECT_EXTEND' },
    { type: 'OC_N_shuffle', label: 'Shuffle', icon: 'UV_SYNC_SELECT' },
  ],
  'Transform': [
    { type: 'OC_N_transform', label: 'Transform', icon: 'ORIENTATION_LOCAL' },
    { type: 'OC_N_crop', label: 'Crop', icon: 'SELECT_SET' },
  ],
};

export const useGraphStore = create<GraphState>((set, get) => ({
  nodes: [],
  edges: [],
  nodeTypes: defaultNodeTypes,
  selectedNodeId: null,
  selectedNode: null,
  activeViewerId: null,

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  onNodesChange: (changes) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes) as OpenCompNode[],
    });

    // Handle position changes - sync to backend
    for (const change of changes) {
      if (change.type === 'position' && change.position && change.dragging === false) {
        // Node finished dragging, sync to backend
        get().updateNodePosition(change.id, change.position.x, change.position.y);
      }
    }
  },

  onEdgesChange: (changes) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
  },

  onConnect: async (connection) => {
    if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) {
      return;
    }

    // Add edge locally first for immediate feedback
    const newEdge: Edge = {
      id: `${connection.source}-${connection.sourceHandle}-${connection.target}-${connection.targetHandle}`,
      source: connection.source,
      target: connection.target,
      sourceHandle: connection.sourceHandle,
      targetHandle: connection.targetHandle,
    };

    set({ edges: [...get().edges, newEdge] });

    // Check if we're connecting to a viewer node
    const targetNode = get().nodes.find(n => n.id === connection.target);
    const isViewerTarget = targetNode?.data.nodeType === 'OC_N_viewer';

    // Sync to backend and trigger evaluation if connecting to viewer
    if (window.opencomp) {
      try {
        await window.opencomp.connect(
          connection.source,
          connection.sourceHandle,
          connection.target,
          connection.targetHandle
        );

        // Trigger evaluation if connected to a viewer
        if (isViewerTarget) {
          set({ activeViewerId: connection.target });
          await window.opencomp.evaluate(connection.target);
        }
      } catch (err) {
        // Backend sync failed - that's OK, frontend graph still works
        console.warn('[Store] Backend connection sync failed (frontend graph preserved):', err);
      }
    }
  },

  loadGraphState: (state) => {
    if (!state || typeof state !== 'object') return;
    const s = state as { nodes?: unknown[]; connections?: unknown[] };
    if (!s.nodes) return;

    // Convert backend nodes to React Flow nodes
    const nodes: OpenCompNode[] = (s.nodes as Array<{
      id: string;
      type: string;
      label: string;
      x: number;
      y: number;
      inputs?: { name: string; type: string }[];
      outputs?: { name: string; type: string }[];
      params?: Record<string, unknown>;
    }>).map((n) => ({
      id: n.id,
      type: 'opencompNode',
      position: { x: n.x, y: n.y },
      data: {
        label: n.label,
        nodeType: n.type,
        inputs: n.inputs || [],
        outputs: n.outputs || [],
        params: n.params || {},
      },
    }));

    // Convert backend connections to React Flow edges
    const edges: Edge[] = ((s.connections || []) as Array<{
      from_node: string;
      from_port: string;
      to_node: string;
      to_port: string;
    }>).map((c) => ({
      id: `${c.from_node}-${c.from_port}-${c.to_node}-${c.to_port}`,
      source: c.from_node,
      target: c.to_node,
      sourceHandle: c.from_port,
      targetHandle: c.to_port,
    }));

    set({ nodes, edges });

    // Set active viewer if there's a viewer node
    const viewerNode = nodes.find((n) => n.data.nodeType === 'OC_N_viewer');
    if (viewerNode) {
      set({ activeViewerId: viewerNode.id });
    }
  },

  loadNodeTypes: (categories) => {
    set({ nodeTypes: categories });
  },

  addNode: async (nodeType, x, y) => {
    // Configure inputs/outputs based on node type
    let inputs = [{ name: 'Image', type: 'OC_NS_image' }];
    let outputs = [{ name: 'Image', type: 'OC_NS_image' }];

    // Viewer has no outputs, Read has no inputs
    if (nodeType === 'OC_N_viewer') {
      outputs = [];
    } else if (nodeType === 'OC_N_read') {
      inputs = [];
    }

    // Try to create on backend first to get the real ID
    let nodeId = `node_${Date.now()}`; // Fallback ID

    if (window.opencomp) {
      try {
        const result = await window.opencomp.createNode(nodeType, x, y);
        if (result.status === 'ok' && result.node_id) {
          nodeId = result.node_id;
        }
      } catch {
        // Backend sync failed - use local ID
      }
    }

    const newNode: OpenCompNode = {
      id: nodeId,
      type: 'opencompNode',
      position: { x, y },
      data: {
        label: nodeType.replace('OC_N_', ''),
        nodeType,
        inputs,
        outputs,
        params: {},
      },
    };
    set({ nodes: [...get().nodes, newNode] });

    // If it's a viewer node, set it as the active viewer
    if (nodeType === 'OC_N_viewer') {
      set({ activeViewerId: nodeId });
    }
  },

  addReadNode: async (filePath, x, y) => {
    // Extract filename for label
    const fileName = filePath.split('/').pop() || filePath.split('\\').pop() || 'Read';

    // Try to create on backend first to get the real ID
    let nodeId = `read_${Date.now()}`; // Fallback ID

    if (window.opencomp) {
      try {
        const result = await window.opencomp.createNode('OC_N_read', x, y);
        if (result.status === 'ok' && result.node_id) {
          nodeId = result.node_id;
          // Set the file path on the backend node
          await window.opencomp.setNodeParam(nodeId, 'filepath', filePath);
        }
      } catch {
        // Backend sync failed - use local ID
      }
    }

    const newNode: OpenCompNode = {
      id: nodeId,
      type: 'opencompNode',
      position: { x, y },
      data: {
        label: fileName,
        nodeType: 'OC_N_read',
        inputs: [],
        outputs: [{ name: 'Image', type: 'OC_NS_image' }],
        params: { filepath: filePath },
      },
    };
    set({ nodes: [...get().nodes, newNode] });
  },

  deleteNode: async (nodeId) => {
    // Remove locally first
    set({
      nodes: get().nodes.filter((n) => n.id !== nodeId),
      edges: get().edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
    });

    // Sync to backend
    if (window.opencomp) {
      try {
        await window.opencomp.deleteNode(nodeId);
      } catch (err) {
        console.error('[Store] Failed to delete node:', err);
      }
    }
  },

  updateNodePosition: async (nodeId, x, y) => {
    if (window.opencomp) {
      try {
        await window.opencomp.moveNode(nodeId, x, y);
      } catch {
        // Backend sync failed - that's OK, frontend graph still works
        // This happens when nodes are created locally without backend sync
      }
    }
  },

  setNodeParam: async (nodeId, param, value) => {
    // Update locally
    set({
      nodes: get().nodes.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, params: { ...n.data.params, [param]: value } } }
          : n
      ),
    });

    // Sync to backend (optional - frontend works independently)
    if (window.opencomp) {
      try {
        await window.opencomp.setNodeParam(nodeId, param, value);

        // Trigger evaluation if there's an active viewer
        const activeViewerId = get().activeViewerId;
        if (activeViewerId) {
          await window.opencomp.evaluate(activeViewerId);
        }
      } catch {
        // Backend sync failed - frontend still works independently
      }
    }
  },

  selectNode: (nodeId) => {
    const node = nodeId ? get().nodes.find((n) => n.id === nodeId) : null;
    set({
      selectedNodeId: nodeId,
      selectedNode: node || null,
    });
  },

  setActiveViewer: (viewerId) => {
    set({ activeViewerId: viewerId });
  },

  // Timeline state
  currentFrame: 1,
  frameStart: 1,
  frameEnd: 100,
  isPlaying: false,

  // Timeline actions
  setCurrentFrame: (frame) => {
    const { frameStart, frameEnd } = get();
    const clampedFrame = Math.max(frameStart, Math.min(frameEnd, frame));
    set({ currentFrame: clampedFrame });
  },

  setFrameRange: (start, end) => {
    const { currentFrame } = get();
    const clampedCurrent = Math.max(start, Math.min(end, currentFrame));
    set({ frameStart: start, frameEnd: end, currentFrame: clampedCurrent });
  },

  setIsPlaying: (playing) => {
    set({ isPlaying: playing });
  },

  nextFrame: () => {
    const { currentFrame, frameEnd, frameStart } = get();
    if (currentFrame >= frameEnd) {
      set({ currentFrame: frameStart }); // Loop back to start
    } else {
      set({ currentFrame: currentFrame + 1 });
    }
  },

  prevFrame: () => {
    const { currentFrame, frameStart, frameEnd } = get();
    if (currentFrame <= frameStart) {
      set({ currentFrame: frameEnd }); // Loop to end
    } else {
      set({ currentFrame: currentFrame - 1 });
    }
  },

  goToStart: () => {
    set({ currentFrame: get().frameStart });
  },

  goToEnd: () => {
    set({ currentFrame: get().frameEnd });
  },
}));

export type { OpenCompNodeData, OpenCompNode };
