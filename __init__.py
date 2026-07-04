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
    bpy.utils.register_class(BSpheresPreferences)
    bpy.utils.register_class(BSpheresSkinSettings)
    bpy.types.Object.bspheres_skin_settings = bpy.props.PointerProperty(
        type=BSpheresSkinSettings
    )
    bpy.utils.register_class(AddBMesh)
    bpy.utils.register_class(applyBSphereModifiers)
    bpy.utils.register_class(MakeBSkin)
    bpy.utils.register_class(MakeRiggedBSkin)
    bpy.utils.register_class(PreviewBSkin)
    bpy.utils.register_class(DeleteBSkinPreview)
    bpy.utils.register_class(BSphereMarkPreserve)
    bpy.utils.register_class(BSphereClearPreserve)
    bpy.utils.register_class(BSphereSetSkinRadius)
    bpy.utils.register_class(GenerateBSphereArmature)
    bpy.utils.register_class(BSphereSelectChildChain)
    bpy.utils.register_class(BSphereSelectParentChain)
    bpy.utils.register_class(BSphereAssignNodeMesh)
    bpy.utils.register_class(BSphereAssignLinkMesh)
    bpy.utils.register_class(BSphereClearInsertMesh)
    bpy.utils.register_class(BSphereRefreshInsertMeshes)
    bpy.utils.register_class(BSpheresDuplicateBranch)
    bpy.utils.register_class(BSpheresMirrorBranch)
    bpy.utils.register_class(BSpheresRadialDuplicate)
    bpy.utils.register_class(BSphereTaperBranch)
    bpy.utils.register_class(BSpheresApplyPreset)
    bpy.utils.register_class(BSpheresPanel)

def unregister():
    bpy.utils.unregister_class(BSpheresPanel)
    bpy.utils.unregister_class(BSpheresApplyPreset)
    bpy.utils.unregister_class(BSphereTaperBranch)
    bpy.utils.unregister_class(BSpheresRadialDuplicate)
    bpy.utils.unregister_class(BSpheresMirrorBranch)
    bpy.utils.unregister_class(BSpheresDuplicateBranch)
    bpy.utils.unregister_class(BSphereRefreshInsertMeshes)
    bpy.utils.unregister_class(BSphereClearInsertMesh)
    bpy.utils.unregister_class(BSphereAssignLinkMesh)
    bpy.utils.unregister_class(BSphereAssignNodeMesh)
    bpy.utils.unregister_class(BSphereSelectParentChain)
    bpy.utils.unregister_class(BSphereSelectChildChain)
    bpy.utils.unregister_class(GenerateBSphereArmature)
    bpy.utils.unregister_class(BSphereSetSkinRadius)
    bpy.utils.unregister_class(BSphereClearPreserve)
    bpy.utils.unregister_class(BSphereMarkPreserve)
    bpy.utils.unregister_class(DeleteBSkinPreview)
    bpy.utils.unregister_class(PreviewBSkin)
    bpy.utils.unregister_class(MakeRiggedBSkin)
    bpy.utils.unregister_class(MakeBSkin)
    bpy.utils.unregister_class(applyBSphereModifiers)
    bpy.utils.unregister_class(AddBMesh)
    del bpy.types.Object.bspheres_skin_settings
    bpy.utils.unregister_class(BSpheresSkinSettings)
    bpy.utils.unregister_class(BSpheresPreferences)

if __name__ == '__main__':
    register()