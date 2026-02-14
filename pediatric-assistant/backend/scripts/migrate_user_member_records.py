#!/usr/bin/env python3
"""
迁移历史错误数据：将 member_id=user_xxx 的医疗记录迁移到真实 member_id。

默认覆盖表：
- consultation_records
- checkup_records
- archived_conversations
"""

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


TABLES: List[str] = [
    "consultation_records",
    "checkup_records",
    "archived_conversations",
]


@dataclass
class MigrationResult:
    table: str
    matched: int
    updated: int


def count_rows(conn: sqlite3.Connection, table: str, member_id: str) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE member_id = ?",
        (member_id,),
    ).fetchone()
    return int(row[0]) if row else 0


def migrate_table(
    conn: sqlite3.Connection,
    table: str,
    from_member_id: str,
    to_member_id: str,
    apply: bool,
) -> MigrationResult:
    matched = count_rows(conn, table, from_member_id)
    updated = 0
    if apply and matched > 0:
        cursor = conn.execute(
            f"UPDATE {table} SET member_id = ? WHERE member_id = ?",
            (to_member_id, from_member_id),
        )
        updated = cursor.rowcount or 0
    return MigrationResult(table=table, matched=matched, updated=updated)


def migrate_member_records(
    db_path: Path,
    from_user_id: str,
    to_member_id: str,
    apply: bool,
) -> Dict[str, MigrationResult]:
    conn = sqlite3.connect(str(db_path))
    try:
        results: Dict[str, MigrationResult] = {}
        for table in TABLES:
            # 表不存在时跳过
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                (table,),
            ).fetchone()
            if not exists:
                results[table] = MigrationResult(table=table, matched=0, updated=0)
                continue
            results[table] = migrate_table(conn, table, from_user_id, to_member_id, apply=apply)

        if apply:
            conn.commit()
        return results
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移历史 user_id 误写为 member_id 的记录")
    parser.add_argument("--from-user-id", required=True, help="旧错误 member_id，例如 user_1001")
    parser.add_argument("--to-member-id", required=True, help="目标真实 member_id")
    parser.add_argument("--dry-run", action="store_true", help="仅统计，不落库")
    parser.add_argument("--apply", action="store_true", help="执行迁移")
    parser.add_argument("--db-path", default=None, help="数据库路径")
    args = parser.parse_args()

    if args.dry_run and args.apply:
        print("不能同时使用 --dry-run 和 --apply")
        return 2
    if not args.dry_run and not args.apply:
        print("请指定 --dry-run 或 --apply")
        return 2

    if args.db_path:
        db_path = Path(args.db_path)
    else:
        db_path = Path(__file__).resolve().parents[1] / "app" / "data" / "pediatric_assistant.db"

    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return 1

    results = migrate_member_records(
        db_path=db_path,
        from_user_id=args.from_user_id,
        to_member_id=args.to_member_id,
        apply=args.apply,
    )

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] from={args.from_user_id} to={args.to_member_id}")
    for _, r in results.items():
        print(f"- {r.table}: matched={r.matched}, updated={r.updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
