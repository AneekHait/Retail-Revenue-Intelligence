"""Load and expose project configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else ROOT / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Resolve relative paths against project root
    for key in ("raw_path", "customers_path", "products_path", "processed_path", "rfm_path", "cohorts_path"):
        if key in cfg.get("data", {}):
            cfg["data"][key] = str(ROOT / cfg["data"][key])
    cfg["output"]["figures_dir"] = str(ROOT / cfg["output"]["figures_dir"])
    cfg["output"]["insights_path"] = str(ROOT / cfg["output"]["insights_path"])
    cfg["output"]["summary_path"] = str(ROOT / cfg["output"]["summary_path"])
    cfg["_root"] = str(ROOT)
    return cfg
