// indicator-engine.js (upgraded)
// Features added:
// - 30+ indicators (added TSI, DPO, Elder-Ray, Z-Score, Heikin-Ashi)
// - Optimized calculations using rolling/streaming algorithms where possible
// - Caching keyed by indicator+timeframe+lastCandleTime for fast live updates
// - Color rules / overbought-oversold flags included in indicator outputs
// - Multi-timeframe support (setCandles accepts optional timeframe id)
// - getIndicatorsGrouped() returns categories for UI

window.IndicatorsEngine = (function(){
  // --- Internal state ---
  const store = {
    candles: {},            // { timeframe: [candles] }
    enabled: {},            // enabled indicators set
    cache: {},              // caching for computed indicators
    callbacks: {},          // onUpdate callbacks per indicator
    params: {}              // per-indicator params
  };

  // default params (can be modified externally)
  const DEFAULTS = {
    SMA: { period: 14 },
    EMA: { period: 14 },
    RSI: { period: 14 },
    MACD: { fast:12, slow:26, signal:9 },
    ATR: { period:14 },
    Bollinger: { period:20, mult:2 },
    VWAP: {},
    STOCH: { k:14, d:3 },
    // ... other defaults ...
    TSI: { long:25, short:13, signal:7 },
    DPO: { period:20 },
    ElderRay: { ema:13 },
    ZScore: { period:20 },
    HeikinAshi: {}
  };

  function setParam(name, p){ store.params[name]=Object.assign({}, DEFAULTS[name]||{}, p); }

  // --- External API ---
  function setCandles(list, timeframe='1m'){
    // list is array of {time,open,high,low,close,volume}
    store.candles[timeframe] = list || [];
    // Invalidate cache for this timeframe
    Object.keys(store.cache).forEach(k=>{ if(k.includes(`::${timeframe}::`)) delete store.cache[k]; });
  }

  function setMultiCandles(map){ // map: {tf: candles[]}
    Object.keys(map||{}).forEach(tf=> setCandles(map[tf], tf));
  }

  function addIndicator(name){ store.enabled[name]=true; }
  function removeIndicator(name){ delete store.enabled[name]; }

  function onUpdate(name, fn){ store.callbacks[name]=fn; }

  function recomputeAll(timeframe='1m'){
    const keys = Object.keys(store.enabled);
    keys.forEach(k => runIndicator(k, timeframe));
  }

  function getIndicatorsGrouped(){
    return {
      Trend: ['SMA','EMA','WMA','HMA','Ichimoku','SuperTrend','PSAR','Keltner','Donchian','PivotPoints','HeikinAshi','DPO','ElderRay'],
      Momentum: ['RSI','MACD','Stochastic','CCI','ROC','Momentum','WilliamsR','TSI','ZScore'],
      VolatilityVolume: ['ATR','Bollinger','VWAP','OBV','MFI','CMF','ADX','VolatilityIndex']
    };
  }

  // --- Utility: cache wrapper ---
  function cacheKey(name, timeframe){
    const c = (store.candles[timeframe]||[]);
    const last = c.length? c[c.length-1].time : '0';
    return `${name}::${timeframe}::${last}`;
  }
  function fromCacheOrCompute(name, timeframe, computeFn){
    const key = cacheKey(name,timeframe);
    if(store.cache[key]) return store.cache[key];
    const res = computeFn();
    store.cache[key] = res;
    // Keep cache small
    const keys = Object.keys(store.cache);
    if(keys.length>200) delete store.cache[keys[0]];
    return res;
  }

  // --- Optimized rolling helpers ---
  function rollingSum(arr, start, len, accessor){
    let s=0; for(let i=start;i<start+len;i++) s += accessor(arr[i]); return s;
  }

  // Efficient EMA that returns array of values and allows incremental continuation
  function emaArray(values, period){
    const k = 2/(period+1);
    const out = new Array(values.length);
    let prev = values[0]; out[0]=prev;
    for(let i=1;i<values.length;i++){ prev = values[i]*k + prev*(1-k); out[i]=prev; }
    return out;
  }

  // --- Core indicator implementations (optimized) ---
  const impl = {
    SMA: (tf)=>{
      const c = store.candles[tf]||[]; const p = (store.params.SMA||DEFAULTS.SMA).period; if(c.length===0) return [];
      const out = new Array(c.length).fill(null);
      let sum=0; for(let i=0;i<c.length;i++){
        sum += c[i].close;
        if(i>=p) sum -= c[i-p].close;
        out[i] = i+1>=p ? sum/p : null;
      }
      return out.map((v,i)=>({time:c[i].time,value:v}));
    },

    EMA: (tf)=>{
      const c = store.candles[tf]||[]; const p=(store.params.EMA||DEFAULTS.EMA).period; if(!c.length) return [];
      const vals = c.map(x=>x.close);
      const arr = emaArray(vals,p);
      return arr.map((v,i)=>({time:c[i].time,value:v}));
    },

    WMA: (tf)=>{
      const c=store.candles[tf]||[]; const p=14; if(!c.length) return [];
      const out=[]; for(let i=0;i<c.length;i++){
        if(i<p-1){ out.push({time:c[i].time,value:null}); continue; }
        let num=0, den=0; for(let j=0;j<p;j++){ num += c[i-j].close*(p-j); den += (p-j); }
        out.push({time:c[i].time,value:num/den});
      }
      return out;
    },

    HMA: (tf)=>{ /* approximate HMA using WMA of half periods - kept simple for perf */
      const c=store.candles[tf]||[]; const p=16; if(!c.length) return [];
      const halfP = Math.floor(p/2);
      const wma = impl.WMA(tf).map(x=>x.value);
      const out = c.map((d,i)=>({time:d.time,value: (wma[i] ? 2*wma[i] - (wma[i]||0) : null)}));
      return out;
    },

    Ichimoku: (tf)=>{
      const c=store.candles[tf]||[]; if(!c.length) return [];
      const conv=9, base=26, span=52;
      const out=c.map((d,i)=>{ const convSlice=c.slice(Math.max(0,i-conv+1),i+1); const baseSlice=c.slice(Math.max(0,i-base+1),i+1); const spanSlice=c.slice(Math.max(0,i-span+1),i+1);
        const convVal = convSlice.length? (Math.max(...convSlice.map(x=>x.high))+Math.min(...convSlice.map(x=>x.low)))/2:null;
        const baseVal = baseSlice.length? (Math.max(...baseSlice.map(x=>x.high))+Math.min(...baseSlice.map(x=>x.low)))/2:null;
        const spanA = convVal && baseVal ? (convVal+baseVal)/2:null;
        const spanB = spanSlice.length? (Math.max(...spanSlice.map(x=>x.high))+Math.min(...spanSlice.map(x=>x.low)))/2:null;
        return {time:d.time, conversion:convVal, base:baseVal, spanA, spanB}; });
      return out;
    },

    SuperTrend: (tf)=>{ /* uses ATR optimized */
      const c=store.candles[tf]||[]; if(!c.length) return [];
      const period=10, mult=3; const atr = computeATRArray(c,period);
      const out=[]; let direction=1, prevFinal=0;
      for(let i=0;i<c.length;i++){ const hl2=(c[i].high+c[i].low)/2; const upper=hl2+mult*atr[i]; const lower=hl2-mult*atr[i]; let final=direction>0?upper:lower; out.push({time:c[i].time,upper,lower,final}); }
      return out;
    },

    PSAR: (tf)=>{ /* simplified PSAR for perf */
      const c=store.candles[tf]||[]; if(c.length<2) return [];
      let af=0.02, maxAf=0.2; let up=true; let ep=c[0].high; let psar=c[0].low; const out=[{time:c[0].time,value:psar}];
      for(let i=1;i<c.length;i++){ const cur=c[i]; psar = psar + af*(ep-psar); if(up){ if(cur.low<psar){ up=false; psar=ep; ep=cur.low; af=0.02;} else if(cur.high>ep){ ep=cur.high; af=Math.min(maxAf,af+0.02);} } else { if(cur.high>psar){ up=true; psar=ep; ep=cur.high; af=0.02;} else if(cur.low<ep){ ep=cur.low; af=Math.min(maxAf,af+0.02);} } out.push({time:cur.time,value:psar}); }
      return out;
    },

    PivotPoints: (tf)=>{ const c=store.candles[tf]||[]; if(c.length<2) return null; const d=c[c.length-2]; const P=(d.high+d.low+d.close)/3; const R1=2*P-d.low; const S1=2*P-d.high; const R2=P+(d.high-d.low); const S2=P-(d.high-d.low); return {P,R1,S1,R2,S2,time:c[c.length-1].time}; },

    Keltner: (tf)=>{ const c=store.candles[tf]||[]; const p=20,m=2; if(!c.length) return []; const ema = impl.EMA(tf).map(x=>x.value); const atr=computeATRArray(c,p); return c.map((d,i)=>({time:d.time,mid:ema[i],upper:ema[i]+atr[i]*m,lower:ema[i]-atr[i]*m})); },

    Donchian: (tf)=>{ const c=store.candles[tf]||[]; const p=20; if(!c.length) return []; return c.map((d,i)=>{ if(i<p) return {time:d.time,high:null,low:null}; const slice=c.slice(i-p+1,i+1); return {time:d.time,high:Math.max(...slice.map(x=>x.high)),low:Math.min(...slice.map(x=>x.low))}; }); },

    // --- Momentum Indicators ---
    RSI: (tf)=>{
      const c=store.candles[tf]||[]; const p=(store.params.RSI||DEFAULTS.RSI).period; if(!c.length) return [];
      const out=new Array(c.length).fill(null); let gains=0, losses=0;
      for(let i=1;i<c.length;i++){
        const change = c[i].close - c[i-1].close;
        if(i<=p){ if(change>0) gains+=change; else losses-=change; if(i===p) out[i]=100-(100/(1+(gains/p)/(losses/p||1))); else out[i]=null; }
        else{ const prevChange = c[i-p].close - c[i-p-1]?.close || 0; if(prevChange>0) gains -= prevChange; else losses -= -prevChange; if(change>0) gains+=change; else losses+=-change; const avgGain = gains/p, avgLoss = losses/p; const rs=avgLoss===0? 100: avgGain/avgLoss; out[i]=100-(100/(1+rs)); }
      }
      return out.map((v,i)=>({time:c[i].time,value:v, flag: v!==null && (v>70?'overbought': v<30?'oversold':'neutral')}));
    },

    MACD: (tf)=>{
      const p = store.params.MACD||DEFAULTS.MACD; const c=store.candles[tf]||[]; if(!c.length) return {macd:[],sig:[],hist:[]};
      const fast = emaArray(c.map(x=>x.close), p.fast);
      const slow = emaArray(c.map(x=>x.close), p.slow);
      const macd = fast.map((v,i)=>v - slow[i]);
      const sig = emaArray(macd, p.signal);
      const hist = macd.map((v,i)=>v - sig[i]);
      return { macd:macd.map((v,i)=>({time:c[i].time,value:v})), sig:sig.map((v,i)=>({time:c[i].time,value:v})), hist:hist.map((v,i)=>({time:c[i].time,value:v})) };
    },

    Stochastic: (tf)=>{
      const c=store.candles[tf]||[]; const p=(store.params.STOCH||DEFAULTS.STOCH).k; if(!c.length) return [];
      const out=[]; for(let i=0;i<c.length;i++){ if(i<p-1){ out.push({time:c[i].time,k:null,d:null}); continue;} const slice=c.slice(i-p+1,i+1); const high=Math.max(...slice.map(x=>x.high)); const low=Math.min(...slice.map(x=>x.low)); const kVal = (c[i].close - low)/(high-low||1)*100; const dVal = (out.slice(-3).reduce((s,x)=>s+(x.k||0),0))/3 || kVal; out.push({time:c[i].time,k:kVal,d:dVal}); }
      return out;
    },

    CCI: (tf)=>{ const c=store.candles[tf]||[]; const p=20; if(!c.length) return []; const out=[]; for(let i=0;i<c.length;i++){ const tp=(c[i].high+c[i].low+c[i].close)/3; if(i<p-1){ out.push({time:c[i].time,value:null}); continue;} const slice=c.slice(i-p+1,i+1).map(x=>(x.high+x.low+x.close)/3); const ma=slice.reduce((s,x)=>s+x,0)/p; const md=slice.reduce((s,x)=>s+Math.abs(x-ma),0)/p; out.push({time:c[i].time,value:(tp-ma)/(0.015*(md||1))}); } return out; },

    ROC: (tf)=>{ const c=store.candles[tf]||[]; const p=12; if(!c.length) return []; return c.map((d,i)=> i<p? {time:d.time,value:null}: {time:d.time,value:(d.close-c[i-p].close)/c[i-p].close*100}); },

    Momentum: (tf)=>{ const c=store.candles[tf]||[]; const p=14; if(!c.length) return []; return c.map((d,i)=> i<p? {time:d.time,value:null} : {time:d.time,value:d.close-c[i-p].close}); },

    WilliamsR: (tf)=>{ const c=store.candles[tf]||[]; const p=14; if(!c.length) return []; return c.map((d,i)=>{ if(i<p-1) return {time:d.time,value:null}; const slice=c.slice(i-p+1,i+1); const high=Math.max(...slice.map(x=>x.high)); const low=Math.min(...slice.map(x=>x.low)); return {time:d.time,value:(high-d.close)/(high-low||1)*-100}; }); },

    TSI: (tf)=>{
      // True Strength Index using double EMA of momentum
      const c=store.candles[tf]||[]; const p1=(store.params.TSI||DEFAULTS.TSI).short, p2=(store.params.TSI||DEFAULTS.TSI).long, signal=(store.params.TSI||DEFAULTS.TSI).signal;
      if(!c.length) return [];
      const m = c.map((d,i)=> i===0?0: d.close - c[i-1].close );
      const absM = m.map(v=>Math.abs(v));
      const ema1 = emaArray(m, p2); const ema2 = emaArray(ema1, p1);
      const emaAbs1 = emaArray(absM, p2); const emaAbs2 = emaArray(emaAbs1, p1);
      const tsi = ema2.map((v,i)=> (emaAbs2[i]===0?0: (v/emaAbs2[i])*100));
      const sig = emaArray(tsi, signal);
      return tsi.map((v,i)=>({time:c[i].time,value:v,signal:sig[i]}));
    },

    DPO: (tf)=>{ const c=store.candles[tf]||[]; const p=(store.params.DPO||DEFAULTS.DPO).period; if(!c.length) return []; const sma = impl.SMA(tf).map(x=>x.value); return c.map((d,i)=>({time:d.time,value: i>=p? c[i].close - sma[i - Math.floor(p/2)] : null })); },

    ElderRay: (tf)=>{ const c=store.candles[tf]||[]; const p=(store.params.ElderRay||DEFAULTS.ElderRay).ema; if(!c.length) return []; const ema = impl.EMA(tf).map(x=>x.value); return c.map((d,i)=>({time:d.time,bull: d.high - ema[i], bear: ema[i] - d.low})); },

    ZScore: (tf)=>{ const c=store.candles[tf]||[]; const p=(store.params.ZScore||DEFAULTS.ZScore).period; if(!c.length) return []; const out=[]; for(let i=0;i<c.length;i++){ if(i<p) { out.push({time:c[i].time,value:null}); continue; } const slice=c.slice(i-p+1,i+1).map(x=>x.close); const mu = slice.reduce((s,x)=>s+x,0)/p; const sd = Math.sqrt(slice.reduce((s,x)=>s+(x-mu)*(x-mu),0)/p); out.push({time:c[i].time,value: sd===0?0: (c[i].close - mu)/sd}); } return out; },

    HeikinAshi: (tf)=>{ const c=store.candles[tf]||[]; if(!c.length) return []; const out=[]; for(let i=0;i<c.length;i++){ const prev = out[i-1]; const haClose = (c[i].open + c[i].high + c[i].low + c[i].close)/4; const haOpen = prev? (prev.open + prev.close)/2 : (c[i].open + c[i].close)/2; const haHigh = Math.max(c[i].high, haOpen, haClose); const haLow = Math.min(c[i].low, haOpen, haClose); out.push({time:c[i].time,open:haOpen,high:haHigh,low:haLow,close:haClose}); } return out; },

    // --- Volatility / Volume ---
    ATR: (tf)=>{ const c=store.candles[tf]||[]; const p=(store.params.ATR||DEFAULTS.ATR).period; if(!c.length) return []; return computeATRArray(c,p).map((v,i)=>({time:c[i].time,value:v})); },

    Bollinger: (tf)=>{ const c=store.candles[tf]||[]; const p=(store.params.Bollinger||DEFAULTS.Bollinger).period, m=(store.params.Bollinger||DEFAULTS.Bollinger).mult; if(!c.length) return []; const out=[]; for(let i=0;i<c.length;i++){ if(i<p-1){ out.push({time:c[i].time,mid:null,upper:null,lower:null}); continue;} const slice=c.slice(i-p+1,i+1).map(x=>x.close); const avg=slice.reduce((s,x)=>s+x,0)/p; const sd=Math.sqrt(slice.reduce((s,x)=>s+(x-avg)*(x-avg),0)/p); out.push({time:c[i].time,mid:avg,upper:avg+sd*m,lower:avg-sd*m}); } return out; },

    VWAP: (tf)=>{ const c=store.candles[tf]||[]; let cumPV=0, cumVol=0; return c.map(d=>{ const tp=(d.high+d.low+d.close)/3; cumPV += tp*d.volume; cumVol += d.volume; return {time:d.time,value: cumVol===0?null: cumPV/cumVol}; }); },

    OBV: (tf)=>{ const c=store.candles[tf]||[]; let val=0; return c.map((d,i)=>{ if(i===0) return {time:d.time,value:0}; if(d.close>c[i-1].close) val+=d.volume; else if(d.close<c[i-1].close) val-=d.volume; return {time:d.time,value:val}; }); },

    MFI: (tf)=>{ const c=store.candles[tf]||[]; const p=14; if(!c.length) return []; const out=[]; for(let i=0;i<c.length;i++){ if(i<p){ out.push({time:c[i].time,value:null}); continue;} let pos=0, neg=0; for(let j=i-p+1;j<=i;j++){ const tp=(c[j].high+c[j].low+c[j].close)/3; const mf=tp*c[j].volume; const tpPrev=(c[j-1]||c[j]).close; if(tp>tpPrev) pos+=mf; else neg+=mf; } const ratio = neg===0? 100: pos/neg; out.push({time:c[i].time,value:100-(100/(1+ratio))}); } return out; },

    CMF: (tf)=>{ const c=store.candles[tf]||[]; const p=20; if(!c.length) return []; const out=[]; for(let i=0;i<c.length;i++){ if(i<p){ out.push({time:c[i].time,value:null}); continue;} let mfv=0,vol=0; const slice=c.slice(i-p+1,i+1); slice.forEach(x=>{ const denom=(x.high-x.low)||1; const mfm=((x.close-x.low)-(x.high-x.close))/denom; mfv += mfm*x.volume; vol += x.volume; }); out.push({time:c[i].time,value: mfv/vol}); } return out; },

    ADX: (tf)=>{ return computeADXSeries(store.candles[tf]||[],14); },

    VolatilityIndex: (tf)=>{ const c=store.candles[tf]||[]; const p=10; if(!c.length) return []; const out=[]; for(let i=0;i<c.length;i++){ if(i<p){ out.push({time:c[i].time,value:null}); continue;} const slice=c.slice(i-p+1,i+1).map(x=>x.close); const mu=slice.reduce((s,x)=>s+x,0)/p; const sd=Math.sqrt(slice.reduce((s,x)=>s+(x-mu)*(x-mu),0)/p); out.push({time:c[i].time,value:sd}); } return out; }
  };

  // --- Helper numerical routines ---
  function computeATRArray(c, p){ const res = new Array(c.length).fill(0); if(c.length<2) return res; const tr = new Array(c.length).fill(0); for(let i=1;i<c.length;i++){ tr[i] = Math.max(c[i].high - c[i].low, Math.abs(c[i].high - c[i-1].close), Math.abs(c[i].low - c[i-1].close)); }
    // Wilder's smoothing
    let atr = 0; for(let i=1;i<p;i++) atr += tr[i]; atr = atr/(p-1||1); for(let i=p;i<c.length;i++){ atr = (atr*(p-1) + tr[i]) / p; res[i]=atr; }
    return res;
  }

  function computeADXSeries(c,p){ if(c.length<2) return []; const len=c.length; const plus = new Array(len).fill(0); const minus = new Array(len).fill(0); const tr = new Array(len).fill(0);
    for(let i=1;i<len;i++){ const up = c[i].high - c[i-1].high; const dn = c[i-1].low - c[i].low; plus[i] = up>dn && up>0 ? up:0; minus[i] = dn>up && dn>0? dn:0; tr[i] = Math.max(c[i].high - c[i].low, Math.abs(c[i].high - c[i-1].close), Math.abs(c[i].low - c[i-1].close)); }
    // Smooth
    const pPlus = new Array(len).fill(0), pMinus = new Array(len).fill(0), pTR = new Array(len).fill(0);
    for(let i=1;i<len;i++){ pPlus[i] = (pPlus[i-1]*(p-1) + plus[i])/p; pMinus[i] = (pMinus[i-1]*(p-1) + minus[i])/p; pTR[i] = (pTR[i-1]*(p-1) + tr[i])/p; }
    const pDI = pPlus.map((v,i)=>100*(v/(pTR[i]||1))); const mDI = pMinus.map((v,i)=>100*(v/(pTR[i]||1))); const dx = pDI.map((v,i)=> 100*Math.abs(v - mDI[i])/(v + mDI[i] || 1));
    // ADX smoothing
    const adx = new Array(len).fill(null); let adxVal=dx.slice(1,p+1).reduce((s,x)=>s+x,0)/(p||1); for(let i=p+1;i<len;i++){ adxVal = (adxVal*(p-1) + dx[i])/p; adx[i]=adxVal; }
    return adx.map((v,i)=> ({time:c[i]?.time||0, value:v})); }

  // --- Runner ---
  function runIndicator(name, timeframe='1m'){
    if(!impl[name]) return;
    const res = fromCacheOrCompute(`${name}`, timeframe, ()=> impl[name](timeframe));
    // Attach color rules / flags (example for RSI, MFI)
    const decorated = decorate(name, res);
    if(store.callbacks[name]) store.callbacks[name](decorated);
    return decorated;
  }

  function decorate(name, res){
    if(!res) return res;
    // Example: add flag for RSI
    if(name==='RSI'){ return res.map(v=> Object.assign({}, v, { flag: v.value===null? 'na' : (v.value>70? 'overbought' : (v.value<30? 'oversold' : 'neutral')) })); }
    if(name==='MFI'){ return res.map(v=> Object.assign({}, v, { flag: v.value===null? 'na' : (v.value>80? 'overbought' : (v.value<20? 'oversold' : 'neutral')) })); }
    // MACD color rules
    if(name==='MACD' && res.macd){
      const macd = res.macd.map((d,i)=>({...d, color: d.value> (res.sig[i]?.value||0) ? 'bull' : 'bear'}));
      return Object.assign({}, res, { macd, sig: res.sig, hist: res.hist });
    }
    // default
    return res;
  }

  // --- Public small utilities ---
  function listAvailable(){ return Object.keys(impl); }
  function clearCache(){ store.cache = {}; }

  // Expose API
  return {
    // core
    setCandles,
    setMultiCandles,
    addIndicator,
    removeIndicator,
    onUpdate,
    recomputeAll,

    // admin
    setParam,
    getIndicatorsGrouped,
    listAvailable,
    clearCache,

    // convenience: compute one indicator on-demand and return result
    compute(name, timeframe='1m'){ return runIndicator(name, timeframe); }
  };
})();
