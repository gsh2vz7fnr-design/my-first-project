import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import memory_review  # noqa: E402
import sync_focus  # noqa: E402


class SyncFocusTests(unittest.TestCase):
    def test_mentioned_names_extracts_doc_and_path(self):
        text = """
## 本周文档
| 文档 | 状态 | 位置 | 备注 |
|---|---|---|---|
| 需求梳理.md | 进行中 | 00 专注区/需求梳理.md | 自动发现 |
"""
        refs = sync_focus.mentioned_names(text)
        self.assertIn("需求梳理.md", refs)
        self.assertIn("00 专注区/需求梳理.md", refs)

    def test_add_sync_section_is_upsert(self):
        base = "## 自动同步记录\n\n### 2026-01-01 深度回溯\n- 扫描文件数: 1\n"
        updated = sync_focus.add_sync_section(base, "2026-01-01 深度回溯", ["扫描文件数: 2"])
        self.assertEqual(updated.count("### 2026-01-01 深度回溯"), 1)
        self.assertIn("扫描文件数: 2", updated)

    def test_append_outputs_table_targets_week_outputs_section(self):
        text = """
## 其他表格
| 列1 | 列2 |
|---|---|
| a | b |

## 本周文档
| 文档 | 状态 | 位置 | 备注 |
|---|---|---|---|
"""
        out = sync_focus.append_outputs_table(text, ["00 专注区/需求梳理.md"])
        self.assertIn("| 需求梳理.md | 进行中 | 00 专注区/需求梳理.md | 自动发现 |", out)
        self.assertEqual(out.count("| 需求梳理.md | 进行中 | 00 专注区/需求梳理.md | 自动发现 |"), 1)

    def test_append_candidates_dedup_by_id(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cdir = root / ".memory-work"
            cdir.mkdir(parents=True)
            (cdir / "candidates.jsonl").write_text(
                json.dumps({"id": "auto-2026-02-25-需求梳理.md"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            p = root / "需求梳理.md"
            p.write_text("# 标题\n", encoding="utf-8")

            with patch.object(sync_focus, "ROOT", root), patch.object(
                sync_focus, "relative_to_root", lambda x: x.name
            ):
                wrote = sync_focus.append_candidates([p], "2026-02-25")

            self.assertEqual(wrote, 0)


class MemoryReviewTests(unittest.TestCase):
    def test_hint_quality_filter(self):
        self.assertTrue(memory_review.is_high_quality_hint("用户每次会先口述再结构化"))
        self.assertFalse(memory_review.is_high_quality_hint("示例：用户习惯"))
        self.assertFalse(memory_review.is_high_quality_hint("偏好"))

    def test_load_candidates_dedup_hint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            week = root / "00 专注区" / "_本周.md"
            week.parent.mkdir(parents=True, exist_ok=True)
            week.write_text("用户每次先口述再结构化\n", encoding="utf-8")

            cand = root / ".memory-work" / "candidates.jsonl"
            cand.parent.mkdir(parents=True, exist_ok=True)
            cand.write_text(
                "\n".join(
                    [
                        json.dumps({"id": "a1", "hint": "用户每次先口述再结构化", "type": "dynamic"}, ensure_ascii=False),
                        json.dumps({"id": "a2", "hint": "用户 每次 先口述再结构化", "type": "dynamic"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.object(memory_review, "ROOT", root), patch.object(memory_review, "CAND_PATH", cand):
                items = memory_review.load_candidates(from_log=True)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["id"], "a1")

    def test_write_entries_returns_inserted_count(self):
        with tempfile.TemporaryDirectory() as td:
            mem = Path(td) / "MEMORY.md"
            mem.write_text(
                "# MEMORY.md\n\n## 动态记忆条目\n### [dup] 旧条目\n- type: dynamic\n\n## 程序记忆条目\n",
                encoding="utf-8",
            )
            with patch.object(memory_review, "MEMORY_PATH", mem):
                inserted = memory_review.write_entries(
                    [
                        {"id": "dup", "hint": "重复", "type": "dynamic", "date": "2026-02-25", "source": "x"},
                        {"id": "new1", "hint": "新增", "type": "dynamic", "date": "2026-02-25", "source": "x"},
                    ]
                )
            self.assertEqual(inserted, 1)
            final = mem.read_text(encoding="utf-8")
            self.assertIn("[new1]", final)


class WeekArchiveTests(unittest.TestCase):
    def test_invalid_week_argument(self):
        root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            ["python3", str(root / "scripts" / "week_archive.py"), "--week", "2026/09"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("week 参数格式错误", proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
