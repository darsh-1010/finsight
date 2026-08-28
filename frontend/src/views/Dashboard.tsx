import React, { useState, useEffect, useRef } from "react";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  BarChart2,
  Zap,
  Clock,
} from "lucide-react";
import { gsap } from "gsap";

import TradingViewChart from "../components/dashboard/TradingViewChart";
import TradingViewCryptoNews from "../components/dashboard/TradingViewCryptoNews";
import TradingViewTickerTape from "../components/dashboard/TradingViewTickerTape";
import TradingViewMarketOverview from "../components/dashboard/TradingViewMarketOverview";
import TradingViewCalendar from "../components/dashboard/TradingViewCalendar";
import TradingViewTechnicalAnalysis from "../components/dashboard/TradingViewTechnicalAnalysis";
import TradingViewScreener from "../components/dashboard/TradingViewScreener";

import { TierWelcomeModal } from "../components/modals/TierWelcomeModal";

import { useAppDispatch } from "@/store/hooks";
import { fetchTiers } from "@/store/slices/tierSlice";

/* ─── KPI Card Data ───────────────────────────────────── */
interface KpiCardProps {
  title: string;
  value: string;
  change: string;
  changePositive: boolean;
  icon: React.ReactNode;
  subtext: string;
  delay: string;
}

const kpiData: Omit<KpiCardProps, "delay">[] = [
  {
    title: "S&P 500",
    value: "5,842.47",
    change: "+1.24%",
    changePositive: true,
    icon: <TrendingUp className="w-5 h-5" />,
    subtext: "Today vs. Yesterday",
  },
  {
    title: "Bitcoin (BTC)",
    value: "$61,254",
    change: "+2.31%",
    changePositive: true,
    icon: <Activity className="w-5 h-5" />,
    subtext: "24h Performance",
  },
  {
    title: "Market Fear/Greed",
    value: "68 / 100",
    change: "Greed",
    changePositive: true,
    icon: <BarChart2 className="w-5 h-5" />,
    subtext: "CNN Index",
  },
  {
    title: "Gold (XAU/USD)",
    value: "$3,287",
    change: "-0.43%",
    changePositive: false,
    icon: <DollarSign className="w-5 h-5" />,
    subtext: "Spot Price",
  },
];

const KpiCard: React.FC<KpiCardProps> = ({
  title,
  value,
  change,
  changePositive,
  icon,
  subtext,
  delay,
}) => (
  <div
    className="kpi-card flex items-center gap-4 py-4 px-5 will-change-transform"
    style={{ animationDelay: delay, opacity: 0, transform: 'translateY(16px)' }}
  >
    <div className="text-muted-foreground/70 shrink-0">{icon}</div>
    <div className="min-w-0">
      <span className="text-xs font-medium text-muted-foreground">{title}</span>
      <div className="flex items-baseline gap-2 flex-wrap">
        <p className="text-xl font-semibold text-foreground tracking-tight">{value}</p>
        <span
          className={`inline-flex items-center gap-1 text-xs font-medium ${
            changePositive ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"
          }`}
        >
          {changePositive ? (
            <TrendingUp className="w-3 h-3" />
          ) : (
            <TrendingDown className="w-3 h-3" />
          )}
          {change}
        </span>
      </div>
      <span className="text-xs text-muted-foreground/70">{subtext}</span>
    </div>
  </div>
);

/* ─── Animated Section Wrapper ────────────────────────── */
const AnimatedSection: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => {
  const sectionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          gsap.to(el, { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out' });
          observer.unobserve(el);
        }
      },
      { threshold: 0.08 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={sectionRef}
      className={className}
      style={{ opacity: 0, transform: 'translateY(24px)' }}
    >
      {children}
    </div>
  );
};

