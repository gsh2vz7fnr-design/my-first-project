"""
健康档案服务 - SQLite 存储与档案更新
"""
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from loguru import logger

from app.config import settings
from app.models.user import (
    HealthProfile, BabyInfo, AllergyRecord, MedicalRecord, MedicationRecord,
    MemberProfile, VitalSigns, HealthHabits, BMIStatus
)


class ProfileService:
    """健康档案服务"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # 存储待处理的档案提取任务
        self._pending_extractions: Dict[str, asyncio.Task] = {}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """初始化数据库"""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    baby_info TEXT,
                    allergy_history TEXT,
                    medical_history TEXT,
                    medication_history TEXT,
                    pending_confirmations TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            
            # 任务队列表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_queue (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    execute_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.commit()

    async def start_worker(self):
        """启动后台任务工作线程"""
        logger.info("启动后台任务工作线程...")
        while True:
            try:
                await self._process_due_tasks()
            except Exception as e:
                logger.error(f"任务处理异常: {e}", exc_info=True)
            
            # 每60秒轮询一次
            await asyncio.sleep(60)
            
    async def _process_due_tasks(self):
        """处理到期任务"""
        now = datetime.now().isoformat()
        
        # 1. 获取到期任务
        tasks = []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_queue 
                WHERE status = 'pending' AND execute_at <= ?
                ORDER BY execute_at ASC
                LIMIT 10
                """,
                (now,)
            ).fetchall()
            tasks = [dict(row) for row in rows]
            
        if not tasks:
            return

        logger.info(f"发现 {len(tasks)} 个到期任务")
        
        # 2. 执行任务
        for task in tasks:
            try:
                task_type = task["task_type"]
                payload = json.loads(task["payload"])
                
                if task_type == "extract_profile":
                    await self._execute_extraction(payload)
                    
                # 3. 标记完成
                self._update_task_status(task["id"], "completed")
                
            except Exception as e:
                logger.error(f"任务执行失败 {task['id']}: {e}", exc_info=True)
                self._update_task_status(task["id"], "failed")

    def _update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE task_queue SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, task_id)
            )
            conn.commit()

    async def _execute_extraction(self, payload: Dict[str, Any]):
        """执行档案提取逻辑"""
        user_id = payload["user_id"]
        conversation_id = payload["conversation_id"]
        
        logger.info(f"开始执行档案提取: user={user_id}, conv={conversation_id}")
        
        # 获取对话历史
        from app.services.conversation_service import conversation_service
        messages = conversation_service.get_history(conversation_id)
        
        # 合并所有用户消息
        user_messages = [msg["content"] for msg in messages if msg["role"] == "user"]
        if not user_messages:
            logger.warning("无用户消息，跳过提取")
            return
            
        combined_message = " ".join(user_messages)
        
        # 提取档案更新
        result = await self.apply_updates_from_message(user_id, combined_message)
        
        if result.get("updated"):
            logger.info(f"档案提取完成: user={user_id}, 更新={result.get('updated')}, "
                      f"待确认={len(result.get('pending_confirmations', []))}")
        else:
            logger.info(f"档案提取完成: user={user_id}, 无更新")

    async def apply_updates_from_message(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        从消息中提取并应用档案更新
        """
        from app.services.llm_service import llm_service
        
        # 1. 抽取信息
        updates = await llm_service.extract_profile_updates(message)
        if not updates:
            return {}
            
        # 2. 转换格式为待确认项
        profile = self.get_profile(user_id)
        pending = profile.pending_confirmations or []
        
        new_pending = []
                
        if updates.get("allergy_history"):
            for item in updates["allergy_history"]:
                new_pending.append({
                    "type": "allergy",
                    "record": item
                })
                
        if updates.get("medical_history"):
            for item in updates["medical_history"]:
                new_pending.append({
                    "type": "medical",
                    "record": item
                })
                
        if updates.get("medication_history"):
            for item in updates["medication_history"]:
                new_pending.append({
                    "type": "medication",
                    "record": item
                })

        if not new_pending:
            return {}

        # 3. 去重并保存
        current_pending_json = [json.dumps(x, sort_keys=True) for x in pending]
        
        added_count = 0
        for item in new_pending:
            item_json = json.dumps(item, sort_keys=True)
            if item_json not in current_pending_json:
                pending.append(item)
                current_pending_json.append(item_json)
                added_count += 1
        
        if added_count > 0:
            profile.pending_confirmations = pending
            self.save_profile(profile)
            
        return {"updated": added_count, "pending_confirmations": pending}

    async def schedule_delayed_extraction(
        self,
        user_id: str,
        conversation_id: str,
        delay_minutes: int = 30
    ) -> None:
        """
        安排延迟的档案提取任务（持久化队列）
        
        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            delay_minutes: 延迟时间（分钟）
        """
        # 取消该对话的旧pending任务
        self._cancel_pending_task(user_id, conversation_id)
        
        # 创建新任务
        import uuid
        from datetime import timedelta
        
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        execute_at = (datetime.now() + timedelta(minutes=delay_minutes)).isoformat()
        now = datetime.now().isoformat()
        
        payload = json.dumps({
            "user_id": user_id,
            "conversation_id": conversation_id
        })
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_queue (id, task_type, payload, execute_at, status, created_at, updated_at)
                VALUES (?, 'extract_profile', ?, ?, 'pending', ?, ?)
                """,
                (task_id, payload, execute_at, now, now)
            )
            conn.commit()
            
        logger.info(f"任务已入队: {task_id}, 将于 {execute_at} 执行")

    def _cancel_pending_task(self, user_id: str, conversation_id: str):
        """取消待执行的任务（如果存在）"""
        # 查找该用户该对话的pending任务
        # 这里需要解析payload，SQLite不支持直接JSON查询，用模糊匹配替代
        search_pattern = f'%"{conversation_id}"%'
        
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE task_queue 
                SET status = 'cancelled', updated_at = ?
                WHERE task_type = 'extract_profile' 
                AND status = 'pending' 
                AND payload LIKE ?
                """,
                (datetime.now().isoformat(), search_pattern)
            )
            conn.commit()


    def get_profile(self, user_id: str) -> HealthProfile:
        """获取用户档案"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            
            if row:
                return self._row_to_profile(row)
            
            # 如果不存在，创建空档案
            return HealthProfile(
                user_id=user_id,
                baby_info=BabyInfo(age_months=0, gender="unknown"),
                allergy_history=[],
                medical_history=[],
                medication_history=[],
                pending_confirmations=[],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

    def save_profile(self, profile: HealthProfile) -> None:
        """保存用户档案"""
        profile.updated_at = datetime.now()
        now = profile.updated_at.isoformat()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO profiles (
                    user_id, baby_info, allergy_history, medical_history,
                    medication_history, pending_confirmations, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._profile_to_row(profile, now)
            )
            conn.commit()

    def get_pending_confirmations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取待确认的档案更新

        Args:
            user_id: 用户ID

        Returns:
            List[Dict[str, Any]]: 待确认项列表
        """
        profile = self.get_profile(user_id)
        return profile.pending_confirmations or []

    def confirm_updates(self, user_id: str, updates: Dict[str, Any]) -> HealthProfile:
        """确认或拒绝待确认更新"""
        profile = self.get_profile(user_id)
        pending = profile.pending_confirmations or []

        confirm_list = updates.get("confirm") or []
        reject_list = updates.get("reject") or []

        def _is_match(pending_item: Dict[str, Any], target: Dict[str, Any]) -> bool:
            return pending_item.get("type") == target.get("type") and pending_item.get("record") == target.get("record")

        # 处理确认
        for item in confirm_list:
            record = item.get("record", {})
            if item.get("type") == "allergy":
                # 确保必填字段有默认值
                if not record.get("reaction"):
                    record["reaction"] = "未知反应"
                profile.allergy_history.append(AllergyRecord(**record, confirmed=True))
            elif item.get("type") == "medical":
                profile.medical_history.append(MedicalRecord(**record, confirmed=True))

        # 处理待确认列表
        new_pending = []
        for pending_item in pending:
            if any(_is_match(pending_item, x) for x in confirm_list):
                continue
            if any(_is_match(pending_item, x) for x in reject_list):
                continue
            new_pending.append(pending_item)

        profile.pending_confirmations = new_pending
        self.save_profile(profile)
        return profile

    def _row_to_profile(self, row: sqlite3.Row) -> HealthProfile:
        baby_info = json.loads(row["baby_info"]) if row["baby_info"] else {}
        allergy_history = json.loads(row["allergy_history"]) if row["allergy_history"] else []
        medical_history = json.loads(row["medical_history"]) if row["medical_history"] else []
        medication_history = json.loads(row["medication_history"]) if row["medication_history"] else []
        pending = json.loads(row["pending_confirmations"]) if row["pending_confirmations"] else []

        return HealthProfile(
            user_id=row["user_id"],
            baby_info=BabyInfo(**baby_info),
            allergy_history=[AllergyRecord(**x) for x in allergy_history],
            medical_history=[MedicalRecord(**x) for x in medical_history],
            medication_history=[MedicationRecord(**x) for x in medication_history],
            pending_confirmations=pending,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.now(),
        )

    def _profile_to_row(self, profile: HealthProfile, now: str) -> tuple:
        return (
            profile.user_id,
            json.dumps(profile.baby_info.model_dump()),
            json.dumps([x.model_dump() for x in profile.allergy_history]),
            json.dumps([x.model_dump() for x in profile.medical_history]),
            json.dumps([x.model_dump() for x in profile.medication_history]),
            json.dumps(profile.pending_confirmations or []),
            profile.created_at.isoformat() if profile.created_at else now,
            now,
        )


profile_service = ProfileService(settings.SQLITE_DB_PATH)


# ============ 成员档案管理扩展 ============

class MemberProfileService:
    """成员档案管理服务"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_member_tables(self) -> None:
        """初始化成员档案相关表"""
        with self._connect() as conn:
            # 成员基础信息表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS members (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    id_card_type TEXT DEFAULT 'id_card',
                    id_card_number TEXT,
                    gender TEXT NOT NULL,
                    birth_date TEXT NOT NULL,
                    phone TEXT,
                    avatar_url TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )

            # 体征信息表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vital_signs (
                    member_id TEXT PRIMARY KEY,
                    height_cm REAL NOT NULL,
                    weight_kg REAL NOT NULL,
                    bmi REAL,
                    bmi_status TEXT,
                    blood_pressure_systolic INTEGER,
                    blood_pressure_diastolic INTEGER,
                    blood_sugar REAL,
                    blood_sugar_type TEXT,
                    updated_at TEXT
                )
                """
            )

            # 生活习惯表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS health_habits (
                    member_id TEXT PRIMARY KEY,
                    diet_habit TEXT,
                    exercise_habit TEXT,
                    sleep_quality TEXT,
                    smoking_drinking TEXT,
                    sedentary_habit TEXT,
                    mental_status TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.commit()

    def get_members(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有家庭成员"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM members WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()

        return [dict(row) for row in rows]

    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        """获取单个成员信息（含体征和习惯）"""
        with self._connect() as conn:
            # 获取基础信息
            member = conn.execute(
                "SELECT * FROM members WHERE id = ?",
                (member_id,)
            ).fetchone()

            if not member:
                return None

            result = dict(member)

            # 获取体征信息
            vital = conn.execute(
                "SELECT * FROM vital_signs WHERE member_id = ?",
                (member_id,)
            ).fetchone()
            if vital:
                result["vital_signs"] = dict(vital)

            # 获取生活习惯
            habits = conn.execute(
                "SELECT * FROM health_habits WHERE member_id = ?",
                (member_id,)
            ).fetchone()
            if habits:
                result["health_habits"] = dict(habits)

        return result

    def create_member(self, member: MemberProfile) -> str:
        """创建新成员"""
        now = datetime.now().isoformat()
        member.id = member.id or f"member_{uuid.uuid4().hex[:12]}"
        member.created_at = datetime.now()
        member.updated_at = datetime.now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO members (
                    id, user_id, name, relationship, id_card_type, id_card_number,
                    gender, birth_date, phone, avatar_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member.id, member.user_id, member.name, member.relationship.value,
                    member.id_card_type.value, member.id_card_number, member.gender.value,
                    member.birth_date, member.phone, member.avatar_url,
                    member.created_at.isoformat(), member.updated_at.isoformat()
                )
            )
            conn.commit()

        return member.id

    def update_member(self, member_id: str, member: MemberProfile) -> bool:
        """更新成员信息"""
        # 检查身份证号不可变规则
        existing = self.get_member(member_id)
        if existing and existing.get("id_card_number"):
            if member.id_card_number and member.id_card_number != existing["id_card_number"]:
                raise ValueError("身份证号一经设置不可修改")

        member.updated_at = datetime.now()

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE members SET
                    name = ?, relationship = ?, id_card_type = ?, id_card_number = ?,
                    gender = ?, birth_date = ?, phone = ?, avatar_url = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    member.name, member.relationship.value, member.id_card_type.value,
                    member.id_card_number, member.gender.value, member.birth_date,
                    member.phone, member.avatar_url, member.updated_at.isoformat(),
                    member_id
                )
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_member(self, member_id: str) -> bool:
        """删除成员（级联删除体征和习惯数据）"""
        with self._connect() as conn:
            conn.execute("DELETE FROM vital_signs WHERE member_id = ?", (member_id,))
            conn.execute("DELETE FROM health_habits WHERE member_id = ?", (member_id,))
            cursor = conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
            conn.commit()
            return cursor.rowcount > 0

    def upsert_vital_signs(self, vital_signs: VitalSigns) -> None:
        """更新或插入体征信息"""
        vital_signs.updated_at = datetime.now()

        # 计算BMI
        if vital_signs.height_cm > 0 and vital_signs.weight_kg > 0:
            height_m = vital_signs.height_cm / 100
            vital_signs.bmi = round(vital_signs.weight_kg / (height_m * height_m), 1)
            vital_signs.bmi_status = self._calculate_bmi_status(vital_signs.bmi)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO vital_signs (
                    member_id, height_cm, weight_kg, bmi, bmi_status,
                    blood_pressure_systolic, blood_pressure_diastolic,
                    blood_sugar, blood_sugar_type, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vital_signs.member_id, vital_signs.height_cm, vital_signs.weight_kg,
                    vital_signs.bmi, vital_signs.bmi_status.value if vital_signs.bmi_status else None,
                    vital_signs.blood_pressure_systolic, vital_signs.blood_pressure_diastolic,
                    vital_signs.blood_sugar, vital_signs.blood_sugar_type,
                    vital_signs.updated_at.isoformat()
                )
            )
            conn.commit()

    def upsert_health_habits(self, habits: HealthHabits) -> None:
        """更新或插入生活习惯"""
        habits.updated_at = datetime.now()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO health_habits (
                    member_id, diet_habit, exercise_habit, sleep_quality,
                    smoking_drinking, sedentary_habit, mental_status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    habits.member_id,
                    habits.diet_habit.value if habits.diet_habit else None,
                    habits.exercise_habit.value if habits.exercise_habit else None,
                    habits.sleep_quality.value if habits.sleep_quality else None,
                    habits.smoking_drinking.value if habits.smoking_drinking else None,
                    habits.sedentary_habit.value if habits.sedentary_habit else None,
                    habits.mental_status.value if habits.mental_status else None,
                    habits.updated_at.isoformat()
                )
            )
            conn.commit()

    def _calculate_bmi_status(self, bmi: float) -> BMIStatus:
        """根据BMI值计算状态"""
        if bmi < 18.5:
            return BMIStatus.UNDERWEIGHT
        elif bmi < 24:
            return BMIStatus.NORMAL
        elif bmi < 28:
            return BMIStatus.OVERWEIGHT
        else:
            return BMIStatus.OBESE


# 创建成员档案服务实例
member_profile_service = MemberProfileService(settings.SQLITE_DB_PATH)
member_profile_service.init_member_tables()


# ============ 健康史管理服务 ============

class HealthHistoryService:
    """健康史管理服务"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_history_tables(self) -> None:
        """初始化健康史相关表"""
        with self._connect() as conn:
            # 过敏史表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS allergy_history (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    allergen TEXT NOT NULL,
                    reaction TEXT NOT NULL,
                    severity TEXT DEFAULT 'mild',
                    confirmed BOOLEAN DEFAULT 0,
                    date TEXT,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )

            # 既往病史表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS medical_history (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    diagnosis_date TEXT,
                    treatment TEXT,
                    status TEXT DEFAULT 'ongoing',
                    hospital TEXT,
                    confirmed BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )

            # 家族病史表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS family_history (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    relative TEXT NOT NULL,
                    confirmed BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )

            # 用药史表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS medication_history (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    drug_name TEXT NOT NULL,
                    dosage TEXT,
                    frequency TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    reason TEXT,
                    confirmed BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )
            conn.commit()

    def get_allergy_history(self, member_id: str) -> List[Dict[str, Any]]:
        """获取过敏史"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM allergy_history WHERE member_id = ? ORDER BY date DESC",
                (member_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_medical_history(self, member_id: str) -> List[Dict[str, Any]]:
        """获取既往病史"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM medical_history WHERE member_id = ? ORDER BY diagnosis_date DESC",
                (member_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_family_history(self, member_id: str) -> List[Dict[str, Any]]:
        """获取家族病史"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM family_history WHERE member_id = ? ORDER BY created_at DESC",
                (member_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_medication_history(self, member_id: str) -> List[Dict[str, Any]]:
        """获取用药史"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM medication_history WHERE member_id = ? ORDER BY start_date DESC",
                (member_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_history_summary(self, member_id: str) -> Dict[str, Any]:
        """获取健康史摘要（用于首页展示）"""
        return {
            "allergy_count": len(self.get_allergy_history(member_id)),
            "medical_count": len(self.get_medical_history(member_id)),
            "family_count": len(self.get_family_history(member_id)),
            "medication_count": len(self.get_medication_history(member_id)),
            "allergy_preview": self._get_preview(self.get_allergy_history(member_id), "allergen"),
            "medical_preview": self._get_preview(self.get_medical_history(member_id), "condition"),
            "family_preview": self._get_preview(self.get_family_history(member_id), "condition"),
            "medication_preview": self._get_preview(self.get_medication_history(member_id), "drug_name"),
        }

    def _get_preview(self, items: List[Dict], key: str) -> str:
        """获取预览文本"""
        if not items:
            return "暂无记录"
        return f"{items[0].get(key, '--')}等{len(items)}项"

    def add_allergy(self, member_id: str, allergen: str, reaction: str,
                    severity: str = "mild", date: str = None) -> str:
        """添加过敏记录"""
        record_id = f"allergy_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO allergy_history (id, member_id, allergen, reaction, severity, date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, allergen, reaction, severity, date, now)
            )
            conn.commit()
        return record_id

    def add_medical_history(self, member_id: str, condition: str, diagnosis_date: str = None,
                           treatment: str = None, status: str = "ongoing",
                           hospital: str = None) -> str:
        """添加既往病史"""
        record_id = f"medical_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO medical_history (id, member_id, condition, diagnosis_date, treatment, status, hospital, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, condition, diagnosis_date, treatment, status, hospital, now)
            )
            conn.commit()
        return record_id

    def add_family_history(self, member_id: str, condition: str, relative: str) -> str:
        """添加家族病史"""
        record_id = f"family_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO family_history (id, member_id, condition, relative, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record_id, member_id, condition, relative, now)
            )
            conn.commit()
        return record_id

    def add_medication_history(self, member_id: str, drug_name: str, dosage: str = None,
                              frequency: str = None, start_date: str = None,
                              end_date: str = None, reason: str = None) -> str:
        """添加用药史"""
        record_id = f"med_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO medication_history (id, member_id, drug_name, dosage, frequency, start_date, end_date, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, drug_name, dosage, frequency, start_date, end_date, reason, now)
            )
            conn.commit()
        return record_id


