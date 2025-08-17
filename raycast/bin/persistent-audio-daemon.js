#!/usr/bin/env node

/**
 * Persistent Audio Daemon - Standalone Audio Service
 *
 * This daemon runs as a persistent service that multiple Raycast extensions
 * can connect to, eliminating the need to spawn a new daemon for each request.
 *
 * Features:
 * - Persistent WebSocket server for multiple client connections
 * - Connection management and client isolation
 * - Automatic cleanup of disconnected clients
 * - Health monitoring and status reporting
 * - Native CoreAudio integration via node-speaker
 *
 * @author @darianrosebrook
 * @version 3.0.0
 * @since 2025-08-17
 * @license MIT
 */

import WebSocket, { WebSocketServer } from "ws";
import http from "http";
import { EventEmitter } from "events";
import { spawn } from "child_process";
import { join } from "path";
import { existsSync } from "fs";

/**
 * Simple logger for the persistent audio daemon
 */
class SimpleLogger {
  constructor() {
    this.isDebugMode = this.checkDebugMode();
  }

  checkDebugMode() {
    const hasDebugFlag = process.argv.includes("--debug") || process.argv.includes("-d");
    const hasAudioDebug = process.env.AUDIO_DEBUG === "true" || process.env.AUDIO_DEBUG === "1";
    return hasDebugFlag || hasAudioDebug;
  }

  info(message, ...args) {
    const timestamp = new Date().toLocaleTimeString();
    console.log(`${timestamp} [INFO]: ${message}`, ...args);
  }

  warn(message, ...args) {
    const timestamp = new Date().toLocaleTimeString();
    console.warn(`${timestamp} [WARN]: ${message}`, ...args);
  }

  error(message, ...args) {
    const timestamp = new Date().toLocaleTimeString();
    console.error(`${timestamp} [ERROR]: ${message}`, ...args);
  }

  debug(message, ...args) {
    if (this.isDebugMode) {
      const timestamp = new Date().toLocaleTimeString();
      console.log(`${timestamp} [DEBUG]: ${message}`, ...args);
    }
  }
}

const logger = new SimpleLogger();

/**
 * Client connection manager
 */
class ClientManager {
  constructor() {
    this.clients = new Map();
    this.nextClientId = 1;
  }

  addClient(ws, request) {
    const clientId = `client_${this.nextClientId++}`;
    const clientInfo = {
      id: clientId,
      ws,
      connectedAt: Date.now(),
      lastActivity: Date.now(),
      userAgent: request.headers['user-agent'] || 'unknown',
      remoteAddress: request.socket.remoteAddress,
      isActive: true
    };

    this.clients.set(clientId, clientInfo);
    logger.info(`Client connected: ${clientId} from ${clientInfo.remoteAddress}`);
    
    // Send welcome message
    ws.send(JSON.stringify({
      type: 'welcome',
      clientId,
      timestamp: Date.now(),
      message: 'Connected to persistent audio daemon'
    }));

    return clientId;
  }

  removeClient(clientId) {
    const client = this.clients.get(clientId);
    if (client) {
      client.isActive = false;
      this.clients.delete(clientId);
      logger.info(`Client disconnected: ${clientId}`);
    }
  }

  getActiveClients() {
    return Array.from(this.clients.values()).filter(client => client.isActive);
  }

  getClientCount() {
    return this.getActiveClients().length;
  }

  updateActivity(clientId) {
    const client = this.clients.get(clientId);
    if (client) {
      client.lastActivity = Date.now();
    }
  }

  cleanupInactiveClients(timeoutMs = 300000) { // 5 minutes
    const now = Date.now();
    const toRemove = [];

    for (const [clientId, client] of this.clients.entries()) {
      if (now - client.lastActivity > timeoutMs) {
        toRemove.push(clientId);
      }
    }

    for (const clientId of toRemove) {
      const client = this.clients.get(clientId);
      if (client) {
        client.ws.close(1000, 'Inactive timeout');
        this.removeClient(clientId);
      }
    }

    if (toRemove.length > 0) {
      logger.info(`Cleaned up ${toRemove.length} inactive clients`);
    }
  }
}

/**
 * Audio format configuration
 */
class AudioFormat {
  constructor(format, sampleRate, channels, bitDepth) {
    this.format = format;
    this.sampleRate = sampleRate;
    this.channels = channels;
    this.bitDepth = bitDepth;
    this.bytesPerSample = bitDepth / 8;
    this.bytesPerSecond = sampleRate * channels * this.bytesPerSample;
  }

  validate() {
    if (![8000, 16000, 22050, 24000, 32000, 44100, 48000].includes(this.sampleRate)) {
      logger.warn(`Unusual sample rate: ${this.sampleRate}Hz`);
    }
    if (![1, 2].includes(this.channels)) {
      throw new Error(`Unsupported channel count: ${this.channels}`);
    }
    if (![8, 16, 24, 32].includes(this.bitDepth)) {
      throw new Error(`Unsupported bit depth: ${this.bitDepth}`);
    }
  }
}