/* ─── Header ──────────────────────────────────────────── */
const HeaderComponent = () => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="dashboard-header flex flex-col md:flex-row md:items-center justify-between gap-3" style={{ opacity: 0 }}>
      <div>
        <div className="flex items-center gap-1.5 mb-1">
          <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-widest">
            Live
          </span>
        </div>
        <h1 className="text-xl md:text-2xl font-semibold text-foreground">
          Market Intelligence Dashboard
        </h1>
        <p className="text-muted-foreground mt-0.5 text-sm">
          Real-time insights and technical analysis.
        </p>
      </div>
      <div className="flex items-center gap-2 text-muted-foreground">
        <Clock className="w-3.5 h-3.5" />
        <span className="text-sm font-mono text-foreground/80">
          {time.toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </span>
        <span className="text-xs">{time.toLocaleDateString()}</span>
      </div>
    </div>
  );
};

/* ─── Section Label ───────────────────────────────────── */
const SectionLabel: React.FC<{ icon: React.ReactNode; label: string }> = ({
  icon,
  label,
}) => (
  <div className="flex items-center gap-2 mb-4 text-muted-foreground">
    {icon}
    <h2 className="text-sm font-semibold text-foreground/90 tracking-wide">{label}</h2>
    <div className="flex-1 h-px bg-border/40 ml-2" />
  </div>
);

/* ─── GSAP Entry Animations ───────────────────────────── */
const useDashboardAnimations = () => {
  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.to('.dashboard-header', { opacity: 1, duration: 0.6, ease: 'power2.out', delay: 0.1 });
      gsap.to('.kpi-card', { opacity: 1, y: 0, duration: 0.55, stagger: 0.1, ease: 'power3.out', delay: 0.3 });
    });
    return () => ctx.revert();
  }, []);
};

/* ─── Hook ────────────────────────────────────────────── */
const useDashboardHook = () => {
  const [showWelcomeModal, setShowWelcomeModal] = useState(() => {
    const storageKey = "has_shown_welcome_modal";
    return typeof window !== "undefined" && !!localStorage.getItem(storageKey);
  });

  const dispatch = useAppDispatch();

  useEffect(() => {
    dispatch(fetchTiers());
  }, [dispatch]);

  const handleCloseWelcomeModal = () => {
    localStorage.removeItem("has_shown_welcome_modal");
    setShowWelcomeModal(false);
  };

  return { handleCloseWelcomeModal, showWelcomeModal };
};

/* ─── Main Dashboard ──────────────────────────────────── */
const Dashboard: React.FC = () => {
  const { showWelcomeModal, handleCloseWelcomeModal } = useDashboardHook();
  useDashboardAnimations();

  return (
    <div className="space-y-6">
      <TierWelcomeModal isOpen={showWelcomeModal} onClose={handleCloseWelcomeModal} />

      {/* Ticker Tape */}
      <TradingViewTickerTape />

      <div className="p-4 md:p-6 space-y-10">
        {/* Header */}
        <HeaderComponent />

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y divide-border/40 sm:divide-y-0 sm:divide-x rounded-xl border border-border/40">
          {kpiData.map((kpi, i) => (
            <KpiCard key={i} {...kpi} delay={`${i * 100}ms`} />
          ))}
        </div>

        {/* Primary Chart */}
        <AnimatedSection>
          <SectionLabel icon={<Activity className="w-4 h-4" />} label="Live Chart" />
          <div className="w-full">
            <TradingViewChart />
          </div>
        </AnimatedSection>

        {/* Row 1: Technical Analysis + Market Overview + Crypto News */}
        <AnimatedSection>
          <SectionLabel icon={<BarChart2 className="w-4 h-4" />} label="Market Signals" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <TradingViewTechnicalAnalysis />
            <TradingViewMarketOverview />
            <TradingViewCryptoNews />
          </div>
        </AnimatedSection>

        {/* Row 2: Screener + Calendar */}
        <AnimatedSection>
          <SectionLabel icon={<Zap className="w-4 h-4" />} label="Research & Events" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TradingViewScreener />
            <TradingViewCalendar />
          </div>
        </AnimatedSection>
      </div>
    </div>
  );
};

export default Dashboard;
