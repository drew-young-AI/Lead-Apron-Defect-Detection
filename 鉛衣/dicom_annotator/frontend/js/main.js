/* main.js  v3-final — End-to-end complete
 *
 * BUG FIXES vs previous version
 * ─────────────────────────────
 * [M1] Brush mode: canvas mouseup → debounce 500ms → _onBrushComplete()
 *      → _getBrushBBox() → _runSeg()  (same flow as box mode)
 * [M2] _exitMarkMode(): removes brush mouseup listener (no memory leak)
 * [M3] _runSeg(): brush uses SEG_CYCLE_BRUSH (adaptive→canny→...) for better
 *      thin-feature detection; box uses SEG_CYCLE_BOX (grabcut→...)
 * [M4] _accept(): viewer.selectedId=null after accept → ALL annotations visible
 * [M5] _adjustThenSave(): clears brush canvas before entering edit mode
 * [M6] _closePending(): clearBrush() when fabMode==='brush'
 * [M7] _save(): deselects + exits edit mode so all annotations render on canvas
 * [M8] renderAnnList(): also updates del-all-btn visibility (defensive)
 * [M9] FAB text resets correctly on ESC
 * [M10] Brush bbox: tries image-space coords first, falls back to screen→image
 */

const SEG_CYCLE_BOX   = ['grabcut','otsu','watershed','adaptive','canny'];
const SEG_CYCLE_BRUSH = ['adaptive','canny','region_growing','watershed','otsu'];

class AppController {
  constructor() {
    this.viewer  = new DicomViewer('viewer-canvas');
    this.annMgr  = new AnnotationManager(this.viewer);
    this.tools   = new ToolManager(
      this.viewer,
      bbox => this._onBox(bbox),
      ann  => this.annMgr.update(ann, {}),
    );

    this.files       = [];     // [{path, el}]
    this.fileIdx     = -1;
    this.lastBbox    = null;
    this.segCycleIdx = 0;
    this.fabMode     = 'box';  // 'box' | 'brush'
    this.marking     = false;
    this._wwTimer    = null;
    this._brushDoneHandler = null;  // [M2]
    this._brushTimer = null;

    // Multi-file selection (Shift/Ctrl click)
    this._selectedFiles = new Set(); // set of paths
    this._lastSelectedFileIdx = null;

    window._app = this;
    App = this;

    this._boot();
  }

  async _boot() {
    this._bindAll();
    this._activateTool('box');
    await this._loadUploaded();
    await this._loadHistory();
  }

  // ══════════════════════════════════════════════════════════ UPLOAD ═══

  _bindDrop() {
    const input = document.getElementById('upload-input');
    const dz    = document.getElementById('drop-zone');
    input.addEventListener('change', e => {
      const files = [...(e.target.files||[])];
      if (files.length) this._upload(files);
      input.value = '';
    });
    let depth = 0;
    document.addEventListener('dragenter', e => { e.preventDefault(); depth++; dz.classList.add('drag-over'); });
    document.addEventListener('dragleave', () => { if(--depth<=0){depth=0;dz.classList.remove('drag-over');} });
    document.addEventListener('dragover',  e => e.preventDefault());

    // Support dropping folders: traverse FileSystemEntries when available
    document.addEventListener('drop', async (e) => {
      e.preventDefault(); depth=0; dz.classList.remove('drag-over');
      const items = e.dataTransfer?.items;
      let files = [];

      if (items && items.length && typeof items[0].webkitGetAsEntry === 'function') {
        try {
          const entries = [];
          for (let i = 0; i < items.length; i++) {
            const it = items[i];
            if (it.kind === 'file') {
              const entry = it.webkitGetAsEntry();
              if (entry) entries.push(entry);
            }
          }

          async function readEntryRec(entry) {
            return new Promise((resolve) => {
              if (entry.isFile) {
                entry.file(f => resolve([f]));
              } else if (entry.isDirectory) {
                const reader = entry.createReader();
                let acc = [];
                const readBatch = () => {
                  reader.readEntries(async (results) => {
                    if (!results.length) {
                      // process collected entries
                      const lists = await Promise.all(acc.map(e => readEntryRec(e)));
                      resolve(lists.flat());
                      return;
                    }
                    acc.push(...results);
                    readBatch();
                  });
                };
                readBatch();
              } else resolve([]);
            });
          }

          for (const ent of entries) {
            const arr = await readEntryRec(ent);
            files.push(...arr);
          }
        } catch (err) {
          console.warn('[drop traverse]', err);
        }
      } else {
        files = [...(e.dataTransfer?.files||[])];
      }

      files = files.filter(f => /\.dcm$/i.test(f.name));
      if (files.length) this._upload(files);
      else this._toast('只接受 .dcm 檔案或資料夾','err');
    });
  }

  async _upload(files) {
    const prog  = document.getElementById('upload-progress');
    const dupEl = document.getElementById('dup-warn');
    prog.innerHTML = ''; dupEl.style.display = 'none';

    let lastGood=null, dupCount=0, dupPath=null;
    for (const f of files) {
      const row = document.createElement('div');
      row.className = 'upl-row';
      row.innerHTML = `<span class="upl-name" title="${this._esc(f.name)}">${this._esc(f.name)}</span><span class="upl-run">…</span>`;
      prog.appendChild(row);
      const st = row.querySelector('span:last-child');
      try {
        const r = await API.uploadDicom(f);
        if (r.duplicate) {
          dupCount++; dupPath = r.path;
          st.textContent = r.duplicate==='exact' ? '⚠ 完全重複' : '⚠ 內容重複';
          let existing = this.files.find(x => x.path === r.path);
          if (!existing) {
            existing = this._addFile(r.path, '', r.original_name);
          }
          if (files.length === 1) {
            this._open(existing.path, existing.el);
          }
          dupEl.textContent = `⚠ "${f.name}" 與已上傳檔案重複（${r.duplicate==='exact'?'SOPInstanceUID':'影像內容'}相符），直接切換至原圖編輯。`;
          dupEl.style.display = '';
        } else {
          st.textContent = '✓ OK';
          this._addFile(r.path, '', r.original_name);
          lastGood = r.path;
        }
      } catch(e) { st.textContent='✗'; st.className='upl-err'; row.title=e.message; }
    }
    this._updateCounts();
    setTimeout(()=>{ prog.innerHTML=''; }, 3500);
    const toOpen = lastGood || (dupCount && dupPath);
    if (toOpen) {
      const entry = this.files.find(f=>f.path===toOpen);
      await this._open(toOpen, entry?.el);
    }
  }

