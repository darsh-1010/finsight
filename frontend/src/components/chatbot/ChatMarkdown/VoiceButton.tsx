import React, { useState, useEffect, useCallback } from "react";
import { PiSpeakerHighBold, PiStopBold } from "react-icons/pi";
import { stripMarkdown } from "@/lib/utils";

interface VoiceButtonProps {
  content: string;
}

const VoiceButton: React.FC<VoiceButtonProps> = ({ content }) => {
  const [isSpeaking, setIsSpeaking] = useState(false);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  const startSpeaking = () => {
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const plainText = stripMarkdown(content);
    const utterance = new SpeechSynthesisUtterance(plainText);

    utterance.onend = () => {
      setIsSpeaking(false);
    };

    utterance.onerror = () => {
      setIsSpeaking(false);
    };

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  const toggleSpeech = () => {
    if (isSpeaking) {
      stopSpeaking();
    } else {
      startSpeaking();
    }
  };

  useEffect(() => {
    return () => {
      stopSpeaking();
    };
  }, [stopSpeaking]);

  return (
    <button
      onClick={toggleSpeech}
      className={`
        flex items-center justify-center p-2 rounded-xl border shadow-xl transition-all active:scale-90 cursor-pointer
        ${
          isSpeaking
            ? "bg-primary text-white border-primary animate-pulse"
            : "bg-white dark:bg-gray-900 border-gray-100 dark:border-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
        }
      `}
      title={isSpeaking ? "Stop reading" : "Read response"}
    >
      {isSpeaking ? <PiStopBold size={14} /> : <PiSpeakerHighBold size={14} />}
    </button>
  );
};

export default VoiceButton;
