# bSpheres NX

> **Fork notice:** This is a fork of [PapaTemporal/blender_bspheres](https://github.com/PapaTemporal/blender_bspheres), updated for Blender 4.2 LTS and newer.

Simulate zBrush-style **zSpheres** in Blender for fast base-mesh creation.

zBrush has a handy tool called zSpheres for blocking out quick base meshes. Blender
has been able to do the same thing for a long time, but the setup was fiddly: you'd
create a single-vertex mesh, then stack three modifiers (Mirror, Skin, Subdivision
Surface) before you could extrude vertices and get the zSphere effect. **bSpheres NX**
wraps all of that behind a single panel so you can just start sketching.

## Compatibility

- **Blender 4.2 LTS and newer (including 5.x).** Ships as a Blender *Extension*
  (`blender_manifest.toml`); the minimum supported version is 4.2.0.
- Earlier Blender releases (2.93–4.1) are not supported by this version.

## Installation

The addon is packaged as an Extension. From this folder you can build a
distributable zip with Blender's command-line tools:

```sh
blender --command extension validate .
blender --command extension build      # produces bspheres-<version>.zip
```

Then in Blender: **Edit → Preferences → Get Extensions → Install from Disk…**, pick
the generated zip, and enable **bSpheres NX**. (For quick local development you can also
drop the folder into your Blender extensions directory and use *Reload Scripts*.)

## Usage

Once enabled, a **bSpheres NX** tab appears in the 3D Viewport sidebar (press <kbd>N</kbd>
to open it).

1. **Create** — builds the single-vertex mesh with the Mirror, Skin, and Subdivision
   modifiers already set up, exposing only the settings that matter.
2. **Mirror Axis (X / Y / Z)** — toggle symmetry on each axis.
3. **Mark Root** — set the selected vertex as the skin root (useful when you plan to
   build bones from the vertices rather than sculpt).
4. **Mark Loose / Clear Loose** — make vertices behave more like a grab brush, pulling
   the skin toward them instead of centering the skin on the vertex.
5. **Viewport** — how much to subdivide the skin. Higher = smoother preview.
6. **bSkin Settings** — per-object output controls (only shown for bSphere control
   objects):
   - **Remesh / Size** — toggle voxel remesh on/off and set the voxel size (default
     0.02). Smaller = finer mesh, slower to compute.
   - **Shade Smooth** — automatically set smooth shading on baked output.
   - **Merge Doubles / Dist** — merge vertices within the given threshold after baking.
     Useful for cleaning up seams left by the Skin modifier.
   - **Recalculate Normals** — run "Recalculate Outside" on the baked mesh to fix
     flipped normals (off by default; the Skin modifier usually produces consistent
     normals already).
   - **Warn Thin Branches / Min Radius** — emit a warning for any vertex whose skin
     radius falls below the minimum (default 0.01). Vertices in the
     `bspheres_preserve` group are exempt. The warning fires during **Make bSkin**
     and **Preview / Refresh**.
7. **Selected Node** (Edit Mode only) — when a vertex is active, shows its live skin
   radius and root/loose flags, plus buttons:
   - **Mark Preserve** — adds the selected vertex to the `bspheres_preserve` group,
     exempting it from the thin-branch warning.
   - **Clear Preserve** — removes the selected vertex from that group.
   - **Select Children** — selects all vertices downstream of the active vertex
     (away from the skin root). Useful for posing a limb or tail as a unit.
   - **Select Parents** — selects all vertices upstream of the active vertex back to
     the skin root. Useful for selecting the spine leading to a joint.
8. **Generate Armature** — creates a Blender armature from the bSphere control mesh.
   Each edge becomes one bone; bones are parented to mirror the vertex graph. The skin
   root vertex (set with **Mark Root**) determines the root bone. Only the unmirrored
   half of the mesh is included — add an Armature Mirror modifier afterwards if needed.
9. **Preview / Refresh** — non-destructive on-demand preview. Creates a temporary mesh
   in a `bSpheres_Preview` collection. Re-clicking updates it in-place so the Outliner
   stays clean. Use **Delete** to remove it.
10. **Make bSkin** — non-destructive permanent bake. Creates a new plain mesh object in a
    `bSpheres_Output` collection without touching the control structure. Each run produces
    a fresh output object named `bSkin…`.
11. **Apply** — destructive bake. Applies all three modifiers directly onto the control
    object, then post-processes using the same bSkin Settings (remesh, smooth, cleanup).
    Use this when you are done iterating.

### Editing shortcuts

While sketching the bSphere in Edit Mode:

- <kbd>E</kbd> — extrude vertices
- <kbd>Ctrl</kbd>+<kbd>A</kbd> — scale the skin at the selected vertex (like scaling a zSphere)
- <kbd>Ctrl</kbd>+<kbd>R</kbd> — select two vertices, then click between them to add a vertex
- <kbd>G</kbd> — move vertices freely from any view

Enjoy!

## License

GNU General Public License v3.0 or later (GPL-3.0-or-later). See [LICENSE](LICENSE).

*Original addon by Abinadi Cordova.*
