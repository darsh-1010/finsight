import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';
import { Calendar } from 'lucide-react';

const TradingViewCalendar: React.FC = () => {
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!container.current) return;

    container.current.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-events.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      "colorTheme": theme,
      "isTransparent": false,
      "width": "100%",
      "height": "100%",
      "locale": "en",
      "importanceFilter": "-1,0,1",
      "countryFilter": "us,eu,it,fr,es,de,gb,jp,ch,ca,au,nz"
    });
    container.current.appendChild(script);
  }, [theme]);

  return (
    <div className="bg-card border border-border rounded-2xl p-6 neon-card h-[500px] flex flex-col">
      <div className="flex items-center gap-2 mb-4 shrink-0">
        <Calendar className="w-5 h-5 text-primary" />
        <h3 className="text-lg font-bold">Economic Calendar</h3>
      </div>
      <div id="tv-calendar-container" ref={container} className="flex-1 w-full overflow-hidden" />
    </div>
  );
};

export default TradingViewCalendar;
