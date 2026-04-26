import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import settings
from app.models.job import JobStatus
from app.services.job_manager import job_manager
from app.services.mesh_processor import MeshProcessor

logger = logging.getLogger(__name__)

COLMAP_BIN = shutil.which("colmap") or "/usr/local/bin/colmap"
OPENMVS_BIN_DIR = Path("/usr/local/bin/OpenMVS")

STAGE_TIMEOUT = 1200  # 20 minutes per stage


def _has_openmvs() -> bool:
    """Check if OpenMVS binaries are available."""
    return (OPENMVS_BIN_DIR / "DensifyPointCloud").exists()


class ColmapPipeline:
    """Photogrammetry pipeline using COLMAP for SfM + OpenMVS for dense reconstruction."""

    def __init__(self) -> None:
        self.mesh_processor = MeshProcessor()

    def _run_cmd(self, cmd: list[str], job_id: str, stage_name: str) -> bool:
        """Run a shell command. Returns True on success."""
        logger.info("Running: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=STAGE_TIMEOUT,
        )

        if result.returncode != 0:
            logger.error(
                "%s failed for job %s:\nstdout: %s\nstderr: %s",
                stage_name,
                job_id,
                result.stdout[-500:] if result.stdout else "",
                result.stderr[-500:] if result.stderr else "",
            )
            job_manager.update_job(
                job_id,
                status=JobStatus.ERROR,
                error=f"Reconstruction failed at '{stage_name}': {(result.stderr or result.stdout or 'unknown error')[:500]}",
            )
            return False
        return True

    def _run_colmap(self, args: list[str], job_id: str, stage_name: str) -> bool:
        """Run a COLMAP command."""
        return self._run_cmd([COLMAP_BIN] + args, job_id, stage_name)

    def _run_openmvs(
        self,
        binary: str,
        args: list[str],
        job_id: str,
        stage_name: str,
        working_dir: Path | None = None,
    ) -> bool:
        """Run an OpenMVS command."""
        cmd = [str(OPENMVS_BIN_DIR / binary)] + args
        logger.info("Running: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=STAGE_TIMEOUT,
            cwd=working_dir,
        )

        if result.returncode != 0:
            logger.error(
                "%s failed for job %s:\nstdout: %s\nstderr: %s",
                stage_name,
                job_id,
                result.stdout[-500:] if result.stdout else "",
                result.stderr[-500:] if result.stderr else "",
            )
            job_manager.update_job(
                job_id,
                status=JobStatus.ERROR,
                error=f"Reconstruction failed at '{stage_name}': {(result.stderr or result.stdout or 'unknown error')[:500]}",
            )
            return False
        return True

    def run(self, job_id: str) -> None:
        """Run the full pipeline. Intended to be called in a background thread."""
        tmp_dir = None
        try:
            upload_dir = settings.UPLOAD_DIR / job_id
            images = list(upload_dir.iterdir())

            if len(images) < 3:
                job_manager.update_job(
                    job_id,
                    status=JobStatus.ERROR,
                    error="At least 3 images are required for reconstruction",
                )
                return

            use_dense = _has_openmvs()
            logger.info(
                "Running %s pipeline for job %s with %d images",
                "dense (OpenMVS)" if use_dense else "sparse",
                job_id,
                len(images),
            )

            # Set up workspace
            tmp_dir = Path(tempfile.mkdtemp(prefix=f"colmap_{job_id}_"))
            db_path = tmp_dir / "database.db"
            sparse_dir = tmp_dir / "sparse"
            sparse_dir.mkdir()

            image_dir = settings.UPLOAD_DIR / job_id

            # ── Stage 1: Feature extraction (0-15%) ──
            job_manager.update_job(
                job_id,
                status=JobStatus.RECONSTRUCTING,
                progress=0,
                stage="feature_extraction",
            )
            if not self._run_colmap(
                [
                    "feature_extractor",
                    "--database_path",
                    str(db_path),
                    "--image_path",
                    str(image_dir),
                    "--ImageReader.single_camera",
                    "1",
                    "--ImageReader.camera_model",
                    "SIMPLE_RADIAL",
                    "--SiftExtraction.use_gpu",
                    "0",
                    "--SiftExtraction.max_num_features",
                    "8192",
                    "--SiftExtraction.max_image_size",
                    "2400",
                    "--SiftExtraction.first_octave",
                    "0",
                    "--SiftExtraction.num_threads",
                    "2",
                ],
                job_id,
                "feature_extraction",
            ):
                return
            job_manager.update_job(job_id, progress=15)
            logger.info("Completed feature_extraction for job %s", job_id)

            # ── Stage 2: Feature matching (15-35%) ──
            job_manager.update_job(job_id, progress=15, stage="feature_matching")
            if not self._run_colmap(
                [
                    "exhaustive_matcher",
                    "--database_path",
                    str(db_path),
                    "--SiftMatching.use_gpu",
                    "0",
                    "--SiftMatching.num_threads",
                    "2",
                ],
                job_id,
                "feature_matching",
            ):
                return
            job_manager.update_job(job_id, progress=35)
            logger.info("Completed feature_matching for job %s", job_id)

            # ── Stage 3: Sparse reconstruction (35-55%) ──
            job_manager.update_job(job_id, progress=35, stage="reconstruction")
            if not self._run_colmap(
                [
                    "mapper",
                    "--database_path",
                    str(db_path),
                    "--image_path",
                    str(image_dir),
                    "--output_path",
                    str(sparse_dir),
                ],
                job_id,
                "reconstruction",
            ):
                return
            job_manager.update_job(job_id, progress=55)
            logger.info("Completed reconstruction for job %s", job_id)

            # Find the best reconstruction (COLMAP creates numbered subdirs: 0, 1, ...)
            sparse_models = sorted(sparse_dir.iterdir())
            if not sparse_models:
                job_manager.update_job(
                    job_id,
                    status=JobStatus.ERROR,
                    error="Sparse reconstruction produced no models",
                )
                return
            sparse_model = sparse_models[0]

            if use_dense:
                output_path = self._run_dense_pipeline(
                    job_id, tmp_dir, sparse_model, image_dir
                )
            else:
                output_path = self._run_sparse_pipeline(job_id, tmp_dir, sparse_model)

            if output_path is None:
                return  # Error already reported

            output_url = f"/api/jobs/{job_id}/model"
            job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETE,
                progress=100,
                stage="complete",
                output_url=output_url,
            )
            logger.info("Pipeline complete for job %s → %s", job_id, output_path)

        except subprocess.TimeoutExpired:
            logger.exception("Pipeline timed out for job %s", job_id)
            job_manager.update_job(
                job_id,
                status=JobStatus.ERROR,
                error="Reconstruction timed out (stage exceeded 20 minutes)",
            )
        except Exception:
            logger.exception("Pipeline failed for job %s", job_id)
            job_manager.update_job(
                job_id,
                status=JobStatus.ERROR,
                error="An unexpected error occurred during reconstruction",
            )
        finally:
            if tmp_dir and tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _run_sparse_pipeline(
        self, job_id: str, tmp_dir: Path, sparse_model: Path
    ) -> Path | None:
        """Fallback: export sparse PLY and mesh with Poisson."""
        # Export to PLY (55-65%)
        job_manager.update_job(job_id, progress=55, stage="export_ply")
        ply_path = tmp_dir / "reconstruction.ply"
        if not self._run_colmap(
            [
                "model_converter",
                "--input_path",
                str(sparse_model),
                "--output_path",
                str(ply_path),
                "--output_type",
                "PLY",
            ],
            job_id,
            "export_ply",
        ):
            return None
        job_manager.update_job(job_id, progress=65)
        logger.info("Completed export_ply for job %s", job_id)

        if not ply_path.exists():
            job_manager.update_job(
                job_id,
                status=JobStatus.ERROR,
                error="Reconstruction completed but no PLY file was produced",
            )
            return None

        ply_size = ply_path.stat().st_size
        logger.info("PLY file size: %.1f MB", ply_size / (1024 * 1024))

        # Mesh processing (65-100%)
        return self.mesh_processor.process(job_id, ply_path)

    def _run_dense_pipeline(
        self, job_id: str, tmp_dir: Path, sparse_model: Path, image_dir: Path
    ) -> Path | None:
        """Dense pipeline: COLMAP undistort → OpenMVS densify → mesh → texture."""
        # ── Stage 4: Undistort images (55-60%) ──
        job_manager.update_job(job_id, progress=55, stage="undistort")
        undistorted_dir = tmp_dir / "undistorted"
        if not self._run_colmap(
            [
                "image_undistorter",
                "--image_path",
                str(image_dir),
                "--input_path",
                str(sparse_model),
                "--output_path",
                str(undistorted_dir),
                "--output_type",
                "COLMAP",
            ],
            job_id,
            "undistort",
        ):
            return None
        logger.info("Completed undistort for job %s", job_id)

        # ── Stage 5: Convert COLMAP → OpenMVS format (60-62%) ──
        job_manager.update_job(job_id, progress=60, stage="convert_to_mvs")
        # InterfaceCOLMAP expects the undistorted sparse model inside the output dir
        mvs_path = tmp_dir / "scene.mvs"
        if not self._run_openmvs(
            "InterfaceCOLMAP",
            [
                "--input-file",
                str(undistorted_dir),
                "--output-file",
                str(mvs_path),
                "--image-folder",
                str(undistorted_dir / "images"),
            ],
            job_id,
            "convert_to_mvs",
            working_dir=tmp_dir,
        ):
            return None
        logger.info("Completed COLMAP→OpenMVS conversion for job %s", job_id)

        # ── Stage 6: Dense point cloud (62-80%) ──
        job_manager.update_job(job_id, progress=62, stage="densify")
        dense_mvs = tmp_dir / "scene_dense.mvs"
        if not self._run_openmvs(
            "DensifyPointCloud",
            [
                "--input-file",
                str(mvs_path),
                "--output-file",
                str(dense_mvs),
                "--resolution-level",
                "2",
                "--number-views",
                "4",
                "--max-threads",
                "2",
            ],
            job_id,
            "densify",
            working_dir=tmp_dir,
        ):
            return None
        logger.info("Completed densification for job %s", job_id)

        # ── Stage 7: Mesh reconstruction (80-90%) ──
        job_manager.update_job(job_id, progress=80, stage="reconstruct_mesh")
        mesh_mvs = tmp_dir / "scene_dense_mesh.mvs"
        if not self._run_openmvs(
            "ReconstructMesh",
            [
                "--input-file",
                str(dense_mvs),
                "--output-file",
                str(mesh_mvs),
                "--max-threads",
                "2",
            ],
            job_id,
            "reconstruct_mesh",
            working_dir=tmp_dir,
        ):
            return None
        logger.info("Completed mesh reconstruction for job %s", job_id)

        # ── Stage 8: Texture mesh (90-95%) ──
        # Try TextureMesh for photorealistic output; fall back to untextured if it fails
        job_manager.update_job(job_id, progress=90, stage="texture_mesh")
        textured_mvs = tmp_dir / "scene_dense_mesh_texture.mvs"
        texture_ok = self._run_openmvs(
            "TextureMesh",
            [
                "--input-file",
                str(mesh_mvs),
                "--output-file",
                str(textured_mvs),
                "--max-threads",
                "2",
            ],
            job_id,
            "texture_mesh",
            working_dir=tmp_dir,
        )

        # ── Stage 9: Export GLB (95-100%) ──
        job_manager.update_job(job_id, progress=95, stage="exporting")

        # Find the best mesh file OpenMVS produced
        # TextureMesh outputs .ply alongside the .mvs; ReconstructMesh also outputs .ply
        mesh_ply = None
        if texture_ok:
            candidate = textured_mvs.with_suffix(".ply")
            if candidate.exists():
                mesh_ply = candidate
                logger.info("Using textured mesh: %s", mesh_ply)

        if mesh_ply is None:
            # Fall back to the untextured dense mesh
            candidate = mesh_mvs.with_suffix(".ply")
            if candidate.exists():
                mesh_ply = candidate
                logger.info("Using untextured dense mesh: %s", mesh_ply)
            # Reset error status since we're falling back gracefully
            job_manager.update_job(job_id, status=JobStatus.RECONSTRUCTING, error=None)

        if mesh_ply is None:
            # Last resort: search for any mesh output
            for candidate in tmp_dir.glob("*.ply"):
                mesh_ply = candidate
                logger.info("Found fallback PLY: %s", mesh_ply)
                break

        if mesh_ply is None:
            job_manager.update_job(
                job_id,
                status=JobStatus.ERROR,
                error="Dense reconstruction completed but no mesh file was produced",
            )
            return None

        ply_size = mesh_ply.stat().st_size
        logger.info("Dense mesh PLY size: %.1f MB", ply_size / (1024 * 1024))

        return self.mesh_processor.process(job_id, mesh_ply)
