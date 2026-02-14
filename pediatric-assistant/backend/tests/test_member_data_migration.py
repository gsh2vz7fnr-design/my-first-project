import sqlite3
from pathlib import Path

from scripts.migrate_user_member_records import migrate_member_records


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE consultation_records (
            id TEXT PRIMARY KEY,
            member_id TEXT,
            summary TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE checkup_records (
            id TEXT PRIMARY KEY,
            member_id TEXT,
            summary TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE archived_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            member_id TEXT,
            summary TEXT
        )
        """
    )


def test_migration_dry_run_no_write(tmp_path: Path):
    db = tmp_path / "migration.db"
    conn = sqlite3.connect(str(db))
    _init_schema(conn)
    conn.execute("INSERT INTO consultation_records VALUES ('c1', 'user_1001', 'old')")
    conn.execute("INSERT INTO checkup_records VALUES ('k1', 'user_1001', 'old')")
    conn.execute("INSERT INTO archived_conversations (conversation_id, member_id, summary) VALUES ('conv1', 'user_1001', 'old')")
    conn.commit()
    conn.close()

    results = migrate_member_records(
        db_path=db,
        from_user_id="user_1001",
        to_member_id="member_abc",
        apply=False,
    )

    assert results["consultation_records"].matched == 1
    assert results["consultation_records"].updated == 0

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT member_id FROM consultation_records").fetchall()
    conn.close()
    assert rows[0][0] == "user_1001"


def test_migration_apply_updates_all_tables(tmp_path: Path):
    db = tmp_path / "migration_apply.db"
    conn = sqlite3.connect(str(db))
    _init_schema(conn)
    conn.execute("INSERT INTO consultation_records VALUES ('c1', 'user_1001', 'old')")
    conn.execute("INSERT INTO consultation_records VALUES ('c2', 'member_x', 'keep')")
    conn.execute("INSERT INTO checkup_records VALUES ('k1', 'user_1001', 'old')")
    conn.execute("INSERT INTO archived_conversations (conversation_id, member_id, summary) VALUES ('conv1', 'user_1001', 'old')")
    conn.commit()
    conn.close()

    results = migrate_member_records(
        db_path=db,
        from_user_id="user_1001",
        to_member_id="member_abc",
        apply=True,
    )

    assert results["consultation_records"].matched == 1
    assert results["consultation_records"].updated == 1
    assert results["checkup_records"].updated == 1
    assert results["archived_conversations"].updated == 1

    conn = sqlite3.connect(str(db))
    consult_ids = conn.execute("SELECT member_id FROM consultation_records ORDER BY id").fetchall()
    checkup_id = conn.execute("SELECT member_id FROM checkup_records").fetchone()
    archive_id = conn.execute("SELECT member_id FROM archived_conversations").fetchone()
    conn.close()

    assert consult_ids[0][0] == "member_abc"
    assert consult_ids[1][0] == "member_x"
    assert checkup_id[0] == "member_abc"
    assert archive_id[0] == "member_abc"
