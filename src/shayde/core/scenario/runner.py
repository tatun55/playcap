"""Scenario runner - executes steps and captures screenshots."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from playwright.async_api import Page

from shayde.core.scenario.actions import ActionExecutor
from shayde.core.scenario.assertions import AssertionExecutor
from shayde.core.scenario.models import StepResult, StepStatus
from shayde.core.scenario.parser import Part, Scenario, Step
from shayde.core.scenario.session import ScenarioSession

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """Executes scenario steps with Playwright.

    Handles:
    - Step execution with actions and assertions
    - Screenshot capture at checkpoints
    - Account switching between parts
    - Progress callbacks for UI updates
    """

    def __init__(
        self,
        session: ScenarioSession,
        on_step_start: Optional[Callable[[Step, Part], None]] = None,
        on_step_complete: Optional[Callable[[Step, StepResult], None]] = None,
        on_part_start: Optional[Callable[[Part], None]] = None,
        on_part_complete: Optional[Callable[[Part], None]] = None,
    ):
        self.session = session
        self.action_executor = ActionExecutor(base_url=session.base_url)
        self.assertion_executor = AssertionExecutor()

        # Callbacks
        self.on_step_start = on_step_start
        self.on_step_complete = on_step_complete
        self.on_part_start = on_part_start
        self.on_part_complete = on_part_complete

        self._stop_on_error = False

    async def run_all(self, stop_on_error: bool = False) -> None:
        """Run all parts and steps in the scenario.

        Args:
            stop_on_error: Stop execution on first error
        """
        self._stop_on_error = stop_on_error
        scenario = self.session.scenario

        logger.info(f"Running scenario: {scenario.meta.id}")

        try:
            await self.session.setup()

            for part in scenario.steps:
                if self.on_part_start:
                    self.on_part_start(part)

                self.session.start_part(part)

                # Switch account if needed
                if part.account != self.session.current_account:
                    success = await self.session.switch_account(part.account)
                    if not success and part.account:
                        logger.error(f"Failed to switch to account: {part.account}")
                        if stop_on_error:
                            break

                # Run steps
                for step in part.items:
                    result = await self.run_step(step, part)

                    if result.status == StepStatus.FAILED and stop_on_error:
                        logger.error(f"Step {step.id} failed, stopping execution")
                        break

                self.session.finish_part()

                if self.on_part_complete:
                    self.on_part_complete(part)

                # Check if we should stop
                if stop_on_error and any(
                    s.status == StepStatus.FAILED
                    for s in self.session.result.parts[-1].steps
                ):
                    break

            self.session.finish_scenario()
            self.session.save_results()

        finally:
            await self.session.teardown()

    async def run_step(self, step: Step, part: Part) -> StepResult:
        """Run a single step.

        Args:
            step: Step to execute
            part: Part containing the step

        Returns:
            StepResult
        """
        logger.info(f"Running step {step.id}: {step.desc}")

        if self.on_step_start:
            self.on_step_start(step, part)

        result = StepResult(
            step_id=step.id,
            desc=step.desc,
            status=StepStatus.RUNNING,
            started_at=datetime.now(),
        )

        page = await self.session.get_page()

        try:
            # Execute action
            if step.action:
                action_result = await self.action_executor.execute(page, step.action)
                if not action_result.success:
                    result.status = StepStatus.FAILED
                    result.error = action_result.error
                    logger.error(f"Action failed: {action_result.error}")

                # Handle login action (account switch)
                if action_result.data and action_result.data.get("account"):
                    account_key = action_result.data["account"]
                    await self.session.switch_account(account_key)

            # Verify expectations
            if step.expect and result.status != StepStatus.FAILED:
                assertions = await self.assertion_executor.verify(page, step.expect)
                result.assertions = assertions

                # Check if all assertions passed
                if not all(a.passed for a in assertions):
                    result.status = StepStatus.FAILED
                    failed = [a for a in assertions if not a.passed]
                    result.error = f"Assertions failed: {[a.message for a in failed]}"
                    logger.error(f"Assertions failed: {failed}")

            # Take screenshot if requested
            if step.has_screenshot and result.status != StepStatus.FAILED:
                screenshot_path = self.session.get_screenshot_path(
                    part, step.id, step.desc, step.screenshot_name
                )
                await page.screenshot(path=str(screenshot_path))
                result.screenshot = screenshot_path
                logger.info(f"Screenshot saved: {screenshot_path}")

            # Mark as passed if no errors
            if result.status == StepStatus.RUNNING:
                result.status = StepStatus.PASSED

        except Exception as e:
            logger.exception(f"Step {step.id} failed with exception")
            result.status = StepStatus.FAILED
            result.error = str(e)

        result.completed_at = datetime.now()
        result.duration_ms = int(
            (result.completed_at - result.started_at).total_seconds() * 1000
        )

        self.session.record_step_result(result)

        if self.on_step_complete:
            self.on_step_complete(step, result)

        return result

    async def run_single_step(self, step_id: str) -> Optional[StepResult]:
        """Run a single step by ID.

        Args:
            step_id: Step ID to run

        Returns:
            StepResult or None if step not found
        """
        scenario = self.session.scenario
        step = scenario.get_step(step_id)
        part = scenario.get_part_for_step(step_id)

        if not step or not part:
            logger.error(f"Step not found: {step_id}")
            return None

        try:
            await self.session.setup()

            # Switch account if needed
            if part.account:
                await self.session.switch_account(part.account)

            self.session.start_part(part)
            result = await self.run_step(step, part)
            self.session.finish_part()
            self.session.finish_scenario()
            self.session.save_results()

            return result

        finally:
            await self.session.teardown()


async def run_scenario(
    scenario_path: Path,
    output_dir: Optional[Path] = None,
    base_url: Optional[str] = None,
    stop_on_error: bool = False,
    part_filter: Optional[int] = None,
) -> ScenarioSession:
    """Run a scenario from YAML file.

    Args:
        scenario_path: Path to scenario YAML
        output_dir: Output directory for screenshots
        base_url: Base URL for the application
        stop_on_error: Stop on first error
        part_filter: Run only specific part

    Returns:
        ScenarioSession with results
    """
    from shayde.config.loader import load_config
    from shayde.core.browser import BrowserManager
    from shayde.core.scenario.parser import ScenarioParser
    from shayde.docker.manager import DockerManager

    # Load and parse scenario
    parser = ScenarioParser()
    scenario = parser.parse(scenario_path)

    # Filter parts if requested
    if part_filter is not None:
        scenario.steps = [p for p in scenario.steps if p.part == part_filter]

    # Load config and determine base URL
    config = load_config()
    if not base_url:
        base_url = config.app.base_url

    # Determine output directory
    if not output_dir:
        if config.output.scenario_directory:
            output_dir = Path.cwd() / config.output.scenario_directory
        else:
            output_dir = Path.cwd() / config.output.directory / "e2e"

    session_output_dir = ScenarioSession.create_output_dir(output_dir, scenario.meta.id)

    # Start Docker and connect to browser
    docker_manager = DockerManager(config)
    if config.docker.auto_start:
        docker_manager.start()

    ws_url = docker_manager.get_ws_url()
    browser_manager = BrowserManager(ws_url)

    try:
        browser = await browser_manager.connect()

        # Create session
        session = ScenarioSession(
            scenario=scenario,
            output_dir=session_output_dir,
            browser=browser,
            base_url=base_url,
        )

        # Create runner with progress callbacks
        def on_step_start(step: Step, part: Part):
            print(f"  [{step.id}] {step.desc}...", end=" ", flush=True)

        def on_step_complete(step: Step, result: StepResult):
            if result.status == StepStatus.PASSED:
                icon = "✓" if not result.screenshot else "📸"
                print(f"{icon}")
            else:
                print(f"✗ {result.error or ''}")

        def on_part_start(part: Part):
            account_info = f" ({part.account})" if part.account else ""
            print(f"\nPart {part.part}: {part.title}{account_info}")

        runner = ScenarioRunner(
            session=session,
            on_step_start=on_step_start,
            on_step_complete=on_step_complete,
            on_part_start=on_part_start,
        )

        # Run scenario
        await runner.run_all(stop_on_error=stop_on_error)

        return session

    finally:
        await browser_manager.disconnect()
        if config.docker.auto_stop:
            docker_manager.stop()


async def run_single_step(
    scenario_path: Path,
    step_id: str,
    output_dir: Optional[Path] = None,
    base_url: Optional[str] = None,
) -> Optional[StepResult]:
    """Run a single step from YAML file.

    Args:
        scenario_path: Path to scenario YAML
        step_id: Step ID to run
        output_dir: Output directory for screenshots
        base_url: Base URL for the application

    Returns:
        StepResult or None if step not found
    """
    from shayde.config.loader import load_config
    from shayde.core.browser import BrowserManager
    from shayde.core.scenario.parser import ScenarioParser
    from shayde.docker.manager import DockerManager

    # Load and parse scenario
    parser = ScenarioParser()
    scenario = parser.parse(scenario_path)

    # Check if step exists
    step = scenario.get_step(step_id)
    part = scenario.get_part_for_step(step_id)
    if not step or not part:
        return None

    # Load config and determine base URL
    config = load_config()
    if not base_url:
        base_url = config.app.base_url

    # Determine output directory
    if not output_dir:
        if config.output.scenario_directory:
            output_dir = Path.cwd() / config.output.scenario_directory
        else:
            output_dir = Path.cwd() / config.output.directory / "e2e"

    session_output_dir = ScenarioSession.create_output_dir(output_dir, scenario.meta.id)

    # Start Docker and connect to browser
    docker_manager = DockerManager(config)
    if config.docker.auto_start:
        docker_manager.start()

    ws_url = docker_manager.get_ws_url()
    browser_manager = BrowserManager(ws_url)

    try:
        browser = await browser_manager.connect()

        # Create session
        session = ScenarioSession(
            scenario=scenario,
            output_dir=session_output_dir,
            browser=browser,
            base_url=base_url,
        )

        # Create runner
        runner = ScenarioRunner(session=session)

        # Run single step
        return await runner.run_single_step(step_id)

    finally:
        await browser_manager.disconnect()
        if config.docker.auto_stop:
            docker_manager.stop()
