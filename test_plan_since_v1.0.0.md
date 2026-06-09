# Manual Test Plan — bSpheres features since v1.0.0

Covers all features added after the v1.0.0 release:
- **Feature 01** — Non-destructive Make bSkin operator
- **Feature 02** — Preview / Refresh / Delete preview
- **Feature 03** — bSkin Settings panel (remesh, smooth, Apply post-processing)
- **Feature 04** — Joint cleanup: Merge Doubles, Recalculate Normals, Warn Thin Branches
- **Feature 05** — Per-node properties: Selected Node info, Mark/Clear Preserve

**Prerequisites:** build and install the current extension zip, open a fresh `General`
scene in Blender 4.2+, press N → bSpheres tab.

---

## 1. Make bSkin (Feature 01)

### 1.1 Basic non-destructive bake

1. Click **Create** — a bSphere control object appears and Edit mode opens.
2. Extrude a few vertices (E), scale one (Ctrl+A), then return to Object mode.
3. Click **Make bSkin**.

**Expected:**
- A new object `bSkin` (or `bSkin<suffix>`) appears in the `bSpheres_Output`
  collection in the Outliner.
- The original bSphere control object is **unchanged** — still has Mirror, Skin,
  and Subdivision modifiers; still in Object mode.
- The output object is a plain mesh with no modifiers.

### 1.2 Each run produces a new output object

4. Click **Make bSkin** a second time without changing anything.

**Expected:** A second `bSkin` object is added to `bSpheres_Output`. The first one
is untouched.

### 1.3 Output respects world transform

5. Move the control object (G, X, 2) before baking.
6. Click **Make bSkin**.

**Expected:** The output object sits at the same world position as the control
object — `matrix_world` is copied, not left at the origin.

### 1.4 Mode is restored after baking from Edit mode

7. Enter Edit mode on the control object.
8. Click **Make bSkin** from inside Edit mode.

**Expected:** After the bake the control object returns to Edit mode.

### 1.5 Output name derived from control object name

9. Rename the control object to `bSphereArm`, then click **Make bSkin**.

**Expected:** The output object is named `bSkinArm`.

---

## 2. Preview / Refresh / Delete (Feature 02)

### 2.1 First click creates preview

1. Select a bSphere control object, click **Preview / Refresh**.

**Expected:**
- A `bPreview` object appears in a `bSpheres_Preview` collection.
- The control object is not modified.

### 2.2 Re-click updates in place (no duplicate in Outliner)

2. Enter Edit mode, move a vertex, exit Edit mode, click **Preview / Refresh** again.

**Expected:** No new object appears — the **same** `bPreview` object is updated in
place. `bSpheres_Preview` still shows exactly one object.

### 2.3 Delete removes preview and mesh datablock

3. With the control object selected, click **Delete**.

**Expected:**
- The `bPreview` object disappears from the Outliner.
- The mesh datablock is also removed (no orphaned `bPreview` mesh in Outliner with
  orphan filter enabled).

### 2.4 Delete button greys out when no preview exists

4. After deleting, observe the **Delete** button.

**Expected:** Button is greyed out / unavailable.

### 2.5 Two bSphere objects keep independent previews

5. Create a second bSphere (Create button again).
6. Preview each one separately.

**Expected:** Two independent preview objects in `bSpheres_Preview`. Deleting one
does not remove the other.

---

## 3. bSkin Settings panel and Apply post-processing (Feature 03)

### 3.1 Panel section only appears for bSphere control objects

1. Select a plain mesh cube — confirm **bSkin Settings** section is **not** shown.
2. Select the bSphere control object — confirm it **is** shown.

### 3.2 Voxel remesh on/off

3. Enable **Remesh**, set Size to `0.05`. Click **Make bSkin**.

**Expected:** Output mesh is uniformly voxel-remeshed (roughly uniform triangle
density, no long thin Skin-modifier quads).

4. Disable **Remesh**. Click **Make bSkin** again.

**Expected:** Output retains raw Skin modifier topology.

### 3.3 Shade Smooth toggle

5. Enable **Shade Smooth**, bake — output should have smooth shading.
6. Disable **Shade Smooth**, bake — output should have flat shading.

(Check via right-click on the output mesh in the viewport, or the Face Orientation
overlay color uniformity.)

### 3.4 Apply uses bSkin Settings

7. Select the control object, set Remesh ON (Size 0.04), Shade Smooth ON.
8. Click **Apply**.

