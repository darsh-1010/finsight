import React, { useState, useEffect } from "react";
import { PiCaretLeftBold, PiCaretRightBold } from "react-icons/pi";
import { useParams, useNavigate } from "react-router-dom";

import ChatBody from "@/components/chatbot/ChatBody";
import ChatHistorySidebar from "@/components/chatbot/ChatHistorySidebar";
import ChatInput from "@/components/chatbot/ChatInput";
import { cn } from "@/lib/utils";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  addMessage,
  addConversation,
  removeConversation,
  fetchSessionById,
  setActiveConversation,
  sendMessage,
  selectActiveConversation,
  selectConversations,
  setChatError,
  selectIsBotTyping,
  selectChatError,
  type Message,
} from "@/store/slices/chatSlice";
import WelcomeScreen from "@/components/chatbot/WelcomeScreen";
import { chatApi } from "@/api/chat";
import { tokensApi } from "@/api/tokens";
import { useAlert } from "@/context/AlertContext";
import { AlertTriangle, X } from "lucide-react";
import { PROFILE_SUBSCRIPTION_PATH } from "@/lib/profileRoutes";

/* -------------------- Hook -------------------- */

const AVAILABALE_DAILY_TOKEN_BUFFER = 5000;

type SendMessageHandler = (
  content: string,
  files: File[],
) => void | Promise<boolean | void>;

const getAvailableTokenBalance = async () => {
  const usage = await tokensApi.getUsage();

  const availableTokens = Number(usage.available_tokens);
  const dailyTokenLimit = Number(usage.daily_token_limit);
  const dailyTokensUsed = Number(usage.daily_tokens_used);

  const dailyTokensLeft = dailyTokenLimit - dailyTokensUsed;
  const tokensLeft = Math.min(availableTokens, dailyTokensLeft);
  const finalBalance = Number.isFinite(tokensLeft) ? tokensLeft : 0;

  return {
    tokensLeft: finalBalance,
    dailyTokensUsed,
    dailyTokenLimit,
  };
};

