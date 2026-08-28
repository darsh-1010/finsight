import { useRouter } from 'next/navigation';

import { Button } from '../ui/button';

const Footer = () => {
  const navigate = useRouter().push;

  return (
    <footer className="bg-gradient-to-b from-background to-secondary/20 border-t border-border/40 transition-colors duration-300">
      <div className="max-w-6xl mx-auto px-6 py-12 md:py-16 flex flex-col md:flex-row items-center justify-between gap-8">
        <div className="text-center md:text-left max-w-lg">
          <h2 className="text-2xl md:text-3.5xl font-bold text-foreground tracking-tight mb-2">
            Ready to Transform Your Investments?
          </h2>
          <p className="text-muted-foreground text-sm md:text-base">
            Start free today and upgrade as you grow. No credit card required to begin.
          </p>
        </div>
        <Button
          size="lg"
          className="whitespace-nowrap px-8 py-5 rounded-full font-semibold text-base bg-primary text-primary-foreground hover:opacity-95 hover:scale-[1.02] transform transition-all shadow-lg hover:shadow-primary/10 border-none cursor-pointer"
          onClick={() => {
            navigate('/signup');
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
        >
          Get Started Now
        </Button>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8 border-t border-border/20 flex flex-col-reverse md:flex-row items-center justify-between gap-4">
        <p className="text-muted-foreground/80 text-xs">
          © {new Date().getFullYear()} FinSight AI Engine. All rights reserved.
        </p>
        <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-xs font-semibold text-muted-foreground">
          <a href="/about-us" className="hover:text-primary transition-colors">About</a>
          <a href="/product" className="hover:text-primary transition-colors">Product</a>
          <a href="/pricing" className="hover:text-primary transition-colors">Pricing</a>
          <a href="#" className="hover:text-primary transition-colors">Privacy</a>
          <a href="#" className="hover:text-primary transition-colors">Terms</a>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
