"""Configuration schema for Shayde using Pydantic."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Platform types for font simulation
PlatformType = Literal["neutral", "mac", "windows"]


class ViewportConfig(BaseModel):
    """Viewport configuration."""

    width: int = 1920
    height: int = 1080
    device_scale_factor: float = 1.0


class FontConfig(BaseModel):
    """Font configuration for platform simulation."""

    platform: PlatformType = "mac"
    custom_fonts_dir: Optional[str] = None  # Mount additional fonts
    css_override: Optional[str] = None  # Custom CSS for font-family


class AppConfig(BaseModel):
    """Application URL configuration."""

    base_url: Optional[str] = None
    env_file: str = ".env"
    env_var: str = "APP_URL"


class ProxyConfig(BaseModel):
    """Dev server proxy configuration."""

    enabled: bool = True
    port: int = 9999
    vite_port: Optional[int] = None  # Auto-detect if None
    websocket: bool = True


class DockerConfig(BaseModel):
    """Docker container configuration."""

    playwright_version: str = "1.48.0"
    container_name: str = "shayde-playwright"
    ws_port: int = 3000
    auto_start: bool = True
    auto_stop: bool = False
    use_custom_image: bool = False  # Set True after running: shayde docker build
    image_name: str = "shayde-playwright"  # Custom image name


class OutputConfig(BaseModel):
    """Screenshot output configuration."""

    directory: str = "storage/screenshots"
    scenario_directory: Optional[str] = None  # Scenario output dir (defaults to {directory}/e2e)
    filename_pattern: str = "{name}_{date}_{time}.png"
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H%M%S"


class CaptureConfig(BaseModel):
    """Default capture settings."""

    default_viewport: str = "desktop"
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "networkidle"
    wait_after: int = 0
    full_page: bool = False
    quality: Optional[int] = None


class VideoConfig(BaseModel):
    """Video recording configuration for scenarios."""

    enabled: bool = False
    size: Optional[Dict[str, int]] = None  # {"width": 1920, "height": 1080}


class RegressionConfig(BaseModel):
    """Visual regression settings."""

    baseline_dir: str = "storage/baselines"
    diff_dir: str = "storage/diffs"
    threshold: float = 0.1
    max_diff_pixels: Optional[int] = None
    ignore_antialiasing: bool = True
    update_snapshots: Literal["none", "missing", "all"] = "none"


class TestConfig(BaseModel):
    """E2E test configuration for Playwright."""

    directory: str = "tests/e2e"
    before: Optional[str] = None  # Command to run before tests (e.g., "php artisan migrate:fresh --seed")
    config_file: Optional[str] = None  # Playwright config file path
    timeout: int = 30000  # Test timeout in ms
    retries: int = 0  # Number of retries on failure
    workers: int = 1  # Number of parallel workers


class ShaydeConfig(BaseModel):
    """Root configuration model for Shayde."""

    version: int = 1
    app: AppConfig = Field(default_factory=AppConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    fonts: FontConfig = Field(default_factory=FontConfig)
    viewports: Dict[str, ViewportConfig] = Field(
        default_factory=lambda: {
            "mobile": ViewportConfig(width=375, height=812, device_scale_factor=2),
            "tablet": ViewportConfig(width=768, height=1024),
            "desktop": ViewportConfig(width=1920, height=1080),
        }
    )
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    regression: RegressionConfig = Field(default_factory=RegressionConfig)
    test: TestConfig = Field(default_factory=TestConfig)

    @classmethod
    def get_default(cls) -> "ShaydeConfig":
        """Return default configuration."""
        return cls()
