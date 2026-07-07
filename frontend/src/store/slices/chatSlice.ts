import { createSlice, createAsyncThunk, type PayloadAction, type ActionReducerMapBuilder } from '@reduxjs/toolkit';

import type { AppDispatch } from '../store';

import { chatApi } from '@/api/chat';
import { apiSlice } from '@/store/apiSlice';






export interface Attachment {
  id: string;
  file_name: string;
  file_type?: string;
  file_size?: number;
  storage_url?: string;
  status: string;
  created_at: string;
}

export interface Source {
  source: string;
  url: string;
  id: string;
  source_type?: string;
  data_type?: string;
  confidence?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'bot';
  content: string;
  timestamp: string;
  suggestedFollowUps?: string[];
  sources?: Source[];
  attachments?: Attachment[];
}

export interface RawMessage {
  id?: string | number;
  role: string;
  content: string;
  created_at?: string;
  attachments?: Attachment[];
  suggested_follow_ups?: string[];
}

export interface RawSession {
  session_id: string;
  id: number;
  messages: RawMessage[];
  title?: string;
  started_at: string;
}

export interface StreamContext {
  actualSessionId: string;
  botMessageId: string;
  content: string;
  fullContent: string;
  onSessionCreated?: (id: string) => void;
}

export interface Conversation {
  id: string; // This will map to session_id (UUID)
  dbId?: number; // Internal DB ID if needed
  title: string;
  snippet: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  isBotTyping: boolean;
  error: string | null;
  isLoadingSessions: boolean;
}

const initialState: ChatState = {
  conversations: [],
  activeConversationId: null,
  isBotTyping: false,
  error: null,
  isLoadingSessions: false,
};

// Async Thunks
export const fetchSessions = createAsyncThunk(
  'chat/fetchSessions',
  async (_, { rejectWithValue }) => {
    try {
      const sessions = await chatApi.getSessions();

      return sessions;
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };

      return rejectWithValue(err.response?.data?.message || 'Failed to fetch sessions');
    }
  }
);

const selectActiveConversationInternal = (state: { chat: ChatState }) => {
  const activeId = state.chat.activeConversationId;

  return state.chat.conversations.find(c => c.id === activeId);
};

export const retryLastMessage = createAsyncThunk(
  'chat/retryLastMessage',
  async (_, { dispatch, getState, rejectWithValue }) => {
    const state = getState() as { chat: ChatState };
    const conversation = selectActiveConversationInternal(state);
    
    if (!conversation) return rejectWithValue('No active conversation');
    
    return handleLastUserMessageRetry(conversation, 'standard', dispatch as AppDispatch, rejectWithValue);
  }
);

const handleLastUserMessageRetry = (
  conversation: Conversation,
  model: string,
  dispatch: AppDispatch,
  rejectWithValue: (v: string) => unknown
) => {
  const lastUserMsg = [...conversation.messages].reverse().find(m => m.role === 'user');
  
  if (!lastUserMsg) return rejectWithValue('No user message to retry');
  
  dispatch(setChatError(null));
  const payload = { sessionId: conversation.id, content: lastUserMsg.content, model };

  return dispatch(sendMessage(payload));
};


interface ChatMetadata {
  suggested_follow_ups?: string[];
  sources?: Source[];
  reference_video_link?: string;
}

const handleParsedStreamData = (
  parsed: { type: string; data: string | ChatMetadata },
  dispatch: AppDispatch,
  context: StreamContext
) => {
  if (parsed.type === 'error') {
    return handleStreamError(parsed.data as string, dispatch, context);
  }

  if (parsed.type === 'session_id') {
    handleSessionCreation(parsed.data as string, dispatch, context);
  } else if ((parsed.type === 'content' || parsed.type === 'content_block_delta') && parsed.data) {
    updateStreamingContent(parsed.data as string, dispatch, context);
  } else if (parsed.type === 'sources' && Array.isArray(parsed.data)) {
    dispatch(updateMessageMetadata({
      conversationId: context.actualSessionId,
      messageId: context.botMessageId,
      sources: parsed.data as Source[]
    }));
  } else if (parsed.type === 'metadata' && typeof parsed.data === 'object' && parsed.data !== null) {
    const dataObj = parsed.data as ChatMetadata;

    if (dataObj.suggested_follow_ups || dataObj.sources) {
      dispatch(updateMessageMetadata({
        conversationId: context.actualSessionId,
        messageId: context.botMessageId,
        suggestedFollowUps: dataObj.suggested_follow_ups,
        sources: dataObj.sources,
      }));
    }
  }
};