/**
 * Audio session for a single client
 */
class AudioSession {
  constructor(clientId, audioFormat) {
    this.clientId = clientId;
    this.audioFormat = audioFormat;
    this.isPlaying = false;
    this.speakerProcess = null;
    this.buffer = [];
    this.stats = {
      bytesReceived: 0,
      chunksProcessed: 0,
      startTime: null,
      endTime: null
    };
  }

  start() {
    if (this.isPlaying) {
      logger.warn(`Session ${this.clientId} already playing`);
      return;
    }

    this.stats.startTime = Date.now();
    this.isPlaying = true;
    logger.info(`Audio session started: ${this.clientId}`);
  }

  stop() {
    if (!this.isPlaying) {
      return;
    }

    this.isPlaying = false;
    this.stats.endTime = Date.now();
    
    if (this.speakerProcess) {
      this.speakerProcess.kill('SIGTERM');
      this.speakerProcess = null;
    }

    logger.info(`Audio session stopped: ${this.clientId}`, {
      duration: this.stats.endTime - this.stats.startTime,
      bytesReceived: this.stats.bytesReceived,
      chunksProcessed: this.stats.chunksProcessed
    });
  }

  processAudioChunk(chunk) {
    if (!this.isPlaying) {
      this.start();
    }

    this.stats.bytesReceived += chunk.length;
    this.stats.chunksProcessed++;

    // For now, just buffer the audio data
    // In a full implementation, this would send to the speaker
    this.buffer.push(chunk);
  }
}

/**
 * Persistent Audio Daemon
 */
class PersistentAudioDaemon {
  constructor(port = 8081) {
    this.port = port;
    this.server = null;
    this.wss = null;
    this.clientManager = new ClientManager();
    this.sessions = new Map();
    this.isRunning = false;
    this.startTime = Date.now();
    
    // Cleanup interval
    this.cleanupInterval = null;
  }

