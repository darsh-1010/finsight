import { useRef, useState, useEffect, type ChangeEvent } from "react";
import { MdOutlineAttachFile } from "react-icons/md";
import { cn } from "@/lib/utils";
import AttachmentLockedPopover from "./AttachmentLockedPopover";

interface AttachmentFileProps {
  handleFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
  /** When provided, clicking the button shows the locked-popover instead of opening the picker */
  onLockedClick?: () => void;
  /** Label for the CTA inside the locked popover */
  lockedCtaLabel?: string;
  accept?: string;
}

const AttachmentFile = ({
  handleFileChange,
  onLockedClick,
  lockedCtaLabel = "Click to Upgrade",
  accept,
}: AttachmentFileProps) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const [showPopover, setShowPopover] = useState(false);

  /* Close popover on outside click */
  useEffect(() => {
    if (!showPopover) return;
    const handleOutside = (e: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setShowPopover(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [showPopover]);

  const handleClick = () => {
    if (onLockedClick) {
      setShowPopover((prev) => !prev);
      return;
    }
    fileInputRef.current?.click();
  };

  return (
    <div ref={wrapperRef} className="relative inline-flex">
      {/* ── Trigger button ── */}
      <button
        type="button"
        title={onLockedClick ? "Upgrade to attach files" : "Attach files"}
        className={cn(
          "p-2 rounded-full transition-colors",
          onLockedClick
            ? "text-gray-400 dark:text-gray-500 cursor-pointer hover:text-primary dark:hover:text-primary"
            : "hover:bg-gray-100 dark:hover:bg-gray-800",
        )}
        onClick={handleClick}
      >
        <MdOutlineAttachFile size={20} />
      </button>

      {/* ── Locked popover ── */}
      {onLockedClick && showPopover && (
        <AttachmentLockedPopover
          popoverRef={popoverRef}
          ctaLabel={lockedCtaLabel}
          onClose={() => setShowPopover(false)}
        />
      )}

      {/* Hidden file input — only rendered when not locked */}
      {!onLockedClick && (
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          multiple
          accept={accept}
          onChange={(e) => {
            handleFileChange(e);
            e.target.value = ""; // allow re-select same file
          }}
        />
      )}
    </div>
  );
};

export default AttachmentFile;
