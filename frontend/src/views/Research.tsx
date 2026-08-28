import { FileSearch, Loader2, AlertTriangle, ExternalLink } from 'lucide-react';
import React, { useState } from 'react';

import { researchApi, type ResearchReport } from '@/api/research';
import { Button } from '@/components/ui/button';
import LockedFeature from '@/components/upgrade/LockedFeature';
import { useAuth } from '@/context/AuthContext';

const MIN_RESEARCH_TIER = 2;

const ReportSection: React.FC<{ title: string; children: React.ReactNode }> = ({
  title,
  children,
}) => (
  <div className="mb-4">
    <h3 className="text-sm font-bold uppercase tracking-wide text-muted-foreground mb-1">
      {title}
    </h3>
    <p className="text-sm leading-relaxed">{children}</p>
  </div>
);

const ReportHeader: React.FC<{ report: ResearchReport }> = ({ report }) => (
  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6 pb-4 border-b border-border/50">
    <div>
      <h2 className="text-2xl font-bold">
        {report.company_name || report.ticker}{' '}
        <span className="text-muted-foreground font-normal">({report.ticker})</span>
      </h2>
      <p className="text-xs text-muted-foreground mt-1">
        Generated {new Date(report.generated_at).toLocaleString()}
        {report.from_cache && ' · cached'}
      </p>
    </div>
  </div>
);

const ReportWarnings: React.FC<{ warnings: string[] }> = ({ warnings }) => {
  if (warnings.length === 0) return null;

  return (
    <div className="mb-6 p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-sm text-amber-600 dark:text-amber-400 flex items-start gap-2">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <ul className="space-y-1">
        {warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </div>
  );
};

const FilingHighlights: React.FC<{ highlights: string[] }> = ({ highlights }) => {
  if (highlights.length === 0) return null;

  return (
    <div className="mb-4">
      <h3 className="text-sm font-bold uppercase tracking-wide text-muted-foreground mb-1">
        From the latest SEC filing
      </h3>
      <ul className="list-disc list-inside text-sm space-y-1">
        {highlights.map((h, i) => (
          <li key={i}>{h}</li>
        ))}
      </ul>
    </div>
  );
};

const ReportSources: React.FC<{ sources: ResearchReport['sources'] }> = ({ sources }) => (
  <div className="mt-6 pt-4 border-t border-border/50">
    <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-2">
      Sources
    </h3>
    <div className="flex flex-wrap gap-2">
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.url || undefined}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-secondary/50 hover:bg-secondary text-foreground/80"
        >
          {s.source}
          {s.url && <ExternalLink size={10} />}
        </a>
      ))}
    </div>
  </div>
);

const ReportCard: React.FC<{ report: ResearchReport }> = ({ report }) => (
  <div className="bg-card border border-border rounded-2xl neon-card p-6 md:p-8 mt-8">
    <ReportHeader report={report} />
    <ReportWarnings warnings={report.warnings} />

    <ReportSection title="Summary">{report.summary}</ReportSection>
    <ReportSection title="Valuation">{report.valuation_take}</ReportSection>
    <ReportSection title="Growth">{report.growth_take}</ReportSection>
    <ReportSection title="Risk">{report.risk_take}</ReportSection>

    <FilingHighlights highlights={report.filing_highlights} />
    <ReportSources sources={report.sources} />
  </div>
);

const useResearch = () => {
  const [ticker, setTicker] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;

    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const result = await researchApi.getReport(ticker.trim());

      setReport(result);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      const detail = error.response?.data?.detail;

      setError(typeof detail === 'string' ? detail : 'Failed to generate research report. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return { ticker, setTicker, loading, report, error, handleSubmit };
};

const Research: React.FC = () => {
  const { user } = useAuth();
  const { ticker, setTicker, loading, report, error, handleSubmit } = useResearch();

  const isLocked = !!user && user.tier_level < MIN_RESEARCH_TIER;

  return (
    <div className="max-w-3xl mx-auto p-4 md:p-8">
      <div className="flex items-center gap-3 mb-2">
        <FileSearch className="text-primary" size={28} />
        <h1 className="text-2xl font-bold">Research</h1>
      </div>
      <p className="text-muted-foreground text-sm mb-6">
        Get a structured, cited research brief for any company — combining live market
        data with its latest SEC filing.
      </p>

      {isLocked ? (
        <LockedFeature
          title="Research Reports"
          description="Unlock structured, cited research briefs for any company."
          requiredTier={MIN_RESEARCH_TIER}
        />
      ) : (
        <>
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="Ticker or company name (e.g. AAPL, Apple)"
              className="flex-1 px-4 py-3 rounded-xl border border-border/60 bg-background/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
            />
            <Button type="submit" disabled={loading || !ticker.trim()} className="px-6">
              {loading ? <Loader2 className="animate-spin" size={18} /> : 'Research'}
            </Button>
          </form>

          {error && (
            <div className="mt-4 p-3.5 bg-destructive/10 border border-destructive/20 text-destructive rounded-xl text-sm text-center">
              {error}
            </div>
          )}

          {report && <ReportCard report={report} />}
        </>
      )}
    </div>
  );
};

export default Research;
