/* viewer.js
 * Canvas-based DICOM viewer.
 *
 * KEY BUGFIX: ctx.scale(dpr,dpr) used to be called on every resize, which
 * ACCUMULATES (scale 2 → 4 → 8…).  Now we call ctx.setTransform(dpr,…) at
 * the TOP of EVERY render frame, so the DPR base is always correct.
 *
 * Coordinate spaces:
 *   CSS pixels  : what the browser reports for mouse events / clientWidth
 *   Image pixels: the DICOM image's native pixel grid (0…imgW, 0…imgH)
 *
 * transform:  imagePoint = (cssPoint – offset) / scale
 */

class DicomViewer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx    = this.canvas.getContext('2d');

    // ── transform (all values in CSS-pixel space) ────────────────────
    this.scale   = 1.0;
    this.offsetX = 0;
    this.offsetY = 0;

    // ── image ────────────────────────────────────────────────────────
    this.img       = null;
    this.imgW      = 0;
    this.imgH      = 0;
    this.imgLoaded = false;

    // ── windowing ────────────────────────────────────────────────────
    this.wc = 0;  this.ww = 4096;
    this.defaultWC = 0;  this.defaultWW = 4096;

    // ── current file ─────────────────────────────────────────────────
    this.currentPath = null;
    this.currentMeta = null;

    // ── annotations (managed externally by AnnotationManager) ────────
    this.annotations  = [];
    this.selectedId   = null;

    // ── pending segmentation result (not yet accepted) ───────────────
    this.pendingPolygon = null;   // [[x,y], …] in image coords
    this.pendingBbox    = null;   // {x,y,w,h} in image coords

    // ── brush overlay ─────────────────────────────────────────────────
    this.brushCanvas = null;
    this.brushCtx    = null;

    // ── pan interaction ──────────────────────────────────────────────
    this.isPanning  = false;
    this.panLastX   = 0;
    this.panLastY   = 0;

    // ── right-drag windowing ─────────────────────────────────────────
    this._wwDrag = false;
    this._wwSX   = 0;  this._wwSY   = 0;
    this._wwSWC  = 0;  this._wwSWW  = 4096;

    // ── middle-drag (wheel) windowing ────────────────────────────────
    this._wheelDrag = false;
    this._wheelSX   = 0;  this._wheelSY   = 0;
    this._wheelSWC  = 0;  this._wheelSWW  = 4096;

    // ── tool delegate (set by ToolManager) ───────────────────────────
    this.currentTool = 'box';
    this.activeTool  = null;

    // ── DPR (set in _resize, used in _render) ────────────────────────
    this._dpr  = window.devicePixelRatio || 1;
    this._cssW = 0;
    this._cssH = 0;

    this._setupCanvas();
    this._bindEvents();
    requestAnimationFrame(() => this._loop());
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Canvas setup
  // ─────────────────────────────────────────────────────────────────────

  _setupCanvas() {
    this._resize();
    new ResizeObserver(() => this._resize()).observe(this.canvas.parentElement);
  }

  _resize() {
    const wrap = this.canvas.parentElement;
    const dpr  = window.devicePixelRatio || 1;
    const W    = wrap.clientWidth  || 1;
    const H    = wrap.clientHeight || 1;

    // Set physical canvas size
    this.canvas.width  = Math.round(W * dpr);
    this.canvas.height = Math.round(H * dpr);
    // Keep CSS size intact (browser may have set it)
    this.canvas.style.width  = W + 'px';
    this.canvas.style.height = H + 'px';

    this._dpr  = dpr;
    this._cssW = W;
    this._cssH = H;
    // NOTE: do NOT call ctx.scale() here – that would accumulate across
    // multiple resize events.  We call setTransform() in every render frame.
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Image loading
  // ─────────────────────────────────────────────────────────────────────

  async loadImage(path, meta) {
    this.currentPath = path;
    this.currentMeta = meta;
    this.wc        = meta.WindowCenter;
    this.ww        = meta.WindowWidth;
    this.defaultWC = meta.WindowCenter;
    this.defaultWW = meta.WindowWidth;
    this.pendingPolygon = null;
    this.pendingBbox    = null;
    this.selectedId     = null;
    this.imgLoaded      = false;

    await this._fetchImage(this.wc, this.ww);
    this.fitToScreen();
    this._initBrush();
  }

  async _fetchImage(wc, ww) {
    const msgEl = document.getElementById('canvas-overlay-msg');
    if (msgEl) msgEl.textContent = 'Loading…';
    try {
      const data = await API.getImage(this.currentPath, wc, ww);
      await new Promise((res, rej) => {
        const img = new Image();
        img.onload  = () => {
          this.img     = img;
          this.imgW    = data.width;
          this.imgH    = data.height;
          this.imgLoaded = true;
          res();
        };
        img.onerror = rej;
        img.src = 'data:image/png;base64,' + data.image_data;
      });
      if (msgEl) msgEl.textContent = '';
    } catch (e) {
      if (msgEl) msgEl.textContent = '❌ ' + e.message;
      throw e;
    }
  }

  async applyWindowing(wc, ww) {
    this.wc = wc;
    this.ww = ww;
    if (this.currentPath) await this._fetchImage(wc, ww);
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Coordinate transforms  (CSS-pixel ↔ image-pixel)
  // ─────────────────────────────────────────────────────────────────────

  screenToImage(sx, sy) {
    return {
      x: (sx - this.offsetX) / this.scale,
      y: (sy - this.offsetY) / this.scale,
    };
  }

  imageToScreen(ix, iy) {
    return {
      x: ix * this.scale + this.offsetX,
      y: iy * this.scale + this.offsetY,
    };
  }

  // ─────────────────────────────────────────────────────────────────────
  //  View manipulation
  // ─────────────────────────────────────────────────────────────────────

  /** Zoom centred on a CSS-pixel point (sx, sy). */
  zoomAt(factor, sx, sy) {
    this.offsetX = sx - (sx - this.offsetX) * factor;
    this.offsetY = sy - (sy - this.offsetY) * factor;
    this.scale   = Math.max(0.04, Math.min(100, this.scale * factor));
  }

  zoomStep(factor) {
    this.zoomAt(factor, this._cssW / 2, this._cssH / 2);
  }

  fitToScreen() {
    if (!this.imgLoaded || !this.imgW || !this.imgH) return;
    const margin = 0.95;
    this.scale   = Math.min(
      (this._cssW * margin) / this.imgW,
      (this._cssH * margin) / this.imgH
    );
    this.offsetX = (this._cssW - this.imgW * this.scale) / 2;
    this.offsetY = (this._cssH - this.imgH * this.scale) / 2;
  }

  resetView() {
    this.scale = 1; this.offsetX = 0; this.offsetY = 0;
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Brush
  // ─────────────────────────────────────────────────────────────────────

  _initBrush() {
    this.brushCanvas        = document.createElement('canvas');
    this.brushCanvas.width  = this.imgW;
    this.brushCanvas.height = this.imgH;
    this.brushCtx           = this.brushCanvas.getContext('2d');
    this.brushCtx.clearRect(0, 0, this.imgW, this.imgH);
  }

  paintBrush(ix, iy, radius, mode) {
    if (!this.brushCtx) return;
    try { console.debug('[paintBrush]', { ix: Math.round(ix), iy: Math.round(iy), radius, mode, offsetX: this.offsetX, offsetY: this.offsetY, scale: this.scale, imgW: this.imgW, imgH: this.imgH, cssW: this._cssW, cssH: this._cssH }); } catch(e){}
    const ctx = this.brushCtx;
    ctx.globalCompositeOperation = mode === 'erase' ? 'destination-out' : 'source-over';
    ctx.fillStyle = mode === 'bg' ? 'rgba(255,80,80,0.55)' : 'rgba(0,230,118,0.55)';
    ctx.beginPath();
    ctx.arc(Math.round(ix), Math.round(iy), Math.max(1, radius), 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = 'source-over';
  }

  clearBrush() {
    if (this.brushCtx) this.brushCtx.clearRect(0, 0, this.imgW, this.imgH);
  }

  getBrushMaskBase64() {
    return this.brushCanvas
      ? this.brushCanvas.toDataURL('image/png').split(',')[1]
      : null;
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Render loop  (THE CRITICAL DPR FIX IS HERE)
  // ─────────────────────────────────────────────────────────────────────

  _loop() {
    this._render();
    requestAnimationFrame(() => this._loop());
  }

  _render() {
    const ctx  = this.ctx;
    const W    = this._cssW;
    const H    = this._cssH;
    const dpr  = this._dpr;

    if (!W || !H) return;

    // ★ FIX: reset to DPR base every single frame – never accumulates
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#050505';
    ctx.fillRect(0, 0, W, H);

    if (!this.imgLoaded || !this.img) return;

    // Apply viewer transform (zoom + pan) on top of DPR base
    ctx.save();
    ctx.translate(this.offsetX, this.offsetY);
    ctx.scale(this.scale, this.scale);

    // 1. DICOM image
    ctx.drawImage(this.img, 0, 0);

    // 2. Brush overlay
    if (this.brushCanvas && this.brushCanvas.width > 0) {
      ctx.globalAlpha = 0.35;  // [BUG #2 FIX] Reduced from 0.6 to be less intrusive
      ctx.drawImage(this.brushCanvas, 0, 0);
      ctx.globalAlpha = 1;
    }

    // 3. Saved annotations
    this._drawAnnotations(ctx);

    // 4. Pending segmentation result (orange preview)
    if (this.pendingBbox) {
      this._drawBboxDashed(ctx, this.pendingBbox, '#ff9800');
    }
    if (this.pendingPolygon && this.pendingPolygon.length >= 3) {
      this._drawPoly(ctx, this.pendingPolygon, '#ff9800', 'rgba(255,152,0,.15)', false);
    }

    // 5. Active tool overlay (e.g. box being drawn)
    if (this.activeTool && this.activeTool.draw) {
      this.activeTool.draw(ctx, this.scale);
    }

    ctx.restore();
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Drawing helpers  (all coords in image space)
  // ─────────────────────────────────────────────────────────────────────

  _drawAnnotations(ctx) {
    const colors = {
      hole: '#40c4ff',
      crack: '#ff5252',
      void: '#40c4ff',
      defect: '#40c4ff',
      default: '#b0bec5'
    };

    for (const ann of this.annotations) {
      const sel  = ann.id === this.selectedId;
      const showVerts = sel || this.currentTool === 'edit';
      const annClass = ann.class || 'defect';
      const baseClr = colors[annClass] || colors.default;

      const clr  = sel ? '#ffeb3b' : baseClr;
      let fill;
      if (sel) {
        fill = 'rgba(255,235,59,.14)';
      } else {
        if (annClass === 'crack') {
          fill = 'rgba(255,82,82,.12)';
        } else {
          fill = 'rgba(64,196,255,.12)';
        }
      }

      if (ann.type === 'polygon' && ann.polygon && ann.polygon.length >= 3) {
        this._drawPoly(ctx, ann.polygon, clr, fill, showVerts);
        // Show class label at centroid
        this._drawPolyLabel(ctx, ann.polygon, annClass, clr);
      } else if (ann.type === 'box') {
        this._drawBox(ctx, ann.x, ann.y, ann.w, ann.h, clr, fill, sel, annClass);
      }
    }
  }

  _drawPoly(ctx, pts, stroke, fill, showVerts) {
    const lw = 1.5 / this.scale;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();
    ctx.fillStyle = fill;   ctx.fill();
    ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke();

    if (showVerts) {
      const r = 4 / this.scale;
      ctx.fillStyle = stroke;
      for (const p of pts) {
        ctx.beginPath();
        ctx.arc(p[0], p[1], r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  _drawPolyLabel(ctx, pts, label, clr) {
    const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    const fs = 12 / this.scale;
    ctx.font = `${fs}px monospace`;
    ctx.fillStyle = clr;
    
    // 計算不規則形狀的長寬
    const xs = pts.map(p => p[0]);
    const ys = pts.map(p => p[1]);
    const wPx = Math.max(...xs) - Math.min(...xs);
    const hPx = Math.max(...ys) - Math.min(...ys);

    let dimText = `${Math.round(wPx)}×${Math.round(hPx)} px`;
    const ps = this.currentMeta?.PixelSpacing;
    if (ps && ps.length >= 2) {
      const wMm = wPx * ps[1];
      const hMm = hPx * ps[0];
      dimText = `${wMm.toFixed(1)}×${hMm.toFixed(1)} mm`;
    }

    // 繪製類別標籤與長寬尺寸
    ctx.fillText(label, cx - ctx.measureText(label).width / 2, cy - 2 / this.scale);
    
    const fsSmall = 9.5 / this.scale;
    ctx.font = `${fsSmall}px monospace`;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
    ctx.fillText(dimText, cx - ctx.measureText(dimText).width / 2, cy + fsSmall + 1 / this.scale);
  }

  _drawBox(ctx, x, y, w, h, stroke, fill, sel, label) {
    const lw = 1.5 / this.scale;
    ctx.fillStyle = fill;   ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.strokeRect(x, y, w, h);

    const fs = 12 / this.scale;
    ctx.font = `${fs}px monospace`;
    ctx.fillStyle = stroke;

    let dimText = "";
    const ps = this.currentMeta?.PixelSpacing;
    if (ps && ps.length >= 2) {
      const wMm = w * ps[1];
      const hMm = h * ps[0];
      dimText = ` (${wMm.toFixed(1)}×${hMm.toFixed(1)} mm)`;
    }
    const fullLabel = label + dimText;
    ctx.fillText(fullLabel, x + 2/this.scale, y - 3/this.scale);

    if (sel) {
      const hs = 5 / this.scale;
      for (const [cx, cy] of [[x,y],[x+w,y],[x,y+h],[x+w,y+h]]) {
        ctx.fillStyle = stroke;
        ctx.fillRect(cx - hs/2, cy - hs/2, hs, hs);
      }
    }
  }

  _drawBboxDashed(ctx, bbox, clr) {
    const lw = 1.2 / this.scale;
    ctx.setLineDash([6/this.scale, 3/this.scale]);
    ctx.strokeStyle = clr; ctx.lineWidth = lw;
    ctx.strokeRect(bbox.x, bbox.y, bbox.w, bbox.h);
    ctx.setLineDash([]);
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Mouse events
  // ─────────────────────────────────────────────────────────────────────

  _bindEvents() {
    const c = this.canvas;
    c.addEventListener('mousedown',   e => this._onDown(e));
    c.addEventListener('mousemove',   e => this._onMove(e));
    c.addEventListener('mouseup',     e => this._onUp(e));
    c.addEventListener('mouseleave',  e => this._onUp(e));
    c.addEventListener('wheel',       e => this._onWheel(e), { passive: false });
    c.addEventListener('contextmenu', e => e.preventDefault());
  }

  /** Returns CSS-pixel coords of the event relative to canvas. */
  _pos(e) {
    const r = this.canvas.getBoundingClientRect();
    return { sx: e.clientX - r.left, sy: e.clientY - r.top };
  }

  _onDown(e) {
    const { sx, sy } = this._pos(e);
    const ip = this.screenToImage(sx, sy);
    try { console.debug('[Viewer._onDown]', { button: e.button, sx, sy, ip, currentTool: this.currentTool }); } catch(e){}

    if (e.button === 1) {
      e.preventDefault();
      this._wheelDrag = true;
      this._wheelSX   = sx;
      this._wheelSY   = sy;
      this._wheelSWC  = this.wc;
      this._wheelSWW  = this.ww;
      this.canvas.style.cursor = 'crosshair';
      return;
    }

    if (e.button === 0 && (this.currentTool === 'pan' || e.altKey)) {
      this.isPanning = true;
      this.panLastX  = sx; this.panLastY = sy;
      this.canvas.style.cursor = 'grabbing';
      return;
    }

    if (e.button === 2) {
      this._wwDrag = true;
      this._wwSX   = sx;  this._wwSY  = sy;
      this._wwSWC  = this.wc; this._wwSWW = this.ww;
      return;
    }

    if (e.button === 0 && this.activeTool) {
      try { console.debug('[Viewer._onDown] calling activeTool.onDown'); } catch(e){}
      this.activeTool.onDown(e, sx, sy, ip);
    }
  }

  _onMove(e) {
    const { sx, sy } = this._pos(e);
    const ip = this.screenToImage(sx, sy);

    // Update status bar via app
    if (window._app) window._app.updatePointer(Math.round(ip.x), Math.round(ip.y));

    if (this._wheelDrag) {
      // 左右移動 (sx - this._wheelSX) 調整 contrast (Window Width, WW)
      // 上下移動 (sy - this._wheelSY) 調整 center (Window Center, WC)
      const newWW = Math.max(1, this._wheelSWW + (sx - this._wheelSX) * 4);
      const newWC = this._wheelSWC + (sy - this._wheelSY) * 2;
      if (window._app) window._app.updateWindowFromDrag(newWC, newWW);
      return;
    }

    if (this.isPanning) {
      this.offsetX += sx - this.panLastX;
      this.offsetY += sy - this.panLastY;
      this.panLastX = sx; this.panLastY = sy;
      return;
    }

    if (this._wwDrag) {
      const newWC = this._wwSWC + (sx - this._wwSX) * 2;
      const newWW = Math.max(1, this._wwSWW - (sy - this._wwSY) * 4);
      if (window._app) window._app.updateWindowFromDrag(newWC, newWW);
      return;
    }

    if (this.activeTool) this.activeTool.onMove(e, sx, sy, ip);
  }

  _onUp(e) {
    const { sx, sy } = this._pos(e);
    const ip = this.screenToImage(sx, sy);

    if (this._wheelDrag) {
      if (e.button === 1) e.preventDefault();
      this._wheelDrag = false;
      this.canvas.style.cursor = '';
      return;
    }
    if (this.isPanning) {
      this.isPanning = false;
      this.canvas.style.cursor = '';
      return;
    }
    if (this._wwDrag) { this._wwDrag = false; return; }
    if (this.activeTool) this.activeTool.onUp(e, sx, sy, ip);
  }

  _onWheel(e) {
    e.preventDefault();
    const { sx, sy } = this._pos(e);
    this.zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, sx, sy);
    if (window._app) window._app.updateZoomDisplay();
  }

  // ─────────────────────────────────────────────────────────────────────
  //  Hit-testing helpers
  // ─────────────────────────────────────────────────────────────────────

  /** Find a polygon vertex within threshPx CSS pixels of (ix, iy). */
  findNearVertex(ix, iy, threshPx = 8) {
    const thresh = threshPx / this.scale;
    for (const ann of this.annotations) {
      if (ann.type !== 'polygon' || !ann.polygon) continue;
      for (let vi = 0; vi < ann.polygon.length; vi++) {
        const [px, py] = ann.polygon[vi];
        if (Math.hypot(px - ix, py - iy) < thresh) return { ann, vi };
      }
    }
    return null;
  }

  /** Return the first annotation (polygon or box) containing (ix, iy). */
  hitTest(ix, iy) {
    for (let i = this.annotations.length - 1; i >= 0; i--) {
      const a = this.annotations[i];
      if (a.type === 'box') {
        if (ix >= a.x && ix <= a.x + a.w && iy >= a.y && iy <= a.y + a.h) return a;
      } else if (a.type === 'polygon' && a.polygon) {
        if (_ptInPoly(ix, iy, a.polygon)) return a;
      }
    }
    return null;
  }
}

// ── geometry ──────────────────────────────────────────────────────────────
function _ptInPoly(px, py, pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if (((yi > py) !== (yj > py)) &&
        px < (xj - xi) * (py - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
