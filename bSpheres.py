# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import bmesh
from bpy_extras.object_utils import AddObjectHelper
from collections import deque
import itertools
import math
import mathutils

# Maps context.mode values (e.g. 'EDIT_MESH') to the values mode_set() accepts
# (e.g. 'EDIT'). Anything not listed is assumed to already be a valid mode_set value.
_MODE_SET_MAP = {
    'EDIT_MESH': 'EDIT',
    'EDIT_CURVE': 'EDIT',
    'EDIT_SURFACE': 'EDIT',
    'EDIT_TEXT': 'EDIT',
    'EDIT_ARMATURE': 'EDIT',
    'EDIT_METABALL': 'EDIT',
    'EDIT_LATTICE': 'EDIT',
    'PAINT_WEIGHT': 'WEIGHT_PAINT',
    'PAINT_VERTEX': 'VERTEX_PAINT',
    'PAINT_TEXTURE': 'TEXTURE_PAINT',
    'PARTICLE': 'PARTICLE_EDIT',
}


def add_box(width, height, depth):
    """
    This function takes inputs and returns vertex and face arrays.
    no actual mesh data creation is done here.
    """

    verts = [
        (+1.0, +1.0, -1.0),
        (+1.0, -1.0, -1.0),
        (-1.0, -1.0, -1.0),
        (-1.0, +1.0, -1.0),
        (+1.0, +1.0, +1.0),
        (+1.0, -1.0, +1.0),
        (-1.0, -1.0, +1.0),
        (-1.0, +1.0, +1.0),
    ]

    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (4, 0, 3, 7),
    ]

    # apply size
    for i, v in enumerate(verts):
        verts[i] = v[0] * width, v[1] * depth, v[2] * height

    return verts, faces
 
 
class applyBSphereModifiers(bpy.types.Operator):
    bl_idname = 'tcg.apply_bsphere_modifiers'
    bl_label = 'Apply bSphere Modifiers'
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        obj = context.object
        bpy.ops.object.mode_set(mode='OBJECT')
        settings = obj.bspheres_skin_settings

        # Collect insert placements before the modifiers are applied — applying
        # them rebuilds the mesh and destroys the per-vertex/edge attributes.
        insert_placements = (
            _collect_insert_placements(self, obj) if settings.use_include_inserts else []
        )

        # Apply by modifier type, not by the default names ("Mirror"/"Skin"/
        # "Subdivision"): Blender suffixes duplicates with ".001" if the object
        # already had a modifier of that type, which would break a name lookup.
        for mod_type in ('MIRROR', 'SKIN', 'SUBSURF'):
            mod = next((m for m in obj.modifiers if m.type == mod_type), None)
            if mod is not None:
                bpy.ops.object.modifier_apply(modifier=mod.name)

        space = context.space_data
        if space and space.type == 'VIEW_3D':
            space.shading.show_xray = False
        _join_inserts(self, context, obj, insert_placements)
        if settings.use_voxel_remesh:
            obj.data.remesh_voxel_size = settings.voxel_size
            bpy.ops.object.voxel_remesh()
        _run_mesh_cleanup(obj, settings, context)
        if settings.use_smooth_shading:
            for poly in obj.data.polygons:
                poly.use_smooth = True
        previous_mode = context.scene.get('previous_mode', 'OBJECT')
        bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
        return {"FINISHED"}
    
from bpy.props import (
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
)


class BSpheresPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    default_mirror_axes: bpy.props.BoolVectorProperty(
        name="Default Mirror Axes",
        size=3,
        default=(False, True, False),
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Default Mirror Axes on Create:")
        row = layout.row()
        row.prop(self, "default_mirror_axes", text="X", index=0)
        row.prop(self, "default_mirror_axes", text="Y", index=1)
        row.prop(self, "default_mirror_axes", text="Z", index=2)


class AddBMesh(bpy.types.Operator):
    """Add a bSphere"""
    bl_idname = "mesh.primitive_bsphere_add"
    bl_label = "Add bSphere"
    bl_options = {'REGISTER', 'UNDO'}

    width: FloatProperty(
        name="Width",
        description="Box Width",
        min=0.01, max=100.0,
        default=1.0,
    )
    height: FloatProperty(
        name="Height",
        description="Box Height",
        min=0.01, max=100.0,
        default=1.0,
    )
    depth: FloatProperty(
        name="Depth",
        description="Box Depth",
        min=0.01, max=100.0,
        default=1.0,
    )

    # generic transform props
    align_items = (
            ('WORLD', "World", "Align the new object to the world"),
            ('VIEW', "View", "Align the new object to the view"),
            ('CURSOR', "3D Cursor", "Use the 3D cursor orientation for the new object")
    )
    align: EnumProperty(
            name="Align",
            items=align_items,
            default='WORLD',
            update=AddObjectHelper.align_update_callback,
            )
    location: FloatVectorProperty(
        name="Location",
        subtype='TRANSLATION',
    )
    rotation: FloatVectorProperty(
        name="Rotation",
        subtype='EULER',
    )

    def execute(self, context):

        context.scene['previous_mode'] = context.mode

        verts_loc, faces = add_box(
            self.width,
            self.height,
            self.depth,
        )

        mesh = bpy.data.meshes.new("bSphere")

        bm = bmesh.new()

        for v_co in verts_loc:
            bm.verts.new(v_co)

        bm.verts.ensure_lookup_table()
        for f_idx in faces:
            bm.faces.new([bm.verts[i] for i in f_idx])

        bm.to_mesh(mesh)
        mesh.update()

        # add the mesh as an object into the scene with this utility module
        from bpy_extras import object_utils
        obj = object_utils.object_data_add(context, mesh, operator=self)
        for v in obj.data.vertices:
            v.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.merge(type='CENTER')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        bpy.ops.object.modifier_add(type='MIRROR')
        addon = bpy.context.preferences.addons.get(__package__)
        mirror_axes = addon.preferences.default_mirror_axes if addon else (False, True, False)
        bpy.context.object.modifiers["Mirror"].use_axis = tuple(mirror_axes)
        bpy.ops.object.modifier_add(type='SKIN')
        bpy.ops.object.modifier_add(type='SUBSURF')
        bpy.context.object.modifiers["Skin"].use_x_symmetry = False
        bpy.context.object.modifiers["Skin"].use_y_symmetry = False
        bpy.context.object.modifiers["Skin"].use_z_symmetry = False
        bpy.context.object.modifiers["Subdivision"].render_levels = 3
        bpy.context.object.modifiers["Subdivision"].levels = 3
        bpy.context.object.modifiers["Subdivision"].quality = 3
        
        bpy.ops.object.mode_set(mode='EDIT')
        space = context.space_data
        if space and space.type == 'VIEW_3D':
            space.shading.show_xray = True

        bpy.ops.object.skin_root_mark()

        return {'FINISHED'}
 
 
def _is_bsphere_control(obj):
    if obj is None or obj.type != 'MESH':
        return False
    mod_types = {m.type for m in obj.modifiers}
    return {'MIRROR', 'SKIN', 'SUBSURF'}.issubset(mod_types)


def _ensure_collection(name, scene):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in {c.name for c in scene.collection.children_recursive}:
        scene.collection.children.link(col)
    return col


def _apply_bskin_settings(obj, settings, context):
    if settings.use_voxel_remesh:
        prev_active = context.view_layer.objects.active
        prev_selected = obj.select_get()
        try:
            context.view_layer.objects.active = obj
            obj.select_set(True)
            obj.data.remesh_voxel_size = settings.voxel_size
            bpy.ops.object.voxel_remesh()
        finally:
            obj.select_set(prev_selected)
            context.view_layer.objects.active = prev_active
    _run_mesh_cleanup(obj, settings, context)
    if settings.use_smooth_shading:
        for poly in obj.data.polygons:
            poly.use_smooth = True


def _find_preview_obj(source_name):
    col = bpy.data.collections.get("bSpheres_Preview")
    if col is None:
        return None
    for obj in col.objects:
        if obj.get("bspheres_preview") and obj.get("bspheres_source") == source_name:
            return obj
    return None


def _warn_thin_branches(operator, source_obj, settings):
    if not source_obj.data.skin_vertices:
        return
    skin_data = source_obj.data.skin_vertices[0].data
    preserve_idx = source_obj.vertex_groups.find("bspheres_preserve")
    for i, vert in enumerate(source_obj.data.vertices):
        if preserve_idx >= 0 and any(g.group == preserve_idx for g in vert.groups):
            continue
        r = skin_data[i].radius
        if r[0] < settings.min_branch_radius or r[1] < settings.min_branch_radius:
            operator.report(
                {'WARNING'},
                f"Vertex {i}: skin radius {r[0]:.4f}×{r[1]:.4f} is below "
                f"minimum {settings.min_branch_radius:.4f}",
            )


def _run_mesh_cleanup(obj, settings, context):
    if not settings.use_merge_doubles and not settings.use_recalc_normals:
        return
    prev_active = context.view_layer.objects.active
    prev_selected = obj.select_get()
    # Deselect everything else so mode_set(EDIT) doesn't enter multi-object
    # edit and run the cleanup operators on other selected meshes (e.g. the
    # bSphere control object during a non-destructive bake).
    other_selected = [o for o in context.selected_objects if o is not obj]
    try:
        for o in other_selected:
            o.select_set(False)
        context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        if settings.use_merge_doubles:
            bpy.ops.mesh.merge_by_distance(threshold=settings.merge_threshold)
        if settings.use_recalc_normals:
            bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    finally:
        obj.select_set(prev_selected)
        for o in other_selected:
            o.select_set(True)
        context.view_layer.objects.active = prev_active


def _build_mesh_graph(obj):
    adj = {i: [] for i in range(len(obj.data.vertices))}
    for edge in obj.data.edges:
        a, b = edge.vertices
        adj[a].append(b)
        adj[b].append(a)
    return adj


def _find_skin_root(obj):
    if not obj.data.skin_vertices:
        return -1
    skin_data = obj.data.skin_vertices[0].data
    for i, sv in enumerate(skin_data):
        if sv.use_root:
            return i
    return -1


def _bfs_tree(adj, root_idx):
    parent_map = {root_idx: None}
    queue = deque([root_idx])
    found_cycle = False
    while queue:
        v = queue.popleft()
        for nb in adj[v]:
            if nb not in parent_map:
                parent_map[nb] = v
                queue.append(nb)
            elif nb != parent_map[v]:
                found_cycle = True
    return parent_map, found_cycle


def _bfs_from_root(bm):
    """BFS the live BMesh from the skin root. Returns (parent_map, found_cycle, error);
    on failure parent_map is None and error is a warning string. BMesh element indices
    go stale (new elements report -1) after topology edits in the same edit session,
    so vertex and edge indices are refreshed here before any index-keyed use."""
    bm.verts.index_update()
    bm.edges.index_update()
    bm.verts.ensure_lookup_table()

    skin_layers = bm.verts.layers.skin
    if not skin_layers:
        return None, False, "No skin layer found."
    root_vert = next((v for v in bm.verts if v[skin_layers[0]].use_root), None)
    if root_vert is None:
        return None, False, "No skin root marked. Mark a vertex as root first."

    adj = {v.index: [e.other_vert(v).index for e in v.link_edges] for v in bm.verts}
    parent_map, found_cycle = _bfs_tree(adj, root_vert.index)
    return parent_map, found_cycle, None


def _get_chain_graph(operator, context):
    obj = context.active_object
    bm = bmesh.from_edit_mesh(obj.data)

    parent_map, found_cycle, error = _bfs_from_root(bm)
    if error is not None:
        operator.report({'WARNING'}, error)
        return None

    active = bm.select_history.active
    if not isinstance(active, bmesh.types.BMVert):
        operator.report({'WARNING'}, "No active vertex. Select a vertex first.")
        return None

    if active.index not in parent_map:
        operator.report({'WARNING'}, "Active vertex is not reachable from root.")
        return None
    if found_cycle:
        operator.report({'WARNING'}, "Cycle detected in mesh graph.")

    return bm, parent_map, active


def _find_parent_edge(bm, parent_map, active_vert):
    """Return the BMEdge connecting active_vert to its BFS parent, or None if the
    active vertex is the root or no such edge exists."""
    parent_idx = parent_map.get(active_vert.index)
    if parent_idx is None:
        return None
    bm.verts.ensure_lookup_table()
    parent_bvert = bm.verts[parent_idx]
    return next((e for e in active_vert.link_edges if e.other_vert(active_vert) == parent_bvert), None)


def _find_parent_edge_idx(bm, active_vert):
    """Return the edge index connecting active_vert to its BFS parent, or -1 if none.
    Refreshes vertex/edge indices as a side effect (via _bfs_from_root)."""
    parent_map, _, error = _bfs_from_root(bm)
    if error is not None:
        return -1
    edge = _find_parent_edge(bm, parent_map, active_vert)
    return edge.index if edge is not None else -1


def _build_children_map(parent_map):
    """Invert a BFS parent_map into {parent_index: [child_index, …]}."""
    children_map = {}
    for child, par in parent_map.items():
        if par is not None:
            children_map.setdefault(par, []).append(child)
    return children_map


def _direct_child_verts(bm, parent_map, parent_idx):
    """Return the BMVerts whose BFS parent is parent_idx. The lookup table must be
    fresh (callers get this via _bfs_from_root)."""
    return [bm.verts[c] for c, p in parent_map.items() if p == parent_idx]


def _get_branch_geom(bm, parent_map, active_vert, exclude_root=False):
    """Return (branch_bverts, branch_bedges) for the downstream branch from active_vert.
    With exclude_root=True, active_vert itself is excluded so mirror/radial keep the
    attachment point fixed instead of moving it to a disconnected position."""
    children_map = _build_children_map(parent_map)

    branch_verts = set()
    start_indices = children_map.get(active_vert.index, []) if exclude_root else [active_vert.index]
    queue = deque(start_indices)
    while queue:
        v = queue.popleft()
        branch_verts.add(v)
        queue.extend(children_map.get(v, []))

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    branch_bverts = [bm.verts[i] for i in branch_verts]
    branch_bedges = [
        e for e in bm.edges
        if e.verts[0].index in branch_verts and e.verts[1].index in branch_verts
    ]
    return branch_bverts, branch_bedges


def _bake_bskin_object(context, source_obj):
    """Bake the evaluated modifier stack of source_obj into a new mesh object linked
    into bSpheres_Output. Must be called in OBJECT mode. Returns the new object."""
    depsgraph = context.evaluated_depsgraph_get()
    evaluated_obj = source_obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated_obj, depsgraph=depsgraph)

    name = source_obj.name
    output_name = ('bSkin' + name[7:]) if name.startswith('bSphere') else 'bSkin'

    new_obj = bpy.data.objects.new(output_name, mesh)
    new_obj.matrix_world = source_obj.matrix_world.copy()

    col = _ensure_collection("bSpheres_Output", context.scene)
    col.objects.link(new_obj)
    return new_obj


class MakeBSkin(bpy.types.Operator):
    """Create a new sculptable mesh from the bSphere control object without modifying it"""
    bl_idname = 'bspheres.make_bskin'
    bl_label = 'Make bSkin'
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        source_obj = context.active_object
        previous_mode = context.mode
        settings = source_obj.bspheres_skin_settings
        bpy.ops.object.mode_set(mode='OBJECT')
        if settings.warn_thin_branches:
            _warn_thin_branches(self, source_obj, settings)

        new_obj = _bake_bskin_object(context, source_obj)
        _maybe_join_inserts(self, context, new_obj, source_obj)

        _apply_bskin_settings(new_obj, settings, context)
        bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
        return {"FINISHED"}


