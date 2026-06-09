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

# Extension metadata lives in blender_manifest.toml (Extensions system, Blender 4.2+).

import bpy
from . bSpheres import *

def register():
    bpy.utils.register_class(BSpheresSkinSettings)
    bpy.types.Object.bspheres_skin_settings = bpy.props.PointerProperty(
        type=BSpheresSkinSettings
    )
    bpy.utils.register_class(AddBMesh)
    bpy.utils.register_class(applyBSphereModifiers)
    bpy.utils.register_class(MakeBSkin)
    bpy.utils.register_class(PreviewBSkin)
    bpy.utils.register_class(DeleteBSkinPreview)
    bpy.utils.register_class(BSphereMarkPreserve)
    bpy.utils.register_class(BSphereClearPreserve)
    bpy.utils.register_class(BSpheresPanel)

def unregister():
    bpy.utils.unregister_class(BSpheresPanel)
    bpy.utils.unregister_class(BSphereClearPreserve)
    bpy.utils.unregister_class(BSphereMarkPreserve)
    bpy.utils.unregister_class(DeleteBSkinPreview)
    bpy.utils.unregister_class(PreviewBSkin)
    bpy.utils.unregister_class(MakeBSkin)
    bpy.utils.unregister_class(applyBSphereModifiers)
    bpy.utils.unregister_class(AddBMesh)
    del bpy.types.Object.bspheres_skin_settings
    bpy.utils.unregister_class(BSpheresSkinSettings)

if __name__ == '__main__':
    register()