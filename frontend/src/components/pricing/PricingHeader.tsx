import React from 'react';
import { PiMoneyWavyLight } from 'react-icons/pi';

const PricingHeader: React.FC = () => (
  <div className="flex flex-col items-center w-full max-w-2xl">
    <div className="w-16 h-16 rounded-full border border-border flex justify-center items-center relative">
      <div className="absolute w-12 h-12 animate-spin">
        <div
          className="absolute inset-0 rounded-full
             border-2 border-transparent
             border-t-primary border-b-primary"
        ></div>
      </div>
      <PiMoneyWavyLight size={25} className="text-primary" />
    </div>
    <h1 className="text-center text-4xl sm:text-5xl my-8 font-bold tracking-tight text-foreground leading-[1.1]">
      Pricing that grows with your{' '}
      <span className="font-serif italic bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">understanding</span>
    </h1>
    <p className="text-center text-muted-foreground text-base md:text-lg leading-relaxed max-w-xl">
      FinSight offers tiered access to education-first investment intelligence —
      from foundations to advanced, professional-level market understanding.{' '}
      FinSight provides education and intelligence, not personalized financial advice.
    </p>
  </div>
);

export default PricingHeader;