class MakeRiggedBSkin(bpy.types.Operator):
    """Bake the bSphere into a mesh, generate its armature, and bind them with automatic weights"""
    bl_idname = 'bspheres.make_rigged_bskin'
    bl_label = 'Make Rigged bSkin'
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        source_obj = context.active_object
        previous_mode = context.mode
        settings = source_obj.bspheres_skin_settings
        bpy.ops.object.mode_set(mode='OBJECT')
        if settings.warn_thin_branches:
            _warn_thin_branches(self, source_obj, settings)

        new_obj = _bake_bskin_object(context, source_obj)
        _maybe_join_inserts(self, context, new_obj, source_obj)
        _apply_bskin_settings(new_obj, settings, context)

        arm_obj = _generate_armature_object(self, context, source_obj, include_mirrored=True)
        if arm_obj is None:
            self.report({'ERROR'}, "Baked mesh was created but not rigged — see the warning above.")
            bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
            return {'CANCELLED'}

        # Bind with automatic weights: parent_set needs the mesh selected and the
        # armature active, so swap selection inside try/finally (same pattern as
        # _run_mesh_cleanup).
        prev_active = context.view_layer.objects.active
        prev_selected = list(context.selected_objects)
        try:
            for o in prev_selected:
                o.select_set(False)
            new_obj.select_set(True)
            arm_obj.select_set(True)
            context.view_layer.objects.active = arm_obj
            bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        finally:
            new_obj.select_set(False)
            arm_obj.select_set(False)
            for o in prev_selected:
                o.select_set(True)
            context.view_layer.objects.active = prev_active

        bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
        self.report({'INFO'}, f"Rigged bSkin '{new_obj.name}' bound to armature '{arm_obj.name}'.")
        return {'FINISHED'}


_PRESET_ITEMS = [
    ('ORGANIC_SMOOTH',    "Organic Smooth",    "Characters and creatures"),
    ('HUMANOID_BASEMESH', "Humanoid Basemesh", "Human / creature body blockouts"),
    ('CREATURE_LIMBS',    "Creature Limbs",    "Monsters, legs, horns, wings"),
    ('TENTACLES',         "Tentacles",         "Long tapered shapes"),
    ('HARD_MANNEQUIN',    "Hard Mannequin",    "Robots and mannequin blockouts"),
    ('LOW_POLY_BLOCKOUT', "Low Poly Blockout", "Fast concepting"),
    ('PRINT_SOLID',       "3D Print Solid",    "Printable miniatures"),
]


class BSpheresSkinSettings(bpy.types.PropertyGroup):
    voxel_size: bpy.props.FloatProperty(
        name="Voxel Size", default=0.02, min=0.001, max=1.0, step=0.1,
        description="Voxel remesh resolution for baked output",
    )
    use_voxel_remesh: bpy.props.BoolProperty(
        name="Voxel Remesh", default=True,
        description="Apply voxel remesh after baking",
    )
    use_smooth_shading: bpy.props.BoolProperty(
        name="Shade Smooth", default=True,
        description="Set smooth shading on baked output",
    )
    use_merge_doubles: bpy.props.BoolProperty(
        name="Merge Doubles", default=False,
        description="Merge vertices by distance after baking",
    )
    merge_threshold: bpy.props.FloatProperty(
        name="Merge Distance", default=0.001, min=0.00001, max=0.1, step=0.01,
        description="Distance threshold for merge-by-distance",
    )
    use_recalc_normals: bpy.props.BoolProperty(
        name="Recalculate Normals", default=False,
        description="Recalculate normals outward after baking",
    )
    use_include_inserts: bpy.props.BoolProperty(
        name="Include Inserts", default=False,
        description="Join assigned insert meshes into the baked output before remeshing",
    )
    warn_thin_branches: bpy.props.BoolProperty(
        name="Warn Thin Branches", default=True,
        description="Report a warning when a vertex skin radius is below the minimum",
    )
    min_branch_radius: bpy.props.FloatProperty(
        name="Min Radius", default=0.01, min=0.0001, max=1.0, step=0.01,
        description="Skin radius below which a warning is issued",
    )
    insert_node_mesh_name: bpy.props.StringProperty(
        name="Node Mesh",
        description="Mesh object to instance at this vertex",
    )
    insert_link_mesh_name: bpy.props.StringProperty(
        name="Link Mesh",
        description="Mesh object to instance along the edge to the parent vertex",
    )
    last_preset: bpy.props.EnumProperty(
        name="Preset",
        items=_PRESET_ITEMS,
        default='ORGANIC_SMOOTH',
        description="Output preset to apply",
    )


class PreviewBSkin(bpy.types.Operator):
    """Create or refresh a temporary preview mesh from the bSphere control object"""
    bl_idname = 'bspheres.preview_bskin'
    bl_label = 'Preview bSkin'
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        source_obj = context.active_object
        previous_mode = context.mode
        settings = source_obj.bspheres_skin_settings
        bpy.ops.object.mode_set(mode='OBJECT')
        if settings.warn_thin_branches:
            _warn_thin_branches(self, source_obj, settings)

        depsgraph = context.evaluated_depsgraph_get()
        evaluated_obj = source_obj.evaluated_get(depsgraph)
        new_mesh = bpy.data.meshes.new_from_object(evaluated_obj, depsgraph=depsgraph)

        col = _ensure_collection("bSpheres_Preview", context.scene)
        preview_obj = _find_preview_obj(source_obj.name)

        if preview_obj is not None:
            old_mesh = preview_obj.data
            preview_obj.data = new_mesh
            bpy.data.meshes.remove(old_mesh)
            preview_obj.matrix_world = source_obj.matrix_world.copy()
        else:
            for orphan in list(col.objects):
                if orphan.get("bspheres_preview") and orphan.get("bspheres_source") not in bpy.data.objects:
                    orphan_mesh = orphan.data if orphan.type == 'MESH' else None
                    bpy.data.objects.remove(orphan, do_unlink=True)
                    if orphan_mesh and orphan_mesh.users == 0:
                        bpy.data.meshes.remove(orphan_mesh)
            name = source_obj.name
            preview_name = ('bPreview' + name[7:]) if name.startswith('bSphere') else 'bPreview'
            preview_obj = bpy.data.objects.new(preview_name, new_mesh)
            preview_obj["bspheres_preview"] = True
            preview_obj["bspheres_source"] = source_obj.name
            preview_obj.matrix_world = source_obj.matrix_world.copy()
            col.objects.link(preview_obj)

        _maybe_join_inserts(self, context, preview_obj, source_obj)
        _apply_bskin_settings(preview_obj, source_obj.bspheres_skin_settings, context)
        bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
        return {"FINISHED"}


