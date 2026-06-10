# 🧪 Bug Fixes Testing Checklist

**Status**: Ready for Manual Validation  
**Date**: 2026-06-09  
**Target**: User manual browser testing

---

## Summary of Fixes

| # | Bug | Status | Evidence |
|---|-----|--------|----------|
| 3 | Right-click vertex deletion | ✅ IMPLEMENTED | contextmenu listener in main.js |
| 2 | Brush canvas opacity | ✅ IMPLEMENTED | opacity 0.35 in viewer.js |
| 1 | Brush mask segmentation | ✅ PHASE 1 | API accepts brush_mask_b64 |

---

## ✅ Verification Checklist

### Pre-Testing
- [x] App is running at http://localhost:8005
- [x] All source files modified and saved
- [x] No syntax errors in JavaScript/Python
- [x] API endpoints responding
- [x] Test documentation created

### BUG #3: Vertex Deletion
- [ ] **TEST**: Create annotation (box or brush)
- [ ] **TEST**: Switch to EDIT mode (✎ button)
- [ ] **TEST**: Right-click on a vertex (corner point)
  - [ ] **EXPECTED**: Vertex is deleted
  - [ ] **EXPECTED**: Hint shows "✓ 已刪除頂點" or similar
  - [ ] **EXPECTED**: Polygon updates on canvas
- [ ] **VERIFY**: Can delete multiple vertices
- [ ] **VERIFY**: Cannot delete below 3 vertices (triangle minimum)
- [ ] **PASS/FAIL**: Mark result

### BUG #2: Brush Opacity
- [ ] **TEST**: Select BRUSH mode (🖌 button)
- [ ] **TEST**: Draw a stroke across image
  - [ ] **EXPECTED**: Green stroke appears
  - [ ] **EXPECTED**: Original DICOM image visible through stroke
  - [ ] **EXPECTED**: NOT an opaque green rectangle
- [ ] **VERIFY**: Opacity appears to be ~35% (semi-transparent)
- [ ] **VERIFY**: Image details visible through brush
- [ ] **VERIFY**: Brush clears after segmentation confirmation
- [ ] **PASS/FAIL**: Mark result

### BUG #1: Brush Mask Transmission
- [ ] **SETUP**: Open DevTools (F12) before starting test
- [ ] **SETUP**: Switch to Network tab
- [ ] **TEST**: Draw brush stroke
- [ ] **OBSERVATION**: POST request to /api/segment should appear
- [ ] **CLICK**: Open the request details
- [ ] **LOOK**: For request payload/body containing:
  ```json
  {
    "image_b64": "...",
    "brush_mask_b64": "...",  ← LOOK FOR THIS
    "method": "grabcut",
    "roi": [...]
  }
  ```
- [ ] **VERIFY**: brush_mask_b64 field is present
- [ ] **VERIFY**: brush_mask_b64 contains base64 data (not empty)
- [ ] **VERIFY**: Field length > 100 bytes (indicates actual mask data)
- [ ] **PASS/FAIL**: Mark result

### Integration Tests
- [ ] **TEST**: Multiple annotations on same image
  - [ ] Draw 2+ annotations (mix box and brush)
  - [ ] Verify all appear in annotation list
  - [ ] Switch tools between annotations
- [ ] **TEST**: Multi-image workflow
  - [ ] Upload 2+ images
  - [ ] Annotate first image
  - [ ] Switch to second image, annotate
  - [ ] Switch back to first image
  - [ ] Verify annotations persist
- [ ] **TEST**: Save and reload
  - [ ] Create 2+ annotations
  - [ ] Click save (💾 button)
  - [ ] Refresh page (F5)
  - [ ] Verify annotations still present

### Edge Cases
- [ ] **TEST**: Edit after save
  - [ ] Save annotations
  - [ ] Switch to EDIT mode
  - [ ] Modify vertices (add/delete)
  - [ ] Save again
  - [ ] Reload - modifications should persist
- [ ] **TEST**: Delete all annotations
  - [ ] Create 2+ annotations
  - [ ] Click "全刪" (delete all)
  - [ ] Verify all removed from list
- [ ] **TEST**: Cancel/discard operations
  - [ ] Draw brush stroke
  - [ ] Click "✕ 取消" (cancel) instead of confirm
  - [ ] Brush should clear, no annotation created

---

## 📋 Test Results Template

### BUG #3 Test Result
```
Outcome: [ ] PASS  [ ] FAIL  [ ] PARTIAL
Observations:
- Right-click vertex deletion: _______________
- Hint/feedback message: _______________
- Polygon updates: _______________

Issues found:
- _______________
- _______________
```

### BUG #2 Test Result
```
Outcome: [ ] PASS  [ ] FAIL  [ ] PARTIAL
Observations:
- Brush opacity visual: _______________
- Image visibility through brush: _______________
- Stroke rendering quality: _______________

Issues found:
- _______________
- _______________
```

### BUG #1 Test Result
```
Outcome: [ ] PASS  [ ] FAIL  [ ] PARTIAL
Observations:
- API request captured: _______________
- brush_mask_b64 field present: _______________
- Data content/length: _______________

Issues found:
- _______________
- _______________
```

---

## 🎯 Success Criteria

✅ **BUG #3 PASS** = Right-click reliably deletes vertices in EDIT mode

✅ **BUG #2 PASS** = Brush stroke is semi-transparent (~35% opacity)

✅ **BUG #1 PASS** = Network tab shows brush_mask_b64 in API request

✅ **ALL TESTS PASS** = Application is production-ready

---

## 📝 Notes for Tester

1. **Be Patient with Network Tab**
   - Make sure Network tab is open BEFORE drawing
   - Sometimes requests take 1-2 seconds to appear
   - Refresh the tab if requests don't show

2. **Multiple Attempts OK**
   - Test each bug 2-3 times to confirm consistency
   - Try different positions/sizes for drawing
   - Verify with multiple images if possible

3. **Record Everything**
   - Take screenshots of both PASS and any FAIL states
   - Note any UI messages that appear
   - Describe any unexpected behavior

4. **Post-Test Actions**
   - If all PASS: Mark bugs as resolved ✅
   - If any FAIL: Collect detailed error info for debugging
   - Report both successes and any issues

---

## 🔗 Reference Links

- **App**: http://localhost:8005
- **Verification Report**: FINAL_VERIFICATION_REPORT.md
- **Quick Start**: BROWSER_TEST_QUICK_START.txt
- **App Logs**: `tail -f /tmp/app.log`

---

Good luck with testing! 🚀
