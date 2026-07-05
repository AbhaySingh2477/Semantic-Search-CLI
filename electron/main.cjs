const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let backendProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      // Consider adding a preload script if you need IPC later
    },
    titleBarStyle: 'hiddenInset', // looks good on macOS
  });

  if (app.isPackaged) {
    // In production, load the built Vite frontend
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  } else {
    // In dev, connect to the Vite dev server
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  }
}

function startBackend() {
  let command;
  let args = [];
  let cwd = __dirname;

  if (app.isPackaged) {
    // In production, the pyinstaller binary is packaged in resources
    const platform = process.platform;
    const binaryName = platform === 'win32' ? 'notebook-backend.exe' : 'notebook-backend';
    command = path.join(process.resourcesPath, 'backend-dist', binaryName);
    cwd = path.join(process.resourcesPath, 'backend-dist');
  } else {
    // In dev, run the python script directly using the virtual environment
    command = path.join(__dirname, '../backend/.venv/bin/python');
    args = [path.join(__dirname, '../backend/main.py')];
    cwd = path.join(__dirname, '../backend');
  }

  console.log('Starting backend:', command, args.join(' '));

  backendProcess = spawn(command, args, { cwd });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend ERR] ${data}`);
  });

  backendProcess.on('close', (code) => {
    console.log(`[Backend] exited with code ${code}`);
  });
}

function waitForBackend(url, timeout = 30000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    
    const check = () => {
      http.get(url, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          retry();
        }
      }).on('error', retry);
    };

    const retry = () => {
      if (Date.now() - startTime > timeout) {
        reject(new Error('Backend timeout'));
      } else {
        setTimeout(check, 1000);
      }
    };

    check();
  });
}

app.whenReady().then(async () => {
  startBackend();
  
  try {
    console.log('Waiting for backend to be ready...');
    // Wait for the backend health check to pass
    await waitForBackend('http://127.0.0.1:8741/api/health');
    console.log('Backend is ready. Creating window.');
    createWindow();
  } catch (error) {
    console.error('Failed to start backend:', error);
    dialog.showErrorBox('Initialization Error', 'Failed to start the local AI backend. Please check the logs.');
    app.quit();
  }

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

// Clean up backend process on exit
app.on('before-quit', () => {
  if (backendProcess) {
    console.log('Killing backend process...');
    backendProcess.kill();
  }
});
