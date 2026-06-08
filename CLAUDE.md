# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Blender addon (`bSpheres`) that emulates zBrush's zSpheres for fast base-mesh creation. It wraps Blender's existing single-vertex + Mirror/Skin/Subdivision-Surface modifier workflow behind a single panel so users can sketch base meshes by extruding/scaling vertices, then bake the result into a sculptable mesh.

Target runtime: **Blender 4.2 LTS through 5.x**, packaged as an **Extension**. Metadata lives in `blender_manifest.toml` (`blender_version_min = "4.2.0"`), not in a `bl_info` dict — the legacy `bl_info` blocks were removed when the addon was converted to the Extensions system. The code is `bpy`/`bmesh` only — there is no lint or test tooling, no third-party dependency, and no entry point outside Blender.

## Running and testing

There is no CLI or test harness — the addon only runs inside Blender. It is an Extension, so install/build go through the extension tooling:

- **Validate manifest:** `blender --command extension validate .` (from the repo folder).
- **Build:** `blender --command extension build` → produces `bspheres-<version>.zip`.
- **Install:** Blender *Preferences → Get Extensions → Install from Disk*, select the zip, enable it. The panel appears in the 3D Viewport N-panel under the **bSpheres** tab.
- **Iterate:** edit the `.py` files and toggle the extension off/on (or use *Reload Scripts*). Because it loads as a package, the relative import `from . bSpheres import *` in `__init__.py` resolves normally.

Validate changes by exercising the full flow manually in Blender: **Create** → extrude/scale/move verts → adjust Mirror axes & Subdivision level → **Apply**. There is no automated coverage to rely on.

## Architecture

Two Python files plus the extension manifest:

- **`blender_manifest.toml`** — extension metadata (id, version, `blender_version_min`, license, tags). This is the source of truth for what used to be `bl_info`.
- **`__init__.py`** — entry point: `register()`/`unregister()` register the three classes from `bSpheres.py`. No `bl_info` (the manifest replaces it).
- **`bSpheres.py`** — all behavior: two operators and one panel.

The three registered classes and how they fit together:

- **`AddBMesh`** (`mesh.primitive_bsphere_add`, "Create" button) — builds an 8-vertex box via `add_box()`, merges all verts to center to get a single vertex, then stacks three modifiers (**Mirror**, **Skin**, **Subdivision**), enters Edit mode with x-ray on, and marks the skin root. This single-vertex-plus-skin setup *is* the "zSphere" the user then extrudes.
- **`applyBSphereModifiers`** (`tcg.apply_bsphere_modifiers`, "Apply" button) — bakes the three modifiers into mesh data, turns off x-ray, then voxel-remeshes at `remesh_voxel_size = 0.01` so overlapping skin volumes fuse into one watertight, sculptable mesh.
- **`BSpheresPanel`** (`OBJECT_PT_bSpheres_Panel`) — the UI. It does **not** own most controls; instead it introspects `context.object.modifiers` and surfaces the live Mirror axes, Subdivision `levels`, and Skin loose/root marking by binding directly to the built-in Blender operators (`object.skin_root_mark`, `object.skin_loose_mark_clear`) and modifier properties. The panel's contents therefore depend entirely on the modifier stack `AddBMesh` created.

### Cross-file coupling to watch

- **Mode round-trip via scene custom prop.** `AddBMesh.execute` stashes `context.mode` into `context.scene['previous_mode']` (a custom ID-property on the active scene), and `applyBSphereModifiers.execute` reads it back to restore the mode after baking. Because `context.mode` returns values like `EDIT_MESH` that `mode_set()` rejects, the `_MODE_SET_MAP` table at the top of `bSpheres.py` normalizes them on restore. Any change to one operator's mode handling must keep the other (and the map) in sync.
- **Modifier matching.** The panel and `applyBSphereModifiers` both locate modifiers by `modifier.type` (`MIRROR`/`SKIN`/`SUBSURF`), so a `.001` name suffix doesn't break them. `AddBMesh` still sets up the freshly-created stack by the default names `"Skin"`/`"Subdivision"` — safe there because the object is brand new.
- The `width`/`height`/`depth` props on `AddBMesh` size the throwaway box before it is merged to a point, so they have no visible effect on the final single-vertex result.
