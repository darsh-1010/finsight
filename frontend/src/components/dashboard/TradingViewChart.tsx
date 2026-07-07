import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';

interface TradingViewChartProps {
  symbol?: string;
  autosize?: boolean;
}

const TradingViewChart: React.FC<TradingViewChartProps> = ({ 
  symbol = 'BINANCE:BTCUSDT', 
  autosize = true 
}) => {
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();
  const widgetRef = useRef<any>(null);

  useEffect(() => {
    if (!container.current) return;

    // Clear existing widget content before re-initializing
    container.current.innerHTML = '';

    const scriptId = 'tradingview-widget-script';
    let script = document.getElementById(scriptId) as HTMLScriptElement;

    const initWidget = () => {
      if (typeof (window as any).TradingView !== 'undefined' && container.current) {
        widgetRef.current = new (window as any).TradingView.widget({
          autosize: autosize,
          symbol: symbol,
          interval: 'D',
          timezone: 'Etc/UTC',
          theme: theme,
          style: '1',
          locale: 'en',
          toolbar_bg: theme === 'dark' ? '#131722' : '#f1f3f6',
          enable_publishing: false,
          hide_top_toolbar: false,
          allow_symbol_change: true,
          container_id: container.current.id,
        });
      }
    };

    if (!script) {
      script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://s3.tradingview.com/tv.js';
      script.async = true;
      script.onload = initWidget;
      document.head.appendChild(script);
    } else {
      initWidget();
    }

    return () => {
      // No specific cleanup needed for the global script, 
      // but we ensure the container is cleared if the component unmounts.
    };
  }, [symbol, theme, autosize]);

  return (
    <div className="w-full h-[500px] bg-card border border-border rounded-2xl overflow-hidden neon-card">
      <div 
        id={`tradingview_${Math.random().toString(36).substring(7)}`} 
        ref={container} 
        className="w-full h-full" 
      />
    </div>
  );
};

export default TradingViewChart;
