import { clsx, type ClassValue } from 'clsx';
import { PiBookOpenDuotone } from 'react-icons/pi';
import { PiBrainDuotone } from 'react-icons/pi';
import { PiStarFourDuotone } from 'react-icons/pi';
import { PiCrownDuotone } from 'react-icons/pi';
import { SlEnergy } from 'react-icons/sl';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const getTierIcon = (level: number) => {
  switch (level) {
  case 1:
    return PiBookOpenDuotone;
  case 2:
    return PiBrainDuotone;
  case 3:
    return PiStarFourDuotone;
  case 4:
    return SlEnergy;
  case 5:
    return PiCrownDuotone;
  default:
    return PiBookOpenDuotone;
  }
};

/**
 * Strips markdown syntax from a string to return plain text.
 */
export const stripMarkdown = (markdown: string): string => {
  if (!markdown) return "";
  
  return markdown
    // Remove code blocks
    .replace(/```[\s\S]*?```/g, "")
    // Remove inline code
    .replace(/`([^`]+)`/g, "$1")
    // Remove HTML tags
    .replace(/<[^>]*>/g, "")
    // Remove images ![alt](url)
    .replace(/!\[([^\]]*)\]\([^\)]+\)/g, "$1")
    // Remove links [text](url)
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
    // Remove headers
    .replace(/^#+\s+/gm, "")
    // Remove emphasis (bold, italic)
    .replace(/([*_]{1,3})(.*?)\1/g, "$2")
    // Remove strikethrough
    .replace(/~~(.*?)~~/g, "$1")
    // Remove blockquotes
    .replace(/^\s*>\s+/gm, "")
    // Remove list markers
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    // Remove horizontal rules
    .replace(/^-{3,}|^\*{3,}|^_{3,}/gm, "")
    // Replace multiple newlines with single ones
    .replace(/\n{3,}/g, "\n\n")
    .trim();
};