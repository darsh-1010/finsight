import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Trash2,
  Plus,
  Play,
  LineChart,
  BookOpen,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import {
  portfolioApi,
  type PortfolioAsset,
  type StressTestResponse,
  type StressScenario,
} from "@/api/portfolio";
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
  const [availableScenarios, setAvailableScenarios] = useState<StressScenario[]>([]);
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>([
    "2008_Crash",
    "2020_COVID",
  ]);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(
    "Historical Crashes"
  );

  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        const list = await portfolioApi.getStressScenarios();
        setAvailableScenarios(list);
      } catch (err) {
        console.error("Failed to load stress test scenarios", err);
      }
    };
    fetchScenarios();
  }, []);

  const groupedScenarios = availableScenarios.reduce((acc, sc) => {
    if (!acc[sc.category]) acc[sc.category] = [];
    acc[sc.category].push(sc);
    return acc;
  }, {} as Record<string, typeof availableScenarios>);

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

      if (selectedScenarios.length === 0) {
        setError("Please select at least one stress scenario to simulate.");
        return;
      }

      const res = await portfolioApi.runStressTest(payload, selectedScenarios);
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

          {/* Stress Scenarios Selector */}
          <div className="glass-panel rounded-2xl p-6 border border-border/40 shadow-sm space-y-4">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded-lg bg-primary/10 text-primary">
                <Sparkles className="w-4 h-4" />
              </span>
              <h2 className="text-base font-bold text-foreground">
                Select Stress Scenarios
              </h2>
            </div>
            <p className="text-muted-foreground text-xs">
              Choose which historical crises and hypothetical regimes to simulate.
            </p>

            {/* Quick Actions */}
            <div className="flex flex-wrap gap-2 text-2xs font-bold">
              <button
                type="button"
                onClick={() => setSelectedScenarios(["2008_Crash", "2020_COVID"])}
                className="px-2.5 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 text-muted-foreground transition-all duration-200"
              >
                Reset to Defaults
              </button>
              <button
                type="button"
                onClick={() => setSelectedScenarios(availableScenarios.map((s) => s.id))}
                className="px-2.5 py-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary transition-all duration-200"
              >
                Select All ({availableScenarios.length})
              </button>
              <button
                type="button"
                onClick={() => setSelectedScenarios([])}
                className="px-2.5 py-1.5 rounded-lg bg-destructive/10 hover:bg-destructive/20 text-destructive transition-all duration-200"
              >
                Clear All
              </button>
            </div>

            {/* Category Accordion */}
            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1 custom-scrollbar">
              {Object.entries(groupedScenarios).map(([category, list]) => {
                const isExpanded = expandedCategory === category;
                const selectedCount = list.filter((s) =>
                  selectedScenarios.includes(s.id)
                ).length;

                return (
                  <div
                    key={category}
                    className="border border-border/30 rounded-xl overflow-hidden bg-secondary/10"
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedCategory(isExpanded ? null : category)}
                      className="w-full px-4 py-3 flex items-center justify-between text-xs font-bold text-foreground hover:bg-secondary/20 transition-all text-left"
                    >
                      <span className="flex items-center gap-1.5">
                        {category}
                        <span className="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-3xs font-extrabold">
                          {selectedCount}/{list.length}
                        </span>
                      </span>
                      {isExpanded ? (
                        <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
                      )}
                    </button>

                    {isExpanded && (
                      <div className="p-3 border-t border-border/20 bg-background/40 space-y-2 animate-fade-in-up">
                        {list.map((sc) => {
                          const isChecked = selectedScenarios.includes(sc.id);
                          return (
                            <label
                              key={sc.id}
                              className="flex items-start gap-2.5 p-2 rounded-lg hover:bg-secondary/20 cursor-pointer transition-all duration-150"
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => {
                                  if (isChecked) {
                                    setSelectedScenarios(
                                      selectedScenarios.filter((id) => id !== sc.id)
                                    );
                                  } else {
                                    setSelectedScenarios([...selectedScenarios, sc.id]);
                                  }
                                }}
                                className="mt-0.5 rounded border-border/60 text-primary focus:ring-primary h-3.5 w-3.5 accent-primary"
                              />
                              <div className="space-y-0.5">
                                <p className="text-xs font-bold text-foreground flex items-center gap-1.5 flex-wrap">
                                  {sc.name}
                                  {sc.type === "synthetic" && (
                                    <span className="px-1.5 py-0.2 bg-purple-500/20 text-purple-400 text-3xs font-black uppercase rounded">
                                      Hypothetical
                                    </span>
                                  )}
                                </p>
                                <p className="text-muted-foreground text-3xs leading-normal">
                                  {sc.description}
                                </p>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
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
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-h-[500px] overflow-y-auto pr-1 custom-scrollbar">
                {Object.entries(results.crises).map(([key, data]) => {
                  const scenarioInfo = availableScenarios.find((s) => s.id === key);
                  const displayName = scenarioInfo?.name || key.replace(/_/g, " ");
                  const displayCategory = scenarioInfo?.category || "Stress Test";
                  const displayDesc = scenarioInfo?.description || "";
                  const isSuccess = data.status === "success";

                  const isNegative = data.return_pct < 0;
                  const returnColorClass = isNegative ? "text-red-500" : "text-emerald-500";

                  return (
                    <div
                      key={key}
                      className="glass-panel rounded-2xl p-6 border border-border/40 relative overflow-hidden bento-hover flex flex-col justify-between"
                    >
                      <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl pointer-events-none" />

                      <div>
                        <div className="flex items-start justify-between gap-2 mb-3">
                          <span className="text-xs font-bold text-foreground leading-snug">
                            {displayName}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-secondary text-muted-foreground text-3xs font-extrabold uppercase shrink-0">
                            {displayCategory}
                          </span>
                        </div>
                        <p className="text-3xs text-muted-foreground leading-normal mb-4">
                          {displayDesc}
                        </p>
                      </div>

                      {isSuccess ? (
                        <div className="space-y-3 pt-3 border-t border-border/30 mt-auto">
                          <div className="flex justify-between items-baseline">
                            <span className="text-2xs text-muted-foreground">Cumulative Return</span>
                            <span className={`text-base font-extrabold ${returnColorClass}`}>
                              {data.return_pct}%
                            </span>
                          </div>
                          <div className="flex justify-between items-baseline">
                            <span className="text-2xs text-muted-foreground">Max Drawdown</span>
                            <span className="text-base font-extrabold text-destructive">
                              {data.max_drawdown}%
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="text-muted-foreground text-xs py-4 border-t border-border/30 mt-auto">
                          Insufficient historical data for this portfolio during this period.
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Custom SVG Comparison Chart */}
              <div className="glass-panel rounded-2xl p-6 border border-border/40">
                <h3 className="text-sm font-bold text-foreground mb-4">
                  Drawdown Comparison Chart
                </h3>

                <div className="w-full flex flex-col gap-4 max-h-[350px] overflow-y-auto pr-1 custom-scrollbar">
                  {Object.entries(results.crises).map(([name, data]) => {
                    if (data.status !== "success") return null;
                    const scenarioInfo = availableScenarios.find((s) => s.id === name);
                    const cleanName = scenarioInfo?.name || name.replace(/_/g, " ");
                    const maxVal = 100;
                    const drawdownPct = Math.abs(data.max_drawdown);
                    const widthPct = Math.min(100, Math.max(5, (drawdownPct / maxVal) * 100));

                    return (
                      <div key={name} className="space-y-1.5 animate-fade-in-up">
                        <div className="flex justify-between text-xs font-bold text-muted-foreground">
                          <span>{cleanName}</span>
                          <span className="text-destructive font-extrabold">
                            {data.max_drawdown}% Drawdown
                          </span>
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
                    Historical crisis simulations and hypothetical sector shocks help you identify hidden asset correlations and structural risk exposure. For instance, tech bubble bursts or rate tightening impact high-multiple growth equities instantly, while supply chain spikes favor commodity and energy sectors over transportation or consumer retail.
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
