import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


PIPELINE_PREFIX = "PIPELINE_EVENT:"
RESULT_PREFIX = "XPANO_TRAIN_RESULT:"
TRAIN_STATE_PREFIX = "XPANO_TRAIN_STATE:"

_TRAINING_STARTED = re.compile(r"Training started - (\d+) iterations planned")
_MCP_LISTENING = re.compile(r"MCP HTTP server listening on http://127\.0\.0\.1:(\d+)/mcp")
_DATASET_LOADED = re.compile(r"COLMAP dataset loaded successfully")
_LOSS_UPDATED = re.compile(r"Loss updated:\s*([-+0-9.eE]+)\s*\(buffer size:\s*(\d+)\)")
_CHECKPOINT_SAVED = re.compile(r"Checkpoint saved:.*\((\d+) Gaussians, iter (\d+)\)")
_LOG_ERROR = re.compile(r"\[error\].*?\s(?:\S+\.cpp:\d+\s)?(.+)$", re.IGNORECASE)
_FATAL_ERROR_MARKERS = (
    "out of memory",
    "training failed",
    "fatal",
    "uncaught exception",
    "unhandled exception",
)


@dataclass(frozen=True)
class LichtfeldTrainingConfig:
    executable: Path
    data_path: Path
    output_path: Path
    output_name: str = "xpano_gaussian"
    iterations: int = 30000
    strategy: str = "mrnf"
    sh_degree: int = 3
    max_gaussians: int = 1_000_000
    resize_factor: str = "auto"
    max_width: int = 3840
    test_every: int = 0
    use_cpu_cache: bool = True
    use_fs_cache: bool = True
    centralize: str = "off"
    undistort: bool = False
    enable_mip: bool = False
    bilateral_grid: bool = True
    enable_eval: bool = False
    background_mode: str = "solidcolor"
    background_color: str = "#000000"
    gui: bool = True
    close_on_finish: bool = True


def _append_value(command, flag, value):
    command.extend([flag, str(value)])


def _validate_config(config):
    if config.iterations <= 0:
        raise ValueError("iterations must be greater than 0")
    if config.strategy not in {"mcmc", "mrnf", "igs+"}:
        raise ValueError("strategy must be one of: mcmc, mrnf, igs+")
    if config.sh_degree not in {0, 1, 2, 3}:
        raise ValueError("sh_degree must be between 0 and 3")
    if config.max_gaussians <= 0:
        raise ValueError("max_gaussians must be greater than 0")
    if str(config.resize_factor) not in {"auto", "1", "2", "4", "8"}:
        raise ValueError("resize_factor must be auto, 1, 2, 4, or 8")
    if config.max_width < 0:
        raise ValueError("max_width must be greater than or equal to 0")
    if config.test_every < 0:
        raise ValueError("test_every must be greater than or equal to 0")
    if config.centralize not in {"off", "by_pointcloud", "by_cameras"}:
        raise ValueError("centralize must be off, by_pointcloud, or by_cameras")
    if config.background_mode not in {"solidcolor", "modulation", "image", "random"}:
        raise ValueError("unsupported background mode")


def build_lichtfeld_training_command(config):
    _validate_config(config)
    executable = config.executable.resolve(strict=False)
    data_path = config.data_path.resolve(strict=False)
    output_path = config.output_path.resolve(strict=False)
    command = [str(executable)]
    _append_value(command, "--data-path", data_path)
    _append_value(command, "--output-path", output_path)
    _append_value(command, "--output-name", config.output_name)
    _append_value(command, "--iter", config.iterations)
    _append_value(command, "--steps-scaler", 1)
    _append_value(command, "--strategy", config.strategy)
    _append_value(command, "--sh-degree", config.sh_degree)
    _append_value(command, "--max-cap", config.max_gaussians)
    _append_value(command, "--resize_factor", config.resize_factor)
    _append_value(command, "--max-width", config.max_width)
    _append_value(command, "--centralize", config.centralize)
    _append_value(command, "--bg-mode", config.background_mode)
    if config.background_mode == "solidcolor":
        _append_value(command, "--bg-color", config.background_color)
    if config.test_every > 0:
        _append_value(command, "--test-every", config.test_every)
    if not config.use_cpu_cache:
        command.append("--no-cpu-cache")
    if not config.use_fs_cache:
        command.append("--no-fs-cache")
    if config.undistort:
        command.append("--undistort")
    if config.enable_mip:
        command.append("--enable-mip")
    if config.bilateral_grid:
        command.append("--bilateral-grid")
    if config.enable_eval:
        command.append("--eval")
    if not config.gui:
        command.append("--headless")
    _append_value(command, "--log-file", output_path / "lichtfeld.log")
    return command


