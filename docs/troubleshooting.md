# Troubleshooting Guide

## CSS Not Loading in Scenario Execution

### Symptoms
- `shayde capture page` works correctly (CSS loads)
- `shayde scenario run` shows unstyled HTML (CSS not loaded)
- Screenshots show plain HTML without Tailwind/daisyUI styles

### Root Cause

ScenarioSession was missing **both** RouteInterceptor and ProxyManager.

#### How Asset Loading Works

```
[Docker Browser]
    ↓ requests http://0.0.0.0:5174/resources/css/app.css
    ↓
[RouteInterceptor]
    ↓ redirects to http://host.docker.internal:9999/...  (proxy port)
    ↓
[ProxyManager]
    ↓ listens on 0.0.0.0:9999, proxies to localhost:5174
    ↓
[Vite Dev Server]
    ↓ serves CSS/JS assets
```

**Key insight**: RouteInterceptor alone is NOT enough!

When `proxy.enabled=true`, RouteInterceptor redirects Vite port (5174) to proxy port (9999). But if ProxyManager isn't running, nothing listens on port 9999.

### Diagnosis

Enable INFO logging in `routes.py` to see redirections:

```
Redirecting: http://0.0.0.0:5174/resources/css/app.css -> http://host.docker.internal:9999/resources/css/app.css
```

If you see redirections but CSS still fails, ProxyManager is not running.

### Solution

ScenarioSession needs both RouteInterceptor AND ProxyManager:

```python
from shayde.proxy.manager import ProxyManager
from shayde.core.routes import create_route_handler
from shayde.config.loader import load_config

class ScenarioSession:
    def __init__(self, ...):
        ...
        self._proxy_manager: Optional[ProxyManager] = None

    async def setup(self) -> None:
        # 1. Start proxy if enabled
        config = load_config()
        if config.proxy.enabled:
            self._proxy_manager = ProxyManager(config)
            await self._proxy_manager.start()

        # 2. Create browser context and page
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

        # 3. Set up route interception
        route_handler = create_route_handler(config)
        await self.page.route("**/*", route_handler)

    async def teardown(self) -> None:
        if self.context:
            await self.context.close()
        if self._proxy_manager:
            await self._proxy_manager.stop()
```

### Component Comparison

| Component | RouteInterceptor | ProxyManager | CSS Loads |
|-----------|------------------|--------------|-----------|
| CaptureSession | Yes | Yes | Yes |
| ScenarioSession (before) | No | No | No |
| ScenarioSession (after) | Yes | Yes | Yes |

### Files Modified
- `src/shayde/core/scenario/session.py` - Added ProxyManager and RouteInterceptor

### Related
- `src/shayde/core/routes.py` - RouteInterceptor implementation
- `src/shayde/proxy/manager.py` - ProxyManager implementation
- `src/shayde/core/capture.py` - Working reference implementation

---

## Video Recording with Remote Browser

### Symptoms
- `video.path()` throws error: "Path is not available when using browserType.connect()"
- `video.save_as()` hangs or times out

### Root Cause

When using `browserType.connect()` for remote browser (Docker Playwright):

1. **`video.path()` unavailable**: Documented Playwright limitation for remote connections
2. **`save_as()` deadlock**: This method waits for page close. If called before `context.close()`, it blocks forever

### Correct Implementation

```python
async def teardown(self) -> None:
    # 1. Get video reference BEFORE closing context
    video = self.page.video if self.page else None
    video_path = self.output_dir / "recording.webm"

    # 2. Close context FIRST (this finalizes the video file)
    if self.context:
        await self.context.close()

    # 3. Save video AFTER context is closed
    if video:
        await video.save_as(str(video_path))
```

### Key Points

| Aspect | Incorrect | Correct |
|--------|-----------|---------|
| Order | save_as() → close() | close() → save_as() |
| Path method | video.path() | video.save_as() |
| record_video_dir | Host path | Container path (`/tmp/...`) |

### Context Setup

```python
# Use container-internal path (not host path)
context_options = {
    "record_video_dir": "/tmp/shayde-videos",  # Inside Docker
    "record_video_size": {"width": 1920, "height": 1080}
}
context = await browser.new_context(**context_options)
```

### Reference
- [Playwright Video API](https://playwright.dev/python/docs/api/class-video)
- `video.save_as()`: Safe to call after page closed, waits for video completion
