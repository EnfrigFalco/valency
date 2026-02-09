# The User Interface
# Role: Houses the buttons and menus.
# Interplay: Adds a checkbox to the Edit Mode MeshEdit overlay menu that toggles pole visualization.
# Documentation: https://docs.blender.org/api/current/bpy.types.Panel.html
# View UI Code
#   Enable Developer Extras > Edit > Preferences
#   Right-click on any button, property, or menu item in the UI > Select Edit Source
#   Open the Text Editor area in Blender.

import bpy
from bpy.types import Panel


class VIEW3D_PT_overlay_edit_mesh_valency(Panel):
    """Pole Visualization checkbox in the Edit Mode mesh overlay menu."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_parent_id = "VIEW3D_PT_overlay_edit_mesh"
    bl_label = "Pole Visualization"

    @classmethod
    def poll(cls, context):
        """Only show in Edit Mode with active mesh."""
        return (
            context.mode == 'EDIT_MESH'
            and context.active_object is not None
            and context.active_object.type == 'MESH'
        )

    def draw(self, context):
        """Draw the pole visualization checkbox."""
        layout = self.layout
        
        scene = context.scene
        
        col = layout.column()
        
        # Create a checkbox property that toggles visualization
        row = col.row()
        row.prop(scene, "valency_visualization_enabled", text="Show Poles")


def register():
    """Register UI classes."""
    bpy.utils.register_class(VIEW3D_PT_overlay_edit_mesh_valency)


def unregister():
    """Unregister UI classes."""
    bpy.utils.unregister_class(VIEW3D_PT_overlay_edit_mesh_valency)