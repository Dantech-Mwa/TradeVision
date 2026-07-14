# auto-blog-generator.py
import requests
import json
import os
import time
import base64
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import pandas as pd

# ============================================
# CONFIGURATION
# ============================================

# Use Binance US API (working endpoint)
BINANCE_API = 'https://api.binance.us/api/v3'

# 10 Popular Assets (expanded list)
TOP_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'ADAUSDT', 'DOGEUSDT', 'DOTUSDT', 'LINKUSDT', 'AVAXUSDT'
]

OUTPUT_DIR = 'pillar-guides/technical-analysis/daily-analysis'

# ============================================
# 1. FETCH MARKET DATA
# ============================================

def fetch_24hr_stats(symbol):
    """Get 24-hour price change statistics from Binance US"""
    url = f"{BINANCE_API}/ticker/24hr?symbol={symbol}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Check if we got valid data
        if isinstance(data, dict) and 'lastPrice' in data:
            return data
        else:
            print(f"⚠️ Unexpected data format for {symbol}")
            return generate_mock_stats(symbol)
            
    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")
        return generate_mock_stats(symbol)

def generate_mock_stats(symbol):
    """Generate mock stats as fallback"""
    base_price = {
        'BTCUSDT': 50000, 'ETHUSDT': 3000, 'BNBUSDT': 600,
        'SOLUSDT': 150, 'XRPUSDT': 0.60, 'ADAUSDT': 0.45,
        'DOGEUSDT': 0.15, 'DOTUSDT': 7.50, 'LINKUSDT': 15.00,
        'AVAXUSDT': 35.00
    }
    price = base_price.get(symbol, 100)
    return {
        'lastPrice': str(price),
        'priceChange': str(price * 0.02),
        'priceChangePercent': '2.0',
        'highPrice': str(price * 1.05),
        'lowPrice': str(price * 0.95),
        'volume': '1000000'
    }

def fetch_klines(symbol, interval='1d', limit=30):
    """Get OHLCV data for chart"""
    url = f"{BINANCE_API}/klines?symbol={symbol}&interval={interval}&limit={limit}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            return [{
                'time': c[0],
                'open': float(c[1]),
                'high': float(c[2]),
                'low': float(c[3]),
                'close': float(c[4]),
                'volume': float(c[5])
            } for c in data]
        else:
            print(f"⚠️ Invalid kline data for {symbol}")
            return generate_mock_klines(symbol, limit)
            
    except Exception as e:
        print(f"⚠️ Kline fetch error for {symbol}: {e}")
        return generate_mock_klines(symbol, limit)

def generate_mock_klines(symbol, limit):
    """Generate mock kline data as fallback"""
    base_price = {
        'BTCUSDT': 50000, 'ETHUSDT': 3000, 'BNBUSDT': 600,
        'SOLUSDT': 150, 'XRPUSDT': 0.60, 'ADAUSDT': 0.45,
        'DOGEUSDT': 0.15, 'DOTUSDT': 7.50, 'LINKUSDT': 15.00,
        'AVAXUSDT': 35.00
    }
    price = base_price.get(symbol, 100)
    now = int(datetime.now().timestamp() * 1000)
    mock_data = []
    for i in range(limit):
        p = price * (1 + 0.005 * i + 0.01 * (i % 5 - 2))
        mock_data.append({
            'time': now - (limit - i) * 86400000,
            'open': p * 0.99,
            'high': p * 1.01,
            'low': p * 0.98,
            'close': p,
            'volume': 1000000 + i * 1000
        })
    return mock_data

# ============================================
# 2. CHART GENERATION
# ============================================

