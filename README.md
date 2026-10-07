# Valency

A Blender add-on that shows the **valence** (number of connected edges) of every vertex in Edit Mode, as an icon drawn on the vertex. Poles (3, 5 and 6+ edge vertices) become easy to spot while retopologizing, with no X-Ray needed.

## Features
- One icon per vertex: loose, 1, 2, 3, 4, 5 and 6+ edges.
- Works in perspective, orthographic and camera views.
- Follows the **Retopology** overlay: icons are pulled toward the viewer by the overlay's *Offset*, the same way Blender draws the edit mesh, so they stay visible on the surface.
- Hides icons on back-facing vertices (optional; ignored in X-Ray).
- Updates as you edit; orbiting the view costs nothing.
- Works with multi-object editing.

## Use
Enable **Pole Visualization** in the Edit Mode *Overlays → Mesh Edit Mode* popover. Settings there: icon size, hide back-facing, show valence 4.

There is also an operator, `valency.toggle_visualization` (search for *Toggle Pole Visualization* with F3), for keymaps.

## Install
Download the zip from the releases page (or build it with `blender --command extension build`) and use **Edit → Preferences → Get Extensions → Install from Disk**.

Developed and tested on Blender 5.2. The manifest asks for 4.2 or newer but older versions are untested.

## Status
Version 0.2 is a rewrite of the first release. Expect rough edges; issues and pull requests are welcome.

## License
[CC0 1.0 Universal](LICENSE): public domain, no rights reserved.