const handleStreamError = (data: string, dispatch: AppDispatch, context: StreamContext) => {
  dispatch(setChatError(data || 'An error occurred during streaming'));
  dispatch(removeMessage({ conversationId: context.actualSessionId, messageId: context.botMessageId }));
};

const handleSessionCreation = (sessionId: string, dispatch: AppDispatch, context: StreamContext) => {
  context.actualSessionId = sessionId;
  dispatch(addConversation({
    id: sessionId,
    title: context.content.slice(0, 50) + (context.content.length > 50 ? '...' : ''),
    firstMessage: context.content
  }));
  dispatch(addMessage({ conversationId: sessionId, message: { role: 'bot', content: '' }, id: context.botMessageId }));

  if (context.onSessionCreated) context.onSessionCreated(sessionId);
};

const updateStreamingContent = (data: string, dispatch: AppDispatch, context: StreamContext) => {
  context.fullContent += data;
  dispatch(updateMessageContent({
    conversationId: context.actualSessionId,
    messageId: context.botMessageId,
    newContent: context.fullContent
  }));
};

const createStreamHandler = (
  dispatch: AppDispatch,
  context: StreamContext
) => {
  let buffer = '';

  const processLine = (line: string) => {
    const trimmed = line.trim();

    if (!trimmed || trimmed === 'data: [DONE]') return;
    if (trimmed.startsWith('data: ')) {
      try {
        handleParsedStreamData(JSON.parse(trimmed.substring(6)), dispatch, context);
      } catch { /* ignore */ }
    }
  };

  return (chunk: string) => {
    buffer += chunk;

    const lines = buffer.split('\n');

    buffer = lines.pop() || '';
    lines.forEach(processLine);
  };
};

export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async (
    payload: {
      sessionId: string,
      content: string,
      model: string,
      attachment_ids?: string[],
      onSessionCreated?: (id: string) => void
    },
    { dispatch, rejectWithValue }
  ) => {
    try {
      return await performMessageStreaming(payload, dispatch as AppDispatch);
    } catch (error: unknown) {
      const err = error as { message?: string };

      return rejectWithValue(err.message || 'Failed to send message');
    } finally {
      dispatch(setBotTyping(false));
      dispatch(apiSlice.util.invalidateTags(['TokenUsage']));
    }
  }
);

export const fetchSessionById = createAsyncThunk(
  'chat/fetchSessionById',
  async (sessionId: string, { rejectWithValue }) => {
    try {
      // WORKAROUND: The backend endpoint GET /chat/sessions/{uuid} returns 422 (likely expecting int ID).
      // Since the list endpoint returns full session details including messages, 
      // we fetch the list and find the session by UUID locally.
      const session = await chatApi.getSessionById(sessionId);
        
      if (session) {
        return session;
      } else {
        return rejectWithValue('Session not found');
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };

      return rejectWithValue(err.response?.data?.message || 'Failed to fetch session details');
    }
  }
);

export const deleteSession = createAsyncThunk(
  'chat/deleteSession',
  async (sessionId: string, { dispatch, getState, rejectWithValue }) => {
    try {
      await chatApi.deleteSession(sessionId);
      handlePostDeleteSync(sessionId, dispatch, getState);

      return sessionId;
    } catch (error: unknown) {
      const err = error as { response?: { data?: { message?: string } } };

      return rejectWithValue(err.response?.data?.message || 'Failed to delete session');
    }
  }
);

const extractFollowUps = (content: string): { cleanContent: string; followUps?: string[] } => {
  const marker = '\n\n### Suggested Questions\n';
  const index = content.indexOf(marker);
  if (index === -1) return { cleanContent: content };
  
  const cleanContent = content.substring(0, index);
  const followUpsText = content.substring(index + marker.length);
  const followUps = followUpsText.split('\n')
    .map(line => line.trim())
    .filter(line => line.startsWith('- '))
    .map(line => line.substring(2).trim());
    
  return { cleanContent, followUps: followUps.length > 0 ? followUps : undefined };
};