const useSendMessage = (
  conversationId: string | undefined,
  setIsUploading: (v: boolean) => void,
  onTokenLimitExceeded: () => void,
) => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { showAlert } = useAlert();

  const hasEnoughAvailableTokens = async () => {
    try {
      const { tokensLeft, dailyTokensUsed, dailyTokenLimit } = await getAvailableTokenBalance();

      console.log("[Token Check] tokensLeft:", tokensLeft);

      if (tokensLeft <= AVAILABALE_DAILY_TOKEN_BUFFER) {
        onTokenLimitExceeded();
        return false;
      }

      // Alert if 75% or more of daily tokens are used
      if (dailyTokenLimit > 0) {
        const percentUsed = (dailyTokensUsed / dailyTokenLimit) * 100;
        if (percentUsed >= 75) {
          showAlert(
            "Daily Token Limit Warning",
            `You have used ${Math.round(percentUsed)}% of your daily token limit. Once your daily limit is reached, you will need to wait for the next refill or upgrade your plan.`
          );
        }
      }

      return true;
    } catch (error) {
      console.error("[Token Check Error]", error);

      showAlert(
        "Unable to Check Token Usage",
        "We could not verify your daily token balance right now. Please try again shortly.",
      );
      return false;
    }
  };

  const handleSendMessage = async (content: string, files: File[] = []) => {
    if (!content.trim() && files.length === 0) return false;

    // ── Global token validation for ALL message types ──────────────────
    const hasTokens = await hasEnoughAvailableTokens();

    if (!hasTokens) {
      return false;
    }
    // ───────────────────────────────────────────────────────────────────

    dispatch(setChatError(null));

    let currentSessionId = conversationId;
    let isNewSession = false;

    // ── Attachment upload gate ──────────────────────────────────────────
    let attachmentIds: string[] = [];

    if (files.length > 0) {
      setIsUploading(true);

      try {
        if (!currentSessionId) {
          const title = content.trim() ? content.slice(0, 50) : (files[0]?.name || "New Chat").slice(0, 50);
          const newSession = await chatApi.createSession({
            title: title,
            model: "standard",
          });

          currentSessionId = newSession.session_id;
          isNewSession = true;
        }

        const uploadResult = await chatApi.uploadAttachments(
          currentSessionId,
          files,
        );

        console.log("[Attachment Upload Result]", uploadResult);

        const failed = uploadResult.results.filter((r) => !r.attached);

        if (failed.length > 0) {
          const details = failed
            .map((r) => `• ${r.filename}: ${r.message}`)
            .join("\n");

          showAlert(
            "Attachment Upload Failed",
            `The following file(s) could not be attached:\n\n${details}\n\nPlease upload a smaller file and try again.`,
          );

          if (isNewSession) {
            await chatApi.deleteSession(currentSessionId).catch(() => {});
          }

          return false;
        }

        attachmentIds = uploadResult.results
          .filter((r) => r.id)
          .map((r) => r.id as string);

        console.log("[Attachment IDs]", attachmentIds);
      } catch (err) {
        console.error("[Attachment Upload Error]", err);

        if (isNewSession && currentSessionId) {
          await chatApi.deleteSession(currentSessionId).catch(() => {});
        }

        showAlert(
          "Attachment Error",
          "An unexpected error occurred while uploading your files. Please try again.",
        );

        return false;
      } finally {
        setIsUploading(false);
      }
    }
    // ───────────────────────────────────────────────────────────────────

    if (!currentSessionId) {
      dispatch(
        sendMessage({
          sessionId: "null",
          content,
          model: "standard",
          attachment_ids: attachmentIds,
          onSessionCreated: (id) =>
            navigate(`/ask_finsight/c/${id}`, { replace: true }),
        }),
      );

      return true;
    }

    const optimisticAttachments = files.map((f, i) => ({
      id: attachmentIds[i] || `temp-${Date.now()}-${i}`,
      file_name: f.name,
      file_type: f.type,
      file_size: f.size,
      status: "uploaded",
      created_at: new Date().toISOString(),
    }));

    if (isNewSession) {
      const title = content.trim() ? content.slice(0, 50) : (files[0]?.name || "New Chat").slice(0, 50);
      dispatch(
        addConversation({
          id: currentSessionId,
          title: title,
          firstMessage: content.trim() ? content : (files.length > 0 ? "Uploaded files" : ""),
          attachments: optimisticAttachments,
        }),
      );

      navigate(`/ask_finsight/c/${currentSessionId}`, { replace: true });

      dispatch(setActiveConversation(currentSessionId));
    } else {
      dispatch(
        addMessage({
          conversationId: currentSessionId,
          message: { role: "user", content },
          attachments: optimisticAttachments,
        }),
      );
    }

    dispatch(
      sendMessage({
        sessionId: currentSessionId,
        content,
        model: "standard",
        attachment_ids: attachmentIds,
      }),
    ).then(async (result) => {
      if (sendMessage.rejected.match(result) && isNewSession) {
        try {
          await chatApi.deleteSession(currentSessionId);
        } catch (e) {
          console.error("Failed to delete session", e);
        }

        dispatch(removeConversation(currentSessionId));
        navigate("/ask_finsight", { replace: true });
      }
    });

    return true;
  };

  return handleSendMessage;
};

const useAskFinSight = () => {
  const { conversationId } = useParams<{ conversationId?: string }>();

  const activeConversation = useAppSelector(selectActiveConversation);
  const conversations = useAppSelector(selectConversations);
  const isBotTyping = useAppSelector(selectIsBotTyping);
  const chatError = useAppSelector(selectChatError);
  const dispatch = useAppDispatch();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    window.innerWidth < 768,
  );
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [isUploading, setIsUploading] = useState(false);
  const [isTokenLimitModalOpen, setIsTokenLimitModalOpen] = useState(false);

  const handleSendMessage = useSendMessage(
    conversationId,
    setIsUploading,
    () => setIsTokenLimitModalOpen(true)
  );

  return {
    conversationId,
    activeConversation,
    conversations,
    isBotTyping,
    chatError,
    sidebarCollapsed,
    setSidebarCollapsed,
    isMobile,
    setIsMobile,
    handleSendMessage,
    dispatch,
    isUploading,
    isTokenLimitModalOpen,
    setIsTokenLimitModalOpen,
  };
};
/* -------------------- Effects Hook -------------------- */

