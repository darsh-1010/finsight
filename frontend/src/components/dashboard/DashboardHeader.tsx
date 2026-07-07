import React from "react";
import { Bell, Check, Inbox, Loader2 } from "lucide-react";
import type { IconType } from "react-icons";
import {
  PiListBold,
  PiUserCircleDuotone,
  PiSignOutDuotone,
  PiSunDim,
  PiMoon,
  PiCoinsDuotone,
} from "react-icons/pi";
import { PiStar, PiCrown, PiRocket } from "react-icons/pi"; // example
import {
  useNavigate,
  useLocation,
  Link,
  type NavigateFunction,
} from "react-router-dom";

import Sidebar from "./Sidebar";

import ChatHistorySidebar from "@/components/chatbot/ChatHistorySidebar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import {
  profilePath,
  PROFILE_SUBSCRIPTION_PATH,
  PROFILE_TOKENS_PATH,
} from "@/lib/profileRoutes";
import { cn } from "@/lib/utils";
import { useAppDispatch } from "@/store/hooks";
import {
  useGetNotificationsQuery,
  useGetTokenUsageQuery,
  useMarkNotificationReadMutation,
  type NotificationResponse,
} from "@/store/apiSlice";

const TIER_ICON_MAP: Record<number, IconType> = {
  0: PiStar,
  1: PiStar,
  2: PiCrown,
  3: PiRocket,
};

/* -------------------- Types -------------------- */

interface User {
  email?: string;
  tier_level: number;
  tier_name: string;
}

type Theme = "light" | "dark";

interface MobileDrawerContentProps {
  isAskFinSight: boolean;
  isAdminPath: boolean;
  setMobileOpen: (open: boolean) => void;
}

interface MobileMenuProps {
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
  isAskFinSight: boolean;
  isAdminPath: boolean;
}

interface ThemeToggleProps {
  theme: Theme;
  toggleTheme: () => void;
}

interface TierBadgeProps {
  user: User | null;
  navigate: NavigateFunction;
}

interface UserDropdownProps {
  user: User | null;
  navigate: NavigateFunction;
  logout: () => void;
}

interface UserActionsProps {
  user: User | null;
  theme: Theme;
  toggleTheme: () => void;
  navigate: NavigateFunction;
  logout: () => void;
}

interface HeaderContentProps {
  isAskFinSight: boolean;
  title: string;
  dispatch: ReturnType<typeof useAppDispatch>;
  user: User | null;
}

interface DashboardHeaderProps {
  collapsed: boolean;
  title: string;
}

/* -------------------- Small Components -------------------- */

const MobileDrawerContent: React.FC<MobileDrawerContentProps> = ({
  isAskFinSight,
  isAdminPath,
  setMobileOpen,
}) => (
  <>
    {isAskFinSight && (
      <ChatHistorySidebar
        sidebarCollapsed={false}
        setSidebarCollapsed={() => setMobileOpen(false)}
        isMobile
        mainSidebarCollapsed={false}
      />
    )}
    {isAdminPath && (
      <Sidebar collapsed={false} setCollapsed={() => {}} mobileOpen adminOnly />
    )}
  </>
);

const MobileLogo: React.FC = () => (
  <Link
    to="/"
    className="md:hidden flex items-center gap-2 hover:opacity-80 transition-opacity"
  >
    <span className="font-extrabold text-xl tracking-tight font-logo bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">FinSight</span>
  </Link>
);

/* -------------------- Mobile Menu -------------------- */

const MobileMenu: React.FC<MobileMenuProps> = ({
  mobileOpen,
  setMobileOpen,
  isAskFinSight,
  isAdminPath,
}) => {
  const showDrawer = isAskFinSight || isAdminPath;

  return (
    <div className="flex items-center gap-4">
      {showDrawer && (
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden">
              <PiListBold size={24} />
            </Button>
          </SheetTrigger>

          <SheetContent side="left" className="p-0 w-80">
            <MobileDrawerContent
              isAskFinSight={isAskFinSight}
              isAdminPath={isAdminPath}
              setMobileOpen={setMobileOpen}
            />
          </SheetContent>
        </Sheet>
      )}

      <MobileLogo />
    </div>
  );
};

/* -------------------- User Actions -------------------- */

const ThemeToggle: React.FC<ThemeToggleProps> = ({ theme, toggleTheme }) => (
  <Button variant="ghost" size="icon" onClick={toggleTheme} className="border">
    {theme === "dark" ? <PiSunDim size={25} /> : <PiMoon size={25} />}
  </Button>
);

const TierBadge: React.FC<TierBadgeProps> = ({ user, navigate }) => {
  const tierLevel = user?.tier_level ?? 0;
  const Icon = TIER_ICON_MAP[tierLevel] || TIER_ICON_MAP[0];

  return (
    <Button
      variant="outline"
      onClick={() => navigate(PROFILE_SUBSCRIPTION_PATH)}
      className="hidden sm:flex gap-2 items-center px-2 sm:px-4"
    >
      <Icon size={20} />
      <span>
        {user ? user.tier_name : "Foundation"}
      </span>
    </Button>
  );
};