**Expected:**
- Mirror, Skin, and Subdivision modifiers are gone from the object.
- The mesh is remeshed and smooth-shaded.
- Mode is restored to what it was before Apply.

### 3.5 Settings persist in the .blend file

9. Save the file, close Blender, reopen.
10. Select the control object, open bSkin Settings.

**Expected:** All settings (voxel size, toggles) match what was saved.

---

## 4. Merge Doubles and Recalculate Normals (Feature 04)

### 4.1 Merge Doubles removes seam vertices

1. Create a bSphere, extrude one arm, bake with **Remesh OFF**, **Merge Doubles ON**,
   threshold `0.001`.
2. Select the output mesh, enter Edit mode, select all, run
   **Mesh → Merge by Distance** with the same threshold.

**Expected:** Blender reports "0 vertices removed" — they were already merged during
bake.

### 4.2 Merge Doubles OFF leaves doubles

3. Bake with **Merge Doubles OFF** and check the same way.

**Expected:** Blender now reports > 0 vertices removed.

### 4.3 Recalculate Normals produces outward-facing normals

4. Enable **Recalculate Normals**, click **Make bSkin**.
5. Select the output, enable the **Face Orientation** overlay (Viewport Overlays →
   Face Orientation).

**Expected:** All faces are blue (outward-facing). No red patches.

### 4.4 No extra undo steps when cleanup is off

6. Disable both **Merge Doubles** and **Recalculate Normals**.
7. Click **Make bSkin**, then open Undo History (Edit → Undo History).

**Expected:** Exactly one step added ("Make bSkin"). No extra "Select" or "Normals"
cleanup steps in the history.

### 4.5 Active object and selection are restored after cleanup

8. Add a plain mesh cube and make it the active object. Then click the bSphere
   control to make it active. Enable **Merge Doubles**, click **Make bSkin**.

**Expected:** After the bake, the active object is back to the bSphere control
(what it was when the operator was invoked). The cube's selection state is
unchanged.

---

## 5. Warn Thin Branches (Feature 04)

### 5.1 Warning fires for a near-zero-radius vertex

1. Create a bSphere, enter Edit mode, select one vertex, press Ctrl+A and drag
   the skin radius down to nearly zero.
2. Ensure **Warn Thin Branches** is ON, Min Radius `0.01`.
3. Exit Edit mode, click **Make bSkin**.

**Expected:** An orange WARNING notification appears in the viewport header, e.g.:
`Vertex 3: skin radius 0.0012×0.0012 is below minimum 0.0100`

### 5.2 Warning fires from Preview too

4. Same setup. Click **Preview / Refresh** instead.

**Expected:** Same WARNING notification fires.

### 5.3 No warning when Warn Thin Branches is off

5. Disable **Warn Thin Branches**, repeat the bake.

**Expected:** No warning notification.

### 5.4 No warning when radius is above threshold

6. Enable **Warn Thin Branches**, set Min Radius to `0.001`.
7. Bake a default-sized bSphere (no vertices shrunk).

**Expected:** No warning — all radii are above the minimum.

### 5.5 Warning fires for all vertices when threshold is very large

8. Set Min Radius to `1.0`, bake a default bSphere.

**Expected:** Warnings fire for every vertex (all radii are below 1.0).

---

## 6. Selected Node info (Feature 05)

### 6.1 Panel section appears in Edit mode on a bSphere

1. Select the bSphere control object, press Tab to enter Edit mode.
2. Click a vertex.

