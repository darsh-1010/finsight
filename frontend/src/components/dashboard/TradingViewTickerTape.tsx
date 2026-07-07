import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';

const TradingViewTickerTape: React.FC = () => {
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!container.current) return;

    container.current.innerHTML = '';
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      "symbols": [
        {
          "proName": "FOREXCOM:SPX500",
          "title": "S&P 500"
        },
        {
          "proName": "FOREXCOM:NSXUSD",
          "title": "US Tech 100"
        },
        {
          "proName": "FX_IDC:EURUSD",
          "title": "EUR/USD"
        },
        {
          "proName": "BITSTAMP:BTCUSD",
          "title": "Bitcoin"
        },
        {
          "proName": "BITSTAMP:ETHUSD",
          "title": "Ethereum"
        }
      ],
      "showSymbolLogo": true,
      "colorTheme": theme,
      "isTransparent": false,
      "displayMode": "adaptive",
      "locale": "en"
    });
    container.current.appendChild(script);
  }, [theme]);

  return (
    <div className="w-full bg-card border-b border-border py-1">
      <div id="tv-ticker-tape-container" ref={container} />
    </div>
  );
};

export default TradingViewTickerTape;
