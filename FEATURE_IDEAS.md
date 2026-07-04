# Feature ideas

Candidate features for future releases, grouped by how naturally they extend the
existing code. The ones at the top reuse existing infrastructure almost entirely;
the ones at the bottom are bigger commitments.

## Completing existing features (low effort, high payoff)

1. **Full-skeleton armature generation.** The biggest documented limitation:
   `GenerateBSphereArmature` only covers the unmirrored half. After building the
   bones, read the Mirror modifier's `use_axis` and run `bpy.ops.armature.symmetrize`
   (naming bones `bone_x_y.L` so Blender's symmetrize picks them up), or mirror the
   `world_positions` directly and emit the second half in the same edit session.
   This turns the armature feature from "starting point" into "done".

2. **One-click Rig & Skin.** The addon already generates both the baked mesh and the
   armature — a "Make Rigged bSkin" operator could run `MakeBSkin`, then
   `GenerateBSphereArmature`, then parent the output with automatic weights
   (`parent_set(type='ARMATURE_AUTO')`). That's the complete zSpheres pipeline
   (sketch → mesh → posed rig) in one button.

3. **Merge inserts into the bake.** Insert meshes are currently visual-only (a
   documented limitation). An option in `BSpheresSkinSettings` like "Include Inserts
   in Bake" could duplicate the instances and join them into the output object before
   `_apply_bskin_settings` runs — voxel remesh then unifies them into one watertight
   mesh for free, which is exactly how zBrush mesh insertion feels.

4. **Editable skin radius in the panel.** The "Selected Node" section displays the
   radius read-only from `bm.verts.layers.skin`. Making it editable (an operator with
   two `FloatProperty`s writing back to the layer, or a slider) would let users type
   exact radii instead of eyeballing Ctrl+A.

## Branch/radius tools (medium effort, builds on `_get_chain_graph`)

5. **Taper Branch.** Walk the downstream chain from the active vertex (via
   `_get_branch_geom`) and interpolate skin radii linearly from the active vertex's
   radius to a target end radius. Perfect for tails, tentacles, horns — currently the
   most tedious thing to do by hand.

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
    with #1 since `.L`/`.R` suffixes drive symmetrize.

## Suggested next release

**1 + 2** make the strongest single theme ("complete rigging pipeline"), with **4**
as the quality-of-life addition — all three stay inside patterns the code already
has (`try/finally` edit sessions, `_get_chain_graph`, the skin layer).