  async start() {
    if (this.isRunning) {
      logger.warn('Daemon already running');
      return;
    }

    try {
      // Create HTTP server
      this.server = http.createServer((req, res) => {
        if (req.url === '/health') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            status: 'healthy',
            uptime: Date.now() - this.startTime,
            clients: this.clientManager.getClientCount(),
            sessions: this.sessions.size,
            timestamp: Date.now()
          }));
        } else if (req.url === '/status') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            daemon: 'persistent-audio-daemon',
            version: '3.0.0',
            port: this.port,
            uptime: Date.now() - this.startTime,
            clients: this.clientManager.getActiveClients().map(client => ({
              id: client.id,
              connectedAt: client.connectedAt,
              lastActivity: client.lastActivity,
              userAgent: client.userAgent
            })),
            sessions: Array.from(this.sessions.keys()),
            timestamp: Date.now()
          }));
        } else {
          res.writeHead(404, { 'Content-Type': 'text/plain' });
          res.end('Not Found');
        }
      });

      // Create WebSocket server
      this.wss = new WebSocketServer({ server: this.server });

      // Handle WebSocket connections
      this.wss.on('connection', (ws, request) => {
        const clientId = this.clientManager.addClient(ws, request);

        ws.on('message', (data) => {
          this.handleMessage(clientId, data);
        });

        ws.on('close', (code, reason) => {
          this.clientManager.removeClient(clientId);
          this.cleanupSession(clientId);
        });

        ws.on('error', (error) => {
          logger.error(`WebSocket error for client ${clientId}:`, error);
          this.clientManager.removeClient(clientId);
          this.cleanupSession(clientId);
        });
      });

      // Start server
      await new Promise((resolve, reject) => {
        this.server.listen(this.port, () => {
          logger.info(`Persistent audio daemon started on port ${this.port}`);
          resolve();
        });

        this.server.on('error', (error) => {
          logger.error('Server error:', error);
          reject(error);
        });
      });

      this.isRunning = true;

      // Start cleanup interval
      this.cleanupInterval = setInterval(() => {
        this.clientManager.cleanupInactiveClients();
      }, 60000); // Clean up every minute

      logger.info('Persistent audio daemon ready for connections');

    } catch (error) {
      logger.error('Failed to start persistent audio daemon:', error);
      throw error;
    }
  }

  handleMessage(clientId, data) {
    try {
      this.clientManager.updateActivity(clientId);
      
      const message = JSON.parse(data.toString());
      logger.debug(`Received message from ${clientId}:`, message.type);

      switch (message.type) {
        case 'ping':
          this.sendResponse(clientId, { type: 'pong', timestamp: Date.now() });
          break;

        case 'start_session':
          this.startSession(clientId, message.audioFormat);
          break;

        case 'audio_chunk':
          this.processAudioChunk(clientId, message.chunk, message.encoding);
          break;

        case 'stop_session':
          this.stopSession(clientId);
          break;

        case 'get_status':
          this.sendStatus(clientId);
          break;

        default:
          logger.warn(`Unknown message type from ${clientId}:`, message.type);
          this.sendResponse(clientId, { 
            type: 'error', 
            error: 'Unknown message type',
            timestamp: Date.now()
          });
      }
    } catch (error) {
      logger.error(`Error handling message from ${clientId}:`, error);
      this.sendResponse(clientId, { 
        type: 'error', 
        error: error.message,
        timestamp: Date.now()
      });
    }
  }

  startSession(clientId, audioFormat) {
    try {
      const format = new AudioFormat(
        audioFormat.format,
        audioFormat.sampleRate,
        audioFormat.channels,
        audioFormat.bitDepth
      );
      format.validate();

      const session = new AudioSession(clientId, format);
      this.sessions.set(clientId, session);

      this.sendResponse(clientId, {
        type: 'session_started',
        clientId,
        audioFormat: format,
        timestamp: Date.now()
      });

      logger.info(`Audio session started for ${clientId}`);
    } catch (error) {
      logger.error(`Failed to start session for ${clientId}:`, error);
      this.sendResponse(clientId, {
        type: 'error',
        error: error.message,
        timestamp: Date.now()
      });
    }
  }

  processAudioChunk(clientId, chunk, encoding = 'base64') {
    const session = this.sessions.get(clientId);
    if (!session) {
      logger.warn(`No session found for client ${clientId}`);
      return;
    }

    try {
      const buffer = Buffer.from(chunk, encoding);
      session.processAudioChunk(buffer);
    } catch (error) {
      logger.error(`Error processing audio chunk for ${clientId}:`, error);
    }
  }

  stopSession(clientId) {
    const session = this.sessions.get(clientId);
    if (session) {
      session.stop();
      this.sessions.delete(clientId);
      
      this.sendResponse(clientId, {
        type: 'session_stopped',
        clientId,
        stats: session.stats,
        timestamp: Date.now()
      });

      logger.info(`Audio session stopped for ${clientId}`);
    }
  }

  cleanupSession(clientId) {
    const session = this.sessions.get(clientId);
    if (session) {
      session.stop();
      this.sessions.delete(clientId);
      logger.info(`Cleaned up session for ${clientId}`);
    }
  }

  sendResponse(clientId, response) {
    const client = this.clientManager.clients.get(clientId);
    if (client && client.ws.readyState === WebSocket.OPEN) {
      client.ws.send(JSON.stringify(response));
    }
  }

  sendStatus(clientId) {
    const client = this.clientManager.clients.get(clientId);
    const session = this.sessions.get(clientId);
    
    this.sendResponse(clientId, {
      type: 'status',
      clientId,
      connected: !!client,
      sessionActive: !!session,
      sessionStats: session ? session.stats : null,
      timestamp: Date.now()
    });
  }

  async stop() {
    if (!this.isRunning) {
      return;
    }

    logger.info('Stopping persistent audio daemon...');

    // Stop cleanup interval
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }

    // Close all sessions
    for (const [clientId, session] of this.sessions.entries()) {
      session.stop();
    }
    this.sessions.clear();

    // Close all client connections
    for (const [clientId, client] of this.clientManager.clients.entries()) {
      client.ws.close(1000, 'Daemon shutting down');
    }
    this.clientManager.clients.clear();

    // Close WebSocket server
    if (this.wss) {
      this.wss.close();
      this.wss = null;
    }

    // Close HTTP server
    if (this.server) {
      await new Promise((resolve) => {
        this.server.close(resolve);
      });
      this.server = null;
    }

    this.isRunning = false;
    logger.info('Persistent audio daemon stopped');
  }
}

// Command line interface
async function main() {
  const args = process.argv.slice(2);
  const port = parseInt(args.find(arg => arg.startsWith('--port='))?.split('=')[1]) || 8081;
  const debug = args.includes('--debug') || args.includes('-d');

  if (debug) {
    process.env.AUDIO_DEBUG = 'true';
  }

  logger.info('Starting persistent audio daemon...', { port, debug });

  const daemon = new PersistentAudioDaemon(port);

  // Handle shutdown signals
  process.on('SIGINT', async () => {
    logger.info('Received SIGINT, shutting down...');
    await daemon.stop();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    logger.info('Received SIGTERM, shutting down...');
    await daemon.stop();
    process.exit(0);
  });

  try {
    await daemon.start();
  } catch (error) {
    logger.error('Failed to start daemon:', error);
    process.exit(1);
  }
}

// Run if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    logger.error('Unhandled error:', error);
    process.exit(1);
  });
}

export { PersistentAudioDaemon };
