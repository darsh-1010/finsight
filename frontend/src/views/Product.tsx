import React from 'react';
import { PiUserLight } from 'react-icons/pi';



interface StatCardInterface {
  numbers: string;
  title: string;
  description: string;
}

const statsData: StatCardInterface[] = [
  {
    numbers: '60%',
    title: 'fewer impulsive decisions',
    description: `By focusing on structure, risk, and context, FinSight helps users avoid emotional and reactive choices.`,
  },
  {
    numbers: '3X',
    title: 'faster understanding',
    description: `Complex market concepts are broken down into clear, step-by-step explanations - without oversimplifying.`,
  },
  {
    numbers: '92%',
    title: 'more disciplined thinking',
    description: `FinSight helps users rely on logic and context instead of speculation, building disciplined decision-making over time.`,
  },
];

const StatCard = ({ numbers, title, description }: StatCardInterface) => (
  <div className="bg-card border border-border/50 rounded-3xl p-8 flex flex-col items-center text-center shadow-xs hover:shadow-lg transition-all duration-300 hover:border-primary/20 backdrop-blur-md">
    <span className="text-5xl font-extrabold text-primary mb-4">{numbers}</span>
    <h3 className="text-lg font-bold text-foreground mb-4">{title}</h3>
    <p className="text-muted-foreground text-sm leading-relaxed">
      {description}
    </p>
  </div>
);

const StatsSection = () => (
  <section className="w-full mt-32 relative overflow-hidden rounded-3xl border border-border/40">
    {/* Background with gradient */}
    <div className="absolute inset-0 bg-muted/20 z-0"></div>
    <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-primary/5 to-transparent z-0"></div>

    <div className="relative z-10 py-24 px-6 max-w-7xl mx-auto flex flex-col items-center">
      <h2 className="text-4xl md:text-5xl font-bold text-foreground text-center mb-6 leading-tight">
        Built for better decisions,
        <br />
        not faster trades
      </h2>
      <p className="text-muted-foreground text-center max-w-2xl mb-16 text-balance text-sm md:text-base">
        FinSight helps investors reduce noise, avoid costly mistakes, and build disciplined thinking - before any decision is made.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full">
        {statsData.map((elm, i) => (
          <StatCard
            key={`statecard-${i}`}
            numbers={elm.numbers}
            title={elm.title}
            description={elm.description}
          />
        ))}
      </div>
    </div>
  </section>
);

