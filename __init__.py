# The Orchestrator
# Role: Handles registration and unregistration.
# Interplay: Imports `operators.py`, `ui.py`, and `draw_handler.py`.
# Note: The draw handler is registered once and stays registered; it returns immediately unless the
#       overlay is enabled and a mesh is in Edit Mode. That keeps it in sync across mode changes,
#       file loads and multiple 3D Views without any extra bookkeeping.

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, IntProperty, PointerProperty
from . import operators, ui, draw_handler


def _redraw_3d_views(context=None):
    wm = (context or bpy.context).window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _on_setting_changed(self, context):
    draw_handler.mark_dirty()
    _redraw_3d_views(context)


class ValencySettings(bpy.types.PropertyGroup):
    enabled: BoolProperty(
        name="Show Poles",
        description="Show an icon on every vertex according to its valence (number of connected edges)",
        default=False,
        update=_on_setting_changed,
    )
    icon_size: IntProperty(
        name="Icon Size",
        description="Icon size in pixels (scaled by the interface Resolution Scale)",
        default=24, min=4, max=128,
        update=_on_setting_changed,
    )
    cull_backfaces: BoolProperty(
        name="Hide Backfacing",
        description="Hide icons on vertices facing away from the view (ignored in X-Ray)",
        default=True,
        update=_on_setting_changed,
    )
    show_regular: BoolProperty(
        name="Show Valence 4",
        description="Also show icons on regular (4-edge) vertices",
        default=True,
        update=_on_setting_changed,
    )


@persistent
def _on_depsgraph_update(scene, depsgraph):
    # Edit-mode changes (moving, adding, deleting vertices) arrive here as geometry updates.
    for update in depsgraph.updates:
        if update.is_updated_geometry and isinstance(update.id, (bpy.types.Object, bpy.types.Mesh)):
            draw_handler.mark_dirty()
            return


@persistent
def _on_undo_redo(scene, *args):
    draw_handler.mark_dirty()


_handler_lists = (
    (bpy.app.handlers.depsgraph_update_post, _on_depsgraph_update),
    (bpy.app.handlers.undo_post, _on_undo_redo),
    (bpy.app.handlers.redo_post, _on_undo_redo),
    (bpy.app.handlers.load_post, _on_undo_redo),
)


def register():
    bpy.utils.register_class(ValencySettings)
    bpy.types.Scene.valency = PointerProperty(type=ValencySettings)
    operators.register()
    ui.register()
    for handlers, func in _handler_lists:
        if func not in handlers:
            handlers.append(func)
    draw_handler.register()
    # bpy.data is restricted during registration; load the icons right after.
    bpy.app.timers.register(draw_handler.load_icon_pixels, first_interval=0.0)


def unregister():
    if bpy.app.timers.is_registered(draw_handler.load_icon_pixels):
        bpy.app.timers.unregister(draw_handler.load_icon_pixels)
    draw_handler.unregister()
    for handlers, func in _handler_lists:
        if func in handlers:
            handlers.remove(func)
    ui.unregister()
    operators.unregister()
    del bpy.types.Scene.valency
    bpy.utils.unregister_class(ValencySettings)
