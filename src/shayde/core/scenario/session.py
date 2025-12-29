"""Scenario session management."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

from shayde.core.scenario.models import (
    PartResult,
    ScenarioResult,
    StepResult,
    StepStatus,
)
from shayde.core.scenario.parser import Account, Part, Scenario, sanitize_filename
from shayde.core.routes import create_route_handler
from shayde.config.loader import load_config
from shayde.proxy.manager import ProxyManager
from shayde.docker.manager import PLATFORM_CSS

logger = logging.getLogger(__name__)


class ScenarioSession:
    """Manages a scenario execution session.

    Handles:
    - Browser context and page management
    - Account switching (login/logout)
    - Screenshot path generation
    - Result recording
    """

    def __init__(
        self,
        scenario: Scenario,
        output_dir: Path,
        browser: "Browser",
        base_url: Optional[str] = None,
        record_video: bool = False,
    ):
        self.scenario = scenario
        self.output_dir = output_dir
        self.browser = browser
        self.base_url = base_url
        self.record_video = record_video

        self.session_id = str(uuid.uuid4())[:8]
        self.current_account: Optional[str] = None
        self.context: Optional["BrowserContext"] = None
        self.page: Optional["Page"] = None

        # Results tracking
        self.result = ScenarioResult(
            scenario_id=scenario.meta.id,
            title=scenario.meta.title,
            status=StepStatus.PENDING,
            output_dir=output_dir,
        )
        self._current_part_result: Optional[PartResult] = None
        self._proxy_manager: Optional[ProxyManager] = None
        self._platform_css: Optional[str] = None
        self._video_dir: Optional[Path] = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def setup(self) -> None:
        """Initialize browser context and page."""
        logger.info(f"Setting up session {self.session_id}")

        # Load config and start proxy if enabled
        config = load_config()
        if config.proxy.enabled:
            self._proxy_manager = ProxyManager(config)
            await self._proxy_manager.start()
            logger.info(f"Proxy started on port {config.proxy.port}")

        # Build context options
        context_options = {}

        # Video recording (use temp dir in container, save via save_as later)
        if self.record_video:
            context_options["record_video_dir"] = "/tmp/shayde-videos"
            context_options["record_video_size"] = {"width": 1920, "height": 1080}
            logger.info("Video recording enabled")

        self.context = await self.browser.new_context(**context_options)
        self.page = await self.context.new_page()

        # Set up route interception for Docker → host redirection
        route_handler = create_route_handler(config)
        await self.page.route("**/*", route_handler)

        # Store platform CSS for injection after navigation
        self._platform_css = PLATFORM_CSS.get(config.fonts.platform, PLATFORM_CSS["neutral"])
        logger.info(f"Platform font: {config.fonts.platform}")

        self.result.started_at = datetime.now()

    async def teardown(self) -> None:
        """Clean up browser context and proxy."""
        import asyncio

        logger.info(f"Tearing down session {self.session_id}")

        # Get video object reference before closing context
        video = None
        video_name = None
        video_path = None
        if self.page and self.record_video:
            video = self.page.video
            video_name = f"{self.scenario.meta.id}.webm"
            video_path = self.output_dir / video_name

        # Close context first (this finalizes the video file)
        if self.context:
            await self.context.close()
            self.context = None
            self.page = None

        # Save video after context is closed (save_as waits for page close)
        if video and video_path:
            try:
                logger.info("Saving video...")
                await asyncio.wait_for(
                    video.save_as(str(video_path)),
                    timeout=60.0
                )
                self.result.video_path = video_path
                logger.info(f"Video saved: {video_path}")
            except asyncio.TimeoutError:
                logger.warning("Video save timed out after 60s")
            except Exception as e:
                logger.warning(f"Failed to save video: {e}")

        if self._proxy_manager:
            await self._proxy_manager.stop()
            self._proxy_manager = None
        self.result.completed_at = datetime.now()

    async def switch_account(self, account_key: Optional[str]) -> bool:
        """Switch to a different account.

        Args:
            account_key: Account key from scenario.accounts, or None for logout

        Returns:
            True if switch was successful
        """
        if account_key == self.current_account:
            logger.debug(f"Already logged in as {account_key}")
            return True

        # Logout first if currently logged in
        if self.current_account:
            logger.info(f"Logging out from {self.current_account}")
            if self.context:
                await self.context.clear_cookies()
            self.current_account = None

        if account_key is None:
            return True

        # Login to new account
        account = self.scenario.accounts.get(account_key)
        if not account:
            logger.error(f"Unknown account: {account_key}")
            return False

        logger.info(f"Logging in as {account_key} ({account.email})")

        try:
            # Navigate to login page
            login_url = f"{self.base_url}/login" if self.base_url else "/login"
            await self.page.goto(login_url, wait_until="networkidle")

            # Fill login form
            await self.page.fill("[name=email], #email, input[type=email]", account.email)
            await self.page.fill("[name=password], #password, input[type=password]", account.password)

            # Submit
            await self.page.click("button[type=submit], input[type=submit]")

            # Wait for navigation (either dashboard or error)
            await self.page.wait_for_load_state("networkidle")

            # Check if login was successful (not on login page anymore)
            if "/login" not in self.page.url:
                self.current_account = account_key
                logger.info(f"Login successful: {account.email}")
                return True
            else:
                logger.error(f"Login failed for {account.email}")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    async def get_page(self) -> "Page":
        """Get current page, ensuring session is set up."""
        if not self.page:
            await self.setup()
        return self.page

    async def inject_platform_css(self) -> None:
        """Inject platform-specific font CSS into the current page.

        Call this after page navigation to apply Mac/Windows fonts.
        """
        if self._platform_css and self.page:
            await self.page.add_style_tag(content=self._platform_css)

    def get_screenshot_path(
        self,
        part: Part,
        step_id: str,
        step_desc: str,
        custom_name: Optional[str] = None,
    ) -> Path:
        """Generate screenshot path for a step.

        Args:
            part: Part containing the step
            step_id: Step ID
            step_desc: Step description
            custom_name: Optional custom screenshot name

        Returns:
            Path to screenshot file
        """
        # Part directory: part-01_未認証アクセス制御
        part_dir_name = f"part-{part.part:02d}_{sanitize_filename(part.title)}"
        part_dir = self.output_dir / part_dir_name
        part_dir.mkdir(parents=True, exist_ok=True)

        # Screenshot filename: step-1-1_ログインページに遷移.png
        if custom_name:
            filename = f"step-{step_id}_{sanitize_filename(custom_name)}.png"
        else:
            filename = f"step-{step_id}_{sanitize_filename(step_desc)}.png"

        return part_dir / filename

    def start_part(self, part: Part) -> None:
        """Start tracking a new part.

        Args:
            part: Part to start
        """
        self._current_part_result = PartResult(
            part=part.part,
            title=part.title,
            status=StepStatus.RUNNING,
        )
        self.result.parts.append(self._current_part_result)

    def record_step_result(self, result: StepResult) -> None:
        """Record a step result.

        Args:
            result: Step result to record
        """
        if self._current_part_result:
            self._current_part_result.steps.append(result)

            # Update part status
            if result.status == StepStatus.FAILED:
                self._current_part_result.status = StepStatus.FAILED
            elif result.status == StepStatus.PASSED:
                if self._current_part_result.status != StepStatus.FAILED:
                    self._current_part_result.status = StepStatus.PASSED

    def finish_part(self) -> None:
        """Finish current part."""
        if self._current_part_result:
            if self._current_part_result.status == StepStatus.RUNNING:
                self._current_part_result.status = StepStatus.PASSED
            self._current_part_result = None

    def finish_scenario(self) -> None:
        """Finish scenario and calculate final status."""
        self.result.completed_at = datetime.now()

        # Determine overall status
        has_failed = any(p.status == StepStatus.FAILED for p in self.result.parts)
        has_passed = any(p.status == StepStatus.PASSED for p in self.result.parts)

        if has_failed:
            self.result.status = StepStatus.FAILED
        elif has_passed:
            self.result.status = StepStatus.PASSED
        else:
            self.result.status = StepStatus.SKIPPED

    def save_results(self) -> Path:
        """Save results to JSON file.

        Returns:
            Path to results file
        """
        results_path = self.output_dir / "results.json"

        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(self.result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Results saved to {results_path}")
        return results_path

    @classmethod
    def create_output_dir(
        cls,
        base_dir: Path,
        scenario_id: str,
        title: Optional[str] = None,
    ) -> Path:
        """Create output directory for scenario.

        Args:
            base_dir: Base output directory
            scenario_id: Scenario ID
            title: Scenario title (optional, for readable directory name)

        Returns:
            Path to output directory
        """
        import shutil

        # Build directory name: {id}_{title} or just {id}
        if title:
            safe_title = sanitize_filename(title)
            dir_name = f"{scenario_id}_{safe_title}"
        else:
            dir_name = scenario_id

        output_dir = base_dir / dir_name

        # Remove existing directory (overwrite mode)
        if output_dir.exists():
            shutil.rmtree(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir


def generate_session_id() -> str:
    """Generate a short session ID."""
    return str(uuid.uuid4())[:8]