def build_runtime_override_code(config):
    return "\n".join([
        "import lichtfeld as lf",
        "p = lf.optimization_params()",
        "d = lf.dataset_params()",
        "if not p.has_params() or not d.has_params():",
        "    raise RuntimeError('LichtFeld training parameters are not ready')",
        # NOTE: v0.5.3 auto-scales CLI iterations after loading datasets with more than 300 images.
        f"p.iterations = {int(config.iterations)}",
        "p.steps_scaler = 1.0",
        f"p.use_bilateral_grid = {bool(config.bilateral_grid)!r}",
        f"d.max_width = {int(config.max_width)}",
        "checks = [",
        f"    ('strategy', p.strategy, {config.strategy!r}),",
        f"    ('sh_degree', p.sh_degree, {int(config.sh_degree)}),",
        f"    ('max_cap', p.max_cap, {int(config.max_gaussians)}),",
        f"    ('mip_filter', p.mip_filter, {bool(config.enable_mip)!r}),",
        f"    ('enable_eval', p.enable_eval, {bool(config.enable_eval)!r}),",
        f"    ('undistort', p.undistort, {bool(config.undistort)!r}),",
        f"    ('max_width', d.max_width, {int(config.max_width)}),",
        "]",
        "mismatches = [(name, actual, expected) for name, actual, expected in checks if actual != expected]",
        "if mismatches:",
        "    raise RuntimeError('CLI parameter mismatch: ' + repr(mismatches))",
        "print('XPANO_RUNTIME_PARAMS', p.iterations, p.steps_scaler, p.strategy, p.sh_degree, p.max_cap, p.use_bilateral_grid, d.max_width)",
    ])


def _post_mcp(port, payload, timeout=10):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise RuntimeError(f"LichtFeld MCP request failed: {error}") from error
    if "error" in result:
        raise RuntimeError(f"LichtFeld MCP error: {result['error']}")
    return result


def _initialize_mcp(port):
    _post_mcp(port, {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "xpano", "version": "1"},
        },
    })


def _call_mcp_tool(port, request_id, name, arguments, timeout=10):
    result = _post_mcp(port, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }, timeout=timeout)
    tool_result = result.get("result") or {}
    if tool_result.get("isError"):
        raise RuntimeError(f"LichtFeld MCP tool {name} failed: {tool_result.get('content')}")
    return tool_result


def _configure_and_start_training(port, config):
    _initialize_mcp(port)
    override = _call_mcp_tool(port, 1, "editor.run", {
        "code": build_runtime_override_code(config),
        "show_console": False,
        "wait_for_completion": True,
        "wait_for_output": True,
        "timeout_ms": 10000,
        "output_max_chars": 4000,
    })
    structured = override.get("structuredContent") or {}
    output = ((structured.get("output") or {}).get("text") or "")
    if not structured.get("success", False) or "Traceback" in output:
        raise RuntimeError(f"LichtFeld rejected xPano parameters: {output or override}")
    started = _call_mcp_tool(port, 2, "training.start", {})
    started_content = started.get("structuredContent") or {}
    if started_content.get("success") is False:
        raise RuntimeError(f"LichtFeld refused to start training: {started_content}")


def build_runtime_state_code():
    return "\n".join([
        "import lichtfeld as lf",
        "print('XPANO_TRAIN_STATE:{}|{}|{}|{}|{}'.format(",
        "    lf.trainer_state(),",
        "    lf.trainer_current_iteration(),",
        "    lf.trainer_total_iterations(),",
        "    lf.trainer_current_loss(),",
        "    lf.trainer_num_splats(),",
        "))",
    ])


