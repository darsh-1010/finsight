import React from 'react';
import { PiLightbulbLight, PiXCircleFill, PiCheckCircleFill } from 'react-icons/pi';

const WeDontColComponent: React.FC = () => (
  <div className="rounded-3xl border border-red-500/20 bg-red-500/5 p-8 md:p-12 relative overflow-hidden group">
    <div className="absolute top-0 inset-x-0 h-px bg-linear-to-r from-transparent via-red-500/50 to-transparent opacity-50"></div>
    <div className="flex items-center justify-center gap-3 mb-10">
      <div className="p-2 rounded-full bg-red-500/10 text-red-500">
        <PiXCircleFill size={24} />
      </div>
      <h3 className="text-2xl font-bold text-foreground">We don&apos;t</h3>
    </div>
    <div className="space-y-5">
      {[
        'Tell you what to buy or sell',
        'Promote speculation or hype',
        'Provide financial advice',
        'Encourage short-term decisions',
        'Gamify investing or risky behavior',
        'Operate as a trading platform',
      ].map((item, i) => (
        <div key={i} className="flex items-center gap-3 text-red-500/80">
          <PiXCircleFill className="shrink-0" size={20} />
          <span className="text-muted-foreground font-medium">{item}</span>
        </div>
      ))}
    </div>
  </div>
);

const FinSightHelpsYouColComponent: React.FC = () => (
  <div className="rounded-3xl border border-green-500/20 bg-green-500/5 p-8 md:p-12 relative overflow-hidden group">
    <div className="absolute top-0 inset-x-0 h-px bg-linear-to-r from-transparent via-green-500/50 to-transparent opacity-50"></div>
    <div className="flex items-center justify-center gap-3 mb-10">
      <div className="p-2 rounded-full bg-green-500/10 text-green-500">
        <PiCheckCircleFill size={24} />
      </div>
      <h3 className="text-2xl font-bold text-foreground">FinSight helps you</h3>
    </div>
    <div className="space-y-5">
      {[
        'Understand risk and market context',
        'Learn long-term decision-making',
        'Build investment knowledge',
        'Connect learning with execution',
        'Think like an institutional investor',
        'Use AI for clarity, not signals',
      ].map((item, i) => (
        <div key={i} className="flex items-center gap-3 text-green-500">
          <PiCheckCircleFill className="shrink-0" size={20} />
          <span className="text-foreground font-medium">{item}</span>
        </div>
      ))}
    </div>
  </div>
);

const PricingAlternative: React.FC = () => (
  <div className="mt-32 w-full max-w-6xl">
    <div className="flex flex-col items-center text-center mb-16">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-primary/10 border border-primary/20 mb-6">
        <PiLightbulbLight className="text-primary" />
        <span className="text-xs font-semibold uppercase tracking-wider text-primary">
          The Solution
        </span>
      </div>
      <h2 className="text-3xl md:text-5xl font-bold mb-6 text-foreground">
        A smarter alternative to
        <br />
        speculation-first platforms
      </h2>
      <p className="text-muted-foreground max-w-2xl text-lg">
        FinSight combines structured education with AI-powered investment
        intelligence to help users understand markets before taking action.
      </p>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 relative">
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 hidden md:flex items-center justify-center w-12 h-12 rounded-full bg-background border border-border shadow-lg">
        <span className="font-bold text-muted-foreground text-sm">v/s</span>
      </div>

      <WeDontColComponent />
      <FinSightHelpsYouColComponent />
    </div>
  </div>
);

export default PricingAlternative;
