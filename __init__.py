# The Orchestrator
# Role: Handles registration and unregistration.
# Interplay: Imports `operators.py`, `ui.py`, and `draw_handler.py`.
# Note: It should not load icons or start the draw handler here. It simply makes the commands available to Blender’s interface.

import bpy
from bpy.props import BoolProperty
from . import operators, ui, draw_handler

bl_info = {
    "name": "Valency",
    "author": "Enfrig Falco",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Toolbar",
    "description": "Topological valence and pole visualization for mesh editing",
    "category": "3D View",
}

_in_callback = False
_last_mode = None
_last_mesh_update = 0


def _on_mesh_change(scene):
    """Handler to detect mesh changes and update pole visualization in real-time."""
    global _last_mesh_update
    
    try:
        # Only update if visualization is enabled and we're in Edit Mode
        if not scene.valency_visualization_enabled or bpy.context.mode != "EDIT_MESH":
            return
        
        # Throttle updates to avoid excessive recomputation
        import time
        current_time = time.time()
        if current_time - _last_mesh_update < 0.1:  # Update max once per 100ms
            return
        
        _last_mesh_update = current_time
        
        # Re-analyze the mesh and update pole data
        if draw_handler.is_registered():
            pole_data = draw_handler.build_pole_data(bpy.context)
            draw_handler.update_pole_data(pole_data)
    except:
        pass


def _on_visualization_toggle(self, context):
    """Callback when visualization checkbox is toggled."""
    global _in_callback
    
    # Prevent recursive callbacks
    if _in_callback:
        return
    
    _in_callback = True
    try:
        is_enabled = context.scene.valency_visualization_enabled
        
        # Only allow in Edit Mode
        if context.mode != "EDIT_MESH":
            # Reset if trying to enable outside Edit Mode
            if is_enabled:
                _in_callback = True
                try:
                    context.scene.valency_visualization_enabled = False
                finally:
                    _in_callback = False
            return
        
        if is_enabled:
            # Enable visualization
            if not draw_handler.is_registered():
                pole_data = draw_handler.build_pole_data(context)
                draw_handler.register(pole_data, context)
        else:
            # Disable visualization
            if draw_handler.is_registered():
                draw_handler.unregister()
    except Exception as e:
        print(f"Error toggling visualization: {e}")
    finally:
        _in_callback = False


def _on_mode_change(scene):
    """Scene update handler to detect mode changes and manage draw handler."""
    global _last_mode, _in_callback
    
    try:
        current_mode = bpy.context.mode
        
        # Exiting Edit Mode - unregister but keep checkbox state
        if _last_mode == "EDIT_MESH" and current_mode != "EDIT_MESH":
            if draw_handler.is_registered():
                draw_handler.unregister()
        
        # Entering Edit Mode - re-register if checkbox is enabled
        elif _last_mode != "EDIT_MESH" and current_mode == "EDIT_MESH":
            if scene.valency_visualization_enabled and not draw_handler.is_registered():
                pole_data = draw_handler.build_pole_data(bpy.context)
                draw_handler.register(pole_data, bpy.context)
        
        _last_mode = current_mode
    except:
        pass


def register():
    """Register the addon by registering classes and UI."""
    
    # Register custom property on Scene with update callback
    bpy.types.Scene.valency_visualization_enabled = BoolProperty(
        name="Pole Visualization Enabled",
        description="Toggle vertex pole visualization overlay",
        default=False,
        update=_on_visualization_toggle
    )
    
    operators.register()
    ui.register()
    
    # Register mode change handler (keeps overlay in sync with Edit Mode)
    bpy.app.handlers.depsgraph_update_post.append(_on_mode_change)
    # Register mesh change handler (rebuilds pole data as topology changes)
    bpy.app.handlers.depsgraph_update_post.append(_on_mesh_change)


def unregister():
    """Unregister the addon by unregistering classes and UI."""
    
    ui.unregister()
    operators.unregister()
    
    # Unregister mode change handler
    if _on_mode_change in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_mode_change)
    
    # Unregister mesh change handler
    if _on_mesh_change in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_mesh_change)
    
    # Clean up draw handler
    if draw_handler.is_registered():
        draw_handler.unregister()
    
    # Unregister custom property
    if hasattr(bpy.types.Scene, "valency_visualization_enabled"):
        del bpy.types.Scene.valency_visualization_enabled