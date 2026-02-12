"""
对话状态管理服务 - 用于追踪多轮对话中的实体累积（增强版）

新增功能：
- SQLite 持久化 medical_contexts 表
- LRU 缓存减少 DB 读取，自动淘汰最久未访问的条目
- 向后兼容旧的 merge_entities/get_entities 接口
"""
import json
import sqlite3
import threading
from collections import OrderedDict
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from app.models.medical_context import MedicalContext
from app.config import settings


class LRUCache:
    """基于 OrderedDict 的 LRU 缓存，限制最大条目数"""

    def __init__(self, max_size: int = 200):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def remove(self, key: str):
        self._cache.pop(key, None)

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def values(self):
        return self._cache.values()

    def clear(self):
        self._cache.clear()


class ConversationStateService:
    """
    对话状态管理服务（增强版）

    功能：
    - 存储每个对话的累积实体（从首次消息开始）
    - 合并新提取的实体到已有实体中
    - 避免重复询问已提供的信息
    - SQLite 持久化 MedicalContext
    - 内存缓存优化性能
    """

    def __init__(self, db_path: Optional[str] = None):
        """初始化"""
        # 旧版：内存状态
        self._state: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # 新版：LRU 缓存（自动淘汰最久未访问的条目）
        self._context_cache = LRUCache(max_size=200)

        # 数据库路径
        self._db_path = db_path or settings.SQLITE_DB_PATH
        self._db_initialized = False

    def init_db(self) -> None:
        """初始化数据库表"""
        with self._lock:
            if self._db_initialized:
                return

            try:
                # 确保数据目录存在
                db_path = Path(self._db_path)
                db_path.parent.mkdir(parents=True, exist_ok=True)

                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                # 创建 medical_contexts 表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS medical_contexts (
                        conversation_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        context_json TEXT NOT NULL,
                        created_at TEXT,
                        updated_at TEXT
                    )
                """)

                # 创建索引
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_medical_contexts_user_id
                    ON medical_contexts(user_id)
                """)

                conn.commit()
                conn.close()

                self._db_initialized = True
                logger.info(f"[ConversationState] 数据库初始化完成: {self._db_path}")

            except Exception as e:
                logger.error(f"[ConversationState] 数据库初始化失败: {e}", exc_info=True)

    # ============ 旧版接口（向后兼容） ============

    def get_entities(self, conversation_id: str) -> Dict[str, Any]:
        """
        获取对话的累积实体

        Args:
            conversation_id: 对话ID

        Returns:
            Dict[str, Any]: 累积的实体字典
        """
        with self._lock:
            # 优先从内存缓存获取
            if conversation_id in self._state:
                return self._state[conversation_id].copy()

            # 尝试从 MedicalContext 缓存获取
            cached = self._context_cache.get(conversation_id)
            if cached:
                return cached.get_entities_dict()

            return {}

    def update_entities(self, conversation_id: str, new_entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新对话的累积实体（合并新实体）

        Args:
            conversation_id: 对话ID
            new_entities: 新提取的实体

        Returns:
            Dict[str, Any]: 合并后的实体字典
        """
        with self._lock:
            if conversation_id not in self._state:
                self._state[conversation_id] = {}

            # 合并实体：新实体覆盖旧实体（但不删除旧实体）
            for key, value in new_entities.items():
                if value is not None and value != "":  # 只更新有效值
                    self._state[conversation_id][key] = value

            merged = self._state[conversation_id].copy()
            logger.info(f"[ConversationState] 对话 {conversation_id} 累积实体: {merged}")
            return merged

    def clear_entities(self, conversation_id: str) -> None:
        """
        清除对话的累积实体

        Args:
            conversation_id: 对话ID
        """
        with self._lock:
            # 清除内存状态
            if conversation_id in self._state:
                del self._state[conversation_id]

            # 清除 MedicalContext 缓存
            self._context_cache.remove(conversation_id)

            logger.info(f"[ConversationState] 已清除对话 {conversation_id} 的状态")

    def merge_entities(
        self,
        conversation_id: str,
        current_entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        将当前提取的实体与历史累积实体合并

        Args:
            conversation_id: 对话ID
            current_entities: 当前轮次提取的实体

        Returns:
            Dict[str, Any]: 合并后的完整实体
        """
        # 先获取历史实体
        historical_entities = self.get_entities(conversation_id)

        # 合并：当前实体优先级更高（可能是用户修正）
        merged = historical_entities.copy()
        for key, value in current_entities.items():
            if value is not None and value != "":
                merged[key] = value

        # 更新状态
        self.update_entities(conversation_id, current_entities)

        return merged

    # ============ 新版接口：MedicalContext 持久化 ============

    def load_medical_context(
        self,
        conversation_id: str,
        user_id: str
    ) -> Optional[MedicalContext]:
        """
        加载或创建 MedicalContext

        顺序：
        1. 检查内存缓存
        2. 从 SQLite 加载
        3. 创建新的

        Args:
            conversation_id: 对话ID
            user_id: 用户ID

        Returns:
            Optional[MedicalContext]: 医疗上下文对象
        """
        with self._lock:
            # 1. 检查缓存
            cached = self._context_cache.get(conversation_id)
            if cached:
                return cached

            # 2. 尝试从数据库加载
            if self._db_initialized:
                try:
                    conn = sqlite3.connect(self._db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT context_json FROM medical_contexts WHERE conversation_id = ?",
                        (conversation_id,)
                    )
                    row = cursor.fetchone()
                    conn.close()

                    if row:
                        ctx = MedicalContext.from_db_json(row[0])
                        self._context_cache.put(conversation_id, ctx)
                        logger.info(f"[ConversationState] 从数据库恢复对话 {conversation_id}")
                        return ctx

                except Exception as e:
                    logger.error(f"[ConversationState] 加载上下文失败: {e}")

            # 3. 创建新的
            ctx = MedicalContext(
                conversation_id=conversation_id,
                user_id=user_id
            )
            self._context_cache.put(conversation_id, ctx)
            return ctx

    def save_medical_context(self, ctx: MedicalContext) -> bool:
        """
        保存 MedicalContext 到数据库

        Args:
            ctx: 医疗上下文对象

        Returns:
            bool: 是否保存成功
        """
        with self._lock:
            # 更新缓存
            self._context_cache.put(ctx.conversation_id, ctx)
            ctx.updated_at = datetime.now()

            if not self._db_initialized:
                # 数据库未初始化，只保存到内存
                return True

            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()

                context_json = ctx.to_db_json()
                created_at_str = ctx.created_at.isoformat()
                updated_at_str = ctx.updated_at.isoformat()

                cursor.execute("""
                    INSERT OR REPLACE INTO medical_contexts
                    (conversation_id, user_id, context_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    ctx.conversation_id,
                    ctx.user_id,
                    context_json,
                    created_at_str,
                    updated_at_str
                ))

                conn.commit()
                conn.close()

                logger.debug(f"[ConversationState] 保存对话 {ctx.conversation_id}")
                return True

            except Exception as e:
                logger.error(f"[ConversationState] 保存上下文失败: {e}", exc_info=True)
                return False

    def delete_medical_context(self, conversation_id: str) -> bool:
        """
        删除 MedicalContext

        Args:
            conversation_id: 对话ID

        Returns:
            bool: 是否删除成功
        """
        with self._lock:
            # 清除缓存
            self._context_cache.remove(conversation_id)

            if not self._db_initialized:
                return True

            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM medical_contexts WHERE conversation_id = ?",
                    (conversation_id,)
                )
                conn.commit()
                conn.close()

                logger.info(f"[ConversationState] 删除对话 {conversation_id}")
                return True

            except Exception as e:
                logger.error(f"[ConversationState] 删除上下文失败: {e}", exc_info=True)
                return False

    def get_user_contexts(self, user_id: str) -> list[MedicalContext]:
        """
        获取用户的所有对话上下文

        Args:
            user_id: 用户ID

        Returns:
            list[MedicalContext]: 对话上下文列表
        """
        contexts = []

        if not self._db_initialized:
            # 从缓存中获取
            for ctx in self._context_cache.values():
                if ctx.user_id == user_id:
                    contexts.append(ctx)
            return contexts

        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT context_json FROM medical_contexts WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                ctx = MedicalContext.from_db_json(row[0])
                contexts.append(ctx)

        except Exception as e:
            logger.error(f"[ConversationState] 获取用户上下文失败: {e}", exc_info=True)

        return contexts

    def clear_cache(self) -> None:
        """清空内存缓存"""
        with self._lock:
            self._context_cache.clear()
            logger.info("[ConversationState] 内存缓存已清空")


# 创建全局实例
conversation_state_service = ConversationStateService()
