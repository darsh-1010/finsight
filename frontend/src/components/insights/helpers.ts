import React from "react";
import { ArrowUpRight, ArrowDownRight, LineChart } from "lucide-react";
import type { WeeklyTrend } from "./marketInsightTypes";

export const formatPriceChange = (value?: number) => {
  if (value === undefined || value === null) return "";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
};

export const getTrendStyle = (trend?: WeeklyTrend) => {
  if (trend === "Bullish") {
    return {
      labelClass: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20",
      icon: React.createElement(ArrowUpRight, { className: "h-3.5 w-3.5" }),
      borderClass: "border-l-rose-500",
    };
  }

  if (trend === "Bearish") {
    return {
      labelClass: "bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20",
      icon: React.createElement(ArrowDownRight, { className: "h-3.5 w-3.5" }),
      borderClass: "border-l-red-500",
    };
  }

  return {
    labelClass: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20",
    icon: React.createElement(LineChart, { className: "h-3.5 w-3.5" }),
    borderClass: "border-l-sky-500",
  };
};

export const getShortLabel = (url: string): string => {
  try {
    const hostname = new URL(url).hostname;
    const parts = hostname.replace(/^www\./, "").split(".");
    return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
  } catch {
    return url;
  }
};

export const getFaviconUrl = (url: string): string => {
  try {
    const origin = new URL(url).origin;
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(origin)}&sz=16`;
  } catch {
    return "";
  }
};

export const getRelativeTime = (dateStr?: string) => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const hours = Math.floor(diffMs / 3600000);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days} day${days > 1 ? "s" : ""} ago`;
  if (hours > 0) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  if (diffMins > 0) return `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`;
  return "Just now";
};

export const isToday = (dateStr?: string) => {
  if (!dateStr) return false;
  const date = new Date(dateStr);
  const today = new Date();
  return (
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate()
  );
};

export const isCurrentWeek = (dateStr?: string) => {
  if (!dateStr) return false;
  const date = new Date(dateStr);
  const today = new Date();
  
  const currentWeekStart = new Date(today);
  currentWeekStart.setDate(today.getDate() - today.getDay());
  currentWeekStart.setHours(0, 0, 0, 0);
  
  return date.getTime() >= currentWeekStart.getTime();
};

export const getGroupDateLabel = (dateStr?: string) => {
  if (!dateStr) return "Older Signals";
  const date = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  const isSameDay = (d1: Date, d2: Date) =>
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate();

  const options: Intl.DateTimeFormatOptions = { month: "long", day: "numeric" };
  const formattedDate = date.toLocaleDateString("en-US", options);

  if (isSameDay(date, today)) {
    return `Today, ${formattedDate}`;
  } else if (isSameDay(date, yesterday)) {
    return `Yesterday, ${formattedDate}`;
  } else {
    const weekday = date.toLocaleDateString("en-US", { weekday: "long" });
    return `${weekday}, ${formattedDate}`;
  }
};
