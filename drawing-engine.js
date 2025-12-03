// drawing-engine.js (upgraded)
// Full-featured drawing engine for chart overlay canvas
// Upgrades: complete tool implementations, robust hit-testing, efficient history, non-blocking text entry,
// proper math for rays/extended lines/trendlines, pitchfork, regression-channel, fibonacci extension, eraser.

(function(window){
  const DrawingEngine = (function(){
    // --- internal state ---
    const state = {
      canvas: null,
      ctx: null,
      devicePixelRatio: window.devicePixelRatio || 1,
      width: 0,
      height: 0,
      isPointerDown: false,
      currentTool: 'cursor',
      currentColor: '#ffeb3b',
      currentLineWidth: 1.5,
      currentFill: 'rgba(255,235,59,0.08)',
      currentFont: '12px Inter, sans-serif',
      drawings: [],
      selectedId: null,
      hoverId: null,
      history: [],
      historyIndex: -1,
      historyThrottleMs: 250, // history throttling during drawing
      lastHistoryPush: 0,
      showDrawings: true,
      onChange: null,
      onRequestText: null, // optional non-blocking text callback: (defaultText, callback)
      chartProxy: null,
      nextId: 1
    };

    const TOOLS = [
      'cursor','line','trendline','ray','extended-line','horizontal-line','vertical-line',
      'rectangle','ellipse','polygon','arrow','text','brush','measure','fibonacci-retracement',
      'fibonacci-extension','fibonacci-fan','pitchfork','channel','regression-channel','eraser'
    ];

    // --- util ---
    function uid(){ return 'd'+(state.nextId++); }
    function now(){ return Date.now(); }
    function deepClone(obj){ return JSON.parse(JSON.stringify(obj)); }

    function resizeCanvas(){
      if(!state.canvas) return;
      const rect = state.canvas.getBoundingClientRect();
      state.width = rect.width; state.height = rect.height;
      const dpr = state.devicePixelRatio || 1;
      state.canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      state.canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      state.canvas.style.width = rect.width + 'px';
      state.canvas.style.height = rect.height + 'px';
      state.ctx.setTransform(dpr,0,0,dpr,0,0);
      redraw();
    }

    // Chart proxy helpers (pixel <-> coordinate)
 function pixelToChart(pt){
  if(state.chartProxy && state.chartProxy.pixelToCoordinate) {
    const result = state.chartProxy.pixelToCoordinate(pt);
    // Ensure we always return {x, y} for backward compatibility
    return { 
      x: result.x || pt.x, 
      y: result.y || pt.y,
      time: result.time,
      price: result.price
    };
  }
  return { x: pt.x, y: pt.y };
}

function chartToPixel(coord){
  if(state.chartProxy && state.chartProxy.coordinateToPixel) {
    return state.chartProxy.coordinateToPixel(coord);
  }
  return { x: coord.x, y: coord.y };
}

    // --- primitives ---
    function drawLine(ctx, p1, p2, props){
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.strokeStyle = props.color || state.currentColor;
      ctx.lineWidth = props.lineWidth || state.currentLineWidth;
      ctx.lineCap='round';
      ctx.stroke();
      ctx.restore();
    }

    function drawDashedLine(ctx, p1, p2, props){
      ctx.save();
      ctx.setLineDash(props.dash || [6,6]);
      drawLine(ctx,p1,p2,props);
      ctx.setLineDash([]);
      ctx.restore();
    }

    function drawArrow(ctx, p1, p2, props){
      drawLine(ctx,p1,p2,props);
      const angle = Math.atan2(p2.y-p1.y,p2.x-p1.x);
      const size = Math.max(6, (props.lineWidth||state.currentLineWidth) * 4);
      ctx.save();
      ctx.fillStyle = props.color || state.currentColor;
      ctx.translate(p2.x,p2.y); ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(0,0);
      ctx.lineTo(-size,-size/2);
      ctx.lineTo(-size,size/2);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    function drawRect(ctx, p1, p2, props){
      const x=Math.min(p1.x,p2.x), y=Math.min(p1.y,p2.y), w=Math.abs(p2.x-p1.x), h=Math.abs(p2.y-p1.y);
      ctx.save();
      if(props.fill) { ctx.fillStyle=props.fill; ctx.fillRect(x,y,w,h); }
      ctx.strokeStyle=props.color||state.currentColor;
      ctx.lineWidth=props.lineWidth||state.currentLineWidth;
      ctx.strokeRect(x,y,w,h);
      ctx.restore();
    }

    function drawEllipse(ctx,p1,p2,props){
      const x=(p1.x+p2.x)/2, y=(p1.y+p2.y)/2, rx=Math.abs(p2.x-p1.x)/2, ry=Math.abs(p2.y-p1.y)/2;
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(x,y,Math.max(1,rx),Math.max(1,ry),0,0,Math.PI*2);
      if(props.fill){ ctx.fillStyle=props.fill; ctx.fill(); }
      ctx.strokeStyle=props.color||state.currentColor;
      ctx.lineWidth=props.lineWidth||state.currentLineWidth;
      ctx.stroke();
      ctx.restore();
    }

    function drawPolygon(ctx, points, props){
      if(points.length<2) return;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for(let i=1;i<points.length;i++) ctx.lineTo(points[i].x, points[i].y);
      if(props.closed) ctx.closePath();
      if(props.fill) { ctx.fillStyle=props.fill; ctx.fill(); }
      ctx.strokeStyle=props.color||state.currentColor;
      ctx.lineWidth=props.lineWidth||state.currentLineWidth;
      ctx.stroke();
      ctx.restore();
    }

    function drawText(ctx, pos, text, props){
      ctx.save();
      ctx.font = props.font || state.currentFont;
      ctx.fillStyle = props.color || state.currentColor;
      ctx.textBaseline='top';
      ctx.fillText(text, pos.x + 4, pos.y + 4);
      ctx.restore();
    }

    function drawBrush(ctx, points, props){
      if(points.length<2) return;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for(let i=1;i<points.length;i++) ctx.lineTo(points[i].x, points[i].y);
      ctx.strokeStyle=props.color||state.currentColor;
      ctx.lineWidth=props.lineWidth||state.currentLineWidth;
      ctx.lineCap='round'; ctx.lineJoin='round';
      ctx.stroke();
      ctx.restore();
    }

    // --- geometry helpers ---
    function clamp(v,a,b){ return Math.max(a, Math.min(b, v)); }

    // returns {x,y} for intersection of infinite line through p1-p2 with canvas rectangle edges.
    function lineIntersectCanvas(p1,p2){
      // parametric: p = p1 + t*(p2-p1), find intersections with x=0,x=width,y=0,y=height
      const intersections = [];
      const dx = p2.x - p1.x, dy = p2.y - p1.y;
      const candidates = [];
      if(Math.abs(dx) > 1e-6){
        // t for x=0
        let t = (0 - p1.x) / dx; candidates.push({t, x:0, y: p1.y + t*dy});
        // t for x=width
        t = (state.width - p1.x) / dx; candidates.push({t, x:state.width, y: p1.y + t*dy});
      }
      if(Math.abs(dy) > 1e-6){
        // y=0
        let t = (0 - p1.y) / dy; candidates.push({t, x: p1.x + t*dx, y:0});
        // y=height
        t = (state.height - p1.y) / dy; candidates.push({t, x: p1.x + t*dx, y:state.height});
      }
      // keep points that lie on the canvas rect
      for(const c of candidates){
        if(c.x >= -1e-6 && c.x <= state.width + 1e-6 && c.y >= -1e-6 && c.y <= state.height + 1e-6) intersections.push({x:c.x, y:c.y, t:c.t});
      }
      // unique by position
      const uniq = [];
      const seen = new Set();
      for(const p of intersections){
        const key = `${Math.round(p.x)}:${Math.round(p.y)}`;
        if(!seen.has(key)){ seen.add(key); uniq.push(p); }
      }
      // sort by t and return first two extremes
      uniq.sort((a,b)=>a.t - b.t);
      if(uniq.length===0) return null;
      if(uniq.length===1) return {a:uniq[0], b:uniq[0]};
      return {a:uniq[0], b:uniq[uniq.length-1]};
    }

    function distancePointToSegment(p, v, w){
      const l2 = (v.x-w.x)*(v.x-w.x)+(v.y-w.y)*(v.y-w.y);
      if(l2===0) return Math.hypot(p.x-v.x,p.y-v.y);
      let t = ((p.x - v.x)*(w.x - v.x) + (p.y - v.y)*(w.y - v.y)) / l2;
      t = Math.max(0, Math.min(1,t));
      const proj = { x: v.x + t*(w.x-v.x), y: v.y + t*(w.y-v.y) };
      return Math.hypot(p.x-proj.x, p.y-proj.y);
    }

    function distancePointToLineInfinite(p, v, w){
      // distance to infinite line through v-w
      const A = w.y - v.y, B = v.x - w.x, C = w.x*v.y - v.x*w.y;
      return Math.abs(A*p.x + B*p.y + C) / Math.hypot(A,B);
    }

    function pointInPolygon(point, vs) {
      // ray-casting algorithm for point in polygon
      let x = point.x, y = point.y;
      let inside = false;
      for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
        let xi = vs[i].x, yi = vs[i].y;
        let xj = vs[j].x, yj = vs[j].y;
        let intersect = ((yi > y) !== (yj > y)) &&
            (x < (xj - xi) * (y - yi) / (yj - yi + 0.0) + xi);
        if (intersect) inside = !inside;
      }
      return inside;
    }

    // brush stroke proximity (distance to any segment)
    function distancePointToPolyline(p, pts){
      let minD = Infinity;
      for(let i=0;i<pts.length-1;i++){
        const d = distancePointToSegment(p, pts[i], pts[i+1]);
        if(d<minD) minD=d;
      }
      return minD;
    }

    // --- hit-tests ---
    function hitTest(shape, pt){
      if(!shape || !shape.points) return false;
      const p = pt;
      const props = shape.props||{};
      const tolerance = Math.max(6, props.lineWidth || state.currentLineWidth) + 2;

      switch(shape.type){
        case 'rectangle': {
          const p1=shape.points[0], p2=shape.points[1];
          const x1=Math.min(p1.x,p2.x), x2=Math.max(p1.x,p2.x), y1=Math.min(p1.y,p2.y), y2=Math.max(p1.y,p2.y);
          return p.x>=x1 && p.x<=x2 && p.y>=y1 && p.y<=y2;
        }
        case 'ellipse': {
          const p1=shape.points[0], p2=shape.points[1];
          const cx=(p1.x+p2.x)/2, cy=(p1.y+p2.y)/2, rx=Math.abs(p2.x-p1.x)/2, ry=Math.abs(p2.y-p1.y)/2;
          if(rx===0||ry===0) return false;
          const nx=(p.x-cx)/rx, ny=(p.y-cy)/ry;
          return nx*nx+ny*ny <= 1.05;
        }
        case 'polygon': {
          // if closed, use point-in-polygon; otherwise bounding box
          if(shape.props && shape.props.closed) return pointInPolygon(p, shape.points);
          const xs = shape.points.map(x=>x.x), ys=shape.points.map(x=>x.y);
          const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
          return p.x>=xmin && p.x<=xmax && p.y>=ymin && p.y<=ymax;
        }
        case 'brush': {
          const d = distancePointToPolyline(p, shape.points);
          return d <= tolerance;
        }
        case 'text': {
          const p1=shape.points[0];
          // approximate bounding box for text
          return Math.abs(p.x-p1.x) < 120 && Math.abs(p.y-p1.y) < 48;
        }
        case 'measure': {
          const a=shape.points[0], b=shape.points[1];
          return distancePointToSegment(p,a,b) <= tolerance;
        }
        case 'fibonacci-retracement':
        case 'fibonacci-fan':
        case 'fibonacci-extension': {
          // treat as line-family - if any line is close
          // approximate by checking distance to main two-point lines
          if(shape.points.length>=2){
            const a=shape.points[0], b=shape.points[1];
            return distancePointToSegment(p,a,b) <= tolerance;
          }
          return false;
        }
        case 'ray': {
          const a=shape.points[0], b=shape.points[1];
          // distance to infinite ray starting at a toward b but not behind a.
          const projT = projectionParameterOnLine(a,b,p);
          if(projT < -1e-6) return false;
          // compute closest point on infinite line and check
          const d = distancePointToLineInfinite(p,a,b);
          return d <= tolerance;
        }
        case 'extended-line':
        case 'trendline':
        case 'line':
        case 'arrow':
        case 'horizontal-line':
        case 'vertical-line':
        case 'channel':
        case 'regression-channel':
        case 'pitchfork': {
          // lines and line-like shapes: check distance to main segments or infinite lines as appropriate
          if(['horizontal-line','vertical-line'].includes(shape.type)){
            const p1 = shape.points[0];
            if(shape.type==='horizontal-line') return Math.abs(p.y - p1.y) <= tolerance;
            return Math.abs(p.x - p1.x) <= tolerance;
          }
          if(shape.points.length>=2){
            // if tool is 'trendline' or 'extended-line' treat as infinite -> use distance to infinite line
            if(['trendline','extended-line'].includes(shape.type)){
              const d = distancePointToLineInfinite(p, shape.points[0], shape.points[1]);
              return d <= tolerance;
            }
            // otherwise segment
            const d = distancePointToSegment(p, shape.points[0], shape.points[1]);
            return d <= tolerance;
          }
          return false;
        }
        default:
          return false;
      }
    }

    function projectionParameterOnLine(a,b,p){
      const dx=b.x-a.x, dy=b.y-a.y;
      const l2 = dx*dx + dy*dy;
      if(l2===0) return 0;
      return ((p.x-a.x)*dx + (p.y-a.y)*dy) / l2;
    }

    // --- core actions ---
    function addDrawing(d, push=true){
      state.drawings.push(d);
      if(push) pushHistoryThrottled();
      emitChange();
    }
    function updateDrawing(id, patch, push=true){
      const i = state.drawings.findIndex(x=>x.id===id); if(i===-1) return;
      state.drawings[i] = Object.assign({}, state.drawings[i], patch);
      if(push) pushHistoryThrottled();
    }
    function removeDrawing(id){
      state.drawings = state.drawings.filter(x=>x.id!==id);
      if(state.selectedId===id) state.selectedId=null;
      pushHistoryImmediate();
      emitChange();
    }

    // --- improved history: push at pointerUp or throttled during drawing ---
    function pushHistoryImmediate(){
      const snapshot = deepClone(state.drawings);
      state.historyIndex++;
      state.history.splice(state.historyIndex);
      state.history.push(snapshot);
      if(state.history.length>200) state.history.shift();
      if(state.historyIndex>=state.history.length) state.historyIndex = state.history.length-1;
      state.lastHistoryPush = now();
    }

    function pushHistoryThrottled(){
      const t = now();
      if(t - state.lastHistoryPush > state.historyThrottleMs){
        pushHistoryImmediate();
      }
      // else skip — final snapshot will be done on pointerUp
    }

    function undo(){ if(state.historyIndex>0){ state.historyIndex--; state.drawings = deepClone(state.history[state.historyIndex]); redraw(); emitChange(); }}
    function redo(){ if(state.historyIndex < state.history.length-1){ state.historyIndex++; state.drawings = deepClone(state.history[state.historyIndex]); redraw(); emitChange(); }}

    function clearAll(){ state.drawings=[]; pushHistoryImmediate(); redraw(); emitChange(); }
    function toggleVisibility(){ state.showDrawings = !state.showDrawings; redraw(); }

    function exportJSON(){ return JSON.stringify({ drawings: state.drawings, meta:{ exported: now() } }); }
    function importJSON(json){ try{ const obj = typeof json==='string'? JSON.parse(json):json; state.drawings = obj.drawings||[]; pushHistoryImmediate(); redraw(); emitChange(); }catch(e){ console.error('import failed',e); }}

    function exportPNG(){ return state.canvas.toDataURL('image/png'); }

    // --- pointer interactions ---
    function onPointerDown(e){
      state.isPointerDown = true;
      const pt = transformEvent(e);
      if(state.currentTool==='cursor'){
        // select or begin dragging
        const hit = hitUnderPoint(pt);
        state.selectedId = hit? hit.id : null;
        redraw();
        return;
      }

      if(state.currentTool==='eraser'){
        // immediate erase any drawing under point
        const hit = hitUnderPoint(pt);
        if(hit) removeDrawing(hit.id);
        // also set selectedId to null so we can drag erase
        state.selectedId = null;
        return;
      }

      // create new drawing template
      const id = uid();
      const base = {
        id, type: state.currentTool, points: [pt],
        props: { color: state.currentColor, lineWidth: state.currentLineWidth, fill: state.currentFill, font: state.currentFont },
        meta:{ created: now() }
      };

      // special tools
      if(state.currentTool === 'text'){
        base.text = 'Text';
        base.points = [pt];
        addDrawing(base, true);
        state.selectedId = id;
        redraw();
        promptForText(id);
        return;
      }

      if(state.currentTool === 'brush'){
        base.points = [pt];
        addDrawing(base, true);
        state.selectedId = id;
        redraw();
        return;
      }

      // polygon: if user clicks near first point to close -> close polygon
      if(state.currentTool === 'polygon'){
        // start new polygon if none in progress
        base.props.closed = false;
        addDrawing(base, true);
        state.selectedId = id;
        redraw();
        return;
      }

      addDrawing(base, true);
      state.selectedId = id;
      redraw();
    }

    function onPointerMove(e){
      const pt = transformEvent(e);
      if(!state.isPointerDown){
        // hover detection
        const hit = hitUnderPoint(pt);
        state.hoverId = hit? hit.id : null;
        redraw();
        return;
      }

      // pointer is down: drawing or dragging
      // Eraser drag: remove shapes under pointer as we go
      if(state.currentTool === 'eraser'){
        const hit = hitUnderPoint(pt);
        if(hit) removeDrawing(hit.id);
        redraw();
        return;
      }

      const d = state.drawings.find(x=>x.id===state.selectedId);
      if(!d) return;

      // brush append point
      if(state.currentTool === 'brush'){
        d.points.push(pt);
        updateDrawing(d.id, { points: d.points }, false);
        redraw();
        return;
      }

      // polygon: append points as pointer moves only when pointer was clicked again (we use pointer events, so we append on pointerup)
      // For line-like tools, ensure second point exists (live preview)
      if(d.points.length===1) d.points.push(pt); else d.points[d.points.length-1] = pt;
      updateDrawing(d.id, { points: d.points }, false);
      redraw();
    }

    function onPointerUp(e){
      if(!state.isPointerDown) return;
      state.isPointerDown = false;
      const pt = transformEvent(e);

      // finalize
      const d = state.drawings.find(x=>x.id===state.selectedId);

      // polygon special behavior: if pointer up near first point and >=3 points -> close polygon
      if(d && d.type === 'polygon'){
        const pts = d.points;
        if(pts.length >= 3){
          const first = pts[0];
          const last = pts[pts.length-1];
          const dist = Math.hypot(last.x-first.x, last.y-first.y);
          if(dist <= 10){
            // close polygon
            d.points = pts.slice(0, pts.length-1); // remove last noisy point
            d.props = Object.assign({}, d.props, { closed: true, fill: d.props.fill || state.currentFill });
            updateDrawing(d.id, d, true);
            state.selectedId = d.id;
            redraw();
            emitChange();
            return;
          }
        }
        // otherwise keep as in-progress polygon (add final point)
        // Note: for an interactive polygon, you might want a separate "complete polygon" button;
        // auto-close logic tries to be helpful
      }

      if(d){
        if(d.points.length===1 && d.type!=='text' && d.type!=='brush') d.points.push(pt);
        updateDrawing(d.id, d, true);
      }

      // push final history snapshot
      pushHistoryImmediate();
      emitChange();
      redraw();
    }

    function transformEvent(e){
      const rect = state.canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left);
      const y = (e.clientY - rect.top);
      return { x, y, chart: pixelToChart({x,y}) };
    }

    function hitUnderPoint(pt){
      for(let i=state.drawings.length-1;i>=0;i--){
        const s = state.drawings[i];
        if(hitTest(s,pt)) return s;
      }
      return null;
    }

    // --- rendering pipeline ---
    function redraw(){
      if(!state.ctx) return;
      const ctx = state.ctx;
      ctx.clearRect(0,0,state.width,state.height);
      if(!state.showDrawings) return;

      for(const shape of state.drawings){
        const props = shape.props || {};
        try {
          switch(shape.type){
            case 'line': if(shape.points.length>=2) drawLine(ctx, shape.points[0], shape.points[1], props); break;
            case 'trendline': if(shape.points.length>=2){
              // extend both ways across canvas as dashed line
              const ext = lineIntersectCanvas(shape.points[0], shape.points[1]);
              if(ext) drawDashedLine(ctx, ext.a, ext.b, props);
            } break;
            case 'ray': if(shape.points.length>=2){
              // ray from p0 through p1 to canvas edge
              const a = shape.points[0], b = shape.points[1];
              const ext = lineIntersectCanvas(a, b);
              if(ext){
                // choose intersection that is in direction of (b-a)
                const tA = ext.a.t, tB = ext.b.t;
                const dirT = projectionParameterOnLine(a,b, ext.b) - projectionParameterOnLine(a,b, ext.a);
                // pick the far intersection that's in forward direction
                const forward = (Math.abs(tB) > Math.abs(tA)) ? ext.b : ext.a;
                // compute forward intersection relative to start
                const f = (Math.abs(ext.a.t - 0) > Math.abs(ext.b.t - 0)) ? ext.a : ext.b;
                // but better: find the intersection with t >= 0 (parametric t from a)
                let ia = ext.a, ib = ext.b;
                let pA = ia.t, pB = ib.t;
                // convert to param t relative to original paramization used earlier: note earlier we used p = p1 + t*(p2-p1)
                // pick the one with t >= 0
                let chosen = null;
                if(ia.t >= 0 && ib.t >= 0) chosen = (ia.t < ib.t ? ia : ib);
                else if(ia.t >= 0) chosen = ia;
                else if(ib.t >= 0) chosen = ib;
                else chosen = (ia.t > ib.t ? ia : ib);
                drawLine(ctx, a, {x: chosen.x, y: chosen.y}, props);
              } else {
                // fallback: draw segment
                drawLine(ctx, a, b, props);
              }
            } break;
            case 'extended-line': if(shape.points.length>=2){
              const ext = lineIntersectCanvas(shape.points[0], shape.points[1]);
              if(ext) drawLine(ctx, ext.a, ext.b, props);
            } break;
            case 'horizontal-line': if(shape.points.length>=1){ const p=shape.points[0]; drawLine(ctx,{x:0,y:p.y},{x:state.width,y:p.y},props); } break;
            case 'vertical-line': if(shape.points.length>=1){ const p=shape.points[0]; drawLine(ctx,{x:p.x,y:0},{x:p.x,y:state.height},props); } break;
            case 'rectangle': if(shape.points.length>=2) drawRect(ctx, shape.points[0], shape.points[1], props); break;
            case 'ellipse': if(shape.points.length>=2) drawEllipse(ctx, shape.points[0], shape.points[1], props); break;
            case 'polygon': if(shape.points.length>=2) drawPolygon(ctx, shape.points, props); break;
            case 'arrow': if(shape.points.length>=2) drawArrow(ctx, shape.points[0], shape.points[1], props); break;
            case 'text': if(shape.points.length>=1) drawText(ctx, shape.points[0], shape.text||'Text', props); break;
            case 'brush': if(shape.points.length>=2) drawBrush(ctx, shape.points, props); break;
            case 'measure': if(shape.points.length>=2){ drawLine(ctx,shape.points[0],shape.points[1],props); drawMeasureLabel(ctx,shape.points[0],shape.points[1],props); } break;
            case 'fibonacci-retracement': if(shape.points.length>=2) drawFiboRetracement(ctx, shape.points[0], shape.points[1], props); break;
            case 'fibonacci-extension': if(shape.points.length>=3) drawFiboExtension(ctx, shape.points[0], shape.points[1], shape.points[2], props); break;
            case 'fibonacci-fan': if(shape.points.length>=2) drawFiboFan(ctx, shape.points[0], shape.points[1], props); break;
            case 'pitchfork': if(shape.points.length>=3) drawPitchfork(ctx, shape.points, props); break;
            case 'channel': if(shape.points.length>=2) drawChannel(ctx, shape.points[0], shape.points[1], props); break;
            case 'regression-channel': if(shape.points.length>=2) drawRegressionChannel(ctx, shape.points, props); break;
            case 'eraser': /* nothing to draw for eraser cursor */ break;
            default: if(shape.points.length>=2) drawLine(ctx,shape.points[0],shape.points[1],props);
          }

          if(state.selectedId === shape.id) drawSelectionHandles(ctx, shape);
        } catch(err){
          // never break drawing loop
          console.error('draw error', err, shape && shape.type);
        }
      }

      // hover highlight
      if(state.hoverId && state.hoverId !== state.selectedId){
        const hover = state.drawings.find(x=>x.id===state.hoverId);
        if(hover) drawHoverOutline(ctx, hover);
      }
    }

    function drawSelectionHandles(ctx, shape){
      ctx.save();
      ctx.strokeStyle='#38bdf8'; ctx.fillStyle='#38bdf8'; ctx.lineWidth=1;
      if(shape.points) shape.points.forEach(p=>{ ctx.beginPath(); ctx.arc(p.x,p.y,5,0,Math.PI*2); ctx.fill(); ctx.stroke(); });
      ctx.restore();
    }

    function drawHoverOutline(ctx, shape){
      ctx.save();
      ctx.strokeStyle='rgba(255,255,255,0.15)'; ctx.lineWidth=2;
      if(shape.points.length>=2){
        drawLine(ctx, shape.points[0], shape.points[shape.points.length-1], { color: 'rgba(255,255,255,0.15)', lineWidth: 2 });
      }
      ctx.restore();
    }

    function drawMeasureLabel(ctx,p1,p2,props){
      const dx = p2.x - p1.x; const dy = p2.y - p1.y;
      const dist = Math.hypot(dx,dy).toFixed(1);
      const mid = {x:(p1.x+p2.x)/2,y:(p1.y+p2.y)/2};
      drawText(ctx, mid, dist+' px', props);
    }

    // --- fibo / pitchfork / channel / regression implementations ---

    function drawFiboRetracement(ctx, pTop, pBottom, props){
      // levels in pixel space between pTop and pBottom
      const levels=[0,0.236,0.382,0.5,0.618,0.786,1];
      const top = pTop, bottom = pBottom;
      const left = 0, right = state.width;
      for(const l of levels){
        const y = top.y + (bottom.y - top.y) * l;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.strokeStyle = props.color || 'rgba(255,165,0,0.9)';
        ctx.lineWidth = Math.max(1, (props.lineWidth||1));
        ctx.setLineDash(props.dash || []);
        ctx.stroke();
        ctx.restore();
        drawText(ctx, {x: right - 48, y: y - 10}, `${(l*100).toFixed(1)}%`, props);
      }
    }

    function drawFiboExtension(ctx, a, b, c, props){
      // A -> B -> C, extend beyond C with common extension ratios
      const ratios = [1.0, 1.272, 1.618, 2.0];
      // project along the vector from A->B, B->C etc by using vertical mapping in pixel space
      // We'll compute extension on line from A->B extrapolated from C
      const dx = b.x - a.x, dy = b.y - a.y;
      const lengthAB = Math.hypot(dx,dy);
      if(lengthAB < 1e-6) return;
      const ux = dx / lengthAB, uy = dy / lengthAB;
      // distance BC used to scale?
      const distBC = Math.hypot(c.x - b.x, c.y - b.y);
      for(const r of ratios){
        const ex = c.x + ux * distBC * (r);
        const ey = c.y + uy * distBC * (r);
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(c.x, c.y);
        ctx.lineTo(ex, ey);
        ctx.strokeStyle = props.color || '#ffa';
        ctx.lineWidth = Math.max(1, props.lineWidth || 1);
        ctx.setLineDash(props.dash || [5,4]);
        ctx.stroke();
        ctx.restore();
        drawText(ctx, {x: ex + 4, y: ey - 8}, `EXT ${r}`, props);
      }
    }

    function drawFiboFan(ctx, p1, p2, props){
      // draw fan lines from p1 to multiple points along p2 line
      const levels=[0.382,0.5,0.618];
      for(const l of levels){
        const x = p1.x + (p2.x - p1.x) * l;
        const y = p1.y + (p2.y - p1.y) * l;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(x, state.height);
        ctx.strokeStyle = props.color || '#ffa500';
        ctx.lineWidth = Math.max(1, props.lineWidth || 1);
        ctx.stroke();
        ctx.restore();
      }
    }

    function drawPitchfork(ctx, pts, props){
      // Andrews Pitchfork: pts[0] = A (left), pts[1] = B (mid), pts[2] = C (right)
      const [p1,p2,p3] = pts;
      // median line from p1 through midpoint of p2-p3
      const mid23 = { x: (p2.x + p3.x)/2, y: (p2.y + p3.y)/2 };
      // extend median across canvas
      const medianExt = lineIntersectCanvas(p1, mid23);
      if(medianExt) drawLine(ctx, medianExt.a, medianExt.b, props);
      // parallels: line through p2->p3 as base, draw line parallel to it through p1 and mid23? We'll draw lines:
      drawLine(ctx, p2, p3, props);
      // draw lines from p1 to p2 and p3 (handles)
      drawLine(ctx, p1, p2, props);
      drawLine(ctx, p1, p3, props);
    }

    function drawChannel(ctx, p1, p2, props){
      // draw base line
      drawLine(ctx, p1, p2, props);
      // offset perpendicular by a distance proportional to line width or provided offset
      const dx = p2.x - p1.x, dy = p2.y - p1.y;
      const len = Math.hypot(dx,dy); if(len<1e-6) return;
      const nx = -(dy/len), ny = (dx/len);
      const offset = (props.offset !== undefined) ? props.offset : 20; // px
      const a2 = { x: p1.x + nx*offset, y: p1.y + ny*offset };
      const b2 = { x: p2.x + nx*offset, y: p2.y + ny*offset };
      drawLine(ctx, a2, b2, props);
    }

    function drawRegressionChannel(ctx, pts, props){
      // Simple linear regression on points array (we expect points[0]..points[n] where x is x pixel, y is y pixel)
      // Use first two points if only two provided to draw regression based on those two.
      // If user supplies many points (e.g., brush of samples), we'll compute regression from those
      let pointsForRegression = [];
      if(pts.points && Array.isArray(pts.points)) pointsForRegression = pts.points; // if drawing passed whole object
      else if(Array.isArray(pts)) pointsForRegression = pts;
      if(pointsForRegression.length < 2) return;
      // compute linear regression y = a + b*x
      const n = pointsForRegression.length;
      let sumX=0, sumY=0, sumXY=0, sumXX=0;
      for(const p of pointsForRegression){ sumX += p.x; sumY += p.y; sumXY += p.x*p.y; sumXX += p.x*p.x; }
      const denom = (n*sumXX - sumX*sumX);
      let b = 0, a = 0;
      if(Math.abs(denom) > 1e-8){
        b = (n*sumXY - sumX*sumY) / denom;
        a = (sumY - b*sumX) / n;
      } else {
        // vertical-ish: fallback to two-point line
        const p1 = pointsForRegression[0], p2 = pointsForRegression[pointsForRegression.length-1];
        b = (p2.y - p1.y) / (p2.x - p1.x + 1e-9);
        a = p1.y - b * p1.x;
      }
      // compute residuals stddev
      let sumRes = 0;
      for(const p of pointsForRegression){ const pred = a + b*p.x; const r = p.y - pred; sumRes += r*r; }
      const variance = sumRes / Math.max(1, n-1);
      const sigma = Math.sqrt(variance);

      // find x-range across canvas for drawing
      const leftX = 0, rightX = state.width;
      const leftY = a + b*leftX;
      const rightY = a + b*rightX;
      drawLine(ctx, {x:leftX, y:leftY}, {x:rightX, y:rightY}, props);

      // upper channel (pred - sigma) and lower channel (pred + sigma)
      drawLine(ctx, {x:leftX, y:leftY - sigma}, {x:rightX, y:rightY - sigma}, props);
      drawLine(ctx, {x:leftX, y:leftY + sigma}, {x:rightX, y:rightY + sigma}, props);
    }

    // --- keyboard ---
    function onKeyDown(e){
      if(e.ctrlKey && (e.key==='z' || (e.key==='Z' && e.metaKey===false))){ undo(); e.preventDefault(); }
      else if(e.ctrlKey && (e.key==='y' || (e.key==='Y' && e.metaKey===false))){ redo(); e.preventDefault(); }
      else if(e.key==='Delete' || e.key==='Backspace'){ if(state.selectedId) removeDrawing(state.selectedId); }
    }

    // --- public API ---
 function init(canvasEl, options={}){
  state.canvas = canvasEl;
  state.ctx = canvasEl.getContext('2d');
  state.currentTool = options.defaultTool || 'cursor';
  state.currentColor = options.color || state.currentColor;
  state.currentLineWidth = options.lineWidth || state.currentLineWidth;
  state.currentFill = options.fill || state.currentFill;
  state.devicePixelRatio = options.devicePixelRatio || window.devicePixelRatio || 1;
  state.chartProxy = options.chartProxy || null;
  state.onChange = options.onChange || null;
  state.onRequestText = options.onRequestText || null;
  state.historyThrottleMs = options.historyThrottleMs || state.historyThrottleMs;
  
  // Store chart reference if provided
  state.chart = options.chart || null;
  state.priceScale = options.priceScale || null;
  state.timeScale = options.timeScale || null;

  // If chartProxy wasn't provided, create one automatically
  if (!state.chartProxy && state.chart) {
    state.chartProxy = createLightweightChartsProxy(state.chart);
  }

  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  canvasEl.addEventListener('pointerdown', onPointerDown);
  canvasEl.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('keydown', onKeyDown);

  // initial history
  pushHistoryImmediate();
}

    function setTool(name){ if(!TOOLS.includes(name)) console.warn('Unknown tool',name); state.currentTool = name; }
    function getTool(){ return state.currentTool; }
    function setColor(c){ state.currentColor = c; }
    function setLineWidth(w){ state.currentLineWidth = w; }
    function setFill(f){ state.currentFill = f; }
    function setFont(f){ state.currentFont = f; }
    function setChartProxy(proxy){ state.chartProxy = proxy; }
    function getDrawings(){ return deepClone(state.drawings); }
    function setDrawings(arr){ state.drawings = deepClone(arr); pushHistoryImmediate(); redraw(); emitChange(); }

    function promptForText(id){
      // non-blocking: use onRequestText callback if provided (signature: (defaultText, cb) => void)
      if(typeof state.onRequestText === 'function'){
        state.onRequestText('Text', function(txt){
          if(txt !== null && typeof txt !== 'undefined'){
            const d = state.drawings.find(x=>x.id===id);
            if(d){ d.text = txt; updateDrawing(id, d, true); redraw(); }
          }
        });
        return;
      }
      // fallback - blocking prompt
      const txt = window.prompt('Enter text:','Label');
      if(txt !== null){
        const d = state.drawings.find(x=>x.id===id);
        if(d){ d.text = txt; updateDrawing(id,d,true); redraw(); }
      }
    }

    function emitChange(){ if(typeof state.onChange === 'function') state.onChange({ drawings: getDrawings() }); }

    // chart integration
    function createChartProxy(chartApi){
      if(!chartApi) return null;
      const proxy = {
        pixelToCoordinate(pt){
          if(chartApi.coordinateToTime && chartApi.coordinateToPrice){
            // convert pixel to time/price
            return { time: chartApi.coordinateToTime(pt.x), price: chartApi.coordinateToPrice(pt.y) };
          }
          return { x: pt.x, y: pt.y };
        },
        coordinateToPixel(coord){
          if(chartApi.timeToCoordinate && chartApi.priceToCoordinate){
            return { x: chartApi.timeToCoordinate(coord.time), y: chartApi.priceToCoordinate(coord.price) };
          }
          return { x: coord.x, y: coord.y };
        }
      };
      setChartProxy(proxy);
      return proxy;
    }

    function importFromChart(drawingsInChartCoords){
      const pixelized = drawingsInChartCoords.map(d=>{
        const pts = d.points.map(p => chartToPixel({time:p.time, price:p.price}));
        return Object.assign({}, d, { points: pts });
      });
      setDrawings(pixelized);
    }
	
function createLightweightChartsProxy(chart) {
  // Get the main series from the chart (assuming it's the first series)
  const series = chart.series && chart.series.length > 0 ? chart.series[0] : null;
  
  return {
    pixelToCoordinate: (pt) => {
      try {
        if (chart && chart.timeScale && series && series.priceScale) {
          // Convert pixel to chart coordinates
          const time = chart.timeScale().coordinateToTime(pt.x);
          const price = series.priceScale().coordinateToPrice(pt.y);
          
          // Handle edge cases where coordinates might be null
          if (time === null || price === null) {
            return { x: pt.x, y: pt.y, time: null, price: null };
          }
          
          return { time, price, x: pt.x, y: pt.y };
        }
      } catch (err) {
        console.warn("pixelToCoordinate failed:", err);
      }
      
      // Fallback: normalized coordinates (0-1 range)
      const rect = state.canvas.getBoundingClientRect();
      return {
        x: pt.x,
        y: pt.y,
        time: (pt.x - rect.left) / rect.width,
        price: (pt.y - rect.top) / rect.height
      };
    },

    coordinateToPixel: (coord) => {
      try {
        if (chart && chart.timeScale && series && series.priceScale) {
          // Check if we have time/price coordinates
          if (coord.time !== undefined && coord.price !== undefined) {
            const x = chart.timeScale().timeToCoordinate(coord.time);
            const y = series.priceScale().priceToCoordinate(coord.price);
            
            // Handle edge cases where coordinates might be null
            if (x === null || y === null) {
              return { x: coord.x || 0, y: coord.y || 0 };
            }
            
            return { x, y };
          }
        }
      } catch (err) {
        console.warn("coordinateToPixel failed:", err);
      }
      
      // Fallback: use normalized coordinates
      const rect = state.canvas.getBoundingClientRect();
      return {
        x: (coord.x || 0) * rect.width + rect.left,
        y: (coord.y || 0) * rect.height + rect.top
      };
    }
  };
}

    return {
      init,
      setTool, getTool, TOOLS,
      setColor, setLineWidth, setFill, setFont,
      addDrawing, updateDrawing, removeDrawing,
      undo, redo, clearAll, toggleVisibility,
      exportJSON, importJSON, exportPNG,
      getDrawings, setDrawings,
      createChartProxy, setChartProxy,
      onChange: (fn)=> state.onChange = fn,
      // advanced hooks
      setOnRequestText: (fn) => state.onRequestText = fn
    };
  })();

  window.DrawingEngine = DrawingEngine;
})(window);
