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
        settings = obj.bspheres_skin_settings
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

    default_mirror_x: bpy.props.BoolProperty(name="X", default=False)
    default_mirror_y: bpy.props.BoolProperty(name="Y", default=True)
    default_mirror_z: bpy.props.BoolProperty(name="Z", default=False)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Default Mirror Axes on Create:")
        row = layout.row()
        row.prop(self, "default_mirror_x", text="X")
        row.prop(self, "default_mirror_y", text="Y")
        row.prop(self, "default_mirror_z", text="Z")


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
        prefs = bpy.context.preferences.addons[__package__].preferences
        bpy.context.object.modifiers["Mirror"].use_axis = (
            prefs.default_mirror_x,
            prefs.default_mirror_y,
            prefs.default_mirror_z,
        )
        bpy.ops.object.modifier_add(type='SKIN')
        bpy.ops.object.modifier_add(type='SUBSURF')
        bpy.context.object.modifiers["Skin"].use_x_symmetry = False
        bpy.context.object.modifiers["Skin"].use_y_symmetry = False
        bpy.context.object.modifiers["Skin"].use_z_symmetry = False
        bpy.context.object.modifiers["Subdivision"].render_levels = 3
        bpy.context.object.modifiers["Subdivision"].levels = 3
        bpy.context.object.modifiers["Subdivision"].quality = 3
        
        bpy.ops.object.mode_set(mode='EDIT')
        context.space_data.shading.show_xray = True
        
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


def _get_chain_graph(operator, context):
    obj = context.active_object
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    skin_layers = bm.verts.layers.skin
    if not skin_layers:
        operator.report({'WARNING'}, "No skin layer found.")
        return None
    skin_layer = skin_layers[0]

    root_vert = next((v for v in bm.verts if v[skin_layer].use_root), None)
    if root_vert is None:
        operator.report({'WARNING'}, "No skin root marked. Mark a vertex as root first.")
        return None

    active = bm.select_history.active
    if not isinstance(active, bmesh.types.BMVert):
        operator.report({'WARNING'}, "No active vertex. Select a vertex first.")
        return None

    adj = {v.index: [e.other_vert(v).index for e in v.link_edges] for v in bm.verts}
    parent_map, found_cycle = _bfs_tree(adj, root_vert.index)

    if active.index not in parent_map:
        operator.report({'WARNING'}, "Active vertex is not reachable from root.")
        return None
    if found_cycle:
        operator.report({'WARNING'}, "Cycle detected in mesh graph.")

    return bm, parent_map, active


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

        depsgraph = context.evaluated_depsgraph_get()
        evaluated_obj = source_obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated_obj, depsgraph=depsgraph)

        name = source_obj.name
        output_name = ('bSkin' + name[7:]) if name.startswith('bSphere') else 'bSkin'

        new_obj = bpy.data.objects.new(output_name, mesh)
        new_obj.matrix_world = source_obj.matrix_world.copy()

        col = _ensure_collection("bSpheres_Output", context.scene)
        col.objects.link(new_obj)

        _apply_bskin_settings(new_obj, source_obj.bspheres_skin_settings, context)
        bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
        return {"FINISHED"}


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
    warn_thin_branches: bpy.props.BoolProperty(
        name="Warn Thin Branches", default=True,
        description="Report a warning when a vertex skin radius is below the minimum",
    )
    min_branch_radius: bpy.props.FloatProperty(
        name="Min Radius", default=0.01, min=0.0001, max=1.0, step=0.01,
        description="Skin radius below which a warning is issued",
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


class GenerateBSphereArmature(bpy.types.Operator):
    """Generate a Blender armature from the bSphere control mesh"""
    bl_idname = 'bspheres.generate_armature'
    bl_label = 'Generate Armature'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _is_bsphere_control(context.active_object)

    def execute(self, context):
        obj = context.active_object
        previous_mode = context.mode

        bpy.ops.object.mode_set(mode='OBJECT')

        root_idx = _find_skin_root(obj)
        if root_idx < 0:
            self.report({'ERROR'}, "No skin root marked. Mark a vertex as root first.")
            bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))
            return {'CANCELLED'}

        adj = _build_mesh_graph(obj)
        parent_map, found_cycle = _bfs_tree(adj, root_idx)

        if found_cycle:
            self.report({'WARNING'}, "Cycle detected in mesh graph — cycle edges are skipped.")

        n_verts = len(obj.data.vertices)
        if len(parent_map) < n_verts:
            self.report(
                {'WARNING'},
                f"{n_verts - len(parent_map)} vertices not reachable from root — they will not become bones.",
            )

        world_positions = [obj.matrix_world @ v.co for v in obj.data.vertices]

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

            bone_refs = {}
            for child_idx, par_idx in parent_map.items():
                if par_idx is None:
                    continue
                head = world_positions[par_idx]
                tail = world_positions[child_idx]
                if (tail - head).length < 1e-6:
                    self.report({'WARNING'}, f"Skipping zero-length edge {par_idx}→{child_idx}.")
                    continue
                bone = arm_data.edit_bones.new(f"bone_{par_idx}_{child_idx}")
                bone.head = head
                bone.tail = tail
                bone_refs[child_idx] = (bone, par_idx)

            for child_idx, (bone, par_idx) in bone_refs.items():
                if par_idx in bone_refs:
                    bone.parent = bone_refs[par_idx][0]
                elif par_idx != root_idx:
                    self.report(
                        {'WARNING'},
                        f"Bone for vertex {child_idx} is disconnected — "
                        f"its parent edge to vertex {par_idx} was skipped.",
                    )

            bpy.ops.object.mode_set(mode='OBJECT')
        finally:
            arm_obj.select_set(False)
            obj.select_set(True)
            for o in other_selected:
                o.select_set(True)
            context.view_layer.objects.active = prev_active
            bpy.ops.object.mode_set(mode=_MODE_SET_MAP.get(previous_mode, previous_mode))

        self.report({'INFO'}, f"Armature '{arm_name}' generated. Note: only the unmirrored half is included.")
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

        children_map = {}
        for child, par in parent_map.items():
            if par is not None:
                children_map.setdefault(par, []).append(child)

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
                    row.prop(settings, "use_voxel_remesh", text="Remesh")
                    row.prop(settings, "voxel_size", text="Size")
                    box.prop(settings, "use_smooth_shading", text="Shade Smooth")
                    row = box.row(align=True)
                    row.prop(settings, "use_merge_doubles", text="Merge Doubles")
                    sub = row.row()
                    sub.active = settings.use_merge_doubles
                    sub.prop(settings, "merge_threshold", text="Dist")
                    box.prop(settings, "use_recalc_normals", text="Recalculate Normals")
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
                            row2 = box2.row(align=True)
                            row2.operator("bspheres.mark_preserve", text="Mark Preserve")
                            row2.operator("bspheres.clear_preserve", text="Clear Preserve")
                            layout.label(text="Chain Selection:")
                            row3 = layout.row(align=True)
                            row3.operator("bspheres.select_child_chain", text="Select Children")
                            row3.operator("bspheres.select_parent_chain", text="Select Parents")

                split = layout.split()
                col = split.column()
                col.label(text="Convert to Sculptable Mesh")
                sub = col.column(align=True)
                sub.operator("bspheres.make_bskin", text="Make bSkin")
                sub.operator("tcg.apply_bsphere_modifiers", text="Apply")
                layout.label(text="Extrude Vert: E")
                layout.label(text="Scale Vert: Ctrl-A")
                layout.label(text="Add Vert Between Verts: Ctrl-R")