  _addFile(path, flag='', originalName='') {
    if (this.files.some(f=>f.path===path)) return;
    const fname = originalName || path.split(/[/\\]/).pop();
    const el    = document.createElement('div');
    el.className = 'fi'; el.dataset.path = path;
    const dot  = Object.assign(document.createElement('span'),{className:'fi-dot'+(flag==='dup'?' dup':'')});
    const name = Object.assign(document.createElement('span'),{className:'fi-name',textContent:fname,title:path});
    const countSpan = Object.assign(document.createElement('span'), {className:'fi-ann-count', textContent:'0'});
    const noteSpan = Object.assign(document.createElement('span'), {className:'fi-note-status', textContent:''});
    el.append(dot, name, countSpan, noteSpan);
    if (flag==='dup') el.append(Object.assign(document.createElement('span'),{className:'fi-dup',textContent:'重複'}));
    el.addEventListener('click', (e) => {
      if (e.shiftKey || e.ctrlKey || e.metaKey) {
        e.stopPropagation();
        this._toggleFileSelection(el, path, e.shiftKey);
      } else {
        // regular click: clear multi-selection and open file
        this._clearFileSelection();
        this._open(path, el);
      }
    });
    document.getElementById('file-list').querySelector('.list-hint')?.remove();
    document.getElementById('file-list').appendChild(el);
    document.getElementById('file-list-hdr').style.display = 'flex';
    this.files.push({path, el});
    this._updateNavLabel();
  }

  async _loadUploaded() {
    try {
      const {files} = await API.listUploaded();
      (files||[]).forEach(f=>this._addFile(f.path, '', f.original_name));
      this._updateCounts();
    } catch {}
  }

  // ══════════════════════════════════════════════════════════ OPEN ════

  async _open(path, rowEl) {
    if (this.annMgr.dirty && this.annMgr.list.length>0) {
      if (!confirm('有未儲存的標註，確定切換影像？')) return;
    }
    this._exitMarkMode();  // always exit mark mode when opening new file
    this.viewer.clearBrush?.();

    document.querySelectorAll('.fi').forEach(r=>{
      r.classList.remove('active');
      r.querySelector('.fi-dot')?.classList.remove('cur');
    });
    rowEl?.classList.add('active');
    rowEl?.querySelector('.fi-dot')?.classList.add('cur');
    this.fileIdx = this.files.findIndex(f=>f.path===path);
    this._updateNavLabel();
    this._setMsg('載入中…'); this._hideFAB();
    document.getElementById('save-btn').disabled = true;

    try {
      const meta = await API.getMetadata(path);
      const wc=meta.WindowCenter, ww=meta.WindowWidth;
      const wcSl=document.getElementById('wc-slider'), wwSl=document.getElementById('ww-slider');
      wcSl.min=Math.min(-4096,Math.round(wc-ww)); wcSl.max=Math.max(8192,Math.round(wc+ww));
      wwSl.min=1; wwSl.max=Math.max(16384,Math.round(ww*2));
      wcSl.value=Math.round(wc); wwSl.value=Math.round(ww);

      await this.viewer.loadImage(path, meta);
      await this.annMgr.load(path, meta);   // [A5] resets selectedId → all annotations show

      // Mark row annotated if has saved annotations
      if (this.annMgr.list.length>0) rowEl?.querySelector('.fi-dot')?.classList.add('done');

      // Reset segmentation state
      this.lastBbox=null; this.segCycleIdx=0;
      this.viewer.pendingPolygon=null; this.viewer.pendingBbox=null;
      document.getElementById('pend-bar').style.display='none';
      document.getElementById('accept-btn').disabled=true;

      const pid=meta.PatientID?`${meta.PatientID}  `:'';
      document.getElementById('sb-info').textContent=`${pid}${meta.Modality||''}  ${meta.Columns}×${meta.Rows}`;
      document.getElementById('save-btn').disabled=false;

      this._setMsg('');
      this._showFAB();
      this._hint('選擇 ▣ 或 🖌 模式，點 FAB「標記缺陷」');
      this.updateZoomDisplay();
      this.updateWindowingDisplay();
    } catch(e) { this._setMsg('❌ '+e.message); console.error('[open]',e); }
  }

  // ══════════════════════════════════════════════════════ MARK MODE ════

  _enterMarkMode() {
    try { console.debug('[enterMarkMode]', { fabMode: this.fabMode, currentPath: this.viewer.currentPath }); } catch(e){}
    if (!this.viewer.currentPath) { this._toast('請先開啟影像','err'); return; }
    this.marking = true;
    const fab = document.getElementById('fab');
    fab.classList.add('marking');

    if (this.fabMode === 'brush') {
      this._activateTool('brush');
      try { console.debug('[enterMarkMode] activated brush'); } catch(e){}
      fab.textContent = '🖌 塗抹中… (Esc 取消)';
      this._hint('用筆刷塗抹缺陷範圍，放開滑鼠後自動偵測');

      // [M1] Auto-segment after brush stroke ends (attach fallback to document)
      const canvas = document.getElementById('viewer-canvas');
      this._brushDoneHandler = (e) => {
        try { console.debug('[brushDoneHandler]', { eventType: e?.type, marking: this.marking, fabMode: this.fabMode }); } catch(e){}
        if (!this.marking || this.fabMode !== 'brush') return;
        clearTimeout(this._brushTimer);
        this._brushTimer = setTimeout(() => this._onBrushComplete(), 500);
      };
      // prefer canvas mouseup but also listen on document as fallback (overlay may intercept)
      canvas.addEventListener('mouseup', this._brushDoneHandler);
      document.addEventListener('mouseup', this._brushDoneHandler);
    } else {
      this._activateTool('box');
      fab.textContent = '🎯 框選中… (Esc 取消)';
      this._hint('在缺陷上拖曳框選矩形');
    }
  }

