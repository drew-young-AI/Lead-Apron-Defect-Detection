/* tools.js
 * Tool strategy objects.  Each implements: onDown, onMove, onUp, draw(ctx, scale).
 */

// ── BoxTool ────────────────────────────────────────────────────────────────
class BoxTool {
  constructor(viewer, onComplete) {
    this.v          = viewer;
    this.onComplete = onComplete;
    this._drawing   = false;
    this._sx = this._sy = this._ex = this._ey = 0;
    /** Last successfully completed bbox (image coords) – read by App. */
    this.lastBbox = null;
  }

  onDown(e, sx, sy, ip) {
    if (e.button !== 0) return;
    this._drawing = true;
    this._sx = this._ex = ip.x;
    this._sy = this._ey = ip.y;
  }

  onMove(e, sx, sy, ip) {
    if (!this._drawing) return;
    this._ex = ip.x;
    this._ey = ip.y;
  }

  onUp(e, sx, sy, ip) {
    if (!this._drawing) return;
    this._drawing = false;

    const x = Math.round(Math.min(this._sx, ip.x));
    const y = Math.round(Math.min(this._sy, ip.y));
    const w = Math.round(Math.abs(ip.x - this._sx));
    const h = Math.round(Math.abs(ip.y - this._sy));

    // Reset drawing state BEFORE calling onComplete so lastBbox is ready
    this._sx = this._sy = this._ex = this._ey = 0;

    if (w >= 4 && h >= 4) {
      this.lastBbox = { x, y, w, h };           // ← stored reliably
      this.onComplete({ x, y, w, h });
    }
  }

  draw(ctx, scale) {
    if (!this._drawing) return;
    const x = Math.min(this._sx, this._ex);
    const y = Math.min(this._sy, this._ey);
    const w = Math.abs(this._ex - this._sx);
    const h = Math.abs(this._ey - this._sy);
    if (w < 1 || h < 1) return;

    const lw = 1.5 / scale;
    ctx.setLineDash([6/scale, 3/scale]);
    ctx.strokeStyle = '#00e676'; ctx.lineWidth = lw;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = 'rgba(0,230,118,.07)';
    ctx.fillRect(x, y, w, h);
    ctx.setLineDash([]);

    // Dimension label
    const fs = 12 / scale;
    ctx.font = `bold ${fs}px monospace`;
    ctx.fillStyle = '#00e676';
    const label = `${Math.round(w)} × ${Math.round(h)}`;
    ctx.fillText(label, x + 3/scale, y - 4/scale);
  }
}

// ── BrushTool ──────────────────────────────────────────────────────────────
class BrushTool {
  constructor(viewer) {
    this.v      = viewer;
    this._down  = false;
    this.radius = 20;   // in image pixels
    this.mode   = 'fg'; // 'fg' | 'bg' | 'erase'
  }

  onDown(e, sx, sy, ip) {
    try { console.debug('[BrushTool.onDown]', { button: e.button, ip: ip }); } catch(e){}
    if (e.button !== 0) return;
    this._down = true;
    this._paint(ip);
  }
  onMove(e, sx, sy, ip) { if (this._down) { try { console.debug('[BrushTool.onMove]', ip); } catch(e){}; this._paint(ip); } }
  onUp() {
    try { console.debug('[BrushTool.onUp]'); } catch(e){}
    this._down = false;
    // If App hasn't attached brushDoneHandler (enterMarkMode not used), trigger segmentation directly when in marking
    try {
      if (window._app && window._app.marking) {
        if (!window._app._brushDoneHandler) {
          // no handler attached -> call onBrushComplete flow with short debounce
          clearTimeout(window._app._brushTimer);
          window._app._brushTimer = setTimeout(()=>{ try{ window._app._onBrushComplete(); } catch(e){} }, 200);
        }
      }
    } catch(e){}
  }
  draw()                 { /* cursor handled via CSS */ }

  _paint(ip) {
    // Radius in image pixels should scale down when we zoom in, so it's a fixed size on screen
    try { console.debug('[BrushTool._paint]', ip); } catch(e){}
    const effectiveRadius = this.radius / this.v.scale;
    this.v.paintBrush(ip.x, ip.y, effectiveRadius, this.mode);
  }
}

// ── PanTool ────────────────────────────────────────────────────────────────
class PanTool {
  onDown() {} onMove() {} onUp() {} draw() {}
}

// ── PolygonEditTool ────────────────────────────────────────────────────────
class PolygonEditTool {
  constructor(viewer, onChanged) {
    this.v         = viewer;
    this.onChanged = onChanged;
    this._drag     = null;   // { ann, vi }
    this._moved    = false;
  }

