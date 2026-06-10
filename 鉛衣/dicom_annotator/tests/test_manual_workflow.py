#!/usr/bin/env python3
"""
Simplified manual browser test guide with verification steps.
"""
import time

print("""
════════════════════════════════════════════════════════════════════════════
                    🧪 MANUAL BROWSER TESTING GUIDE
════════════════════════════════════════════════════════════════════════════

App is running at: http://localhost:8005

OPEN BROWSER DEVELOPER TOOLS (F12) to monitor Network tab for API calls.

════════════════════════════════════════════════════════════════════════════
TEST PLAN
════════════════════════════════════════════════════════════════════════════

【BUG #3 Test: Vertex Deletion via Right-Click】
────────────────────────────────────────────────────────────────────────────
🎯 Goal: Verify right-click on vertex in EDIT mode deletes it

Steps:
  1. Upload a test image (drag & drop or click upload)
  2. Click "＋ 標記缺陷" button (FAB)
  3. Click "▣ 矩形框選" (should be default)
  4. Draw a rectangle on image (click-drag from ~(100,100) to ~(300,200))
  5. Click "✓ 確認" button to accept annotation
  6. Verify annotation appears in right panel and on canvas
  7. Click "✎ 編輯頂點" to enter EDIT mode
  8. RIGHT-CLICK on one of the vertices (corners of polygon)
  9. ✅ Expected: Vertex is deleted, you see message or visual feedback
  10. Check that annotation in right panel updates

🔍 What to look for:
   • Hint message like "✓ 已刪除頂點" or "Vertex deleted"
   • Polygon on canvas should show fewer vertices
   • Should be able to delete vertices until only 3 left (minimum triangle)

────────────────────────────────────────────────────────────────────────────

【BUG #2 Test: Brush Canvas Opacity】
────────────────────────────────────────────────────────────────────────────
🎯 Goal: Verify brush stroke doesn't heavily obscure original image

Steps:
  1. Upload a test image
  2. Click "＋ 標記缺陷"
  3. Click "🖌 筆刷塗抹" to switch to BRUSH mode
  4. Draw a brush stroke across image (mouse drag)
  5. You should see:
     • Green brush stroke appears
     • Original DICOM image is STILL VISIBLE behind the stroke
     • Stroke is somewhat transparent (opacity ~0.35)
  6. Release mouse - brush stroke stays but remains semi-transparent
  7. ✅ Expected: Original image is clearly visible; brush doesn't obscure it

🔍 What to look for:
   • Brush canvas should be light/translucent
   • You can still see DICOM image values/details through brush stroke
   • NO opaque green rectangle blocking view

⚠️  Previous bug: brush canvas opacity was 0.6 (too opaque)
    Fixed to: 0.35 (more transparent)

────────────────────────────────────────────────────────────────────────────

【BUG #1 Test: Brush Mask Transmission】
────────────────────────────────────────────────────────────────────────────
🎯 Goal: Verify brush_mask_b64 is sent to backend API

Steps:
  1. Open Developer Tools (F12) → Network tab
  2. Upload a test image
  3. Click "＋ 標記缺陷"
  4. Click "🖌 筆刷塗抹"
  5. Draw a brush stroke across image
  6. Release mouse
  7. ✅ Expected: Segmentation runs, check Network tab for POST to /api/segment
  8. Click the request to see request body
  9. In "Request" tab, look for JSON payload
  10. Look for field: "brush_mask_b64"

🔍 What to look for in Network:
   ✅ Request to: POST http://localhost:8005/api/segment
   ✅ Request headers show Content-Type: application/json
   ✅ Request body contains:
       - "image_b64": "..." (base64 image)
       - "brush_mask_b64": "..." (base64 mask) ← NEW
       - "method": "grabcut" or other
       - "roi": [...coordinates...]

Current Status (Phase 1):
   ✅ Frontend sends brush_mask_b64
   ✅ Backend accepts brush_mask_b64 field
   🔄 Backend segmentation not yet using mask (Phase 2)

────────────────────────────────────────────────────────────────────────────

【BONUS: Complete Workflow Test】
────────────────────────────────────────────────────────────────────────────
🎯 Goal: Test box + brush + edit + save in sequence

Steps:
  1. Upload 2 test images
  2. Image 1:
     a. BOX mode: draw 1 rectangle annotation
     b. BRUSH mode: draw 1 brush stroke annotation
     c. EDIT mode: add/delete some vertices
     d. Click "💾 儲存" to save
  3. Image 2:
     a. BOX mode: draw 1 rectangle
     b. Confirm
  4. Switch back to Image 1
  5. Verify all annotations still there
  6. Check file system: data/annotations.json should contain 3 annotations

════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
════════════════════════════════════════════════════════════════════════════

❌ Button not appearing?
   • Refresh page (F5)
   • Check browser console (F12 → Console tab) for errors
   • Verify app is running: curl http://localhost:8005

❌ Brush not drawing?
   • Make sure you're in BRUSH mode (click 🖌 button first)
   • Try drawing in the white canvas area, not edges
   • Check console for JavaScript errors

❌ Right-click delete not working?
   • Make sure you're in EDIT mode (✎ 編輯頂點)
   • Try right-clicking directly on a vertex (corner)
   • Check console for errors

❌ Save button grayed out?
   • Must have at least 1 annotation to save
   • Click "✓ 確認" on pending segmentation first

════════════════════════════════════════════════════════════════════════════
EXPECTED RESULTS SUMMARY
════════════════════════════════════════════════════════════════════════════

BUG #3: ✅ PASS
  Right-click deletes vertex in EDIT mode
  Polygon updates in real-time

BUG #2: ✅ PASS  
  Brush stroke is semi-transparent (opacity 0.35)
  Original image visible through stroke

BUG #1: ✅ PASS (Phase 1)
  Network tab shows brush_mask_b64 in API request
  Backend accepts the field

════════════════════════════════════════════════════════════════════════════

Ready to test? Open http://localhost:8005 in your browser!

════════════════════════════════════════════════════════════════════════════