  _exitMarkMode() {
    this.marking = false;
    clearTimeout(this._brushTimer);

    // [M2] Remove brush mouseup listener (both canvas and document)
    if (this._brushDoneHandler) {
      const c = document.getElementById('viewer-canvas');
      if (c) c.removeEventListener('mouseup', this._brushDoneHandler);
      try { document.removeEventListener('mouseup', this._brushDoneHandler); } catch(e){}
      this._brushDoneHandler = null;
    }

    const fab = document.getElementById('fab');
    if (fab) { fab.classList.remove('marking'); fab.textContent = '＋ 標記缺陷'; }
    this._activateTool('pan');
  }

  // ══════════════════════════════════════════════════════ BOX MODE ════

  _onBox(bbox) {
    try { console.debug('[onBox]', bbox); } catch(e){}
    this.lastBbox = {...bbox};
    this._exitMarkMode();
    this._runSeg();
  }

  // ══════════════════════════════════════════════════ BRUSH MODE ════

  // [M1] Called 500ms after last brush mouseup
  async _onBrushComplete() {
    try { console.debug('[onBrushComplete]', { marking: this.marking, fabMode: this.fabMode }); } catch(e){}
    if (!this.marking || this.fabMode !== 'brush') return;

    const bbox = this._getBrushBBox();
    if (!bbox || bbox.w < 4 || bbox.h < 4) {
      this._hint('繼續塗抹缺陷範圍…');
      return;
    }
    this.lastBbox    = bbox;
    this.segCycleIdx = 0;   // start brush cycle from adaptive
    this._exitMarkMode();
    await this._runSeg();
  }

  // [M10] Extract bounding box from painted pixels on brushCanvas
  _getBrushBBox() {
    try {
      const bc = this.viewer.brushCanvas;
      if (!bc || !bc.width || !bc.height) return null;
      const ctx = bc.getContext('2d');
      const d   = ctx.getImageData(0, 0, bc.width, bc.height).data;
      let x1=bc.width, y1=bc.height, x2=0, y2=0, found=false;
      for (let y=0; y<bc.height; y++) {
        for (let x=0; x<bc.width; x++) {
          if (d[(y*bc.width+x)*4+3] > 10) {
            x1=Math.min(x1,x); y1=Math.min(y1,y);
            x2=Math.max(x2,x); y2=Math.max(y2,y);
            found=true;
          }
        }
      }
      if (!found || x2<=x1 || y2<=y1) return null;

      const M = 30; // margin in pixels
      const iW = this.viewer.imgW || 512, iH = this.viewer.imgH || 512;

      // Determine if brushCanvas is in image-space or display-space
      const sameAsImage = Math.abs(bc.width-iW)<4 && Math.abs(bc.height-iH)<4;
      if (sameAsImage) {
        // brushCanvas pixel coords = image pixel coords
        return { x:Math.max(0,x1-M), y:Math.max(0,y1-M),
                 w:Math.min(iW,x2+M)-Math.max(0,x1-M),
                 h:Math.min(iH,y2+M)-Math.max(0,y1-M) };
      } else {
        // brushCanvas is in display/screen coords → convert
        const tl = this.viewer.screenToImage(Math.max(0,x1-M), Math.max(0,y1-M));
        const br = this.viewer.screenToImage(Math.min(bc.width-1,x2+M), Math.min(bc.height-1,y2+M));
        return { x:Math.max(0,tl.x), y:Math.max(0,tl.y),
                 w:Math.max(1,br.x-tl.x), h:Math.max(1,br.y-tl.y) };
      }
    } catch(e) { console.warn('[getBrushBBox]',e); return null; }
  }

  // ══════════════════════════════════════════════ SEGMENTATION ════

  async _runSeg() {
    // Debug: ensure prerequisites are present
    try { console.debug('[runSeg.start]', { currentPath: this.viewer.currentPath, lastBbox: this.lastBbox }); } catch(e){}
    if (!this.viewer.currentPath || !this.lastBbox) { console.debug('[runSeg.abort]', { currentPath: this.viewer.currentPath, lastBbox: this.lastBbox }); return; }
    const b  = this.lastBbox;
    const iW = this.viewer.imgW, iH = this.viewer.imgH;
    const sx = Math.max(0,Math.round(b.x)), sy=Math.max(0,Math.round(b.y));
    const ex = Math.min(iW,sx+Math.round(b.w)), ey=Math.min(iH,sy+Math.round(b.h));
    const safe = {x:sx,y:sy,w:ex-sx,h:ey-sy};
    if (safe.w<4||safe.h<4) { this._toast('請框選/塗抹稍大的區域','warn'); return; }

    // [M3] Use method cycle appropriate for current tool
    const cycle  = this.fabMode==='brush' ? SEG_CYCLE_BRUSH : SEG_CYCLE_BOX;
    const method = cycle[this.segCycleIdx % cycle.length];
    document.getElementById('seg-method').value = method;

    this._setPend(`⏳ 自動偵測中（${method}）…`, false);

    try {
      // [BUG #1] Send brush mask for mask-guided segmentation
      const segReq = {
        path:this.viewer.currentPath, bbox:safe, method,
        wc:this.viewer.wc, ww:this.viewer.ww,
      };
      if (this.fabMode === 'brush') {
        segReq.brush_mask_b64 = this.viewer.getBrushMaskBase64?.();
      }
      
      // Debug: log segmentation request summary to console
      try {
        console.debug('[segreq]', { method, fabMode: this.fabMode, hasMask: !!segReq.brush_mask_b64, maskLen: segReq.brush_mask_b64 ? segReq.brush_mask_b64.length : 0, bbox: segReq.bbox });
      } catch(e){/* ignore */}

      const r = await API.segment(segReq);
      if (r.success && r.polygon?.length>=3) {
        this.viewer.pendingPolygon = r.polygon;
        this.viewer.pendingBbox    = safe;
        document.getElementById('accept-btn').disabled = false;
        this._setPend(`✨ 偵測到 ${r.polygon.length} 個頂點，確認加入？`, true);
      } else {
        this._setPend('⚠ 未找到輪廓，試試「↺ 換方法」或重新繪製', true);
      }
    } catch(e) { this._setPend('❌ '+e.message, true); console.error('[seg]',e); }
  }