  onDown(e, sx, sy, ip) {
    if (e.button !== 0) return;
    try { console.debug('[PolygonEditTool.onDown]', { button: e.button, ip }); } catch(e){}

    // 1. Try to drag an existing vertex
    const vhit = this.v.findNearVertex(ip.x, ip.y);
    if (vhit) {
      try { console.debug('[PolygonEditTool] vertex hit', vhit); } catch(e){}
      this._drag  = vhit;  // { ann, vi }
      this._moved = false;
      return;
    }

    // 2. Try to insert vertex on a polygon edge
    const edgeHit = this._findEdge(ip.x, ip.y);
    if (edgeHit) {
      try { console.debug('[PolygonEditTool] edge hit, inserting'); } catch(e){}
      const idx = this._edgeInsertIdx(edgeHit, ip.x, ip.y);
      edgeHit.polygon.splice(idx, 0, [Math.round(ip.x), Math.round(ip.y)]);
      this.onChanged(edgeHit);
      return;
    }

    // 3. Click inside an annotation → start MOVE (drag whole ann)
    const ann = this.v.hitTest(ip.x, ip.y);
    if (ann) {
      try { console.debug('[PolygonEditTool] ann hit, start move', { id: ann.id }); } catch(e){}
      // Start move drag: store starting point and a copy of original coords
      this._drag = {
        ann: ann,
        vi: null,
        mode: 'move',
        startX: ip.x,
        startY: ip.y,
        origPolygon: ann.polygon ? ann.polygon.map(p => [p[0], p[1]]) : null,
        origBox: ann.type === 'box' ? { x: ann.x, y: ann.y } : null,
      };
      this._moved = false;
      this.v.selectedId = ann.id;
      if (window._app) window._app.renderAnnList();
      return;
    }

    // 4. Click to clear selection if nothing hit
    try { console.debug('[PolygonEditTool] nothing hit — clearing selection'); } catch(e){}
    this.v.selectedId = null;
    if (window._app) window._app.renderAnnList();
  }

  onMove(e, sx, sy, ip) {
    try { console.debug('[PolygonEditTool.onMove]', { drag: !!this._drag, ip }); } catch(e){}
    if (!this._drag) return;

    // If dragging a vertex
    if (this._drag.vi !== null && typeof this._drag.vi !== 'undefined') {
      try { console.debug('[PolygonEditTool] dragging vertex', this._drag.vi); } catch(e){}
      this._drag.ann.polygon[this._drag.vi] = [Math.round(ip.x), Math.round(ip.y)];
      this._moved = true;
      return;
    }

    // If dragging the whole annotation (move)
    const ann = this._drag.ann;
    const dx = Math.round(ip.x - this._drag.startX);
    const dy = Math.round(ip.y - this._drag.startY);
    try { console.debug('[PolygonEditTool] moving ann', { id: ann.id, dx, dy }); } catch(e){}
    if (ann.type === 'polygon' && this._drag.origPolygon) {
      ann.polygon = this._drag.origPolygon.map(p => [p[0] + dx, p[1] + dy]);
    } else if (ann.type === 'box' && this._drag.origBox) {
      ann.x = this._drag.origBox.x + dx;
      ann.y = this._drag.origBox.y + dy;
    }
    this._moved = true;
  }

  onUp() {
    try { console.debug('[PolygonEditTool.onUp]', { drag: !!this._drag, moved: this._moved }); } catch(e){}
    if (this._drag) {
      if (this._moved) this.onChanged(this._drag.ann);
      this._drag = null;
      this._moved = false;
    }
  }

  draw() {}

  // Right-click → delete vertex (called from main.js contextmenu handler)
  tryDeleteVertex(ip) {
    const hit = this.v.findNearVertex(ip.x, ip.y, 6);
    if (!hit) return false;
    const { ann, vi } = hit;
    if (ann.polygon.length <= 3) return false; // keep minimum triangle
    ann.polygon.splice(vi, 1);
    this.onChanged(ann);
    return true;
  }

  _findEdge(ix, iy) {
    const thresh = 8 / this.v.scale;
    for (const ann of this.v.annotations) {
      if (ann.type !== 'polygon' || !ann.polygon) continue;
      const pts = ann.polygon;
      for (let i = 0; i < pts.length; i++) {
        const a = pts[i], b = pts[(i+1) % pts.length];
        if (_distSeg(ix, iy, a[0], a[1], b[0], b[1]) < thresh) return ann;
      }
    }
    return null;
  }

  _edgeInsertIdx(ann, ix, iy) {
    const pts = ann.polygon;
    let best = 1, bestD = Infinity;
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i+1) % pts.length];
      const d = _distSeg(ix, iy, a[0], a[1], b[0], b[1]);
      if (d < bestD) { bestD = d; best = i + 1; }
    }
    return best;
  }
}

// ── geometry ──────────────────────────────────────────────────────────────
function _distSeg(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  if (dx === 0 && dy === 0) return Math.hypot(px-ax, py-ay);
  const t = Math.max(0, Math.min(1, ((px-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)));
  return Math.hypot(px - (ax + t*dx), py - (ay + t*dy));
}

// ── ToolManager ────────────────────────────────────────────────────────────
class ToolManager {
  constructor(viewer, onBoxComplete, onAnnotationChanged) {
    this.v       = viewer;
    this.current = 'box';

    this.tools = {
      box:   new BoxTool(viewer, onBoxComplete),
      brush: new BrushTool(viewer),
      pan:   new PanTool(),
      edit:  new PolygonEditTool(viewer, onAnnotationChanged),
    };

    this.setTool('box');
  }

  setTool(name) {
    try { console.debug('[ToolManager.setTool]', name); } catch(e){}
    this.current       = name;
    this.v.currentTool = name;
    this.v.activeTool  = this.tools[name] || this.tools.box;
    this._updateCursor(name);

    const bs = document.getElementById('brush-section');
    if (bs) bs.style.display = name === 'brush' ? '' : 'none';
  }

  _updateCursor(name) {
    const map = { box: 'crosshair', brush: 'cell', pan: 'grab', edit: 'default' };
    this.v.canvas.style.cursor = map[name] || 'crosshair';
  }

  get boxTool()   { return this.tools.box; }
  get brushTool() { return this.tools.brush; }
  get editTool()  { return this.tools.edit; }
}
