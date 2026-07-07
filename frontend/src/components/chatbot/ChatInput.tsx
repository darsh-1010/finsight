import type { ChangeEvent, KeyboardEvent } from "react";
import { useState, useEffect } from "react";

import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { useAlert } from "@/context/AlertContext";

import UpgradePlanModal from "./ChatInput/UpgradePlanModal";
import TextareaContainer from "./ChatInput/TextareaContainer";

interface ChatInputProps {
  onSend: (content: string, files: File[]) => void | Promise<boolean | void>;
  isWelcome?: boolean;
  disabled?: boolean;
  isUploading?: boolean;
  isTrial?: boolean;
  onDisabledClick?: () => void;
}

const ChatInput = ({
  onSend,
  isWelcome,
  disabled,
  isUploading,
  isTrial,
  onDisabledClick,
}: ChatInputProps) => {
  const { user } = useAuth();
  const { showAlert } = useAlert();
  const tierLevel = user?.tier_level ?? 1;
  const isAttachmentLocked = isTrial || tierLevel <= 2;

  const [content, setContent] = useState("");
  const [isFileUpload, setIsFileUpload] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const maxFiles = tierLevel >= 4 ? 5 : 3;
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [modalConfig, setModalConfig] = useState<{
    title: string;
    description: React.ReactNode;
    showTierRequirement: boolean;
  }>({
    title: isTrial ? "Feature Locked" : "File Attachments Locked",
    description: null,
    showTierRequirement: !isTrial,
  });

  const handleSend = async () => {
    if (content.trim() || files.length > 0) {
      const didSend = await onSend(content, files);
      if (didSend === false) return;

      setContent("");
      setFiles([]);
      setIsFileUpload(false);
    }
  };

  useEffect(() => {
    if (files.length === 0) {
      setIsFileUpload(false);
    }
  }, [files.length]);

  const removeFile = (index: number) => {
    setFiles((prev) => {
      const newFiles = prev.filter((_, i) => i !== index);
      if (newFiles.length === 0) {
        setIsFileUpload(false);
      }
      return newFiles;
    });
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);

    if (!selectedFiles.length) return;

    // Format Validation
    const isSpreadsheet = (file: File) => {
      const name = file.name.toLowerCase();
      const type = file.type;
      return (
        type === "application/vnd.ms-excel" ||
        type ===
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
        type === "text/csv" ||
        name.endsWith(".xls") ||
        name.endsWith(".xlsx") ||
        name.endsWith(".csv")
      );
    };

    if (tierLevel < 4) {
      const restrictedFile = selectedFiles.find(isSpreadsheet);
      if (restrictedFile) {
        setModalConfig({
          title: "Premium Feature Required",
          description: (
            <div className="space-y-4 text-left">
              <p className="text-sm">
                Uploading{" "}
                <span className="font-bold text-primary">
                  Spreadsheets & Data files
                </span>{" "}
                is an Institutional feature. Upgrade your plan to analyze CSV,
                Excel, and other data formats.
              </p>

              <div className="bg-gray-50 dark:bg-gray-900/50 rounded-xl border border-gray-100 dark:border-gray-800 overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="bg-gray-100 dark:bg-gray-800">
                      <th className="p-2.5 font-semibold">Feature</th>
                      <th className="p-2.5 font-semibold">Tier 3 (Pro)</th>
                      <th className="p-2.5 font-semibold">Tier 4 (Inst.)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    <tr>
                      <td className="p-2.5">Documents</td>
                      <td className="p-2.5 text-green-600 dark:text-green-400">
                        ✓ PDF, DOC
                      </td>
                      <td className="p-2.5 text-green-600 dark:text-green-400">
                        ✓ PDF, DOC
                      </td>
                    </tr>
                    <tr>
                      <td className="p-2.5">Images</td>
                      <td className="p-2.5 text-green-600 dark:text-green-400">
                        ✓ JPG, PNG
                      </td>
                      <td className="p-2.5 text-green-600 dark:text-green-400">
                        ✓ JPG, PNG
                      </td>
                    </tr>
                    <tr className="bg-primary/5">
                      <td className="p-2.5 font-medium">Data Files</td>
                      <td className="p-2.5 text-red-500 italic">
                        Not Supported
                      </td>
                      <td className="p-2.5 font-bold text-primary">
                        ✓ XLS, CSV
                      </td>
                    </tr>
                    <tr>
                      <td className="p-2.5">Upload Limit</td>
                      <td className="p-2.5 text-gray-500">5 files</td>
                      <td className="p-2.5 font-medium">20 files</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ),
          showTierRequirement: false,
        });
        setShowUpgradeModal(true);
        return;
      }
    }

    setFiles((prev) => {
      const totalFiles = [...prev, ...selectedFiles];

      if (totalFiles.length > maxFiles) {
        if (tierLevel < 4) {
          setModalConfig({
            title: "Upload Limit Reached",
            description: (
              <div className="space-y-4">
                <p>
                  You've reached the{" "}
                  <span className="font-medium text-primary">3-file limit</span>{" "}
                  for your current plan. Upgrade to the{" "}
                  <span className="font-medium text-primary">
                    FinSight Pro plan
                  </span>{" "}
                  to upload more files at once!
                </p>
              </div>
            ),
            showTierRequirement: false,
          });
          setShowUpgradeModal(true);
        } else {
          showAlert(
            "Upload Limit",
            `You can upload up to ${maxFiles} files only.`,
          );
        }
        return prev;
      }

      return totalFiles;
    });

    setIsFileUpload(true);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      if (disabled) return;
      e.preventDefault();
      void handleSend();
    }
  };

  const getAcceptString = () => {
    const images = "image/jpeg,image/png,image/webp,image/gif";
    const docs =
      ".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    const data =
      ".xls,.xlsx,.csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv";

    if (tierLevel >= 4) {
      return `${images},${docs},${data}`;
    }
    return `${images},${docs}`;
    // return '.pdf, application/pdf'
  };

  return (
    <>
      {/* Upgrade-plan modal */}
      {showUpgradeModal && (
        <UpgradePlanModal
          onClose={() => setShowUpgradeModal(false)}
          title={modalConfig.title}
          description={modalConfig.description}
          showTierRequirement={modalConfig.showTierRequirement}
          isTrial={isTrial}
        />
      )}
      <div className="w-full px-2 md:py-4 sm:p-4 flex justify-center">
        <div
          className={cn(
            " pt-2 md:pb-6 w-full max-w-4xl",
            !isWelcome &&
              "bg-linear-to-t from-white dark:from-[#08070A] to-transparent",
          )}
          onClick={() => {
            if (disabled && onDisabledClick) {
              onDisabledClick();
            }
          }}
        >
          <div className="w-full relative group">
            <div className="absolute inset-0 bg-primary/5 dark:bg-primary/10 blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity rounded-3xl" />

            {disabled && isTrial && (
              <div
                className="absolute inset-0 z-20 cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation();
                  if (onDisabledClick) onDisabledClick();
                }}
              />
            )}

            <TextareaContainer
              content={content}
              setContent={setContent}
              handleKeyDown={handleKeyDown}
              disabled={disabled || isUploading}
              handleSend={handleSend}
              isFileUpload={isFileUpload}
              setIsFileUpload={setIsFileUpload}
              handleFileChange={handleFileChange}
              files={files}
              removeFile={removeFile}
              accept={getAcceptString()}
              isUploading={isUploading}
              lockedCtaLabel={
                isTrial ? "Sign Up to Continue" : "Click to Upgrade"
              }
              onAttachmentLockedClick={
                isAttachmentLocked
                  ? () => {
                      setModalConfig({
                        title: isTrial
                          ? "Login Required"
                          : "File Attachments Locked",
                        description: (
                          <p>
                            {isTrial ? (
                              "You need to login or signup to use that functionality."
                            ) : (
                              <>
                                Uploading files and images is available on the{" "}
                                <span className="font-medium text-primary">
                                  Premium plans
                                </span>
                                . Upgrade your account to unlock this feature.
                              </>
                            )}
                          </p>
                        ),
                        showTierRequirement: !isTrial,
                      });
                      setShowUpgradeModal(true);
                    }
                  : undefined
              }
            />
            <div className="mt-2 text-center">
              <p className="text-[10px] text-gray-400">
                Press Enter to send, Shift + Enter for new line
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ChatInput;
