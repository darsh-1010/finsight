import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import { PiSunDim, PiMoon, PiList } from 'react-icons/pi';

import { useTheme } from '../../context/ThemeContext';

import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';

const navLinkClasses = (isActive: boolean) => `relative text-sm font-medium transition-all duration-300 hover:text-primary py-1 ${
  isActive
    ? 'text-primary after:content-[""] after:absolute after:-bottom-1 after:left-1/2 after:-translate-x-1/2 after:w-1.5 after:h-1.5 after:bg-primary after:rounded-full after:shadow-[0_0_8px_var(--color-primary)]'
    : 'text-muted-foreground'
}`;

const mobileNavLinkClasses = (isActive: boolean) => `text-lg font-medium transition-all duration-200 hover:text-primary ${
  isActive ? 'text-primary' : 'text-muted-foreground'
}`;

/* -------------------- Constants -------------------- */

const navLinks = [
  { to: '/', label: 'Home' },
  { to: '/about-us', label: 'About' },
  { to: '/product', label: 'Product' },
  { to: '/pricing', label: 'Pricing' },
];

/* -------------------- Sub Components -------------------- */

const Logo: React.FC = () => (
  <Link href="/" className="hover:opacity-90 transition-opacity flex items-center gap-2">
    <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white font-bold text-lg shadow-sm">F</span>
    <h3 className="text-2.5xl md:text-3xl font-logo tracking-wider bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent font-extrabold">
      FinSight
    </h3>
  </Link>
);

const DesktopNav: React.FC = () => {
  const pathname = usePathname();

  return (
    <div className="hidden lg:flex gap-8">
      {navLinks.map((link) => (
        <Link key={link.to} href={link.to} className={navLinkClasses(pathname === link.to)}>
          {link.label}
        </Link>
      ))}
    </div>
  );
};

interface ThemeToggleProps {
  theme: string;
  toggleTheme: () => void;
}

const ThemeToggle: React.FC<ThemeToggleProps> = ({ theme, toggleTheme }) => (
  <button
    onClick={toggleTheme}
    className="p-2 rounded-full hover:bg-secondary/50 transition-colors"
    aria-label="Toggle Theme"
  >
    {theme === 'dark' ? <PiSunDim size={20} /> : <PiMoon size={20} />}
  </button>
);

const DesktopCTA: React.FC = () => (
  <Link
    href="/login"
    className="hidden sm:block px-6 py-2.5 bg-primary text-primary-foreground rounded-full font-semibold hover:bg-primary/95 shadow-xl shadow-primary/20 hover:shadow-primary/30 hover:-translate-y-0.5 active:scale-95 transition-all duration-300"
  >
    Get Started
  </Link>
);

const MobileMenu: React.FC = () => {
  const [open, setOpen] = React.useState(false);
  const pathname = usePathname();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          className="lg:hidden p-2 rounded-lg hover:bg-secondary/50 transition-colors"
          aria-label="Toggle Menu"
        >
          <PiList size={24} />
        </button>
      </SheetTrigger>

      <SheetContent
        side="right"
        className="bg-background/95 backdrop-blur-md border-l dark:border-gray-800"
      >
        <nav className="flex flex-col items-center gap-8 pt-12">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              href={link.to}
              className={mobileNavLinkClasses(pathname === link.to)}
              onClick={() => setOpen(false)}
            >
              {link.label}
            </Link>
          ))}

          <Link
            href="/login"
            className="sm:hidden px-8 py-3 bg-primary text-primary-foreground rounded-lg font-semibold hover:bg-primary/90 transition-colors shadow-lg mt-4"
            onClick={() => setOpen(false)}
          >
            Get Started
          </Link>
        </nav>
      </SheetContent>
    </Sheet>
  );
};

/* -------------------- Main Component -------------------- */

const Navbar: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="py-4 px-6 md:px-16 lg:px-24 flex justify-between items-center fixed w-full top-0 bg-background/70 backdrop-blur-md z-50 border-b border-border/30 transition-all duration-300">
      <Logo />
      <DesktopNav />

      <div className="flex items-center gap-2 md:gap-4">
        <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
        <DesktopCTA />
        <MobileMenu />
      </div>
    </header>
  );
};

export default Navbar;
