import { useEffect } from 'react';
import { useDispatch } from 'react-redux';

import { apiSlice } from '../store/apiSlice';
import { useWebSocket } from '../hooks/useWebSocket';

export const GlobalWebSocket = () => {
  const { isConnected, lastMessage, sendMessage } = useWebSocket('/ws');
  const dispatch = useDispatch();

  useEffect(() => {
    if (isConnected) {
      console.warn('GlobalWebSocket connected securely');
      // Optional: send an initial handshake message
      // sendMessage('Hello from Frontend via WebSocket');
    } else {
      console.warn('GlobalWebSocket disconnected');
    }
  }, [isConnected, sendMessage]);

  useEffect(() => {
    if (lastMessage) {
      try {
        const payload = JSON.parse(lastMessage);
        if (payload.type === 'NEW_NOTIFICATION') {
          dispatch(apiSlice.util.invalidateTags(['Notification']));
        }
      } catch {
        // Ignore non-JSON messages or parse errors
      }
    }
  }, [lastMessage, dispatch]);

  return null;
};