def generate_chart(symbol, klines, output_path):
    """Generate a simple price chart with matplotlib"""
    try:
        # Prepare data
        dates = [datetime.fromtimestamp(k['time'] / 1000) for k in klines]
        closes = [k['close'] for k in klines]
        highs = [k['high'] for k in klines]
        lows = [k['low'] for k in klines]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
        
        # Plot price line
        ax.plot(dates, closes, color='#58a6ff', linewidth=2, label='Close')
        ax.fill_between(dates, highs, lows, alpha=0.1, color='#58a6ff')
        
        # Style
        ax.set_facecolor('#0d1117')
        fig.patch.set_facecolor('#0d1117')
        ax.tick_params(colors='#8b949e')
        ax.spines['bottom'].set_color('#30363d')
        ax.spines['top'].set_color('#30363d')
        ax.spines['left'].set_color('#30363d')
        ax.spines['right'].set_color('#30363d')
        ax.set_title(f'{symbol} Price Chart', color='#e6edf3', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', color='#8b949e')
        ax.set_ylabel('Price (USDT)', color='#8b949e')
        ax.grid(True, alpha=0.1, color='#30363d')
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Save to buffer
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=100, facecolor='#0d1117')
        buf.seek(0)
        
        # Convert to base64 for embedding
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        
        return img_base64
        
    except Exception as e:
        print(f"⚠️ Chart generation error for {symbol}: {e}")
        return None

