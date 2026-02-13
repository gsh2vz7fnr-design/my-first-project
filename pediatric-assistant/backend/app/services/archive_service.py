"""
归档服务 - 将对话归档到consultation_records表
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger

from app.config import settings
from app.services.conversation_state_service import conversation_state_service
from app.services.llm_service import llm_service


class ArchiveService:
    """对话归档服务"""

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

    def init_db(self) -> None:
        """初始化数据库表"""
        with self._connect() as conn:
            # 创建consultation_records表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consultation_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT UNIQUE,
                    member_id TEXT,
                    chief_complaint TEXT,
                    medical_context TEXT,
                    summary TEXT,
                    triage_level TEXT,
                    created_at TEXT,
                    archived_at TEXT
                )
                """
            )
            conn.commit()
            logger.info("consultation_records表初始化完成")

    async def archive_conversation(
        self,
        conversation_id: str,
        member_id: str,
        medical_context: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        归档对话到consultation_records

        Args:
            conversation_id: 对话ID
            member_id: 用户ID
            medical_context: 医疗上下文（可选，如果不提供则从DB加载）

        Returns:
            Dict[str, Any]: 归档结果
        """
        try:
            # 1. 获取MedicalContext
            if medical_context is None:
                # 从conversation_state_service获取
                ctx = conversation_state_service.load_medical_context(conversation_id, member_id)
                # 检查是否为新创建的空上下文（通过turn_count判断）
                if not ctx or ctx.turn_count == 0:
                    raise ValueError(f"未找到对话 {conversation_id} 的医疗上下文")
            else:
                ctx = medical_context

            # 2. 生成摘要
            summary = await self.generate_summary(conversation_id, ctx)

            # 3. 写入consultation_records
            archived_at = datetime.now().isoformat()

            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO consultation_records (
                        conversation_id, member_id, chief_complaint,
                        medical_context, summary, triage_level,
                        created_at, archived_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(conversation_id) DO UPDATE SET
                        summary = excluded.summary,
                        archived_at = excluded.archived_at
                    """,
                    (
                        conversation_id,
                        member_id,
                        ctx.chief_complaint or "",
                        ctx.to_db_json(),
                        summary,
                        ctx.triage_level or "",
                        ctx.created_at.isoformat(),
                        archived_at
                    )
                )
                conn.commit()

            logger.info(f"对话 {conversation_id} 已归档")

            return {
                "conversation_id": conversation_id,
                "member_id": member_id,
                "summary": summary,
                "archived_at": archived_at
            }

        except Exception as e:
            logger.error(f"归档对话失败: {e}", exc_info=True)
            raise

    async def generate_summary(
        self,
        conversation_id: str,
        ctx: Optional[Any] = None
    ) -> str:
        """
        生成对话摘要（100-200字）

        Args:
            conversation_id: 对话ID
            ctx: 医疗上下文（可选，如果不提供则从DB加载）

        Returns:
            str: 摘要文本
        """
        try:
            # 如果没有提供ctx，从DB加载
            if ctx is None:
                from app.services.conversation_service import conversation_service
                history = conversation_service.get_history(conversation_id, limit=20)

                if not history:
                    return "空对话，无内容"

                # 构建对话文本
                conversation_text = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in history
                ])
            else:
                # 使用MedicalContext生成摘要
                conversation_text = f"""
主诉：{ctx.chief_complaint or "未记录"}
症状：{ctx.get_symptom() or "未记录"}
实体信息：{json.dumps(ctx.slots, ensure_ascii=False)}
分诊结果：{ctx.triage_level or "未分诊"}
"""

            # 使用LLM生成摘要
            prompt = f"""请为以下医疗咨询对话生成一个简洁的摘要（100-200字）：

对话内容：
{conversation_text[:1000]}  # 限制输入长度

要求：
1. 总结患者的主要症状和诉求
2. 概括给出的建议或诊断结果
3. 控制在100-200字
4. 使用专业但易懂的语言

直接输出摘要，不要添加标题或前缀。"""

            if not llm_service.remote_available:
                # 本地兜底：从MedicalContext提取关键信息
                return self._generate_fallback_summary(ctx)

            response = llm_service.client.chat.completions.create(
                model=llm_service.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的医疗对话摘要助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )

            summary = response.choices[0].message.content.strip()

            # 确保摘要长度合理
            if len(summary) > 300:
                summary = summary[:297] + "..."

            return summary

        except Exception as e:
            logger.error(f"生成摘要失败: {e}", exc_info=True)
            # 返回基本摘要
            return self._generate_fallback_summary(ctx)

    def _generate_fallback_summary(self, ctx: Optional[Any]) -> str:
        """本地兜底：生成简化摘要"""
        if ctx is None:
            return "对话摘要生成失败"

        symptom = ctx.get_symptom() or "未知症状"
        chief_complaint = ctx.chief_complaint or "无主诉"
        triage_level = ctx.triage_level or "未分诊"

        summary = f"患者咨询{symptom}相关问题。主诉：{chief_complaint[:50]}。"

        if ctx.triage_snapshot:
            summary += f"分诊结果：{triage_level}。建议：{ctx.triage_snapshot.action[:50]}。"

        return summary

    def get_archived_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取已归档的对话

        Args:
            conversation_id: 对话ID

        Returns:
            Optional[Dict[str, Any]]: 归档记录
        """
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM consultation_records
                    WHERE conversation_id = ?
                    """,
                    (conversation_id,)
                ).fetchone()

                if not row:
                    return None

                return {
                    "id": row["id"],
                    "conversation_id": row["conversation_id"],
                    "member_id": row["member_id"],
                    "chief_complaint": row["chief_complaint"],
                    "medical_context": json.loads(row["medical_context"]) if row["medical_context"] else {},
                    "summary": row["summary"],
                    "triage_level": row["triage_level"],
                    "created_at": row["created_at"],
                    "archived_at": row["archived_at"]
                }

        except Exception as e:
            logger.error(f"获取归档对话失败: {e}", exc_info=True)
            return None

    def get_member_archived_conversations(self, member_id: str) -> list:
        """
        获取用户的所有归档对话

        Args:
            member_id: 用户ID

        Returns:
            list: 归档记录列表
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, conversation_id, chief_complaint, summary,
                           triage_level, created_at, archived_at
                    FROM consultation_records
                    WHERE member_id = ?
                    ORDER BY archived_at DESC
                    """,
                    (member_id,)
                ).fetchall()

                return [
                    {
                        "id": row["id"],
                        "conversation_id": row["conversation_id"],
                        "chief_complaint": row["chief_complaint"],
                        "summary": row["summary"],
                        "triage_level": row["triage_level"],
                        "created_at": row["created_at"],
                        "archived_at": row["archived_at"]
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"获取用户归档对话失败: {e}", exc_info=True)
            return []


# 创建全局实例
archive_service = ArchiveService(settings.SQLITE_DB_PATH)
