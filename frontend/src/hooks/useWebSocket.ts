/* global WebSocket */
import { useEffect, useRef, useState, useCallback } from 'react';

type WebSocketHookResult = {
  isConnected: boolean;
  sendMessage: (message: string) => void;
  lastMessage: string | null;
};

const buildWsUrl = (urlPath: string): string => {
  const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL as string || '')?.replace(/\/+$/, '') || '';

  return baseUrl.replace(/^http/, 'ws') + urlPath;
};

const createWebSocket = (
  wsUrl: string,
  setIsConnected: (value: boolean) => void,
  setLastMessage: (value: string) => void,
  reconnect: () => void,
): WebSocket => {
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setIsConnected(true);
  };

  ws.onmessage = (event) => {
    setLastMessage(event.data);
  };

  ws.onclose = () => {
    setIsConnected(false);
    setTimeout(reconnect, 5000);
  };

  ws.onerror = (error) => {
    console.error('WebSocket Error:', error);
    ws.close();
  };

  return ws;
};

export const useWebSocket = (
  urlPath: string = '/ws',
): WebSocketHookResult => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    const wsUrl = buildWsUrl(urlPath);

    wsRef.current = createWebSocket(
      wsUrl,
      setIsConnected,
      (message) => setLastMessage(message),
      () => connectRef.current(),
    );
  }, [urlPath]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message);

      return;
    }

    console.warn('WebSocket is not connected.');
  }, []);

  return {
    isConnected,
    sendMessage,
    lastMessage,
  };
};