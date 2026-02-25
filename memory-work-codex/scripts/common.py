#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / '.memory-work' / 'config.json'
LOCK_PATH = ROOT / '.memory-work' / '.lock'


@dataclass
class Cfg:
    language_preference: str
    timezone: str
    deep_sync_day_start: int
    memory_decay_weeks: int
    graduation_threshold: int
    focus_zone_path: str
    week_file: str
    memory_log_file: str
    iteration_log_file: str


def load_cfg() -> Cfg:
    data = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    return Cfg(**data)


def iso_today() -> str:
    return dt.date.today().isoformat()


def iso_now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def iso_week(d: dt.date | None = None) -> str:
    d = d or dt.date.today()
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def week_range(d: dt.date | None = None) -> str:
    d = d or dt.date.today()
    monday = d - dt.timedelta(days=d.weekday())
    sunday = monday + dt.timedelta(days=6)
    return f"{monday.isoformat()} ~ {sunday.isoformat()}"


def focus_dir(cfg: Cfg) -> Path:
    return ROOT / cfg.focus_zone_path


def week_file_path(cfg: Cfg) -> Path:
    return focus_dir(cfg) / cfg.week_file


def memory_log_path(cfg: Cfg) -> Path:
    return focus_dir(cfg) / cfg.memory_log_file


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_line(path: Path, line: str) -> None:
    ensure_parent(path)
    with path.open('a', encoding='utf-8') as f:
        f.write(line.rstrip('\n') + '\n')


def log_event(cfg: Cfg, event_type: str, summary: str) -> None:
    append_line(memory_log_path(cfg), f"{iso_today()} | {event_type} | {summary}")


@contextlib.contextmanager
def repo_lock():
    ensure_parent(LOCK_PATH)
    with LOCK_PATH.open('w', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding='utf-8')


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text, encoding='utf-8')


def list_focus_files(cfg: Cfg) -> list[Path]:
    base = focus_dir(cfg)
    out: list[Path] = []
    ignored = {
        cfg.week_file,
        cfg.memory_log_file,
        cfg.iteration_log_file,
        '00.专注区_agent.md',
    }
    for p in sorted(base.rglob('*')):
        if p.is_dir():
            continue
        if '_归档' in p.parts or p.name.startswith('.'):
            continue
        if p.name in ignored:
            continue
        out.append(p)
    return out


def relative_to_root(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))
