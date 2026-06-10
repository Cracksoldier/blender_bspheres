# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Blender addon (`bSpheres`) that emulates zBrush's zSpheres for fast base-mesh creation. It wraps Blender's existing single-vertex + Mirror/Skin/Subdivision-Surface modifier workflow behind a single panel so users can sketch base meshes by extruding/scaling vertices, then bake the result into a sculptable mesh.

This is a fork of [PapaTemporal/blender_bspheres](https://github.com/PapaTemporal/blender_bspheres), updated for the Blender Extensions system (4.2+).

Target runtime: **Blender 4.2 LTS through 5.x**, packaged as an **Extension**. Metadata lives in `blender_manifest.toml` (`blender_version_min = "4.2.0"`), not in a `bl_info` dict — the legacy `bl_info` blocks were removed when the addon was converted to the Extensions system. The code is `bpy`/`bmesh` only — there is no lint or test tooling, no third-party dependency, and no entry point outside Blender.

## Running and testing

There is no CLI or test harness — the addon only runs inside Blender. It is an Extension, so install/build go through the extension tooling:

- **Validate manifest:** `blender --command extension validate .` (from the repo folder).
- **Build:** `blender --command extension build` → produces `bspheres-<version>.zip`.
- **Install:** Blender *Preferences → Get Extensions → Install from Disk*, select the zip, enable it. The panel appears in the 3D Viewport N-panel under the **bSpheres** tab.
- **Iterate:** edit the `.py` files and toggle the extension off/on (or use *Reload Scripts*). Because it loads as a package, the relative import `from . bSpheres import *` in `__init__.py` resolves normally.

Validate changes by exercising the full flow manually in Blender: **Create** → extrude/scale/move verts → adjust Mirror axes, Subdivision level, and bSkin Settings → **Preview / Refresh** → **Make bSkin** → **Apply**. There is no automated coverage to rely on.

## CI / release

- **`.github/workflows/ci.yml`** — runs on every branch push and PR: byte-compiles the Python files and runs `blender --command extension validate`. Tag pushes are skipped (handled by the release workflow).
- **`.github/workflows/release.yml`** — manual `workflow_dispatch`. Takes a version string, bumps `blender_manifest.toml`, downloads Blender 4.2 LTS into `/tmp` (not the repo root), validates and builds the extension zip, commits the bump, pushes a `v<version>` tag, and publishes a GitHub Release with the zip attached.

## Docs

- **`docs/index.html`** — self-contained GitHub Pages landing page (no external dependencies). Deployed via Pages with source = `main /docs`.
- **`docs/favicon.svg`** — orange sphere icon matching the site's accent colour.
- Both files are excluded from the packaged extension via `[build].paths_exclude_pattern` in the manifest.

## Architecture

Two Python files plus the extension manifest:

- **`blender_manifest.toml`** — extension metadata (id, version, `blender_version_min`, license, tags). This is the source of truth for what used to be `bl_info`.
- **`__init__.py`** — entry point: `register()`/`unregister()` register all classes from `bSpheres.py`. `BSpheresSkinSettings` must be registered first (before the `PointerProperty` assignment) and unregistered last. No `bl_info` (the manifest replaces it).
- **`bSpheres.py`** — all behavior: one `PropertyGroup`, seven operators, one panel, and six module-level helper functions.

The registered classes and how they fit together:

- **`BSpheresSkinSettings`** (`bpy.types.PropertyGroup`) — per-object output settings: `voxel_size`, `use_voxel_remesh`, `use_smooth_shading`, `use_merge_doubles`, `merge_threshold`, `use_recalc_normals`, `warn_thin_branches`, `min_branch_radius`. Attached to every Blender object via `bpy.types.Object.bspheres_skin_settings`. Persists in the `.blend` file. Read by `MakeBSkin`, `PreviewBSkin`, and `applyBSphereModifiers` to control post-bake processing.
- **`AddBMesh`** (`mesh.primitive_bsphere_add`, "Create" button) — builds an 8-vertex box via `add_box()`, merges all verts to center to get a single vertex, then stacks three modifiers (**Mirror**, **Skin**, **Subdivision**), enters Edit mode with x-ray on, and marks the skin root. This single-vertex-plus-skin setup *is* the "zSphere" the user then extrudes.
- **`MakeBSkin`** (`bspheres.make_bskin`, "Make bSkin" button) — non-destructive permanent bake. Evaluates the modifier stack via the depsgraph (`new_from_object`), creates a new plain mesh in `bSpheres_Output`, applies post-bake settings (remesh, smooth), and returns the user to their previous mode. The control object is untouched; each run produces a new output object.
- **`PreviewBSkin`** (`bspheres.preview_bskin`, "Preview / Refresh" button) — non-destructive on-demand preview. Same bake logic as `MakeBSkin` but places output in `bSpheres_Preview` and tags it with `obj["bspheres_preview"] = True` / `obj["bspheres_source"] = source_name`. On re-run, replaces the existing preview object's mesh data in-place (same object, updated geometry) so the Outliner stays clean.
- **`DeleteBSkinPreview`** (`bspheres.delete_bskin_preview`, "Delete" button) — removes the preview object and its mesh datablock for the active bSphere. Poll is wired to `_find_preview_obj` so the button greys out automatically when no preview exists.
- **`applyBSphereModifiers`** (`tcg.apply_bsphere_modifiers`, "Apply" button) — **destructive** bake. Applies the three modifiers directly onto the control object, then conditionally voxel-remeshes, runs `_run_mesh_cleanup`, and shade-smooths using the same `bspheres_skin_settings` as the non-destructive operators. Use when done iterating.
- **`BSphereMarkPreserve`** (`bspheres.mark_preserve`, "Mark Preserve" button) — adds selected vertices in EDIT mode to the `bspheres_preserve` vertex group. Preserved vertices are skipped by `_warn_thin_branches`. Poll-guarded to EDIT_MESH mode on bSphere control objects only. Saves/restores `vertex_groups.active_index` so the user's active group is not clobbered.
- **`BSphereClearPreserve`** (`bspheres.clear_preserve`, "Clear Preserve" button) — removes selected vertices from the `bspheres_preserve` group. Same guard and save/restore pattern as `BSphereMarkPreserve`.
- **`BSpheresPanel`** (`OBJECT_PT_bSpheres_Panel`) — the UI. Introspects `context.object.modifiers` and surfaces the live Mirror axes, Subdivision `levels`, and Skin loose/root marking. The "bSkin Settings", "Preview", and "Convert" sections are only drawn when `_is_bsphere_control(obj)` is true. In EDIT_MESH mode, also draws a "Selected Node" section when a vertex is active in `bm.select_history`, showing live skin radius and root/loose flags (read from `bm.verts.layers.skin`, not from the RNA mesh layer) plus Mark/Clear Preserve buttons.

### Module-level helpers in `bSpheres.py`

- **`_is_bsphere_control(obj)`** — returns True if `obj` is a mesh with MIRROR, SKIN, and SUBSURF modifiers all present. Used as the `poll` guard for `MakeBSkin`, `PreviewBSkin`, `applyBSphereModifiers`, and the settings/preview panel section.
- **`_ensure_collection(name, scene)`** — finds or creates a named collection and ensures it is linked to the current scene. Used by `MakeBSkin` (`bSpheres_Output`) and `PreviewBSkin` (`bSpheres_Preview`).
- **`_apply_bskin_settings(obj, settings, context)`** — applies post-bake processing to a mesh object: voxel remesh (with active+selected object swap), then `_run_mesh_cleanup`, then shade smooth. Order matters: cleanup and smooth run after remesh so they apply to the final geometry.
- **`_find_preview_obj(source_name)`** — searches `bSpheres_Preview` for an object tagged with `bspheres_source == source_name`. Used by `PreviewBSkin` (refresh path) and `DeleteBSkinPreview.poll`.
- **`_warn_thin_branches(operator, source_obj, settings)`** — iterates the source object's skin vertices (read in OBJECT mode after `mode_set` flush) and calls `operator.report({'WARNING'}, …)` for any vertex whose skin radius is below `settings.min_branch_radius`. Skips vertices that are in the `bspheres_preserve` vertex group. Must be called **after** `mode_set(OBJECT)` so the RNA mesh layer reflects the current BMesh state.
- **`_run_mesh_cleanup(obj, settings, context)`** — enters EDIT mode on `obj`, optionally runs `mesh.merge_by_distance` and/or `mesh.normals_make_consistent`, then returns to OBJECT mode. Deselects all other selected objects first so `mode_set(EDIT)` cannot enter multi-object edit and run the cleanup on them (e.g. the still-selected control object during a non-destructive bake). Saves/restores the active object and all selection state. Uses `try/finally` so everything is restored even if an operator raises. No-ops immediately if both `use_merge_doubles` and `use_recalc_normals` are False.

### Cross-file coupling to watch

- **Mode round-trip.** `AddBMesh.execute` stashes `context.mode` into `context.scene['previous_mode']`, and `applyBSphereModifiers.execute` reads it back. `MakeBSkin` and `PreviewBSkin` capture mode locally and restore it. All use `_MODE_SET_MAP` to normalize `EDIT_MESH` → `EDIT` etc. Remesh, cleanup, and smooth all run **before** `mode_set` restore — `voxel_remesh` and `_run_mesh_cleanup` both require OBJECT mode entry points. `_warn_thin_branches` must also be called **after** `mode_set(OBJECT)` (not before) so the RNA `skin_vertices` layer is flushed from the BMesh.
- **Settings coupling.** `BSpheresSkinSettings` is the single source of truth for all bake settings. All three bake operators (`MakeBSkin`, `PreviewBSkin`, `applyBSphereModifiers`) read from it. `applyBSphereModifiers` does NOT use the `_apply_bskin_settings` helper (the object is already active there, so no active-object swap is needed) but must be kept in sync with any logic changes.
- **Per-node preserve flag.** The `bspheres_preserve` vertex group is the per-vertex flag for "preserve thickness". Vertex groups survive edit-mode extrude/delete more reliably than mesh attributes. `BSphereMarkPreserve` and `BSphereClearPreserve` manage this group; `_warn_thin_branches` reads it to skip preserved vertices.
- **Skin data in EDIT mode.** `obj.data.skin_vertices[0].data[i].radius` is the RNA mesh layer — only valid in OBJECT mode (stale in EDIT mode until `mode_set(OBJECT)` flushes the BMesh). Whenever skin vertex data must be read in EDIT mode (panel display), use `bm.verts.layers.skin[0]` on the already-open BMesh instead.
- **Modifier matching.** The panel and all operator polls locate modifiers by `modifier.type` (`MIRROR`/`SKIN`/`SUBSURF`), so `.001` name suffixes don't break them.
- **Collection hygiene.** `_ensure_collection` guards against multi-scene blend files by checking `context.scene.collection.children_recursive` before linking (recursive, so a collection the user nested elsewhere in the scene is not linked a second time at the root). `bSpheres_Output` (permanent) and `bSpheres_Preview` (temporary) are separate collections.
- The `width`/`height`/`depth` props on `AddBMesh` size the throwaway box before it is merged to a point, so they have no visible effect on the final single-vertex result.