def parse_runtime_state_result(result):
    structured = result.get("structuredContent") or {}
    output = ((structured.get("output") or {}).get("text") or "")
    marker_at = output.rfind(TRAIN_STATE_PREFIX)
    if not structured.get("success", False) or marker_at < 0:
        raise RuntimeError(f"LichtFeld runtime state query failed: {output or result}")
    payload = output[marker_at + len(TRAIN_STATE_PREFIX):].strip()
    try:
        trainer_state, iteration, maximum, loss, splats = payload.split("|", 4)
        state = {
            "state": trainer_state,
            "iteration": int(iteration),
            "max_iterations": int(maximum),
            "loss": float(loss),
            "num_gaussians": int(splats),
        }
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"LichtFeld returned invalid runtime state: {payload}") from error
    trainer_state = str(state.get("state") or "").lower()
    state["is_running"] = trainer_state == "running"
    state["is_paused"] = trainer_state == "paused"
    return state


def _query_runtime_state(port, request_id):
    result = _call_mcp_tool(port, request_id, "editor.run", {
        "code": build_runtime_state_code(),
        "show_console": False,
        "wait_for_completion": True,
        "wait_for_output": True,
        "timeout_ms": 1500,
        "output_max_chars": 2000,
    }, timeout=3)
    return parse_runtime_state_result(result)


class LichtfeldLogTracker:
    def __init__(self, expected_iterations):
        self.total = max(0, int(expected_iterations))
        self.current = 0
        self.loss = None
        self.splat_count = 0
        self.completed = False
        self.fatal_error = None
        self.started_at = None

    def _event(self, stage, message, percent=None):
        if percent is None:
            percent = self.current / self.total * 100.0 if self.total else 0.0
        result = {
            "phase": "train",
            "stage": stage,
            "percent": round(max(0.0, min(100.0, percent)), 4),
            "phasePercent": round(max(0.0, min(100.0, percent)), 4),
            "message": message,
            "current": self.current,
            "total": self.total,
            "loss": self.loss,
            "splatCount": self.splat_count,
            "trainerState": "finished" if self.completed else "running",
        }
        if self.started_at is not None and self.current > 0 and self.total >= self.current:
            elapsed = max(0.0, time.monotonic() - self.started_at)
            result["etaSeconds"] = int(round(elapsed / self.current * (self.total - self.current)))
        return result

    def parse_line(self, line):
        started = _TRAINING_STARTED.search(line)
        if started:
            self.total = int(started.group(1))
            self.started_at = time.monotonic()
            return self._event("training.initialize", "LichtFeld 已加载数据集，开始高斯训练")

        loss = _LOSS_UPDATED.search(line)
        if loss:
            self.loss = float(loss.group(1))
            return None

        checkpoint = _CHECKPOINT_SAVED.search(line)
        if checkpoint:
            self.splat_count = int(checkpoint.group(1))
            self.current = max(self.current, int(checkpoint.group(2)))
            return self._event(
                "training.optimize",
                f"已保存训练检查点 {self.current}/{self.total}" if self.total else "已保存训练检查点",
            )

        if "Training completed successfully" in line:
            if self.completed:
                return None
            self.completed = True
            self.current = self.total
            return self._event("training.finalize", "高斯训练完成，正在确认结果", percent=100.0)

        error = _LOG_ERROR.search(line)
        if error:
            message = error.group(1).strip()
            if any(marker in message.lower() for marker in _FATAL_ERROR_MARKERS):
                self.fatal_error = message
            event = self._event("training.error", f"LichtFeld 报告错误：{message}")
            event["trainerState"] = "failed" if self.fatal_error else "warning"
            return event
        return None

    def update_from_mcp_state(self, state):
        self.current = max(0, int(state.get("iteration") or 0))
        reported_total = max(0, int(state.get("max_iterations") or 0))
        if reported_total:
            self.total = reported_total
        loss = state.get("loss")
        if isinstance(loss, (int, float)):
            self.loss = float(loss)
        self.splat_count = max(0, int(state.get("num_gaussians") or 0))
        if self.started_at is None and self.current > 0:
            self.started_at = time.monotonic()
        event = self._event(
            "training.optimize",
            f"正在训练高斯 {self.current}/{self.total}" if self.total else "正在训练高斯",
        )
        event["trainerState"] = "paused" if state.get("is_paused") else "running"
        # Live state updates should refresh the UI without filling the human-readable task log.
        event["heartbeat"] = True
        return event


