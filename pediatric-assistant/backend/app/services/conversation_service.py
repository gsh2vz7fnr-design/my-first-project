"""
对话历史服务 - SQLite 存储
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

from loguru import logger

from app.config import settings


class ConversationService:
    """对话历史服务"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

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
                    created_at TEXT
                )
                """
            )

            # Conversations metadata table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    title TEXT,
                    message_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )

            conn.commit()

    def append_message(self, conversation_id: str, user_id: str, role: str, content: str) -> None:
        """追加消息"""
        with self._connect() as conn:
            # Insert message
            conn.execute(
                """
                INSERT INTO conversation_messages (
                    conversation_id, user_id, role, content, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, user_id, role, content, datetime.now().isoformat()),
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
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (title, now, conversation_id)
                )
            else:
                # Create new conversation
                title = content[:30] if role == "user" else "新对话"
                conn.execute(
                    """
                    INSERT INTO conversations (id, user_id, title, message_count, created_at, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (conversation_id, user_id, title, now, now)
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
            rows = conn.execute(
                """
                SELECT id, title, message_count, created_at, updated_at
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

    def create_conversation(self, conversation_id: str, user_id: str, title: str = "新对话") -> Dict[str, any]:
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
            conn.execute(
                """
                INSERT INTO conversations (id, user_id, title, message_count, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (conversation_id, user_id, title, now, now)
            )
            conn.commit()

        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "title": title,
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }


conversation_service = ConversationService(settings.SQLITE_DB_PATH)