class DeleteBSkinPreview(bpy.types.Operator):
    """Delete the preview mesh for the active bSphere control object"""
    bl_idname = 'bspheres.delete_bskin_preview'
    bl_label = 'Delete Preview'
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and _find_preview_obj(obj.name) is not None

    def execute(self, context):
        preview_obj = _find_preview_obj(context.active_object.name)
        if preview_obj is None:
            return {"CANCELLED"}
        mesh = preview_obj.data
        bpy.data.objects.remove(preview_obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        return {"FINISHED"}


class BSphereMarkPreserve(bpy.types.Operator):
    """Mark selected vertices as preserved (skip thin-branch warnings and cleanup thinning)"""
    bl_idname = 'bspheres.mark_preserve'
    bl_label = 'Mark Preserve'
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        vg = obj.vertex_groups.get("bspheres_preserve") or obj.vertex_groups.new(name="bspheres_preserve")
        prev_active_idx = obj.vertex_groups.active_index
        obj.vertex_groups.active_index = vg.index
        bpy.ops.object.vertex_group_assign()
        if prev_active_idx >= 0:
            obj.vertex_groups.active_index = prev_active_idx
        return {"FINISHED"}


class BSphereClearPreserve(bpy.types.Operator):
    """Unmark selected vertices from the preserve group"""
    bl_idname = 'bspheres.clear_preserve'
    bl_label = 'Clear Preserve'
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        vg = obj.vertex_groups.get("bspheres_preserve")
        if vg is None:
            return {"CANCELLED"}
        prev_active_idx = obj.vertex_groups.active_index
        obj.vertex_groups.active_index = vg.index
        bpy.ops.object.vertex_group_remove_from()
        if prev_active_idx >= 0:
            obj.vertex_groups.active_index = prev_active_idx
        return {"FINISHED"}


class BSphereSetSkinRadius(bpy.types.Operator):
    """Set the skin radius of all selected vertices numerically"""
    bl_idname = 'bspheres.set_skin_radius'
    bl_label = 'Set Skin Radius'
    bl_options = {'REGISTER', 'UNDO'}

    radius: FloatVectorProperty(
        name="Radius",
        size=2,
        min=0.0001,
        max=10.0,
        default=(0.25, 0.25),
        description="Skin radius (X × Y) to assign to the selected vertices",
    )

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def invoke(self, context, event):
        # Prime the dialog with the active vertex's current radius.
        bm = bmesh.from_edit_mesh(context.active_object.data)
        skin_layers = bm.verts.layers.skin
        active = bm.select_history.active
        if skin_layers and isinstance(active, bmesh.types.BMVert):
            r = active[skin_layers[0]].radius
            self.radius = (r[0], r[1])
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        skin_layers = bm.verts.layers.skin
        if not skin_layers:
            self.report({'WARNING'}, "No skin layer found.")
            return {'CANCELLED'}
        layer = skin_layers[0]
        count = 0
        for v in bm.verts:
            if v.select:
                v[layer].radius = (self.radius[0], self.radius[1])
                count += 1
        if count == 0:
            self.report({'WARNING'}, "No vertices selected.")
            return {'CANCELLED'}
        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


def _generate_armature_object(operator, context, obj, include_mirrored=True):
    """Create an armature object from the bSphere control mesh in bSpheres_Armatures.
    With include_mirrored, also creates bone sets for the halves produced by the
    Mirror modifier (one set per non-empty subset of its enabled axes, mirrored in
    the control object's local space — Blender's armature symmetrize only handles X,
    while bSpheres defaults to Y mirroring). Must be called in OBJECT mode; restores
    selection and the active object, and leaves the mode in OBJECT. Returns the
    armature object, or None if no skin root is marked."""
    root_idx = _find_skin_root(obj)
    if root_idx < 0:
        operator.report({'ERROR'}, "No skin root marked. Mark a vertex as root first.")
        return None

    adj = _build_mesh_graph(obj)
    parent_map, found_cycle = _bfs_tree(adj, root_idx)

    if found_cycle:
        operator.report({'WARNING'}, "Cycle detected in mesh graph — cycle edges are skipped.")

    n_verts = len(obj.data.vertices)
    if len(parent_map) < n_verts:
        operator.report(
            {'WARNING'},
            f"{n_verts - len(parent_map)} vertices not reachable from root — they will not become bones.",
        )

    # The Mirror modifier mirrors in object-local space, so keep local positions
    # and only transform to world when assigning bone heads/tails.
    local_positions = [v.co.copy() for v in obj.data.vertices]

    mirror_combos = []
    if include_mirrored:
        mirror_mod = next((m for m in obj.modifiers if m.type == 'MIRROR'), None)
        if mirror_mod is not None:
            axes = [i for i in range(3) if mirror_mod.use_axis[i]]
            for r in range(1, len(axes) + 1):
                mirror_combos.extend(itertools.combinations(axes, r))

    def mirrored(co, combo):
        m = co.copy()
        for axis in combo:
            m[axis] = -m[axis]
        return m

    name = obj.name
    arm_name = ('bArmature' + name[7:]) if name.startswith('bSphere') else 'bArmature'
    arm_data = bpy.data.armatures.new(arm_name)
    arm_obj = bpy.data.objects.new(arm_name, arm_data)
    _ensure_collection("bSpheres_Armatures", context.scene).objects.link(arm_obj)

    prev_active = context.view_layer.objects.active
    other_selected = [o for o in context.selected_objects if o is not obj]
    try:
        for o in other_selected:
            o.select_set(False)
        obj.select_set(False)
        context.view_layer.objects.active = arm_obj
        arm_obj.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')

        # One bone set per combo; the empty combo () is the unmirrored base set.
        # Edges lying entirely on the mirror plane(s) are skipped for mirrored
        # combos — their copy would coincide with the base bone.
        refs_by_combo = {}
        for combo in [()] + mirror_combos:
            suffix = ('.m' + ''.join('XYZ'[i] for i in combo)) if combo else ''
            combo_refs = {}
            for child_idx, par_idx in parent_map.items():
                if par_idx is None:
                    continue
                head_l = mirrored(local_positions[par_idx], combo)
                tail_l = mirrored(local_positions[child_idx], combo)
                if combo and ((head_l - local_positions[par_idx]).length < 1e-6
                              and (tail_l - local_positions[child_idx]).length < 1e-6):
                    continue
                head = obj.matrix_world @ head_l
                tail = obj.matrix_world @ tail_l
                if (tail - head).length < 1e-6:
                    if not combo:
                        operator.report({'WARNING'}, f"Skipping zero-length edge {par_idx}→{child_idx}.")
                    continue
                bone = arm_data.edit_bones.new(f"bone_{par_idx}_{child_idx}{suffix}")
                bone.head = head
                bone.tail = tail
                combo_refs[child_idx] = (bone, par_idx)
            refs_by_combo[combo] = combo_refs

        base_refs = refs_by_combo[()]
        for combo, combo_refs in refs_by_combo.items():
            for child_idx, (bone, par_idx) in combo_refs.items():
                if par_idx in combo_refs:
                    bone.parent = combo_refs[par_idx][0]
                elif combo and par_idx in base_refs:
                    # The parent edge lies on the mirror plane — hang the
                    # mirrored chain off the base (shared) bone.
                    bone.parent = base_refs[par_idx][0]
                elif not combo and par_idx != root_idx:
                    operator.report(
                        {'WARNING'},
                        f"Bone for vertex {child_idx} is disconnected — "
                        f"its parent edge to vertex {par_idx} was skipped.",
                    )

        bpy.ops.object.mode_set(mode='OBJECT')
    finally:
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        arm_obj.select_set(False)
        obj.select_set(True)
        for o in other_selected:
            o.select_set(True)
        context.view_layer.objects.active = prev_active

    return arm_obj


class GenerateBSphereArmature(bpy.types.Operator):
    """Generate a Blender armature from the bSphere control mesh"""
    bl_idname = 'bspheres.generate_armature'
    bl_label = 'Generate Armature'
    bl_options = {'REGISTER', 'UNDO'}

    include_mirrored: bpy.props.BoolProperty(
        name="Include Mirrored Half",
        default=True,
        description="Also generate bones for the halves produced by the Mirror modifier",
    )

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        obj = context.active_object
        previous_mode = context.mode

        bpy.ops.object.mode_set(mode='OBJECT')
        arm_obj = _generate_armature_object(self, context, obj, self.include_mirrored)
        bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))

        if arm_obj is None:
            return {'CANCELLED'}
        if self.include_mirrored:
            self.report({'INFO'}, f"Armature '{arm_obj.name}' generated.")
        else:
            self.report({'INFO'}, f"Armature '{arm_obj.name}' generated. Note: only the unmirrored half is included.")
        return {'FINISHED'}


class BSphereSelectChildChain(bpy.types.Operator):
    """Select all vertices downstream of the active vertex (away from root)"""
    bl_idname = 'bspheres.select_child_chain'
    bl_label = 'Select Child Chain'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        result = _get_chain_graph(self, context)
        if result is None:
            return {'CANCELLED'}
        bm, parent_map, active = result
        obj = context.active_object

        children_map = _build_children_map(parent_map)

        child_chain = set()
        queue = deque(children_map.get(active.index, []))
        while queue:
            v = queue.popleft()
            child_chain.add(v)
            queue.extend(children_map.get(v, []))

        if not child_chain:
            self.report({'INFO'}, "No child vertices found from active vertex.")
            return {'FINISHED'}

        for v in bm.verts:
            if v.index in child_chain:
                v.select = True

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


class BSphereSelectParentChain(bpy.types.Operator):
    """Select all vertices upstream of the active vertex (toward root)"""
    bl_idname = 'bspheres.select_parent_chain'
    bl_label = 'Select Parent Chain'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        result = _get_chain_graph(self, context)
        if result is None:
            return {'CANCELLED'}
        bm, parent_map, active = result
        obj = context.active_object

        parent_chain = set()
        current = parent_map.get(active.index)
        while current is not None:
            parent_chain.add(current)
            current = parent_map.get(current)

        if not parent_chain:
            self.report({'INFO'}, "Active vertex is the root — no parent chain.")
            return {'FINISHED'}

        for v in bm.verts:
            if v.index in parent_chain:
                v.select = True

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


