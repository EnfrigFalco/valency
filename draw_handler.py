# The Rendering Engine
# Role: Draws one icon per vertex, chosen by valence, over the mesh being edited.
# Interplay:
#     Icons: `load_icon_pixels()` reads `icons/` once (from a timer, outside drawing) into plain pixel arrays.
#            GPU textures are made from those arrays lazily, inside the draw callback.
#     Data: `mark_dirty()` (called from the depsgraph/undo handlers in `__init__.py`) flags the cache.
#           The next draw rebuilds per-valence GPU batches from bmesh. Orbiting/zooming never rebuilds.
#     Shader: A custom shader does all projection on the GPU, so perspective, orthographic and camera views
#             behave the same. Icons are a fixed pixel size and are pulled toward the viewer in depth by the
#             Retopology overlay offset (or a small bias), the same idea Blender's own edit-mesh overlay uses.

import os

import bpy
import gpu
import bmesh
from gpu_extras.batch import batch_for_shader


# Valence key -> icon file. 0 = loose vertex (no edges). 6 = 6 or more.
ICON_FILES = {
    0: "icon_pole_loose.png",
    1: "icon_pole_1.png",
    2: "icon_pole_2.png",
    3: "icon_pole_3.png",
    4: "icon_pole_4.png",
    5: "icon_pole_5.png",
    6: "icon_pole_6plus.png",
}

# Depth bias used when the Retopology overlay is off, as a fraction of the view distance.
# Keeps icons from z-fighting with the edit mesh's own surface.
_BIAS_FACTOR = 0.002

# Unit quad as two triangles, corners in [-1, 1].
_QUAD = ((-1, -1), (1, -1), (1, 1), (-1, -1), (1, 1), (-1, 1))


_handle = None
_icon_pixels = {}   # valence key -> (width, height, flat RGBA float list)
_textures = {}      # valence key -> GPUTexture
_shader = None
_batches = {}       # valence key -> GPUBatch
_dirty = True
_signature = None   # identifies which meshes are in edit mode, to detect mode/selection changes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register():
    global _handle
    if _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")


def unregister():
    global _handle, _shader
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
        _handle = None
    _batches.clear()
    _textures.clear()
    _icon_pixels.clear()
    _shader = None


def mark_dirty():
    global _dirty
    _dirty = True


def load_icon_pixels():
    """Read the icon PNGs into pixel arrays, then remove the temporary images.

    Runs from a timer (not during registration, where bpy.data is restricted, and not during drawing,
    where adding datablocks is unsafe). Nothing is left behind in the user's .blend file.
    """
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    for key, filename in ICON_FILES.items():
        path = os.path.join(icons_dir, filename)
        if not os.path.exists(path):
            print(f"Valency: missing icon {path}")
            continue
        image = None
        try:
            image = bpy.data.images.load(path, check_existing=False)
            width, height = image.size
            pixels = [0.0] * (width * height * 4)
            image.pixels.foreach_get(pixels)
            _icon_pixels[key] = (width, height, pixels)
        except Exception as error:
            print(f"Valency: could not load {filename}: {error}")
        finally:
            if image is not None:
                bpy.data.images.remove(image)
    _textures.clear()
    mark_dirty()
    return None  # one-shot timer


# ---------------------------------------------------------------------------
# Shader
# ---------------------------------------------------------------------------

_VERTEX_SOURCE = """
void main()
{
  uv = corner * 0.5 + 0.5;

  /* Backface culling. u_eye.w = 1: perspective, xyz = eye position.
   *                   u_eye.w = 0: orthographic, xyz = direction toward the viewer. */
  if (u_misc.z > 0.5 && dot(nor, nor) > 0.0) {
    vec3 to_eye = u_eye.xyz - pos * u_eye.w;
    if (dot(nor, to_eye) < 0.0) {
      gl_Position = vec4(0.0, 0.0, 2.0, 1.0); /* outside the clip volume: dropped */
      return;
    }
  }

  vec4 clip = u_viewproj * vec4(pos, 1.0);

  /* Pull depth toward the viewer by a view-space distance (u_params.z). Only z changes, so the icon
   * stays exactly over its vertex. For perspective, clip.w == -view_z; never cross the near plane. */
  float offset = u_params.z;
  if (u_eye.w > 0.5) {
    offset = min(offset, clip.w * 0.5);
  }
  float z_off = clip.z + offset * u_params.x;
  float w_off = clip.w + offset * u_params.y;
  clip.z = z_off / w_off * clip.w;

  /* Fixed pixel size: u_params.w = icon size in px, u_misc.xy = viewport size in px. */
  clip.xy += corner * (u_params.w / u_misc.xy) * clip.w;

  gl_Position = clip;
}
"""

_FRAGMENT_SOURCE = """
void main()
{
  vec4 color = texture(u_image, uv);
  if (color.a < 0.02) {
    discard;
  }
  FragColor = color;
}
"""


