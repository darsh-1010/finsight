import React, { useEffect, useRef } from "react";
import {

  PiArrowsCounterClockwiseBold,
  PiFilePdfDuotone,
  PiImageDuotone,
  PiFileDocDuotone,
  PiFileDuotone,
  PiDownloadSimpleBold,
} from "react-icons/pi";

import type { Attachment } from "@/store/slices/chatSlice";

import ChatMarkdown from "./ChatMarkdown";

import { cn } from "@/lib/utils";
import { useAppDispatch } from "@/store/hooks";
import { retryLastMessage, type Message } from "@/store/slices/chatSlice";
import StreamingLoader from "./ChatMarkdown/StreamingLoader";

interface ErrorMessageProps {
  error: string;
  handleRetry: () => void;
}

interface ChatMessageItemProps {
  msg: Message;
  idx: number;
  messagesLength: number;
  isTyping: boolean;
  onSend: (content: string, files: File[]) => void | Promise<boolean | void>;
}

interface ChatBodyProps {
  messages: Message[];
  isTyping?: boolean;
  error?: string | null;
  onSend: (content: string, files: File[]) => void | Promise<boolean | void>;
}


const ErrorMessage = ({ error, handleRetry }: ErrorMessageProps) => (
  <div className="flex flex-col items-start gap-3 my-6 animate-in fade-in slide-in-from-top-4 duration-500 w-full">
    <div className="flex items-center gap-2.5 px-5 py-3 rounded-2xl bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/20 text-red-600 dark:text-red-400 shadow-sm max-w-md text-left w-fit">
      <div className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
      <p className="text-xs sm:text-sm font-medium leading-relaxed">{error}</p>
    </div>

    <button
      onClick={handleRetry}
      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-300 text-xs sm:text-sm font-semibold hover:bg-gray-50 dark:hover:bg-gray-800 transition-all shadow-sm active:scale-95 cursor-pointer group w-fit"
    >
      <PiArrowsCounterClockwiseBold
        size={16}
        className="group-hover:rotate-180 transition-transform duration-500"
      />
      Retry Message
    </button>
  </div>
);



const AttachmentItem = ({
  attachment,
  isBot,
}: {
  attachment: Attachment;
  isBot: boolean;
}) => {
  const isImage = attachment.file_type?.startsWith("image/");
  const isPdf = attachment.file_type === "application/pdf";
  const isDoc =
    attachment.file_type?.includes("word") ||
    attachment.file_type?.includes("officedocument");

  const Icon = isImage
    ? PiImageDuotone
    : isPdf
      ? PiFilePdfDuotone
      : isDoc
        ? PiFileDocDuotone
        : PiFileDuotone;

  return (
    <div
      className={cn(
        "flex items-center gap-3 p-2.5 rounded-xl border transition-all",
        isBot
          ? "bg-gray-50 dark:bg-gray-800/50 border-gray-100 dark:border-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
          : "bg-white/10 border-white/20 text-white hover:bg-white/20",
      )}
    >
      <div
        className={cn(
          "p-2 rounded-lg shrink-0",
          isBot ? "bg-primary/10 text-primary" : "bg-white/20",
        )}
      >
        <Icon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-medium truncate leading-tight">
          {attachment.file_name}
        </p>
        <p className="text-[9px] opacity-60">
          {attachment.file_size
            ? `${(attachment.file_size / 1024).toFixed(1)} KB`
            : "Unknown size"}
        </p>
      </div>
      <a
        href={attachment.storage_url}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "p-1.5 rounded-lg transition-all shrink-0",
          isBot
            ? "hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400"
            : "hover:bg-white/20 text-white/80",
        )}
        onClick={(e) => e.stopPropagation()}
        title="View/Download"
      >
        <PiDownloadSimpleBold size={14} />
      </a>
    </div>
  );
};

