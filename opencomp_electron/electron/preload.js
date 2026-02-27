/**
 * OpenComp Electron Preload Script
 *
 * Exposes a secure API to the renderer process.
 * Uses contextBridge to avoid exposing Node.js to the web content.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose a safe API to the renderer
contextBridge.exposeInMainWorld('opencomp', {
  // Graph operations
  getGraphState: () => ipcRenderer.invoke('get-graph-state'),
  getNodeTypes: () => ipcRenderer.invoke('get-node-types'),

  createNode: (nodeType, x, y) =>
    ipcRenderer.invoke('node-create', { nodeType, x, y }),

  deleteNode: (nodeId) =>
    ipcRenderer.invoke('node-delete', { nodeId }),

  moveNode: (nodeId, x, y) =>
    ipcRenderer.invoke('node-move', { nodeId, x, y }),

  setNodeParam: (nodeId, param, value) =>
    ipcRenderer.invoke('node-set-param', { nodeId, param, value }),

  connect: (fromNode, fromPort, toNode, toPort) =>
    ipcRenderer.invoke('connect', { fromNode, fromPort, toNode, toPort }),

  disconnect: (fromNode, fromPort, toNode, toPort) =>
    ipcRenderer.invoke('disconnect', { fromNode, fromPort, toNode, toPort }),

  // Evaluation
  evaluate: (viewerNodeId) =>
    ipcRenderer.invoke('evaluate', { viewerNodeId }),

  getViewerBuffer: (viewerNodeId) =>
    ipcRenderer.invoke('get-viewer-buffer', { viewerNodeId }),

  // Project operations
  newProject: () => ipcRenderer.invoke('new-project'),
  openProject: () => ipcRenderer.invoke('open-project'),
  saveProject: () => ipcRenderer.invoke('save-project'),

  // Utility
  ping: () => ipcRenderer.invoke('ping'),

  // File dialogs
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),

  // Image file reading for viewer
  readImageFile: (filePath, frame) => ipcRenderer.invoke('read-image-file', { filePath, frame }),

  // Read rendered output from shared memory
  readViewerShm: () => ipcRenderer.invoke('read-viewer-shm'),

  // Event listeners
  onBackendReady: (callback) => {
    ipcRenderer.on('backend-ready', callback);
    return () => ipcRenderer.removeListener('backend-ready', callback);
  },

  onBackendEvent: (callback) => {
    ipcRenderer.on('backend-event', (_, event) => callback(event));
    return () => ipcRenderer.removeListener('backend-event', callback);
  },

  onViewerUpdated: (callback) => {
    const handler = (_, event) => {
      if (event.event === 'viewer_updated') {
        callback(event);
      }
    };
    ipcRenderer.on('backend-event', handler);
    return () => ipcRenderer.removeListener('backend-event', handler);
  },
});

// Also expose platform info
contextBridge.exposeInMainWorld('platform', {
  isElectron: true,
  platform: process.platform,
  arch: process.arch,
});