  _setPend(msg, showBtns) {
    document.getElementById('pend-txt').textContent = msg;
    document.getElementById('pend-bar').style.display = 'flex';
    document.querySelector('.pend-btns').style.visibility = showBtns?'visible':'hidden';
  }

  // [M4] After accept: deselect → ALL annotations show on canvas
  _accept() {
    const ann = this.annMgr.acceptPending();
    if (!ann) { this._toast('無法接受：分割結果無效','err'); return; }
    this._closePending();
    this.viewer.selectedId = null;     // [M4]
    this._activateTool('pan');
    this.annMgr.renderList();
    this._toast('✓ 已加入標註','ok');
    this._showFAB();
    this._hint(`已加入 ${this.annMgr.list.length} 個標註，繼續標記或按 S 儲存`);
  }

  // [M5] Accept + immediately enter vertex edit mode
  _adjustThenSave() {
    const ann = this.annMgr.acceptPending();
    if (!ann) { this._toast('無法接受：分割結果無效','err'); return; }
    this._closePending();        // [M6] clears brush inside
    this.annMgr.renderList();
    this.viewer.selectedId = ann.id;
    this._activateTool('edit');
    this._hint('拖曳 ● 黃點微調頂點，完成後按 S 儲存');
    this._toast('✏ 微調模式：拖曳黃點後按 S 儲存','warn');
    this._showFAB();
  }

  // [M6] Clear brush canvas when closing pending if was in brush mode
  _closePending() {
    document.getElementById('pend-bar').style.display='none';
    document.getElementById('accept-btn').disabled=true;
    this.viewer.pendingPolygon=null;
    this.viewer.pendingBbox=null;
    this.segCycleIdx=0;
    if (this.fabMode==='brush') this.viewer.clearBrush?.();
  }

  _retry() {
    this.segCycleIdx++;
    const cycle  = this.fabMode==='brush' ? SEG_CYCLE_BRUSH : SEG_CYCLE_BOX;
    const next   = cycle[this.segCycleIdx % cycle.length];
    this._toast(`切換至 ${next}`,'warn');
    this._runSeg();
  }

  _discard() {
    this._closePending();
    this.viewer.selectedId = null;
    this._activateTool('pan');
    this._showFAB();
  }

  // ══════════════════════════════════════════════════════════ SAVE ════

  // [M7] Deselect + exit edit mode on save so all annotations visible
  async _save() {
    if (!this.annMgr.sopUid) { this._toast('請先開啟影像','err'); return; }
    document.getElementById('save-btn').disabled=true;
    try {
      const ok = await this.annMgr.save();
      if (ok) {
        await this._recHistory();
        await this._loadHistory();
        document.querySelector('.fi.active')?.querySelector('.fi-dot')?.classList.add('done');
        this._updateCounts();
        await this._markAnnotated();
        // [M7] Exit edit mode, deselect
        this.viewer.selectedId = null;
        this._activateTool('pan');
        this.annMgr.renderList();
        this._toast('儲存完成 ✓','ok');
      } else { this._toast('儲存失敗','err'); }
    } finally { document.getElementById('save-btn').disabled=false; }
  }

  async _recHistory() {
    const meta=this.viewer.currentMeta||{}, path=this.viewer.currentPath||'';
    try {
      await API.addHistory({
        sop_uid:this.annMgr.sopUid, path, filename:path.split(/[/\\]/).pop(),
        annotation_count:this.annMgr.list.length,
        classes:[...new Set(this.annMgr.list.map(a=>a.class))],
        patient_id:meta.PatientID||'', modality:meta.Modality||'',
        image_size:[this.viewer.imgW, this.viewer.imgH],
      });
    } catch {}
  }

  // ══════════════════════════════════════════════════════ HISTORY ════

  async _loadHistory() {
    try { const {records}=await API.getHistory(); this._histRecords=records||[]; } catch {}
  }

  _renderHistoryInDrawer(body) {
    const recs=this._histRecords||[];
    if (!recs.length) {
      body.innerHTML='<p style="color:var(--dim);font-size:11px;padding:10px 0">尚無記錄。儲存標註後出現在這裡。</p>';
      return;
    }
    body.innerHTML='';
    for (const r of recs) {
      const li=document.createElement('div'); li.className='hi-item';
      const cls=(r.classes||[]).join('、')||'–';
      const cnt=r.annotation_count??0;
      const ts=r.saved_at?this._timeAgo(r.saved_at):'';
      li.innerHTML=
        `<div class="hi-name" title="${this._esc(r.path)}">${this._esc(r.filename||r.sop_uid)}</div>`+
        `<div class="hi-meta">${cnt} 個標註・${cls}・${ts}</div>`+
        `<div class="hi-path">${this._esc(r.path)}</div>`+
        `<button class="hi-del" title="移除">✕</button>`;
      li.querySelector('.hi-del').addEventListener('click', async e=>{
        e.stopPropagation();
        try{await API.deleteHistory(r.sop_uid);}catch{}
        await this._loadHistory(); this.openDrawer('history');
      });
      li.addEventListener('click',async()=>{
        this.closeDrawer();
        const entry=this.files.find(f=>f.path===r.path);
        await this._open(r.path, entry?.el||null);
      });
      body.appendChild(li);
    }
  }

  // ══════════════════════════════════════════════════════ DRAWER ════

  openDrawer(name) {
    const titles={settings:'⚙ 設定',history:'🕐 標註記錄',export:'📤 匯出',folder:'📁 資料夾',keys:'⌨ 快捷鍵'};
    const body=document.getElementById('drawer-body');
    document.getElementById('drawer-title').textContent=titles[name]||name;
    body.innerHTML='';
    this['_drawerContent_'+name]?.(body);
    document.getElementById('backdrop').style.display='';
    document.getElementById('drawer').style.display='flex';
  }

  closeDrawer() {
    document.getElementById('backdrop').style.display='none';
    document.getElementById('drawer').style.display='none';
  }

