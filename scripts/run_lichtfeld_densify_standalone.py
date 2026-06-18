import argparse
import importlib.util
import os
import sys
import types
from pathlib import Path


def _configure_console_output():
    for stream in [sys.stdout, sys.stderr]:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


class _StdoutLogger:
    def info(self, text):
        print(text, flush=True)

    def warn(self, text):
        print(f"WARN: {text}", flush=True)

    def error(self, text):
        print(f"ERROR: {text}", flush=True)

    def debug(self, text):
        print(f"DEBUG: {text}", flush=True)


def _install_lichtfeld_stub():
    module = types.ModuleType("lichtfeld")
    module.log = _StdoutLogger()
    module.ui = types.SimpleNamespace(set_panel_enabled=lambda *args, **kwargs: None)
    module.register_class = lambda *args, **kwargs: None
    module.unregister_class = lambda *args, **kwargs: None
    sys.modules.setdefault("lichtfeld", module)


def _load_plugin_densify(plugin_dir):
    plugin_dir = Path(plugin_dir).resolve()
    densify_path = plugin_dir / "densify.py"
    if not densify_path.exists():
        raise FileNotFoundError(densify_path)
    project_root = Path(__file__).resolve().parents[1]
    torch_home = project_root / "tools" / "torch-cache"
    os.environ.setdefault("TORCH_HOME", str(torch_home))
    roma_src = plugin_dir / "RoMaV2" / "src"
    for path in [plugin_dir, roma_src]:
        if path.exists() and str(path) not in sys.path:
            sys.path.insert(0, str(path))
    package_name = "_xpano_lichtfeld_densification_plugin"
    package = types.ModuleType(package_name)
    package.__path__ = [str(plugin_dir)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(
        f"{package_name}.densify",
        densify_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{package_name}.densify"] = module
    spec.loader.exec_module(module)
    return module


def main():
    _configure_console_output()
    parser = argparse.ArgumentParser(
        description="Run LichtFeld densification plugin outside LichtFeld Studio.",
        add_help=False,
    )
    parser.add_argument("--plugin-dir", required=True)
    args, plugin_args = parser.parse_known_args()

    _install_lichtfeld_stub()
    densify = _load_plugin_densify(args.plugin_dir)
    plugin_parser = densify.build_argparser()
    if not plugin_args or any(arg in {"-h", "--help"} for arg in plugin_args):
        plugin_parser.print_help()
        return 0

    def progress(percent, message):
        print(f"PROGRESS:{float(percent):.1f}:{message}", flush=True)

    return densify.dense_init(plugin_parser.parse_args(plugin_args), progress_callback=progress)


if __name__ == "__main__":
    raise SystemExit(main())
