import { gsap } from 'gsap';
import { motion } from 'framer-motion';
import Link from 'next/link';
import React, { useEffect, useRef, useState } from 'react';
import { IoArrowForwardOutline } from 'react-icons/io5';
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
import * as THREE from 'three';

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

/* ─── Interactive Three.js Background ────────────────────── */
const InteractiveThreeBackground: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // Scene
    const scene = new THREE.Scene();

    // Camera
    const camera = new THREE.PerspectiveCamera(60, width / height, 1, 1000);

    camera.position.z = 400;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });

    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Particles Group
    const group = new THREE.Group();

    scene.add(group);

    // Create particles
    const particleCount = 100;
    const r = 350;
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);
      const radius = r * Math.cbrt(Math.random());

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      velocities[i * 3] = (Math.random() - 0.5) * 0.4;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.4;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.4;
    }

    const pointsGeometry = new THREE.BufferGeometry();

    pointsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const pointsMaterial = new THREE.PointsMaterial({
      color: 0xB49C6E,
      size: 4,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
    });

    const points = new THREE.Points(pointsGeometry, pointsMaterial);

    group.add(points);

    // Line segments geometry
    const lineGeometry = new THREE.BufferGeometry();
    const lineMaterial = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      blending: THREE.AdditiveBlending,
      linewidth: 1,
    });

    const lines = new THREE.LineSegments(lineGeometry, lineMaterial);

    group.add(lines);

    // Mouse tracking
    let mouseX = 0;
    let mouseY = 0;
    const handleMouseMove = (event: MouseEvent) => {
      mouseX = (event.clientX / window.innerWidth) - 0.5;
      mouseY = (event.clientY / window.innerHeight) - 0.5;
    };

    window.addEventListener('mousemove', handleMouseMove);

    // Animation Loop
    let animationFrameId: number;
    const maxDistance = 120;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Rotate group gently
      group.rotation.y += 0.001;
      group.rotation.x += 0.0005;

      // Parallax camera movement based on mouse
      camera.position.x += (mouseX * 250 - camera.position.x) * 0.05;
      camera.position.y += (-mouseY * 250 - camera.position.y) * 0.05;
      camera.lookAt(scene.position);

      const posAttr = pointsGeometry.getAttribute('position') as THREE.BufferAttribute;
      const posArray = posAttr.array as Float32Array;

      for (let i = 0; i < particleCount; i++) {
        posArray[i * 3] += velocities[i * 3];
        posArray[i * 3 + 1] += velocities[i * 3 + 1];
        posArray[i * 3 + 2] += velocities[i * 3 + 2];

        // Boundary checks (bounce back)
        const x = posArray[i * 3];
        const y = posArray[i * 3 + 1];
        const z = posArray[i * 3 + 2];
        const dist = Math.sqrt(x*x + y*y + z*z);

        if (dist > r) {
          velocities[i * 3] *= -1;
          velocities[i * 3 + 1] *= -1;
          velocities[i * 3 + 2] *= -1;
        }
      }
      posAttr.needsUpdate = true;

      const linePositions: number[] = [];
      const lineColors: number[] = [];

      for (let i = 0; i < particleCount; i++) {
        for (let j = i + 1; j < particleCount; j++) {
          const dx = posArray[i * 3] - posArray[j * 3];
          const dy = posArray[i * 3 + 1] - posArray[j * 3 + 1];
          const dz = posArray[i * 3 + 2] - posArray[j * 3 + 2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

          if (dist < maxDistance) {
            linePositions.push(posArray[i * 3], posArray[i * 3 + 1], posArray[i * 3 + 2]);
            linePositions.push(posArray[j * 3], posArray[j * 3 + 1], posArray[j * 3 + 2]);

            const alpha = 1.0 - (dist / maxDistance);

            lineColors.push(0.706 * alpha, 0.612 * alpha, 0.431 * alpha);
            lineColors.push(0.706 * alpha, 0.612 * alpha, 0.431 * alpha);
          }
        }
      }

      lineGeometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
      lineGeometry.setAttribute('color', new THREE.Float32BufferAttribute(lineColors, 3));

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;

      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return <div ref={containerRef} className="absolute inset-0 z-0 pointer-events-none" />;
};

