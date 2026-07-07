import { useNavigate } from "react-router-dom";
import { PiSparkleFill, PiArrowUpRightBold } from "react-icons/pi";
import { PROFILE_SUBSCRIPTION_PATH } from "@/lib/profileRoutes";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

interface AttachmentLockedPopoverProps {
  popoverRef?: React.RefObject<HTMLDivElement | null>;
  /** Label for the CTA button */
  ctaLabel?: string;
  onClose: () => void;
}

const FEATURES = [
  "Portfolio Performance Deep-Dive",
  "Deep Context Analysis",
  "Multi-Document Intelligence",
];

const AttachmentLockedPopover = ({
  popoverRef,
  ctaLabel = "Click to Upgrade",
  onClose,
}: AttachmentLockedPopoverProps) => {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();

  const handleCtaClick = () => {
    onClose();
    navigate(isLoggedIn ? PROFILE_SUBSCRIPTION_PATH : "/signup");
  };

  return (
    <div
      ref={popoverRef}
      className={cn(
        // Position
        "absolute bottom-full left-0 mb-3 z-50",
        // Size & shape
        "w-64 rounded-2xl overflow-hidden",
        // Light theme
        "bg-white border border-gray-200 shadow-xl",
        // Dark theme
        "dark:bg-gray-950 dark:border-gray-800/80 dark:shadow-2xl dark:shadow-black/60",
        // Entrance animation
        "animate-in fade-in zoom-in-95 duration-200 origin-bottom-left",
      )}
    >
      {/* Top accent bar */}
      <div className="h-0.5 w-full bg-gradient-to-r from-primary/80 via-primary to-primary/20" />

      <div className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center gap-2">
          <PiSparkleFill size={14} className="text-primary shrink-0" />
          <span className="text-[11px] font-bold tracking-widest uppercase text-primary">
            Unlock Intelligence
          </span>
        </div>

        {/* Description */}
        <p className="text-[11px] leading-relaxed text-gray-500 dark:text-gray-400">
          Analyze your portfolio with deep-document insights and personalized
          financial reasoning.
        </p>

        {/* Feature bullets */}
        <ul className="space-y-1.5">
          {FEATURES.map((feature) => (
            <li
              key={feature}
              className="flex items-center gap-2 text-[11px] text-gray-700 dark:text-gray-300"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" />
              {feature}
            </li>
          ))}
        </ul>

        {/* CTA */}
        <button
          onClick={handleCtaClick}
          className={cn(
            "w-full mt-1 py-2 rounded-xl",
            "flex items-center justify-center gap-1.5",
            "text-[11px] font-bold tracking-widest uppercase",
            // Light
            "border border-primary/60 text-primary",
            // Hover (works for both themes)
            "hover:bg-primary hover:text-white hover:border-primary",
            "transition-all duration-200",
          )}
        >
          {ctaLabel}
          <PiArrowUpRightBold size={12} />
        </button>
      </div>
    </div>
  );
};

export default AttachmentLockedPopover;
