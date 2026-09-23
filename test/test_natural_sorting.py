from pathlib import Path

from gui.utils.sorting import natural_sorted_by_basename


def test_natural_sorted_by_basename_orders_numeric_chunks_as_integers():
    values = ["frame1", "frame10", "frame2"]

    assert natural_sorted_by_basename(values) == ["frame1", "frame2", "frame10"]


def test_natural_sorted_by_basename_uses_path_basename_case_insensitive():
    values = [
        Path("cam1") / "Frame10.tif",
        Path("cam2") / "frame2.tif",
        Path("cam10") / "frame1.tif",
    ]

    assert natural_sorted_by_basename(values) == [
        Path("cam10") / "frame1.tif",
        Path("cam2") / "frame2.tif",
        Path("cam1") / "Frame10.tif",
    ]


def test_point_detection_cli_orders_camera_slots_and_frames_naturally(tmp_path):
    from modules.camera_calibration.wand_calibration.point_detection_cli import (
        build_image_paths_dict,
        discover_cam_folders,
    )

    t0_dir = tmp_path / "T0"
    for cam_name in ("cam10", "cam2", "cam1"):
        cam_dir = t0_dir / cam_name
        cam_dir.mkdir(parents=True)
        for frame_name in ("frame1.tif", "frame10.tif", "frame2.tif"):
            (cam_dir / frame_name).write_bytes(b"image")
    (t0_dir / "cam2" / "ignored.txt").write_bytes(b"not an image")

    image_paths = build_image_paths_dict(discover_cam_folders(t0_dir))

    assert list(image_paths) == [0, 1, 2]
    assert [Path(paths[0]).parent.name for paths in image_paths.values()] == ["cam1", "cam2", "cam10"]
    assert [Path(path).name for path in image_paths[0]] == ["frame1.tif", "frame2.tif", "frame10.tif"]
