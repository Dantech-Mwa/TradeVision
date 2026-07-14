# auto-blog-generator.py
import requests
import json
import os
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================

TOP_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
BINANCE_API = 'https://api.binance.com/api/v3'
OUTPUT_DIR = 'pillar-guides/technical-analysis/daily-analysis'

# ============================================
# 1. FETCH MARKET DATA
# ============================================

def fetch_24hr_stats(symbol):
    url = f"{BINANCE_API}/ticker/24hr?symbol={symbol}"
    response = requests.get(url)
    return response.json()

def fetch_klines(symbol, interval='4h', limit=100):
    url = f"{BINANCE_API}/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    data = response.json()
    return [{
        'time': c[0],
        'open': float(c[1]),
        'high': float(c[2]),
        'low': float(c[3]),
        'close': float(c[4]),
        'volume': float(c[5])
    } for c in data]

# ============================================
# 2. CALCULATE INDICATORS
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
# 3. GENERATE ANALYSIS
# ============================================

def generate_analysis(symbol, stats, klines):
    current_price = float(stats['lastPrice'])
    price_change = float(stats['priceChange'])
    price_change_pct = float(stats['priceChangePercent'])
    high_24h = float(stats['highPrice'])
    low_24h = float(stats['lowPrice'])
    volume = float(stats['volume'])
    
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
# 4. GENERATE HTML WITH TRADEVISION PRO LINK
# ============================================

def generate_html(report):
    day = datetime.now().strftime('%d')
    month = datetime.now().strftime('%m')
    year = datetime.now().strftime('%Y')
    symbol_name = report['symbol'].replace('USDT', '')
    date_str = datetime.now().strftime('%B %d, %Y')
    
    tv_link = f"https://tradevisionpro.online?symbol={report['symbol']}"
    
    signal_class = 'up' if report['signal'] == 'BUY' else 'down' if report['signal'] == 'SELL' else 'neutral'
    change_class = 'up' if report['change'] > 0 else 'down'
    
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
  <script src="https://unpkg.com/lightweight-charts@4.2.2/dist/lightweight-charts.standalone.production.js"></script>
  <style>
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
    .signal-badge.up {{ background: rgba(38, 166, 154, 0.15); color: var(--up-color); }}
    .signal-badge.down {{ background: rgba(239, 83, 80, 0.15); color: var(--down-color); }}
    .signal-badge.neutral {{ background: rgba(210, 153, 34, 0.15); color: #d29922; }}
    
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
    
    .chart-embed {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-primary);
      border-radius: var(--radius-xl);
      overflow: hidden;
      margin: 24px 0;
    }}
    .chart-embed-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 16px;
      background: var(--bg-tertiary);
      border-bottom: 1px solid var(--border-primary);
    }}
    .chart-embed-header span {{
      font-size: 12px;
      font-weight: 600;
      color: var(--text-secondary);
    }}
    .chart-embed-body {{
      padding: 0;
      min-height: 320px;
      background: var(--bg-primary);
      position: relative;
      cursor: pointer;
    }}
    .chart-embed-body .chart-container {{
      width: 100%;
      height: 320px;
      position: relative;
    }}
    .chart-embed-body .chart-container canvas {{
      width: 100% !important;
      height: 100% !important;
    }}
    .chart-embed-body .click-overlay {{
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 10;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      background: rgba(0, 0, 0, 0.4);
      opacity: 0;
      transition: opacity 0.3s;
      cursor: pointer;
    }}
    .chart-embed-body:hover .click-overlay {{ opacity: 1; }}
    .chart-embed-body .click-overlay span {{
      background: var(--accent-primary);
      color: white;
      padding: 10px 24px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 14px;
    }}
    .chart-embed-footer {{
      padding: 10px 16px;
      background: var(--bg-tertiary);
      border-top: 1px solid var(--border-primary);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      color: var(--text-muted);
    }}
    .chart-embed-footer .live-dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--up-color);
      display: inline-block;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.3; }}
    }}
    .chart-embed-footer .launch-btn {{
      background: var(--accent-primary);
      color: white;
      border: none;
      padding: 6px 16px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 11px;
      cursor: pointer;
      transition: opacity 0.2s;
      text-decoration: none;
    }}
    .chart-embed-footer .launch-btn:hover {{ opacity: 0.85; }}
    
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
      .chart-embed-body {{ min-height: 220px; }}
      .chart-embed-body .chart-container {{ height: 220px; }}
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

    <div class="chart-embed">
      <div class="chart-embed-header">
        <span><i class="fas fa-chart-line"></i> {symbol_name}/USDT Live Chart</span>
        <span style="font-size:10px;color:var(--text-muted);">4H · Real-time</span>
      </div>
      <div class="chart-embed-body">
        <div class="chart-container" id="chart"></div>
        <div class="click-overlay" onclick="window.open('{tv_link}', '_blank')">
          <span>🚀 Analyze on TradeVision Pro</span>
        </div>
      </div>
      <div class="chart-embed-footer">
        <span><span class="live-dot"></span> Live via Binance</span>
        <a href="{tv_link}" target="_blank" class="launch-btn">
          <i class="fas fa-chart-line"></i> Full Analysis → 
        </a>
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

