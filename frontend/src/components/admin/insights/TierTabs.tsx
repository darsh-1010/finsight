import type React from 'react';

import type { TierInsightGroup } from './types';

import { cn } from '@/lib/utils';

const TierTabs: React.FC<{
  groups: TierInsightGroup[];
  activeTier: number | null;
  onTierChange: (tier: number) => void;
}> = ({ groups, activeTier, onTierChange }) => (
  <div
    role="tablist"
    aria-label="Insight tiers"
    className="flex gap-3 overflow-x-auto"
  >
    {groups.map((group) => {
      const isActive = group.tier === activeTier;

      return (
        <button
          key={group.tier}
          role="tab"
          aria-selected={isActive}
          onClick={() => onTierChange(group.tier)}
          className={cn(
            'flex h-9 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-semibold transition-colors',
            isActive
              ? 'bg-[#9683C2] text-white shadow-sm'
              : 'bg-card border border-border text-muted-foreground hover:bg-secondary hover:text-foreground',
          )}
        >
          <span>Tier {group.tier}</span>
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-[10px]',
              isActive
                ? 'bg-white/20 text-white'
                : 'bg-secondary/80 text-muted-foreground',
            )}
          >
            {group.count}
          </span>
        </button>
      );
    })}
  </div>
);

export default TierTabs;