  _drawerContent_settings(body) {
    body.innerHTML=`
      <div class="d-section">
        <span class="d-label">筆刷工具（R 鍵）</span>
        <span class="d-desc">在 🖌 筆刷模式下塗抹缺陷，放開滑鼠後自動偵測輪廓。</span>
        <div style="display:flex;align-items:center;gap:8px;margin-top:6px">
          <span style="font-size:11px;color:var(--dim)">大小</span>
          <input id="d-brush-sz" type="range" min="3" max="120" value="20" style="flex:1">
          <span id="d-brush-val" style="font-size:11px;color:var(--dim);min-width:28px">20px</span>
        </div>
        <div class="brush-modes" style="margin-top:6px">
          <button class="bm active" data-mode="fg">前景</button>
          <button class="bm" data-mode="bg">背景</button>
          <button class="bm" data-mode="erase">清除</button>
        </div>
        <button class="d-btn danger" id="d-clear-brush" style="margin-top:8px">✗ 清除筆刷</button>
      </div>
      <div class="sep"></div>
      <div class="d-section">
        <span class="d-label">亮度 / 對比</span>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:11px;color:var(--dim);width:24px">WC</span>
          <input id="d-wc" type="range">
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:11px;color:var(--dim);width:24px">WW</span>
          <input id="d-ww" type="range" min="1">
        </div>
        <button class="d-btn" id="d-ww-reset">⊙ 重置預設值</button>
      </div>
      <div class="sep"></div>
      <div class="d-section">
        <button class="d-btn" id="d-history">🕐 標註記錄…</button>
        <button class="d-btn" id="d-export">📤 匯出標註…</button>
        <button class="d-btn" id="d-folder">📁 從資料夾載入…</button>
        <button class="d-btn" id="d-keys">⌨ 快捷鍵…</button>
      </div>`;

    // Brush
    const bsz=document.getElementById('d-brush-sz');
    bsz.addEventListener('input',()=>{
      document.getElementById('d-brush-val').textContent=bsz.value+'px';
      this.tools.brushTool.radius=+bsz.value;
    });
    document.querySelectorAll('.bm').forEach(b=>b.addEventListener('click',()=>{
      document.querySelectorAll('.bm').forEach(x=>x.classList.remove('active'));
      b.classList.add('active'); this.tools.brushTool.mode=b.dataset.mode;
    }));
    document.getElementById('d-clear-brush').addEventListener('click',()=>this.viewer.clearBrush?.());

    // WW sliders sync
    const wcSl=document.getElementById('wc-slider'), wwSl=document.getElementById('ww-slider');
    const dwc=document.getElementById('d-wc'), dww=document.getElementById('d-ww');
    dwc.min=wcSl.min; dwc.max=wcSl.max; dwc.value=wcSl.value;
    dww.min=1; dww.max=wwSl.max; dww.value=wwSl.value;
    const _dw=()=>{
      wcSl.value=dwc.value; wwSl.value=dww.value;
      clearTimeout(this._wwTimer);
      this._wwTimer=setTimeout(()=>this.viewer.applyWindowing(+dwc.value,+dww.value),280);
    };
    dwc.addEventListener('input',_dw); dww.addEventListener('input',_dw);
    document.getElementById('d-ww-reset').addEventListener('click',()=>{
      dwc.value=this.viewer.defaultWC; dww.value=this.viewer.defaultWW;
      _dw();
    });

    document.getElementById('d-history').addEventListener('click',()=>this.openDrawer('history'));
    document.getElementById('d-export').addEventListener('click', ()=>this.openDrawer('export'));
    document.getElementById('d-folder').addEventListener('click', ()=>this.openDrawer('folder'));
    document.getElementById('d-keys').addEventListener('click',   ()=>this.openDrawer('keys'));
  }

  _drawerContent_history(body) { this._renderHistoryInDrawer(body); }

  _drawerContent_export(body) {
    body.innerHTML=`
      <div class="d-section"><span class="d-label">格式</span>
        <div class="radio-grp">
          <label><input type="radio" name="efmt" value="yolo_seg" checked> YOLO Segmentation</label>
          <label><input type="radio" name="efmt" value="yolo_det"> YOLO Detection</label>
          <label><input type="radio" name="efmt" value="coco"> COCO JSON</label>
        </div>
      </div>
      <div class="d-section" style="margin-top:10px"><span class="d-label">範圍</span>
        <div class="radio-grp">
          <label><input type="radio" name="escope" value="current" checked> 目前影像</label>
          <label><input type="radio" name="escope" value="history"> 全部記錄</label>
        </div>
      </div>
      <button class="d-btn primary" id="do-export" style="margin-top:14px">⬇ 下載</button>`;
    document.getElementById('do-export').addEventListener('click',()=>this._doExport());
  }

  _drawerContent_folder(body) {
    body.innerHTML=`
      <div class="d-section"><span class="d-label">根目錄路徑</span>
        <input id="d-root" class="d-input" placeholder="/data/dicom" spellcheck="false">
        <button class="d-btn primary" id="d-load-root" style="margin-top:8px">📂 載入</button>
      </div>`;
    document.getElementById('d-root').addEventListener('keydown',e=>{if(e.key==='Enter')this._loadFolder();});
    document.getElementById('d-load-root').addEventListener('click',()=>this._loadFolder());
  }

  _drawerContent_keys(body) {
    body.innerHTML=`<table class="kb-tbl">
      <tr><td>B</td><td>框選（標記缺陷，矩形）</td></tr>
      <tr><td>R</td><td>筆刷（標記缺陷，手繪）</td></tr>
      <tr><td>H</td><td>平移視窗</td></tr>
      <tr><td>E</td><td>編輯頂點（微調黃點）</td></tr>
      <tr><td>S</td><td>儲存</td></tr>
      <tr><td>N / P</td><td>下一張 / 上一張</td></tr>
      <tr><td>F</td><td>符合螢幕</td></tr>
      <tr><td>+ / −</td><td>放大 / 縮小</td></tr>
      <tr><td>Del</td><td>刪除選取的標註</td></tr>
      <tr><td>Esc</td><td>取消標記 / 捨棄分割 / 取消選取</td></tr>
    </table>`;
  }

