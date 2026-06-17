/* annotations.js  v3-final
 *
 * BUG FIXES vs previous version
 * ─────────────────────────────
 * [A1] renderList: CSS class corrected to match style.css (.ann-lbl)
 * [A2] renderList: show/hide del-all-btn + empty-state li
 * [A3] renderList: update ann-count pill
 * [A4] add(): v.selectedId set AFTER list.push + _sync() so viewer sees new item
 * [A5] load(): reset v.selectedId to null so ALL annotations show on canvas
 * [A6] acceptPending: guards degenerate polygon (all same point)
 */
class AnnotationManager {
  constructor(viewer) {
    this.v      = viewer;
    this.list   = [];
    this.sopUid = null;
    this.dirty  = false;
    this._ctr   = 1;
    this._currentPath = null;
    this._currentMeta = null;
    this._colours = {
      hole:'#40c4ff', crack:'#ff5252', void:'#40c4ff', defect:'#40c4ff', default:'#b0bec5',
    };
    this._listEl  = document.getElementById('ann-list');
    this._countEl = document.getElementById('ann-count');
    this.comments = [];
    this.annotator_history = [];

    // 監聽類別下拉選單變更，以支援編修選中標註的類別
    const selectEl = document.getElementById('defect-class');
    if (selectEl) {
      selectEl.addEventListener('change', () => {
        const selectedId = this.v.selectedId;
        if (selectedId) {
          const newClass = selectEl.value;
          this.update(selectedId, { class: newClass });
          this.v.draw();
        }
      });
    }

    // 監聽防護具部位下拉選單變更，以支援編修選中標註的部位
    const partSelectEl = document.getElementById('apron-part-class');
    if (partSelectEl) {
      partSelectEl.addEventListener('change', () => {
        const selectedId = this.v.selectedId;
        if (selectedId) {
          const newPart = partSelectEl.value;
          this.update(selectedId, { apron_part: newPart });
          this.v.draw();
        }
      });
    }

    // 監聽備註框變更以解鎖儲存
    const notesEl = document.getElementById('image-notes');
    if (notesEl) {
      notesEl.addEventListener('input', () => {
        this.dirty = true;
        this._notifyDirty();
        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) saveBtn.disabled = false;
      });
    }
  }

  setContext(path, meta) {
    this._currentPath = path;
    this._currentMeta = meta;
    this.sopUid = (meta.SOPInstanceUID || '').trim() || path;
  }

  _uid() { return 'ann_' + Date.now() + '_' + (this._ctr++); }

  _currentClass() {
    return document.getElementById('defect-class')?.value || 'defect';
  }

  _currentApronPart() {
    return document.getElementById('apron-part-class')?.value || 'none';
  }

  // ── CRUD ────────────────────────────────────────────────────────────────

  add(partial) {
    const x = +(partial.x ?? 0), y = +(partial.y ?? 0);
    const w = +(partial.w ?? 0), h = +(partial.h ?? 0);
    const ann = {
      id:       this._uid(),
      class:    partial.class || this._currentClass(),
      apron_part: partial.apron_part || this._currentApronPart(),
      type:     partial.type  || 'box',
      x, y, w, h,
      polygon:  partial.polygon || null,
      bbox:     partial.bbox || (w > 0 ? [x,y,w,h] : null),
      auto:     partial.auto || false,
      method:   partial.method || null,
      created:  new Date().toISOString(),
      modified: new Date().toISOString(),
    };
    this.list.push(ann);     // mutate in place so viewer sees it via _sync reference
    this._sync();
    this.v.selectedId = ann.id;   // [A4] after push
    this.dirty = true;
    this._notifyDirty();
    this.renderList();
    return ann;
  }

  update(annOrId, changes) {
    const ann = typeof annOrId === 'object'
      ? annOrId : this.list.find(a => a.id === annOrId);
    if (!ann) return;
    Object.assign(ann, changes, { modified: new Date().toISOString() });
    this.dirty = true;
    this._notifyDirty();
    this.renderList();
  }

  remove(id) {
    const idx = this.list.findIndex(a => a.id === id);
    if (idx < 0) return;
    this.list.splice(idx, 1);
    if (this.v.selectedId === id) this.v.selectedId = null;
    this._sync();
    this.dirty = true;
    this._notifyDirty();
    this.renderList();
  }

  removeAll() {
    this.list = [];
    this.v.selectedId = null;
    this._sync();
    this.dirty = true;
    this._notifyDirty();
    this.renderList();
  }

  select(id) {
    this.v.selectedId = id;
    this.renderList();
    if (id) {
      const ann = this.list.find(a => a.id === id);
      if (ann) {
        // 連動類別下拉選單
        const selectEl = document.getElementById('defect-class');
        if (selectEl) {
          let val = ann.class;
          if (val === 'defect' || val === 'void') val = 'hole';
          selectEl.value = val;
        }
        // 連動防護具部位下拉選單
        const partSelectEl = document.getElementById('apron-part-class');
        if (partSelectEl) {
          partSelectEl.value = ann.apron_part || 'none';
        }
      }
    }
  }

  // ── accept pending segmentation polygon ─────────────────────────────────

  acceptPending() {
    const poly = this.v.pendingPolygon;
    if (!poly || poly.length < 3) return null;

    // [A6] Reject degenerate polygon (all points identical)
    const xs = poly.map(p=>p[0]), ys = poly.map(p=>p[1]);
    if (Math.max(...xs)-Math.min(...xs) < 2 && Math.max(...ys)-Math.min(...ys) < 2) return null;

    const pb   = this.v.pendingBbox;
    const bbox = pb ? [pb.x, pb.y, pb.w, pb.h] : this._polyBbox(poly);
    const [bx, by, bw, bh] = bbox;

    const ann = this.add({
      type:    'polygon',
      class:   this._currentClass(),
      apron_part: this._currentApronPart(),
      x:bx, y:by, w:bw, h:bh,
      polygon: poly.map(p => [Math.round(p[0]), Math.round(p[1])]),
      bbox, auto:true,
      method:  document.getElementById('seg-method')?.value || '',
    });

    this.v.pendingPolygon = null;
    this.v.pendingBbox    = null;
    return ann;
  }

  _polyBbox(pts) {
    const xs=pts.map(p=>p[0]), ys=pts.map(p=>p[1]);
    const x=Math.min(...xs), y=Math.min(...ys);
    return [x, y, Math.max(...xs)-x, Math.max(...ys)-y];
  }

  // ── persistence ─────────────────────────────────────────────────────────

  // ── persistence ─────────────────────────────────────────────────────────

  renderCommentsAndHistory() {
    // Render comments list
    const notesHistoryList = document.getElementById('notes-history-list');
    if (notesHistoryList) {
      notesHistoryList.innerHTML = '';
      const comments = this.comments || [];
      if (comments.length === 0) {
        notesHistoryList.innerHTML = '<div style="color:var(--dim);text-align:center;padding:10px 0;">尚無備註留言</div>';
      } else {
        comments.forEach(c => {
          const item = document.createElement('div');
          item.style = 'border-bottom: 1px solid var(--b1); padding-bottom: 4px; display:flex; flex-direction:column; gap:2px;';
          
          let timeStr = '';
          if (c.created_at) {
            try {
              const d = new Date(c.created_at);
              timeStr = `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
            } catch(e) { timeStr = c.created_at; }
          }
          
          const header = document.createElement('div');
          header.style = 'display:flex; justify-content:space-between; font-size:9.5px;';
          header.innerHTML = `<span style="color:#ffb74d;font-weight:bold;">✍ ${c.annotator || '未指定'}</span><span style="color:var(--dim);">${timeStr}</span>`;
          
          const body = document.createElement('div');
          body.style = 'color:var(--tx); padding-left: 2px; word-break: break-all;';
          body.textContent = c.text || '';
          
          item.appendChild(header);
          item.appendChild(body);
          notesHistoryList.appendChild(item);
        });
      }
    }

    // Render annotator history list
    const historyList = document.getElementById('annotator-history-list');
    if (historyList) {
      historyList.innerHTML = '';
      const history = this.annotator_history || [];
      if (history.length === 0) {
        historyList.innerHTML = '<div style="color:var(--dim);text-align:center;padding:10px 0;">尚無修改歷程</div>';
      } else {
        history.forEach(h => {
          const item = document.createElement('div');
          item.style = 'border-bottom: 1px dashed var(--b1); padding-bottom: 2px; display:flex; justify-content:space-between;';
          
          let timeStr = '';
          if (h.saved_at) {
            try {
              const d = new Date(h.saved_at);
              timeStr = `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
            } catch(e) { timeStr = h.saved_at; }
          }
          item.innerHTML = `<span style="color:var(--tx);font-weight:bold;">${h.annotator || '未指定'}</span><span style="color:var(--dim); text-align:center; flex:1; padding:0 4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${h.action || '存檔'}">${h.action || '存檔'}</span><span style="font-size:9px;color:var(--dim2);">${timeStr}</span>`;
          historyList.appendChild(item);
        });
      }
    }
  }

  async save() {
    if (!this.sopUid) return false;
    const annotatorVal = document.getElementById('annotator-input')?.value.trim() || '未指定';
    const payload = {
      image_path: this._currentPath || '',
      dicom_meta: this._currentMeta || {},
      image_info: { width:this.v.imgW, height:this.v.imgH, wc:this.v.wc, ww:this.v.ww },
      notes: document.getElementById('image-notes')?.value || '',
      annotator: annotatorVal,
      comments: this.comments || [],
      annotations: this.list.map(a => ({
        id:a.id, class:a.class, type:a.type,
        apron_part: a.apron_part || 'none',
        bbox_x:a.x, bbox_y:a.y, bbox_w:a.w, bbox_h:a.h,
        polygon:a.polygon, bbox:a.bbox,
        auto:a.auto, method:a.method,
        created:a.created, modified:a.modified,
      })),
    };
    try {
      await API.saveAnnotations(this.sopUid, payload);
      this.dirty = false;
      this._notifyDirty();

      // 重新載入以更新歷程與留言
      const doc = await API.getAnnotations(this.sopUid);
      this.comments = doc.comments || [];
      this.annotator_history = doc.annotator_history || [];
      this.renderCommentsAndHistory();

      // 即時更新左側列表呈現的標註者名單
      if (window._app) {
        const annotators = Array.from(new Set(
          (this.annotator_history || []).map(h => h.annotator).concat((this.comments || []).map(c => c.annotator))
        )).filter(Boolean);
        
        const matched = window._app.files.find(f => f.path === this._currentPath);
        if (matched) {
          this._currentMeta = this._currentMeta || {};
          this._currentMeta.Annotators = annotators;
          this._currentMeta.annotator_history = this.annotator_history;
          this._currentMeta.comments = this.comments;
          window._app._updateFileLabel(this._currentPath, this._currentMeta);
        }
      }

      return true;
    } catch(e) { console.error('[ann] save:', e); return false; }
  }

  async load(path, meta) {
    this.setContext(path, meta);
    // Keep first annotation selected after load to allow immediate editing
    try {
      const doc = await API.getAnnotations(this.sopUid);
      
      // 載入協同備註
      const notesEl = document.getElementById('image-notes');
      if (notesEl) notesEl.value = doc.notes || '';

      // 載入留言與修改歷程
      this.comments = doc.comments || [];
      this.annotator_history = doc.annotator_history || [];

      // 舊版備註相容移轉：若有舊備註且未曾在留言板出現過，將其自動轉為留言與歷程
      if (doc.notes && doc.notes.trim()) {
        const textExists = this.comments.some(c => c.text === doc.notes.trim());
        if (!textExists) {
          this.comments.unshift({
            annotator: '16724',
            text: doc.notes.trim(),
            created_at: doc.saved_at || new Date().toISOString()
          });
          if (this.annotator_history.length === 0) {
            this.annotator_history.push({
              annotator: '16724',
              saved_at: doc.saved_at || new Date().toISOString(),
              action: '建立影像備註'
            });
          }
          this.dirty = true;
          this._notifyDirty();
        }
      }

      this.renderCommentsAndHistory();

      this.list = (doc.annotations || []).map(a => {
        const bxRaw = a.bbox_x ?? (a.bbox ? a.bbox[0] : (a.x ?? 0));
        const byRaw = a.bbox_y ?? (a.bbox ? a.bbox[1] : (a.y ?? 0));
        const bwRaw = a.bbox_w ?? (a.bbox ? a.bbox[2] : (a.w ?? 0));
        const bhRaw = a.bbox_h ?? (a.bbox ? a.bbox[3] : (a.h ?? 0));
        const bx = Math.round(Number(bxRaw || 0));
        const by = Math.round(Number(byRaw || 0));
        const bw = Math.round(Number(bwRaw || 0));
        const bh = Math.round(Number(bhRaw || 0));
        const polygon = a.polygon ? a.polygon.map(p => [Math.round(Number(p[0])), Math.round(Number(p[1]))]) : null;
        return {
          id: a.id || this._uid(),
          class: a.class || 'defect',
          apron_part: a.apron_part || 'none',
          type: a.type || 'polygon',
          x: bx, y: by, w: bw, h: bh,
          polygon: polygon,
          bbox: a.bbox ? a.bbox.map(v => Math.round(Number(v))) : [bx, by, bw, bh],
          auto: a.auto || false, method: a.method || null,
          created: a.created || '', modified: a.modified || '',
        };
      });
    } catch { this.list = []; this.comments = []; this.annotator_history = []; }
    this.dirty = false;
    this._notifyDirty();
    // Auto-select first annotation to allow immediate edit after reload
    if (this.list && this.list.length) {
      this.v.selectedId = this.list[0].id;
    } else {
      this.v.selectedId = null;
    }
    this._sync();
    this.renderList();
  }

  toExportItem() {
    if (!this._currentPath) return null;
    return {
      image_path:  this._currentPath,
      sop_uid:     this.sopUid || this._currentPath,
      width:       this.v.imgW,
      height:      this.v.imgH,
      annotations: this.list.map(a => ({
        id:a.id, class:a.class,
        polygon:a.polygon||null,
        bbox:a.bbox||(a.w>0?[a.x,a.y,a.w,a.h]:null),
      })),
    };
  }

  // ── render ──────────────────────────────────────────────────────────────

  renderList() {
    if (!this._listEl) return;
    this._listEl.innerHTML = '';

    // [A2] empty state
    if (!this.list.length) {
      const li = document.createElement('li');
      li.className = 'ann-empty';
      li.textContent = '尚未標記任何缺陷';
      this._listEl.appendChild(li);
      if (this._countEl) this._countEl.textContent = '0';
      const btn = document.getElementById('del-all-btn');
      if (btn) btn.style.display = 'none';
      return;
    }

    // [A2] show del-all-btn
    const btn = document.getElementById('del-all-btn');
    if (btn) btn.style.display = '';

    // [A3] update count
    if (this._countEl) this._countEl.textContent = this.list.length;

    for (const ann of this.list) {
      const li = document.createElement('li');
      li.className = 'ann-item' + (ann.id === this.v.selectedId ? ' selected' : '');
      li.dataset.id = ann.id;

      const dot = document.createElement('span');
      dot.className = 'ann-dot';
      dot.style.background = this._colours[ann.class] || this._colours.default;

      const lbl = document.createElement('span');
      lbl.className = 'ann-lbl';   // matches .ann-lbl in style.css
      const icon = ann.type === 'polygon' ? '⬟' : '▣';
      const dispNames = { hole: '破洞', void: '破洞', defect: '破洞', crack: '裂痕' };
      const dispName = dispNames[ann.class] || ann.class;
      
      const partNames = { none: '', cap: '鉛帽', neck: '鉛頸', vest: '半身', skirt: '鉛裙', suit: '連身' };
      const partName = partNames[ann.apron_part || 'none'] || '';
      const partPrefix = partName ? `[${partName}] ` : '';
      
      lbl.textContent = `${icon} ${partPrefix}${dispName}`;
      lbl.title = `ID: ${ann.id.slice(-8)}\nPart: ${partName || '未指定'}\nType: ${ann.type}\nMethod: ${ann.method||'manual'}\nPos: (${ann.x},${ann.y}) ${ann.w}×${ann.h}`;

      const del = document.createElement('button');
      del.className = 'ann-del'; del.textContent = '✕'; del.title = '刪除';
      del.addEventListener('click', ev => { ev.stopPropagation(); this.remove(ann.id); });

      li.append(dot, lbl, del);
      li.addEventListener('click', () => { this.select(ann.id); this.renderList(); });
      li.addEventListener('dblclick', () => { this.select(ann.id); try{ window.App && window.App._activateTool && window.App._activateTool('edit'); }catch(e){} });
      this._listEl.appendChild(li);
    }
  }

  // ── internals ────────────────────────────────────────────────────────────

  _sync() { this.v.annotations = this.list; }

  _notifyDirty() {
    const dot = document.getElementById('dirty-dot');
    if (dot) dot.style.display = this.dirty ? '' : 'none';
  }
}