const mapSessionToConversation = (
  session: RawSession,
  existingConversation?: Conversation | null
): Conversation => {
  const messages: Message[] = session.messages.map((msg: RawMessage) => {
    const { cleanContent, followUps } = extractFollowUps(msg.content);
    return {
      id: (msg.id || Date.now()).toString(),
      role: msg.role as 'user' | 'bot',
      content: cleanContent,
      timestamp: new Date(msg.created_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      attachments: msg.attachments,
      suggestedFollowUps: msg.suggested_follow_ups && msg.suggested_follow_ups.length > 0 
        ? msg.suggested_follow_ups 
        : followUps
    };
  });

  const finalMessages = (messages.length === 0 && existingConversation)
    ? existingConversation.messages
    : messages;

  const titleText = (session.title && session.title !== 'string') ? session.title : '';
  const firstMsg = finalMessages.length > 0 ? finalMessages[0].content : '';
  
  const defaultTitle = titleText || (firstMsg 
    ? (firstMsg.slice(0, 30) + (firstMsg.length > 30 ? '...' : '')) 
    : 'New Chat');

  return {
    id: session.session_id,
    dbId: session.id,
    title: defaultTitle,
    snippet: finalMessages.length > 0 ? finalMessages[finalMessages.length - 1].content : '',
    messages: finalMessages,
    createdAt: session.started_at,
    updatedAt: session.started_at
  };
};

const attachFetchSessionsCases = (builder: ActionReducerMapBuilder<ChatState>) => {
  builder.addCase(fetchSessions.pending, (state: ChatState) => {
    state.isLoadingSessions = true;
    state.error = null;
  });

  builder.addCase(fetchSessions.fulfilled, (state: ChatState, action: PayloadAction<RawSession[]>) => {
    state.isLoadingSessions = false;
    state.conversations = action.payload.map((s: RawSession) => mapSessionToConversation(s));
  });

  builder.addCase(fetchSessions.rejected, (state: ChatState, action) => {
    state.isLoadingSessions = false;
    state.error = action.payload as string;
  });
};

const attachDeleteSessionCases = (builder: ActionReducerMapBuilder<ChatState>) => {
  builder.addCase(deleteSession.fulfilled, (state: ChatState, action: PayloadAction<string>) => {
    const sessionId = action.payload;

    state.conversations = state.conversations.filter(c => c.id !== sessionId);

    if (state.activeConversationId === sessionId) state.activeConversationId = null;
  });

  builder.addCase(deleteSession.rejected, (state: ChatState, action) => {
    state.error = action.payload as string;
  });

};

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    // Optimistic creation (can be used for immediate UI feedback if needed, 
    // but we are moving to async now)
    addConversation: (state, action: PayloadAction<{ id: string; title: string; firstMessage: string; attachments?: Attachment[] }>) => {
      const { id, title, firstMessage, attachments } = action.payload;

      if (!state.conversations.find(c => c.id === id)) {
        state.conversations.unshift({
          id,
          title,
          snippet: firstMessage,
          messages: [{
            id: Date.now().toString(),
            role: 'user',
            content: firstMessage,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            attachments: attachments || []
          }],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        });
      }
    },
    removeConversation: (state, action: PayloadAction<string>) => {
      const sessionId = action.payload;
      state.conversations = state.conversations.filter(c => c.id !== sessionId);
      if (state.activeConversationId === sessionId) {
        state.activeConversationId = null;
      }
    },
    addMessage: (state, action: PayloadAction<{ conversationId: string; message: Omit<Message, 'id' | 'timestamp'>, id?: string, attachments?: Attachment[] }>) => {
      const { conversationId, message, id, attachments } = action.payload;
      const conversation = state.conversations.find(c => c.id === conversationId);

      if (conversation) {
        const newMessage: Message = {
          ...message,
          id: id || (Date.now().toString() + Math.random().toString(36).substring(7)),
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          attachments: attachments || [],
        };

        conversation.messages.push(newMessage);
        conversation.updatedAt = new Date().toISOString();
        if (message.role === 'user') conversation.snippet = message.content;
      }
    },
    removeMessage: (state, action: PayloadAction<{ conversationId: string; messageId: string }>) => {
      const { conversationId, messageId } = action.payload;
      const conversation = state.conversations.find(c => c.id === conversationId);

      if (conversation) {
        conversation.messages = conversation.messages.filter(m => m.id !== messageId);
        conversation.updatedAt = new Date().toISOString();
      }
    },
    updateMessageContent: (
      state, 
      action: PayloadAction<{ conversationId: string; messageId: string; newContent: string }>
    ) => {
      const { conversationId, messageId, newContent } = action.payload;
      const conv = state.conversations.find(c => c.id === conversationId);

      if (!conv) return;

      const message = conv.messages.find(m => m.id === messageId);

      if (message) {
        message.content = newContent;
        conversationSyncAfterUpdate(conv, newContent);
      }
    },
    updateMessageMetadata: (
      state,
      action: PayloadAction<{ 
        conversationId: string; 
        messageId: string; 
        suggestedFollowUps?: string[];
        sources?: Source[];
      }>
    ) => {
      const { conversationId, messageId, suggestedFollowUps, sources } = action.payload;
      const conv = state.conversations.find(c => c.id === conversationId);

      if (!conv) return;

      const message = conv.messages.find(m => m.id === messageId);

      if (message) {
        if (suggestedFollowUps) message.suggestedFollowUps = suggestedFollowUps;
        if (sources) message.sources = sources;
      }
    },
    setActiveConversation: (state, action: PayloadAction<string | null>) => {
      state.activeConversationId = action.payload;
    },
    clearActiveConversation: (state) => {
      state.activeConversationId = null;
    },
    setBotTyping: (state, action: PayloadAction<boolean>) => {
      state.isBotTyping = action.payload;
    },
    setChatError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },

  },
  extraReducers: (builder) => {
    attachFetchSessionsCases(builder);
    attachDeleteSessionCases(builder);

    builder.addCase(fetchSessionById.fulfilled, (state, action) => {
      handleFetchSessionByIdFulfilled(state, action);
    });

    builder.addCase(sendMessage.fulfilled, (state, action) => {
      handleSendMessageFulfilled(state, action);
    });

    builder.addCase(sendMessage.rejected, (state, action) => {
      state.error = action.payload as string;
    });
  }
});

