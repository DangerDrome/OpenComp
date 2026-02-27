/**
 * OpenComp Electron Main Process
 *
 * Handles:
 * - Window creation and management
 * - Blender backend process spawning
 * - IPC bridge between renderer and backend
 */

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');
const fs = require('fs');

// Configuration
const SOCKET_PATH = '/tmp/opencomp_server.sock';
const DEV_URL = 'http://localhost:5200';
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

// State
let mainWindow = null;
let blenderProcess = null;
let ipcClient = null;
let messageBuffer = '';
let requestCallbacks = new Map();
let requestIdCounter = 0;

/**
 * Get path to Blender binary - searches multiple locations
 */
function getBlenderPath() {
  const candidates = [];

  // Get the real AppImage location (not the /tmp mount point)
  const appImagePath = process.env.APPIMAGE;
  const cwd = process.cwd();

  if (app.isPackaged) {
    // 1. Inside AppImage resources (if bundled)
    candidates.push(path.join(process.resourcesPath, 'blender', 'blender'));

    if (appImagePath) {
      // 2. Next to the actual AppImage file
      const appImageDir = path.dirname(appImagePath);
      candidates.push(path.join(appImageDir, 'blender', 'blender'));

      // 3. Parent of AppImage location (if AppImage is in dist-electron/)
      candidates.push(path.join(appImageDir, '..', 'blender', 'blender'));

      // 4. Two levels up (repo root if AppImage is in opencomp_electron/dist-electron/)
      candidates.push(path.join(appImageDir, '..', '..', 'blender', 'blender'));
    }
  }

  // 5. Current working directory (where user ran the app from)
  candidates.push(path.join(cwd, 'blender', 'blender'));

  // 6. Development: repo-local Blender (relative to electron/main.js)
  candidates.push(path.join(__dirname, '..', '..', 'blender', 'blender'));

  // 7. Common system locations
  candidates.push('/usr/bin/blender');
  candidates.push('/usr/local/bin/blender');

  console.log('[Electron] Searching for Blender in:', candidates);

  // Find first existing
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      console.log('[Electron] Found Blender at:', candidate);
      return candidate;
    }
  }

  // Return first candidate for error message
  return candidates[0];
}

/**
 * Get path to headless.py script - searches multiple locations
 */
function getHeadlessScript() {
  const candidates = [];
  const appImagePath = process.env.APPIMAGE;
  const cwd = process.cwd();

  if (app.isPackaged) {
    // 1. Inside AppImage resources
    candidates.push(path.join(process.resourcesPath, 'opencomp_server', 'headless.py'));

    if (appImagePath) {
      const appImageDir = path.dirname(appImagePath);
      // 2-4. Relative to AppImage location
      candidates.push(path.join(appImageDir, 'opencomp_server', 'headless.py'));
      candidates.push(path.join(appImageDir, '..', 'opencomp_server', 'headless.py'));
      candidates.push(path.join(appImageDir, '..', '..', 'opencomp_server', 'headless.py'));
    }
  }

  // 5. Current working directory
  candidates.push(path.join(cwd, 'opencomp_server', 'headless.py'));

  // 6. Development location
  candidates.push(path.join(__dirname, '..', '..', 'opencomp_server', 'headless.py'));

  // Find first existing
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return candidates[0];
}

/**
 * Get path to opencomp_core addon - for BLENDER_USER_SCRIPTS
 */
function getAddonPath() {
  const candidates = [];
  const appImagePath = process.env.APPIMAGE;
  const cwd = process.cwd();

  if (app.isPackaged) {
    // 1. Inside AppImage resources
    candidates.push(path.join(process.resourcesPath, 'opencomp_core'));

    if (appImagePath) {
      const appImageDir = path.dirname(appImagePath);
      // 2-4. Relative to AppImage location
      candidates.push(path.join(appImageDir, 'opencomp_core'));
      candidates.push(path.join(appImageDir, '..', 'opencomp_core'));
      candidates.push(path.join(appImageDir, '..', '..', 'opencomp_core'));
    }
  }

  // 5. Current working directory
  candidates.push(path.join(cwd, 'opencomp_core'));

  // 6. Development location
  candidates.push(path.join(__dirname, '..', '..', 'opencomp_core'));

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return path.dirname(candidate); // Return parent dir for BLENDER_USER_SCRIPTS
    }
  }

  return null;
}