interface MessageBubbleProps {
  msg: ChatMessageItemProps["msg"];
  isTyping: boolean;
  isLast: boolean;
  onSend: (q: string, files: File[]) => void | Promise<boolean | void>;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  msg,
  isTyping,
  isLast,
  onSend,
}) => {
  const isBot = msg.role === "bot";

  return (
    <>
      {isBot && !msg.content && isTyping && isLast ? (
        <StreamingLoader />
      ) : (
        <div
          className={cn(
            "p-3 sm:p-4 rounded-xl sm:rounded-2xl ",
            isBot
              ? ""
              : "bg-primary text-white rounded-tr-none border-primary shadow-lg shadow-primary/20",
          )}
        >
          <div className="space-y-3">
            {isBot? <ChatMarkdown
              content={msg.content}
              isBot={isBot}
              isStreaming={isBot && isLast && isTyping}
              suggestedFollowUps={msg.suggestedFollowUps}
              sources={msg.sources?.filter(
                (src) => src.url != null && src.url !== "https://example.com",
              )}
              onQuestionClick={(q) => void onSend(q, [])}
            />:<p className="">{msg.content}</p>}
           

            {msg.attachments && msg.attachments.length > 0 && (
              <div className="flex flex-col gap-2 pt-1">
                {msg.attachments.map((att) => (
                  <AttachmentItem key={att.id} attachment={att} isBot={isBot} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};

const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  msg,
  idx,
  messagesLength,
  isTyping,
  onSend,
}) => {
  const isUser = msg.role === "user";
  const isLast = idx === messagesLength - 1;

  return (
    <div
      className={cn(
        "flex gap-3 sm:gap-4 mb-12",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* <MessageAvatar role={msg.role} /> */}

      <div
        className={cn(
          "flex flex-col gap-1",
          isUser ? "items-end" : "items-start",
        )}
      >
        <MessageBubble
          msg={msg}
          isTyping={isTyping}
          isLast={isLast}
          onSend={onSend}
        />

        {/* {!(msg.role === "bot" && !msg.content && isTyping && isLast) && (
          <span className="text-[10px] text-gray-400 mt-1">{msg.timestamp}</span>
        )} */}
      </div>
    </div>
  );
};

const ChatBody = ({ messages, isTyping, error, onSend }: ChatBodyProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const dispatch = useAppDispatch();
  const isAtBottom = useRef(true);

  const handleScroll = () => {
    if (containerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
      // If we are within 100px of the bottom, we consider it "at bottom"
      isAtBottom.current = scrollHeight - scrollTop - clientHeight < 100;
    }
  };

  const prevMessageState = useRef({ id: '', length: 0 });

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    let isLargeChunk = false;

    if (lastMessage) {
      const currentId = lastMessage.id;
      const currentLength = lastMessage.content?.length || 0;

      if (isTyping && currentId === prevMessageState.current.id) {
        isLargeChunk = currentLength - prevMessageState.current.length > 50;
      } else if (isTyping && currentId !== prevMessageState.current.id) {
        isLargeChunk = currentLength > 50;
      }

      prevMessageState.current = { id: currentId, length: currentLength };
    }

    if (isAtBottom.current || isLargeChunk) {
      scrollRef.current?.scrollIntoView({
        behavior: "smooth",
      });
      if (isLargeChunk) {
        isAtBottom.current = true;
      }
    }
  }, [messages, isTyping, error]);

  const handleRetry = () => {
    dispatch(retryLastMessage());
  };

  const lastMessage = messages[messages.length - 1];

  const shouldShowRetry =
    !isTyping &&
    ((lastMessage?.role === "user" && !!error) ||
      (lastMessage?.role === "bot" && !lastMessage?.content));

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto space-y-2 sm:space-y-0 mx-auto w-full scrollbar-hide [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
    >
      <div className="w-full max-w-4xl mx-auto pt-4 px-4 sm:px-8 pt-12">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full opacity-50">
            <p className="text-sm">Start a conversation with FinSight</p>
          </div>
        ) : (
          <>
            {messages.map((msg, idx) => (
              <ChatMessageItem
                key={msg.id || idx}
                msg={msg}
                idx={idx}
                messagesLength={messages.length}
                isTyping={!!isTyping}
                onSend={onSend}
              />
            ))}

            {isTyping && lastMessage?.role !== "bot" && <StreamingLoader />}

            {shouldShowRetry && (
              <ErrorMessage
                error={error || "Failed to get response. Please retry."}
                handleRetry={handleRetry}
              />
            )}
          </>
        )}
      </div>

      <div ref={scrollRef} />
    </div>
  );
};

export default ChatBody;
