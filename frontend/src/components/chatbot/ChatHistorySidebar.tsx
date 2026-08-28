import { useRouter, useParams } from 'next/navigation';
import React, { useEffect, useState } from 'react';
import { PiPlusBold, PiTrashSimpleBold, PiXBold } from 'react-icons/pi';

import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';

import type { SubSidebarProps } from '@/lib/interfaces/Sidebar';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  selectConversations,
  fetchSessions,
  deleteSession,
} from '@/store/slices/chatSlice';
import type { Conversation } from '@/store/slices/chatSlice';

interface DeleteSessionModalProps {
  pendingDeleteId: string | null;
  setPendingDeleteId: (id: string | null) => void;
  handleConfirmDelete: () => void;
}

function extractFirst30Words(markdown: string): string {
  const text = markdown
    // Remove markdown links: [text](url) -> text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // Remove markdown symbols
    .replace(/[*_#>`~-]/g, '')
    // Remove inline code backticks
    .replace(/`+/g, '')
    // Normalize whitespace
    .trim();

  return text.split(/\s+/).slice(0, 30).join(' ');
}

const DeleteSessionModal = ({
  pendingDeleteId,
  setPendingDeleteId,
  handleConfirmDelete,
}: DeleteSessionModalProps) => (
  <Dialog
    open={!!pendingDeleteId}
    onOpenChange={(open) => !open && setPendingDeleteId(null)}
  >
    <DialogContent className="max-w-sm">
      <DialogHeader>
        <DialogTitle className="text-xl">Delete Chat Session</DialogTitle>
        <DialogDescription className="pt-1">
          Are you sure you want to delete this chat session? This action cannot
          be undone and all messages will be permanently removed.
        </DialogDescription>
      </DialogHeader>
      <DialogFooter className="gap-2 sm:gap-0 mt-2">
        <Button
          variant="ghost"
          onClick={() => setPendingDeleteId(null)}
          className="rounded-xl"
        >
          Cancel
        </Button>
        <Button
          onClick={handleConfirmDelete}
          className="rounded-xl bg-red-500 hover:bg-red-600 text-white border-0"
        >
          Delete
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

interface ConversationItemProps {
  chat: Conversation;
  activeId?: string;
  navigate: (path: string) => void;
  handleDeleteClick: (e: React.MouseEvent, sessionId: string) => void;
}

const ChatTime = ({ updatedAt }: { updatedAt: string }) => (
  <span className="text-[10px] text-gray-400 whitespace-nowrap shrink-0 ml-1 group-hover:hidden">
    {new Date(updatedAt).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    })}
  </span>
);

const ConversationItem = ({
  chat,
  activeId,
  navigate,
  handleDeleteClick,
}: ConversationItemProps) => (
  <button
    key={chat.id}
    onClick={() => navigate(`/ask_finsight/c/${chat.id}`)}
    className={cn(
      'w-full text-left p-3 rounded-2xl transition-all duration-200 group relative',
      activeId === chat.id
        ? 'bg-primary/5 dark:bg-primary/10 border border-primary/20'
        : 'hover:bg-gray-50 dark:hover:bg-gray-900 border border-transparent',
    )}
  >
    <div className="flex justify-between items-start mb-1 min-w-0">
      <span
        className={cn(
          'font-medium text-sm truncate pr-8 flex-1',
          activeId === chat.id
            ? 'text-primary'
            : 'text-gray-900 dark:text-gray-100',
        )}
      >
        {chat.title}
      </span>
      <ChatTime updatedAt={chat.updatedAt} />
      <button
        onClick={(e) => handleDeleteClick(e, chat.id)}
        className={cn(
          'absolute right-3 top-3.5 p-1 text-gray-400',
          'hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-10',
        )}
        title="Delete chat"
      >
        <PiTrashSimpleBold size={16} />
      </button>
    </div>
    <div className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1 pointer-events-none sidebar-snippet">
      <p>{extractFirst30Words(chat.snippet)}</p>
      {/* <ChatMarkdown content={chat.snippet} /> */}
    </div>
  </button>
);

interface SidebarHeaderProps {
  isMobile?: boolean;
  navigate: (path: string) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

const SidebarHeader = ({
  isMobile,
  navigate,
  setSidebarCollapsed,
}: SidebarHeaderProps) => (
  <div className="p-4 flex items-center justify-between">
    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
      Chats
    </h2>
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => navigate('/ask_finsight')}
        className="h-8 w-8 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
      >
        <PiPlusBold size={18} />
      </Button>
      {isMobile && (
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setSidebarCollapsed(true)}
          className="h-8 w-8 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
        >
          <PiXBold size={18} />
        </Button>
      )}
    </div>
  </div>
);

interface ConversationListProps {
  conversations: Conversation[];
  activeId?: string;
  navigate: (path: string) => void;
  handleDeleteClick: (e: React.MouseEvent, sessionId: string) => void;
}

const ConversationList = ({
  conversations,
  activeId,
  navigate,
  handleDeleteClick,
}: ConversationListProps) => (
  <div className="flex-1 overflow-y-auto px-2 space-y-1 mt-4">
    {conversations.length === 0 ? (
      <div className="px-4 py-8 text-center">
        <p className="text-xs text-gray-400">No conversations yet</p>
      </div>
    ) : (
      conversations.map((chat) => (
        <ConversationItem
          key={chat.id}
          chat={chat}
          activeId={activeId}
          navigate={navigate}
          handleDeleteClick={handleDeleteClick}
        />
      ))
    )}
  </div>
);

const useChatHistory = () => {
  const navigate = useRouter().push;
  const dispatch = useAppDispatch();
  const { conversationId: activeId } = useParams<{ conversationId?: string }>();
  const conversations = useAppSelector(selectConversations);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  useEffect(() => {
    dispatch(fetchSessions());
  }, [dispatch]);

  return {
    navigate,
    dispatch,
    activeId,
    conversations,
    pendingDeleteId,
    setPendingDeleteId,
  };
};

/* -------------------- Sub Component -------------------- */

interface SidebarLayoutProps extends SubSidebarProps {
  navigate: (path: string) => void;
  conversations: Conversation[]; // replace with proper type if available
  activeId: string | undefined;
  handleDeleteClick: (e: React.MouseEvent, id: string) => void;
}

const SidebarLayout: React.FC<SidebarLayoutProps> = ({
  sidebarCollapsed,
  setSidebarCollapsed,
  isMobile,
  navigate,
  conversations,
  activeId,
  handleDeleteClick,
}) => (
  <aside
    className={cn(
      'flex flex-col h-full',
      'transition-all duration-300 bg-white dark:bg-[#08070A]',
      isMobile
        ? cn(
          'fixed inset-y-0 left-0 z-50 transition-transform duration-300 transform',
          sidebarCollapsed ? '-translate-x-full' : 'translate-x-0',
        )
        : cn('relative', sidebarCollapsed ? 'w-0 overflow-hidden' : 'w-80'),
    )}
    style={isMobile ? { width: 'min(320px, 85vw)' } : {}}
  >
    <SidebarHeader
      isMobile={isMobile}
      navigate={navigate}
      setSidebarCollapsed={setSidebarCollapsed}
    />
    <ConversationList
      conversations={conversations}
      activeId={activeId}
      navigate={navigate}
      handleDeleteClick={handleDeleteClick}
    />
  </aside>
);

/* -------------------- Main Component -------------------- */

const ChatHistorySidebar: React.FC<SubSidebarProps> = (props) => {
  const { sidebarCollapsed, setSidebarCollapsed, isMobile } = props;

  const {
    navigate,
    dispatch,
    activeId,
    conversations,
    pendingDeleteId,
    setPendingDeleteId,
  } = useChatHistory();

  const handleDeleteClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setPendingDeleteId(sessionId);
  };

  const handleConfirmDelete = () => {
    if (!pendingDeleteId) return;

    dispatch(deleteSession(pendingDeleteId));

    if (activeId === pendingDeleteId) {
      navigate('/ask_finsight');
    }

    setPendingDeleteId(null);
  };

  return (
    <>
      <DeleteSessionModal
        pendingDeleteId={pendingDeleteId}
        setPendingDeleteId={setPendingDeleteId}
        handleConfirmDelete={handleConfirmDelete}
      />

      <SidebarLayout
        sidebarCollapsed={sidebarCollapsed}
        setSidebarCollapsed={setSidebarCollapsed}
        isMobile={isMobile}
        navigate={navigate}
        conversations={conversations}
        activeId={activeId}
        handleDeleteClick={handleDeleteClick}
        mainSidebarCollapsed={false}
      />
    </>
  );
};

export default ChatHistorySidebar;
