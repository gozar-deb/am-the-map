"""
Am the Map CLI (section 4) -- Typer + Rich, talks to the FastAPI backend
over HTTP so it works identically whether the backend is local, on a
Raspberry Pi, or on a remote Linux server (set AM_MAP_API_URL).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from am_map.client import ApiError, Client

app = typer.Typer(add_completion=False, no_args_is_help=False, help="Am the Map -- WiFi/RF spatial sensing platform CLI")
sensors_app = typer.Typer(help="Manage sensors")
models_app = typer.Typer(help="Manage spatial ML models")
dataset_app = typer.Typer(help="Manage datasets (section 28)")
experiments_app = typer.Typer(help="Manage experiments (section 29)")
app.add_typer(sensors_app, name="sensors")
app.add_typer(models_app, name="models")
app.add_typer(dataset_app, name="dataset")
app.add_typer(experiments_app, name="experiments")

console = Console()


def _client() -> Client:
    return Client()


def _fail(e: ApiError) -> None:
    console.print(f"[bold red]Error:[/bold red] {e}")
    raise typer.Exit(code=1)


BANNER = r"""
[bold cyan] █████╗ ███╗   ███╗    ████████╗██╗  ██╗███████╗    ███╗   ███╗ █████╗ ██████╗ [/bold cyan]
[bold cyan]██╔══██╗████╗ ████║    ╚══██╔══╝██║  ██║██╔════╝    ████╗ ████║██╔══██╗██╔══██╗[/bold cyan]
[bold cyan]███████║██╔████╔██║       ██║   ███████║█████╗      ██╔████╔██║███████║██████╔╝[/bold cyan]
[bold cyan]██╔══██║██║╚██╔╝██║       ██║   ██╔══██║██╔══╝      ██║╚██╔╝██║██╔══██║██╔═══╝ [/bold cyan]
[bold cyan]██║  ██║██║ ╚═╝ ██║       ██║   ██║  ██║███████╗    ██║ ╚═╝ ██║██║  ██║██║     [/bold cyan]
[bold cyan]╚═╝  ╚═╝╚═╝     ╚═╝       ╚═╝   ╚═╝  ╚═╝╚══════╝    ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     [/bold cyan]
[dim]Wireless Spatial Intelligence -- an experimental RF spatial perception platform[/dim]
"""


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        try:
            client = Client()
            data = client.get("/api/status")
            _print_status(data)
        except ApiError as e:
            console.print(f"[yellow]{e}[/yellow]")
        console.print("\nRun [bold]am-map --help[/bold] for commands, or [bold]am-map interactive[/bold] for a REPL.")


def _print_status(data: dict) -> None:
    m = data.get("map", {})
    env = m.get("environment", {})
    table = Table(show_header=False, box=None)
    table.add_row("Sensors", f"{len(m.get('sensors', []))} ({sum(1 for s in m.get('sensors', []) if s['status']=='online')} online)")
    table.add_row("CSI", f"{env.get('avg_csi_hz', 0)} Hz -- {'[green]Streaming[/green]' if data.get('acquisition_running') else '[red]Stopped[/red]'}")
    table.add_row("Environment", f"{env.get('bounds_m')} m, voxel {env.get('voxel_resolution_m')} m")
    table.add_row("Occupancy", str(env.get("occupancy_count_estimate", "-")))
    table.add_row("Movement probability", str(env.get("movement_probability", "-")))
    table.add_row("3D confidence", f"{env.get('confidence', 0)*100:.0f}%" if env.get("confidence") is not None else "-")
    table.add_row("Model", f"{env.get('model')} (baseline, unvalidated)" if env.get("model_is_baseline") else str(env.get("model")))
    table.add_row("Data provenance", str(m.get("provenance", "-")))
    table.add_row("AI", f"{data.get('ai_mode', '-').upper()}" + (" -- 🔒 Privacy Mode" if data.get("privacy_mode") else ""))
    table.add_row("Map", "[bold green]LIVE[/bold green]" if data.get("acquisition_running") else "idle")
    console.print(Panel(table, title="AM THE MAP", border_style="cyan"))


@app.command()
def status():
    """Show current system + map status."""
    client = _client()
    try:
        data = client.get("/api/status")
    except ApiError as e:
        _fail(e)
        return
    _print_status(data)


@app.command()
def doctor():
    """Run health checks (section 45)."""
    client = _client()
    try:
        d = client.get("/api/system/doctor")
    except ApiError as e:
        _fail(e)
        return
    table = Table(title="am-map doctor")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Python", d["python"])
    for name, ok in d["dependencies"].items():
        table.add_row(f"dependency: {name}", "✓" if ok else "✗ (optional)")
    table.add_row("Database", "✓" if d["database"] else "✗")
    table.add_row("WebSocket", "✓" if d["websocket"] else "✗")
    table.add_row("GPU detected", "✓" if d["gpu_detected"] else "✗ (CPU mode)")
    table.add_row("CUDA available", "✓" if d["cuda_available"] else "✗")
    table.add_row("Sensor connectivity", "✓" if d["sensor_connectivity"] else "✗")
    table.add_row("CSI stream active", "✓" if d["csi_stream_active"] else "✗")
    table.add_row("Inference mode", d["inference_mode"])
    table.add_row("Training recommendation", d["training_recommendation"])
    console.print(table)


@app.command()
def scan():
    """Probe for reachable sensors (section 4)."""
    client = _client()
    try:
        d = client.get("/api/system/scan")
    except ApiError as e:
        _fail(e)
        return
    table = Table(title="Sensor scan")
    table.add_column("ID")
    table.add_column("Hardware")
    table.add_column("Status")
    for s in d["known_sensors"]:
        table.add_row(s["id"], s["hardware_type"], s["status"])
    console.print(table)
    if not d["known_sensors"]:
        console.print("[dim]No sensors registered yet. The simulator provides NODE-01/02/03 "
                       "automatically once the pipeline is started (see `am-map config`).[/dim]")


@app.command(name="map")
def show_map(visualize: bool = typer.Option(False, "--visualize", "-v", help="Render an ASCII top-down heatmap")):
    """Show the current probabilistic RF spatial map (section 8)."""
    client = _client()
    try:
        d = client.get("/api/maps/current")
    except ApiError as e:
        _fail(e)
        return
    env = d.get("environment", {})
    console.print(Panel.fit(
        f"Occupancy: {env.get('occupancy_count_estimate')} (p={env.get('occupancy_probability')})\n"
        f"Movement probability: {env.get('movement_probability')}\n"
        f"Confidence: {env.get('confidence')}\n"
        f"Change state: {env.get('change_state')}\n"
        f"Active voxels: {len(d.get('voxels', []))}\n"
        f"Provenance: {d.get('provenance')}",
        title="Map summary",
    ))
    if visualize:
        from am_map.render import render_topdown_heatmap
        console.print(render_topdown_heatmap(d.get("voxels", []), tuple(env.get("bounds_m", [5, 5, 3]))))


@app.command()
def visualize():
    """Render an ASCII top-down RF heatmap in the terminal (section 6/7 --
    the full interactive 3D view lives in the web dashboard)."""
    show_map(visualize=True)


@app.command()
def track():
    """Show currently tracked candidate objects (section 33)."""
    client = _client()
    try:
        d = client.get("/api/tracking")
    except ApiError as e:
        _fail(e)
        return
    table = Table(title="Tracked objects")
    for col in ("ID", "X", "Y", "Z", "Velocity (m/s)", "Confidence"):
        table.add_column(col)
    for o in d.get("objects", []):
        table.add_row(o["id"], str(o["x"]), str(o["y"]), str(o["z"]), str(o["velocity_mps"]), str(o["confidence"]))
    console.print(table)


@app.command()
def calibrate(name: str = typer.Option("calibration", "--name"), duration: float = typer.Option(10.0, "--duration", "-d")):
    """Guided calibration workflow (section 22)."""
    client = _client()
    console.print(f"[cyan]Calibrating for {duration:.0f}s...[/cyan] (make sure the room is in its baseline state)")
    try:
        result = client.post("/api/calibration/run", json={"name": name, "duration_s": duration})
    except ApiError as e:
        _fail(e)
        return
    if "error" in result:
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(1)
    table = Table(show_header=False)
    table.add_row("Signal stability", f"{result['signal_stability_pct']}%")
    table.add_row("Sensor synchronization", f"{result['sensor_synchronization_pct']}%")
    table.add_row("Packet quality", f"{result['packet_quality_pct']}%")
    table.add_row("Calibration confidence", f"{result['calibration_confidence_pct']}%")
    console.print(Panel(table, title="Calibration complete"))


@app.command()
def record(
    name: str = typer.Argument(..., help="Session name"),
    duration: Optional[float] = typer.Option(None, "--duration", "-d", help="Stop automatically after N seconds"),
):
    """Record a session (section 30)."""
    client = _client()
    try:
        session = client.post("/api/sessions/record", json={"name": name, "source": "simulated"})
    except ApiError as e:
        _fail(e)
        return
    console.print(f"[green]Recording started[/green] -- session {session['id']}")
    if duration:
        with console.status(f"Recording for {duration:.0f}s..."):
            time.sleep(duration)
        stopped = client.post(f"/api/sessions/{session['id']}/stop")
        console.print(f"[green]Recording stopped[/green] -- {stopped['frame_count']} frames -> {stopped['recording_path']}")
    else:
        console.print(f"Run [bold]am-map sessions stop {session['id']}[/bold] when done.")


@app.command()
def replay(session_id: str, speed: float = typer.Option(1.0, "--speed")):
    """Replay a recorded session (section 30)."""
    client = _client()
    try:
        result = client.post(f"/api/sessions/{session_id}/replay", json={}, speed=speed)
    except ApiError as e:
        _fail(e)
        return
    console.print(f"[green]Replaying[/green] session {session_id} at {speed}x from {result['path']}")


@app.command()
def sessions(stop: Optional[str] = typer.Option(None, "--stop", help="Stop the given session id")):
    """List sessions, or stop one with --stop <id> (section 30)."""
    client = _client()
    if stop:
        try:
            result = client.post(f"/api/sessions/{stop}/stop")
        except ApiError as e:
            _fail(e)
            return
        console.print(f"Stopped -- {result['frame_count']} frames recorded.")
        return
    try:
        rows = client.get("/api/sessions")
    except ApiError as e:
        _fail(e)
        return
    table = Table(title="Sessions")
    for col in ("ID", "Name", "Status", "Source", "Frames"):
        table.add_column(col)
    for s in rows:
        table.add_row(s["id"], s["name"], s["status"], s["source"], str(s["frame_count"]))
    console.print(table)


@app.command()
def export(
    out: Path = typer.Option(Path("am-map-export.json"), "--out", "-o"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    fmt: str = typer.Option("json", "--format", help="json | markdown | html | pdf"),
):
    """Export the current map (or a session's report) to a local file (section 53 MVP #15)."""
    client = _client()
    try:
        report = client.post("/api/reports", json={"session_id": session_id, "format": fmt})
    except ApiError as e:
        _fail(e)
        return
    if isinstance(report, dict):
        out.write_text(json.dumps(report, indent=2))
    elif isinstance(report, bytes):
        out.write_bytes(report)
    else:
        out.write_text(str(report))
    console.print(f"[green]Exported[/green] -> {out}")


@sensors_app.command("list")
def sensors_list():
    client = _client()
    try:
        rows = client.get("/api/sensors")
    except ApiError as e:
        _fail(e)
        return
    table = Table(title="Sensor network")
    for col in ("ID", "Name", "Hardware", "Status", "Position"):
        table.add_column(col)
    for s in rows:
        table.add_row(s["id"], s["name"], s["hardware_type"], s["status"], str(s["position"]))
    console.print(table)


@sensors_app.command("add")
def sensors_add(
    name: str,
    x: float = typer.Option(0.0),
    y: float = typer.Option(0.0),
    z: float = typer.Option(2.0),
    hardware_type: str = typer.Option("esp32-s3"),
):
    """Register a sensor and its position (sections 9, 10)."""
    client = _client()
    try:
        sensor = client.post("/api/sensors", json={"name": name, "x": x, "y": y, "z": z, "hardware_type": hardware_type})
    except ApiError as e:
        _fail(e)
        return
    console.print(f"[green]Added[/green] {sensor['name']} at {sensor['position']}")


@sensors_app.command("position")
def sensors_position(sensor_id: str, x: float, y: float, z: float):
    client = _client()
    try:
        sensor = client.put(f"/api/sensors/{sensor_id}/position", json={"x": x, "y": y, "z": z})
    except ApiError as e:
        _fail(e)
        return
    console.print(f"[green]Updated[/green] {sensor['id']} -> {sensor['position']}")


@models_app.command("list")
def models_list():
    client = _client()
    try:
        rows = client.get("/api/models")
    except ApiError as e:
        _fail(e)
        return
    table = Table(title="Models (section 40)")
    for col in ("Name", "Task", "Architecture", "Validated", "Baseline"):
        table.add_column(col)
    for m in rows:
        table.add_row(m["name"], m["task"], m["architecture"], str(m["validated"]), str(m["is_baseline"]))
    console.print(table)


@models_app.command("info")
def models_info(name: str):
    client = _client()
    try:
        m = client.get(f"/api/models/{name}")
    except ApiError as e:
        _fail(e)
        return
    console.print_json(data=m)


@models_app.command("install")
def models_install(name: str):
    client = _client()
    try:
        result = client.post(f"/api/models/{name}/install")
    except ApiError as e:
        _fail(e)
        return
    console.print(result["message"])


@models_app.command("remove")
def models_remove(name: str):
    client = _client()
    try:
        client.delete(f"/api/models/{name}")
    except ApiError as e:
        _fail(e)
        return
    console.print(f"Removed {name}")


@app.command()
def train(config: Optional[Path] = typer.Option(None, "--config", "-c")):
    """Research training interface (section 41).

    Am the Map ships with an unvalidated baseline heuristic, not a trained
    neural model -- there is nothing to fine-tune yet. This command explains
    the path to a real trainer rather than pretending to train something.
    """
    console.print(Panel(
        "No trainable checkpoint is wired up yet (see docs/training.md).\n\n"
        "To add real training:\n"
        "  1. Collect a labeled dataset with `am-map dataset create` + ground truth.\n"
        "  2. Implement a PyTorch training loop against backend/app/ml/interfaces.py::TorchSpatialModel.\n"
        "  3. Point ml/registry.py at the resulting checkpoint.\n\n"
        f"Config file given: {config or '(none)'}",
        title="am-map train",
        border_style="yellow",
    ))


@app.command()
def config():
    """Show current runtime configuration (section 4)."""
    client = _client()
    try:
        d = client.get("/api/system/config")
    except ApiError as e:
        _fail(e)
        return
    console.print_json(data=d)
    console.print("[dim]Edit .env to change these (see .env.example); AI provider keys are never read from the CLI.[/dim]")


@app.command()
def ai(question: str, provider: Optional[str] = typer.Option(None, "--provider")):
    """Ask the optional AI Gateway about the current map (sections 18-20)."""
    client = _client()
    try:
        result = client.post("/api/ai/ask", json={"question": question, "provider": provider})
    except ApiError as e:
        _fail(e)
        return
    if not result.get("answered"):
        console.print(f"[yellow]{result.get('message')}[/yellow]")
        return
    console.print(Panel(result["response"], title=f"AI ({result['provider']})", border_style="magenta"))


@dataset_app.command("create")
def dataset_create(name: str, description: str = typer.Option("", "--description")):
    client = _client()
    try:
        result = client.post("/api/datasets", json={"name": name, "description": description})
    except ApiError as e:
        _fail(e)
        return
    console.print(f"[green]Created dataset[/green] {result['name']}")


@dataset_app.command("import")
def dataset_import(name: str, source_dir: str):
    client = _client()
    try:
        result = client.post("/api/datasets/import", json={"name": name, "source_dir": source_dir})
    except ApiError as e:
        _fail(e)
        return
    console.print_json(data=result)


@dataset_app.command("export")
def dataset_export(name: str, dest_dir: str):
    client = _client()
    try:
        result = client.post("/api/datasets/export", json={"name": name, "dest_dir": dest_dir})
    except ApiError as e:
        _fail(e)
        return
    console.print(f"[green]Exported[/green] -> {result['archive_path']}")


@dataset_app.command("inspect")
def dataset_inspect(name: str):
    client = _client()
    try:
        result = client.get(f"/api/datasets/{name}")
    except ApiError as e:
        _fail(e)
        return
    console.print_json(data=result)


@experiments_app.command("create")
def experiments_create(
    name: str,
    hardware: Optional[str] = typer.Option(None),
    model_name: Optional[str] = typer.Option(None, "--model"),
    duration_minutes: Optional[float] = typer.Option(None, "--duration"),
):
    client = _client()
    try:
        result = client.post("/api/experiments", json={
            "name": name, "hardware": hardware, "model_name": model_name, "duration_minutes": duration_minutes,
        })
    except ApiError as e:
        _fail(e)
        return
    console.print(f"[green]Created experiment[/green] {result['id']}")


@experiments_app.command("list")
def experiments_list():
    client = _client()
    try:
        rows = client.get("/api/experiments")
    except ApiError as e:
        _fail(e)
        return
    table = Table(title="Experiments")
    for col in ("ID", "Name", "Hardware", "Model", "Created"):
        table.add_column(col)
    for e in rows:
        table.add_row(e["id"], e["name"], str(e["hardware"]), str(e["model_name"]), e["created_at"])
    console.print(table)


@app.command()
def interactive():
    """Interactive terminal (section 4)."""
    console.print(BANNER)
    console.print("Type a command (status, sensors, calibrate, scan, map, record, visualize, track, exit)\n")
    client = _client()
    while True:
        try:
            cmd = console.input("[bold cyan]> [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd in ("exit", "quit"):
            break
        if not cmd:
            continue
        try:
            if cmd == "status":
                _print_status(client.get("/api/status"))
            elif cmd == "sensors":
                sensors_list()
            elif cmd == "scan":
                scan()
            elif cmd == "map":
                show_map(visualize=False)
            elif cmd == "visualize":
                show_map(visualize=True)
            elif cmd == "track":
                track()
            elif cmd == "calibrate":
                calibrate(name="interactive", duration=10.0)
            elif cmd == "record":
                console.print("[dim]Use `am-map record <name>` from the shell for recording with options.[/dim]")
            else:
                console.print(f"[yellow]Unknown command: {cmd}[/yellow]")
        except typer.Exit:
            pass
        except ApiError as e:
            console.print(f"[red]{e}[/red]")


if __name__ == "__main__":
    app()
