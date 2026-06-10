/* api.js  –  typed fetch wrappers  v3
 *
 * CRITICAL FIX: Annotation endpoints now use ?sop_uid= query param,
 * NOT path segment.  This avoids the Starlette router bug where
 * %2F (encoded slash) gets decoded to "/" before routing,
 * making paths like /annotations//data/file.dcm → 404 → empty load.
 */
const API = (() => {
  const BASE = '/api';

  async function _req(method, url, body) {
    const opts = { method };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body    = JSON.stringify(body);
    }
    const r = await fetch(BASE + url, opts);
    if (!r.ok) { const t = await r.text(); throw new Error(t || r.statusText); }
    return r.json();
  }
  const _get  = url       => _req('GET',    url);
  const _post = (url, b)  => _req('POST',   url, b);
  const _del  = url       => _req('DELETE', url);

  async function _postForm(url, formData) {
    const r = await fetch(BASE + url, { method: 'POST', body: formData });
    if (!r.ok) { const t = await r.text(); throw new Error(t || r.statusText); }
    return r.json();
  }
  async function _postBlob(url, body) {
    const r = await fetch(BASE + url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) { const t = await r.text(); throw new Error(t || r.statusText); }
    return r.blob();
  }

  const _qp = v => encodeURIComponent(v);   // safe query-param encoding

  return {
    // ── DICOM ──────────────────────────────────────────────────────────
    getFiles:    r    => _get(`/files?root=${_qp(r)}`),
    getImage:    (p, wc, ww) => _get(`/image?path=${_qp(p)}&wc=${wc}&ww=${ww}`),
    getMetadata: p    => _get(`/metadata?path=${_qp(p)}`),

    // ── Upload ─────────────────────────────────────────────────────────
    uploadDicom:       f  => { const fd = new FormData(); fd.append('file', f); return _postForm('/upload', fd); },
    listUploaded:      () => _get('/uploaded'),
    getAnnotatedPaths: () => _get('/annotated_paths'),

    // ── Segmentation ───────────────────────────────────────────────────
    segment:    b => _post('/segment', b),
    getMethods: () => _get('/segment/methods'),

    // ── Annotations  (query-param API — fixes slash-in-path bug) ───────
    getAnnotations:  sop     => _get(`/annotations?sop_uid=${_qp(sop)}`),
    saveAnnotations: (sop,d) => _post(`/annotations?sop_uid=${_qp(sop)}`, d),
    deleteAnnotation:(sop,id)=> _del(`/annotations/one?sop_uid=${_qp(sop)}&ann_id=${_qp(id)}`),
    listAnnotated:   ()      => _get('/annotated'),

    // ── History  (query-param API) ─────────────────────────────────────
    getHistory:    ()    => _get('/history'),
    addHistory:    e     => _post('/history', e),
    deleteHistory: sop   => _del(`/history/one?sop_uid=${_qp(sop)}`),

    // ── Export ─────────────────────────────────────────────────────────
    exportYoloSeg: b => _postBlob('/export/yolo_seg', b),
    exportYoloDet: b => _postBlob('/export/yolo_det', b),
    exportCoco:    b => _postBlob('/export/coco',     b),

    // ── Files (batch operations)
    deleteFiles: (paths, remove_annotations = true) => _post('/files/delete', { paths, remove_annotations }),
  };
})();
