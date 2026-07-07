import React, { useMemo } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";

import remarkGfm from "remark-gfm";

import type { Source } from "@/store/slices/chatSlice";
import FollowUpButtons from "./ChatMarkdown/FollowUpButtons";
import CopyButton from "./ChatMarkdown/CopyButton";
import SourcesPanel from "./ChatMarkdown/SourcesPanel";
import VoiceButton from "./ChatMarkdown/VoiceButton";
import { PiArrowSquareOutBold } from "react-icons/pi";

interface ChatMarkdownProps {
  content: string;
  isBot?: boolean;
  suggestedFollowUps?: string[];
  sources?: Source[];
  onQuestionClick?: (question: string) => void;
  isStreaming?: boolean;
}

interface ParsedMarkdown {
  markdown: string;
  followUpQuestions: string[];
  parsedSources: Source[];
}

const parseMarkdownContent = (content: string): ParsedMarkdown => {
  if (!content) {
    return { markdown: "", followUpQuestions: [], parsedSources: [] };
  }

  const BASE_URL = window.location.origin;

  const cleanedContent = content;

  const lines = cleanedContent.split("\n");
  const followUpQuestions: string[] = [];
  const parsedSources: Source[] = [];
  const markdownLines: string[] = [];

  let inFollowUpSection = false;
  let inSourcesSection = false;

  lines.forEach((line) => {
    const trimmed = line.trim();
    const lowerTrimmed = trimmed.toLowerCase();

    if (
      lowerTrimmed.includes("follow-up questions") ||
      lowerTrimmed.includes("suggested questions")
    ) {
      inFollowUpSection = true;
      inSourcesSection = false;
      return;
    }

    if (
      lowerTrimmed.includes("### sources") ||
      (lowerTrimmed.startsWith("sources:") && trimmed.length < 15)
    ) {
      inSourcesSection = true;
      inFollowUpSection = false;
      return;
    }

    if (inFollowUpSection) {
      const match = trimmed.match(/^[-*]\s+(.*)/);

      if (match) {
        followUpQuestions.push(match[1].trim());
        return;
      }

      if (trimmed === "") return;

      inFollowUpSection = false;
    }

    if (inSourcesSection) {
      const match = trimmed.match(/^[-*]\s+\[(.*?)\]\((.*?)\)/);

      if (match) {
        let sourceUrl = match[2].trim();

        // 👉 Fix relative URLs here too
        if (sourceUrl.startsWith("/")) {
          sourceUrl = `${BASE_URL}${sourceUrl}`;
        }

        parsedSources.push({
          id: match[1].trim(),
          source: match[1].trim(),
          url: sourceUrl,
        });

        return;
      }

      if (trimmed === "") return;

      inSourcesSection = false;
    }

    markdownLines.push(line);
  });

  return {
    markdown: markdownLines.join("\n").trim(),
    followUpQuestions,
    parsedSources,
  };
};

const isFilteredLink = (href: any) => {
  return href === null || href === undefined || href === "#" || href === "https://example.com";
};

const shouldHideNode = (children: React.ReactNode): boolean => {
  return React.Children.toArray(children).every((child) => {
    if (child === null || child === undefined) return true;
    if (typeof child === "string") return !child.trim();
    if (React.isValidElement(child)) {
      // Check if it's an anchor tag with filtered href
      if (child.type === "a" || (child.props as any).href !== undefined) {
        return isFilteredLink((child.props as any).href);
      }
      // Recursively check children of common containers
      if (child.type === "p" || child.type === "span" || (child.props as any).children) {
        return shouldHideNode((child.props as any).children);
      }
    }
    return false;
  });
};

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="text-xl font-bold mt-4 mb-2">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold mt-4 mb-2">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold mt-3 mb-2">{children}</h3>
  ),
  p: ({ children }) => {
    if (shouldHideNode(children)) return null;
    return <p className="mb-2 leading-relaxed">{children}</p>;
  },
  ul: ({ children }) => <ul className="list-disc ml-6 mb-2">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal ml-6 mb-2">{children}</ol>,
  li: ({ children }) => {
    if (shouldHideNode(children)) return null;
    return <li className="mb-1">{children}</li>;
  },
  table: ({ children }) => (
    <div className="overflow-x-auto my-3">
      <table className="border border-gray-300 dark:border-gray-700 border-collapse w-full">
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border px-3 py-2 bg-gray-100 dark:bg-gray-800 text-left">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="border px-3 py-2">{children}</td>,
  code: ({
    inline,
    children,
    ...props
  }: React.ComponentPropsWithoutRef<"code"> & { inline?: boolean }) =>
    inline ? (
      <code
        className="px-1 py-0.5 rounded bg-gray-200 dark:bg-gray-800"
        {...props}
      >
        {children}
      </code>
    ) : (
      <pre className="bg-gray-900 text-white p-3 rounded-md overflow-x-auto">
        <code {...props}>{children}</code>
      </pre>
    ),
  a: ({ href, children }) => {
    if (!isFilteredLink(href)) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary font-semibold underline underline-offset-4 decoration-primary/30 hover:decoration-primary transition-all inline-flex items-center gap-0.5 group mx-0.5"
        >
          {children}
          <PiArrowSquareOutBold
            size={12}
            className="opacity-40 group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all duration-200"
          />
        </a>
      );
    }
    return null;
  },
};


const ChatMarkdown: React.FC<ChatMarkdownProps> = ({
  content,
  isBot = false,
  suggestedFollowUps = [],
  sources = [],
  onQuestionClick,
  isStreaming = false,
}) => {
  const { markdown, followUpQuestions, parsedSources } =
    useMemo(() => parseMarkdownContent(content), [content]);

  const finalFollowUps =
    suggestedFollowUps.length > 0 ? suggestedFollowUps : followUpQuestions;

  let finalSources = sources.length > 0 ? sources : parsedSources;

  return (
    <div className="relative group/markdown">
      <div className="prose prose-sm max-w-none dark:prose-invert break-words overflow-hidden">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={markdownComponents}
        >
          {markdown}
        </ReactMarkdown>
        {isStreaming && (
          <span className="inline-block w-1.5 h-4 ml-1 bg-primary animate-pulse align-middle" />
        )}

        {isBot && (
          <div className="flex gap-2 mt-6 mb-2">
            <VoiceButton content={markdown} />
            <CopyButton content={markdown} />
            <SourcesPanel sources={finalSources} />
          </div>
        )}

        <FollowUpButtons
          questions={finalFollowUps}
          onQuestionClick={onQuestionClick}
        />
      </div>
    </div>
  );
};

export default ChatMarkdown;
