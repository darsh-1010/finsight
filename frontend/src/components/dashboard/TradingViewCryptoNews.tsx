import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';
import { Zap } from 'lucide-react';

const TradingViewCryptoNews: React.FC = () => {
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!container.current) return;

    container.current.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-timeline.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      "feedMode": "market",
      "market": "crypto",
      "colorTheme": theme,
      "isTransparent": false,
      "displayMode": "regular",
      "width": "100%",
      "height": "100%",
      "locale": "en"
    });
    container.current.appendChild(script);
  }, [theme]);

  return (
    <div className="bg-card border border-border rounded-2xl p-6 neon-card h-[500px] flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-5 h-5 text-primary" />
        <h3 className="text-lg font-bold">Crypto News</h3>
      </div>
      <div id="tv-crypto-news-container" ref={container} className="flex-1 w-full" />
    </div>
  );
};

export default TradingViewCryptoNews;
