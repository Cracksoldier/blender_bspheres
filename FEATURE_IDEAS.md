# Feature ideas

Candidate features for future releases, grouped by how naturally they extend the
existing code.

## Shipped (July 2026)

Former ideas 1–5, now implemented:

1. **Full-skeleton armature generation** — mirrored bone sets per Mirror-modifier
   axis subset, with an `include_mirrored` redo-panel toggle.
2. **One-click Rig & Skin** — `Make Rigged bSkin` bakes, generates the armature,
   and binds with automatic weights.
3. **Merge inserts into the bake** — `Include Inserts` bSkin setting joins insert
   meshes into all bake paths before remeshing.
4. **Editable skin radius** — `Set Radius` dialog writes exact X/Y radii to all
   selected vertices.
5. **Taper Branch** — interpolates skin radii from the active vertex to an end
   radius at the branch tips, by distance along the branch.

## Branch/radius tools (medium effort, builds on `_get_chain_graph`)

6. **Rotate Branch.** Select-children + rotate is possible manually, but a dedicated
   operator with the pivot locked to the active vertex's *parent* joint would behave
   like posing a zSphere limb. The math is the same as `BSpheresRadialDuplicate`'s
   pivot rotation, applied to the existing branch instead of copies.

7. **Relax/Smooth Radii.** Average each vertex's skin radius with its graph neighbors
   (adjacency from `_bfs_from_root`) over N iterations. Cheap to implement, smooths
   out lumpy sketches before baking.

## Feedback and workflow (medium effort)

8. **Thin-branch overlay instead of warnings.** `_warn_thin_branches` prints to the
   status bar, which is easy to miss and spammy on dense meshes. A viewport overlay
   (a `gpu` draw handler tinting sub-threshold vertices red, respecting the preserve
   group) would make the problem visible where the user is looking.

9. **Auto-refresh preview.** A `depsgraph_update_post` handler that re-runs the
   preview bake when the control mesh changes (guarded by a panel toggle and a
   debounce, since voxel remesh isn't free). This is the difference between
   "on-demand preview" and the live feel of actual zSpheres.

10. **User-defined presets.** `BSpheresApplyPreset.PRESETS` is hardcoded. A "Save
    Current as Preset" operator writing JSON into the extension's user directory
    (`bpy.utils.extension_path_user`, which the Extensions system provides for
    exactly this) plus a dynamic `EnumProperty` items callback would let users keep
    their own recipes.

## Bigger swings

11. **Armature → bSphere import.** The inverse of Generate Armature: build a control
    mesh from an existing armature (one vertex per bone head/tail, skin radii from
    bone envelope sizes). Great for editing proportions of an already-rigged
    character, and it reuses `_bfs_tree` thinking in reverse.

12. **Named branches → named bones.** Let users tag the active vertex with a label
    (string attribute, same pattern as `bspheres_node_mesh`), then have armature
    generation name bones `spine`, `arm.L`, etc. instead of `bone_3_7`. Pairs well
    with full-skeleton generation since `.L`/`.R` suffixes aid symmetry tooling.