/* ─── 3D Hero Section ────────────────────────────────────── */
const HeroSection = () => (
  <div className="relative flex flex-col justify-center items-center min-h-[calc(100vh-80px)] px-6 text-center pt-16 pb-8 overflow-hidden perspective-[1000px]">
    {/* Interactive WebGL 3D Constellation Background */}
    <InteractiveThreeBackground />

    {/* Dynamic Glow Overlays */}
    <div className="absolute inset-0 z-0 pointer-events-none">
      <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-background/20" />
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full bg-primary/10 blur-[120px]" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-[30rem] h-[30rem] rounded-full bg-accent/10 blur-[150px]" />
    </div>

    <div className="w-full max-w-5xl flex flex-col items-center justify-center z-10 relative">
      <h1 className="hero-title text-5xl sm:text-7xl md:text-[6rem] font-extrabold tracking-tighter max-w-5xl leading-[1.05] text-foreground drop-shadow-2xl">
          Redefining <span className="text-transparent bg-clip-text bg-gradient-to-br from-primary via-amber-500 to-accent drop-shadow-sm">Intelligence</span> for the Modern Investor
      </h1>

      <p className="hero-subtitle mt-8 text-lg md:text-2xl text-muted-foreground max-w-3xl leading-relaxed font-medium">
          Experience the future of financial research with AI-driven insights, institutional thinking, and education-first portfolio analysis.
      </p>

      <div className="hero-buttons mt-12 flex flex-col sm:flex-row gap-6 items-center">
        <Link href="/try-finsight">
          <Button className="text-lg py-7 px-12 rounded-full bg-primary text-primary-foreground shadow-2xl shadow-primary/30 hover:shadow-primary/50 hover:scale-[1.05] active:scale-95 transition-all duration-300 font-bold group">
              Start Your Journey
            <IoArrowForwardOutline className="ml-3 group-hover:translate-x-2 transition-transform" />
          </Button>
        </Link>
        <Link href="/product">
          <Button variant="outline" className="text-lg py-7 px-12 rounded-full border-2 border-border/80 hover:border-primary/40 hover:bg-primary/5 hover:text-primary transition-all font-bold group hover:-translate-y-1 transform duration-300">
              Discover Product <PiSparkleFill className="ml-3 text-primary group-hover:rotate-12 transition-transform" />
          </Button>
        </Link>
      </div>

      {/* Social proof numbers */}
      <div className="mt-24 flex flex-wrap justify-center gap-12 sm:gap-24">
        {[
          { value: 60, suffix: '%', label: 'Better Decisions' },
          { value: 3, suffix: 'X', label: 'Faster Understanding' },
        ].map((stat) => (
          <div key={stat.label} className="hero-social-stat text-center group">
            <p className="text-4xl sm:text-6xl font-black text-foreground group-hover:text-primary transition-colors duration-300 drop-shadow-xl">
              <AnimatedCounter end={stat.value} suffix={stat.suffix} />
            </p>
            <p className="text-sm uppercase tracking-widest font-bold text-muted-foreground mt-3">{stat.label}</p>
          </div>
        ))}
      </div>
    </div>
  </div>
);

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

