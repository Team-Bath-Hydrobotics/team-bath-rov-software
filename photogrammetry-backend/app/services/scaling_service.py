import trimesh
from app.config import settings
from app.models.scaling import BoundingBox, ScaleResponse


class ScalingService:
    def estimate_height(self, job_id: str, true_length_cm: float) -> ScaleResponse:
        model_path = settings.OUTPUT_DIR / job_id / "model.glb"
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found at {model_path}")

        scene = trimesh.load(str(model_path), file_type="glb")

        if isinstance(scene, trimesh.Scene):
            mesh = scene.dump(concatenate=True)
        else:
            mesh = scene

        bounds = mesh.bounding_box.extents
        x_extent, y_extent, z_extent = (
            float(bounds[0]),
            float(bounds[1]),
            float(bounds[2]),
        )

        # The coral garden is much longer (1-2.5m) than it is wide (~36cm)
        # or tall (unknown). COLMAP/OpenMVS don't guarantee axis orientation,
        # so we identify axes by size:
        #   longest  = length (the dimension the pilot measured)
        #   shortest = width  (~36cm, the narrow dimension)
        #   middle   = height (what we want to estimate)
        extents = sorted([x_extent, y_extent, z_extent])
        model_width = extents[0]  # shortest
        model_height = extents[1]  # middle
        model_length = extents[2]  # longest

        scale_factor = true_length_cm / model_length
        estimated_height_cm = model_height * scale_factor

        return ScaleResponse(
            job_id=job_id,
            estimated_height_cm=round(estimated_height_cm, 2),
            scale_factor=round(scale_factor, 4),
            bounding_box=BoundingBox(
                width=round(model_width, 4),
                height=round(model_height, 4),
                depth=round(model_length, 4),
            ),
        )
