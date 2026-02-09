# The Rendering Engine
# Role: The bridge between your CPU logic and your GPU hardware.
# Interplay:
#     Texture Management: Loads your `icons/` folder into `gpu.types.GPUTexture`.
#     Projection: Uses `location_3d_to_region_2d` to calculate where on the screen the icons sit.
#     Shader Binding: Uses the `IMAGE_COLOR` builtin shader via the `POST_VIEW` callback with depth testing.
#     Dependency: Relies on the coordinate list provided by `operators.py`.

import bpy
import gpu
import os
import bmesh
from gpu_extras.batch import batch_for_shader
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_location_3d
from mathutils import Vector, kdtree


# Global state
_draw_handler_handle = None
_pole_data = None
_context = None
_textures = {}

# Render constants
_ICON_SIZE = 24  # pixels
_DEPTH_BIAS_MIN = 0.1
_DEPTH_BIAS_FACTOR = 1e-4
_USE_RETOPOLOGY_OFFSET_CULLING = False

# Icon lookup table
_icon_mapping = {
    2: "icon_pole_2.png",
    3: "icon_pole_3.png",
    4: "icon_pole_4.png",
    5: "icon_pole_5.png",
    "6+": "icon_pole_6plus.png",
}


def is_registered():
    """Check if the draw handler is currently registered."""
    return _draw_handler_handle is not None


def update_pole_data(new_pole_data):
    """Update the pole data without re-registering the draw handler."""
    global _pole_data
    _pole_data = new_pole_data


def build_pole_data(context):
    """Analyze mesh topology and collect pole coordinates with vertex indices.

    Returns a dict mapping pole type to a list of (world_co, vertex_index).
    This is called on-demand from operators or update handlers.
    """
    active_object = context.active_object
    if active_object is None or active_object.type != "MESH":
        return {2: [], 3: [], 4: [], 5: [], "6+": []}

    # Access live edit-mode geometry
    bm = bmesh.from_edit_mesh(active_object.data)
    bm.verts.ensure_lookup_table()

    return _build_pole_data_from_bm(bm, active_object.matrix_world)


def _build_pole_data_from_bm(bm, matrix):
    """Build pole data from a bmesh and transform matrix."""
    pole_data = {2: [], 3: [], 4: [], 5: [], "6+": []}

    for vert in bm.verts:
        valence = len(vert.link_edges)
        world_co = (matrix @ vert.co).copy()
        pole_entry = (world_co, vert.index)

        if valence in pole_data:
            pole_data[valence].append(pole_entry)
        elif valence > 5:
            pole_data["6+"].append(pole_entry)

    return pole_data


def _get_active_mesh(context):
    """Return the active mesh object and its mesh data, if valid."""
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        return None, None
    return obj, obj.data





def _get_vertex_normal(bm_cache, normal_cache, vert_index):
    """Return averaged vertex normal, cached by vertex index."""
    if vert_index in normal_cache:
        return normal_cache[vert_index]

    if vert_index >= len(bm_cache.verts):
        normal_cache[vert_index] = None
        return None

    vert = bm_cache.verts[vert_index]
    if not vert.link_faces:
        normal_cache[vert_index] = None
        return None

    normal = Vector((0, 0, 0))
    for face in vert.link_faces:
        normal += face.normal
    normal = normal.normalized()

    normal_cache[vert_index] = normal
    return normal


def _is_backfacing(pole_co, vert_index, cam_pos, bm_cache, normal_cache):
    """Check if a pole is backfacing relative to the camera."""
    try:
        normal = _get_vertex_normal(bm_cache, normal_cache, vert_index)
        if normal is None:
            return False

        view_dir = (cam_pos - pole_co).normalized()
        return normal.dot(view_dir) < 0
    except Exception:
        return False


def _get_depth_bias(pole_co, cam_pos):
    """Compute a small camera-facing bias to avoid z-fighting/clipping."""
    distance = (cam_pos - pole_co).length
    return max(_DEPTH_BIAS_MIN, distance * _DEPTH_BIAS_FACTOR)


def _build_retopology_kdtree(context, obj, mesh):
    """Build a KD-tree of mesh vertices in world space for retopology culling."""
    overlay = context.space_data.overlay
    if not overlay.show_retopology:
        return None

    matrix = obj.matrix_world
    kd = kdtree.KDTree(len(mesh.vertices))
    for i, vert in enumerate(mesh.vertices):
        world_co = matrix @ vert.co
        kd.insert(world_co, i)
    kd.balance()
    return kd


def _is_within_retopology_offset(pole_co, context, kd_tree):
    """Check if pole is within retopology offset distance from mesh surface."""
    if not _USE_RETOPOLOGY_OFFSET_CULLING:
        return True

    overlay = context.space_data.overlay
    if not overlay.show_retopology:
        return True

    if kd_tree is None:
        return True

    try:
        _, _, closest_dist = kd_tree.find(pole_co)
        return closest_dist <= overlay.retopology_offset
    except Exception:
        return True





