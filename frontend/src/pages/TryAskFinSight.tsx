import React, { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";


import ChatBody from "@/components/chatbot/ChatBody";
import ChatInput from "@/components/chatbot/ChatInput";
import { chatApi } from "@/api/chat";
import TrialLimitModal from "@/components/chatbot/TrialLimitModal";
import WelcomeScreen from "@/components/chatbot/WelcomeScreen";
import TrialJoinModal from "@/components/chatbot/TrialJoinModal";
import EmailGateModal from "@/components/chatbot/EmailGateModal";
import { useAuth } from "@/context/AuthContext";
import {
  visitingUsersApi,
  storeVisitingUser,
  getStoredVisitingUser,
  clearVisitingUser,
  type VisitingUser,
} from "@/api/auth";
import type { Message } from "@/store/slices/chatSlice";

const TRIAL_LIMIT = 5;

const TryAskFinSight: React.FC = () => {
  const navigate = useNavigate();
  const { isLoggedIn, isLoading: isAuthLoading } = useAuth();

  // ── Redirect logged-in users ────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthLoading && isLoggedIn) {
      clearVisitingUser();
      navigate("/dashboard", { replace: true });
    }
  }, [isLoggedIn, isAuthLoading, navigate]);

  // ── Visiting user state (gate) ──────────────────────────────────────────
  const [visitingUser, setVisitingUser] = useState<VisitingUser | null>(() =>
    getStoredVisitingUser(),
  );

  // ── Chat state ──────────────────────────────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([]);
  const [isBotTyping, setIsBotTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // chat_count is the source of truth (synced from API); fall back to stored value
  const [chatCount, setChatCount] = useState<number>(
    () => getStoredVisitingUser()?.chat_count ?? 0,
  );

  // ── Modal flags ─────────────────────────────────────────────────────────
  const [showLimitModal, setShowLimitModal] = useState(false);
  const [showJoinModal, setShowJoinModal] = useState(false);
  const [hasShownJoinAlert3, setHasShownJoinAlert3] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Show limit modal immediately if the user has already exhausted their trial
  useEffect(() => {
    if (visitingUser && visitingUser.chat_count >= TRIAL_LIMIT) {
      setShowLimitModal(true);
    }
  }, [visitingUser]);

  // Show limit modal after bot finishes typing (when count just hit the limit)
  useEffect(() => {
    if (chatCount >= TRIAL_LIMIT && !isBotTyping && messages.length > 0) {
      const timer = setTimeout(() => setShowLimitModal(true), 800);
      return () => clearTimeout(timer);
    }
  }, [chatCount, isBotTyping, messages.length]);

  // Show join nudge modal after 3rd bot response
  useEffect(() => {
    if (!isBotTyping && messages.length > 0) {
      if (chatCount === 3 && !hasShownJoinAlert3) {
        const timer = setTimeout(() => {
          setShowJoinModal(true);
          setHasShownJoinAlert3(true);
        }, 1000);
        return () => clearTimeout(timer);
      }
    }
  }, [
    chatCount,
    isBotTyping,
    messages.length,
    hasShownJoinAlert3,
  ]);

  // ── Email gate resolved ─────────────────────────────────────────────────
  const handleEmailGateSuccess = (user: VisitingUser) => {
    setVisitingUser(user);
    setChatCount(user.chat_count);
    // Show limit modal immediately if they've already used all messages
    if (user.chat_count >= TRIAL_LIMIT) {
      setShowLimitModal(true);
    }
  };

  // ── Send message ────────────────────────────────────────────────────────
  const handleSendMessage = async (content: string, _files: File[] = []) => {
    if (!content.trim()) return;

    if (chatCount >= TRIAL_LIMIT) {
      setShowLimitModal(true);
      return false;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsBotTyping(true);
    setError(null);

    const botMessageId = "bot-" + Date.now().toString();
    let fullBotContent = "";

    // Add empty bot bubble immediately
    setMessages((prev) => [
      ...prev,
      {
        id: botMessageId,
        role: "bot",
        content: "",
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ]);

    try {
      await chatApi
        .sendTrialMessageStream(content, (chunk) => {
          const lines = chunk.split("\n");
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed === "data: [DONE]") continue;
            if (trimmed.startsWith("data: ")) {
              try {
                const parsed = JSON.parse(trimmed.substring(6));
                if (
                  parsed.type === "content" ||
                  parsed.type === "content_block_delta"
                ) {
                  fullBotContent += parsed.data;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMessageId
                        ? { ...m, content: fullBotContent }
                        : m,
                    ),
                  );
                } else if (parsed.type === "sources" && Array.isArray(parsed.data)) {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMessageId
                        ? { ...m, sources: parsed.data }
                        : m,
                    ),
                  );
                } else if (
                  parsed.type === "metadata" &&
                  typeof parsed.data === "object" &&
                  parsed.data !== null
                ) {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === botMessageId
                        ? {
                            ...m,
                            suggestedFollowUps:
                              parsed.data.suggested_follow_ups ||
                              m.suggestedFollowUps,
                            sources: parsed.data.sources || m.sources,
                          }
                        : m,
                    ),
                  );
                } else if (parsed.type === "error") {
                  setError(parsed.data);
                }
              } catch (e) {
                console.error("Error parsing stream chunk", e);
              }
            }
          }
        })
        .catch((err: any) => {
          setError(err.message || "Failed to send message");
          setMessages((prev) => prev.filter((m) => m.id !== botMessageId));
        })
        .finally(() => {
          setIsBotTyping(false);
        });

      // ── Update chat count via API after successful bot response ──────────
      const newCount = chatCount + 1;
      setChatCount(newCount);

      if (visitingUser) {
        try {
          const updated = await visitingUsersApi.updateChatCount(
            visitingUser.id,
            newCount,
          );
          // Keep local state in sync with server response
          const synced: VisitingUser = {
            ...visitingUser,
            chat_count: updated.chat_count,
          };
          setVisitingUser(synced);
          storeVisitingUser(synced);
          setChatCount(updated.chat_count);
        } catch {
          // Fail silently — local count already updated, localStorage is backup
          const synced: VisitingUser = {
            ...visitingUser,
            chat_count: newCount,
          };
          storeVisitingUser(synced);
          setVisitingUser(synced);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to send message";
      setError(msg);
      setMessages((prev) => prev.filter((m) => m.id !== botMessageId));
    } finally {
      setIsBotTyping(false);
      return false;
    }
  };

  const remaining = Math.max(0, TRIAL_LIMIT - chatCount);

  return (
    <div className="flex flex-col h-screen min-h-screen overflow-hidden bg-white dark:bg-[#08070A]">
      {/* ── Email gate — shown before any chatbot UI is accessible ── */}
      <EmailGateModal
        isOpen={visitingUser === null}
        onSuccess={handleEmailGateSuccess}
      />

      {/* ── Header ── */}
      <div className="w-full max-w-4xl flex items-center justify-between mx-auto px-4 py-4 border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-center gap-2">
          {/* <button
            onClick={() => navigate("/")}
            className="p-2 -ml-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
            aria-label="Back to home"
          >
            <PiCaretLeftBold size={20} />
          </button> */}
          <Link to="/" className="hover:opacity-80 transition-opacity flex items-center">
            <h3 className="text-2xl md:text-3xl font-logo tracking-tight">FinSight</h3>
          </Link>
          <span className="hidden sm:inline-flex bg-primary/10 text-primary text-xs font-medium px-2 py-0.5 rounded ml-2">
            Trial
          </span>
        </div>

        <div className="flex items-center gap-3">
          {visitingUser?.email && (
            <div className="hidden sm:flex items-center gap-2 text-xs text-muted-foreground bg-secondary/30 dark:bg-secondary/10 border border-gray-100 dark:border-gray-800 px-1.5 py-1 rounded-full">
              <div className="w-5 h-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-medium text-[10px] uppercase">
                {visitingUser.email.charAt(0)}
              </div>
              <span className="truncate max-w-[150px] pr-2 font-medium">{visitingUser.email}</span>
            </div>
          )}

          <div
            className={`px-3 py-1.5 rounded-full text-xs font-medium border flex items-center gap-2 ${
              remaining <= 2
                ? "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-900/50 dark:bg-indigo-900/20 dark:text-indigo-400"
                : "border-gray-200 bg-gray-50 text-muted-foreground dark:border-gray-800 dark:bg-gray-900"
            }`}
          >
            <div
              className={`w-1.5 h-1.5 rounded-full ${remaining <= 2 ? "bg-indigo-500" : "bg-primary"}`}
            />
            <span>
              {remaining} of {TRIAL_LIMIT} left
            </span>
          </div>
        </div>
      </div>

      {/* ── Chat area ── */}
      <section className="flex-1 flex flex-col relative overflow-hidden">
        {messages.length === 0 ? (
          <WelcomeScreen
            onSend={handleSendMessage}
            disabled={isBotTyping}
            hideInput
          />
        ) : (
          <ChatBody
            messages={messages}
            isTyping={isBotTyping}
            error={error}
            onSend={handleSendMessage}
          />
        )}
        <ChatInput
          onSend={handleSendMessage}
          disabled={isBotTyping || chatCount >= TRIAL_LIMIT}
          isTrial
          onDisabledClick={() => {
            if (chatCount >= TRIAL_LIMIT) setShowLimitModal(true);
          }}
        />
      </section>

      <div ref={chatEndRef} />

      {/* ── Modals ── */}
      <TrialLimitModal
        isOpen={showLimitModal}
        onClose={() => setShowLimitModal(false)}
      />
      <TrialJoinModal
        isOpen={showJoinModal}
        onClose={() => setShowJoinModal(false)}
      />
    </div>
  );
};

export default TryAskFinSight;