/**
 * Start the Blender backend process
 */
function startBlenderBackend() {
  return new Promise((resolve, reject) => {
    const blenderPath = getBlenderPath();
    const headlessScript = getHeadlessScript();
    const addonPath = getAddonPath();

    console.log('[Electron] Starting Blender backend...');
    console.log(`[Electron] Blender: ${blenderPath}`);
    console.log(`[Electron] Script: ${headlessScript}`);
    console.log(`[Electron] Addon path: ${addonPath}`);

    // Check if Blender exists
    if (!fs.existsSync(blenderPath)) {
      reject(new Error(`Blender not found at: ${blenderPath}\n\nPlease ensure Blender 5.0+ is installed in the 'blender' directory.`));
      return;
    }

    // Check if headless script exists
    if (!fs.existsSync(headlessScript)) {
      reject(new Error(`Headless script not found at: ${headlessScript}`));
      return;
    }

    // Build environment with paths for addon discovery
    const env = {
      ...process.env,
      // Ensure GPU backend is available
      __EGL_VENDOR_LIBRARY_FILENAMES: '/usr/share/glvnd/egl_vendor.d/50_mesa.json',
    };

    // Set BLENDER_USER_SCRIPTS so Blender can find the addon
    if (addonPath) {
      env.BLENDER_USER_SCRIPTS = addonPath;
      // Also add to PYTHONPATH for imports
      env.PYTHONPATH = addonPath + (env.PYTHONPATH ? ':' + env.PYTHONPATH : '');
    }

    // Spawn Blender with virtual framebuffer for GPU support
    // On Linux, use xvfb-run to provide a GPU context in headless mode
    const isLinux = process.platform === 'linux';
    let spawnCmd, spawnArgs;

    if (isLinux) {
      // Run Blender inside xvfb WITHOUT --background to enable GPU
      // The script runs headless logic but with GPU context available
      spawnCmd = 'xvfb-run';
      spawnArgs = [
        '-a',  // Auto-select display
        '--server-args=-screen 0 1920x1080x24 +extension GLX',
        blenderPath,
        '--window-geometry', '0', '0', '1', '1',  // Tiny hidden window
        '--python', headlessScript,
      ];
    } else {
      // macOS/Windows - just use background mode (may have GPU limitations)
      spawnCmd = blenderPath;
      spawnArgs = [
        '--background',
        '--python', headlessScript,
      ];
    }

    blenderProcess = spawn(spawnCmd, spawnArgs, {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: addonPath || process.cwd(),  // Set working directory
      env,
    });

    blenderProcess.stdout.on('data', (data) => {
      const output = data.toString();
      console.log('[Blender]', output.trim());

      // Check if server is ready
      if (output.includes('Ready for connections')) {
        setTimeout(() => {
          connectToBackend()
            .then(resolve)
            .catch(reject);
        }, 500);
      }
    });

    blenderProcess.stderr.on('data', (data) => {
      console.error('[Blender ERROR]', data.toString().trim());
    });

    blenderProcess.on('close', (code) => {
      console.log(`[Electron] Blender process exited with code ${code}`);
      blenderProcess = null;
    });

    blenderProcess.on('error', (err) => {
      console.error('[Electron] Failed to start Blender:', err);
      reject(err);
    });

    // Timeout if backend doesn't start in 30s
    setTimeout(() => {
      if (!ipcClient) {
        reject(new Error('Backend startup timeout'));
      }
    }, 30000);
  });
}

