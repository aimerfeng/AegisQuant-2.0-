/**
 * Titan-Quant WebSocket Client Service
 * 
 * Provides WebSocket connection management with:
 * - Automatic reconnection with exponential backoff
 * - Heartbeat/ping-pong mechanism
 * - Message queue for offline messages
 * - Type-safe message handling
 * 
 * Requirements: 1.1, 1.4
 */

import { MessageType, Message, MessageHandler, WebSocketConfig } from '../types/websocket';

// Default configuration
const DEFAULT_CONFIG: WebSocketConfig = {
  url: 'ws://localhost:8765',
  reconnectInterval: 1000,
  maxReconnectInterval: 30000,
  reconnectDecay: 1.5,
  maxReconnectAttempts: 10,
  heartbeatInterval: 30000,
  heartbeatTimeout: 10000,
};

export interface WebSocketCallbacks {
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Error) => void;
  onMessage?: (message: Message) => void;
  onReconnecting?: (attempt: number) => void;
}

export class WebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private callbacks: WebSocketCallbacks;
  private messageHandlers: Map<MessageType, Set<MessageHandler>> = new Map();
  private messageQueue: Message[] = [];
  private reconnectAttempts: number = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private isManualClose: boolean = false;
  private messageIdCounter: number = 0;

  constructor(url?: string, callbacks?: WebSocketCallbacks) {
    this.config = {
      ...DEFAULT_CONFIG,
      url: url || DEFAULT_CONFIG.url,
    };
    this.callbacks = callbacks || {};
  }

  /**
   * Connect to WebSocket server
   */
  public connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.warn('[WebSocket] Already connected');
      return;
    }

    this.isManualClose = false;
    this.createConnection();
  }

  /**
   * Disconnect from WebSocket server
   */
  public disconnect(): void {
    this.isManualClose = true;
    this.cleanup();
    
    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
      this.ws = null;
    }
  }

  /**
   * Send a message to the server
   */
  public send<T = unknown>(type: MessageType, payload: T): string {
    const message: Message<T> = {
      id: this.generateMessageId(),
      type,
      timestamp: Date.now(),
      payload,
    };

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      // Queue message for later delivery
      this.messageQueue.push(message as Message);
      console.warn('[WebSocket] Connection not open, message queued');
    }

    return message.id;
  }

  /**
   * Subscribe to a specific message type
   */
  public subscribe(type: MessageType, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        handlers.delete(handler);
      }
    };
  }

  /**
   * Check if connected
   */
  public isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get current connection state
   */
  public getReadyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }

  // Private methods

  private createConnection(): void {
    try {
      this.ws = new WebSocket(this.config.url);
      this.setupEventHandlers();
    } catch (error) {
      console.error('[WebSocket] Failed to create connection:', error);
      this.handleError(error as Error);
    }
  }

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('[WebSocket] Connected to', this.config.url);
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.flushMessageQueue();
      this.callbacks.onOpen?.();
    };

    this.ws.onclose = (event) => {
      console.log('[WebSocket] Connection closed:', event.code, event.reason);
      this.cleanup();
      this.callbacks.onClose?.();

      if (!this.isManualClose) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (event) => {
      console.error('[WebSocket] Error:', event);
      this.handleError(new Error('WebSocket error'));
    };

    this.ws.onmessage = (event) => {
      this.handleMessage(event.data);
    };
  }

  private handleMessage(data: string): void {
    try {
      const message: Message = JSON.parse(data);

      // Handle heartbeat response
      if (message.type === MessageType.HEARTBEAT) {
        this.handleHeartbeatResponse();
        return;
      }

      // Notify global callback
      this.callbacks.onMessage?.(message);

      // Notify type-specific handlers
      const handlers = this.messageHandlers.get(message.type);
      if (handlers) {
        handlers.forEach((handler) => {
          try {
            handler(message);
          } catch (error) {
            console.error('[WebSocket] Handler error:', error);
          }
        });
      }
    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error);
    }
  }

  private handleError(error: Error): void {
    this.callbacks.onError?.(error);
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnect attempts reached');
      this.handleError(new Error('Max reconnect attempts reached'));
      return;
    }

    const delay = Math.min(
      this.config.reconnectInterval * Math.pow(this.config.reconnectDecay, this.reconnectAttempts),
      this.config.maxReconnectInterval
    );

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);
    
    this.callbacks.onReconnecting?.(this.reconnectAttempts + 1);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.createConnection();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();

    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send(MessageType.HEARTBEAT, { ping: Date.now() });
        
        // Set timeout for heartbeat response
        this.heartbeatTimeoutTimer = setTimeout(() => {
          console.warn('[WebSocket] Heartbeat timeout, reconnecting...');
          this.ws?.close(4000, 'Heartbeat timeout');
        }, this.config.heartbeatTimeout);
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private handleHeartbeatResponse(): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message && this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(message));
      }
    }
  }

  private cleanup(): void {
    this.stopHeartbeat();
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private generateMessageId(): string {
    return `msg_${Date.now()}_${++this.messageIdCounter}`;
  }
}

// Singleton instance for global access
let globalWebSocketService: WebSocketService | null = null;

export function getWebSocketService(): WebSocketService {
  if (!globalWebSocketService) {
    globalWebSocketService = new WebSocketService();
  }
  return globalWebSocketService;
}

export function initWebSocketService(url: string, callbacks?: WebSocketCallbacks): WebSocketService {
  globalWebSocketService = new WebSocketService(url, callbacks);
  return globalWebSocketService;
}