const WhoItsForSection = () => (
  <section className="py-32 relative overflow-hidden bg-background">
    <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/5 via-background to-background" />
    <div className="max-w-7xl mx-auto px-6 relative z-10">
      <motion.div
        className="text-center max-w-4xl mx-auto mb-24"
        initial={{ opacity: 0, y: 40 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.1 }}
        transition={{ duration: 1, ease: 'easeOut' }}
      >
        <span className="inline-block px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-sm font-bold uppercase tracking-widest text-primary mb-6 shadow-[0_0_15px_rgba(212,169,79,0.2)]">
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
              className="perspective-[1000px]"
              initial={{ opacity: 0, y: 60, rotateX: 10 }}
              whileInView={{ opacity: 1, y: 0, rotateX: 0 }}
              viewport={{ once: true, amount: 0.1 }}
              transition={{ duration: 1, delay: i * 0.2, ease: 'easeOut' }}
            >
              <div
                ref={tiltRef}
                className="glass-panel p-10 rounded-3xl flex flex-col items-start group will-change-transform cursor-pointer border-t border-l border-white/10 shadow-2xl transition-all duration-200 h-full bg-gradient-to-br from-background/80 to-background/40"
              >
                <div className="flex items-center justify-between w-full mb-8">
                  <div className="p-5 bg-gradient-to-br from-primary to-amber-600 rounded-2xl text-white shadow-xl shadow-primary/30 group-hover:scale-110 transition-transform duration-300">
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

/* ─── CTA Banner ──────────────────────────────────────── */
const CTASection = () => (
  <section className="py-32 px-6 relative overflow-hidden">
    <div className="absolute inset-0 bg-background pointer-events-none" />
    <motion.div
      className="max-w-5xl mx-auto relative z-10"
      initial={{ opacity: 0, scale: 0.95, y: 40 }}
      whileInView={{ opacity: 1, scale: 1, y: 0 }}
      viewport={{ once: true, amount: 0.1 }}
      transition={{ duration: 1.2, ease: 'easeOut' }}
    >
      <div className="relative overflow-hidden rounded-[3rem] border border-primary/30 bg-gradient-to-br from-primary/10 via-background to-amber-900/10 p-16 md:p-24 text-center shadow-[0_0_50px_rgba(212,169,79,0.15)] backdrop-blur-2xl">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 blur-[100px] rounded-full" />
        </div>

        <div className="relative z-10">
          <h2 className="text-4xl md:text-6xl font-black text-foreground mb-8 leading-tight drop-shadow-lg">
              Elevate Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-amber-500">Portfolio</span> Today
          </h2>
          <p className="text-muted-foreground text-lg md:text-2xl font-medium max-w-2xl mx-auto mb-12">
              Join professionals who understand markets before they make decisions. Start with FinSight today.
          </p>
          <div className="flex flex-col sm:flex-row gap-6 justify-center">
            <Link href="/try-finsight">
              <Button className="text-lg py-8 px-14 rounded-full bg-primary text-white shadow-2xl shadow-primary/40 hover:shadow-primary/60 hover:scale-105 active:scale-95 transition-all duration-300 font-bold group">
                  Start for Free <IoArrowForwardOutline className="ml-3 group-hover:translate-x-2 transition-transform" />
              </Button>
            </Link>
            <Link href="/pricing">
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

/* ─── Main ────────────────────────────────────────────── */
const LandingPage: React.FC = () => {
  const landingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      // 1. Hero timeline reveal animation
      const tl = gsap.timeline({ defaults: { ease: 'power4.out', duration: 1.2 } });

      tl.from('.hero-title', { opacity: 0, y: 60, rotationX: -15, transformOrigin: 'top center', duration: 1.5 })
        .from('.hero-subtitle', { opacity: 0, y: 30, duration: 1.2 }, '-=1.0')
        .from('.hero-buttons', { opacity: 0, scale: 0.9, duration: 0.8 }, '-=0.9')
        .from('.hero-social-stat', { opacity: 0, y: 40, stagger: 0.15, duration: 1 }, '-=0.7');

      // Who-it's-for and CTA scroll reveals moved to framer-motion's whileInView
      // (see WhoItsForSection / CTASection below) — a raw IntersectionObserver
      // here left an orphaned observer under React Strict Mode's dev
      // double-invoke, which made those sections stick at opacity:0.
    }, landingRef);

    return () => ctx.revert();
  }, []);

  return (
    <main ref={landingRef} className="relative bg-background overflow-x-hidden">
      <HeroSection />
      <FeatureStrip />
      <WhoItsForSection />
      <CTASection />
    </main>
  );
};

export default LandingPage;
