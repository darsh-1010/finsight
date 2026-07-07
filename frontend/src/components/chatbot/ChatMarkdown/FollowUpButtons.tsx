
const FollowUpButtons = ({
  questions,
  onQuestionClick,
}: {
  questions: string[];
  onQuestionClick?: (question: string) => void;
}) => {
  if (!questions.length) return null;

  return (
    <div className="mt-6 flex flex-col gap-3">
      <div className="flex items-center gap-2 text-gray-400">
        <div className="h-px flex-1 bg-gray-100 dark:bg-gray-800" />
        <span className="text-[10px] font-bold uppercase tracking-widest shrink-0">
          Suggested
        </span>
        <div className="h-px flex-1 bg-gray-100 dark:bg-gray-800" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {questions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onQuestionClick?.(question)}
            className="
              px-4 py-2.5 rounded-xl text-left text-xs sm:text-sm
              border border-gray-200 dark:border-gray-800
              bg-white dark:bg-gray-900
              hover:bg-primary/5 hover:text-primary hover:border-primary/30
              transition-all duration-200 cursor-pointer shadow-sm
              relative overflow-hidden group w-full break-words
            "
          >
            <div className="absolute inset-y-0 left-0 w-1 bg-primary transform scale-x-0 group-hover:scale-x-100 transition-transform duration-200" />
            {question}
          </button>
        ))}
      </div>
    </div>
  );
};

export default FollowUpButtons;