export const { 
  addConversation, 
  addMessage, 
  removeMessage,
  removeConversation,
  setActiveConversation, 
  clearActiveConversation,
  updateMessageContent,
  updateMessageMetadata,
  setBotTyping,
  setChatError,
} = chatSlice.actions;

export const selectConversations = (state: { chat: ChatState }) => state.chat.conversations;
export const selectActiveConversationId = (state: { chat: ChatState }) => (
  state.chat.activeConversationId
);
export const selectActiveConversation = (state: { chat: ChatState }) => (
  state.chat.conversations.find(c => c.id === state.chat.activeConversationId)
);
export const selectIsBotTyping = (state: { chat: ChatState }) => state.chat.isBotTyping;
export const selectChatError = (state: { chat: ChatState }) => state.chat.error;

export const selectIsLoadingSessions = (state: { chat: ChatState }) => state.chat.isLoadingSessions;

const initStreamBotMessage = (sessionId: string, botMessageId: string, dispatch: AppDispatch) => {
  dispatch(setBotTyping(true));
  if (sessionId !== 'null') {
    dispatch(addMessage({ conversationId: sessionId, message: { role: 'bot', content: '' }, id: botMessageId }));
  }
};

const performMessageStreaming = async (
  payload: {
    sessionId: string,
    content: string,
    model: string,
    attachment_ids?: string[],
    onSessionCreated?: (id: string) => void
  },
  dispatch: AppDispatch
) => {
  const { sessionId, content, model, attachment_ids, onSessionCreated } = payload;
  const botMessageId = 'bot-' + Date.now().toString();
  const context = { actualSessionId: sessionId, botMessageId, content, fullContent: '', onSessionCreated };

  initStreamBotMessage(sessionId, botMessageId, dispatch);

  await chatApi.sendMessageStream(sessionId, content, model, createStreamHandler(dispatch, context), attachment_ids);

  return { sessionId: context.actualSessionId, botMessageId, content: context.fullContent };
};

const handlePostDeleteSync = (sessionId: string, dispatch: (action: unknown) => unknown, getState: () => unknown) => {
  const state = getState() as { chat: ChatState };

  if (state.chat.activeConversationId === sessionId) {
    dispatch(setActiveConversation(null));
  }
};

const handleFetchSessionByIdFulfilled = (
  state: ChatState,
  action: PayloadAction<RawSession>
) => {
  const session = action.payload;
  const index = state.conversations.findIndex(c => c.id === session.session_id);
  const existing = index !== -1 ? state.conversations[index] : null;
  const updated = mapSessionToConversation(session, existing);

  if (index !== -1) {
    state.conversations[index] = updated;
  } else {
    state.conversations.unshift(updated);
  }
};

const handleSendMessageFulfilled = (
  state: ChatState, 
  action: PayloadAction<{ sessionId: string; botMessageId: string; content: string }>
) => {
  const { sessionId, botMessageId, content } = action.payload;
  const conversation = state.conversations.find(c => c.id === sessionId);

  if (conversation) {
    const message = conversation.messages.find(m => m.id === botMessageId);

    if (message) message.content = content;
    conversation.updatedAt = new Date().toISOString();
    conversation.snippet = content;
  }
};

const conversationSyncAfterUpdate = (conv: Conversation, content: string) => {
  conv.updatedAt = new Date().toISOString();
  conv.snippet = content;
};

export default chatSlice.reducer;
