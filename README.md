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

### Recommended: add the extension repository (automatic updates)

bSpheres NX is published to its own Blender extensions repository, so Blender can
update it in place — no uninstall/reinstall:

1. In Blender, open **Edit → Preferences → Get Extensions**, expand the
   **Repositories** dropdown (top right) and choose **+ → Add Remote Repository**.
2. Enter the URL `https://cracksoldier.github.io/blender_bspheres/index.json` and
   enable **Check for Updates on Startup**.
3. Search for **bSpheres NX** in Get Extensions and click **Install**.

New releases then show up as regular extension updates. If you previously installed
from disk, uninstall that copy once before installing from the repository —
afterwards updates are automatic. (Addon preferences reset on that one migration;
per-object settings stored in your `.blend` files are unaffected.)

### Manual: install from disk

Download `bspheres-<version>.zip` from the
[Releases page](https://github.com/Cracksoldier/blender_bspheres/releases), then in
Blender: **Edit → Preferences → Get Extensions → Install from Disk…**, pick the zip,
and enable **bSpheres NX**.

### From source

The addon is packaged as an Extension. From this folder you can build a
distributable zip with Blender's command-line tools:

```sh
blender --command extension validate .
blender --command extension build      # produces bspheres-<version>.zip
```

(For quick local development you can also drop the folder into your Blender
extensions directory and use *Reload Scripts*.)

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
   - **Preset + Apply** — pick one of seven output presets (Organic Smooth, Humanoid
     Basemesh, Creature Limbs, Tentacles, Hard Mannequin, Low Poly Blockout, 3D Print
     Solid) and click **Apply** to set all of the settings below — plus the Subdivision
     level — in one go. You can still tweak individual settings afterwards.
   - **Remesh / Size** — toggle voxel remesh on/off and set the voxel size (default
     0.02). Smaller = finer mesh, slower to compute.
   - **Shade Smooth** — automatically set smooth shading on baked output.
   - **Merge Doubles / Dist** — merge vertices within the given threshold after baking.
     Useful for cleaning up seams left by the Skin modifier.
   - **Recalculate Normals** — run "Recalculate Outside" on the baked mesh to fix
     flipped normals (off by default; the Skin modifier usually produces consistent
     normals already).
   - **Include Inserts** — join the assigned insert meshes (see **Refresh Insert
     Meshes**) into the baked output before remeshing, so voxel remesh unifies
     everything into one watertight mesh (off by default).
   - **Warn Thin Branches / Min Radius** — emit a warning for any vertex whose skin
     radius falls below the minimum (default 0.01). Vertices in the
     `bspheres_preserve` group are exempt. The warning fires during **Make bSkin**
     and **Preview / Refresh**.
7. **Selected Node** (Edit Mode only) — when a vertex is active, shows its live skin
   radius and root/loose flags, plus buttons:
   - **Set Radius** — opens a dialog pre-filled with the active vertex's skin radius;
     type exact X/Y values to apply them to all selected vertices (instead of
     eyeballing <kbd>Ctrl</kbd>+<kbd>A</kbd>).
   - **Mark Preserve** — adds the selected vertex to the `bspheres_preserve` group,
     exempting it from the thin-branch warning.
   - **Clear Preserve** — removes the selected vertex from that group.
   - **Select Children** — selects all vertices downstream of the active vertex
     (away from the skin root). Useful for posing a limb or tail as a unit.
   - **Select Parents** — selects all vertices upstream of the active vertex back to
     the skin root. Useful for selecting the spine leading to a joint.
   - **Assign Insert Meshes (Node / Link + Set)** — assign any mesh object in the
     scene to the active vertex (**Node**) or to the edge leading toward its parent
     (**Link**). **Clear Active Node** removes both assignments. The instances are
     created by **Refresh Insert Meshes** (see below). The target must be a mesh
     object other than the bSphere control object itself.
   - **Branch Tools**:
     - **Duplicate Branch** — duplicates the active vertex and everything downstream
       of it. The copy is left selected so you can move it into place with <kbd>G</kbd>.
     - **Mirror X / Y / Z** — duplicates everything downstream of the active vertex,
       mirrors it across the chosen axis (object-local space), and connects the
       mirrored branch back to the active vertex.
     - **Radial Duplicate** — creates rotated copies of the downstream branch around
       the chosen axis through the active vertex, each connected back to the active
       vertex. Count (default 4) and axis are adjustable in the operator redo panel.
     - **Taper Branch** — interpolates skin radii from the active vertex down to an
       end radius at the branch tips (by distance along the branch). The end radius
       is adjustable in the operator redo panel. Great for tails, tentacles, horns.
8. **Generate Armature** — creates a Blender armature from the bSphere control mesh.
   Each edge becomes one bone; bones are parented to mirror the vertex graph. The skin
   root vertex (set with **Mark Root**) determines the root bone. The armature is placed
   in a `bSpheres_Armatures` collection. Bones for the mirrored halves are generated
   too (matching the Mirror modifier's enabled axes); untick **Include Mirrored Half**
   in the redo panel to get only the unmirrored half.
9. **Refresh Insert Meshes** — creates or updates instances of the assigned insert
   meshes in a `bSpheres_Inserts` collection: node meshes are placed at their vertex,
   link meshes at the edge midpoint, aligned along the edge (local +Z) and stretched
   to its length. Instances are matched by vertex/edge index, so click Refresh again
   after topology edits. By default insert meshes are visual kitbash helpers; enable
   **Include Inserts** in bSkin Settings to merge them into baked output.
10. **Preview / Refresh** — non-destructive on-demand preview. Creates a temporary mesh
    in a `bSpheres_Preview` collection. Re-clicking updates it in-place so the Outliner
    stays clean. Use **Delete** to remove it.
11. **Make bSkin** — non-destructive permanent bake. Creates a new plain mesh object in a
    `bSpheres_Output` collection without touching the control structure. Each run produces
    a fresh output object named `bSkin…`.
12. **Make Rigged bSkin** — the full pipeline in one click: bakes a bSkin, generates the
    full-skeleton armature, and binds the mesh to it with automatic weights. The result
    is ready to pose.
13. **Apply** — destructive bake. Applies all three modifiers directly onto the control
    object, then post-processes using the same bSkin Settings (remesh, smooth, cleanup).
    Use this when you are done iterating.

### Addon preferences

Go to **Edit → Preferences → Add-ons → bSpheres NX** to configure:

- **Default Mirror Axes on Create (X / Y / Z)** — which axes are enabled on the Mirror
  modifier when you click **Create**. Default is Y only (matching the original behaviour).
  Uncheck all three to start with no mirroring active.

These are addon-wide settings and persist across Blender sessions.

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
