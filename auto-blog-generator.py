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

# ============================================
# CONFIGURATION
# ============================================

BINANCE_API = 'https://api.binance.us/api/v3'

# 50+ Popular Assets from Binance
TOP_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'ADAUSDT', 'DOGEUSDT', 'DOTUSDT', 'LINKUSDT', 'AVAXUSDT',
    'MATICUSDT', 'UNIUSDT', 'ATOMUSDT', 'LTCUSDT', 'BCHUSDT',
    'NEARUSDT', 'FILUSDT', 'APTUSDT', 'ARBUSDT', 'OPUSDT',
    'INJUSDT', 'SUIUSDT', 'SEIUSDT', 'RNDRUSDT', 'GRTUSDT',
    'MKRUSDT', 'AAVEUSDT', 'VETUSDT', 'ICPUSDT', 'FTMUSDT',
    'ALGOUSDT', 'EGLDUSDT', 'XLMUSDT', 'HBARUSDT', 'QNTUSDT',
    'SNXUSDT', 'EOSUSDT', 'THETAUSDT', 'KAVAUSDT', 'ZECUSDT',
    'XTZUSDT', 'MANAUSDT', 'SANDUSDT', 'GALAUSDT', 'AXSUSDT',
    'CHZUSDT', 'APEUSDT', 'ARUSDT', 'RUNEUSDT', 'FLOWUSDT',
    'NEOUSDT', 'IOTAUSDT', 'KSMUSDT', 'XMRUSDT', 'ETCUSDT',
    'TRXUSDT', 'TONUSDT', 'PEPEUSDT', 'WLDUSDT', 'ENAUSDT',
    'ONDOUSDT', 'FETUSDT', 'TAOUSDT', 'HYPEUSDT', 'SHIBUSDT',
    'FLOKIUSDT', 'MEMEUSDT', 'ORDIUSDT', 'STXUSDT', 'WIFUSDT'
]

OUTPUT_DIR = 'pillar-guides/technical-analysis/daily-analysis'

# ============================================
# BATCH FETCH FUNCTIONS
# ============================================

def fetch_all_prices():
    url = f"{BINANCE_API}/ticker/price"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        return {item['symbol']: float(item['price']) for item in data}
    except Exception as e:
        print(f"⚠️ Error fetching prices: {e}")
        return {}

def fetch_all_24hr_stats():
    url = f"{BINANCE_API}/ticker/24hr"
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        return {item['symbol']: item for item in data}
    except Exception as e:
        print(f"⚠️ Error fetching 24hr stats: {e}")
        return {}

def fetch_klines(symbol, interval='1d', limit=30):
    url = f"{BINANCE_API}/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        return [{
            'time': c[0],
            'open': float(c[1]),
            'high': float(c[2]),
            'low': float(c[3]),
            'close': float(c[4]),
            'volume': float(c[5])
        } for c in data]
    except Exception as e:
        print(f"⚠️ Kline error for {symbol}: {e}")
        return []

# ============================================
# CHART GENERATION
# ============================================

def generate_chart(symbol, klines):
    if not klines or len(klines) < 5:
        return None
    
    try:
        dates = [datetime.fromtimestamp(k['time'] / 1000) for k in klines]
        closes = [k['close'] for k in klines]
        highs = [k['high'] for k in klines]
        lows = [k['low'] for k in klines]
        
        fig, ax = plt.subplots(figsize=(8, 4), dpi=80)
        ax.plot(dates, closes, color='#58a6ff', linewidth=2)
        ax.fill_between(dates, highs, lows, alpha=0.1, color='#58a6ff')
        
        ax.set_facecolor('#0d1117')
        fig.patch.set_facecolor('#0d1117')
        ax.tick_params(colors='#8b949e')
        ax.spines['bottom'].set_color('#30363d')
        ax.spines['top'].set_color('#30363d')
        ax.spines['left'].set_color('#30363d')
        ax.spines['right'].set_color('#30363d')
        ax.set_title(f'{symbol} Price', color='#e6edf3', fontsize=12)
        ax.grid(True, alpha=0.1, color='#30363d')
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=80, facecolor='#0d1117')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        
        return img_base64
        
    except Exception as e:
        print(f"⚠️ Chart error for {symbol}: {e}")
        return None