const useAskFinSightEffects = (
  conversationId: string | undefined,
  conversations: ReturnType<typeof selectConversations>,
  dispatch: ReturnType<typeof useAppDispatch>,
  isMobile: boolean,
  setSidebarCollapsed: (v: boolean) => void,
  setIsMobile: (v: boolean) => void,
) => {
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };

    window.addEventListener("resize", handleResize);

    return () => window.removeEventListener("resize", handleResize);
  }, [setIsMobile]);

  useEffect(() => {
    if (!conversationId) {
      dispatch(setActiveConversation(null));

      return;
    }

    dispatch(setActiveConversation(conversationId));

    const exists = conversations.some((c) => c.id === conversationId);

    if (!exists) {
      dispatch(fetchSessionById(conversationId));
    }

    if (isMobile) {
      setTimeout(() => setSidebarCollapsed(true), 0);
    }
  }, [conversationId, conversations, dispatch, isMobile, setSidebarCollapsed]);
};

/* -------------------- UI Components -------------------- */

interface SidebarProps {
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean) => void;
  isMobile: boolean;
}

const AskSidebar: React.FC<SidebarProps> = ({
  sidebarCollapsed,
  setSidebarCollapsed,
  isMobile,
}) => (
  <div className="hidden md:block h-full bg-white dark:bg-[#08070A] border-r border-gray-100 dark:border-gray-800">
    <ChatHistorySidebar
      sidebarCollapsed={sidebarCollapsed}
      setSidebarCollapsed={setSidebarCollapsed}
      isMobile={isMobile}
      mainSidebarCollapsed={false}
    />
  </div>
);

