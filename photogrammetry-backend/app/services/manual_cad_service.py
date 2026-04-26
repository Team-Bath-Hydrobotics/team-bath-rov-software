import numpy as np
import trimesh
from app.config import settings


class ManualCADService:
    def generate(self, job_id: str, height_cm: float, length_cm: float) -> str:
        """Generate a 3-rectangular-prism stepped coral model and save as GLB.

        Produces three boxes arranged as a stepped block (staircase viewed
        from the side), matching the MATE 2026 competition specification:

                ┌───┐
                │   │
           ┌────┤   │
           │    │   │
           │    │   ├────┐
           │    │   │    │
           └────┴───┴────┘
           ←── length ──→
        """
        output_dir = settings.OUTPUT_DIR / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "model.glb"

        # Each prism occupies one-third of the total length along X.
        prism_length = length_cm / 3.0

        # Depth (Y axis) — approximate width of the coral garden.
        depth = 36.0

        # Three steps: left (medium), centre (tallest), right (shortest).
        steps = [
            {"height_scale": 0.70, "color": [210, 125, 80, 255]},  # left
            {"height_scale": 1.00, "color": [255, 127, 80, 255]},  # centre
            {"height_scale": 0.45, "color": [233, 150, 122, 255]},  # right
        ]

        prisms = []
        for i, step in enumerate(steps):
            h = height_cm * step["height_scale"]

            box = trimesh.creation.box(extents=[prism_length, depth, h])

            # Position: side-by-side along X, centred about origin, bottom at Z=0.
            x_centre = prism_length * (i + 0.5) - length_cm / 2.0
            z_centre = h / 2.0
            box.apply_translation([x_centre, 0, z_centre])

            box.visual.vertex_colors = np.tile(step["color"], (len(box.vertices), 1))
            prisms.append(box)

        scene = trimesh.Scene(prisms)
        scene.export(str(output_path), file_type="glb")
        return str(output_path)
