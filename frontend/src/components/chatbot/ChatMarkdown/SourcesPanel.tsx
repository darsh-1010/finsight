import React from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { PiBookOpenLight, PiLinkSimpleBold } from "react-icons/pi";
import type { Source } from "@/store/slices/chatSlice";

interface SourcesPanelProps {
  sources: Source[];
}

const SourcesPanel: React.FC<SourcesPanelProps> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;

  return (
    <Sheet>
      <SheetTrigger asChild>
        <button
          className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-xl text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 transition-all active:scale-90 cursor-pointer"
          title={`${sources.length} ${sources.length === 1 ? "Source" : "Sources"}`}
        >
          <PiBookOpenLight size={14} className="shrink-0 text-primary" />
          <span className="text-xs font-bold leading-none">
            {sources.length}
          </span>
        </button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="w-full sm:max-w-md p-0 flex flex-col border-l border-gray-100 dark:border-gray-800"
      >
        <SheetHeader className="p-6 border-b border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50">
          <SheetTitle className="flex items-center gap-3 text-xl">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shadow-inner">
              <PiBookOpenLight size={20} />
            </div>
            <div className="flex flex-col items-start text-left">
              <span>Sources & Citations</span>
              <span className="text-xs font-normal text-gray-400">
                {sources.length} references found
              </span>
            </div>
          </SheetTitle>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {sources.map((source, idx) => (
              <a
                key={idx}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="
                  flex items-start gap-4 p-4 rounded-2xl
                  bg-white dark:bg-gray-900
                  border border-gray-100 dark:border-gray-800
                  hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5
                  transition-all duration-300 group no-underline
                "
              >
                <div className="w-12 h-12 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 flex items-center justify-center shrink-0 shadow-sm transition-all group-hover:scale-110 group-hover:bg-primary/5">
                  <PiLinkSimpleBold
                    size={20}
                    className="text-gray-400 group-hover:text-primary transition-colors"
                  />
                </div>

                <div className="flex-1 min-w-0 pt-0.5">
                  <p className="text-sm font-bold text-gray-700 dark:text-gray-200 m-0 truncate group-hover:text-primary transition-colors text-left">
                    {source.id || source.source}
                  </p>
                  <p className="text-[11px] text-gray-400 m-0 truncate opacity-60 group-hover:opacity-100 transition-opacity mt-1 text-left">
                    {source.url}
                  </p>
                </div>
              </a>
            ))}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
};

export default SourcesPanel;
