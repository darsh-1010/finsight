import React from 'react';
import { PiUserLight } from 'react-icons/pi';

import { useTheme } from '@/context/ThemeContext';

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
  const { theme } = useTheme();

  return (
    <div className="mt-16 rounded-3xl max-w-7xl relative">
      <div
        className="mt-16 rounded-3xl overflow-hidden max-w-7xl
    relative
    shadow-[0_0_35px_rgba(13,92,70,0.25),0_0_55px_rgba(197,160,89,0.12)] z-2 border border-border/45"
      >
        <img
          src={`${theme === 'dark' ? '/assets/images/dashbaord-dark.png' : '/assets/images/dashbaord-light.png'}`}
          className="object-contain w-full"
          alt="FinSight Dashboard Showcase"
          loading="lazy"
        />
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