def _latest_artifact(output_path):
    candidates = []
    for pattern in ("*.ply", "*.sog", "*.spz"):
        candidates.extend(output_path.rglob(pattern))
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


def _drain_output(lines):
    while True:
        try:
            raw_line = lines.get_nowait()
        except queue.Empty:
            return
        if raw_line:
            line = raw_line.rstrip()
            if line:
                print(line, flush=True)


def _read_new_log_lines(log_path, offset, pending):
    if not log_path.is_file():
        return offset, pending, []
    size = log_path.stat().st_size
    if size < offset:
        offset = 0
        pending = b""
    with log_path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read()
        offset = handle.tell()
    if not chunk:
        return offset, pending, []
    parts = (pending + chunk).split(b"\n")
    pending = parts.pop()
    lines = [part.rstrip(b"\r").decode("utf-8", errors="replace") for part in parts]
    return offset, pending, lines


def _emit_pipeline_event(event):
    print(PIPELINE_PREFIX + json.dumps(event, ensure_ascii=False), flush=True)


def _close_managed_process(process):
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    except OSError:
        pass


def run_lichtfeld_training(config):
    output_path = config.output_path.resolve(strict=False)
    executable = config.executable.resolve(strict=False)
    output_path.mkdir(parents=True, exist_ok=True)
    log_path = output_path / "lichtfeld.log"
    log_path.unlink(missing_ok=True)
    command = build_lichtfeld_training_command(config)
    environment = os.environ.copy()
    environment["PATH"] = str(executable.parent) + os.pathsep + environment.get("PATH", "")
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8:replace"
    _emit_pipeline_event({
        "phase": "train",
        "stage": "training.launch",
        "percent": 0,
        "phasePercent": 0,
        "message": "正在启动 LichtFeld Studio GUI" if config.gui else "正在启动 LichtFeld Studio",
        "current": 0,
        "total": config.iterations,
        "trainerState": "launching",
    })
    process = subprocess.Popen(
        command,
        cwd=str(executable.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    output_lines = queue.Queue()

    def read_output():
        if process.stdout is not None:
            for raw_line in process.stdout:
                output_lines.put(raw_line)
        output_lines.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    tracker = LichtfeldLogTracker(config.iterations)
    log_offset = 0
    pending = b""
    last_emit_at = 0.0
    last_event = None
    success_seen_at = None
    mcp_port = None
    dataset_ready = False
    training_started = False
    next_mcp_poll_at = 0.0
    mcp_request_id = 3
    mcp_poll_failures = 0
    startup_deadline = time.monotonic() + 120

    while True:
        _drain_output(output_lines)
        log_offset, pending, new_lines = _read_new_log_lines(log_path, log_offset, pending)
        for line in new_lines:
            mcp_match = _MCP_LISTENING.search(line)
            if mcp_match:
                mcp_port = int(mcp_match.group(1))
            if _DATASET_LOADED.search(line):
                dataset_ready = True
            event = tracker.parse_line(line)
            if event is None:
                continue
            last_event = event
            now = time.monotonic()
            terminal = event["stage"] in {"training.finalize", "training.error"}
            if terminal or now - last_emit_at >= 0.25:
                _emit_pipeline_event(event)
                last_emit_at = now
            if tracker.completed and success_seen_at is None:
                success_seen_at = now

        if not training_started and mcp_port is not None and dataset_ready:
            _emit_pipeline_event({
                "phase": "train",
                "stage": "training.configure",
                "percent": 0,
                "phasePercent": 0,
                "message": "正在向 LichtFeld GUI 应用 xPano 训练参数",
                "current": 0,
                "total": config.iterations,
                "trainerState": "configuring",
            })
            try:
                _configure_and_start_training(mcp_port, config)
            except Exception:
                _close_managed_process(process)
                raise
            training_started = True
            next_mcp_poll_at = time.monotonic() + 1.0

        now = time.monotonic()
        if (
            training_started
            and mcp_port is not None
            and not tracker.completed
            and now >= next_mcp_poll_at
        ):
            next_mcp_poll_at = now + 1.0
            try:
                state = _query_runtime_state(mcp_port, mcp_request_id)
                mcp_request_id += 1
                event = tracker.update_from_mcp_state(state)
                _emit_pipeline_event(event)
                mcp_poll_failures = 0
            except RuntimeError as error:
                mcp_request_id += 1
                mcp_poll_failures += 1
                # WARN: Progress polling is diagnostic; a transient MCP failure must not abort healthy training.
                if mcp_poll_failures == 1 or mcp_poll_failures % 10 == 0:
                    print(f"WARNING:LichtFeld progress polling failed: {error}", flush=True)

        if not training_started and time.monotonic() > startup_deadline:
            _close_managed_process(process)
            raise RuntimeError("LichtFeld GUI did not finish loading the dataset within 120 seconds")

        if tracker.fatal_error:
            _close_managed_process(process)
            raise RuntimeError(tracker.fatal_error)

        artifact = _latest_artifact(output_path) if tracker.completed else None
        if tracker.completed and artifact is not None:
            if last_event is not None and last_event["stage"] != "training.finalize":
                _emit_pipeline_event(tracker._event("training.finalize", "高斯训练完成", percent=100.0))
            if config.close_on_finish:
                _close_managed_process(process)
            print(RESULT_PREFIX + json.dumps({
                "outputPath": str(output_path),
                "artifactPath": str(artifact),
            }, ensure_ascii=False), flush=True)
            return

        if tracker.completed and success_seen_at is not None and time.monotonic() - success_seen_at > 5:
            _close_managed_process(process)
            raise RuntimeError("LichtFeld reported success but produced no Gaussian artifact")

        return_code = process.poll()
        if return_code is not None:
            # Consume one final log flush before deciding whether the run failed.
            time.sleep(0.05)
            log_offset, pending, final_lines = _read_new_log_lines(log_path, log_offset, pending)
            for line in final_lines:
                event = tracker.parse_line(line)
                if event is not None:
                    _emit_pipeline_event(event)
            artifact = _latest_artifact(output_path) if tracker.completed else None
            if tracker.completed and artifact is not None:
                print(RESULT_PREFIX + json.dumps({
                    "outputPath": str(output_path),
                    "artifactPath": str(artifact),
                }, ensure_ascii=False), flush=True)
                return
            detail = tracker.fatal_error or f"LichtFeld Studio exited with code {return_code}"
            raise RuntimeError(detail)

        time.sleep(0.1)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Run one xPano LichtFeld Studio training stage.")
    parser.add_argument("--executable", required=True)
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--project-root")
    parser.add_argument("--output-name", default="xpano_gaussian")
    parser.add_argument("--iterations", type=int, default=30000)
    parser.add_argument("--strategy", default="mrnf")
    parser.add_argument("--sh-degree", type=int, default=3)
    parser.add_argument("--max-gaussians", type=int, default=1_000_000)
    parser.add_argument("--resize-factor", default="auto")
    parser.add_argument("--max-width", type=int, default=3840)
    parser.add_argument("--test-every", type=int, default=0)
    parser.add_argument("--no-cpu-cache", action="store_true")
    parser.add_argument("--no-fs-cache", action="store_true")
    parser.add_argument("--centralize", default="off")
    parser.add_argument("--undistort", action="store_true")
    parser.add_argument("--enable-mip", action="store_true")
    parser.add_argument("--bilateral-grid", action="store_true")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--background-mode", default="solidcolor")
    parser.add_argument("--background-color", default="#000000")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--keep-open", action="store_true")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    config = LichtfeldTrainingConfig(
        executable=Path(args.executable),
        data_path=Path(args.data_path),
        output_path=Path(args.output_path),
        output_name=args.output_name,
        iterations=args.iterations,
        strategy=args.strategy,
        sh_degree=args.sh_degree,
        max_gaussians=args.max_gaussians,
        resize_factor=args.resize_factor,
        max_width=args.max_width,
        test_every=args.test_every,
        use_cpu_cache=not args.no_cpu_cache,
        use_fs_cache=not args.no_fs_cache,
        centralize=args.centralize,
        undistort=args.undistort,
        enable_mip=args.enable_mip,
        bilateral_grid=args.bilateral_grid,
        enable_eval=args.eval,
        background_mode=args.background_mode,
        background_color=args.background_color,
        gui=not args.headless,
        close_on_finish=not args.keep_open,
    )
    try:
        run_lichtfeld_training(config)
    except Exception as error:
        print(f"ERROR:{error}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
