import { format } from "date-fns";
import { ChevronDown, Loader2 } from "lucide-react";
import React, { useState } from "react";

import type { TokenTransaction } from "@/api/tokens";

/* -------------------- Utils -------------------- */

const formatNumber = (value: number) =>
  new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);

const formatDateTime = (value: string | null) => {
  if (!value) return "—";

  return format(new Date(value), "MMM d, yyyy · h:mm a");
};

const formatLabel = (value: string) =>
  value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

const TransactionTypeBadge = ({ type }: { type: string }) => (
  <span className="inline-flex text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-secondary text-muted-foreground">
    {formatLabel(type)}
  </span>
);

const TransactionsTable = ({
  transactions,
  isLoading,
}: {
  transactions: TokenTransaction[];
  isLoading: boolean;
}) => (
  <>
    {isLoading ? (
      <div className="flex justify-center py-6">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    ) : transactions.length === 0 ? (
      <p className="text-sm text-muted-foreground py-4">
        No token transactions yet.
      </p>
    ) : (
      <div className="overflow-x-auto rounded-xl border border-border/50">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/50 bg-secondary/30 text-left">
              <th className="px-3 py-2 font-medium text-muted-foreground">
                Date
              </th>
              <th className="px-3 py-2 font-medium text-muted-foreground">
                Type
              </th>
              <th className="px-3 py-2 font-medium text-muted-foreground text-right">
                Tokens
              </th>
              <th className="px-3 py-2 font-medium text-muted-foreground text-right hidden sm:table-cell">
                Balance
              </th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx) => (
              <tr
                key={tx.id}
                className="border-b border-border/30 last:border-0"
              >
                <td className="px-3 py-2.5 text-xs whitespace-nowrap">
                  {formatDateTime(tx.created_at)}
                </td>
                <td className="px-3 py-2.5">
                  <TransactionTypeBadge type={tx.transaction_type} />
                  {tx.description && (
                    <p className="text-xs text-muted-foreground mt-1 max-w-[200px] truncate">
                      {tx.description}
                    </p>
                  )}
                </td>
                <td
                  className={`px-3 py-2.5 text-right font-semibold tabular-nums ${
                    tx.tokens >= 0
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-500"
                  }`}
                >
                  {tx.tokens >= 0 ? "+" : ""}
                  {formatNumber(tx.tokens)}
                </td>
                <td className="px-3 py-2.5 text-right text-xs text-muted-foreground hidden sm:table-cell tabular-nums">
                  {formatNumber(tx.balance_before)} →{" "}
                  {formatNumber(tx.balance_after)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </>
);

interface RecentTransactionsAccordionProps {
  transactions: TokenTransaction[];
  isLoading: boolean;
}

const RecentTransactionsAccordion: React.FC<RecentTransactionsAccordionProps> = ({
  transactions,
  isLoading,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const transactionCount = transactions.length;

  return (
    <div className="rounded-xl border border-border/50 overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-4 px-4 py-3 text-left hover:bg-secondary/30 transition-colors"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <div>
          <h3 className="text-sm font-semibold">Recent Transactions</h3>
          <p className="text-xs text-muted-foreground">
            {isLoading
              ? "Loading transaction history"
              : `${transactionCount} recent ${transactionCount === 1 ? "entry" : "entries"}`}
          </p>
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
            isOpen ? "rotate-180" : ""
          }`}
          aria-hidden="true"
        />
      </button>

      {isOpen && (
        <div className="border-t border-border/50 p-3">
          <TransactionsTable
            transactions={transactions}
            isLoading={isLoading}
          />
        </div>
      )}
    </div>
  );
};

export default RecentTransactionsAccordion;