<script>
  function renderChart() {{
    const container = document.getElementById('chart');
    if (!container) return;
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const colors = {{
      background: isDark ? '#0d1117' : '#ffffff',
      grid: isDark ? '#21262d' : '#e1e4e8',
      text: isDark ? '#c9d1d9' : '#424a53',
      up: '#26a69a',
      down: '#ef5350'
    }};
    const chart = LightweightCharts.createChart(container, {{
      width: container.clientWidth || 700,
      height: container.clientHeight || 320,
      layout: {{ background: {{ color: colors.background }}, textColor: colors.text, fontSize: 10 }},
      grid: {{ vertLines: {{ color: colors.grid }}, horzLines: {{ color: colors.grid }} }},
      rightPriceScale: {{ borderColor: colors.grid }},
      timeScale: {{ borderColor: colors.grid, timeVisible: true }},
    }});
    const series = chart.addCandlestickSeries({{
      upColor: colors.up,
      downColor: colors.down,
      borderUpColor: colors.up,
      borderDownColor: colors.down,
      wickUpColor: colors.up,
      wickDownColor: colors.down,
    }});
    fetch('https://api.binance.com/api/v3/klines?symbol={report['symbol']}&interval=4h&limit=100')
      .then(res => res.json())
      .then(data => {{
        const candles = data.map(c => ({{
          time: Math.floor(c[0] / 1000),
          open: parseFloat(c[1]),
          high: parseFloat(c[2]),
          low: parseFloat(c[3]),
          close: parseFloat(c[4]),
        }}));
        series.setData(candles);
        chart.timeScale().fitContent();
      }})
      .catch(() => {{
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);">📊 Loading data...</div>';
      }});
    const resize = () => {{
      const rect = container.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {{
        chart.applyOptions({{ width: rect.width, height: rect.height }});
        chart.timeScale().fitContent();
      }}
    }};
    window.addEventListener('resize', resize);
    new ResizeObserver(resize).observe(container);
  }}
  setTimeout(renderChart, 300);
</script>

</body>
</html>'''
    
    return html

# ============================================
# 5. GENERATE POSTS JSON FOR BLOG PAGE
# ============================================

def generate_posts_json(articles):
    json_path = f'{OUTPUT_DIR}/posts.json'
    with open(json_path, 'w') as f:
        json.dump(articles, f, indent=2)
    print(f'✅ Created posts.json with {len(articles)} articles')

# ============================================
# 6. UPDATE ARCHIVE PAGE
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
# 7. MAIN EXECUTION
# ============================================

def main():
    print('🚀 Starting auto-blog generator...')
    
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
            stats = fetch_24hr_stats(symbol)
            klines = fetch_klines(symbol, '4h', 100)
            report = generate_analysis(symbol, stats, klines)
            
            symbol_name = symbol.replace('USDT', '').lower()
            filename = f'{OUTPUT_DIR}/{year}/{month}/{day}-{symbol_name}-analysis.html'
            
            html = generate_html(report)
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
    
    if articles:
        update_archive_page(year, month, articles)
    
    if posts_json:
        generate_posts_json(posts_json)
    
    print('🎉 Auto-blog generation complete!')

if __name__ == '__main__':
    main()
