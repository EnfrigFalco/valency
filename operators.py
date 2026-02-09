# The Trigger
# Role: Contains the logic to toggle the visualization on and off.
# Interplay: Poll logic restricts the tool to Edit Mode.
#     Execution: When clicked, it calls `draw_handler.register()` or `unregister()`.
#     Bmesh Analysis: It performs the "Snaphot" loop (using the `v.co.copy()` logic we discussed) and passes that dictionary of coordinates to the `draw_handler`.

import bpy
from . import draw_handler


class VALENCY_OT_toggle_visualization(bpy.types.Operator):
    """Toggle the vertex pole visualization overlay."""
    bl_idname = "valency.toggle_visualization"
    bl_label = "Toggle Pole Visualization"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Only available in Edit Mode with an active object."""
        return (
            context.mode == "EDIT_MESH"
            and context.active_object is not None
            and context.active_object.type == "MESH"
        )

    def execute(self, context):
        """Toggle visualization on/off."""
        if draw_handler.is_registered():
            # Unregister: stop visualization
            draw_handler.unregister()
            context.scene.valency_visualization_enabled = False
            self.report({"INFO"}, "Pole visualization disabled")
        else:
            # Register: analyze mesh and start visualization
            pole_data = self._analyze_mesh(context)
            draw_handler.register(pole_data, context)
            context.scene.valency_visualization_enabled = True
            self.report({"INFO"}, "Pole visualization enabled")

        return {"FINISHED"}

    def invoke(self, context, event):
        """Allow invoke to support tool activation."""
        return self.execute(context)

    def _analyze_mesh(self, context):
        """Analyze mesh topology and collect pole coordinates with vertex indices."""
        return draw_handler.build_pole_data(context)


def register():
    """Register the operator class."""
    bpy.utils.register_class(VALENCY_OT_toggle_visualization)


def unregister():
    """Unregister the operator class."""
    bpy.utils.unregister_class(VALENCY_OT_toggle_visualization)