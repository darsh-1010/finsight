import { useNavigate } from "react-router-dom";

import { PROFILE_SUBSCRIPTION_PATH } from "@/lib/profileRoutes";
import {  PiX, PiLockFill, PiSparkleFill } from "react-icons/pi";

interface UpgradePlanModalProps {
  onClose: () => void;
  title?: string;
  description?: React.ReactNode;
  showTierRequirement?: boolean;
  isTrial?: boolean;
}

const UpgradePlanModal = ({ 
  onClose, 
  title = "File Attachments Locked", 
  description,
  showTierRequirement = true,
  isTrial = false
}: UpgradePlanModalProps) => {
  const navigate = useNavigate();

  const handleAction = () => {
    onClose();
    if (isTrial) {
      navigate("/signup");
    } else {
      navigate(PROFILE_SUBSCRIPTION_PATH);
    }
  };

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Card */}
      <div
        className="relative w-full max-w-sm mx-4 rounded-2xl bg-white dark:bg-[#0F0E14] border border-gray-200 dark:border-gray-800 shadow-2xl p-7 flex flex-col items-center gap-4 animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-full text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          <PiX size={16} />
        </button>

        {/* Icon */}
        <div className="p-4 rounded-full bg-linear-to-br from-primary/20 to-primary/5 dark:from-primary/30 dark:to-primary/10">
          <PiLockFill size={28} className="text-primary" />
        </div>

        {/* Text */}
        <div className="text-center space-y-1.5">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
          <div className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
            {description || (
              <p>
                Uploading files and images is available on the{" "}
                <span className="font-medium text-primary">Premium plan</span>. Upgrade
                your account to unlock this feature.
              </p>
            )}
          </div>
          {showTierRequirement && (
            <p className="text-xs font-medium text-gray-400 dark:text-gray-500 pt-1">
              🔒 Unlocks at <span className="text-primary">Tier 3 (Premium)</span>
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col w-full gap-2 pt-1">
          <button
            onClick={handleAction}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-white text-sm font-medium hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20"
          >
            <PiSparkleFill size={16} />
            {isTrial ? "Get Started" : "Upgrade Plan"}
          </button>
          <button
            onClick={onClose}
            className="w-full py-2 rounded-xl text-sm text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
};

export default UpgradePlanModal;