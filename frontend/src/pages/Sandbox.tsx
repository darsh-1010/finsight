import React, { useState } from "react";
import {
  Sparkles,
  Trash2,
  Plus,
  Play,
  LineChart,
  BookOpen,
  AlertTriangle,
} from "lucide-react";
import { portfolioApi, type PortfolioAsset, type StressTestResponse } from "@/api/portfolio";
import { Button } from "@/components/ui/button";

const QUICK_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "NFLX", "META", "SPY", "QQQ"];

const Sandbox: React.FC = () => {
  const [assets, setAssets] = useState<PortfolioAsset[]>([
    { ticker: "AAPL", weight: 60 },
    { ticker: "MSFT", weight: 40 },
  ]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<StressTestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const totalWeight = assets.reduce((sum, asset) => sum + (asset.weight || 0), 0);

  const handleAddAsset = () => {
    setAssets([...assets, { ticker: "", weight: 0 }]);
  };

  const handleRemoveAsset = (index: number) => {
    if (assets.length <= 1) return;
    setAssets(assets.filter((_, i) => i !== index));
  };

  const handleAssetChange = (index: number, field: keyof PortfolioAsset, value: string | number) => {
    const updated = [...assets];
    if (field === "weight") {
      const numValue = typeof value === "string" ? parseFloat(value) || 0 : value;
      updated[index] = { ...updated[index], weight: numValue };
    } else {
      updated[index] = { ...updated[index], ticker: (value as string).toUpperCase() };
    }
    setAssets(updated);
  };

  const handleQuickAdd = (ticker: string) => {
    // Check if ticker already exists
    if (assets.some((a) => a.ticker === ticker)) return;
    
    // Add with weight 0 or split remaining weight
    const remaining = Math.max(0, 100 - totalWeight);
    setAssets([...assets, { ticker, weight: remaining > 0 ? remaining : 0 }]);
  };

  const handleNormalize = () => {
    if (totalWeight <= 0) return;
    const normalized = assets.map((asset) => ({
      ...asset,
      weight: Math.round(((asset.weight || 0) / totalWeight) * 1000) / 10,
    }));
    setAssets(normalized);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResults(null);

    // Validate tickers
    const emptyTickers = assets.some((a) => !a.ticker.trim());
    if (emptyTickers) {
      setError("Please fill in all ticker symbols.");
      return;
    }

    setLoading(true);
    try {
      // Send weights normalized (0.0 to 1.0)
      const payload = assets.map((a) => ({
        ticker: a.ticker.trim().toUpperCase(),
        weight: a.weight / 100,
      }));

      const res = await portfolioApi.runStressTest(payload);
      setResults(res);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 
        "Failed to calculate stress test. Please verify ticker symbols are valid on Yahoo Finance."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl p-4 md:p-8 space-y-8 animate-fade-in-up">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="p-1 rounded-lg bg-primary/10 text-primary">
            <Sparkles className="w-4 h-4" />
          </span>
          <span className="text-xs font-semibold text-primary uppercase tracking-widest">
            Interactive Tool
          </span>
        </div>
        <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          Portfolio Stress-Testing Sandbox
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Simulate historical crisis performance of custom portfolios using live Yahoo Finance market data.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Side: Builder */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-panel rounded-2xl p-6 border border-border/40 shadow-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl" />
            <h2 className="text-lg font-bold text-foreground mb-4 flex items-center gap-2">
              <LineChart className="w-5 h-5 text-primary" />
              Configure Assets
            </h2>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-3">
                {assets.map((asset, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <div className="flex-1">
                      <input
                        type="text"
                        placeholder="Ticker (e.g. AAPL)"
                        value={asset.ticker}
                        onChange={(e) => handleAssetChange(index, "ticker", e.target.value)}
                        className="w-full bg-secondary/40 border border-border/50 rounded-xl px-3.5 py-2.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all uppercase placeholder:normal-case"
                        required
                      />
                    </div>
                    <div className="w-28 relative">
                      <input
                        type="number"
                        placeholder="Weight"
                        min="0"
                        max="100"
                        step="any"
                        value={asset.weight || ""}
                        onChange={(e) => handleAssetChange(index, "weight", e.target.value)}
                        className="w-full bg-secondary/40 border border-border/50 rounded-xl pl-3.5 pr-8 py-2.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                        required
                      />
                      <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground text-xs font-bold">
                        %
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveAsset(index)}
                      disabled={assets.length <= 1}
                      className="p-2.5 rounded-xl hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Total Weight Indicators */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-secondary/30 border border-border/30 text-xs">
                <span className="font-semibold text-muted-foreground">Total Allocation:</span>
                <div className="flex items-center gap-2">
                  <span className={`font-bold ${totalWeight === 100 ? "text-primary" : "text-amber-500"}`}>
                    {totalWeight.toFixed(1)}%
                  </span>
                  {totalWeight !== 100 && totalWeight > 0 && (
                    <button
                      type="button"
                      onClick={handleNormalize}
                      className="text-primary hover:underline font-bold"
                    >
                      Auto-Normalize
                    </button>
                  )}
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAddAsset}
                  className="flex-1 rounded-xl py-5"
                >
                  <Plus className="w-4 h-4 mr-1.5" /> Add Asset
                </Button>
                <Button
                  type="submit"
                  disabled={loading || assets.length === 0}
                  className="flex-1 rounded-xl py-5 shadow-lg shadow-primary/20"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                      Simulating...
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <Play className="w-4 h-4 fill-current" /> Run Simulation
                    </span>
                  )}
                </Button>
              </div>
            </form>
          </div>

          {/* Quick Select Panel */}
          <div className="glass-panel rounded-2xl p-5 border border-border/40 shadow-sm">
            <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-3">
              Quick Add Tickers
            </h3>
            <div className="flex flex-wrap gap-2">
              {QUICK_TICKERS.map((ticker) => (
                <button
                  key={ticker}
                  type="button"
                  onClick={() => handleQuickAdd(ticker)}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-secondary hover:bg-primary hover:text-primary-foreground transition-all duration-200"
                >
                  +{ticker}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Side: Results */}
        <div className="lg:col-span-7 space-y-6">
          {error && (
            <div className="p-4 rounded-xl border border-destructive/20 bg-destructive/10 text-destructive text-sm flex gap-3 animate-fade-in-up">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-bold">Simulation Error</p>
                <p className="opacity-90 mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {!results && !error && !loading && (
            <div className="glass-panel rounded-2xl border border-border/40 p-12 text-center flex flex-col items-center justify-center min-h-[300px] group">
              <div className="p-4 rounded-full bg-secondary/80 text-muted-foreground group-hover:scale-110 transition-transform duration-300">
                <LineChart className="w-8 h-8 text-primary" />
              </div>
              <h3 className="text-lg font-bold text-foreground mt-4">No Active Simulation</h3>
              <p className="text-muted-foreground text-sm max-w-sm mt-1">
                Configure your mock portfolio assets and weights on the left, then click "Run Simulation" to evaluate performance.
              </p>
            </div>
          )}

          {loading && (
            <div className="glass-panel rounded-2xl border border-border/40 p-12 text-center flex flex-col items-center justify-center min-h-[300px]">
              <div className="relative w-16 h-16">
                <div className="absolute inset-0 rounded-full border-4 border-primary/20" />
                <div className="absolute inset-0 rounded-full border-4 border-primary border-t-transparent animate-spin" />
              </div>
              <h3 className="text-lg font-bold text-foreground mt-6">Simulating Historical Performance</h3>
              <p className="text-muted-foreground text-sm max-w-sm mt-1">
                Downloading historical daily prices from Yahoo Finance and computing crisis drawdowns...
              </p>
            </div>
          )}

          {results && (
            <div className="space-y-6 animate-fade-in-up">
              {/* Bento Grid Results */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* 2008 Crisis Card */}
                <div className="glass-panel rounded-2xl p-6 border border-border/40 relative overflow-hidden bento-hover">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-destructive/5 rounded-full blur-2xl" />
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                      2008 Financial Crisis
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full bg-destructive/10 text-destructive text-2xs font-extrabold uppercase">
                      Subprime Collapse
                    </span>
                  </div>

                  {results.crises["2008_Crash"]?.status === "success" ? (
                    <div className="space-y-4">
                      <div>
                        <p className="text-3xl font-extrabold tracking-tight text-foreground">
                          {results.crises["2008_Crash"].return_pct}%
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">Cumulative Period Return</p>
                      </div>
                      <div className="pt-2 border-t border-border/40">
                        <p className="text-xl font-bold text-destructive">
                          {results.crises["2008_Crash"].max_drawdown}%
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">Maximum Peak-to-Trough Drawdown</p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-muted-foreground text-xs py-8">
                      Insufficient historical data for this portfolio during the 2008 GFC.
                    </div>
                  )}
                </div>

                {/* 2020 COVID Card */}
                <div className="glass-panel rounded-2xl p-6 border border-border/40 relative overflow-hidden bento-hover">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-destructive/5 rounded-full blur-2xl" />
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                      2020 COVID-19 Dip
                    </span>
                    <span className="px-2.5 py-0.5 rounded-full bg-destructive/10 text-destructive text-2xs font-extrabold uppercase">
                      Pandemic Shock
                    </span>
                  </div>

                  {results.crises["2020_COVID"]?.status === "success" ? (
                    <div className="space-y-4">
                      <div>
                        <p className="text-3xl font-extrabold tracking-tight text-foreground">
                          {results.crises["2020_COVID"].return_pct}%
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">Cumulative Period Return</p>
                      </div>
                      <div className="pt-2 border-t border-border/40">
                        <p className="text-xl font-bold text-destructive">
                          {results.crises["2020_COVID"].max_drawdown}%
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">Maximum Peak-to-Trough Drawdown</p>
                      </div>
                    </div>
                  ) : (
                    <div className="text-muted-foreground text-xs py-8">
                      Insufficient historical data for this portfolio during the 2020 COVID dip.
                    </div>
                  )}
                </div>
              </div>

              {/* Custom SVG Comparison Chart */}
              <div className="glass-panel rounded-2xl p-6 border border-border/40">
                <h3 className="text-sm font-bold text-foreground mb-4">
                  Drawdown Comparison Chart
                </h3>

                {/* Render SVG Bar Chart */}
                <div className="w-full flex flex-col gap-4">
                  {Object.entries(results.crises).map(([name, data]) => {
                    if (data.status !== "success") return null;
                    const cleanName = name === "2008_Crash" ? "2008 Financial Crisis" : "2020 COVID Crash";
                    const maxVal = 100;
                    const drawdownPct = Math.abs(data.max_drawdown);
                    const widthPct = Math.min(100, Math.max(5, (drawdownPct / maxVal) * 100));

                    return (
                      <div key={name} className="space-y-1.5">
                        <div className="flex justify-between text-xs font-bold text-muted-foreground">
                          <span>{cleanName}</span>
                          <span className="text-destructive font-extrabold">{data.max_drawdown}% Drawdown</span>
                        </div>
                        <div className="h-6 w-full bg-secondary/40 rounded-full overflow-hidden border border-border/30">
                          <div
                            style={{ width: `${widthPct}%` }}
                            className="h-full bg-gradient-to-r from-destructive/60 to-destructive rounded-full transition-all duration-1000 shadow-inner"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Education / Insights Panel */}
              <div className="glass-panel rounded-2xl p-6 border border-border/40 bg-secondary/20 flex gap-4">
                <div className="p-3 h-fit rounded-xl bg-primary/10 text-primary shrink-0">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div className="space-y-1 text-sm">
                  <h4 className="font-bold text-foreground">Why Stress-Test Your Portfolio?</h4>
                  <p className="text-muted-foreground text-xs leading-relaxed">
                    Historical crisis simulations help you identify hidden asset correlations and structural risks. During GFC (2008), highly levered financial assets suffered major declines, whereas the 2020 COVID crash hit retail and hospitality segments instantly, but rebounded quickly due to central bank interventions.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Sandbox;
