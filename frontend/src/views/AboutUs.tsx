import { gsap } from 'gsap';
import Link from 'next/link';
import React, { useEffect, useRef } from 'react';
import {
  PiUsersThreeLight,
  PiMagnifyingGlassLight,
  PiBuildingsLight,
  PiUsersFourLight,
  PiHandshakeLight,
  PiTrendUpLight,
  PiQuestionLight,
  PiCheckCircleFill,
  PiBookOpenLight,
  PiTargetLight,
  PiGlobeLight,
  PiStackLight,
  PiSparkleFill,
  PiBrainLight,
  PiGraduationCapLight,
  PiLightningLight,
  PiArrowUpRightBold,
} from 'react-icons/pi';
import * as THREE from 'three';

/* â”€â”€â”€ Three.js Rotating Geometric Background â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const ThreeBackground: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, width / height, 1, 2000);

    camera.position.z = 500;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });

    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    container.appendChild(renderer.domElement);

    // Floating wireframe icosahedron â€” "interconnected intelligence" motif
    const icoGeo = new THREE.IcosahedronGeometry(140, 1);
    const icoMat = new THREE.MeshBasicMaterial({
      color: 0x7b61ff,
      wireframe: true,
      transparent: true,
      opacity: 0.12,
    });
    const icosahedron = new THREE.Mesh(icoGeo, icoMat);

    icosahedron.position.set(220, -60, 0);
    scene.add(icosahedron);

    // Secondary smaller sphere
    const sphereGeo = new THREE.IcosahedronGeometry(70, 1);
    const sphereMat = new THREE.MeshBasicMaterial({
      color: 0xa78bfa,
      wireframe: true,
      transparent: true,
      opacity: 0.10,
    });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);

    sphere.position.set(-200, 80, -100);
    scene.add(sphere);

    // Floating particles
    const particleCount = 60;
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * width;
      positions[i * 3 + 1] = (Math.random() - 0.5) * height;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 300;
    }
    const pGeo = new THREE.BufferGeometry();

    pGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const pMat = new THREE.PointsMaterial({
      color: 0x7b61ff,
      size: 2.5,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(pGeo, pMat);

    scene.add(particles);

    let mouseX = 0;
    let mouseY = 0;
    const handleMouseMove = (e: MouseEvent) => {
      mouseX = (e.clientX / window.innerWidth - 0.5) * 0.4;
      mouseY = (e.clientY / window.innerHeight - 0.5) * 0.4;
    };

    window.addEventListener('mousemove', handleMouseMove);

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      icosahedron.rotation.x += 0.003;
      icosahedron.rotation.y += 0.005;
      sphere.rotation.x -= 0.004;
      sphere.rotation.z += 0.003;
      particles.rotation.y += 0.0008;
      camera.position.x += (mouseX * 80 - camera.position.x) * 0.04;
      camera.position.y += (-mouseY * 80 - camera.position.y) * 0.04;
      camera.lookAt(scene.position);
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
      cancelAnimationFrame(animId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return <div ref={containerRef} className="fixed inset-0 z-0 pointer-events-none opacity-70" />;
};

/* â”€â”€â”€ GSAP Scroll Reveal Hook â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const useScrollReveal = () => {
  useEffect(() => {
    const elements = document.querySelectorAll<HTMLElement>('.reveal');
    const observers: IntersectionObserver[] = [];

    elements.forEach((el) => {
      gsap.set(el, { opacity: 0, y: 40 });
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            const delay = parseFloat(el.dataset.delay ?? '0');

            gsap.to(el, { opacity: 1, y: 0, duration: 0.7, ease: 'power3.out', delay });
            observer.unobserve(el);
          }
        },
        { threshold: 0.1 },
      );

      observer.observe(el);
      observers.push(observer);
    });

    return () => observers.forEach((obs) => obs.disconnect());
  }, []);
};

/* â”€â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const AboutUsHeader = () => (
  <div className="reveal flex flex-col items-center w-full max-w-3xl mb-20 text-center" data-delay="0">
    <div className="w-16 h-16 rounded-full border border-border flex justify-center items-center relative mb-8">
      <div className="absolute w-12 h-12 animate-spin">
        <div
          className="absolute inset-0 rounded-full
                       border-2 border-transparent
                       border-t-primary border-b-primary"
        ></div>
      </div>
      <PiUsersThreeLight size={25} className="text-primary" />
    </div>
    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-primary/10 border border-primary/20 text-xs font-semibold uppercase tracking-wider text-primary mb-6">
      Our Story
    </span>
    <h1 className="text-4xl sm:text-6xl font-bold tracking-tight text-foreground leading-[1.1] mb-6">
      Intelligence for{' '}
      <span className="font-serif italic bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
        smarter investors
      </span>
    </h1>
    <p className="text-muted-foreground text-base md:text-xl max-w-2xl leading-relaxed">
      FinSight was created to bring clarity, structure, and professional thinking to investing â€” before action is taken. We believe great decisions start with better understanding.
    </p>
  </div>
);

/* â”€â”€â”€ Target Audience â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const TargetAudience = () => (
  <div className="reveal w-full max-w-5xl mb-24 overflow-hidden" data-delay="0.1">
    <p className="text-center text-muted-foreground text-xs uppercase tracking-widest font-semibold mb-8">
      Who We Built This For
    </p>
    <div className="flex flex-wrap justify-center gap-3">
      {[
        { label: 'Professionals', icon: <PiMagnifyingGlassLight /> },
        { label: 'Founders', icon: <PiBuildingsLight /> },
        { label: 'Executives', icon: <PiUsersFourLight /> },
        { label: 'Business Owners', icon: <PiHandshakeLight /> },
        { label: 'Long-term Investors', icon: <PiTrendUpLight /> },
      ].map((item, idx) => (
        <div
          key={idx}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full border border-border bg-card shadow-xs hover:border-primary/30 hover:shadow-md transition-all cursor-default text-foreground/80 hover:text-foreground hover:scale-[1.03] transform duration-200 group"
        >
          <span className="text-primary group-hover:scale-110 transition-transform duration-200">{item.icon}</span>
          <span className="text-sm font-semibold">{item.label}</span>
        </div>
      ))}
    </div>
  </div>
);

/* â”€â”€â”€ Mission Values â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const missionValues = [
  {
    icon: <PiBrainLight size={24} />,
    title: 'Intelligence Over Noise',
    description: 'We cut through the daily flood of market chatter to surface what actually matters â€” structured, contextual insights that lead to better thinking.',
  },
  {
    icon: <PiGraduationCapLight size={24} />,
    title: 'Education First',
    description: 'We believe investing mastery starts with understanding, not tips. FinSight builds conceptual knowledge before building confidence in action.',
  },
  {
    icon: <PiLightningLight size={24} />,
    title: 'Speed Without Sacrifice',
    description: 'Our AI-powered research engine delivers institutional-level analysis in seconds, without sacrificing depth or context.',
  },
  {
    icon: <PiGlobeLight size={24} />,
    title: 'Universal Accessibility',
    description: "Professional-grade intelligence shouldn't be locked behind hedge fund walls. We democratize sophisticated financial thinking.",
  },
];

const MissionSection = () => (
  <div className="w-full max-w-5xl mb-24">
    <div className="reveal text-center max-w-3xl mx-auto mb-12" data-delay="0">
      <span className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-primary/10 border border-primary/20 text-xs font-semibold uppercase tracking-wider text-primary mb-4">
        <PiSparkleFill /> Our Mission
      </span>
      <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground mb-4">
        What drives everything we build
      </h2>
      <p className="text-muted-foreground text-base leading-relaxed">
        Four core beliefs that guide every feature, every insight, and every decision at FinSight.
      </p>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      {missionValues.map((value, i) => (
        <div
          key={i}
          className="reveal flex items-start gap-5 p-6 rounded-3xl border border-border/60 bg-card hover:border-primary/30 hover:shadow-lg transition-all duration-300 group hover:-translate-y-0.5 transform"
          data-delay={`${i * 0.1}`}
        >
          <div className="p-3 rounded-2xl bg-secondary text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-all duration-300 shrink-0">
            {value.icon}
          </div>
          <div>
            <h3 className="text-base font-bold text-foreground mb-1.5">{value.title}</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">{value.description}</p>
          </div>
        </div>
      ))}
    </div>
  </div>
);

/* â”€â”€â”€ Why FinSight â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const ChecksComponent = () => (
  <div className="flex flex-col gap-4">
    {[
      'Noise is everywhere.',
      'Opinions are cheap.',
      'Confidence is often misplaced.',
    ].map((text, idx) => (
      <div
        key={idx}
        className="flex items-center gap-3 px-5 py-3 rounded-full border border-accent/20 bg-accent/5 w-fit shadow-xs"
      >
        <PiCheckCircleFill className="text-primary shrink-0" size={18} />
        <span className="text-base md:text-lg font-semibold text-foreground/90">{text}</span>
      </div>
    ))}
  </div>
);

const FeatureComponent = () => (
  <div className="flex flex-col gap-4">
    {[
      { title: 'Risk before return', icon: <PiBookOpenLight size={24} /> },
      { title: 'Regimes and cycles', icon: <PiTargetLight size={24} /> },
      { title: 'Probabilities, not predictions', icon: <PiGlobeLight size={24} /> },
      { title: 'Portfolios, not single bets', icon: <PiStackLight size={24} /> },
    ].map((item, idx) => (
      <div
        key={idx}
        className="flex items-center gap-6 p-6 rounded-3xl border border-border/80 bg-card hover:border-primary/30 hover:shadow-lg transition-all duration-300 group hover:-translate-y-0.5 transform"
      >
        <div className="p-3.5 rounded-2xl bg-secondary text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-all duration-300">
          {item.icon}
        </div>
        <h3 className="text-lg md:text-xl font-bold text-foreground">{item.title}</h3>
      </div>
    ))}

    <p className="text-muted-foreground text-sm italic mt-6 border-t border-border/40 pt-6 leading-relaxed">
      FinSight was built to bridge this gap â€” not by replacing human judgement, but by helping people think better before they act.
    </p>
  </div>
);

const WhyFinSightExists = () => (
  <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 gap-16 items-start mb-24">
    <div className="reveal flex flex-col gap-8" data-delay="0">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-primary/10 border border-primary/20 w-fit">
        <PiQuestionLight className="text-primary" />
        <span className="text-xs font-semibold uppercase tracking-wider text-primary">
          Our Philosophy
        </span>
      </div>
      <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground leading-[1.1]">
        Why FinSight exists
      </h2>

      <ChecksComponent />

      <p className="text-muted-foreground text-base md:text-lg leading-relaxed">
        Most investment platforms focus on what to buy, what&apos;s trending, or what worked yesterday. Professionals focus on something very different:
      </p>
    </div>

    <div className="reveal" data-delay="0.15">
      <FeatureComponent />
    </div>
  </div>
);

/* â”€â”€â”€ CTA Banner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const AboutCTA = () => (
  <div className="reveal w-full max-w-5xl" data-delay="0.05">
    <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-br from-primary/8 via-primary/3 to-accent/5 p-10 md:p-12 text-center">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[400px] h-[200px] bg-primary/10 blur-[80px] rounded-full" />
      </div>
      <div className="relative z-10">
        <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-4">
          Ready to think like a professional?
        </h2>
        <p className="text-muted-foreground text-sm md:text-base max-w-xl mx-auto mb-8 leading-relaxed">
          Join investors who understand markets deeply before making decisions. Start your intelligence journey today.
        </p>
        <Link
          href="/try-finsight"
          className="inline-flex items-center gap-2 px-8 py-3.5 bg-primary text-primary-foreground rounded-full font-semibold hover:opacity-95 shadow-lg shadow-primary/20 hover:-translate-y-0.5 transform duration-200 transition-all"
        >
          Try FinSight Free <PiArrowUpRightBold size={16} />
        </Link>
      </div>
    </div>
  </div>
);

/* â”€â”€â”€ Main About Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
const AboutUs: React.FC = () => {
  useScrollReveal();

  return (
    <div className="relative flex items-center flex-col pt-24 pb-24 min-h-[calc(100vh-80px)] px-6 md:px-16 lg:px-24">
      <ThreeBackground />
      <AboutUsHeader />
      <TargetAudience />
      <MissionSection />
      <WhyFinSightExists />
      <AboutCTA />
    </div>
  );
};

export default AboutUs;

