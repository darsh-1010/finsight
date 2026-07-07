import React from 'react';
import { Outlet, Link } from 'react-router-dom';

const AnimatedBackground = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
    <div className="absolute -top-[25%] -left-[10%] w-[50%] h-[50%] rounded-full bg-primary/20 blur-[120px] animate-pulse mix-blend-screen" style={{ animationDuration: '8s' }}></div>
    <div className="absolute top-[40%] -right-[10%] w-[50%] h-[60%] rounded-full bg-blue-600/20 blur-[120px] animate-pulse mix-blend-screen" style={{ animationDuration: '12s' }}></div>
    <div className="absolute -bottom-[20%] left-[20%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px] animate-pulse mix-blend-screen" style={{ animationDuration: '10s' }}></div>
  </div>
);

const MinimalLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-background text-foreground relative overflow-hidden">
      <AnimatedBackground />
      
      <div className="absolute top-10 w-full flex justify-center z-20">
        <Link to="#" className="hover:opacity-80 transition-opacity">
          <h1 className="text-4xl md:text-5xl font-logo tracking-tight">FinSight</h1>
        </Link>
      </div>
      <div className="w-full z-10 flex justify-center items-center flex-1 pt-16">
        <Outlet />
      </div>
    </div>
  );
};

export default MinimalLayout;
