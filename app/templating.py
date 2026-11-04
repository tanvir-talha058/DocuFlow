import os

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def _static_version() -> str:
    """Cache-busting token for static assets, derived from the newest mtime
    under app/static. Browsers that cached an old style.css/app.js from a
    prior run will fetch fresh copies instead of silently running stale JS."""
    static_dir = "app/static"
    newest = 0.0
    for root, _dirs, files in os.walk(static_dir):
        for name in files:
            newest = max(newest, os.path.getmtime(os.path.join(root, name)))
    return str(int(newest))


templates.env.globals["static_version"] = _static_version()

# A small, on-brand palette (not the full accent set — stamp colors stay
# reserved for verdicts) so avatars read as "part of the system" rather than
# random hues.
_AVATAR_PALETTE = ["#2b3a66", "#6b4f8a", "#1f6f6b", "#8a5a2e", "#4a5a7a", "#7a3b4a"]


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _avatar_color(name: str) -> str:
    index = sum(ord(c) for c in (name or "")) % len(_AVATAR_PALETTE)
    return _AVATAR_PALETTE[index]


templates.env.filters["initials"] = _initials
templates.env.filters["avatar_color"] = _avatar_color
