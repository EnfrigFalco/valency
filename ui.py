# The User Interface
# Role: Adds the pole visualization settings to the Edit Mode "Mesh Edit Mode" overlay popover.
# Documentation: https://docs.blender.org/api/current/bpy.types.Panel.html
# View UI Code
#   Enable Developer Extras > Edit > Preferences
#   Right-click on any button, property, or menu item in the UI > Select Edit Source
#   Open the Text Editor area in Blender.

import bpy
from bpy.types import Panel


class VIEW3D_PT_overlay_edit_mesh_valency(Panel):
    """Pole Visualization settings in the Edit Mode mesh overlay menu."""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_parent_id = "VIEW3D_PT_overlay_edit_mesh"
    bl_label = "Pole Visualization"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw_header(self, context):
        self.layout.prop(context.scene.valency, "enabled", text="")

    def draw(self, context):
        layout = self.layout
        settings = context.scene.valency

        col = layout.column()
        col.active = settings.enabled and context.space_data.overlay.show_overlays
        col.prop(settings, "icon_size")
        col.prop(settings, "cull_backfaces")
        col.prop(settings, "show_regular")


def register():
    bpy.utils.register_class(VIEW3D_PT_overlay_edit_mesh_valency)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_overlay_edit_mesh_valency)