**Expected:** A **Selected Node** section appears in the bSpheres panel showing:
- `Skin: X.XXX × Y.YYY` (the vertex's skin radius)
- `Root: True/False   Loose: True/False`

### 6.2 Section disappears in Object mode

3. Tab back to Object mode.

**Expected:** The **Selected Node** section is gone.

### 6.3 Skin radius updates live without leaving Edit mode

4. Enter Edit mode, select a vertex, note the displayed radius.
5. Press Ctrl+A and drag the skin radius to a different size.

**Expected:** The `Skin:` values in the panel update immediately — no need to
exit/re-enter Edit mode.

### 6.4 Root/Loose flags reflect current state

6. Select a vertex, click **Mark Root** (modifier section button).

**Expected:** `Root: True` appears for that vertex in the Selected Node section.

7. Select a different vertex, click **Mark Loose**.

**Expected:** `Loose: True` for that vertex.

### 6.5 Section absent when no vertex is active

8. In Edit mode, press Alt+A to deselect all.

**Expected:** The **Selected Node** section does not appear.

### 6.6 Section absent on non-bSphere objects

9. Select a plain mesh cube, enter Edit mode.

**Expected:** The **Selected Node** section is not present in the bSpheres panel.

---

## 7. Mark Preserve / Clear Preserve (Feature 05)

### 7.1 Mark Preserve creates vertex group and assigns vertex

1. Enter Edit mode on a bSphere, select one vertex.
2. Click **Mark Preserve**.

**Expected:**
- A `bspheres_preserve` vertex group appears in Properties → Object Data →
  Vertex Groups.
- The selected vertex has weight 1.0 in that group.

### 7.2 Preserve exempts vertex from thin-branch warning

3. Shrink that vertex's skin to near-zero (Ctrl+A), exit Edit mode.
4. Ensure **Warn Thin Branches** ON, Min Radius `0.01`.
5. Click **Make bSkin**.

**Expected:** No warning for that vertex — it is in the preserve group and skipped.

### 7.3 Clear Preserve re-exposes vertex to warning

6. Enter Edit mode, select the preserved vertex, click **Clear Preserve**.
7. Exit Edit mode, click **Make bSkin**.

**Expected:** The WARNING fires for the thin vertex (no longer preserved).

### 7.4 Mark Preserve does not clobber active vertex group

8. In Object mode, create a vertex group named `MyGroup` and make it active
   (highlighted in the Vertex Groups list).
9. Enter Edit mode, select a vertex, click **Mark Preserve**.
10. Exit Edit mode, look at the Vertex Groups list.

**Expected:** `MyGroup` is still the active group.

### 7.5 Clear Preserve does not clobber active vertex group

11. Repeat test 7.4 steps using **Clear Preserve** instead.

**Expected:** `MyGroup` remains the active group.

### 7.6 Clear Preserve is a no-op when no preserve group exists

12. On a freshly created bSphere (no preserve group yet), enter Edit mode,
    select a vertex, click **Clear Preserve**.

**Expected:** Nothing crashes; operator cancels silently (no error).

---

## 8. Regression — core v1.0.0 workflow

These confirm the new code does not break anything that existed before.

### 8.1 Create → Extrude → Apply full pipeline

1. Click **Create**. Edit mode opens on a single-vertex mesh with Mirror, Skin,
   Subdivision modifiers.
2. Extrude several vertices, scale some, move them.
3. Exit Edit mode, click **Apply**.

**Expected:** All three modifiers applied; sculptable mesh remains. No errors.

### 8.2 Mirror axis toggles

4. Create a bSphere. Toggle Mirror X off, then Y on.

**Expected:** Viewport preview updates immediately.

### 8.3 Subdivision Viewport level

5. Drag the **Viewport** slider from 1 to 3.

**Expected:** Mesh becomes progressively smoother.

### 8.4 Mark Root / Mark Loose / Clear Loose

6. Enter Edit mode, select a vertex, click **Mark Root**.
7. Select another vertex, click **Mark Loose**, then **Clear Loose**.

**Expected:** No errors; skin responds visually.

### 8.5 Apply from Edit mode restores mode

8. Enter Edit mode on a bSphere, click **Apply**.

**Expected:** Modifiers applied; user is returned to Edit mode on the resulting
mesh.

---

## 9. Edge cases

### 9.1 Name derivation for non-standard control object names

1. Create a bSphere, rename the control object to a plain name (e.g. `Torso`,
   not `bSphere...`). Click **Make bSkin**.

**Expected:** Output is named `bSkin` (fallback, no suffix extraction crash).

### 9.2 Settings are per-object (no bleed between objects)

2. Create two bSpheres. Set Remesh ON on object A, Remesh OFF on object B.
   Bake both.

**Expected:** Object A's output is remeshed; object B's is raw Skin topology.

### 9.3 Undo after Make bSkin removes the output object

3. Click **Make bSkin**, then Ctrl+Z.

**Expected:** The output object is removed. Control object unchanged.

### 9.4 Redo restores the output object

4. Ctrl+Shift+Z after the undo above.

**Expected:** The output object reappears. No errors.

### 9.5 Preview for two different control objects are independent

5. Create two bSpheres, preview each. Delete the preview for the first.

**Expected:** Only the first preview is removed; the second is unaffected.