# ── Feature 08: Insert Node & Link Meshes ────────────────────────────────────

def _get_string_attr(data_item):
    """Read a STRING attribute value as str — Blender 4.5+ exposes it as bytes,
    4.2 LTS as str."""
    value = data_item.value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def _set_string_attr(data_item, text):
    """Write a STRING attribute value — Blender 4.5+ expects bytes, 4.2 LTS str."""
    try:
        data_item.value = text
    except TypeError:
        data_item.value = text.encode("utf-8")


def _validate_insert_mesh(operator, control_obj, mesh_name, field_label):
    """Validate an insert-mesh assignment target. Reports a warning and returns
    False if the name is empty, the object is missing, it is not a mesh, or it
    is the control object itself."""
    if not mesh_name:
        operator.report({'WARNING'}, f"No mesh object selected in {field_label} field.")
        return False
    target = bpy.data.objects.get(mesh_name)
    if target is None:
        operator.report({'WARNING'}, f"Object '{mesh_name}' not found.")
        return False
    if target.type != 'MESH':
        operator.report({'WARNING'}, f"Object '{mesh_name}' is not a mesh.")
        return False
    if target == control_obj:
        operator.report({'WARNING'}, "Cannot use the bSphere control object as its own insert mesh.")
        return False
    return True


class BSphereAssignNodeMesh(bpy.types.Operator):
    """Assign the selected mesh object as the insert mesh for the active vertex"""
    bl_idname = 'bspheres.assign_node_mesh'
    bl_label = 'Assign Node Mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        settings = obj.bspheres_skin_settings
        mesh_name = settings.insert_node_mesh_name
        if not _validate_insert_mesh(self, obj, mesh_name, "Node Mesh"):
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)
        active = bm.select_history.active
        if not isinstance(active, bmesh.types.BMVert):
            self.report({'WARNING'}, "No active vertex. Select a vertex first.")
            return {'CANCELLED'}

        # Refresh indices before using active.index as a mesh attribute index —
        # a stale/-1 index would silently write to the wrong vertex.
        bm.verts.index_update()
        vert_idx = active.index
        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            attr = obj.data.attributes.get("bspheres_node_mesh")
            if attr is None:
                attr = obj.data.attributes.new("bspheres_node_mesh", 'STRING', 'POINT')
            _set_string_attr(attr.data[vert_idx], mesh_name)
        finally:
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class BSphereAssignLinkMesh(bpy.types.Operator):
    """Assign the selected mesh object as the insert mesh for the edge to the parent vertex"""
    bl_idname = 'bspheres.assign_link_mesh'
    bl_label = 'Assign Link Mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        settings = obj.bspheres_skin_settings
        mesh_name = settings.insert_link_mesh_name
        if not _validate_insert_mesh(self, obj, mesh_name, "Link Mesh"):
            return {'CANCELLED'}

        result = _get_chain_graph(self, context)
        if result is None:
            return {'CANCELLED'}
        bm, parent_map, active_vert = result

        if parent_map.get(active_vert.index) is None:
            self.report({'WARNING'}, "Active vertex is the root — no incoming edge to assign a link mesh to.")
            return {'CANCELLED'}

        edge = _find_parent_edge(bm, parent_map, active_vert)
        if edge is None:
            self.report({'ERROR'}, "Could not find the edge between active vertex and parent.")
            return {'CANCELLED'}

        edge_idx = edge.index
        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            attr = obj.data.attributes.get("bspheres_link_mesh")
            if attr is None:
                attr = obj.data.attributes.new("bspheres_link_mesh", 'STRING', 'EDGE')
            _set_string_attr(attr.data[edge_idx], mesh_name)
        finally:
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


class BSphereClearInsertMesh(bpy.types.Operator):
    """Clear the insert mesh assignment from the active vertex and its incoming edge"""
    bl_idname = 'bspheres.clear_insert_mesh'
    bl_label = 'Clear Insert Mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        active = bm.select_history.active
        if not isinstance(active, bmesh.types.BMVert):
            self.report({'WARNING'}, "No active vertex.")
            return {'CANCELLED'}

        # _find_parent_edge_idx refreshes stale indices, so call it before
        # reading active.index.
        edge_idx = _find_parent_edge_idx(bm, active)
        if edge_idx == -1:
            edge_idx = None
        vert_idx = active.index

        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            attr_node = obj.data.attributes.get("bspheres_node_mesh")
            if attr_node and vert_idx < len(attr_node.data):
                _set_string_attr(attr_node.data[vert_idx], "")

            if edge_idx is not None:
                attr_edge = obj.data.attributes.get("bspheres_link_mesh")
                if attr_edge and edge_idx < len(attr_edge.data):
                    _set_string_attr(attr_edge.data[edge_idx], "")
        finally:
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


def _find_insert_instances(source_name):
    """Return ({vert_idx: inst}, {edge_idx: inst}) for the live instances in
    bSpheres_Inserts tagged with the given source object name."""
    existing_node = {}
    existing_edge = {}
    col = bpy.data.collections.get("bSpheres_Inserts")
    if col is None:
        return existing_node, existing_edge
    for inst in col.objects:
        if not inst.get("bspheres_insert") or inst.get("bspheres_source") != source_name:
            continue
        vi = inst.get("bspheres_vert_idx")
        ei = inst.get("bspheres_edge_idx")
        if vi is not None:
            existing_node[vi] = inst
        elif ei is not None:
            existing_edge[ei] = inst
    return existing_node, existing_edge


_COMPUTED_MATRIX_PROP = "bspheres_computed_matrix"


def _store_computed_matrix(inst, matrix):
    """Record the computed placement on the instance so later refreshes and bakes
    can tell a deliberate user tweak apart from mere staleness."""
    inst[_COMPUTED_MATRIX_PROP] = [v for row in matrix for v in row]


def _get_stored_computed_matrix(inst):
    vals = inst.get(_COMPUTED_MATRIX_PROP)
    if vals is None or len(vals) != 16:
        return None
    vals = list(vals)
    return mathutils.Matrix((vals[0:4], vals[4:8], vals[8:12], vals[12:16]))


def _matrices_close(a, b):
    """Element-wise comparison with combined absolute+relative tolerance —
    matrix_world channels are float32-backed, so exact or 1e-6 comparison would
    misclassify decompose/recompose round-trips as tweaks. 1e-5 keeps ~10x
    headroom over float32 round-trip noise while still detecting cm-scale
    tweaks at km-scale coordinates (1e-4 masked them)."""
    return all(
        abs(a[i][j] - b[i][j]) <= 1e-5 + 1e-5 * abs(b[i][j])
        for i in range(4) for j in range(4)
    )


def _resolve_instance_matrix(inst, computed):
    """Final world matrix for an instance given its freshly computed placement.
    Returns None when the instance has no usable baseline — either none stored
    (created before the baseline mechanism existed) or a singular one that no
    delta can be extracted from (e.g. a zero-scale source object) — and the
    caller keeps the legacy behavior. Untweaked (the instance still matches its
    baseline) resolves to the computed placement, so the instance follows the
    geometry. Tweaked resolves to the computed placement with the user's delta
    re-applied in the placement's local frame, so the tweak rides the joint: a
    rotation stays about the instance's own pivot and an offset follows the
    edge's direction."""
    stored = _get_stored_computed_matrix(inst)
    if stored is None or abs(stored.determinant()) < 1e-12:
        return None
    if _matrices_close(inst.matrix_world, stored):
        return computed.copy()
    try:
        delta = stored.inverted() @ inst.matrix_world
    except ValueError:
        return None
    return computed @ delta


def _apply_instance_matrix(inst, kind, matrix):
    """EDGE instances get decomposed quaternion channels (an Euler decomposition
    near the ±90° singularity gimbal-locks if the instance is later keyframed);
    VERT instances take the matrix directly."""
    if kind == 'EDGE':
        loc, rot, sca = matrix.decompose()
        inst.rotation_mode = 'QUATERNION'
        inst.location = loc
        inst.rotation_quaternion = rot
        inst.scale = sca
    else:
        inst.matrix_world = matrix