# ============================================
# ANALYSIS FUNCTIONS
# ============================================

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
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
    return 100 - (100 / (1 + (avg_gain / avg_loss)))

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
    if len(closes) < 20:
        return 'neutral', 'Insufficient data'
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
    return 'neutral', 'Consolidating'

def find_support_resistance(klines):
    if len(klines) < 10:
        return {'resistance': 0, 'support': 0}
    highs = [k['high'] for k in klines[-30:]]
    lows = [k['low'] for k in klines[-30:]]
    current = klines[-1]['close'] if klines else 0
    resistance = min([h for h in highs if h > current], default=max(highs) if highs else 0)
    support = max([l for l in lows if l < current], default=min(lows) if lows else 0)
    return {'resistance': round(resistance, 2), 'support': round(support, 2)}

def generate_analysis(symbol, stats, klines, price_data=None):
    if symbol in stats:
        s = stats[symbol]
        current_price = float(s.get('lastPrice', 0))
        price_change_pct = float(s.get('priceChangePercent', 0))
        high_24h = float(s.get('highPrice', 0))
        low_24h = float(s.get('lowPrice', 0))
    elif price_data and symbol in price_data:
        current_price = price_data[symbol]
        price_change_pct = 0
        high_24h = current_price * 1.05
        low_24h = current_price * 0.95
    else:
        return None
    
    closes = [k['close'] for k in klines] if klines else []
    rsi = calculate_rsi(closes) if closes else 50
    ema_20 = calculate_ema(closes, 20) if closes else current_price
    ema_50 = calculate_ema(closes, 50) if closes else current_price
    levels = find_support_resistance(klines) if klines else {'resistance': current_price * 1.05, 'support': current_price * 0.95}
    trend, trend_desc = detect_trend(klines) if klines else ('neutral', 'Data unavailable')
    
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
    
    return {
        'symbol': symbol,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M'),
        'price': current_price,
        'change_pct': price_change_pct,
        'high_24h': high_24h,
        'low_24h': low_24h,
        'rsi': round(rsi, 1),
        'ema_20': round(ema_20, 2),
        'ema_50': round(ema_50, 2),
        'trend': trend,
        'trend_desc': trend_desc,
        'resistance': levels['resistance'],
        'support': levels['support'],
        'signal': signal,
        'confidence': min(confidence, 100),
        'signal_reason': signal_reason
    }

# ============================================
# HTML GENERATION - COMPLETELY FIXED
# ============================================