const UserDropdown: React.FC<UserDropdownProps> = ({
  user,
  navigate,
  logout,
}) => {
  const [showLogoutDialog, setShowLogoutDialog] = React.useState(false);

  return (
    <>
      <DropdownMenu>
       <DropdownMenuTrigger asChild>
  <Button
    variant="ghost"
    size="icon"
    className="relative border md:w-auto md:px-3"
  >
    <PiUserCircleDuotone className="h-5 w-5" />

    <span className="hidden md:block ml-2 max-w-28 truncate">
      {user?.email?.split("@")[0]}
    </span>
  </Button>
</DropdownMenuTrigger>

        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>My Account</DropdownMenuLabel>
          <DropdownMenuSeparator />

          <DropdownMenuItem
            onClick={() => navigate(profilePath("personal"))}
            className="cursor-pointer"
          >
            Profile Settings
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem
            className="text-red-500 cursor-pointer"
            onSelect={(e) => {
              e.preventDefault();
              setShowLogoutDialog(true);
            }}
          >
            <PiSignOutDuotone className="mr-2" size={18} />
            Logout
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={showLogoutDialog} onOpenChange={setShowLogoutDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Are you sure you want to log out?
            </AlertDialogTitle>
            <AlertDialogDescription>
              You will need to sign in again to access your account and
              dashboard.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="cursor-pointer">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={logout}
              className="bg-red-500 text-white hover:bg-red-600 cursor-pointer"
            >
              Logout
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

const DailyUsageBadge: React.FC<{ navigate: NavigateFunction }> = ({
  navigate,
}) => {
  const { data: usage, isLoading } = useGetTokenUsageQuery();

  if (isLoading || !usage) return null;

  const dailyTokensLeft = usage.daily_token_limit - usage.daily_tokens_used;
  const tokensLeft = Math.min(usage.available_tokens, dailyTokensLeft);
  const displayDailyUsed =
    tokensLeft <= 5000 ? usage.daily_token_limit : usage.daily_tokens_used;

  const dailyPercent =
    usage.daily_token_limit <= 0
      ? 0
      : Math.min(
          100,
          Math.round((displayDailyUsed / usage.daily_token_limit) * 100),
        );

  let badgeColorClass =
    "bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20 hover:bg-green-500/20";
  if (dailyPercent >= 85) {
    badgeColorClass =
      "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 hover:bg-red-500/20 animate-pulse";
  } else if (dailyPercent >= 50) {
    badgeColorClass =
      "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20 hover:bg-indigo-500/20";
  }

  return (
    <Button
      variant="outline"
      onClick={() => navigate(PROFILE_TOKENS_PATH)}
      className={`flex gap-1.5 items-center px-2 sm:px-3 text-xs font-semibold rounded-xl ${badgeColorClass}`}
      title="Daily Request Limit (Click to view details)"
    >
      <PiCoinsDuotone size={16} className="text-current" />
      <span>
        {dailyPercent}% <span className="hidden sm:inline">Used</span>
      </span>
    </Button>
  );
};

const getNotificationCardStyle = (
  priority: NotificationResponse["priority"],
) => {
  if (priority === "high") {
    return "bg-red-500/10 focus:bg-red-500/20 dark:bg-red-500/10 dark:focus:bg-red-500/20";
  }

  if (priority === "low") {
    return "bg-slate-500/10 focus:bg-slate-500/20 dark:bg-slate-500/10 dark:focus:bg-slate-500/20";
  }

  return "bg-indigo-500/10 focus:bg-indigo-500/20 dark:bg-indigo-500/10 dark:focus:bg-indigo-500/20";
};

const formatNotificationTime = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));

const NotificationItem: React.FC<{
  notification: NotificationResponse;
  navigate: NavigateFunction;
  onMarkRead: (id: number) => void;
}> = ({ notification, navigate, onMarkRead }) => {
  const openNotification = () => {
    if (!notification.is_read) {
      onMarkRead(notification.id);
    }

    if (notification.action_url) {
      let targetUrl = notification.action_url;
      if (notification.entity_type === "insight" && notification.entity_id) {
        if (!targetUrl.includes("insightId=")) {
          const separator = targetUrl.includes("?") ? "&" : "?";
          targetUrl = `${targetUrl}${separator}insightId=${notification.entity_id}`;
        }
      }
      navigate(targetUrl);
    }
  };

  return (
    <DropdownMenuItem
      onClick={openNotification}
      className={cn(
        "items-start gap-3 p-3 cursor-pointer mb-1",
        getNotificationCardStyle(notification.priority),
      )}
    >
      <span
        className={cn(
          "mt-1 h-2 w-2 rounded-full shrink-0",
          notification.is_read ? "bg-muted" : "bg-primary",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold leading-tight truncate">
            {notification.title}
          </p>
        </div>
        {notification.message && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {notification.message}
          </p>
        )}
        <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
          <span>{formatNotificationTime(notification.created_at)}</span>
        </div>
      </div>
    </DropdownMenuItem>
  );
};

const NotificationsMenu: React.FC<{ navigate: NavigateFunction }> = ({
  navigate,
}) => {
  const { data: notifications = [], isLoading } = useGetNotificationsQuery({
    limit: 10,
  });
  const [markNotificationRead] = useMarkNotificationReadMutation();
  const unreadCount = notifications.filter((item) => !item.is_read).length;

  const handleMarkRead = (id: number) => {
    void markNotificationRead(id);
  };

  const markAllRead = () => {
    notifications
      .filter((item) => !item.is_read)
      .forEach((item) => {
        void markNotificationRead(item.id);
      });
  };

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative border"
          title="Notifications"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        alignOffset={isMobile ? -88 : 0}
        className="w-[calc(100vw-2rem)] sm:w-96"
      >
        <div className="flex items-center justify-between gap-3 p-3">
          <div>
            <DropdownMenuLabel className="p-0">Notifications</DropdownMenuLabel>
            <p className="text-xs text-muted-foreground">
              Updates matched to your audience.
            </p>
          </div>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={markAllRead}
              className="h-8 gap-1 text-xs"
            >
              <Check className="h-3.5 w-3.5" />
              Read
            </Button>
          )}
        </div>
        <DropdownMenuSeparator />

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading
          </div>
        ) : notifications.filter((item) => !item.is_read).length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-sm text-muted-foreground">
            <Inbox className="mb-2 h-8 w-8" />
            No notifications yet
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            {notifications
              .filter((item) => !item.is_read)
              .map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  navigate={navigate}
                  onMarkRead={handleMarkRead}
                />
              ))}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const UserActions: React.FC<UserActionsProps> = ({
  user,
  theme,
  toggleTheme,
  navigate,
  logout,
}) => (
  <div className="flex items-center gap-1 sm:gap-2 md:gap-4">
    <DailyUsageBadge navigate={navigate} />
    <NotificationsMenu navigate={navigate} />
    <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
    <TierBadge user={user} navigate={navigate} />
    <UserDropdown user={user} navigate={navigate} logout={logout} />
  </div>
);