/**
 * Connect to the Blender backend via Unix socket
 */
function connectToBackend() {
  return new Promise((resolve, reject) => {
    console.log('[Electron] Connecting to backend...');

    ipcClient = net.createConnection(SOCKET_PATH, () => {
      console.log('[Electron] Connected to backend');
      resolve();
    });

    ipcClient.on('data', (data) => {
      messageBuffer += data.toString();

      // Parse complete messages (newline-delimited)
      let newlineIndex;
      while ((newlineIndex = messageBuffer.indexOf('\n')) !== -1) {
        const line = messageBuffer.slice(0, newlineIndex);
        messageBuffer = messageBuffer.slice(newlineIndex + 1);

        try {
          const msg = JSON.parse(line);
          handleBackendMessage(msg);
        } catch (e) {
          console.error('[Electron] Failed to parse message:', e);
        }
      }
    });

    ipcClient.on('error', (err) => {
      console.error('[Electron] IPC connection error:', err);
      if (!ipcClient.connecting) {
        reject(err);
      }
    });

    ipcClient.on('close', () => {
      console.log('[Electron] IPC connection closed');
      ipcClient = null;
    });
  });
}

/**
 * Handle messages from the backend
 */
function handleBackendMessage(msg) {
  // Check if it's a response to a request
  if (msg.id && requestCallbacks.has(msg.id)) {
    const callback = requestCallbacks.get(msg.id);
    requestCallbacks.delete(msg.id);
    callback(msg);
    return;
  }

  // It's an event - forward to renderer
  if (msg.event && mainWindow) {
    mainWindow.webContents.send('backend-event', msg);
  }
}

/**
 * Send a request to the backend and return a promise
 */
function sendRequest(cmd, params = {}) {
  return new Promise((resolve, reject) => {
    if (!ipcClient) {
      reject(new Error('Not connected to backend'));
      return;
    }

    const id = `req_${++requestIdCounter}`;
    const message = JSON.stringify({ cmd, id, ...params }) + '\n';

    requestCallbacks.set(id, (response) => {
      if (response.status === 'ok') {
        resolve(response);
      } else {
        reject(new Error(response.message || 'Request failed'));
      }
    });

    ipcClient.write(message);

    // Timeout after 30s
    setTimeout(() => {
      if (requestCallbacks.has(id)) {
        requestCallbacks.delete(id);
        reject(new Error('Request timeout'));
      }
    }, 30000);
  });
}

/**
 * Create the main application window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1024,
    minHeight: 768,
    title: 'OpenComp',
    backgroundColor: '#1a1a1a',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    // Frameless for custom title bar (optional)
    // frame: false,
    // titleBarStyle: 'hidden',
  });

  if (isDev) {
    mainWindow.loadURL(DEV_URL);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Set up IPC handlers for renderer process
 */