# 创建健康史服务实例
health_history_service = HealthHistoryService(settings.SQLITE_DB_PATH)
health_history_service.init_history_tables()


# ============ 健康记录管理服务 ============

class HealthRecordsService:
    """健康记录管理服务（问诊、处方、挂号、病历、体检）"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_records_tables(self) -> None:
        """初始化健康记录相关表"""
        with self._connect() as conn:
            # 问诊记录表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consultation_records (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    doctor TEXT,
                    hospital TEXT,
                    department TEXT,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )

            # 处方记录表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prescription_records (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    drugs TEXT NOT NULL,
                    doctor TEXT,
                    hospital TEXT,
                    diagnosis TEXT,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )

            # 挂号记录表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS appointment_records (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    department TEXT NOT NULL,
                    hospital TEXT NOT NULL,
                    doctor TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )

            # 病历存档表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_records (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    file_url TEXT,
                    description TEXT,
                    hospital TEXT,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )

            # 体检检验记录表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkup_records (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL,
                    hospital TEXT,
                    summary TEXT,
                    results TEXT,
                    abnormal_items TEXT,
                    created_at TEXT,
                    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
                )
                """
            )
            conn.commit()

    def get_records_summary(self, member_id: str) -> Dict[str, Any]:
        """获取健康记录摘要（用于首页展示）"""
        with self._connect() as conn:
            consultation_count = conn.execute(
                "SELECT COUNT(*) as count FROM consultation_records WHERE member_id = ?",
                (member_id,)
            ).fetchone()["count"]

            prescription_count = conn.execute(
                "SELECT COUNT(*) as count FROM prescription_records WHERE member_id = ?",
                (member_id,)
            ).fetchone()["count"]

            appointment_count = conn.execute(
                "SELECT COUNT(*) as count FROM appointment_records WHERE member_id = ?",
                (member_id,)
            ).fetchone()["count"]

            document_count = conn.execute(
                "SELECT COUNT(*) as count FROM document_records WHERE member_id = ?",
                (member_id,)
            ).fetchone()["count"]

            checkup_count = conn.execute(
                "SELECT COUNT(*) as count FROM checkup_records WHERE member_id = ?",
                (member_id,)
            ).fetchone()["count"]

        return {
            "consultation_count": consultation_count,
            "prescription_count": prescription_count,
            "appointment_count": appointment_count,
            "document_count": document_count,
            "checkup_count": checkup_count,
        }

    def add_consultation(self, member_id: str, date: str, summary: str,
                        doctor: str = None, hospital: str = None,
                        department: str = None) -> str:
        """添加问诊记录"""
        record_id = f"consult_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO consultation_records (id, member_id, date, summary, doctor, hospital, department, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, date, summary, doctor, hospital, department, now)
            )
            conn.commit()
        return record_id

    def add_prescription(self, member_id: str, date: str, drugs: list,
                        doctor: str = None, hospital: str = None,
                        diagnosis: str = None) -> str:
        """添加处方记录"""
        record_id = f"presc_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO prescription_records (id, member_id, date, drugs, doctor, hospital, diagnosis, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, date, json.dumps(drugs, ensure_ascii=False), doctor, hospital, diagnosis, now)
            )
            conn.commit()
        return record_id

    def add_appointment(self, member_id: str, date: str, department: str,
                      hospital: str, doctor: str = None) -> str:
        """添加挂号记录"""
        record_id = f"appoint_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO appointment_records (id, member_id, date, department, hospital, doctor, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, date, department, hospital, doctor, now)
            )
            conn.commit()
        return record_id

    def add_document(self, member_id: str, date: str, doc_type: str,
                    title: str, file_url: str = None, description: str = None,
                    hospital: str = None) -> str:
        """添加病历存档"""
        record_id = f"doc_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_records (id, member_id, date, type, title, file_url, description, hospital, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, date, doc_type, title, file_url, description, hospital, now)
            )
            conn.commit()
        return record_id

    def add_checkup(self, member_id: str, date: str, checkup_type: str,
                   hospital: str = None, summary: str = None,
                   results: str = None, abnormal_items: list = None) -> str:
        """添加体检检验记录"""
        record_id = f"checkup_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO checkup_records (id, member_id, date, type, hospital, summary, results, abnormal_items, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (record_id, member_id, date, checkup_type, hospital, summary, results,
                 json.dumps(abnormal_items or [], ensure_ascii=False), now)
            )
            conn.commit()
        return record_id


# 创建健康记录服务实例
health_records_service = HealthRecordsService(settings.SQLITE_DB_PATH)
health_records_service.init_records_tables()