def register(pole_data, context):
    """Register the draw handler and store the pole data."""
    global _draw_handler_handle, _pole_data, _context

    if _draw_handler_handle is not None:
        return

    _pole_data = pole_data
    _context = context

    # Load textures lazily when registering
    _load_textures()

    _draw_handler_handle = bpy.types.SpaceView3D.draw_handler_add(
        _draw_callback,
        (),
        "WINDOW",
        "POST_VIEW",
    )


def unregister():
    """Unregister the draw handler and clean up resources."""
    global _draw_handler_handle, _pole_data, _context, _textures

    if _draw_handler_handle is None:
        return

    bpy.types.SpaceView3D.draw_handler_remove(_draw_handler_handle, "WINDOW")
    _draw_handler_handle = None

    _pole_data = None
    _context = None
    _textures.clear()


def _load_textures():
    """Load icon textures from the icons directory."""
    global _textures
    addon_dir = os.path.dirname(__file__)
    icons_dir = os.path.join(addon_dir, "icons")
    
    for pole_type, filename in _icon_mapping.items():
        icon_path = os.path.join(icons_dir, filename)
        if os.path.exists(icon_path):
            try:
                # Load image datablock once, then create a GPU texture
                if filename not in bpy.data.images:
                    image = bpy.data.images.load(icon_path)
                else:
                    image = bpy.data.images[filename]
                
                # Create GPU texture
                texture = gpu.texture.from_image(image)
                _textures[pole_type] = texture
            except Exception as e:
                print(f"Error loading texture {filename}: {e}")


def _draw_callback(*args):
    """Draw overlay icons for all poles in the current view."""
    global _pole_data
    if _pole_data is None or _context is None:
        return

    # Ensure we are in a 3D view region
    area = _context.area
    region = _context.region
    if area is None or region is None or area.type != "VIEW_3D":
        return

    obj, mesh = _get_active_mesh(_context)
    if obj is None or mesh is None:
        return

    # Build bmesh once per draw for face-normal access
    try:
        bm_cache = bmesh.from_edit_mesh(mesh)
        bm_cache.verts.ensure_lookup_table()
    except Exception:
        return

    # Refresh pole data from live bmesh to keep icons responsive while editing
    try:
        _pole_data = _build_pole_data_from_bm(bm_cache, obj.matrix_world)
    except Exception:
        return

    # Cache normals only for vertices we test
    normal_cache = {}

    # Cache camera position once per draw
    region_3d = _context.space_data.region_3d
    cam_pos = region_3d.view_matrix.inverted().translation

    # Optional retopology culling KD-tree (Solid mode retopology overlay)
    kd_tree = _build_retopology_kdtree(_context, obj, mesh)

    gpu.state.blend_set("ADDITIVE")
    gpu.state.depth_test_set("LESS_EQUAL")
    shader = gpu.shader.from_builtin("IMAGE_COLOR")
    half = _ICON_SIZE / 2
    region_3d = _context.space_data.region_3d
    region_width = region.width
    region_height = region.height

    for pole_type, coords in _pole_data.items():
        if not coords or pole_type not in _textures:
            continue

        texture = _textures[pole_type]
        positions = []
        uvs = []
        indices = []
        base_index = 0

        for world_co, vert_index in coords:
            # Retopology offset culling
            if not _is_within_retopology_offset(world_co, _context, kd_tree):
                continue

            # Backfacing culling
            if _is_backfacing(world_co, vert_index, cam_pos, bm_cache, normal_cache):
                continue

            # Project 3D coordinate to 2D screen space
            screen_co = location_3d_to_region_2d(
                region,
                region_3d,
                world_co
            )

            if screen_co is None:
                continue

            # Skip offscreen icons
            if (
                screen_co.x < -half or screen_co.x > region_width + half or
                screen_co.y < -half or screen_co.y > region_height + half
            ):
                continue

            # Create billboard quad in 3D, depth-tested
            view_dir = (cam_pos - world_co).normalized()
            offset_world_co = world_co + (view_dir * _get_depth_bias(world_co, cam_pos))
            screen_positions = [
                Vector((screen_co.x - half, screen_co.y - half)),
                Vector((screen_co.x + half, screen_co.y - half)),
                Vector((screen_co.x + half, screen_co.y + half)),
                Vector((screen_co.x - half, screen_co.y + half)),
            ]

            quad_positions = [
                region_2d_to_location_3d(
                    region,
                    region_3d,
                    sp,
                    offset_world_co,
                )
                for sp in screen_positions
            ]

            positions.extend(quad_positions)
            uvs.extend([(0, 0), (1, 0), (1, 1), (0, 1)])
            indices.extend([
                (base_index + 0, base_index + 1, base_index + 2),
                (base_index + 0, base_index + 2, base_index + 3),
            ])
            base_index += 4

        if not positions:
            continue

        batch = batch_for_shader(
            shader,
            "TRIS",
            {
                "pos": positions,
                "texCoord": uvs,
            },
            indices=indices,
        )

        # Draw all icons for this texture in one batch
        shader.bind()
        shader.uniform_sampler("image", texture)
        batch.draw(shader)

    gpu.state.depth_test_set("NONE")