def _iter_insert_placements(operator, obj):
    """Yield (kind, index, source_obj, matrix_world) for every valid insert-mesh
    assignment on obj: kind 'VERT' places at the vertex (keeping the source
    object's world rotation/scale), kind 'EDGE' aligns local +Z along the edge and
    stretches to its length. Reports warnings for missing/non-mesh assignments and
    zero-length edges. Must be called in OBJECT mode (reads the RNA mesh layer)."""
    attr_node = obj.data.attributes.get("bspheres_node_mesh")
    if attr_node:
        for i, vert in enumerate(obj.data.vertices):
            mesh_name = _get_string_attr(attr_node.data[i])
            if not mesh_name:
                continue
            source_mesh_obj = bpy.data.objects.get(mesh_name)
            if source_mesh_obj is None or source_mesh_obj.type != 'MESH':
                operator.report({'WARNING'}, f"Insert mesh '{mesh_name}' for vertex {i} is missing or not a mesh.")
                continue
            matrix = source_mesh_obj.matrix_world.copy()
            matrix.translation = obj.matrix_world @ vert.co
            yield 'VERT', i, source_mesh_obj, matrix

    attr_edge = obj.data.attributes.get("bspheres_link_mesh")
    if attr_edge:
        for i, edge in enumerate(obj.data.edges):
            mesh_name = _get_string_attr(attr_edge.data[i])
            if not mesh_name:
                continue
            source_mesh_obj = bpy.data.objects.get(mesh_name)
            if source_mesh_obj is None or source_mesh_obj.type != 'MESH':
                operator.report({'WARNING'}, f"Insert mesh '{mesh_name}' for edge {i} is missing or not a mesh.")
                continue
            v0 = obj.data.vertices[edge.vertices[0]].co
            v1 = obj.data.vertices[edge.vertices[1]].co
            if (v1 - v0).length < 1e-6:
                operator.report({'WARNING'}, f"Skipping zero-length edge {i}.")
                continue
            midpoint = obj.matrix_world @ ((v0 + v1) / 2)
            edge_vec = (obj.matrix_world.to_3x3() @ (v1 - v0)).normalized()
            edge_len = (obj.matrix_world @ v1 - obj.matrix_world @ v0).length
            up = mathutils.Vector((0.0, 0.0, 1.0))
            rot = up.rotation_difference(edge_vec)
            matrix = (mathutils.Matrix.Translation(midpoint)
                      @ rot.to_matrix().to_4x4()
                      @ mathutils.Matrix.Diagonal((1.0, 1.0, edge_len, 1.0)))
            yield 'EDGE', i, source_mesh_obj, matrix


def _collect_insert_placements(operator, source_obj):
    """Placements for baking, resolved against the live instances in
    bSpheres_Inserts via _resolve_instance_matrix: untweaked instances follow the
    current geometry, tweaked instances keep their delta riding the placement.
    A stale instance (assignment changed without a refresh) keeps the computed
    transform and is reported. Note the bake evaluates the assigned source
    object's modifiers — modifier edits made on an instance copy are not baked.
    Must be called in OBJECT mode."""
    existing_node, existing_edge = _find_insert_instances(source_obj.name)
    placements = []
    for kind, i, source_mesh_obj, matrix in _iter_insert_placements(operator, source_obj):
        inst = (existing_node if kind == 'VERT' else existing_edge).get(i)
        if inst is not None:
            if inst.data == source_mesh_obj.data:
                resolved = _resolve_instance_matrix(inst, matrix)
                # Legacy instance without a baseline: its matrix wins, as before.
                matrix = inst.matrix_world.copy() if resolved is None else resolved
            else:
                operator.report(
                    {'WARNING'},
                    f"Insert instance for {kind.lower()} {i} is stale (assignment "
                    f"changed without a refresh) — using the computed placement.",
                )
        placements.append((kind, i, source_mesh_obj, matrix))
    return placements


def _join_inserts(operator, context, target_obj, placements):
    """Join evaluated copies of the given insert placements into target_obj.
    Each placement's *source object* is evaluated through the depsgraph, so the
    source's modifiers apply but modifier edits on instance copies do not.
    Must be called in OBJECT mode; selection/active are saved and restored.
    No-ops when placements is empty."""
    if not placements:
        return
    depsgraph = context.evaluated_depsgraph_get()
    baked = []
    for kind, i, source_mesh_obj, matrix in placements:
        eval_obj = source_mesh_obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=depsgraph)
        baked.append((mesh, matrix))

    target_col = target_obj.users_collection[0]
    temp_objs = []
    for mesh, matrix in baked:
        tmp = bpy.data.objects.new("bspheres_insert_tmp", mesh)
        target_col.objects.link(tmp)
        tmp.matrix_world = matrix
        temp_objs.append(tmp)

    prev_active = context.view_layer.objects.active
    prev_selected = list(context.selected_objects)
    try:
        for o in prev_selected:
            o.select_set(False)
        for t in temp_objs:
            t.select_set(True)
        target_obj.select_set(True)
        context.view_layer.objects.active = target_obj
        bpy.ops.object.join()
    finally:
        target_obj.select_set(False)
        for o in prev_selected:
            o.select_set(True)
        context.view_layer.objects.active = prev_active


def _maybe_join_inserts(operator, context, target_obj, source_obj):
    """Join source_obj's insert meshes into target_obj when use_include_inserts is
    on. Reads assignments live from source_obj, so the destructive Apply path
    cannot use this — it must collect placements before modifier apply and call
    _join_inserts directly."""
    if source_obj.bspheres_skin_settings.use_include_inserts:
        _join_inserts(operator, context, target_obj,
                      _collect_insert_placements(operator, source_obj))


class BSphereRefreshInsertMeshes(bpy.types.Operator):
    """Create or update insert mesh instances in the bSpheres_Inserts collection.
    Instances are matched by vertex/edge index, so refresh after topology edits"""
    bl_idname = 'bspheres.refresh_insert_meshes'
    bl_label = 'Refresh Insert Meshes'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        obj = context.active_object
        previous_mode = context.mode
        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            col = _ensure_collection("bSpheres_Inserts", context.scene)
            existing_node, existing_edge = _find_insert_instances(obj.name)

            live_verts = set()
            live_edges = set()
            for kind, i, source_mesh_obj, matrix in _iter_insert_placements(self, obj):
                existing = existing_node if kind == 'VERT' else existing_edge
                (live_verts if kind == 'VERT' else live_edges).add(i)
                inst = existing.get(i)
                if inst is not None and inst.data != source_mesh_obj.data:
                    # Reassigned to a different source: rebuild the instance so it
                    # picks up the new source's modifiers, not just its mesh data.
                    bpy.data.objects.remove(inst, do_unlink=True)
                    inst = None
                created = inst is None
                if created:
                    inst = source_mesh_obj.copy()
                    inst["bspheres_insert"] = True
                    inst["bspheres_source"] = obj.name
                    if kind == 'VERT':
                        inst["bspheres_vert_idx"] = i
                    else:
                        inst["bspheres_edge_idx"] = i
                    col.objects.link(inst)

                if created:
                    _apply_instance_matrix(inst, kind, matrix)
                else:
                    resolved = _resolve_instance_matrix(inst, matrix)
                    if resolved is not None:
                        _apply_instance_matrix(inst, kind, resolved)
                    elif kind == 'VERT':
                        # No usable baseline: apply the pre-baseline behavior
                        # once (location-only, preserving manual rotation and
                        # scale); the baseline stored below upgrades the
                        # instance for the next refresh.
                        inst.location = matrix.translation
                    else:
                        _apply_instance_matrix(inst, kind, matrix)
                _store_computed_matrix(inst, matrix)

            for vi, inst in existing_node.items():
                if vi not in live_verts:
                    bpy.data.objects.remove(inst, do_unlink=True)
            for ei, inst in existing_edge.items():
                if ei not in live_edges:
                    bpy.data.objects.remove(inst, do_unlink=True)
        finally:
            bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
        return {'FINISHED'}


# ── Feature 09: Branch Duplicate, Mirror, Radial ─────────────────────────────

