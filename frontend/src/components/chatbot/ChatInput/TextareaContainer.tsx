import { useRef, useEffect } from "react";
import type { Dispatch, KeyboardEvent, SetStateAction } from "react";
import { 
  PiX, 
  PiFile, 
  PiFilePdf, 
  PiFileXls, 
  PiFileDoc, 
  PiVideo,
  PiFileZip,
  PiFileText,
  PiFileCode,
  PiFileAudio,
  PiPaperPlaneTiltFill
} from "react-icons/pi";
import AttachmentFile from "./AttachmentFile";
import { cn } from "@/lib/utils";

interface TextareaContainerProps {
  content: string;
  setContent: (content: string) => void;
  handleKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled?: boolean;
  handleSend: () => void | Promise<void>;
  isFileUpload: boolean;
  setIsFileUpload: Dispatch<SetStateAction<boolean>>;
  handleFileChange: any;
  files: any;
  removeFile: any;
  onAttachmentLockedClick?: () => void;
  /** CTA label shown inside the locked popover */
  lockedCtaLabel?: string;
  accept?: string;
  isUploading?: boolean;
}

const getFileIcon = (file: File) => {
  const type = file.type;
  const name = file.name.toLowerCase();

  if (type.startsWith("video/")) return <PiVideo size={20} className="text-indigo-500" />;
  if (type.startsWith("audio/")) return <PiFileAudio size={20} className="text-pink-500" />;
  if (type === "application/pdf" || name.endsWith(".pdf")) return <PiFilePdf size={20} className="text-red-500" />;
  
  if (
    type === "application/vnd.ms-excel" || 
    type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
    name.endsWith(".xls") || 
    name.endsWith(".xlsx") ||
    name.endsWith(".csv")
  ) {
    return <PiFileXls size={20} className="text-green-600" />;
  }

  if (
    type === "application/msword" || 
    type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    name.endsWith(".doc") || 
    name.endsWith(".docx")
  ) {
    return <PiFileDoc size={20} className="text-blue-600" />;
  }

  if (
    type === "application/zip" || 
    type === "application/x-zip-compressed" || 
    name.endsWith(".zip") || 
    name.endsWith(".rar") || 
    name.endsWith(".7z")
  ) {
    return <PiFileZip size={20} className="text-orange-500" />;
  }

  if (type.startsWith("text/") || name.endsWith(".txt")) return <PiFileText size={20} className="text-gray-500" />;
  
  if (
    name.endsWith(".js") || 
    name.endsWith(".ts") || 
    name.endsWith(".tsx") || 
    name.endsWith(".html") || 
    name.endsWith(".css") || 
    name.endsWith(".json") ||
    name.endsWith(".py")
  ) {
    return <PiFileCode size={20} className="text-yellow-600" />;
  }

  return <PiFile size={20} className="text-gray-400" />;
};

const TextareaContainer = ({
  content,
  setContent,
  handleKeyDown,
  disabled,
  handleSend,
  isFileUpload,
  handleFileChange,
  files,
  removeFile,
  onAttachmentLockedClick,
  lockedCtaLabel,
  accept,
  isUploading,
}: TextareaContainerProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (content === "" && textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [content]);

  const isImage = (file: File) => file.type.startsWith("image/");
  return (
    <>
      {isFileUpload && (
        <div className="max-h-20 p-2 w-full rounded-t-xl flex flex-wrap gap-2 items-start overflow-auto">
          {files.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {files.map((file: File, index: number) => (
                <div
                  key={index}
                  className="relative flex items-center gap-2 bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-xl text-sm"
                >
                  {isImage(file) ? (
                    <img
                      src={URL.createObjectURL(file)}
                      alt={file.name}
                      className="w-10 h-10 object-cover rounded-md"
                    />
                  ) : (
                    getFileIcon(file)
                  )}

                  <span className="truncate max-w-30">{file.name}</span>

                  <button
                    onClick={() => removeFile(index)}
                    className="text-gray-500 hover:text-red-500"
                  >
                    <PiX size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="relative flex items-center gap-2 p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl shadow-sm focus-within:border-primary/50 transition-all">
        <AttachmentFile
          handleFileChange={handleFileChange}
          onLockedClick={onAttachmentLockedClick}
          lockedCtaLabel={lockedCtaLabel}
          accept={accept}
        />
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={
            disabled ? "Upgrade to use this model" : "Message AskFinSight..."
          }
          className={cn(
            "flex-1 bg-transparent border-none focus:ring-0 resize-none py-3 px-4 text-sm min-h-13 max-h-40 outline-none",
            disabled && "opacity-50 cursor-not-allowed",
          )}
          rows={1}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;

            target.style.height = "auto";
            target.style.height = `${target.scrollHeight}px`;
          }}
        />
        <button
          onClick={handleSend}
          disabled={(!content.trim() && files.length === 0) || disabled || isUploading}
          className="p-2.5 bg-primary text-white rounded-xl hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20 disabled:opacity-50 disabled:shadow-none cursor-pointer disabled:cursor-not-allowed"
          title={isUploading ? "Uploading files…" : "Send message"}
        >
          {isUploading ? (
            <span className="block w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <PiPaperPlaneTiltFill size={20} />
          )}
        </button>
      </div>
    </>
  );
};


export default TextareaContainer;