  async _loadFolder() {
    const root=(document.getElementById('d-root')?.value||'').trim();
    if (!root){this._toast('請輸入路徑','err');return;}
    try {
      const data=await API.getFiles(root);
      this._flatTree(data.tree||[]);
      this._updateCounts();
      await this._markAnnotated();
      this.closeDrawer();
      this._toast(`載入 ${data.total} 個檔案`,'ok');
    } catch(e){this._toast('載入失敗：'+e.message,'err');}
  }

  _flatTree(nodes) {
    nodes.forEach(n=>n.type==='folder'?this._flatTree(n.children||[]):this._addFile(n.path));
  }

  async _markAnnotated() {
    try {
      const {paths, details}=await API.getAnnotatedPaths();
      this._annotatedDetails = details || {};
      const set=new Set(paths);
      this.files.forEach(f=>{
        const hasAnn = set.has(f.path);
        const info = this._annotatedDetails[f.path] || { count: 0, has_notes: 0 };
        const dot = f.el.querySelector('.fi-dot');
        if (dot) {
          if (hasAnn) dot.classList.add('done');
          else dot.classList.remove('done');
        }
        const countSpan = f.el.querySelector('.fi-ann-count');
        if (countSpan) {
          countSpan.textContent = info.count > 0 ? `${info.count} 個` : '0';
          countSpan.style.opacity = info.count > 0 ? '1' : '0.4';
        }
        const noteSpan = f.el.querySelector('.fi-note-status');
        if (noteSpan) {
          noteSpan.textContent = info.has_notes ? '📝' : '';
        }
      });
    } catch {}
  }

  async _doExport() {
    const fmt  =document.querySelector('input[name="efmt"]:checked')?.value;
    const scope=document.querySelector('input[name="escope"]:checked')?.value;
    let items=[];
    if (scope==='current'){
      const it=this.annMgr.toExportItem(); if(it)items.push(it);
    } else {
      try {
        const {records}=await API.getHistory();
        for (const r of records){
          const doc=await API.getAnnotations(r.sop_uid).catch(()=>null);
          if(!doc?.annotations?.length)continue;
          items.push({image_path:r.path,sop_uid:r.sop_uid,
            width:doc.image_info?.width||512,height:doc.image_info?.height||512,
            annotations:doc.annotations});
        }
      } catch(e){this._toast('讀取記錄失敗','err');return;}
    }
    if(!items.length){this._toast('沒有標註可匯出','err');return;}
    try {
      let blob,fname;
      if(fmt==='yolo_seg'){blob=await API.exportYoloSeg({items});fname='yolo_seg.zip';}
      else if(fmt==='yolo_det'){blob=await API.exportYoloDet({items});fname='yolo_det.zip';}
      else{blob=await API.exportCoco({items});fname='coco.json';}
      const url=URL.createObjectURL(blob),a=document.createElement('a');
      Object.assign(a,{href:url,download:fname}); document.body.appendChild(a); a.click();
      setTimeout(()=>{URL.revokeObjectURL(url);a.remove();},1200);
      this.closeDrawer(); this._toast(`匯出完成 → ${fname}`,'ok');
    } catch(e){this._toast('匯出失敗：'+e.message,'err');}
  }

  // ══════════════════════════════════════════════════════ BIND ALL ════