class BSpheresDuplicateBranch(bpy.types.Operator):
    """Duplicate the downstream branch from the active vertex"""
    bl_idname = 'bspheres.duplicate_branch'
    bl_label = 'Duplicate Branch'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        result = _get_chain_graph(self, context)
        if result is None:
            return {'CANCELLED'}
        bm, parent_map, active_vert = result
        obj = context.active_object

        branch_bverts, branch_bedges = _get_branch_geom(bm, parent_map, active_vert)
        dup = bmesh.ops.duplicate(bm, geom=branch_bverts + branch_bedges)

        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        for elem in dup['geom']:
            if isinstance(elem, (bmesh.types.BMVert, bmesh.types.BMEdge)):
                elem.select = True

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


class BSpheresMirrorBranch(bpy.types.Operator):
    """Duplicate and mirror the downstream branch across the chosen axis (object-local space)"""
    bl_idname = 'bspheres.mirror_branch'
    bl_label = 'Mirror Branch'
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(
        name="Axis",
        items=[('X', "X", "Mirror across the YZ plane"),
               ('Y', "Y", "Mirror across the XZ plane"),
               ('Z', "Z", "Mirror across the XY plane")],
        default='X',
    )

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        result = _get_chain_graph(self, context)
        if result is None:
            return {'CANCELLED'}
        bm, parent_map, active_vert = result
        obj = context.active_object

        branch_bverts, branch_bedges = _get_branch_geom(bm, parent_map, active_vert, exclude_root=True)
        if not branch_bverts:
            self.report({'WARNING'}, "Active vertex has no children to mirror.")
            return {'CANCELLED'}
        # Resolve the direct children before duplicating — the lookup table is
        # invalidated once new geometry is added.
        child_verts = _direct_child_verts(bm, parent_map, active_vert.index)
        dup = bmesh.ops.duplicate(bm, geom=branch_bverts + branch_bedges)

        for elem in dup['geom']:
            if isinstance(elem, bmesh.types.BMVert):
                if self.axis == 'X':
                    elem.co.x = -elem.co.x
                elif self.axis == 'Y':
                    elem.co.y = -elem.co.y
                else:
                    elem.co.z = -elem.co.z

        # Re-attach the mirrored branch at the active vertex so it stays
        # reachable from the root (skin connectivity, chain selection, and
        # armature generation all depend on it).
        attach_edges = []
        for cv in child_verts:
            new_v = dup['vert_map'].get(cv)
            if new_v is not None:
                attach_edges.append(bm.edges.new((active_vert, new_v)))

        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        for elem in dup['geom'] + attach_edges:
            if isinstance(elem, (bmesh.types.BMVert, bmesh.types.BMEdge)):
                elem.select = True

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


class BSpheresRadialDuplicate(bpy.types.Operator):
    """Duplicate the downstream branch radially around the active vertex"""
    bl_idname = 'bspheres.radial_duplicate'
    bl_label = 'Radial Duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    count: bpy.props.IntProperty(
        name="Count", min=2, max=32, default=4,
        description="Total number of copies including the original",
    )
    axis: EnumProperty(
        name="Axis",
        items=[('X', "X", "Rotate around the X axis"),
               ('Y', "Y", "Rotate around the Y axis"),
               ('Z', "Z", "Rotate around the Z axis")],
        default='Z',
    )

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        result = _get_chain_graph(self, context)
        if result is None:
            return {'CANCELLED'}
        bm, parent_map, active_vert = result
        obj = context.active_object

        branch_bverts, branch_bedges = _get_branch_geom(bm, parent_map, active_vert, exclude_root=True)
        if not branch_bverts:
            self.report({'WARNING'}, "Active vertex has no children to duplicate radially.")
            return {'CANCELLED'}
        pivot = active_vert.co.copy()
        axis_vec = mathutils.Vector(
            (1.0, 0.0, 0.0) if self.axis == 'X' else
            (0.0, 1.0, 0.0) if self.axis == 'Y' else
            (0.0, 0.0, 1.0)
        )
        # Resolve the direct children before duplicating — the lookup table is
        # invalidated once new geometry is added.
        child_verts = _direct_child_verts(bm, parent_map, active_vert.index)

        all_new = []
        for i in range(1, self.count):
            angle = (2.0 * math.pi / self.count) * i
            rot = mathutils.Matrix.Rotation(angle, 4, axis_vec)
            dup = bmesh.ops.duplicate(bm, geom=branch_bverts + branch_bedges)
            for elem in dup['geom']:
                if isinstance(elem, bmesh.types.BMVert):
                    elem.co = rot @ (elem.co - pivot) + pivot
            # Re-attach each copy at the active vertex so it stays reachable
            # from the root (skin connectivity, chain selection, armature).
            for cv in child_verts:
                new_v = dup['vert_map'].get(cv)
                if new_v is not None:
                    all_new.append(bm.edges.new((active_vert, new_v)))
            all_new.extend(dup['geom'])

        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        for elem in all_new:
            if isinstance(elem, (bmesh.types.BMVert, bmesh.types.BMEdge)):
                elem.select = True

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


class BSphereTaperBranch(bpy.types.Operator):
    """Taper skin radii from the active vertex down to an end radius at the branch tips"""
    bl_idname = 'bspheres.taper_branch'
    bl_label = 'Taper Branch'
    bl_options = {'REGISTER', 'UNDO'}

    end_radius: FloatProperty(
        name="End Radius", default=0.01, min=0.0001, max=1.0,
        description="Skin radius at the farthest vertex of the branch",
    )

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object) and context.mode == 'EDIT_MESH'

    def execute(self, context):
        result = _get_chain_graph(self, context)
        if result is None:
            return {'CANCELLED'}
        bm, parent_map, active_vert = result
        obj = context.active_object

        children_map = _build_children_map(parent_map)

        # Geometric path distance from the active vertex, so unevenly spaced
        # joints still taper smoothly.
        bm.verts.ensure_lookup_table()
        dist = {active_vert.index: 0.0}
        queue = deque([active_vert.index])
        while queue:
            v_idx = queue.popleft()
            v_co = bm.verts[v_idx].co
            for c in children_map.get(v_idx, []):
                dist[c] = dist[v_idx] + (bm.verts[c].co - v_co).length
                queue.append(c)
        del dist[active_vert.index]  # the active vertex keeps its radius

        if not dist:
            self.report({'INFO'}, "No child vertices found from active vertex.")
            return {'FINISHED'}

        layer = bm.verts.layers.skin[0]
        start = active_vert[layer].radius
        start = (start[0], start[1])
        max_dist = max(dist.values())
        for v_idx, d in dist.items():
            t = d / max_dist if max_dist > 0 else 1.0
            bm.verts[v_idx][layer].radius = (
                start[0] + (self.end_radius - start[0]) * t,
                start[1] + (self.end_radius - start[1]) * t,
            )

        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


# ── Feature 10: Output Presets ───────────────────────────────────────────────