# ============================================
# 3. CALCULATE INDICATORS
# ============================================

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(closes, period):
    if len(closes) < period:
        return closes[-1]
    multiplier = 2 / (period + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = (price * multiplier) + (ema * (1 - multiplier))
    return ema

def detect_trend(klines):
    closes = [k['close'] for k in klines]
    ema_20 = calculate_ema(closes, 20)
    ema_50 = calculate_ema(closes, 50)
    last_price = closes[-1]
    
    if last_price > ema_20 > ema_50:
        return 'bullish', 'Strong uptrend'
    elif last_price < ema_20 < ema_50:
        return 'bearish', 'Strong downtrend'
    elif last_price > ema_20:
        return 'bullish', 'Mild uptrend'
    elif last_price < ema_20:
        return 'bearish', 'Mild downtrend'
    else:
        return 'neutral', 'Consolidating'

def find_support_resistance(klines):
    highs = [k['high'] for k in klines[-30:]]
    lows = [k['low'] for k in klines[-30:]]
    current = klines[-1]['close']
    resistance = min([h for h in highs if h > current], default=max(highs))
    support = max([l for l in lows if l < current], default=min(lows))
    return {
        'resistance': round(resistance, 2),
        'support': round(support, 2),
        'high': round(max(highs), 2),
        'low': round(min(lows), 2)
    }

# ============================================
# 4. GENERATE ANALYSIS
# ============================================

def generate_analysis(symbol, stats, klines):
    try:
        current_price = float(stats.get('lastPrice', 0))
        price_change = float(stats.get('priceChange', 0))
        price_change_pct = float(stats.get('priceChangePercent', 0))
        high_24h = float(stats.get('highPrice', 0))
        low_24h = float(stats.get('lowPrice', 0))
        volume = float(stats.get('volume', 0))
    except (ValueError, TypeError):
        current_price = 50000 if symbol == 'BTCUSDT' else 3000
        price_change = 100
        price_change_pct = 2.0
        high_24h = current_price * 1.05
        low_24h = current_price * 0.95
        volume = 1000000
    
    closes = [k['close'] for k in klines]
    rsi = calculate_rsi(closes)
    ema_20 = calculate_ema(closes, 20)
    ema_50 = calculate_ema(closes, 50)
    levels = find_support_resistance(klines)
    trend, trend_desc = detect_trend(klines)
    
    signal = 'HOLD'
    confidence = 0
    signal_reason = []
    
    if rsi < 30:
        signal = 'BUY'
        confidence += 40
        signal_reason.append(f'RSI oversold at {rsi:.1f}')
    elif rsi > 70:
        signal = 'SELL'
        confidence += 40
        signal_reason.append(f'RSI overbought at {rsi:.1f}')
    else:
        signal_reason.append(f'RSI neutral at {rsi:.1f}')
    
    if trend == 'bullish' and signal == 'BUY':
        confidence += 30
    elif trend == 'bullish' and signal == 'HOLD':
        signal = 'BUY'
        confidence += 20
    elif trend == 'bearish' and signal == 'SELL':
        confidence += 30
    elif trend == 'bearish' and signal == 'HOLD':
        signal = 'SELL'
        confidence += 20
    
    if price_change > 0 and signal == 'BUY':
        confidence += 10
    elif price_change < 0 and signal == 'SELL':
        confidence += 10
    
    return {
        'symbol': symbol,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M'),
        'price': current_price,
        'change': price_change,
        'change_pct': price_change_pct,
        'high_24h': high_24h,
        'low_24h': low_24h,
        'volume': volume,
        'rsi': round(rsi, 1),
        'ema_20': round(ema_20, 2),
        'ema_50': round(ema_50, 2),
        'trend': trend,
        'trend_desc': trend_desc,
        'resistance': levels['resistance'],
        'support': levels['support'],
        'signal': signal,
        'confidence': min(confidence, 100),
        'signal_reason': signal_reason,
        'summary': generate_summary(symbol, current_price, trend, signal, rsi, levels)
    }

def generate_summary(symbol, price, trend, signal, rsi, levels):
    base_name = symbol.replace('USDT', '')
    summary = f"{base_name} is currently trading at ${price:,.2f}. "
    if trend == 'bullish':
        summary += f"The trend is bullish, with price above key moving averages. "
    elif trend == 'bearish':
        summary += f"The trend is bearish, with price below key moving averages. "
    else:
        summary += f"The market is consolidating. "
    summary += f"Key resistance is at ${levels['resistance']:,.2f}, support at ${levels['support']:,.2f}. "
    summary += f"RSI is at {rsi:.1f} "
    if rsi < 30:
        summary += f"(oversold). "
    elif rsi > 70:
        summary += f"(overbought). "
    else:
        summary += f"(neutral). "
    if signal == 'BUY':
        summary += f"The indicators suggest a BUY opportunity with {min(100, 50 + (70 - rsi))}% confidence."
    elif signal == 'SELL':
        summary += f"The indicators suggest a SELL opportunity with {min(100, 50 + (rsi - 30))}% confidence."
    else:
        summary += f"Indicators are neutral. Wait for a clearer signal."
    return summary

# ============================================
# 5. GENERATE HTML WITH CHART
# ============================================

def generate_html(report, chart_base64):
    day = datetime.now().strftime('%d')
    month = datetime.now().strftime('%m')
    year = datetime.now().strftime('%Y')
    symbol_name = report['symbol'].replace('USDT', '')
    date_str = datetime.now().strftime('%B %d, %Y')
    
    tv_link = f"https://tradevisionpro.online?symbol={report['symbol']}"
    
    signal_class = 'buy' if report['signal'] == 'BUY' else 'sell' if report['signal'] == 'SELL' else 'hold'
    change_class = 'up' if report['change'] > 0 else 'down'
    
    # Build chart HTML
    if chart_base64:
        chart_img = f'<img src="data:image/png;base64,{chart_base64}" alt="{symbol_name} Price Chart" style="width:100%;border-radius:8px;" />'
    else:
        chart_img = '<div style="padding:20px;text-align:center;color:var(--text-muted);">📊 Chart unavailable</div>'
    
    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{symbol_name} Daily Analysis - {date_str} | TradeVision Pro</title>
  <meta name="description" content="{symbol_name} ({report['symbol']}) daily market analysis for {date_str}. Price ${report['price']:,.2f}, {report['trend']} trend, RSI {report['rsi']}." />
  <link rel="canonical" href="https://tradevisionpro.online/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/{day}-{symbol_name.lower()}-analysis.html" />
  <meta property="og:title" content="{symbol_name} Daily Analysis - {date_str}" />
  <meta property="og:description" content="Daily {symbol_name} market analysis. Price: ${report['price']:,.2f}, Signal: {report['signal']}." />
  <meta property="og:image" content="https://tradevisionpro.online/profile.png" />
  <meta property="og:url" content="https://tradevisionpro.online/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/{day}-{symbol_name.lower()}-analysis.html" />
  <meta property="og:type" content="article" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" />
  <style>
    /* ... (same styles as before) ... */
    :root {{
      --bg-primary: #0d1117;
      --bg-secondary: #161b22;
      --bg-tertiary: #1c2128;
      --text-primary: #e6edf3;
      --text-secondary: #c9d1d9;
      --text-muted: #8b949e;
      --accent-primary: #58a6ff;
      --up-color: #26a69a;
      --down-color: #ef5350;
      --border-primary: #30363d;
      --radius-xl: 16px;
      --radius-lg: 12px;
    }}
    [data-theme="light"] {{
      --bg-primary: #ffffff;
      --bg-secondary: #f6f8fa;
      --bg-tertiary: #f0f2f5;
      --text-primary: #1f2328;
      --text-secondary: #424a53;
      --text-muted: #656d76;
      --border-primary: #d0d7de;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: var(--bg-primary);
      color: var(--text-primary);
      line-height: 1.8;
      transition: background 0.3s, color 0.3s;
    }}
    .header {{
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border-primary);
      padding: 12px 24px;
      position: sticky;
      top: 0;
      z-index: 1000;
    }}
    .header-content {{
      max-width: 1000px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      color: var(--text-primary);
      font-weight: 800;
      font-size: 20px;
    }}
    .logo-pro {{
      background: rgba(88, 166, 255, 0.1);
      color: var(--accent-primary);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
    }}
    .back-link {{
      color: var(--text-muted);
      text-decoration: none;
      font-size: 14px;
      transition: color 0.2s;
    }}
    .back-link:hover {{ color: var(--accent-primary); }}
    .back-link i {{ margin-right: 6px; }}
    .container {{
      max-width: 900px;
      margin: 0 auto;
      padding: 32px 24px 60px;
    }}
    .article-header {{
      margin-bottom: 32px;
      border-bottom: 1px solid var(--border-primary);
      padding-bottom: 20px;
    }}
    .article-header .meta {{
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 8px;
    }}
    .article-header .meta span {{ margin-right: 16px; }}
    .article-header h1 {{
      font-size: 34px;
      font-weight: 800;
      line-height: 1.2;
      margin-bottom: 8px;
    }}
    .article-header .excerpt {{
      font-size: 18px;
      color: var(--text-secondary);
    }}
    .article-body {{
      font-size: 16px;
      color: var(--text-secondary);
    }}
    .article-body h2 {{
      font-size: 26px;
      font-weight: 700;
      color: var(--text-primary);
      margin-top: 40px;
      margin-bottom: 16px;
    }}
    .article-body h3 {{
      font-size: 20px;
      font-weight: 600;
      color: var(--text-primary);
      margin-top: 28px;
      margin-bottom: 12px;
    }}
    .article-body p {{ margin-bottom: 16px; }}
    .article-body ul, .article-body ol {{ padding-left: 24px; margin-bottom: 16px; }}
    .article-body li {{ margin-bottom: 6px; }}
    .article-body strong {{ color: var(--text-primary); font-weight: 700; }}
    
    .signal-badge {{
      display: inline-block;
      padding: 4px 16px;
      border-radius: 20px;
      font-weight: 700;
      font-size: 14px;
      margin-right: 8px;
    }}
    .signal-badge.buy {{ background: rgba(38, 166, 154, 0.15); color: var(--up-color); }}
    .signal-badge.sell {{ background: rgba(239, 83, 80, 0.15); color: var(--down-color); }}
    .signal-badge.hold {{ background: rgba(210, 153, 34, 0.15); color: #d29922; }}
    
    .chart-container {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-primary);
      border-radius: var(--radius-xl);
      overflow: hidden;
      margin: 24px 0;
    }}
    .chart-container .chart-header {{
      padding: 10px 16px;
      background: var(--bg-tertiary);
      border-bottom: 1px solid var(--border-primary);
      font-size: 12px;
      font-weight: 600;
      color: var(--text-secondary);
    }}
    .chart-container .chart-body {{
      padding: 16px;
      background: var(--bg-primary);
    }}
    
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 12px;
      margin: 20px 0;
    }}
    .metric-card {{
      background: var(--bg-tertiary);
      border-radius: var(--radius-lg);
      padding: 14px 16px;
      text-align: center;
    }}
    .metric-card .value {{
      font-size: 18px;
      font-weight: 700;
      color: var(--text-primary);
    }}
    .metric-card .label {{
      font-size: 10px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .metric-card .value.up {{ color: var(--up-color); }}
    .metric-card .value.down {{ color: var(--down-color); }}
    
    .table-wrapper {{
      overflow-x: auto;
      margin: 20px 0;
      border: 1px solid var(--border-primary);
      border-radius: var(--radius-lg);
    }}
    .table-wrapper table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    .table-wrapper th {{
      padding: 10px 16px;
      text-align: left;
      font-weight: 700;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      background: var(--bg-tertiary);
      border-bottom: 2px solid var(--border-primary);
    }}
    .table-wrapper td {{
      padding: 8px 16px;
      border-bottom: 1px solid var(--border-primary);
    }}
    .table-wrapper .up {{ color: var(--up-color); font-weight: 600; }}
    .table-wrapper .down {{ color: var(--down-color); font-weight: 600; }}
    
    .info-box {{
      background: var(--bg-tertiary);
      border-left: 4px solid var(--accent-primary);
      border-radius: var(--radius-lg);
      padding: 16px 20px;
      margin: 20px 0;
    }}
    .info-box.success {{ border-left-color: var(--up-color); }}
    .info-box.warning {{ border-left-color: #d29922; }}
    .info-box.danger {{ border-left-color: var(--down-color); }}
    
    .tags {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 16px 0;
    }}
    .tags span {{
      font-size: 11px;
      padding: 4px 12px;
      border-radius: 20px;
      background: var(--bg-tertiary);
      border: 1px solid var(--border-primary);
      color: var(--text-muted);
    }}
    .footer {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 24px 24px;
      border-top: 1px solid var(--border-primary);
      text-align: center;
      color: var(--text-muted);
      font-size: 13px;
    }}
    .footer-links {{
      display: flex;
      justify-content: center;
      gap: 20px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    .footer-links a {{ color: var(--text-muted); text-decoration: none; transition: color 0.2s; }}
    .footer-links a:hover {{ color: var(--text-primary); }}
    @media (max-width: 768px) {{
      .article-header h1 {{ font-size: 26px; }}
      .article-header .excerpt {{ font-size: 15px; }}
      .article-body h2 {{ font-size: 22px; }}
      .metrics-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body>

<header class="header">
  <div class="header-content">
    <a href="/" class="logo">
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect width="28" height="28" rx="6" fill="#58a6ff"/>
        <path d="M6 20L12 12L16 16L22 8" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="22" cy="8" r="2" fill="white"/>
      </svg>
      TradeVision<span class="logo-pro">PRO</span>
    </a>
    <a href="/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/" class="back-link">
      <i class="fas fa-arrow-left"></i> Back to Archive
    </a>
  </div>
</header>

<main class="container">

  <header class="article-header">
    <div class="meta">
      <span><i class="far fa-calendar-alt"></i> {date_str}</span>
      <span><i class="far fa-clock"></i> Auto-generated</span>
      <span><i class="fas fa-tag"></i> {symbol_name}</span>
    </div>
    <h1>{symbol_name} Daily Market Analysis</h1>
    <p class="excerpt">{report['summary']}</p>
  </header>

  <div class="article-body">

    <div style="margin-bottom:16px;">
      <span class="signal-badge {signal_class}">{report['signal']}</span>
      <span style="font-size:13px;color:var(--text-muted);">Confidence: {report['confidence']}%</span>
    </div>

    <!-- CHART -->
    <div class="chart-container">
      <div class="chart-header">
        <span><i class="fas fa-chart-line"></i> {symbol_name} Price Chart (30 Days)</span>
      </div>
      <div class="chart-body">
        {chart_img}
      </div>
    </div>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="value">${report['price']:,.2f}</div>
        <div class="label">Price</div>
      </div>
      <div class="metric-card">
        <div class="value {change_class}">{report['change_pct']:+.2f}%</div>
        <div class="label">24h Change</div>
      </div>
      <div class="metric-card">
        <div class="value">{report['rsi']}</div>
        <div class="label">RSI</div>
      </div>
      <div class="metric-card">
        <div class="value">{report['trend'].capitalize()}</div>
        <div class="label">Trend</div>
      </div>
    </div>

    <div class="info-box {'success' if report['trend'] == 'bullish' else 'danger' if report['trend'] == 'bearish' else 'warning'}">
      <strong>📈 Trend Analysis:</strong> {report['trend_desc']}
    </div>

    <h2>🎯 Key Levels</h2>
    <div class="table-wrapper">
      <table>
        <thead><tr><th>Level</th><th>Price</th><th>Significance</th></tr></thead>
        <tbody>
          <tr><td><strong>Resistance</strong></td><td class="down">${report['resistance']:,.2f}</td><td>Key resistance level</td></tr>
          <tr><td><strong>Support</strong></td><td class="up">${report['support']:,.2f}</td><td>Key support level</td></tr>
          <tr><td><strong>EMA 20</strong></td><td>${report['ema_20']:,.2f}</td><td>Short-term MA</td></tr>
          <tr><td><strong>EMA 50</strong></td><td>${report['ema_50']:,.2f}</td><td>Medium-term MA</td></tr>
        </tbody>
      </table>
    </div>

    <h2>🎯 Trading Signal</h2>
    <div class="info-box {'success' if report['signal'] == 'BUY' else 'danger' if report['signal'] == 'SELL' else 'warning'}">
      <strong>{'🟢' if report['signal'] == 'BUY' else '🔴' if report['signal'] == 'SELL' else '🟡'} {report['signal']} Signal</strong><br>
      Confidence: {report['confidence']}%<br><br>
      <strong>Reasons:</strong><br>
      {'<br>'.join(['• ' + r for r in report['signal_reason']])}
    </div>

    <div style="background:linear-gradient(135deg,var(--accent-muted),rgba(155,108,255,0.05));border:1px solid var(--accent-primary);border-radius:16px;padding:24px;text-align:center;margin:32px 0;">
      <h3 style="font-size:20px;font-weight:800;margin-bottom:8px;">🚀 Analyze {symbol_name} on TradeVision Pro</h3>
      <p style="color:var(--text-muted);margin-bottom:16px;">
        Use professional charts, 100+ indicators, and real-time data to make better trading decisions.
      </p>
      <a href="{tv_link}" target="_blank" style="display:inline-block;padding:12px 32px;background:linear-gradient(135deg,var(--accent-primary),#9b6cff);color:white;border-radius:10px;font-weight:700;font-size:16px;text-decoration:none;transition:opacity 0.2s;">
        <i class="fas fa-chart-line"></i> Open in TradeVision Pro
      </a>
      <p style="font-size:10px;color:var(--text-muted);margin-top:8px;">✓ Free ✓ 100+ indicators ✓ Real-time data</p>
    </div>

    <div class="info-box">
      <strong>📚 Related Content:</strong><br><br>
      • <a href="/pillar-guides/technical-analysis/">Complete Guide to Technical Analysis</a><br>
      • <a href="/pillar-guides/strategy-library/">Strategy Library</a><br>
      • <a href="/pillar-guides/institutional-tools/">Institutional Trading Tools</a>
    </div>
    
  </div>
  
</main>

<footer class="footer">
  <div class="footer-links">
    <a href="/">Home</a>
    <a href="/pillar-guides/technical-analysis/">Complete Guide</a>
    <a href="/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/">Daily Archive</a>
    <a href="https://tradevisionpro.online" target="_blank">TradeVision Pro</a>
  </div>
  <p>&copy; 2026 TradeVision Pro. All rights reserved.</p>
</footer>

</body>
</html>'''
    
    return html

# ============================================
# 6. GENERATE POSTS JSON
# ============================================

def generate_posts_json(articles):
    json_path = f'{OUTPUT_DIR}/posts.json'
    with open(json_path, 'w') as f:
        json.dump(articles, f, indent=2)
    print(f'✅ Created posts.json with {len(articles)} articles')

# ============================================
# 7. UPDATE ARCHIVE PAGE
# ============================================

def update_archive_page(year, month, articles):
    archive_path = f'{OUTPUT_DIR}/{year}/{month}/index.html'
    
    article_list = []
    for article in articles:
        article_list.append(f'''
    <a href="/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/{article['day']}-{article['symbol'].lower().replace('usdt', '')}-analysis.html" class="article-item">
      <span class="date">{article['date']}</span>
      <span class="title">{article['title']}</span>
      <span class="arrow"><i class="fas fa-arrow-right"></i></span>
    </a>
    ''')
    
    month_name = datetime(int(year), int(month), 1).strftime('%B')
    
    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Market Analysis - {month_name} {year} | TradeVision Pro</title>
  <meta name="description" content="Daily crypto market analysis for {month_name} {year}. Technical analysis, key levels, and trading signals." />
  <link rel="canonical" href="https://tradevisionpro.online/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" />
  <style>
    /* ... (archive styles) ... */
    :root {{
      --bg-primary: #0d1117;
      --bg-secondary: #161b22;
      --bg-tertiary: #1c2128;
      --text-primary: #e6edf3;
      --text-secondary: #c9d1d9;
      --text-muted: #8b949e;
      --accent-primary: #58a6ff;
      --border-primary: #30363d;
      --radius-xl: 16px;
    }}
    [data-theme="light"] {{
      --bg-primary: #ffffff;
      --bg-secondary: #f6f8fa;
      --bg-tertiary: #f0f2f5;
      --text-primary: #1f2328;
      --text-secondary: #424a53;
      --text-muted: #656d76;
      --border-primary: #d0d7de;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: var(--bg-primary);
      color: var(--text-primary);
      line-height: 1.7;
      transition: background 0.3s, color 0.3s;
    }}
    .header {{
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border-primary);
      padding: 12px 24px;
      position: sticky;
      top: 0;
      z-index: 1000;
    }}
    .header-content {{
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      color: var(--text-primary);
      font-weight: 800;
      font-size: 20px;
    }}
    .logo-pro {{
      background: rgba(88, 166, 255, 0.1);
      color: var(--accent-primary);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 700;
    }}
    .back-link {{
      color: var(--text-muted);
      text-decoration: none;
      font-size: 14px;
      transition: color 0.2s;
    }}
    .back-link:hover {{ color: var(--accent-primary); }}
    .back-link i {{ margin-right: 6px; }}
    .container {{
      max-width: 1000px;
      margin: 0 auto;
      padding: 32px 24px 60px;
    }}
    .page-header {{
      margin-bottom: 32px;
      border-bottom: 1px solid var(--border-primary);
      padding-bottom: 16px;
    }}
    .page-header h1 {{
      font-size: 32px;
      font-weight: 800;
    }}
    .page-header .subtitle {{
      color: var(--text-muted);
      font-size: 16px;
    }}
    .article-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .article-item {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 20px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-primary);
      border-radius: var(--radius-xl);
      text-decoration: none;
      color: var(--text-primary);
      transition: all 0.2s;
    }}
    .article-item:hover {{
      border-color: var(--accent-primary);
      transform: translateX(4px);
    }}
    .article-item .date {{
      font-size: 12px;
      color: var(--text-muted);
      min-width: 80px;
    }}
    .article-item .title {{
      font-weight: 600;
      font-size: 15px;
      flex: 1;
      margin: 0 12px;
    }}
    .article-item .arrow {{
      color: var(--text-muted);
      font-size: 14px;
      transition: transform 0.2s;
    }}
    .article-item:hover .arrow {{
      transform: translateX(4px);
      color: var(--accent-primary);
    }}
    .footer {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 40px 24px 24px;
      border-top: 1px solid var(--border-primary);
      text-align: center;
      color: var(--text-muted);
      font-size: 13px;
    }}
    @media (max-width: 768px) {{
      .page-header h1 {{ font-size: 24px; }}
      .article-item {{ flex-wrap: wrap; gap: 8px; }}
      .article-item .date {{ min-width: auto; }}
    }}
  </style>
</head>
<body>

<header class="header">
  <div class="header-content">
    <a href="/" class="logo">
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect width="28" height="28" rx="6" fill="#58a6ff"/>
        <path d="M6 20L12 12L16 16L22 8" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="22" cy="8" r="2" fill="white"/>
      </svg>
      TradeVision<span class="logo-pro">PRO</span>
    </a>
    <a href="/pillar-guides/technical-analysis/daily-analysis/" class="back-link">
      <i class="fas fa-arrow-left"></i> Back to Blog
    </a>
  </div>
</header>

<main class="container">
  <div class="page-header">
    <h1>📊 {month_name} {year} Daily Analysis</h1>
    <p class="subtitle">Technical analysis, key levels, and trading signals</p>
  </div>
  
  <div class="article-list">
    {''.join(article_list)}
  </div>
  
  <div style="margin-top:32px;padding-top:16px;border-top:1px solid var(--border-primary);text-align:center;">
    <a href="https://tradevisionpro.online" target="_blank" style="display:inline-block;padding:10px 24px;background:var(--accent-primary);color:white;border-radius:8px;font-weight:600;text-decoration:none;">
      <i class="fas fa-chart-line"></i> Analyze on TradeVision Pro
    </a>
  </div>
</main>

<footer class="footer">
  <p>&copy; 2026 TradeVision Pro. All rights reserved.</p>
</footer>

</body>
</html>'''
    
    with open(archive_path, 'w') as f:
        f.write(html)
    print(f'✅ Updated archive: {archive_path}')

# ============================================
# 8. MAIN EXECUTION
# ============================================

def main():
    print('🚀 Starting auto-blog generator...')
    print(f'📡 Using Binance US API: {BINANCE_API}')
    
    now = datetime.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    day = now.strftime('%d')
    
    os.makedirs(f'{OUTPUT_DIR}/{year}/{month}', exist_ok=True)
    
    articles = []
    posts_json = []
    
    for symbol in TOP_SYMBOLS:
        print(f'📊 Analyzing {symbol}...')
        try:
            # Fetch data
            stats = fetch_24hr_stats(symbol)
            klines = fetch_klines(symbol, '1d', 30)
            
            # Generate analysis
            report = generate_analysis(symbol, stats, klines)
            
            # Generate chart
            print(f'   📈 Generating chart for {symbol}...')
            chart_base64 = generate_chart(symbol, klines, None)
            
            # Generate HTML
            symbol_name = symbol.replace('USDT', '').lower()
            filename = f'{OUTPUT_DIR}/{year}/{month}/{day}-{symbol_name}-analysis.html'
            
            html = generate_html(report, chart_base64)
            with open(filename, 'w') as f:
                f.write(html)
            print(f'✅ Created: {filename}')
            
            articles.append({
                'day': day,
                'symbol': symbol,
                'date': now.strftime('%b %d'),
                'title': f'{symbol.replace("USDT", "")} - ${report["price"]:,.2f} ({report["trend"].capitalize()})'
            })
            
            posts_json.append({
                'url': f'/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/{day}-{symbol_name}-analysis.html',
                'symbol': symbol.replace('USDT', ''),
                'date': now.strftime('%b %d, %Y'),
                'title': f'{symbol.replace("USDT", "")} - {report["trend"].capitalize()} Trend at ${report["price"]:,.2f}',
                'excerpt': report['summary'][:150] + '...',
                'price': f'{report["price"]:,.2f}',
                'change': f'{report["change_pct"]:.2f}',
                'signal': report['signal']
            })
            
        except Exception as e:
            print(f'❌ Error analyzing {symbol}: {e}')
            continue
    
    if articles:
        update_archive_page(year, month, articles)
    
    if posts_json:
        generate_posts_json(posts_json)
    
    print('🎉 Auto-blog generation complete!')
    print(f'📊 Generated {len(articles)} articles for {len(TOP_SYMBOLS)} assets')

if __name__ == '__main__':
    main()
