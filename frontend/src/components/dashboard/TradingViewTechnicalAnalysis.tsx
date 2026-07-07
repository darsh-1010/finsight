import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';
import { Activity } from 'lucide-react';

const TradingViewTechnicalAnalysis: React.FC = () => {
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!container.current) return;

    container.current.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      "interval": "1D",
      "width": "100%",
      "isTransparent": false,
      "height": "100%",
      "symbol": "BINANCE:BTCUSDT",
      "showIntervalTabs": true,
      "locale": "en",
      "colorTheme": theme
    });
    container.current.appendChild(script);
  }, [theme]);

  return (
    <div className="bg-card border border-border rounded-2xl p-6 neon-card h-[500px] flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-primary" />
        <h3 className="text-lg font-bold">Technical Analysis</h3>
      </div>
      <div id="tv-ta-gauge-container" ref={container} className="flex-1 w-full" />
    </div>
  );
};

export default TradingViewTechnicalAnalysis;