const DashbaordImage = () => {
  return (
    <div className="mt-16 w-full max-w-5xl rounded-3xl border border-border/40 bg-card/60 backdrop-blur-xl shadow-2xl overflow-hidden relative group">
      {/* Background gradients */}
      <div className="absolute top-0 right-0 w-80 h-80 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Dashboard container */}
      <div className="flex h-[520px] md:h-[600px] text-xs font-medium">
        {/* Mock Sidebar */}
        <div className="hidden sm:flex flex-col w-48 border-r border-border/40 bg-muted/20 p-4 shrink-0">
          <div className="flex items-center gap-2 mb-8 px-2">
            <span className="w-6 h-6 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold">F</span>
            <span className="font-logo font-bold text-sm tracking-tight text-foreground">FinSight</span>
          </div>
          <div className="space-y-1.5 flex-1">
            {[
              { label: 'Dashboard', active: false },
              { label: 'Market Insights', active: false },
              { label: 'Ask FinSight', active: false },
              { label: 'Portfolio Sandbox', active: true },
              { label: 'Profile & Billing', active: false },
            ].map((item) => (
              <div
                key={item.label}
                className={`flex items-center px-3 py-2.5 rounded-xl transition-all cursor-pointer ${
                  item.active
                    ? 'bg-primary text-primary-foreground font-semibold shadow-lg shadow-primary/20'
                    : 'text-muted-foreground hover:bg-secondary/40 hover:text-foreground'
                }`}
              >
                {item.label}
              </div>
            ))}
          </div>
          <div className="border-t border-border/30 pt-4 flex items-center gap-3 px-2">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold">U</div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-foreground truncate text-left">Active Investor</p>
              <p className="text-3xs text-muted-foreground truncate text-left">Tier 4 (Institutional)</p>
            </div>
          </div>
        </div>

        {/* Mock Content */}
        <div className="flex-1 flex flex-col min-w-0 bg-background/30">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-border/40">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded-md bg-primary/10 text-primary">
                <span className="w-2.5 h-2.5 rounded-full bg-primary inline-block" />
              </span>
              <span className="font-bold text-foreground">Stress-Testing Workspace</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-500 text-3xs font-extrabold uppercase">Live Connection</span>
              <div className="w-7 h-7 rounded-full bg-muted/60 flex items-center justify-center border border-border/40">
                <span className="w-2 h-2 rounded-full bg-primary" />
              </div>
            </div>
          </div>

          {/* Inner Content */}
          <div className="flex-1 p-6 space-y-6 overflow-y-auto">
            {/* Bento Grid top */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Asset weights */}
              <div className="md:col-span-1 border border-border/40 bg-card/40 rounded-2xl p-4 flex flex-col justify-between text-left">
                <div>
                  <h3 className="font-bold text-foreground mb-3 uppercase tracking-wider text-2xs text-muted-foreground">Portfolio Weights</h3>
                  <div className="space-y-2.5">
                    {[
                      { ticker: 'AAPL', weight: 60, color: 'bg-primary' },
                      { ticker: 'MSFT', weight: 40, color: 'bg-accent' },
                    ].map((asset) => (
                      <div key={asset.ticker} className="space-y-1">
                        <div className="flex justify-between font-bold text-foreground">
                          <span>{asset.ticker}</span>
                          <span>{asset.weight}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-muted/50 rounded-full overflow-hidden">
                          <div className={`h-full ${asset.color}`} style={{ width: `${asset.weight}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="pt-3 border-t border-border/30 mt-3 flex items-center justify-between text-2xs">
                  <span className="font-bold text-muted-foreground">Total: 100.0%</span>
                  <span className="text-primary font-bold hover:underline cursor-pointer">Auto-Normalize</span>
                </div>
              </div>

              {/* 2008 Crash */}
              <div className="border border-border/40 bg-card/40 rounded-2xl p-4 relative overflow-hidden text-left">
                <div className="absolute top-0 right-0 w-16 h-16 bg-destructive/5 rounded-full blur-xl" />
                <div className="flex items-center justify-between mb-3">
                  <span className="text-3xs font-bold text-muted-foreground uppercase tracking-wider">2008 Financial Crisis</span>
                  <span className="px-2 py-0.5 rounded-full bg-destructive/10 text-destructive text-3xs font-extrabold uppercase">GFC</span>
                </div>
                <div className="space-y-3 mt-4">
                  <div>
                    <p className="text-2xl font-black text-foreground">-34.50%</p>
                    <p className="text-3xs text-muted-foreground mt-0.5">Cumulative Period Return</p>
                  </div>
                  <div className="pt-2.5 border-t border-border/30">
                    <p className="text-lg font-bold text-destructive">-41.20%</p>
                    <p className="text-3xs text-muted-foreground mt-0.5">Max Peak-to-Trough Drawdown</p>
                  </div>
                </div>
              </div>

              {/* 2020 COVID */}
              <div className="border border-border/40 bg-card/40 rounded-2xl p-4 relative overflow-hidden text-left">
                <div className="absolute top-0 right-0 w-16 h-16 bg-destructive/5 rounded-full blur-xl" />
                <div className="flex items-center justify-between mb-3">
                  <span className="text-3xs font-bold text-muted-foreground uppercase tracking-wider">2020 COVID-19 Dip</span>
                  <span className="px-2 py-0.5 rounded-full bg-destructive/10 text-destructive text-3xs font-extrabold uppercase">Pandemic</span>
                </div>
                <div className="space-y-3 mt-4">
                  <div>
                    <p className="text-2xl font-black text-foreground">-12.80%</p>
                    <p className="text-3xs text-muted-foreground mt-0.5">Cumulative Period Return</p>
                  </div>
                  <div className="pt-2.5 border-t border-border/30">
                    <p className="text-lg font-bold text-destructive">-19.50%</p>
                    <p className="text-3xs text-muted-foreground mt-0.5">Max Peak-to-Trough Drawdown</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Performance line chart */}
            <div className="border border-border/40 bg-card/40 rounded-2xl p-4 text-left">
              <h3 className="font-bold text-foreground mb-4">Historical Stress Simulation Chart</h3>
              <div className="h-32 w-full relative">
                {/* SVG Chart Line */}
                <svg className="w-full h-full overflow-visible animate-fade-in-up" viewBox="0 0 100 30" preserveAspectRatio="none">
                  {/* Grid Lines */}
                  <line x1="0" y1="10" x2="100" y2="10" stroke="var(--border)" strokeWidth="0.1" strokeDasharray="1 1" />
                  <line x1="0" y1="20" x2="100" y2="20" stroke="var(--border)" strokeWidth="0.1" strokeDasharray="1 1" />
                  {/* Purple Line */}
                  <path
                    d="M0,10 L10,12 L20,8 L30,15 L40,25 L50,18 L60,26 L70,22 L80,28 L90,19 L100,24"
                    fill="none"
                    stroke="var(--primary)"
                    strokeWidth="1"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {/* Highlight circles */}
                  <circle cx="40" cy="25" r="1.5" fill="var(--destructive)" />
                  <circle cx="80" cy="28" r="1.5" fill="var(--destructive)" />
                </svg>
                {/* Labels */}
                <div className="absolute top-16 left-[40%] -translate-x-1/2 bg-destructive/10 text-destructive text-[8px] font-bold px-1.5 py-0.5 rounded-md border border-destructive/20 shadow-xs">
                  2008 Drawdown Bottom
                </div>
                <div className="absolute top-20 left-[80%] -translate-x-1/2 bg-destructive/10 text-destructive text-[8px] font-bold px-1.5 py-0.5 rounded-md border border-destructive/20 shadow-xs">
                  2020 Drawdown Bottom
                </div>
              </div>
              <div className="flex justify-between text-muted-foreground text-[10px] mt-2 font-semibold">
                <span>Start Period</span>
                <span>Crisis Maximum Bottom</span>
                <span>Recovery Period</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Product: React.FC = () => (
  <div className="flex items-center flex-col pt-24 pb-24 min-h-[calc(100vh-80px)] px-6 md:px-16 lg:px-24">
    <div className="flex flex-col items-center w-full max-w-3xl">
      <div className="w-16 h-16 rounded-full border border-border flex justify-center items-center relative">
        <div className="absolute w-12 h-12 animate-spin">
          <div
            className="absolute inset-0 rounded-full
                   border-2 border-transparent
                   border-t-primary border-b-primary"
          ></div>
        </div>
        <PiUserLight size={25} className="text-primary" />
      </div>
      <h1 className="text-center text-4xl sm:text-6xl my-8 font-semibold tracking-tight text-foreground leading-[1.1]">
        AI-powered intelligence for smarter investing
      </h1>
      <h4 className="text-center text-muted-foreground text-base md:text-lg max-w-2xl leading-relaxed">
        FinSight helps you understand markets with clarity and structure - using AI to explain risk, context, and market behavior before decisions are made.
      </h4>
    </div>
    <DashbaordImage />
    {/* Stats Section */}
    <StatsSection />
  </div>
);

export default Product;