def _get_shader():
    global _shader
    if _shader is None:
        iface = gpu.types.GPUStageInterfaceInfo("valency_iface")
        iface.smooth("VEC2", "uv")

        info = gpu.types.GPUShaderCreateInfo()
        # 112 bytes of push constants (limit is 128).
        info.push_constant("MAT4", "u_viewproj")
        info.push_constant("VEC4", "u_eye")     # see vertex source
        info.push_constant("VEC4", "u_params")  # P[2][2], P[3][2], depth offset, icon size px
        info.push_constant("VEC4", "u_misc")    # viewport w, viewport h, cull backfaces, unused
        info.sampler(0, "FLOAT_2D", "u_image")
        info.vertex_in(0, "VEC3", "pos")
        info.vertex_in(1, "VEC3", "nor")
        info.vertex_in(2, "VEC2", "corner")
        info.vertex_out(iface)
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(_VERTEX_SOURCE)
        info.fragment_source(_FRAGMENT_SOURCE)
        _shader = gpu.shader.create_from_info(info)
    return _shader


def _get_texture(key):
    texture = _textures.get(key)
    if texture is None and key in _icon_pixels:
        width, height, pixels = _icon_pixels[key]
        buffer = gpu.types.Buffer("FLOAT", width * height * 4, pixels)
        texture = gpu.types.GPUTexture((width, height), format="RGBA16F", data=buffer)
        _textures[key] = texture
    return texture


# ---------------------------------------------------------------------------
# Mesh data -> batches
# ---------------------------------------------------------------------------

def _edit_mesh_objects(context):
    return [ob for ob in context.objects_in_mode_unique_data if ob.type == "MESH"]


def _build_batches(objects, shader):
    """One batch per valence key: 6 vertices (two triangles) per icon."""
    data = {key: ([], [], []) for key in ICON_FILES}

    for ob in objects:
        bm = bmesh.from_edit_mesh(ob.data)
        matrix = ob.matrix_world
        normal_matrix = matrix.to_3x3().inverted_safe().transposed()

        for vert in bm.verts:
            if vert.hide:
                continue
            key = min(len(vert.link_edges), 6)
            pos = (matrix @ vert.co)[:]
            # Loose and wire-only verts have no meaningful normal: zero means "never cull".
            nor = (normal_matrix @ vert.normal).normalized()[:] if vert.link_faces else (0.0, 0.0, 0.0)
            positions, normals, corners = data[key]
            positions.extend((pos,) * 6)
            normals.extend((nor,) * 6)
            corners.extend(_QUAD)

    _batches.clear()
    for key, (positions, normals, corners) in data.items():
        if positions:
            _batches[key] = batch_for_shader(
                shader, "TRIS", {"pos": positions, "nor": normals, "corner": corners}
            )


# ---------------------------------------------------------------------------
# Draw callback
# ---------------------------------------------------------------------------

def _draw():
    global _dirty, _signature

    context = bpy.context
    if context.mode != "EDIT_MESH":
        return
    settings = getattr(context.scene, "valency", None)
    if settings is None or not settings.enabled:
        return
    space = context.space_data
    region = context.region
    rv3d = context.region_data
    if space is None or space.type != "VIEW_3D" or rv3d is None or not space.overlay.show_overlays:
        return

    shader = _get_shader()

    objects = _edit_mesh_objects(context)
    signature = tuple(ob.name for ob in objects)
    if _dirty or signature != _signature:
        _signature = signature
        _dirty = False
        try:
            _build_batches(objects, shader)
        except Exception as error:
            _batches.clear()
            print(f"Valency: could not read the edit mesh: {error}")
    if not _batches:
        return

    view = gpu.matrix.get_model_view_matrix()
    projection = gpu.matrix.get_projection_matrix()
    view_inv = view.inverted_safe()
    # Read the projection type from the matrix itself: correct for camera views with ortho cameras too.
    if projection[3][3] == 0.0:
        eye = (*view_inv.translation, 1.0)
    else:
        # Orthographic: every view ray is parallel, so use the view's +Z axis (toward the viewer).
        eye = (*view_inv.col[2].xyz.normalized(), 0.0)

    overlay = space.overlay
    if overlay.show_retopology:
        offset = overlay.retopology_offset
    else:
        offset = rv3d.view_distance * _BIAS_FACTOR

    icon_px = settings.icon_size * context.preferences.system.ui_scale
    viewport = gpu.state.viewport_get()

    shading = space.shading
    xray = shading.show_xray_wireframe if shading.type == "WIREFRAME" else shading.show_xray

    shader.bind()
    shader.uniform_float("u_viewproj", projection @ view)
    shader.uniform_float("u_eye", eye)
    shader.uniform_float("u_params", (projection[2][2], projection[3][2], offset, icon_px))
    shader.uniform_float(
        "u_misc", (float(viewport[2]), float(viewport[3]), 1.0 if settings.cull_backfaces and not xray else 0.0, 0.0)
    )

    gpu.state.blend_set("ALPHA")
    gpu.state.depth_mask_set(False)
    gpu.state.depth_test_set("NONE" if xray else "LESS_EQUAL")

    for key, batch in _batches.items():
        if key == 4 and not settings.show_regular:
            continue
        texture = _get_texture(key)
        if texture is None:
            continue
        shader.uniform_sampler("u_image", texture)
        batch.draw(shader)

    gpu.state.depth_test_set("NONE")
    gpu.state.blend_set("NONE")