/* -------------------- Header Content -------------------- */

const HeaderContent: React.FC<HeaderContentProps> = ({ isAskFinSight, title }) =>
  isAskFinSight ? (
    <h4 className="font-bold text-lg">Ask FinSight</h4>
  ) : (
    <h4 className="font-bold text-lg">{title}</h4>
  );

/* -------------------- Main Component -------------------- */

const useHeaderState = () => {
  const location = useLocation();

  const isAskFinSight =
    location.pathname === "/ask_finsight" ||
    location.pathname.startsWith("/ask_finsight/c/");

  const isAdminPath = location.pathname.startsWith("/admin");

  return { isAskFinSight, isAdminPath };
};

interface HeaderLayoutProps {
  isAskFinSight: boolean;
  isAdminPath: boolean;
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
  user: User | null;
  logout: () => void;
  theme: Theme;
  toggleTheme: () => void;
  navigate: NavigateFunction;
  title: string;
  dispatch: ReturnType<typeof useAppDispatch>;
}

const HeaderLayout: React.FC<HeaderLayoutProps> = ({
  isAskFinSight,
  isAdminPath,
  mobileOpen,
  setMobileOpen,
  user,
  logout,
  theme,
  toggleTheme,
  navigate,
  title,
  dispatch,
}) => (
  <div className="h-full px-4 flex items-center justify-between">
    <div className="hidden md:block">
      <HeaderContent
        isAskFinSight={isAskFinSight}
        title={title}
        dispatch={dispatch}
        user={user}
      />
    </div>

    <MobileMenu
      mobileOpen={mobileOpen}
      setMobileOpen={setMobileOpen}
      isAskFinSight={isAskFinSight}
      isAdminPath={isAdminPath}
    />

    <UserActions
      user={user}
      theme={theme}
      toggleTheme={toggleTheme}
      navigate={navigate}
      logout={logout}
    />
  </div>
);

const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  collapsed,
  title,
}) => {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const location = useLocation();

  const { isAskFinSight, isAdminPath } = useHeaderState();

  React.useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  return (
    <header
      className={cn(
        "h-16 fixed top-0 right-0 backdrop-blur-md border-b z-40",
        collapsed ? "md:left-20" : "md:left-64",
        "left-0",
      )}
    >
      <HeaderLayout
        isAskFinSight={isAskFinSight}
        isAdminPath={isAdminPath}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
        user={user}
        logout={logout}
        theme={theme}
        toggleTheme={toggleTheme}
        navigate={navigate}
        title={title}
        dispatch={dispatch}
      />
    </header>
  );
};

export default DashboardHeader;