class BSpheresApplyPreset(bpy.types.Operator):
    """Apply a bSkin output preset to the active bSphere"""
    bl_idname = 'bspheres.apply_preset'
    bl_label = 'Apply Preset'
    bl_options = {'REGISTER', 'UNDO'}

    PRESETS = {
        'ORGANIC_SMOOTH': {
            'use_voxel_remesh': True,  'voxel_size': 0.02,
            'use_smooth_shading': True, 'use_merge_doubles': True,
            'merge_threshold': 0.001,  'use_recalc_normals': True,
            'warn_thin_branches': True, 'min_branch_radius': 0.01,
            '_subdivision_levels': 3,
        },
        'HUMANOID_BASEMESH': {
            'use_voxel_remesh': True,  'voxel_size': 0.02,
            'use_smooth_shading': True, 'use_merge_doubles': True,
            'merge_threshold': 0.001,  'use_recalc_normals': True,
            'warn_thin_branches': True, 'min_branch_radius': 0.01,
            '_subdivision_levels': 2,
        },
        'CREATURE_LIMBS': {
            'use_voxel_remesh': True,  'voxel_size': 0.015,
            'use_smooth_shading': True, 'use_merge_doubles': True,
            'merge_threshold': 0.0005, 'use_recalc_normals': True,
            'warn_thin_branches': True, 'min_branch_radius': 0.005,
            '_subdivision_levels': 3,
        },
        'TENTACLES': {
            'use_voxel_remesh': True,  'voxel_size': 0.015,
            'use_smooth_shading': True, 'use_merge_doubles': False,
            'use_recalc_normals': True, 'warn_thin_branches': True,
            'min_branch_radius': 0.003, '_subdivision_levels': 4,
        },
        'HARD_MANNEQUIN': {
            'use_voxel_remesh': False, 'use_smooth_shading': False,
            'use_merge_doubles': True, 'merge_threshold': 0.001,
            'use_recalc_normals': False, 'warn_thin_branches': False,
            '_subdivision_levels': 2,
        },
        'LOW_POLY_BLOCKOUT': {
            'use_voxel_remesh': False, 'use_smooth_shading': False,
            'use_merge_doubles': False, 'use_recalc_normals': False,
            'warn_thin_branches': False, '_subdivision_levels': 1,
        },
        'PRINT_SOLID': {
            'use_voxel_remesh': True,  'voxel_size': 0.008,
            'use_smooth_shading': True, 'use_merge_doubles': True,
            'merge_threshold': 0.0001, 'use_recalc_normals': True,
            'warn_thin_branches': True, 'min_branch_radius': 0.005,
            '_subdivision_levels': 3,
        },
    }

    preset: EnumProperty(
        name="Preset",
        items=_PRESET_ITEMS,
        default='ORGANIC_SMOOTH',
    )

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        obj = context.active_object
        settings = obj.bspheres_skin_settings
        for key, val in self.PRESETS[self.preset].items():
            if key == '_subdivision_levels':
                mod = next((m for m in obj.modifiers if m.type == 'SUBSURF'), None)
                if mod:
                    mod.levels = val
            else:
                if not hasattr(type(settings), key):
                    self.report({'ERROR'}, f"BUG: unknown preset key '{key}'")
                    return {'CANCELLED'}
                setattr(settings, key, val)
        return {'FINISHED'}


class BSpheresPanel(bpy.types.Panel):
    bl_idname = 'OBJECT_PT_bSpheres_Panel'
    bl_label = 'bSpheres NX'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'bSpheres NX'
 
    def draw(self, context):
        layout = self.layout
        obj = context.object
        
        split = layout.split()
        col = split.column()
        col.label(text="Create bSphere Mesh")
        sub = col.column(align=True)
        sub.operator("mesh.primitive_bsphere_add", text="Create")
        
        if obj:
            if obj.modifiers:
                for modifier in obj.modifiers:
                    if modifier.type == "MIRROR":
                        axis_text = "XYZ"
                        layout.label(text="Mirror Axis:")
                        row = layout.row()
                        for i, text in enumerate(axis_text):
                            row.prop(modifier, "use_axis", text=text, index=i)
                    if modifier.type == "SUBSURF":
                        layout.label(text="Subdivisions:")
                        split = layout.split()
                        col = split.column()
                        sub = col.column(align=True)
                        sub.prop(modifier, "levels", text="Viewport")
                    if modifier.type == "SKIN":
                        split = layout.split()
                        col = split.column()
                        col.label(text="Selected Vertices:")
                        sub = col.column(align=True)
                        sub.operator("object.skin_loose_mark_clear", text="Mark Loose").action = 'MARK'
                        sub.operator("object.skin_loose_mark_clear", text="Clear Loose").action = 'CLEAR'
                        sub = col.column()
                        sub.operator("object.skin_root_mark", text="Mark Root")
            
                if _is_bsphere_control(obj):
                    settings = obj.bspheres_skin_settings
                    layout.label(text="bSkin Settings:")
                    box = layout.column(align=True)
                    row = box.row(align=True)
                    row.prop(settings, "last_preset", text="")
                    op = row.operator("bspheres.apply_preset", text="Apply")
                    op.preset = settings.last_preset
                    row = box.row(align=True)
                    row.prop(settings, "use_voxel_remesh", text="Remesh")
                    row.prop(settings, "voxel_size", text="Size")
                    box.prop(settings, "use_smooth_shading", text="Shade Smooth")
                    row = box.row(align=True)
                    row.prop(settings, "use_merge_doubles", text="Merge Doubles")
                    sub = row.row()
                    sub.active = settings.use_merge_doubles
                    sub.prop(settings, "merge_threshold", text="Dist")
                    box.prop(settings, "use_recalc_normals", text="Recalculate Normals")
                    box.prop(settings, "use_include_inserts", text="Include Inserts")
                    row = box.row(align=True)
                    row.prop(settings, "warn_thin_branches", text="Warn Thin Branches")
                    sub = row.row()
                    sub.active = settings.warn_thin_branches
                    sub.prop(settings, "min_branch_radius", text="Min")

                    layout.label(text="Preview:")
                    row = layout.row(align=True)
                    row.operator("bspheres.preview_bskin", text="Preview / Refresh")
                    row.operator("bspheres.delete_bskin_preview", text="Delete")

                    layout.label(text="Armature:")
                    layout.operator("bspheres.generate_armature", text="Generate Armature")

                    layout.label(text="Insert Meshes:")
                    layout.operator("bspheres.refresh_insert_meshes", text="Refresh Insert Meshes")

                    if context.mode == 'EDIT_MESH':
                        bm = bmesh.from_edit_mesh(obj.data)
                        active_elem = bm.select_history.active
                        if isinstance(active_elem, bmesh.types.BMVert):
                            layout.label(text="Selected Node:")
                            box2 = layout.column(align=True)
                            skin_layers = bm.verts.layers.skin
                            if skin_layers:
                                sv = active_elem[skin_layers[0]]
                                r = sv.radius
                                box2.label(text=f"Skin: {r[0]:.3f} × {r[1]:.3f}")
                                box2.label(text=f"Root: {sv.use_root}  Loose: {sv.use_loose}")
                            box2.operator("bspheres.set_skin_radius", text="Set Radius")
                            row2 = box2.row(align=True)
                            row2.operator("bspheres.mark_preserve", text="Mark Preserve")
                            row2.operator("bspheres.clear_preserve", text="Clear Preserve")
                            layout.label(text="Assign Insert Meshes:")
                            box3 = layout.column(align=True)
                            row3a = box3.row(align=True)
                            row3a.prop_search(settings, "insert_node_mesh_name", bpy.data, "objects", text="Node")
                            row3a.operator("bspheres.assign_node_mesh", text="Set")
                            row3b = box3.row(align=True)
                            row3b.prop_search(settings, "insert_link_mesh_name", bpy.data, "objects", text="Link")
                            row3b.operator("bspheres.assign_link_mesh", text="Set")
                            box3.operator("bspheres.clear_insert_mesh", text="Clear Active Node")
                            layout.label(text="Chain Selection:")
                            row3 = layout.row(align=True)
                            row3.operator("bspheres.select_child_chain", text="Select Children")
                            row3.operator("bspheres.select_parent_chain", text="Select Parents")
                            layout.label(text="Branch Tools:")
                            box4 = layout.column(align=True)
                            box4.operator("bspheres.duplicate_branch", text="Duplicate Branch")
                            row4 = box4.row(align=True)
                            row4.label(text="Mirror:")
                            op4 = row4.operator("bspheres.mirror_branch", text="X")
                            op4.axis = 'X'
                            op4 = row4.operator("bspheres.mirror_branch", text="Y")
                            op4.axis = 'Y'
                            op4 = row4.operator("bspheres.mirror_branch", text="Z")
                            op4.axis = 'Z'
                            box4.operator("bspheres.radial_duplicate", text="Radial Duplicate")
                            box4.operator("bspheres.taper_branch", text="Taper Branch")

                split = layout.split()
                col = split.column()
                col.label(text="Convert to Sculptable Mesh")
                sub = col.column(align=True)
                sub.operator("bspheres.make_bskin", text="Make bSkin")
                sub.operator("bspheres.make_rigged_bskin", text="Make Rigged bSkin")
                sub.operator("tcg.apply_bsphere_modifiers", text="Apply")
                layout.label(text="Extrude Vert: E")
                layout.label(text="Scale Vert: Ctrl-A")
                layout.label(text="Add Vert Between Verts: Ctrl-R")