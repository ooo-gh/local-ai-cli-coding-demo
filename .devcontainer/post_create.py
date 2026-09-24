#!/usr/bin/env python3
"""Reconcile the container's persistent Claude config with the baked-in seed.

~/.claude is a named Docker volume so the Claude Code login survives between
demo runs. The Semgrep Guardian plugin is baked into the image at
/opt/claude-seed -- rebuilding the image should deliver a newer plugin even to a
volume that already exists. This script runs on every container start and:

  - copies plugin state out of the seed when it is missing or stale
  - enables the Guardian plugin at user scope
  - sets the startup permission mode to bypassPermissions
  - pre-answers the first-run dialogs (theme, TUI style, permission-mode
    confirmation, workspace trust) so a fresh volume comes up at the input box
  - fixes ownership on the mounted volume
  - writes a tmux config with a large scrollback for post-demo review

It never touches .credentials.json: the OAuth login is the one first-run step
left, because it needs a real credential rather than a flag. Safe to re-run.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SEED = Path(os.environ.get("CLAUDE_SEED_DIR", "/opt/claude-seed"))
CONFIG = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
# Manifest key for the plugin, "<name>@<marketplace>". The Dockerfile installs
# from Semgrep's own marketplace (github.com/semgrep/guardian), so the key is
# semgrep@semgrep-marketplace -- matching what MDM rolls out to real machines.
GUARDIAN_PLUGIN = "semgrep@semgrep-marketplace"


def log(msg):
    print(f"[post_create] {msg}", file=sys.stderr)


def fix_ownership():
    """Last-resort check that the named volume is ours to write.

    The image pre-creates /home/vscode/.claude as vscode, so Docker initialises a
    fresh volume vscode-owned and there is normally nothing to do here. The
    container runs with --cap-drop=ALL and no-new-privileges, so if a volume does
    somehow come up root-owned there is no way to repair it from inside -- say so
    plainly instead of leaving Claude Code to fail on an unwritable config.

    Deliberately limited to CONFIG, the volume this container owns. ~/.semgrep is
    a bind mount of the presenter's real credential directory on the host -- we
    read it, we do not chown it. (Colima's virtiofs remaps ownership anyway, so a
    chown there would be both risky and pointless.)
    """
    uid, gid = os.getuid(), os.getgid()
    if not CONFIG.exists() or CONFIG.stat().st_uid == uid:
        return
    try:
        os.chown(CONFIG, uid, gid)
        log(f"fixed ownership: {CONFIG}")
    except OSError as e:
        log(f"ERROR: {CONFIG} is owned by uid {CONFIG.stat().st_uid}, not {uid}, "
            f"and cannot be chowned ({e}).")
        log("ERROR: Claude Code will not be able to write its config. Recreate "
            "the volume:  docker volume rm taskboard-demo-claude")


def sync_from_seed():
    """Copy plugin state out of the image seed into the volume.

    Only the plugin cache is authoritative in the image. Anything the user
    established inside the volume (credentials, history, sessions) is untouched.
    """
    if not SEED.is_dir():
        log(f"warning: no seed at {SEED}; the Guardian plugin may be missing")
        return

    CONFIG.mkdir(parents=True, exist_ok=True)

    seed_plugins = SEED / "plugins"
    if not seed_plugins.is_dir():
        log("warning: seed has no plugins/ directory")
        return

    dest_plugins = CONFIG / "plugins"

    # Skip the copy when the volume already carries the version the image ships.
    # This is the common path -- the container is recreated on every launch, so
    # this runs constantly and must be cheap and side-effect free.
    seed_version = _guardian_version(seed_plugins)
    dest_version = _guardian_version(dest_plugins)
    if seed_version is not None and seed_version == dest_version:
        log(f"plugins already at seed version {seed_version}")
        return

    # Replace outright rather than merge. copytree(dirs_exist_ok=True) cannot
    # overwrite the marketplace clone's git pack files -- git writes those mode
    # 0444, so opening them for write fails with EACCES. Removing first sidesteps
    # that (unlinking a read-only file only needs a writable parent) and means a
    # rebuilt image cleanly replaces a stale plugin version. The seed is the
    # authority for plugins/; anything hand-installed in the volume goes with it.
    if dest_plugins.exists():
        shutil.rmtree(dest_plugins)
    shutil.copytree(seed_plugins, dest_plugins)
    log(f"synced plugins from seed -> {dest_plugins}")

    # The install was recorded at build time against CLAUDE_CONFIG_DIR=/opt/
    # claude-seed, so installPath still points into the seed. Repoint it at the
    # copy in the volume, so ~/.claude is self-contained and the plugin does not
    # quietly depend on the seed still being there.
    manifest = dest_plugins / "installed_plugins.json"
    data = _load_json(manifest)
    rewritten = 0
    for entries in data.get("plugins", {}).values():
        if isinstance(entries, dict):
            entries = [entries]
        for entry in entries:
            path = entry.get("installPath", "")
            if path.startswith(str(SEED)):
                entry["installPath"] = str(CONFIG) + path[len(str(SEED)):]
                rewritten += 1
    if rewritten:
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        log(f"repointed {rewritten} plugin installPath(s) at {CONFIG}")


def _load_json(path):
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _claude_version():
    """Version string reported by the installed CLI, or None.

    Read at runtime rather than baked into the image: Claude Code replays
    onboarding whenever lastOnboardingVersion is older than the running CLI,
    regardless of hasCompletedOnboarding.
    """
    try:
        out = subprocess.run(
            ["claude", "--version"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        log(f"warning: could not read the claude version: {e}")
        return None
    # "2.1.238 (Claude Code)" -> "2.1.238"
    return out.split()[0] if out else None


def _guardian_version(plugins_dir):
    """Version of the Guardian plugin recorded in a plugins/ dir, or None."""
    data = _load_json(plugins_dir / "installed_plugins.json")
    entries = data.get("plugins", {}).get(GUARDIAN_PLUGIN)
    if isinstance(entries, dict):
        entries = [entries]
    if not entries:
        return None
    return entries[0].get("version")


def configure_settings():
    """Enable Guardian, pin the permission mode, pre-answer the first-run pickers.

    The permission mode is set explicitly so a bare `claude` started inside the
    container behaves like the one demo.sh launches with --permission-mode.
    """
    path = CONFIG / "settings.json"
    settings = _load_json(path)

    seed_settings = _load_json(SEED / "settings.json")
    if "extraKnownMarketplaces" in seed_settings:
        merged = dict(seed_settings["extraKnownMarketplaces"])
        merged.update(settings.get("extraKnownMarketplaces", {}))
        settings["extraKnownMarketplaces"] = merged

    settings.setdefault("enabledPlugins", {})[GUARDIAN_PLUGIN] = True
    settings.setdefault("permissions", {})["defaultMode"] = "bypassPermissions"

    # bypassPermissions above is what raises the "this bypasses all permission
    # checks" confirmation, so the flag that skips it belongs with it. Those two
    # are hard-set, since the mode they cover is set here too. theme and tui only
    # fill in a default: change the theme mid-demo and Claude Code writes it back
    # to this file, where setdefault leaves the choice alone on the next start.
    settings["skipDangerousModePermissionPrompt"] = True
    settings["skipAutoPermissionPrompt"] = True
    settings.setdefault("theme", "auto")
    settings.setdefault("tui", "fullscreen")

    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    log(
        f"settings written: {path} (Guardian enabled, "
        "defaultMode=bypassPermissions, first-run pickers pre-answered)"
    )


def write_tmux_conf():
    """Large scrollback so the presenter can scroll back over the findings."""
    conf = Path.home() / ".tmux.conf"
    conf.write_text(
        "\n".join(
            [
                "set-option -g history-limit 200000",
                "set -g mouse on",
                "setw -g mode-keys vi",
                "set -sg escape-time 10",
                # Claude Code prints a "tmux focus-events off" advisory into the
                # session without this -- a warning line on the projector, and it
                # cannot track focus to redraw when the presenter switches away.
                "set -g focus-events on",
                'set -g default-terminal "tmux-256color"',
                'set -ag terminal-overrides ",xterm-256color:RGB"',
                'set -as terminal-features ",xterm*:RGB"',
                'set -as terminal-features ",xterm-ghostty:RGB"',
                # No status bar: the audience should see Claude Code, not tmux.
                "set -g status off",
                "",
            ]
        ),
        encoding="utf-8",
    )
    log(f"tmux configured: {conf}")


def report_guardian_credentials():
    """Non-fatal heads-up if the bind-mounted OIDC token is missing or unreadable.

    Reads rather than repairs: this file is the host's, and a permission problem
    here is something to report, not something to chown away.
    """
    guardian = Path.home() / ".semgrep" / "guardian.yml"
    if guardian.is_file() and guardian.stat().st_size > 0:
        try:
            with guardian.open("rb") as fh:
                fh.read(1)
            log("Semgrep Guardian credentials present and readable")
        except OSError as e:
            log(f"warning: ~/.semgrep/guardian.yml is not readable as this user: {e}")
    else:
        log(
            "warning: ~/.semgrep/guardian.yml missing or empty -- ask "
            '"log in to semgrep using oauth" inside the session'
        )


def seed_onboarding_flags():
    """Pre-answer the first-run dialogs so a fresh volume boots straight to the
    input box. Only the OAuth login is left -- it needs a real credential."""
    path = CONFIG / ".claude.json"
    data = _load_json(path)
    data["hasCompletedOnboarding"] = True
    data["lastOnboardingVersion"] = _claude_version() or data.get(
        "lastOnboardingVersion", "0.0.0")
    data.setdefault("projects", {}).setdefault("/workspace", {})[
        "hasTrustDialogAccepted"] = True
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    log(f"onboarding flags seeded: {path} (trust pre-accepted for /workspace)")


def main():
    fix_ownership()
    sync_from_seed()
    configure_settings()
    write_tmux_conf()
    report_guardian_credentials()
    seed_onboarding_flags()
    log("ready")


if __name__ == "__main__":
    main()
