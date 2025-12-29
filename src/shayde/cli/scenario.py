"""Scenario CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()
app = typer.Typer(no_args_is_help=True)


@app.command("parse")
def parse_scenario(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    validate: bool = typer.Option(
        False, "--validate", "-v", help="Validate scenario structure"
    ),
    output_json: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON"
    ),
):
    """Parse and display scenario structure."""
    from shayde.core.scenario.parser import ScenarioParser

    parser = ScenarioParser()

    try:
        scenario = parser.parse(file)
    except Exception as e:
        console.print(f"[red]Error parsing scenario:[/red] {e}")
        raise typer.Exit(1)

    if validate:
        is_valid, errors, warnings = parser.validate(scenario)

        if errors:
            console.print("[red]Validation Errors:[/red]")
            for error in errors:
                console.print(f"  [red]✗[/red] {error}")

        if warnings:
            console.print("[yellow]Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]![/yellow] {warning}")

        if is_valid:
            console.print("[green]✓ Scenario is valid[/green]")
        else:
            raise typer.Exit(1)

    if output_json:
        console.print_json(json.dumps(scenario.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_scenario_summary(scenario)


@app.command("list")
def list_steps(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    part: Optional[int] = typer.Option(
        None, "--part", "-p", help="Show only specific part"
    ),
):
    """List all steps in scenario."""
    from shayde.core.scenario.parser import ScenarioParser

    parser = ScenarioParser()

    try:
        scenario = parser.parse(file)
    except Exception as e:
        console.print(f"[red]Error parsing scenario:[/red] {e}")
        raise typer.Exit(1)

    _print_step_list(scenario, part_filter=part)


def _print_scenario_summary(scenario) -> None:
    """Print scenario summary."""
    # Header
    console.print()
    console.print(Panel(
        f"[bold]{scenario.meta.title}[/bold]\n"
        f"ID: {scenario.meta.id} | Priority: {scenario.meta.priority.value} | "
        f"Est. Time: {scenario.meta.estimated_time or '?'}min",
        title="Scenario",
        border_style="blue",
    ))

    # Prerequisites
    if scenario.prerequisites:
        console.print("\n[bold]Prerequisites:[/bold]")
        for prereq in scenario.prerequisites:
            console.print(f"  • {prereq}")

    # Coverage
    if scenario.coverage:
        console.print("\n[bold]Coverage:[/bold]")
        for cov in scenario.coverage:
            status_icon = "○" if cov.status.value == "complete" else "△"
            console.print(f"  {status_icon} {cov.name}")

    # Accounts
    if scenario.accounts:
        console.print("\n[bold]Accounts:[/bold]")
        for key, acc in scenario.accounts.items():
            console.print(f"  [{key}] {acc.email} ({acc.role or 'N/A'})")

    # Summary
    console.print()
    table = Table(show_header=False, box=None)
    table.add_column("Label", style="dim")
    table.add_column("Value")
    table.add_row("Parts", str(len(scenario.steps)))
    table.add_row("Steps", str(scenario.total_steps))
    table.add_row("Screenshots", str(scenario.total_screenshots))
    console.print(table)


def _print_step_list(scenario, part_filter: Optional[int] = None) -> None:
    """Print step list."""
    console.print()
    console.print(f"[bold]{scenario.meta.id}:[/bold] {scenario.meta.title}")
    console.print("━" * 50)

    total_steps = 0
    total_screenshots = 0

    for part in scenario.steps:
        if part_filter is not None and part.part != part_filter:
            continue

        account_info = f"(account: {part.account or 'none'})"
        console.print(f"\n[bold blue]Part {part.part}:[/bold blue] {part.title} [dim]{account_info}[/dim]")

        for step in part.items:
            screenshot_icon = " 📸" if step.has_screenshot else ""
            action_type = _get_action_type(step.action)
            action_hint = f" [dim]({action_type})[/dim]" if action_type else ""

            console.print(f"  [{step.id}] {step.desc}{action_hint}{screenshot_icon}")
            total_steps += 1
            if step.has_screenshot:
                total_screenshots += 1

    console.print()
    console.print(f"[dim]Total: {total_steps} steps, {total_screenshots} screenshots[/dim]")


def _get_action_type(action) -> Optional[str]:
    """Get action type hint."""
    if action is None:
        return "verify"
    if isinstance(action, dict):
        if "goto" in action:
            return "goto"
        if "fill" in action:
            return "fill"
        if "click" in action:
            return "click"
        if "select" in action:
            return "select"
        if "upload" in action:
            return "upload"
        if "login" in action:
            return "login"
        if "logout" in action:
            return "logout"
    if isinstance(action, list):
        return "multi"
    return None


@app.command("run")
def run_scenario_cmd(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for screenshots"
    ),
    part: Optional[int] = typer.Option(
        None, "--part", "-p", help="Run only specific part"
    ),
    stop_on_error: bool = typer.Option(
        False, "--stop-on-error", "-e", help="Stop execution on first error"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", "-b", help="Base URL override"
    ),
    video: bool = typer.Option(
        False, "--video", "-v", help="Record video of scenario execution"
    ),
):
    """Run all steps in scenario."""
    import asyncio
    from shayde.core.scenario.runner import run_scenario
    from shayde.core.scenario.models import StepStatus

    console.print(f"\n[bold blue]Running scenario:[/bold blue] {file.name}")

    try:
        session = asyncio.run(run_scenario(
            scenario_path=file,
            output_dir=output_dir,
            base_url=base_url,
            stop_on_error=stop_on_error,
            part_filter=part,
            record_video=video,
        ))

        # Print summary
        result = session.result
        console.print()
        console.print("━" * 50)

        status_icon = "✓" if result.status == StepStatus.PASSED else "✗"
        status_color = "green" if result.status == StepStatus.PASSED else "red"
        console.print(f"[{status_color}]{status_icon} {result.status.value.upper()}[/{status_color}]")

        console.print(f"  Total: {result.total_steps} steps")
        console.print(f"  Passed: [green]{result.passed_count}[/green]")
        if result.failed_count > 0:
            console.print(f"  Failed: [red]{result.failed_count}[/red]")
        if result.skipped_count > 0:
            console.print(f"  Skipped: [yellow]{result.skipped_count}[/yellow]")
        console.print(f"  Duration: {result.duration_ms / 1000:.1f}s")
        console.print(f"  Output: {result.output_dir}")
        if result.video_path:
            console.print(f"  🎬 Video: {result.video_path}")

        if result.status == StepStatus.FAILED:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error running scenario:[/red] {e}")
        raise typer.Exit(1)


@app.command("step")
def run_step_cmd(
    file: Path = typer.Argument(..., help="Path to scenario YAML file", exists=True),
    step_id: str = typer.Argument(..., help="Step ID to execute (e.g., '1-1')"),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for screenshot"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--base-url", "-b", help="Base URL override"
    ),
):
    """Execute a single step."""
    import asyncio
    from shayde.core.scenario.runner import run_single_step
    from shayde.core.scenario.models import StepStatus

    console.print(f"\n[bold blue]Running step:[/bold blue] {step_id}")

    try:
        result = asyncio.run(run_single_step(
            scenario_path=file,
            step_id=step_id,
            output_dir=output_dir,
            base_url=base_url,
        ))

        if result is None:
            console.print(f"[red]Step not found:[/red] {step_id}")
            raise typer.Exit(1)

        # Print result
        console.print()
        status_icon = "✓" if result.status == StepStatus.PASSED else "✗"
        status_color = "green" if result.status == StepStatus.PASSED else "red"
        console.print(f"[{status_color}]{status_icon} {result.desc}[/{status_color}]")

        if result.screenshot:
            console.print(f"  📸 {result.screenshot}")

        if result.error:
            console.print(f"  [red]Error: {result.error}[/red]")

        console.print(f"  Duration: {result.duration_ms}ms")

        if result.status == StepStatus.FAILED:
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error running step:[/red] {e}")
        raise typer.Exit(1)


@app.command("report")
def generate_report_cmd(
    results_dir: Path = typer.Argument(
        ..., help="Directory containing results.json", exists=True
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (default: report.md in results_dir)"
    ),
):
    """Generate Markdown report from execution results."""
    from shayde.core.scenario.reporter import generate_report

    try:
        report_path = generate_report(results_dir, output)
        console.print(f"[green]✓ Report generated:[/green] {report_path}")

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error generating report:[/red] {e}")
        raise typer.Exit(1)
