import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';
import { Map } from 'lucide-react';

const TradingViewHeatmap: React.FC = () => {
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!container.current) return;

    container.current.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      "exchanges": [],
      "dataSource": "SPX500",
      "grouping": "sector",
      "blockSize": "market_cap_basic",
      "blockColor": "change",
      "locale": "en",
      "symbolUrl": "",
      "colorTheme": theme,
      "hasTopBar": false,
      "isDataSetEnabled": false,
      "isZoomEnabled": true,
      "hasSymbolTooltip": true,
      "isMonoSize": false,
      "width": "100%",
      "height": "100%"
    });
    container.current.appendChild(script);
  }, [theme]);

  return (
    <div className="glass-panel border border-border/50 rounded-3xl p-6 shadow-xl shadow-black/5 dark:shadow-black/20 h-[500px] flex flex-col">
      <div className="flex items-center gap-2 mb-4 shrink-0">
        <Map className="w-5 h-5 text-primary" />
        <h3 className="text-lg font-bold">S&P 500 Heatmap</h3>
      </div>
      <div ref={container} className="flex-1 w-full overflow-hidden rounded-xl" />
    </div>
  );
};

export default TradingViewHeatmap;