const TokenLimitSnackbar = ({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) => {
  const navigate = useNavigate();
  if (!isOpen) return null;
  return (
    <div className="w-full flex justify-center px-2 sm:px-4 mb-2 shrink-0 animate-in fade-in slide-in-from-bottom-4">
      <div className="w-full max-w-4xl p-3 sm:p-4 bg-orange-50 dark:bg-[#1A1005] border border-orange-200 dark:border-orange-900/50 rounded-2xl shadow-lg flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <AlertTriangle className="h-5 w-5 text-orange-500 shrink-0" />
          <p className="text-sm text-orange-800 dark:text-orange-200 text-balance">
            <strong>Daily Limit Exceeded.</strong> You have reached your daily token limit. Wait until tomorrow or upgrade.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button 
            onClick={() => { onClose(); navigate(PROFILE_SUBSCRIPTION_PATH); }}
            className="text-xs sm:text-sm font-bold px-3 py-1.5 sm:px-4 sm:py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
          >
            Upgrade
          </button>
          <button 
            onClick={onClose}
            className="p-1 sm:p-2 text-orange-600 dark:text-orange-400 hover:bg-orange-100 dark:hover:bg-orange-900/30 rounded-lg transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

interface ChatContentProps {
  messages: Message[];
  isTyping: boolean;
  error: string | null;
  onSend: SendMessageHandler;
  disabled: boolean;
  isUploading: boolean;
  tokenLimitSnackbar?: React.ReactNode;
}

const ChatContent: React.FC<ChatContentProps> = ({
  messages,
  isTyping,
  error,
  onSend,
  disabled,
  isUploading,
  tokenLimitSnackbar,
}) => (
  <>
    <ChatBody
      messages={messages}
      isTyping={isTyping}
      error={error}
      onSend={onSend}
    />
    {tokenLimitSnackbar}
    <ChatInput
      onSend={onSend}
      disabled={disabled}
      isWelcome
      isUploading={isUploading}
    />
  </>
);

interface ToggleProps {
  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean) => void;
}

const SidebarToggle: React.FC<ToggleProps> = ({
  sidebarCollapsed,
  setSidebarCollapsed,
}) => (
  <button
    onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
    className={cn(
      "absolute z-50 top-1/2 -translate-y-1/2 hidden md:block bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-full p-1.5 shadow-sm hover:shadow-md transition-all duration-300",
      sidebarCollapsed ? "-left-1" : "left-0 -translate-x-1/2",
    )}
  >
    {sidebarCollapsed ? (
      <PiCaretRightBold size={14} />
    ) : (
      <PiCaretLeftBold size={14} />
    )}
  </button>
);

/* -------------------- Main Component -------------------- */

interface AskContentProps {
  conversationId?: string;
  chatError: string | null;
  isBotTyping: boolean;
  activeConversation: ReturnType<typeof selectActiveConversation>;
  onSend: SendMessageHandler;
  isUploading: boolean;
  tokenLimitSnackbar?: React.ReactNode;
}

const AskContent: React.FC<AskContentProps> = ({
  conversationId,
  chatError,
  isBotTyping,
  activeConversation,
  onSend,
  isUploading,
  tokenLimitSnackbar,
}) => {
  if (!conversationId) {
    return (
      <WelcomeScreen
        onSend={onSend}
        disabled={!!chatError}
        isUploading={isUploading}
        tokenLimitSnackbar={tokenLimitSnackbar}
      />
    );
  }

  return (
    <ChatContent
      messages={activeConversation?.messages || []}
      isTyping={isBotTyping}
      error={chatError}
      onSend={onSend}
      disabled={!!chatError}
      isUploading={isUploading}
      tokenLimitSnackbar={tokenLimitSnackbar}
    />
  );
};

interface AskFinSightContainerProps {
  state: ReturnType<typeof useAskFinSight>;
}

const AskFinSightContainer: React.FC<AskFinSightContainerProps> = ({ state }) => {
  const {
    conversationId,
    conversations,
    dispatch,
    isMobile,
    setSidebarCollapsed,
    setIsMobile,
  } = state;

  useAskFinSightEffects(
    conversationId,
    conversations,
    dispatch,
    isMobile,
    setSidebarCollapsed,
    setIsMobile,
  );

  return null;
};

const AskFinSight: React.FC = () => {
  const state = useAskFinSight();

  const {
    conversationId,
    activeConversation,
    isBotTyping,
    chatError,
    sidebarCollapsed,
    setSidebarCollapsed,
    isMobile,
    handleSendMessage,
    isUploading,
    isTokenLimitModalOpen,
    setIsTokenLimitModalOpen,
  } = state;

  return (
    <div className="flex flex-1 h-[calc(100vh-144px)] md:h-[calc(100vh-64px)] overflow-hidden">
      <AskFinSightContainer state={state} />

      <AskSidebar
        sidebarCollapsed={sidebarCollapsed}
        setSidebarCollapsed={setSidebarCollapsed}
        isMobile={isMobile}
      />

      <section className="flex-1 flex flex-col relative">
        <SidebarToggle
          sidebarCollapsed={sidebarCollapsed}
          setSidebarCollapsed={setSidebarCollapsed}
        />

        <AskContent
          conversationId={conversationId}
          chatError={chatError}
          isBotTyping={isBotTyping}
          activeConversation={activeConversation}
          onSend={handleSendMessage}
          isUploading={isUploading}
          tokenLimitSnackbar={
            <TokenLimitSnackbar 
              isOpen={isTokenLimitModalOpen} 
              onClose={() => setIsTokenLimitModalOpen(false)} 
            />
          }
        />
      </section>
    </div>
  );
};

export default AskFinSight;
