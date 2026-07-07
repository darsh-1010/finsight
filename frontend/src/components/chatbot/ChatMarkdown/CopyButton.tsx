import React, { useState } from "react";
import { PiCopyBold, PiCheckBold } from "react-icons/pi";
import { stripMarkdown } from "@/lib/utils";

interface CopyButtonProps {
  content: string;
}

const CopyButton: React.FC<CopyButtonProps> = ({ content }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const plainText = stripMarkdown(content);
    navigator.clipboard.writeText(plainText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center justify-center p-2 rounded-xl cursor-pointer bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-xl text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-all active:scale-90"
      title="Copy response"
    >
      {copied ? (
        <PiCheckBold size={14} className="text-green-500" />
      ) : (
        <PiCopyBold size={14} />
      )}
    </button>
  );
};

export default CopyButton;
