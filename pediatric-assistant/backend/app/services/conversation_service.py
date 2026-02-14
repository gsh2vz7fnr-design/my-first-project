"""
对话历史服务 - SQLite 存储
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Optional

from loguru import logger

from app.config import settings


class ConversationService:
    """对话历史服务"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db_lock = threading.Lock()

    @contextmanager
    def _connect(self):
        with self._db_lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    @staticmethod
    def _ensure_member_column(conn: sqlite3.Connection) -> None:
        """兼容旧库: 确保 conversations.member_id 列存在"""
        try:
            conn.execute("ALTER TABLE conversations ADD COLUMN member_id TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    def init_db(self) -> None:
        """初始化数据库"""
        with self._connect() as conn:
            # Messages table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT,
                    user_id TEXT,
                    role TEXT,
                    content TEXT,
                    metadata TEXT,
                    created_at TEXT
                )
                """
            )

            # 兼容旧表：如果表已存在但缺少 metadata 列，补充添加
            try:
                conn.execute(
                    "ALTER TABLE conversation_messages ADD COLUMN metadata TEXT"
                )
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在，忽略

            # Conversations metadata table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    member_id TEXT,
                    title TEXT,
                    message_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )

            # 兼容旧表：添加archived相关字段
            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN archived BOOLEAN DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在
            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN member_id TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在

            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN archived_at TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在

            try:
                conn.execute("ALTER TABLE conversations ADD COLUMN archived_member_id TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在

            # Users table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    nickname TEXT,
                    email TEXT,
                    created_at TEXT,
                    last_login TEXT
                )
                """
            )

            conn.commit()

    def append_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
        member_id: Optional[str] = None
    ) -> None:
        """追加消息"""
        metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

        with self._connect() as conn:
            self._ensure_member_column(conn)
            # Insert message
            conn.execute(
                """
                INSERT INTO conversation_messages (
                    conversation_id, user_id, role, content, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, user_id, role, content, metadata_json, datetime.now().isoformat()),
            )

            # Update or create conversation metadata
            now = datetime.now().isoformat()

            # Check if conversation exists
            existing = conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (conversation_id,)
            ).fetchone()

            if existing:
                # Update existing conversation
                # Update title if this is the first user message
                first_user_msg = conn.execute(
                    """
                    SELECT content FROM conversation_messages
                    WHERE conversation_id = ? AND role = 'user'
                    ORDER BY id ASC LIMIT 1
                    """,
                    (conversation_id,)
                ).fetchone()

                title = first_user_msg[0][:30] if first_user_msg else "新对话"

                conn.execute(
                    """
                    UPDATE conversations
                    SET message_count = message_count + 1,
                        title = ?,
                        updated_at = ?,
                        member_id = COALESCE(member_id, ?)
                    WHERE id = ?
                    """,
                    (title, now, member_id, conversation_id)
                )
            else:
                # Create new conversation
                title = content[:30] if role == "user" else "新对话"
                conn.execute(
                    """
                    INSERT INTO conversations (id, user_id, member_id, title, message_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (conversation_id, user_id, member_id, title, now, now)
                )

            conn.commit()

    def get_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, str]]:
        """获取历史消息"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()

        return [
            {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["created_at"],
            }
            for row in rows
        ]

    def get_user_conversations(self, user_id: str) -> List[Dict[str, any]]:
        """
        获取用户的所有对话

        Args:
            user_id: 用户ID

        Returns:
            List[Dict]: 对话列表
        """
        with self._connect() as conn:
            self._ensure_member_column(conn)
            rows = conn.execute(
                """
                SELECT id, title, message_count, created_at, updated_at,
                       archived, archived_member_id, archived_at, member_id
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,)
            ).fetchall()

        return [
            {
                "conversation_id": row["id"],
                "title": row["title"],
                "message_count": row["message_count"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "archived": row["archived"],
                "archived_member_id": row["archived_member_id"],
                "archived_at": row["archived_at"],
                "member_id": row["member_id"],
            }
            for row in rows
        ]

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """
        删除对话

        Args:
            conversation_id: 对话ID
            user_id: 用户ID

        Returns:
            bool: 是否删除成功
        """
        try:
            with self._connect() as conn:
                # Delete messages
                conn.execute(
                    "DELETE FROM conversation_messages WHERE conversation_id = ?",
                    (conversation_id,)
                )

                # Delete conversation metadata
                conn.execute(
                    "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                    (conversation_id, user_id)
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除对话失败: {e}")
            return False

    def create_conversation(
        self,
        conversation_id: str,
        user_id: str,
        title: str = "新对话",
        member_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        创建新对话

        Args:
            conversation_id: 对话ID
            user_id: 用户ID
            title: 对话标题

        Returns:
            Dict: 对话信息
        """
        now = datetime.now().isoformat()

        with self._connect() as conn:
            self._ensure_member_column(conn)
            conn.execute(
                """
                INSERT INTO conversations (id, user_id, member_id, title, message_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (conversation_id, user_id, member_id, title, now, now)
            )
            conn.commit()

        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "member_id": member_id,
            "title": title,
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }

    def get_bound_member_id(self, conversation_id: str) -> Optional[str]:
        """获取会话已绑定的 member_id"""
        with self._connect() as conn:
            self._ensure_member_column(conn)
            row = conn.execute(
                "SELECT member_id FROM conversations WHERE id = ?",
                (conversation_id,)
            ).fetchone()
        if not row:
            return None
        return row["member_id"]

    def bind_member(self, conversation_id: str, user_id: str, member_id: str) -> str:
        """
        绑定会话的 member_id（不可变）
        - 未绑定: 写入
        - 已绑定同值: 直接返回
        - 已绑定不同值: 抛 ValueError
        """
        with self._connect() as conn:
            self._ensure_member_column(conn)
            row = conn.execute(
                "SELECT member_id FROM conversations WHERE id = ?",
                (conversation_id,)
            ).fetchone()
            if row is None:
                now = datetime.now().isoformat()
                conn.execute(
                    """
                    INSERT INTO conversations (id, user_id, member_id, title, message_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (conversation_id, user_id, member_id, "新对话", now, now)
                )
                conn.commit()
                return member_id

            bound = row["member_id"]
            if bound and bound != member_id:
                raise ValueError(f"member_mismatch:{bound}")
            if not bound:
                conn.execute(
                    "UPDATE conversations SET member_id = ?, updated_at = ? WHERE id = ?",
                    (member_id, datetime.now().isoformat(), conversation_id)
                )
                conn.commit()
            return member_id

    def upsert_user(self, user_id: str, nickname: Optional[str] = None, email: Optional[str] = None) -> Dict[str, any]:
        """
        创建或更新用户，更新 last_login

        Args:
            user_id: 用户ID
            nickname: 昵称（可选）
            email: 邮箱（可选）

        Returns:
            Dict: 用户信息
        """
        now = datetime.now().isoformat()

        with self._connect() as conn:
            # 检查用户是否存在
            existing = conn.execute(
                "SELECT user_id, nickname, email, created_at FROM users WHERE user_id = ?",
                (user_id,)
            ).fetchone()

            if existing:
                # 更新 last_login，以及提供的字段
                update_fields = ["last_login = ?"]
                update_values = [now]

                if nickname is not None:
                    update_fields.append("nickname = ?")
                    update_values.append(nickname)

                if email is not None:
                    update_fields.append("email = ?")
                    update_values.append(email)

                update_values.append(user_id)

                conn.execute(
                    f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?",
                    update_values
                )
                conn.commit()

                # 返回更新后的用户信息
                result = conn.execute(
                    "SELECT user_id, nickname, email, created_at, last_login FROM users WHERE user_id = ?",
                    (user_id,)
                ).fetchone()

                return {
                    "user_id": result["user_id"],
                    "nickname": result["nickname"],
                    "email": result["email"],
                    "created_at": result["created_at"],
                    "last_login": result["last_login"],
                }
            else:
                # 创建新用户
                conn.execute(
                    """
                    INSERT INTO users (user_id, nickname, email, created_at, last_login)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, nickname, email, now, now)
                )
                conn.commit()

                return {
                    "user_id": user_id,
                    "nickname": nickname,
                    "email": email,
                    "created_at": now,
                    "last_login": now,
                }

    def get_user(self, user_id: str) -> Optional[Dict[str, any]]:
        """
        获取用户信息

        Args:
            user_id: 用户ID

        Returns:
            Optional[Dict]: 用户信息，不存在返回 None
        """
        with self._connect() as conn:
            result = conn.execute(
                "SELECT user_id, nickname, email, created_at, last_login FROM users WHERE user_id = ?",
                (user_id,)
            ).fetchone()

            if result:
                return {
                    "user_id": result["user_id"],
                    "nickname": result["nickname"],
                    "email": result["email"],
                    "created_at": result["created_at"],
                    "last_login": result["last_login"],
                }
            return None

    def mark_archived(self, conversation_id: str, member_id: str) -> bool:
        """
        标记对话为已归档

        Args:
            conversation_id: 对话ID
            member_id: 用户ID

        Returns:
            bool: 是否标记成功
        """
        try:
            now = datetime.now().isoformat()

            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE conversations
                    SET archived = 1,
                        archived_at = ?,
                        archived_member_id = ?
                    WHERE id = ?
                    """,
                    (now, member_id, conversation_id)
                )
                conn.commit()

                # 检查是否成功更新
                updated = conn.execute(
                    "SELECT archived FROM conversations WHERE id = ?",
                    (conversation_id,)
                ).fetchone()

                return updated is not None and updated["archived"] == 1

        except Exception as e:
            logger.error(f"标记对话为已归档失败: {e}")
            return False


conversation_service = ConversationService(settings.SQLITE_DB_PATH)
