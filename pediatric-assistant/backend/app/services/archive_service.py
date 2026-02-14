"""
归档服务 - 将对话归档到 archived_conversations 表，并提取结构化健康数据到健康档案
"""
import asyncio
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS archived_conversations (
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
            logger.info("archived_conversations 表初始化完成")

    async def archive_conversation(
        self,
        conversation_id: str,
        member_id: str,
        medical_context: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        归档对话到 archived_conversations，并提取健康数据到档案

        Args:
            conversation_id: 对话ID
            member_id: 用户/成员ID
            medical_context: 医疗上下文（可选，如果不提供则从DB加载）

        Returns:
            Dict[str, Any]: 归档结果，包含健康数据提取摘要
        """
        try:
            ctx = None
            summary = ""
            health_extraction = {}

            # 1. 获取 MedicalContext
            if medical_context is not None:
                ctx = medical_context
            else:
                try:
                    ctx = conversation_state_service.load_medical_context(conversation_id, member_id)
                    if ctx and ctx.turn_count == 0:
                        ctx = None
                except Exception as e:
                    logger.warning(f"加载 MedicalContext 失败: {e}")
                    ctx = None

            # 2. 生成摘要
            if ctx:
                summary = await self.generate_summary(conversation_id, ctx)
            else:
                logger.warning(f"MedicalContext not found for {conversation_id}, using history fallback")
                summary = await self._generate_summary_from_history(conversation_id)

            # 3. 写入 archived_conversations
            archived_at = datetime.now().isoformat()

            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO archived_conversations (
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
                        ctx.chief_complaint if ctx else "",
                        ctx.to_db_json() if ctx else "{}",
                        summary,
                        ctx.triage_level if ctx else "",
                        ctx.created_at.isoformat() if ctx else archived_at,
                        archived_at
                    )
                )
                conn.commit()

            logger.info(f"对话 {conversation_id} 已归档到 archived_conversations")

            # 4. 提取结构化健康数据到健康档案（best-effort）
            if ctx:
                try:
                    health_extraction = await self.extract_health_data_to_profile(
                        member_id, ctx, conversation_id, summary
                    )
                except Exception as e:
                    logger.error(f"健康数据提取失败（不影响归档）: {e}", exc_info=True)
                    health_extraction = {"error": str(e)}

            return {
                "conversation_id": conversation_id,
                "member_id": member_id,
                "summary": summary,
                "archived_at": archived_at,
                "health_extraction": health_extraction
            }

        except Exception as e:
            logger.error(f"归档对话失败: {e}", exc_info=True)
            raise

    async def extract_health_data_to_profile(
        self,
        member_id: str,
        ctx: Any,
        conversation_id: str,
        summary: str = ""
    ) -> Dict[str, Any]:
        """
        从 MedicalContext.slots 中提取结构化数据写入健康档案

        提取项:
        - 问诊记录: chief_complaint + summary → health_records_service.add_consultation()
        - 过敏信息: allergy/过敏 → health_history_service.add_allergy()
        - 用药信息: medication/用药 → health_history_service.add_medication_history()
        - 体征数据: temperature/weight_kg → health_records_service.add_checkup()

        Returns:
            Dict[str, Any]: 提取结果摘要
        """
        from app.services.profile_service import health_records_service, health_history_service

        result = {
            "consultation": 0,
            "allergy": 0,
            "medication": 0,
            "checkup": 0,
            "baby_info": 0,
        }

        today = datetime.now().strftime("%Y-%m-%d")
        slots = ctx.slots or {}

        # 0. 提取宝宝基本信息到档案
        from app.services.profile_service import profile_service
        baby_update = {}
        if slots.get("age_months"):
            baby_update["age_months"] = slots["age_months"]
        if slots.get("weight_kg"):
            baby_update["weight_kg"] = slots["weight_kg"]
        if slots.get("gender"):
            baby_update["gender"] = slots["gender"]
        
        if baby_update:
            try:
                from app.models.user import BabyInfo
                profile = profile_service.get_profile(member_id)
                current_baby = profile.baby_info.model_dump()
                current_baby.update(baby_update)
                
                profile.baby_info = BabyInfo(**current_baby)
                profile_service.save_profile(profile)
                result["baby_info"] = 1
                logger.info(f"已更新宝宝档案: member={member_id}, updates={baby_update}")
            except Exception as e:
                logger.warning(f"更新宝宝档案失败: {e}")

        # 1. 问诊记录
        try:
            consultation_summary = summary or f"主诉：{ctx.chief_complaint or '未记录'}"
            health_records_service.add_consultation(
                member_id=member_id,
                date=today,
                summary=consultation_summary,
                department="儿科",
            )
            result["consultation"] = 1
            logger.info(f"已写入问诊记录: member={member_id}")
        except Exception as e:
            logger.warning(f"写入问诊记录失败: {e}")

        # 2. 过敏信息
        allergy_value = slots.get("allergy") or slots.get("过敏")
        if allergy_value and allergy_value not in ("无", "没有", "无过敏", "不清楚", "unknown"):
            try:
                allergens = allergy_value if isinstance(allergy_value, list) else [allergy_value]
                for allergen in allergens:
                    if allergen and allergen.strip():
                        health_history_service.add_allergy(
                            member_id=member_id,
                            allergen=allergen.strip(),
                            reaction="对话中提及",
                            severity="unknown",
                            date=today,
                        )
                        result["allergy"] += 1
                logger.info(f"已写入过敏记录: member={member_id}, count={result['allergy']}")
            except Exception as e:
                logger.warning(f"写入过敏记录失败: {e}")

        # 3. 用药信息
        medication_value = slots.get("medication") or slots.get("用药") or slots.get("current_medication")
        if medication_value and medication_value not in ("无", "没有", "未用药", "不清楚", "unknown"):
            try:
                meds = medication_value if isinstance(medication_value, list) else [medication_value]
                for med in meds:
                    if med and med.strip():
                        health_history_service.add_medication_history(
                            member_id=member_id,
                            drug_name=med.strip(),
                            start_date=today,
                            reason=ctx.chief_complaint or "对话中提及",
                        )
                        result["medication"] += 1
                logger.info(f"已写入用药记录: member={member_id}, count={result['medication']}")
            except Exception as e:
                logger.warning(f"写入用药记录失败: {e}")

        # 4. 体征数据（体温、体重等）
        checkup_items = []
        temperature = slots.get("temperature") or slots.get("体温")
        if temperature:
            checkup_items.append(f"体温: {temperature}")

        weight_kg = slots.get("weight_kg") or slots.get("体重")
        if weight_kg:
            checkup_items.append(f"体重: {weight_kg}kg")

        if checkup_items:
            try:
                health_records_service.add_checkup(
                    member_id=member_id,
                    date=today,
                    checkup_type="对话体征记录",
                    summary="、".join(checkup_items),
                    results=json.dumps(
                        {k: v for k, v in [
                            ("temperature", temperature),
                            ("weight_kg", weight_kg),
                        ] if v},
                        ensure_ascii=False
                    ),
                )
                result["checkup"] = 1
                logger.info(f"已写入体征记录: member={member_id}, items={checkup_items}")
            except Exception as e:
                logger.warning(f"写入体征记录失败: {e}")

        return result

    async def _generate_summary_from_history(self, conversation_id: str) -> str:
        """
        从对话历史消息生成摘要（MedicalContext 不可用时的回退方案）

        Args:
            conversation_id: 对话ID

        Returns:
            str: 摘要文本
        """
        try:
            from app.services.conversation_service import conversation_service
            history = conversation_service.get_history(conversation_id, limit=20)

            if not history:
                return "空对话，无内容可归档"

            conversation_text = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in history
            ])

            return await self._call_llm_for_summary(conversation_text)
        except Exception as e:
            logger.error(f"从历史生成摘要失败: {e}", exc_info=True)
            return "对话摘要生成失败（历史回退）"

    async def generate_summary(
        self,
        conversation_id: str,
        ctx: Optional[Any] = None
    ) -> str:
        """
        生成对话摘要（100-200字）

        Args:
            conversation_id: 对话ID
            ctx: 医疗上下文（可选）

        Returns:
            str: 摘要文本
        """
        try:
            if ctx is None:
                return await self._generate_summary_from_history(conversation_id)

            conversation_text = f"""
主诉：{ctx.chief_complaint or "未记录"}
症状：{ctx.get_symptom() or "未记录"}
实体信息：{json.dumps(ctx.slots, ensure_ascii=False)}
分诊结果：{ctx.triage_level or "未分诊"}
"""
            return await self._call_llm_for_summary(conversation_text)

        except Exception as e:
            logger.error(f"生成摘要失败: {e}", exc_info=True)
            return self._generate_fallback_summary(ctx)

    async def _call_llm_for_summary(self, conversation_text: str) -> str:
        """
        调用 LLM 生成摘要（使用 asyncio.to_thread 避免阻塞事件循环）
        """
        prompt = f"""请为以下医疗咨询对话生成一个简洁的摘要（100-200字）：

对话内容：
{conversation_text[:1000]}

要求：
1. 总结患者的主要症状和诉求
2. 概括给出的建议或诊断结果
3. 控制在100-200字
4. 使用专业但易懂的语言

直接输出摘要，不要添加标题或前缀。"""

        if not llm_service.remote_available:
            return f"对话摘要（本地生成）：{conversation_text[:100]}..."

        try:
            response = await asyncio.to_thread(
                llm_service.client.chat.completions.create,
                model=llm_service.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的医疗对话摘要助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )

            summary = response.choices[0].message.content.strip()

            if len(summary) > 300:
                summary = summary[:297] + "..."

            return summary
        except Exception as e:
            logger.error(f"LLM 摘要调用失败: {e}", exc_info=True)
            return f"对话摘要（本地生成）：{conversation_text[:100]}..."

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
        """获取已归档的对话"""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM archived_conversations
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
        """获取用户的所有归档对话"""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, conversation_id, chief_complaint, summary,
                           triage_level, created_at, archived_at
                    FROM archived_conversations
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