def generate_html(report, chart_base64):
    """Generate HTML with dark/light theme support"""
    symbol_name = report['symbol'].replace('USDT', '')
    date_str = datetime.now().strftime('%B %d, %Y')
    year = datetime.now().strftime('%Y')
    month = datetime.now().strftime('%m')
    day = datetime.now().strftime('%d')
    
    tv_link = f"https://tradevisionpro.online?symbol={report['symbol']}"
    signal_class = 'buy' if report['signal'] == 'BUY' else 'sell' if report['signal'] == 'SELL' else 'hold'
    change_class = 'up' if report['change_pct'] > 0 else 'down'
    
    chart_img = f"<img src='data:image/png;base64,{chart_base64}' alt='{symbol_name} Price Chart' style='width:100%;border-radius:12px;' />" if chart_base64 else "<p style='color:var(--text-muted);text-align:center;'>📊 Chart unavailable</p>"
    
    # Use a separate string for the JavaScript to avoid f-string issues
    js_code = """
  const themeToggle = document.getElementById('themeToggle');
  const themeIcon = document.getElementById('themeIcon');
  const html = document.documentElement;
  
  const savedTheme = localStorage.getItem('tv-theme') || 'dark';
  html.setAttribute('data-theme', savedTheme);
  themeIcon.className = savedTheme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
  
  themeToggle.addEventListener('click', function() {
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('tv-theme', next);
    themeIcon.className = next === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
  });
"""
    
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{symbol_name} Analysis - {date_str} | TradeVision Pro</title>
  <meta name="description" content="{symbol_name} daily analysis. Price ${report['price']:,.2f}, {report['trend']} trend, RSI {report['rsi']}.">
  <link rel="canonical" href="https://tradevisionpro.online/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/{day}-{symbol_name.lower()}-analysis.html">
  
  <meta property="og:title" content="{symbol_name} Daily Analysis - {date_str}" />
  <meta property="og:description" content="{symbol_name} market analysis. Price: ${report['price']:,.2f}, Signal: {report['signal']}." />
  <meta property="og:image" content="https://tradevisionpro.online/profile.png" />
  <meta property="og:url" content="https://tradevisionpro.online/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/{day}-{symbol_name.lower()}-analysis.html" />
  <meta property="og:type" content="article" />
  
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
  
  <style>
    :root {{
      --bg-primary: #0a0e17;
      --bg-secondary: #111827;
      --bg-tertiary: #1a2332;
      --bg-card: #0f1729;
      --bg-card-hover: #1a2744;
      --text-primary: #f0f4ff;
      --text-secondary: #b0c4e8;
      --text-muted: #6b8bb0;
      --accent-primary: #4f8cff;
      --accent-secondary: #7c6bff;
      --accent-glow: rgba(79, 140, 255, 0.15);
      --gradient-main: linear-gradient(135deg, #4f8cff, #7c6bff);
      --up-color: #00d4aa;
      --down-color: #ff6b8a;
      --border-primary: rgba(79, 140, 255, 0.12);
      --shadow-lg: 0 20px 60px rgba(0, 0, 0, 0.5);
      --shadow-glow: 0 0 60px rgba(79, 140, 255, 0.05);
      --radius-xl: 20px;
      --radius-lg: 14px;
      --transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    [data-theme="light"] {{
      --bg-primary: #f0f4ff;
      --bg-secondary: #ffffff;
      --bg-tertiary: #e8edf8;
      --bg-card: #ffffff;
      --bg-card-hover: #f5f8ff;
      --text-primary: #0a1628;
      --text-secondary: #2a3a5a;
      --text-muted: #6b8bb0;
      --border-primary: rgba(79, 140, 255, 0.15);
      --shadow-lg: 0 20px 60px rgba(79, 140, 255, 0.08);
      --shadow-glow: 0 0 60px rgba(79, 140, 255, 0.03);
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Inter', sans-serif; background: var(--bg-primary); color: var(--text-primary); line-height: 1.8; transition: background var(--transition), color var(--transition); min-height: 100vh; }}
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: var(--bg-secondary); }}
    ::-webkit-scrollbar-thumb {{ background: var(--accent-primary); border-radius: 3px; }}
    a {{ color: var(--accent-primary); text-decoration: none; transition: color var(--transition); }}
    a:hover {{ color: var(--accent-secondary); }}
    
    .header {{ background: var(--bg-secondary); border-bottom: 1px solid var(--border-primary); padding: 14px 24px; position: sticky; top: 0; z-index: 1000; backdrop-filter: blur(20px); transition: background var(--transition), border-color var(--transition); }}
    .header-content {{ max-width: 1000px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }}
    .logo {{ display: flex; align-items: center; gap: 10px; text-decoration: none; color: var(--text-primary); font-weight: 800; font-size: 20px; transition: color var(--transition); }}
    .logo svg {{ flex-shrink: 0; }}
    .logo-pro {{ background: var(--gradient-main); color: white; padding: 2px 10px; border-radius: 6px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; }}
    .back-link {{ color: var(--text-muted); text-decoration: none; font-size: 14px; font-weight: 500; transition: color var(--transition); display: flex; align-items: center; gap: 6px; }}
    .back-link:hover {{ color: var(--accent-primary); }}
    .theme-toggle-btn {{ background: var(--bg-tertiary); border: 1px solid var(--border-primary); border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--text-secondary); font-size: 17px; transition: all var(--transition); }}
    .theme-toggle-btn:hover {{ border-color: var(--accent-primary); color: var(--accent-primary); background: var(--accent-glow); transform: rotate(30deg); }}
    
    .container {{ max-width: 900px; margin: 0 auto; padding: 32px 24px 60px; }}
    .article-header {{ margin-bottom: 32px; padding-bottom: 20px; border-bottom: 1px solid var(--border-primary); }}
    .article-header .meta {{ font-size: 13px; color: var(--text-muted); margin-bottom: 10px; display: flex; gap: 20px; flex-wrap: wrap; }}
    .article-header .meta span {{ display: flex; align-items: center; gap: 6px; }}
    .article-header h1 {{ font-size: 38px; font-weight: 900; line-height: 1.2; margin-bottom: 10px; }}
    .article-header .excerpt {{ font-size: 18px; color: var(--text-secondary); line-height: 1.6; }}
    
    .signal-badge {{ display: inline-block; padding: 6px 20px; border-radius: 30px; font-weight: 700; font-size: 14px; margin-right: 10px; letter-spacing: 0.5px; }}
    .signal-badge.buy {{ background: rgba(0, 212, 170, 0.15); color: var(--up-color); border: 1px solid rgba(0, 212, 170, 0.2); }}
    .signal-badge.sell {{ background: rgba(255, 107, 138, 0.15); color: var(--down-color); border: 1px solid rgba(255, 107, 138, 0.2); }}
    .signal-badge.hold {{ background: rgba(255, 193, 7, 0.15); color: #ffc107; border: 1px solid rgba(255, 193, 7, 0.2); }}
    .confidence {{ font-size: 13px; color: var(--text-muted); }}
    
    .chart-container {{ background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: var(--radius-xl); overflow: hidden; margin: 24px 0; transition: border-color var(--transition); }}
    .chart-container:hover {{ border-color: var(--accent-primary); }}
    .chart-container .chart-header {{ padding: 12px 18px; background: var(--bg-tertiary); border-bottom: 1px solid var(--border-primary); font-size: 12px; font-weight: 600; color: var(--text-secondary); display: flex; justify-content: space-between; align-items: center; }}
    .chart-container .chart-body {{ padding: 16px; background: var(--bg-primary); }}
    .chart-container .chart-body img {{ width: 100%; border-radius: 12px; }}
    
    .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric-card {{ background: var(--bg-card); border: 1px solid var(--border-primary); border-radius: var(--radius-lg); padding: 16px; text-align: center; transition: all var(--transition); }}
    .metric-card:hover {{ border-color: var(--accent-primary); transform: translateY(-2px); }}
    .metric-card .value {{ font-size: 20px; font-weight: 800; color: var(--text-primary); font-family: 'SF Mono', monospace; }}
    .metric-card .value.up {{ color: var(--up-color); }}
    .metric-card .value.down {{ color: var(--down-color); }}
    .metric-card .label {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
    
    .table-wrapper {{ overflow-x: auto; margin: 20px 0; border: 1px solid var(--border-primary); border-radius: var(--radius-lg); }}
    .table-wrapper table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    .table-wrapper th {{ padding: 12px 16px; text-align: left; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; background: var(--bg-tertiary); border-bottom: 2px solid var(--border-primary); color: var(--text-muted); }}
    .table-wrapper td {{ padding: 10px 16px; border-bottom: 1px solid var(--border-primary); color: var(--text-secondary); }}
    .table-wrapper tr:hover td {{ background: var(--bg-card-hover); }}
    .table-wrapper .up {{ color: var(--up-color); font-weight: 600; }}
    .table-wrapper .down {{ color: var(--down-color); font-weight: 600; }}
    
    .info-box {{ background: var(--bg-card); border-left: 4px solid var(--accent-primary); border-radius: var(--radius-lg); padding: 18px 22px; margin: 24px 0; border: 1px solid var(--border-primary); transition: border-color var(--transition); }}
    .info-box:hover {{ border-color: var(--accent-primary); }}
    .info-box.success {{ border-left-color: var(--up-color); }}
    .info-box.danger {{ border-left-color: var(--down-color); }}
    .info-box strong {{ color: var(--text-primary); }}
    
    .cta-box {{ background: var(--bg-card); border: 1px solid var(--accent-primary); border-radius: var(--radius-xl); padding: 28px 32px; text-align: center; margin: 32px 0; transition: all var(--transition); }}
    .cta-box:hover {{ border-color: var(--accent-secondary); box-shadow: var(--shadow-glow); transform: translateY(-2px); }}
    .cta-box h3 {{ font-size: 22px; font-weight: 800; margin-bottom: 8px; }}
    .cta-box p {{ color: var(--text-muted); margin-bottom: 16px; }}
    .cta-box .btn {{ display: inline-block; padding: 12px 32px; background: var(--gradient-main); color: white; border-radius: 10px; font-weight: 700; font-size: 16px; text-decoration: none; transition: all var(--transition); box-shadow: 0 4px 20px rgba(79, 140, 255, 0.3); }}
    .cta-box .btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(79, 140, 255, 0.4); opacity: 0.9; }}
    .cta-box .sub {{ font-size: 10px; color: var(--text-muted); margin-top: 8px; }}
    
    .tags {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0; }}
    .tags span {{ font-size: 11px; padding: 4px 14px; border-radius: 20px; background: var(--bg-tertiary); border: 1px solid var(--border-primary); color: var(--text-muted); }}
    
    .footer {{ max-width: 1200px; margin: 0 auto; padding: 40px 24px 24px; border-top: 1px solid var(--border-primary); text-align: center; color: var(--text-muted); font-size: 13px; }}
    .footer-links {{ display: flex; justify-content: center; gap: 20px; margin-bottom: 12px; flex-wrap: wrap; }}
    .footer-links a {{ color: var(--text-muted); transition: color var(--transition); }}
    .footer-links a:hover {{ color: var(--text-primary); }}
    
    @media (max-width: 768px) {{
      .article-header h1 {{ font-size: 28px; }}
      .article-header .excerpt {{ font-size: 15px; }}
      .metrics-grid {{ grid-template-columns: 1fr 1fr; }}
      .cta-box {{ padding: 20px; }}
      .cta-box h3 {{ font-size: 18px; }}
    }}
    @media (max-width: 480px) {{
      .article-header h1 {{ font-size: 22px; }}
      .metrics-grid {{ grid-template-columns: 1fr; }}
      .cta-box .btn {{ width: 100%; text-align: center; }}
    }}
  </style>
</head>
<body data-theme="dark">

<header class="header">
  <div class="header-content">
    <a href="/" class="logo">
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect width="28" height="28" rx="6" fill="#4f8cff"/>
        <path d="M6 20L12 12L16 16L22 8" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="22" cy="8" r="2" fill="white"/>
      </svg>
      TradeVision<span class="logo-pro">PRO</span>
    </a>
    <div style="display:flex;align-items:center;gap:12px;">
      <button class="theme-toggle-btn" id="themeToggle" aria-label="Toggle theme">
        <i class="fas fa-moon" id="themeIcon"></i>
      </button>
      <a href="/pillar-guides/technical-analysis/daily-analysis/" class="back-link">
        <i class="fas fa-arrow-left"></i> Blog
      </a>
    </div>
  </div>
</header>

<main class="container">
  <header class="article-header">
    <div class="meta">
      <span><i class="far fa-calendar-alt"></i> {date_str}</span>
      <span><i class="far fa-clock"></i> Updated {report['time']}</span>
      <span><i class="fas fa-tag"></i> {symbol_name}</span>
    </div>
    <h1>{symbol_name} Market Analysis</h1>
    <p class="excerpt">{symbol_name} is trading at ${report['price']:,.2f} with {report['trend']} trend. RSI at {report['rsi']}. {report['signal']} signal with {report['confidence']}% confidence.</p>
  </header>

  <div style="margin-bottom:24px;">
    <span class="signal-badge {signal_class}">{report['signal']}</span>
    <span class="confidence">Confidence: {report['confidence']}%</span>
  </div>

  <div class="chart-container">
    <div class="chart-header">
      <span><i class="fas fa-chart-line"></i> {symbol_name} Price Chart (30 Days)</span>
      <span style="font-size:10px;color:var(--text-muted);">Source: Binance</span>
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

  <div class="info-box {'success' if report['trend']=='bullish' else 'danger' if report['trend']=='bearish' else ''}">
    <strong>📈 Trend Analysis:</strong> {report['trend_desc']}
  </div>

  <h2 style="font-size:26px;font-weight:800;margin-top:32px;margin-bottom:16px;">🎯 Key Levels</h2>
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

  <h2 style="font-size:26px;font-weight:800;margin-top:32px;margin-bottom:16px;">🎯 Trading Signal</h2>
  <div class="info-box {'success' if report['signal']=='BUY' else 'danger' if report['signal']=='SELL' else ''}">
    <strong>{'🟢' if report['signal']=='BUY' else '🔴' if report['signal']=='SELL' else '🟡'} {report['signal']} Signal</strong><br>
    Confidence: {report['confidence']}%<br><br>
    <strong>Reasons:</strong><br>
    {'<br>'.join(['• ' + r for r in report['signal_reason']])}
  </div>

  <div class="cta-box">
    <h3>🚀 Analyze {symbol_name} on TradeVision Pro</h3>
    <p>Use professional charts, 100+ indicators, and real-time data to make better trading decisions.</p>
    <a href="{tv_link}" target="_blank" class="btn">
      <i class="fas fa-chart-line"></i> Open TradeVision Pro
    </a>
    <p class="sub">✓ Free ✓ 100+ indicators ✓ Real-time data</p>
  </div>

  <div class="info-box">
    <strong>📚 Related Content:</strong><br><br>
    • <a href="/pillar-guides/technical-analysis/">Complete Guide to Technical Analysis</a><br>
    • <a href="/pillar-guides/strategy-library/">Strategy Library</a><br>
    • <a href="/pillar-guides/institutional-tools/">Institutional Trading Tools</a>
  </div>

</main>

<footer class="footer">
  <div class="footer-links">
    <a href="/">Home</a>
    <a href="/pillar-guides/technical-analysis/">Complete Guide</a>
    <a href="/pillar-guides/technical-analysis/daily-analysis/{year}/{month}/">Archive</a>
    <a href="https://tradevisionpro.online" target="_blank">TradeVision Pro</a>
  </div>
  <p>&copy; 2026 TradeVision Pro. All rights reserved.</p>
</footer>

<script>
{js_code}
</script>

</body>
</html>"""

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    start_time = time.time()
    print(f'🚀 Auto-blog generator started at {datetime.now()}')
    print(f'📊 Tracking {len(TOP_SYMBOLS)} assets')
    
    now = datetime.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    day = now.strftime('%d')
    
    os.makedirs(f'{OUTPUT_DIR}/{year}/{month}', exist_ok=True)
    
    print('📡 Fetching market data...')
    price_data = fetch_all_prices()
    stats_data = fetch_all_24hr_stats()
    
    available_symbols = [s for s in TOP_SYMBOLS if s in price_data or s in stats_data]
    print(f'✅ Found {len(available_symbols)} available assets out of {len(TOP_SYMBOLS)}')
    
    articles = []
    posts_json = []
    
    total = len(available_symbols)
    for idx, symbol in enumerate(available_symbols, 1):
        print(f'📊 [{idx}/{total}] Analyzing {symbol}...')
        try:
            klines = fetch_klines(symbol, '1d', 30)
            report = generate_analysis(symbol, stats_data, klines, price_data)
            if not report:
                continue
            
            chart_base64 = generate_chart(symbol, klines) if klines else None
            
            symbol_name = symbol.replace('USDT', '').lower()
            filename = f'{OUTPUT_DIR}/{year}/{month}/{day}-{symbol_name}-analysis.html'
            
            html = generate_html(report, chart_base64)
            with open(filename, 'w') as f:
                f.write(html)
            
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
                'time': report['time'],
                'title': f'{symbol.replace("USDT", "")} - {report["trend"].capitalize()} at ${report["price"]:,.2f}',
                'price': f'{report["price"]:,.2f}',
                'change': f'{report["change_pct"]:.2f}',
                'signal': report['signal']
            })
            
        except Exception as e:
            print(f'❌ Error analyzing {symbol}: {e}')
            continue
    
    if posts_json:
        json_path = f'{OUTPUT_DIR}/posts.json'
        with open(json_path, 'w') as f:
            json.dump(posts_json, f, indent=2)
        print(f'✅ Updated posts.json with {len(posts_json)} articles')
    
    if articles:
        update_archive_page(year, month, articles)
    
    elapsed = time.time() - start_time
    print(f'🎉 Generation complete! {len(articles)} articles updated in {elapsed:.2f} seconds')

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
  <meta name="description" content="Daily crypto market analysis for {month_name} {year}." />
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
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:'Inter',sans-serif; background:var(--bg-primary); color:var(--text-primary); line-height:1.7; transition:background 0.3s, color 0.3s; }}
    .header {{ background:var(--bg-secondary); border-bottom:1px solid var(--border-primary); padding:12px 24px; position:sticky; top:0; z-index:1000; }}
    .header-content {{ max-width:1200px; margin:0 auto; display:flex; justify-content:space-between; align-items:center; }}
    .logo {{ display:flex; align-items:center; gap:10px; text-decoration:none; color:var(--text-primary); font-weight:800; font-size:20px; }}
    .logo-pro {{ background:rgba(88,166,255,0.1); color:var(--accent-primary); padding:2px 8px; border-radius:4px; font-size:10px; font-weight:700; }}
    .back-link {{ color:var(--text-muted); text-decoration:none; font-size:14px; transition:color 0.2s; }}
    .back-link:hover {{ color:var(--accent-primary); }}
    .back-link i {{ margin-right:6px; }}
    .container {{ max-width:1000px; margin:0 auto; padding:32px 24px 60px; }}
    .page-header {{ margin-bottom:32px; border-bottom:1px solid var(--border-primary); padding-bottom:16px; }}
    .page-header h1 {{ font-size:32px; font-weight:800; }}
    .page-header .subtitle {{ color:var(--text-muted); font-size:16px; }}
    .article-list {{ display:flex; flex-direction:column; gap:12px; }}
    .article-item {{ display:flex; justify-content:space-between; align-items:center; padding:14px 20px; background:var(--bg-secondary); border:1px solid var(--border-primary); border-radius:var(--radius-xl); text-decoration:none; color:var(--text-primary); transition:all 0.2s; }}
    .article-item:hover {{ border-color:var(--accent-primary); transform:translateX(4px); }}
    .article-item .date {{ font-size:12px; color:var(--text-muted); min-width:80px; }}
    .article-item .title {{ font-weight:600; font-size:15px; flex:1; margin:0 12px; }}
    .article-item .arrow {{ color:var(--text-muted); font-size:14px; transition:transform 0.2s; }}
    .article-item:hover .arrow {{ transform:translateX(4px); color:var(--accent-primary); }}
    .footer {{ max-width:1200px; margin:0 auto; padding:40px 24px 24px; border-top:1px solid var(--border-primary); text-align:center; color:var(--text-muted); font-size:13px; }}
    @media (max-width:768px) {{
      .page-header h1 {{ font-size:24px; }}
      .article-item {{ flex-wrap:wrap; gap:8px; }}
      .article-item .date {{ min-width:auto; }}
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
    <p class="subtitle">Technical analysis for {len(articles)} assets</p>
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

if __name__ == '__main__':
    main()