function setupIpcHandlers() {
  // Graph operations
  ipcMain.handle('get-graph-state', () => sendRequest('get_graph_state'));
  ipcMain.handle('get-node-types', () => sendRequest('get_node_types'));

  ipcMain.handle('node-create', (_, { nodeType, x, y }) =>
    sendRequest('node_create', { node_type: nodeType, x, y }));

  ipcMain.handle('node-delete', (_, { nodeId }) =>
    sendRequest('node_delete', { node_id: nodeId }));

  ipcMain.handle('node-move', (_, { nodeId, x, y }) =>
    sendRequest('node_move', { node_id: nodeId, x, y }));

  ipcMain.handle('node-set-param', (_, { nodeId, param, value }) =>
    sendRequest('node_set_param', { node_id: nodeId, param, value }));

  ipcMain.handle('connect', async (_, { fromNode, fromPort, toNode, toPort }) => {
    console.log('[Electron] Connect:', fromNode, fromPort, '->', toNode, toPort);
    try {
      const result = await sendRequest('connect', {
        from_node: fromNode,
        from_port: fromPort,
        to_node: toNode,
        to_port: toPort,
      });
      console.log('[Electron] Connect result:', result);
      return result;
    } catch (err) {
      console.error('[Electron] Connect error:', err);
      throw err;
    }
  });

  ipcMain.handle('disconnect', (_, { fromNode, fromPort, toNode, toPort }) =>
    sendRequest('disconnect', {
      from_node: fromNode,
      from_port: fromPort,
      to_node: toNode,
      to_port: toPort,
    }));

  // Evaluation
  ipcMain.handle('evaluate', async (_, { viewerNodeId }) => {
    console.log('[Electron] Evaluate called for viewer:', viewerNodeId);
    try {
      const result = await sendRequest('evaluate', { viewer_node_id: viewerNodeId });
      console.log('[Electron] Evaluate result:', result);
      return result;
    } catch (err) {
      console.error('[Electron] Evaluate error:', err);
      throw err;
    }
  });

  ipcMain.handle('get-viewer-buffer', (_, { viewerNodeId }) =>
    sendRequest('get_viewer_buffer', { viewer_node_id: viewerNodeId }));

  // Project operations
  ipcMain.handle('new-project', () => sendRequest('new_project'));

  ipcMain.handle('open-project', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      filters: [{ name: 'Blender Files', extensions: ['blend'] }],
      properties: ['openFile'],
    });
    if (!result.canceled && result.filePaths.length > 0) {
      return sendRequest('open_project', { path: result.filePaths[0] });
    }
    return { status: 'cancelled' };
  });

  ipcMain.handle('save-project', async () => {
    const result = await dialog.showSaveDialog(mainWindow, {
      filters: [{ name: 'Blender Files', extensions: ['blend'] }],
    });
    if (!result.canceled && result.filePath) {
      return sendRequest('save_project', { path: result.filePath });
    }
    return { status: 'cancelled' };
  });

  // Utility
  ipcMain.handle('ping', () => sendRequest('ping'));

  // File dialogs - generic for use throughout the app
  ipcMain.handle('show-open-dialog', async (_, options) => {
    const result = await dialog.showOpenDialog(mainWindow, options || {});
    return result;
  });

  ipcMain.handle('show-save-dialog', async (_, options) => {
    const result = await dialog.showSaveDialog(mainWindow, options || {});
    return result;
  });

  // Read viewer shared memory (rendered output from Blender backend)
  ipcMain.handle('read-viewer-shm', async () => {
    try {
      const shmPath = '/dev/shm/opencomp_viewer';
      if (!fs.existsSync(shmPath)) {
        return { status: 'error', message: 'Shared memory not found' };
      }

      const fd = fs.openSync(shmPath, 'r');

      // Read header (32 bytes)
      const headerBuf = Buffer.alloc(32);
      fs.readSync(fd, headerBuf, 0, 32, 0);

      const width = headerBuf.readUInt32LE(0);
      const height = headerBuf.readUInt32LE(4);
      const channels = headerBuf.readUInt32LE(8);
      const frameCounter = headerBuf.readUInt32LE(12);

      if (width === 0 || height === 0) {
        fs.closeSync(fd);
        return { status: 'error', message: 'No image data in shared memory' };
      }

      // Read float32 pixel data
      const pixelBytes = width * height * channels * 4; // 4 bytes per float
      const pixelBuf = Buffer.alloc(pixelBytes);
      fs.readSync(fd, pixelBuf, 0, pixelBytes, 32);
      fs.closeSync(fd);

      // Convert float32 to uint8 with simple tone mapping
      const rgba = new Uint8Array(width * height * 4);
      for (let i = 0; i < width * height; i++) {
        for (let c = 0; c < Math.min(channels, 4); c++) {
          const floatVal = pixelBuf.readFloatLE((i * channels + c) * 4);
          // Simple sRGB tone mapping: clamp + gamma 2.2
          const linear = Math.max(0, Math.min(1, floatVal));
          const srgb = Math.pow(linear, 1 / 2.2);
          rgba[i * 4 + c] = Math.round(srgb * 255);
        }
        // Fill alpha if not present
        if (channels < 4) {
          rgba[i * 4 + 3] = 255;
        }
      }

      // Return as base64
      const base64 = Buffer.from(rgba).toString('base64');
      return {
        status: 'ok',
        width,
        height,
        frameCounter,
        rgba_base64: base64,
      };
    } catch (err) {
      console.error('[Electron] Failed to read viewer SHM:', err);
      return { status: 'error', message: err.message };
    }
  });

  // Read image file for viewer display
  // For browser-native formats, returns base64 data URL
  // For EXR/DPX, returns metadata and pixel data when possible
  ipcMain.handle('read-image-file', async (_, { filePath, frame }) => {
    try {
      if (!filePath) {
        return { status: 'error', message: 'No file path provided' };
      }

      // Handle frame number in sequence (####, %04d patterns)
      let resolvedPath = filePath;
      if (frame !== undefined) {
        // Replace #### pattern
        resolvedPath = resolvedPath.replace(/#+/g, (match) => {
          return String(frame).padStart(match.length, '0');
        });
        // Replace %04d pattern
        resolvedPath = resolvedPath.replace(/%0(\d+)d/g, (_, digits) => {
          return String(frame).padStart(parseInt(digits), '0');
        });
      }

      if (!fs.existsSync(resolvedPath)) {
        return { status: 'error', message: `File not found: ${resolvedPath}` };
      }

      const ext = path.extname(resolvedPath).toLowerCase();
      const stats = fs.statSync(resolvedPath);

      // Browser-native formats - return as base64 data URL
      if (['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'].includes(ext)) {
        const data = fs.readFileSync(resolvedPath);
        const base64 = data.toString('base64');
        const mimeType = {
          '.png': 'image/png',
          '.jpg': 'image/jpeg',
          '.jpeg': 'image/jpeg',
          '.gif': 'image/gif',
          '.webp': 'image/webp',
          '.bmp': 'image/bmp',
        }[ext];
        return {
          status: 'ok',
          type: 'dataUrl',
          dataUrl: `data:${mimeType};base64,${base64}`,
          filePath: resolvedPath,
          size: stats.size,
        };
      }

      // For EXR/DPX/TIFF - return metadata for now
      // These would need backend processing or WebAssembly decoder
      if (['.exr', '.dpx', '.tif', '.tiff', '.hdr'].includes(ext)) {
        return {
          status: 'ok',
          type: 'rawFormat',
          format: ext.substring(1).toUpperCase(),
          filePath: resolvedPath,
          size: stats.size,
          needsConversion: true,
        };
      }

      return { status: 'error', message: `Unsupported format: ${ext}` };
    } catch (err) {
      console.error('[Electron] Failed to read image:', err);
      return { status: 'error', message: err.message };
    }
  });
}

/**
 * Application lifecycle
 */
app.whenReady().then(async () => {
  console.log('[Electron] App ready');

  setupIpcHandlers();
  createWindow();

  try {
    await startBlenderBackend();
    console.log('[Electron] Backend ready');

    // Notify renderer that backend is ready
    if (mainWindow) {
      mainWindow.webContents.send('backend-ready');
    }
  } catch (err) {
    console.error('[Electron] Failed to start backend:', err);
    dialog.showErrorBox('Backend Error',
      `Failed to start Blender backend: ${err.message}\n\nMake sure Blender is installed in the 'blender' directory.`);
  }
});

app.on('window-all-closed', () => {
  // Kill Blender process
  if (blenderProcess) {
    blenderProcess.kill();
    blenderProcess = null;
  }

  // Close IPC connection
  if (ipcClient) {
    ipcClient.end();
    ipcClient = null;
  }

  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('before-quit', () => {
  if (blenderProcess) {
    blenderProcess.kill();
  }
});
