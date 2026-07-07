import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { IoArrowForwardOutline } from 'react-icons/io5';
import { motion, useScroll, useTransform } from 'framer-motion';
import {
  PiMonitor,
  PiUserFocus,
  PiBuildings,
  PiBrain,
  PiDatabase,
  PiChartLine,
  PiShieldCheck,
  PiArrowRight,
  PiSparkleFill,
  PiChartPieSlice,
  PiGraduationCap,
  PiLightning,
} from 'react-icons/pi';

import { Button } from '@/components/ui/button';

/* ─── Animated Counter ────────────────────────────────── */
const AnimatedCounter: React.FC<{ end: number; suffix?: string; duration?: number }> = ({
  end,
  suffix = '',
  duration = 2000,
}) => {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          const startTime = performance.now();
          const step = (now: number) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * end));
            if (progress < 1) requestAnimationFrame(step);
            else setCount(end);
          };
          requestAnimationFrame(step);
        }
      },
      { threshold: 0.5 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [end, duration]);

  return (
    <span ref={ref}>
      {count}
      {suffix}
    </span>
  );
};

/* ─── 3D Hero Section ────────────────────────────────────── */
const HeroSection = () => {
  const { scrollY } = useScroll();
  const y1 = useTransform(scrollY, [0, 1000], [0, 200]);
  const y2 = useTransform(scrollY, [0, 1000], [0, -100]);
  const scale = useTransform(scrollY, [0, 1000], [1, 1.2]);
  const opacity = useTransform(scrollY, [0, 500], [1, 0]);

  return (
    <div className="relative flex flex-col justify-center items-center min-h-[calc(100vh-80px)] px-6 text-center pt-16 pb-8 overflow-hidden perspective-[1000px]">
      {/* Dynamic 3D Background */}
      <motion.div style={{ scale, opacity }} className="absolute inset-0 z-0 pointer-events-none">
        <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-background/20" />
        <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full bg-primary/20 blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-[30rem] h-[30rem] rounded-full bg-purple-500/20 blur-[150px]" />
      </motion.div>

      <div className="w-full max-w-5xl flex flex-col items-center justify-center z-10 relative">
        <motion.div 
          initial={{ opacity: 0, y: -20, rotateX: 30 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="flex items-center gap-3 border border-primary/30 px-5 py-2 rounded-full bg-background/60 backdrop-blur-xl shadow-2xl shadow-primary/10 hover:border-primary/60 transition-all cursor-pointer mb-10"
        >
          <span className="flex h-2.5 w-2.5 rounded-full bg-primary animate-pulse shadow-[0_0_12px_var(--color-primary)]" />
          <p className="text-xs md:text-sm font-bold tracking-wide text-foreground uppercase">
            Join 200+ Professional Investors
          </p>
          <span className="text-xs bg-primary/20 px-3 py-1 rounded-full text-primary font-bold">Explore</span>
        </motion.div>

        <motion.h1 
          initial={{ opacity: 0, y: 40, rotateX: -20 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ duration: 1, ease: "easeOut", delay: 0.2 }}
          className="text-5xl sm:text-7xl md:text-[6rem] font-extrabold tracking-tighter max-w-5xl leading-[1.05] text-foreground drop-shadow-2xl"
        >
          Redefining <span className="text-transparent bg-clip-text bg-gradient-to-br from-primary via-purple-500 to-accent drop-shadow-sm">Intelligence</span> for the Modern Investor
        </motion.h1>

        <motion.p 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: "easeOut", delay: 0.4 }}
          className="mt-8 text-lg md:text-2xl text-muted-foreground max-w-3xl leading-relaxed font-medium"
        >
          Experience the future of financial research with AI-driven insights, institutional thinking, and education-first portfolio analysis.
        </motion.p>

        <motion.div 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, ease: "easeOut", delay: 0.6 }}
          className="mt-12 flex flex-col sm:flex-row gap-6 items-center"
        >
          <Link to="/try-finsight">
            <Button className="text-lg py-7 px-12 rounded-full bg-primary text-primary-foreground shadow-2xl shadow-primary/30 hover:shadow-primary/50 hover:scale-[1.05] active:scale-95 transition-all duration-300 font-bold group">
              Start Your Journey
              <IoArrowForwardOutline className="ml-3 group-hover:translate-x-2 transition-transform" />
            </Button>
          </Link>
          <Link to="/product">
            <Button variant="outline" className="text-lg py-7 px-12 rounded-full border-2 border-border/80 hover:border-primary/40 hover:bg-primary/5 hover:text-primary transition-all font-bold group hover:-translate-y-1 transform duration-300">
              Discover Product <PiSparkleFill className="ml-3 text-primary group-hover:rotate-12 transition-transform" />
            </Button>
          </Link>
        </motion.div>

        {/* Social proof numbers */}
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1 }}
          className="mt-24 flex flex-wrap justify-center gap-12 sm:gap-24"
        >
          {[
            { value: 200, suffix: '+', label: 'Investors' },
            { value: 60, suffix: '%', label: 'Better Decisions' },
            { value: 3, suffix: 'X', label: 'Faster Understanding' },
          ].map((stat) => (
            <motion.div 
              key={stat.label} 
              whileHover={{ scale: 1.1, y: -5 }}
              className="text-center group"
            >
              <p className="text-4xl sm:text-6xl font-black text-foreground group-hover:text-primary transition-colors duration-300 drop-shadow-xl">
                <AnimatedCounter end={stat.value} suffix={stat.suffix} />
              </p>
              <p className="text-sm uppercase tracking-widest font-bold text-muted-foreground mt-3">{stat.label}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>

      {/* 3D Floating elements */}
      <motion.div style={{ y: y1 }} className="absolute right-[5%] top-[20%] hidden xl:block">
        <div className="glass-panel p-6 rounded-3xl rotate-12 hover:rotate-0 transition-transform duration-500 shadow-2xl backdrop-blur-xl border border-white/10">
          <PiBrain className="text-6xl text-primary drop-shadow-[0_0_15px_rgba(255,68,51,0.5)]" />
        </div>
      </motion.div>
      <motion.div style={{ y: y2 }} className="absolute left-[5%] top-[40%] hidden xl:block">
        <div className="glass-panel p-6 rounded-3xl -rotate-12 hover:rotate-0 transition-transform duration-500 shadow-2xl backdrop-blur-xl border border-white/10">
          <PiChartLine className="text-6xl text-purple-500 drop-shadow-[0_0_15px_rgba(168,85,247,0.5)]" />
        </div>
      </motion.div>
    </div>
  );
};

/* ─── Features Marquee Strip ──────────────────────────── */
const features = [
  { icon: <PiBrain size={20} />, text: 'RAG-Powered Research' },
  { icon: <PiChartLine size={20} />, text: 'Real-time Market Data' },
  { icon: <PiGraduationCap size={20} />, text: 'Education-First Approach' },
  { icon: <PiShieldCheck size={20} />, text: 'Multi-Tier Compliance' },
  { icon: <PiDatabase size={20} />, text: 'Institutional Intelligence' },
  { icon: <PiLightning size={20} />, text: 'Lightning-Fast Insights' },
  { icon: <PiChartPieSlice size={20} />, text: 'Portfolio Analytics' },
  { icon: <PiSparkleFill size={20} />, text: 'AI-Driven Signals' },
];

const FeatureStrip = () => (
  <div className="overflow-hidden border-y border-primary/20 bg-primary/5 py-6 relative backdrop-blur-md">
    <div className="flex animate-marquee gap-16 whitespace-nowrap">
      {[...features, ...features, ...features].map((f, i) => (
        <div key={i} className="flex items-center gap-3 text-foreground shrink-0">
          <span className="text-primary bg-primary/10 p-2 rounded-xl">{f.icon}</span>
          <span className="text-base font-bold uppercase tracking-wide">{f.text}</span>
          <span className="ml-12 text-primary/40 text-xl">✦</span>
        </div>
      ))}
    </div>
  </div>
);

/* ─── 3D Card Hook for Features ───────────────────────── */
const useTilt = (maxTilt = 20) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const handleMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      const rotateX = ((y - cy) / cy) * -maxTilt;
      const rotateY = ((x - cx) / cx) * maxTilt;
      el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.05,1.05,1.05)`;
    };

    const handleLeave = () => {
      el.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)';
    };

    el.addEventListener('mousemove', handleMove);
    el.addEventListener('mouseleave', handleLeave);
    return () => {
      el.removeEventListener('mousemove', handleMove);
      el.removeEventListener('mouseleave', handleLeave);
    };
  }, [maxTilt]);

  return ref;
};

/* ─── Who It's For ────────────────────────────────────── */
const audienceCards = [
  {
    icon: <PiMonitor size={36} />,
    title: 'Retail Investors',
    description: 'Build real investing foundations — understand risk, market cycles, and disciplined thinking before you act.',
    tag: 'Getting Started',
  },
  {
    icon: <PiUserFocus size={36} />,
    title: 'Serious Investors',
    description: 'Upgrade your decision-making discipline with AI-backed analysis and institutional-grade context.',
    tag: 'Level Up',
  },
  {
    icon: <PiBuildings size={36} />,
    title: 'Institutions & Funds',
    description: 'Access advanced research, compliance controls, and deep intelligence tools built for professionals.',
    tag: 'Enterprise',
  },
];

const WhoItsForSection = () => {
  return (
    <section className="py-32 relative overflow-hidden bg-background">
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/5 via-background to-background" />
      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <motion.div 
          initial={{ opacity: 0, y: 50 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8 }}
          className="text-center max-w-4xl mx-auto mb-24"
        >
          <span className="inline-block px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-sm font-bold uppercase tracking-widest text-primary mb-6 shadow-[0_0_15px_rgba(255,68,51,0.2)]">
            Ecosystem
          </span>
          <h2 className="text-4xl md:text-6xl font-black tracking-tight text-foreground mb-6 drop-shadow-md">
            Engineered For Excellence
          </h2>
          <p className="text-muted-foreground text-lg md:text-xl font-medium">
            Whether you&apos;re starting your wealth journey or managing institutional portfolios.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {audienceCards.map((card, i) => {
            const tiltRef = useTilt(15);
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.6, delay: i * 0.2 }}
                className="perspective-[1000px]"
              >
                <div
                  ref={tiltRef}
                  className="glass-panel p-10 rounded-3xl flex flex-col items-start group will-change-transform cursor-pointer border-t border-l border-white/10 shadow-2xl transition-all duration-200 h-full bg-gradient-to-br from-background/80 to-background/40"
                >
                  <div className="flex items-center justify-between w-full mb-8">
                    <div className="p-5 bg-gradient-to-br from-primary to-purple-600 rounded-2xl text-white shadow-xl shadow-primary/30 group-hover:scale-110 transition-transform duration-300">
                      {card.icon}
                    </div>
                    <span className="text-xs font-black uppercase tracking-wider text-muted-foreground bg-secondary/80 px-4 py-2 rounded-full border border-border/50 shadow-inner">
                      {card.tag}
                    </span>
                  </div>
                  <h3 className="text-2xl font-black text-foreground mb-4 group-hover:text-primary transition-colors">{card.title}</h3>
                  <p className="text-muted-foreground text-base leading-relaxed font-medium mb-8 flex-grow">{card.description}</p>
                  <div className="flex items-center gap-2 text-primary text-base font-bold group-hover:gap-4 transition-all duration-300">
                    Explore Solutions <PiArrowRight size={20} />
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

/* ─── CTA Banner ──────────────────────────────────────── */
const CTASection = () => {
  return (
    <section className="py-32 px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-background pointer-events-none" />
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1 }}
        className="max-w-5xl mx-auto relative z-10"
      >
        <div className="relative overflow-hidden rounded-[3rem] border border-primary/30 bg-gradient-to-br from-primary/10 via-background to-purple-900/10 p-16 md:p-24 text-center shadow-[0_0_50px_rgba(255,68,51,0.15)] backdrop-blur-2xl">
          {/* Animated glow */}
          <div className="absolute inset-0 pointer-events-none">
            <motion.div 
              animate={{ rotate: 360 }}
              transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 blur-[100px] rounded-full" 
            />
          </div>

          <div className="relative z-10">
            <h2 className="text-4xl md:text-6xl font-black text-foreground mb-8 leading-tight drop-shadow-lg">
              Elevate Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-purple-500">Portfolio</span> Today
            </h2>
            <p className="text-muted-foreground text-lg md:text-2xl font-medium max-w-2xl mx-auto mb-12">
              Join professionals who understand markets before they make decisions. Start with FinSight today.
            </p>
            <div className="flex flex-col sm:flex-row gap-6 justify-center">
              <Link to="/try-finsight">
                <Button className="text-lg py-8 px-14 rounded-full bg-primary text-white shadow-2xl shadow-primary/40 hover:shadow-primary/60 hover:scale-105 active:scale-95 transition-all duration-300 font-bold group">
                  Start for Free <IoArrowForwardOutline className="ml-3 group-hover:translate-x-2 transition-transform" />
                </Button>
              </Link>
              <Link to="/pricing">
                <Button variant="outline" className="text-lg py-8 px-14 rounded-full border-2 border-primary/30 bg-background/50 backdrop-blur-md hover:bg-primary hover:text-white hover:border-primary transition-all font-bold hover:scale-105 duration-300">
                  View Pricing
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  );
};

/* ─── Main ────────────────────────────────────────────── */
const LandingPage: React.FC = () => (
  <main className="relative bg-background">
    <HeroSection />
    <FeatureStrip />
    <WhoItsForSection />
    <CTASection />
  </main>
);

export default LandingPage;
