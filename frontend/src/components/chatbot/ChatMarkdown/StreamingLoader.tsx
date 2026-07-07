import { useAuth } from "@/context/AuthContext";
import { useEffect, useMemo, useState } from "react";

type TierType = 1 | 2 | 3 | 4 | 5;

const TIER_MESSAGES: Record<TierType, string[]> = {
  1: [
    "Analyzing your question...",
    "Reviewing financial context...",
    "Preparing a simplified explanation...",
    "Gathering relevant insights...",
  ],

  2: [
    "Processing your market query...",
    "Analyzing trends and financial signals...",
    "Preparing personalized insights...",
    "Reviewing relevant market context...",
  ],

  3: [
    "Preparing a deeper market breakdown...",
    "Connecting insights across financial signals...",
    "Analyzing patterns and market context...",
    "Evaluating key financial indicators...",
  ],

  4: [
    "Running advanced market analysis...",
    "Synthesizing macro and technical insights...",
    "Evaluating multi-layer financial signals...",
    "Generating deeper AI-powered intelligence...",
  ],

  5: [
    "Processing advanced market intelligence models...",
    "Mapping market sentiment and trend signals...",
    "Running institutional-grade analysis...",
    "Generating high-depth financial insights...",
  ],
};

const StreamingLoader = () => {
  const { user } = useAuth();

  // Ensure tier is always a valid TierType
  const tier: TierType = (user?.tier_level as TierType) || 1;

  const messages = useMemo(() => {
    return TIER_MESSAGES[tier];
  }, [tier]);

  const [messageIndex, setMessageIndex] = useState(0);
  const [fade, setFade] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);

      const timeout = setTimeout(() => {
        setMessageIndex((prev) => (prev + 1) % messages.length);
        setFade(true);
      }, 250);

      return () => clearTimeout(timeout);
    }, 2800);

    return () => clearInterval(interval);
  }, [messages]);

  return (
    <div className="w-full py-2 px-2">
      <div className="flex flex-col gap-3">
        {/* Text Content */}
        <div className="flex flex-col gap-1">
          {/* Primary Message */}
          <p className="text-base font-medium text-foreground">
            FinSight is analyzing your request
          </p>

          {/* Rotating Secondary Message */}
          <p
            className={`text-sm text-muted-foreground transition-opacity duration-300 ${
              fade ? "opacity-100" : "opacity-0"
            }`}
          >
            {messages[messageIndex]}
          </p>
        </div>

        {/* Processing Loader */}
        <div className="mt-4 w-[400px] max-w-[400px] overflow-hidden rounded-full bg-muted/50 h-1.5 relative">
          <div className="absolute inset-0 bg-primary/10 animate-pulse" />
          <div className="h-full w-1/3 rounded-full bg-gradient-to-r from-primary/80 via-primary to-primary/80 shadow-[0_0_10px_rgba(3,87,255,0.3)] animate-[loading_1.5s_ease-in-out_infinite]" />
        </div>
      </div>
    </div>
  );
};

export default StreamingLoader;