  _bindAll() {
    this._bindDrop();
    // global click debug (temporary for E2E tracing)
    document.addEventListener('click', e=>{ try{ console.debug('[GLOBAL.CLICK]', e.target?.id, e.target?.className); }catch(e){} });
    // global mouseup debug (detect if mouseup events fire during Playwright interactions)
    document.addEventListener('mouseup', e=>{ try{ console.debug('[GLOBAL.MOUSEUP]', e.type, e.target?.id); }catch(e){} });

    // Settings + save
    document.getElementById('settings-btn').addEventListener('click',()=>this.openDrawer('settings'));
    document.getElementById('save-btn').addEventListener('click',()=>this._save());

    // Toolbar: view controls
    document.getElementById('fit-btn').addEventListener('click', ()=>{this.viewer.fitToScreen();this.updateZoomDisplay();});
    document.getElementById('zin-btn').addEventListener('click', ()=>{this.viewer.zoomStep(1.3);this.updateZoomDisplay();});
    document.getElementById('zout-btn').addEventListener('click',()=>{this.viewer.zoomStep(1/1.3);this.updateZoomDisplay();});
    document.getElementById('ww-reset').addEventListener('click', ()=>this._resetWW());

    const _ww=()=>{
      this.updateWindowingDisplay();
      clearTimeout(this._wwTimer);
      this._wwTimer=setTimeout(()=>this.viewer.applyWindowing(
        +document.getElementById('wc-slider').value,
        +document.getElementById('ww-slider').value
      ),280);
    };
    document.getElementById('wc-slider').addEventListener('input',_ww);
    document.getElementById('ww-slider').addEventListener('input',_ww);

    // FAB mode selector
    const _setFabMode=mode=>{
      this.fabMode=mode;
      try { console.debug('[setFabMode]',{mode,stack:(new Error()).stack.split('\n').slice(1,4)}); } catch(e){}
      document.getElementById('fab-mode-box').classList.toggle('active',mode==='box');
      document.getElementById('fab-mode-brush').classList.toggle('active',mode==='brush');
    };
    document.getElementById('fab-mode-box').addEventListener('click',e=>{e.stopPropagation();_setFabMode('box');});
    document.getElementById('fab-mode-box').addEventListener('pointerup',e=>{e.stopPropagation();_setFabMode('box');});
    document.getElementById('fab-mode-brush').addEventListener('click',e=>{e.stopPropagation();_setFabMode('brush');});
    document.getElementById('fab-mode-brush').addEventListener('pointerup',e=>{e.stopPropagation();_setFabMode('brush');});

    // FAB + pending banner
    document.getElementById('fab').addEventListener('click',()=>this._enterMarkMode());
    document.getElementById('fab').addEventListener('pointerdown',()=>this._enterMarkMode());
    document.getElementById('accept-btn').addEventListener('click', ()=>this._accept());
    document.getElementById('adjust-btn').addEventListener('click', ()=>this._adjustThenSave());
    document.getElementById('retry-btn').addEventListener('click',  ()=>this._retry());
    document.getElementById('discard-btn').addEventListener('click',()=>this._discard());

    // Annotation panel
    document.getElementById('del-all-btn').addEventListener('click',()=>{
      if(confirm('刪除此影像所有標註？'))this.annMgr.removeAll();
    });
    const delSelBtn = document.getElementById('delete-selected-btn');
    if (delSelBtn) delSelBtn.addEventListener('click', ()=>this._deleteSelectedFiles());
    const delCurBtn = document.getElementById('delete-current-btn');
    if (delCurBtn) delCurBtn.addEventListener('click', ()=>this._deleteSelectedFiles());

    // Nav
    document.getElementById('prev-btn').addEventListener('click',()=>this._nav(-1));
    document.getElementById('next-btn').addEventListener('click',()=>this._nav(+1));

    // History item clicks (event delegation)
    document.addEventListener('click',e=>{
      const item=e.target.closest('#drawer-body .hi-item');
      if (!item) return;
      if (e.target.classList.contains('hi-del')){
        e.stopPropagation();
        // handled inside _renderHistoryInDrawer
      }
    });

    // Canvas click selection: allow selecting an annotation by clicking it (helps after load)
    const canvas = document.getElementById('viewer-canvas');
    if (canvas) {
      canvas.addEventListener('click', (e) => {
        try {
          if (this.marking) return; // ignore during marking
          const rect = canvas.getBoundingClientRect();
          const sx = e.clientX - rect.left;
          const sy = e.clientY - rect.top;
          const ip = this.viewer.screenToImage(sx, sy);
          const hit = this.viewer.hitTest(ip.x, ip.y);
          if (hit) this.viewer.selectedId = hit.id;
          else this.viewer.selectedId = null;
          this.annMgr.renderList();
        } catch (err) { console.warn('[canvas.click.select]', err); }
      });
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', e=>{
      if (['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) return;
      switch(e.key.toLowerCase()){
        case 'b': this.fabMode='box';
                  document.getElementById('fab-mode-box').classList.add('active');
                  document.getElementById('fab-mode-brush').classList.remove('active');
                  this._enterMarkMode(); break;
        case 'r': this.fabMode='brush';
                  document.getElementById('fab-mode-brush').classList.add('active');
                  document.getElementById('fab-mode-box').classList.remove('active');
                  this._enterMarkMode(); break;
        case 'h': this._activateTool('pan'); break;
        case 'e': this._activateTool('edit'); break;
        case 's': e.preventDefault(); this._save(); break;
        case 'n': this._nav(+1); break;
        case 'p': this._nav(-1); break;
        case 'f': this.viewer.fitToScreen(); this.updateZoomDisplay(); break;
        case '+': case '=': this.viewer.zoomStep(1.3);   this.updateZoomDisplay(); break;
        case '-':            this.viewer.zoomStep(1/1.3); this.updateZoomDisplay(); break;
        case 'escape':
          if (this.marking)                  { this._exitMarkMode(); break; }
          if (this.viewer.pendingPolygon)    { this._discard();      break; }
          this.viewer.selectedId=null; this._activateTool('pan'); this.annMgr.renderList();
          break;
        case 'delete': case 'backspace':
          if (e.shiftKey) { this._deleteSelectedFiles(); break; }
          if (this.viewer.selectedId) this.annMgr.remove(this.viewer.selectedId);
          break;
      }
    });
  }

  _activateTool(name) {
    document.querySelectorAll('.tool-btn[data-tool]').forEach(b=>b.classList.toggle('active',b.dataset.tool===name));
    this.tools.setTool(name);

    // Auto-select first annotation when entering edit mode (improves save→load→edit flow)
    if (name === 'edit' && !this.viewer.selectedId && this.annMgr.list && this.annMgr.list.length) {
      this.viewer.selectedId = this.annMgr.list[0].id;
      this.annMgr.renderList();
    }
    
    // [BUG #3 FIX] Enable right-click to delete vertices in edit mode
    const canvas = document.getElementById('viewer-canvas');
    if (!canvas) return;
    
    // Remove old contextmenu handler if any
    if (this._contextMenuHandler) {
      canvas.removeEventListener('contextmenu', this._contextMenuHandler);
      this._contextMenuHandler = null;
    }
    
    // Add contextmenu handler for edit tool
    if (name === 'edit') {
      this._contextMenuHandler = (e) => {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const screenX = e.clientX - rect.left;
        const screenY = e.clientY - rect.top;
        const imgCoords = this.viewer.screenToImage(screenX, screenY);
        try {
          const editTool = (this.tools && (this.tools.editTool || this.tools.edit));
          if (imgCoords && editTool && typeof editTool.tryDeleteVertex === 'function' && editTool.tryDeleteVertex(imgCoords)) {
            this._hint('✓ 已刪除頂點');
          }
        } catch (err) { console.warn('[contextmenu.delete]', err); }
      };
      canvas.addEventListener('contextmenu', this._contextMenuHandler);
    }
  }

  _resetWW() {
    document.getElementById('wc-slider').value=this.viewer.defaultWC;
    document.getElementById('ww-slider').value=this.viewer.defaultWW;
    this.viewer.applyWindowing(this.viewer.defaultWC, this.viewer.defaultWW);
    this.updateWindowingDisplay();
  }

  _nav(delta) {
    if(!this.files.length)return;
    const idx=Math.max(0,Math.min(this.files.length-1, this.fileIdx+delta));
    if(idx===this.fileIdx)return;
    const f=this.files[idx];
    this._open(f.path,f.el);
  }

  _updateNavLabel(){
    const n=this.files.length, i=this.fileIdx>=0?this.fileIdx+1:0;
    document.getElementById('nav-lbl').textContent=n?`${i}/${n}`:'–';
  }

  _updateCounts(){
    const total=this.files.length;
    const done =document.querySelectorAll('.fi-dot.done').length;
    document.getElementById('file-count').textContent=`${total} 張`;
    document.getElementById('ann-badge').textContent=`${done} 標完`;
    document.getElementById('prog-text').textContent=`${done} / ${total}`;
    document.getElementById('prog-fill').style.width=total?(done/total*100)+'%':'0%';
    if(total>0) document.getElementById('file-list-hdr').style.display='flex';
  }

  // Multi-file selection helpers
  _toggleFileSelection(el, path, shift) {
    const idx = this.files.findIndex(f => f.path === path);
    if (idx < 0) return;
    if (shift && this._lastSelectedFileIdx != null) {
      const a = Math.min(this._lastSelectedFileIdx, idx);
      const b = Math.max(this._lastSelectedFileIdx, idx);
      for (let i = a; i <= b; i++) {
        const f = this.files[i];
        f.el.classList.add('multi-selected');
        this._selectedFiles.add(f.path);
      }
    } else {
      if (this._selectedFiles.has(path)) {
        this._selectedFiles.delete(path);
        el.classList.remove('multi-selected');
      } else {
        this._selectedFiles.add(path);
        el.classList.add('multi-selected');
      }
    }
    this._lastSelectedFileIdx = idx;
    this._updateCounts();
    const delBtn = document.getElementById('delete-selected-btn');
    if (delBtn) delBtn.style.display = this._selectedFiles.size ? '' : 'none';
  }

  _clearFileSelection() {
    if (!this._selectedFiles.size) return;
    for (const p of Array.from(this._selectedFiles)) {
      const entry = this.files.find(f => f.path === p);
      if (entry) entry.el.classList.remove('multi-selected');
    }
    this._selectedFiles.clear();
    this._lastSelectedFileIdx = null;
    this._updateCounts();
    const delBtn = document.getElementById('delete-selected-btn');
    if (delBtn) delBtn.style.display = 'none';
  }

  async _deleteSelectedFiles() {
    let toDelete = [];
    if (this._selectedFiles.size > 0) {
      toDelete = Array.from(this._selectedFiles);
    } else if (this.viewer.currentPath) {
      toDelete = [this.viewer.currentPath];
    } else {
      this._toast('沒有可刪除的檔案', 'err'); 
      return;
    }
    
    const preview = toDelete.slice(0, 10).map(p => p.split(/[/\\]/).pop()).join('\n');
    const msg = toDelete.length === 1 
      ? `確定刪除當前影像檔案？\n\n${preview}\n\n此動作將從磁碟與資料庫移除，無法還原。`
      : `確定刪除 ${toDelete.length} 個檔案？\n\n${preview}${toDelete.length > 10 ? '\n...' : ''}\n\n此動作將從磁碟與資料庫移除，無法還原。`;
      
    if (!confirm(msg)) return;
    try {
      const resp = await API.deleteFiles(toDelete, true);
      const deleted = new Set(resp.deleted || []);
      
      const remainingFiles = [];
      for (const f of this.files) {
        if (deleted.has(f.path)) {
          try { f.el.remove(); } catch(e){}
        } else {
          remainingFiles.push(f);
        }
      }
      this.files = remainingFiles;
      this.fileIdx = this.viewer.currentPath ? this.files.findIndex(f => f.path === this.viewer.currentPath) : -1;
      this._updateNavLabel();

      for (const p of deleted) {
        // if current open image deleted, clear viewer & annotations
        if (this.viewer.currentPath === p) {
          this.viewer.currentPath = null;
          this.viewer.currentMeta = null;
          this.viewer.img = null;
          this.viewer.imgLoaded = false;
          this.viewer.annotations = [];
          this.viewer.selectedId = null;
          this.annMgr.list = [];
          this.annMgr._sync();
          this.annMgr.renderList();
        }
      }
      this._clearFileSelection();
      this._updateCounts();
      this._toast(`刪除 ${deleted.size} 個檔案`,'ok');
    } catch(e) {
      console.error('[deleteFiles]', e);
      this._toast('刪除失敗：'+e.message,'err');
    }
  }

  // ══════════════════════════════════════════════════════ HELPERS ════

  _setMsg(t)  { const e=document.getElementById('canvas-msg'); if(e){e.textContent=t;e.style.display=t?'':'none';} }
  _showFAB()  { const g=document.getElementById('fab-group'); if(g)g.style.display='flex'; }
  _hideFAB()  { const g=document.getElementById('fab-group'); if(g)g.style.display='none'; }
  _hint(t)    {
    const h=document.getElementById('step-hint');
    if(!h)return; h.textContent=t; h.style.display='';
    clearTimeout(this._ht);
    this._ht=setTimeout(()=>{h.style.display='none';},3500);
  }

  // Called by viewer.js and tools.js
  updateZoomDisplay()  { document.getElementById('sb-zoom').textContent=Math.round(this.viewer.scale*100)+'%'; }
  updatePointer(x,y)   { document.getElementById('sb-pos').textContent=`x:${x} y:${y}`; }
  updateWindowingDisplay() {
    const wc = document.getElementById('wc-slider').value;
    const ww = document.getElementById('ww-slider').value;
    const wcVal = document.getElementById('wc-value');
    const wwVal = document.getElementById('ww-value');
    if (wcVal) wcVal.textContent = wc;
    if (wwVal) wwVal.textContent = ww;
  }
  updateWindowFromDrag(wc,ww){
    document.getElementById('wc-slider').value=Math.round(wc);
    document.getElementById('ww-slider').value=Math.round(ww);
    this.updateWindowingDisplay();
    clearTimeout(this._wwTimer);
    this._wwTimer=setTimeout(()=>this.viewer.applyWindowing(wc,ww),280);
  }
  // [M8] renderAnnList also updates del-all-btn
  renderAnnList(){ this.annMgr.renderList(); }

  _toast(msg,type=''){
    const e=document.getElementById('toast');
    e.textContent=msg; e.className='toast '+type; e.style.display='';
    clearTimeout(this._tt); this._tt=setTimeout(()=>{e.style.display='none';},2800);
  }
  _esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  _timeAgo(iso){
    const s=Math.floor((Date.now()-new Date(iso).getTime())/1000);
    if(isNaN(s)||s<0)return''; if(s<60)return'剛才'; if(s<3600)return`${Math.floor(s/60)}分前`;
    if(s<86400)return`${Math.floor(s/3600)}小時前`; return`${Math.floor(s/86400)}天前`;
  }
}

let App;
document.addEventListener('DOMContentLoaded', ()=>{ new AppController(); });
