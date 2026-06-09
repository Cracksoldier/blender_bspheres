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
- **`bSpheres.py`** — all behavior: one `PropertyGroup`, five operators, one panel, and four module-level helper functions.

The registered classes and how they fit together:

- **`BSpheresSkinSettings`** (`bpy.types.PropertyGroup`) — per-object output settings: `voxel_size`, `use_voxel_remesh`, `use_smooth_shading`. Attached to every Blender object via `bpy.types.Object.bspheres_skin_settings`. Persists in the `.blend` file. Read by `MakeBSkin`, `PreviewBSkin`, and `applyBSphereModifiers` to control post-bake processing.
- **`AddBMesh`** (`mesh.primitive_bsphere_add`, "Create" button) — builds an 8-vertex box via `add_box()`, merges all verts to center to get a single vertex, then stacks three modifiers (**Mirror**, **Skin**, **Subdivision**), enters Edit mode with x-ray on, and marks the skin root. This single-vertex-plus-skin setup *is* the "zSphere" the user then extrudes.
- **`MakeBSkin`** (`bspheres.make_bskin`, "Make bSkin" button) — non-destructive permanent bake. Evaluates the modifier stack via the depsgraph (`new_from_object`), creates a new plain mesh in `bSpheres_Output`, applies post-bake settings (remesh, smooth), and returns the user to their previous mode. The control object is untouched; each run produces a new output object.
- **`PreviewBSkin`** (`bspheres.preview_bskin`, "Preview / Refresh" button) — non-destructive on-demand preview. Same bake logic as `MakeBSkin` but places output in `bSpheres_Preview` and tags it with `obj["bspheres_preview"] = True` / `obj["bspheres_source"] = source_name`. On re-run, replaces the existing preview object's mesh data in-place (same object, updated geometry) so the Outliner stays clean.
- **`DeleteBSkinPreview`** (`bspheres.delete_bskin_preview`, "Delete" button) — removes the preview object and its mesh datablock for the active bSphere. Poll is wired to `_find_preview_obj` so the button greys out automatically when no preview exists.
- **`applyBSphereModifiers`** (`tcg.apply_bsphere_modifiers`, "Apply" button) — **destructive** bake. Applies the three modifiers directly onto the control object, then conditionally voxel-remeshes and shade-smooths using the same `bspheres_skin_settings` as the non-destructive operators. Use when done iterating.
- **`BSpheresPanel`** (`OBJECT_PT_bSpheres_Panel`) — the UI. Introspects `context.object.modifiers` and surfaces the live Mirror axes, Subdivision `levels`, and Skin loose/root marking. The "bSkin Settings", "Preview", and "Convert" sections are only drawn when `_is_bsphere_control(obj)` is true, so they do not appear on non-bSphere objects.

### Module-level helpers in `bSpheres.py`

- **`_is_bsphere_control(obj)`** — returns True if `obj` is a mesh with MIRROR, SKIN, and SUBSURF modifiers all present. Used as the `poll` guard for `MakeBSkin`, `PreviewBSkin`, and the settings/preview panel section.
- **`_ensure_collection(name, scene)`** — finds or creates a named collection and ensures it is linked to the current scene. Used by `MakeBSkin` (`bSpheres_Output`) and `PreviewBSkin` (`bSpheres_Preview`).
- **`_apply_bskin_settings(obj, settings, context)`** — applies post-bake processing to a mesh object: voxel remesh (with active+selected object swap) then shade smooth. Order matters: smooth runs after remesh so it applies to the final geometry.
- **`_find_preview_obj(source_name)`** — searches `bSpheres_Preview` for an object tagged with `bspheres_source == source_name`. Used by `PreviewBSkin` (refresh path) and `DeleteBSkinPreview.poll`.

### Cross-file coupling to watch

- **Mode round-trip.** `AddBMesh.execute` stashes `context.mode` into `context.scene['previous_mode']`, and `applyBSphereModifiers.execute` reads it back. `MakeBSkin` and `PreviewBSkin` capture mode locally and restore it. All use `_MODE_SET_MAP` to normalize `EDIT_MESH` → `EDIT` etc. Remesh and smooth run **before** `mode_set` restore in all operators — `voxel_remesh` requires OBJECT mode.
- **Settings coupling.** `BSpheresSkinSettings` is the single source of truth for voxel size, remesh toggle, and shade-smooth toggle. All three bake operators (`MakeBSkin`, `PreviewBSkin`, `applyBSphereModifiers`) read from it. `applyBSphereModifiers` does NOT use the `_apply_bskin_settings` helper (the object is already active there, so no active-object swap is needed) but must be kept in sync with any logic changes.
- **Modifier matching.** The panel and all operator polls locate modifiers by `modifier.type` (`MIRROR`/`SKIN`/`SUBSURF`), so `.001` name suffixes don't break them.
- **Collection hygiene.** `_ensure_collection` guards against multi-scene blend files by checking `context.scene.collection.children` before linking. `bSpheres_Output` (permanent) and `bSpheres_Preview` (temporary) are separate collections.
- The `width`/`height`/`depth` props on `AddBMesh` size the throwaway box before it is merged to a point, so they have no visible effect on the final single-vertex result.
