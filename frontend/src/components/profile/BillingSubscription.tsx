import { CreditCard } from "lucide-react";
import React from "react";
import type { User as UserInterface } from "@/api/auth";
import { getTierIcon } from "@/lib/utils";
import UpgradeModal from "./UpgradeModal";

interface BillingSubscriptionProps {
  user: UserInterface | null;
  embedded?: boolean;
}

type IconType = React.ComponentType<{ size?: number; className?: string }>;

const ICON_MAP: Record<number, IconType> = {
  0: CreditCard,
  1: getTierIcon(1),
  2: getTierIcon(2),
  3: getTierIcon(3),
  4: getTierIcon(4),
  5: getTierIcon(5),
};

const BillingSubscription: React.FC<BillingSubscriptionProps> = ({
  user,
  embedded = false,
}) => {
  const Icon = ICON_MAP[user?.tier_level ?? 0] || CreditCard;

  const content = (
    <div className="space-y-3 relative z-10 w-full max-w-4xl mx-auto">
      {/* Modern Combined Subscription Card */}
      <div className="relative overflow-hidden rounded-[1.5rem] border border-border/40 bg-gradient-to-br from-card to-card/40 shadow-xl transition-all">
        {/* Glassmorphism background blobs */}
        <div className="absolute -top-16 -right-16 w-32 h-32 bg-primary/20 blur-[50px] rounded-full pointer-events-none" />
        <div className="absolute -bottom-16 -left-16 w-32 h-32 bg-blue-500/10 blur-[50px] rounded-full pointer-events-none" />

        <div className="relative p-4 sm:p-5 space-y-4">
          {/* Header Section */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-background/80 backdrop-blur-md rounded-xl shadow-inner border border-primary/20 text-primary">
                <Icon size={20} />
              </div>
              <div>
                <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-[0.15em] mb-0.5">
                  Current Plan
                </p>
                <h2 className="text-xl sm:text-2xl font-extrabold text-foreground tracking-tight">
                  {user?.tier_name || "Foundation"}
                </h2>
              </div>
            </div>

            {user?.tier_level !== 1 && (
              <span className="inline-flex items-center justify-center font-bold uppercase text-[9px] tracking-widest px-2.5 py-1 rounded-md backdrop-blur-md border bg-green-500/10 text-green-600 border-green-500/20 dark:text-green-400">
                Active
              </span>
            )}
          </div>

          {/* Billing Details Grid */}
          {user?.tier_level === 1 ? (
            <div className="bg-background/40 backdrop-blur-sm border border-primary/20 rounded-xl p-4 text-center">
              <p className="text-sm text-foreground/80 font-medium">
                You are currently on the{" "}
                <span className="text-primary font-bold">Foundation</span> plan.
                Upgrade below to unlock premium features.
              </p>
            </div>
          ) : (
            <div className="bg-background/40 backdrop-blur-sm border border-primary/20 rounded-xl p-4 text-center">
              <p className="text-sm text-foreground/80 font-medium">
                You are currently on a premium plan.
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 pt-2">
            <div className="flex-1">
              <UpgradeModal />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {embedded ? (
        <div className="relative overflow-hidden rounded-2xl p-2 sm:p-4">
          {content}
        </div>
      ) : (
        <section className="p-6 sm:p-8 rounded-3xl neon-card overflow-hidden relative border border-primary/20 bg-primary/5 shadow-xl">
          <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-[80px] -mr-32 -mt-32 pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-500/10 rounded-full blur-[80px] -ml-32 -mb-32 pointer-events-none" />

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 relative z-10">
            <h2 className="text-2xl font-bold flex items-center gap-3 text-foreground">
              <div className="p-2 bg-primary/10 rounded-lg">
                <CreditCard size={24} className="text-primary" />
              </div>
              Subscription
            </h2>
            <p className="text-sm text-muted-foreground font-medium">
              Your active plan
            </p>
          </div>

          {content}
        </section>
      )}
    </>
  );
};

export default BillingSubscription;
