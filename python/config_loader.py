"""Load + validate pipeline_config.yaml and resolve its paths against the repo root.

The repo root is derived from this file's location (python/ sits one level under the
root), so nothing machine-specific is stored and the repo stays portable.
"""

from pathlib import Path

import yaml

_REQUIRED_SECTIONS = ("speakers", "tiers", "paths", "analysis", "validation")
_RANGE_KEYS = (
    "vot_range_ms", "closure_dur_range_ms", "burst_dur_range_ms", "cog_range_hz",
    "f1_range_hz", "f2_range_hz", "f3_range_hz",
)


def find_repo_root():
    """Repo root = parent of the python/ package directory."""
    return Path(__file__).resolve().parent.parent


class Config:
    """Thin typed wrapper over the YAML with repo-root-resolved paths."""

    def __init__(self, raw, repo_root):
        self.raw = raw
        self.repo_root = Path(repo_root)
        self.speakers = raw.get("speakers", {})
        self.tiers = raw.get("tiers", {})
        self.analysis = raw.get("analysis", {})
        self.validation = raw.get("validation", {})
        self.spectrogram = raw.get("spectrogram", {})
        self._paths = raw.get("paths", {})

    def path(self, key):
        """Absolute Path for a `paths:` entry, resolved against the repo root."""
        rel = self._paths.get(key)
        if rel is None:
            raise KeyError(f"paths.{key} is not defined in the config")
        return (self.repo_root / rel).resolve()

    def speaker_ids(self):
        return list(self.speakers.keys())

    def speaker(self, sid):
        if sid not in self.speakers:
            raise KeyError(f"speaker '{sid}' is not defined in the config")
        return self.speakers[sid]

    # per-speaker manifest lives under {words}/{speaker}/words_manifest.csv
    def manifest_path(self, sid):
        return self.path("words") / sid / "words_manifest.csv"

    def extraction_path(self, sid):
        return self.path("extraction") / f"measurements_{sid}.csv"


def load_config(path=None):
    repo_root = find_repo_root()
    if path is None:
        path = repo_root / "config" / "pipeline_config.yaml"
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    _validate_config(raw, path)
    return Config(raw, repo_root)


def _validate_config(raw, path):
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top level is not a mapping")
    missing = [k for k in _REQUIRED_SECTIONS if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing config section(s): {missing}")
    if not raw["speakers"]:
        raise ValueError(f"{path}: no speakers defined")
    v = raw["validation"]
    for key in _RANGE_KEYS:
        if key in v:
            pair = v[key]
            if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
                raise ValueError(f"{path}: validation.{key} must be a [lo, hi] pair")
            lo, hi = pair
            if lo >= hi:
                raise ValueError(f"{path}: validation.{key} has lo >= hi: {pair}")
