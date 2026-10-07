# The Trigger
# Role: An operator that toggles the pole overlay (handy for a keymap entry or the F3 search).
# Interplay: Flips `scene.valency.enabled`; the draw handler in `draw_handler.py` reads that setting.

import bpy


class VALENCY_OT_toggle_visualization(bpy.types.Operator):
    """Toggle the vertex pole visualization overlay"""
    bl_idname = "valency.toggle_visualization"
    bl_label = "Toggle Pole Visualization"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        settings = context.scene.valency
        settings.enabled = not settings.enabled
        self.report({"INFO"}, "Pole visualization " + ("enabled" if settings.enabled else "disabled"))
        return {"FINISHED"}


def register():
    bpy.utils.register_class(VALENCY_OT_toggle_visualization)


def unregister():
    bpy.utils.unregister_class(VALENCY_OT_toggle_visualization)
