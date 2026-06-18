from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LichtfieldStudioConfig:
    executable: str = "lichtfield-studio"
    input_colmap: Path = None
    image_dir: Path = None
    output_dir: Path = None
    point_count: int = 0
    bilateral_grid: int = 0
    extra_args: list = field(default_factory=list)


def _append_path_arg(command, name, value):
    if value is not None:
        command.extend([name, str(value)])


def _append_int_arg(command, name, value):
    if value:
        if value < 0:
            raise ValueError(f"{name} must be greater than or equal to 0")
        command.extend([name, str(value)])


def build_lichtfield_command(config):
    if not config.input_colmap:
        raise ValueError("LICHT Field Studio input_colmap is required")
    if not config.image_dir:
        raise ValueError("LICHT Field Studio image_dir is required")
    if not config.output_dir:
        raise ValueError("LICHT Field Studio output_dir is required")

    command = [config.executable]
    _append_path_arg(command, "--input-colmap", config.input_colmap)
    _append_path_arg(command, "--image-dir", config.image_dir)
    _append_path_arg(command, "--output", config.output_dir)
    _append_int_arg(command, "--point-count", config.point_count)
    _append_int_arg(command, "--bilateral-grid", config.bilateral_grid)
    command.extend(str(item) for item in config.extra_args)
    return command
