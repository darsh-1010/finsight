import React, { useEffect, useState } from "react";
import { PiSparkleFill } from "react-icons/pi";
import ChatInput from "./ChatInput";
import data from "@/data/finsight_starter_questions.json";
import { useAuth } from "@/context/AuthContext";

interface WelcomeProps {
  onSend: (msg: string, files: File[]) => void | Promise<boolean | void>;
  disabled: boolean;
  hideInput?: boolean;
  isUploading?: boolean;
  tokenLimitSnackbar?: React.ReactNode;
}

type Question = {
  id: string;
  tier: number;
  category: string;
  question: string;
};

export const getRandomQuestionsByTier = (
  tier: number = 1,
  limit: number = 3,
): Question[] => {
  const filtered = data.finsight_starter_questions.filter((q) => q.tier === tier);
  const shuffled = [...filtered].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, limit);
};

const WelcomeScreen: React.FC<WelcomeProps> = ({
  onSend,
  disabled,
  hideInput,
  isUploading,
  tokenLimitSnackbar,
}) => {
  const [questions, setQuestions] = useState<Question[]>([]);
  const { user } = useAuth();

  useEffect(() => {
    const result = getRandomQuestionsByTier(user?.tier_level || 1, 4);
    setQuestions(result);
  }, [user?.tier_level]);

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6 md:px-8 py-8 ">
      {/* Icon */}
      <div
        className="w-12 h-12 sm:w-20 sm:h-20 rounded-2xl sm:rounded-3xl bg-primary/10 
        flex items-center justify-center text-primary mb-6 sm:mb-8 border animate-pulse"
      >
        <PiSparkleFill className="text-2xl sm:text-4xl" />
      </div>

      {/* Heading */}
      <h1 className="text-xl sm:text-2xl md:text-3xl font-bold mb-3 sm:mb-4 text-center px-2">
        How can FinSight help you today?
      </h1>

      {/* Subtext */}
      <p className="text-gray-500 text-sm sm:text-base text-center max-w-xs sm:max-w-md mb-8 sm:mb-12">
        Ask about market insights, course roadmaps, or technical analysis.
      </p>

      {/* Content */}
      <div className="mt-4 sm:mt-8 w-full max-w-4xl">
        {/* Questions Grid */}
        <div
          className="
      max-h-[30vh] sm:max-h-[25vh] md:max-h-[25vh]
      overflow-y-auto pr-1
    "
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {questions.map((q) => (
              <button
                key={q.id}
                className="bg-primary/10 border hover:text-primary dark:hover:text-white 
            hover:border-primary/60 sm:px-4 sm:py-3 p-2 rounded-xl 
            dark:bg-white/10 dark:hover:bg-primary/10
            cursor-pointer text-xs sm:text-sm text-left
            wrap-break-word transition-all"
                onClick={() => void onSend(q.question, [])}
              >
                {q.question}
              </button>
            ))}
          </div>
        </div>

        {/* Input */}
        {!hideInput && (
          <div className="mt-6 sm:mt-8 w-full flex flex-col items-center">
            {tokenLimitSnackbar}
            <ChatInput onSend={onSend} isWelcome disabled={disabled} isUploading={isUploading} />
          </div>
        )}
      </div>
    </div>
  );
};

export default WelcomeScreen;
