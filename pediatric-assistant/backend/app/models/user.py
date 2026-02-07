"""
数据模型定义
"""
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ============ 健康档案枚举定义 ============

class IdCardType(str, Enum):
    """证件类型枚举"""
    ID_CARD = "id_card"
    PASSPORT = "passport"
    BIRTH_CERT = "birth_cert"
    OTHER = "other"


class Relationship(str, Enum):
    """与本人关系枚举"""
    SELF = "self"
    CHILD = "child"
    SPOUSE = "spouse"
    PARENT = "parent"
    OTHER = "other"


class Gender(str, Enum):
    """性别枚举"""
    MALE = "male"
    FEMALE = "female"


class DietHabit(str, Enum):
    """饮食习惯枚举"""
    REGULAR = "regular"
    IRREGULAR = "irregular"
    PICKY = "picky"
    OVEREATING = "overeating"


class ExerciseHabit(str, Enum):
    """运动习惯枚举"""
    DAILY = "daily"
    WEEKLY = "weekly"
    RARELY = "rarely"
    NEVER = "never"


class SleepQuality(str, Enum):
    """睡眠质量枚举"""
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    INSOMNIA = "insomnia"


class SmokingDrinking(str, Enum):
    """烟酒习惯枚举"""
    NONE = "none"
    SMOKING_ONLY = "smoking_only"
    DRINKING_ONLY = "drinking_only"
    BOTH = "both"


class SedentaryHabit(str, Enum):
    """久坐习惯枚举"""
    RARELY = "rarely"
    SOMETIMES = "sometimes"
    OFTEN = "often"
    ALWAYS = "always"


class MentalStatus(str, Enum):
    """心理情绪枚举"""
    GOOD = "good"
    STRESSED = "stressed"
    ANXIOUS = "anxious"
    DEPRESSED = "depressed"


class BMIStatus(str, Enum):
    """BMI状态枚举"""
    UNDERWEIGHT = "underweight"
    NORMAL = "normal"
    OVERWEIGHT = "overweight"
    OBESE = "obese"


# ============ 用户相关模型 ============

class BabyInfo(BaseModel):
    """宝宝基本信息"""
    age_months: Optional[int] = Field(None, description="月龄")
    weight_kg: Optional[float] = Field(None, description="体重(kg)")
    gender: Optional[str] = Field(None, description="性别: male/female")


class AllergyRecord(BaseModel):
    """过敏记录"""
    allergen: str = Field(..., description="过敏原")
    reaction: str = Field(..., description="过敏反应")
    confirmed: bool = Field(False, description="是否已确认")
    date: Optional[str] = Field(None, description="记录日期")


class MedicalRecord(BaseModel):
    """既往病史"""
    condition: str = Field(..., description="病症")
    date: Optional[str] = Field(None, description="发生日期")
    confirmed: bool = Field(False, description="是否已确认")
    note: Optional[str] = Field(None, description="备注")


class MedicationRecord(BaseModel):
    """用药记录"""
    drug: str = Field(..., description="药品名称")
    note: Optional[str] = Field(None, description="备注")
    date: Optional[str] = Field(None, description="用药日期")


class HealthProfile(BaseModel):
    """健康档案"""
    user_id: str = Field(..., description="用户ID")
    baby_info: BabyInfo = Field(default_factory=BabyInfo, description="宝宝信息")
    allergy_history: List[AllergyRecord] = Field(default_factory=list, description="过敏史")
    medical_history: List[MedicalRecord] = Field(default_factory=list, description="既往病史")
    medication_history: List[MedicationRecord] = Field(default_factory=list, description="用药史")
    pending_confirmations: List[Dict[str, Any]] = Field(default_factory=list, description="待确认更新")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


# ============ 对话相关模型 ============

class Message(BaseModel):
    """消息"""
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class Conversation(BaseModel):
    """对话"""
    conversation_id: str = Field(..., description="对话ID")
    user_id: str = Field(..., description="用户ID")
    messages: List[Message] = Field(default_factory=list, description="消息列表")
    status: str = Field("active", description="状态: active/closed")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


# ============ 请求/响应模型 ============

class ChatRequest(BaseModel):
    """聊天请求"""
    user_id: str = Field(..., description="用户ID")
    conversation_id: Optional[str] = Field(None, description="对话ID")
    message: str = Field(..., description="用户消息")


class ChatResponse(BaseModel):
    """聊天响应"""
    conversation_id: str = Field(..., description="对话ID")
    message: str = Field(..., description="助手回复")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="知识来源")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class StreamChunk(BaseModel):
    """流式输出块"""
    type: str = Field(..., description="类型: emotion/content/citation/done/metadata")
    content: Optional[str] = Field(None, description="内容")
    source: Optional[str] = Field(None, description="来源")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据（分诊级别、危险信号等）")


# ============ 分诊相关模型 ============

class Intent(BaseModel):
    """意图"""
    type: str = Field(..., description="意图类型: triage/consult/medication/care")
    confidence: float = Field(..., description="置信度")


class Entity(BaseModel):
    """实体"""
    name: str = Field(..., description="实体名称")
    value: Any = Field(..., description="实体值")
    confidence: float = Field(..., description="置信度")


class IntentAndEntities(BaseModel):
    """意图和实体"""
    intent: Intent = Field(..., description="意图")
    entities: Dict[str, Any] = Field(default_factory=dict, description="实体字典")


class TriageDecision(BaseModel):
    """分诊决策"""
    level: str = Field(..., description="分诊级别: emergency/observe/online")
    reason: str = Field(..., description="原因")
    action: str = Field(..., description="建议行动")
    danger_signal: Optional[str] = Field(None, description="危险信号")


# ============ RAG相关模型 ============

class KnowledgeSource(BaseModel):
    """知识来源"""
    content: str = Field(..., description="内容")
    source: str = Field(..., description="来源")
    score: float = Field(..., description="相似度分数")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class RAGResult(BaseModel):
    """RAG检索结果"""
    answer: str = Field(..., description="答案")
    sources: List[KnowledgeSource] = Field(default_factory=list, description="来源列表")
    has_source: bool = Field(..., description="是否有权威来源")


# ============ 安全相关模型 ============

class SafetyCheckResult(BaseModel):
    """安全检查结果"""
    is_safe: bool = Field(..., description="是否安全")
    matched_keywords: List[str] = Field(default_factory=list, description="匹配的违禁词")
    fallback_message: Optional[str] = Field(None, description="兜底话术")
    category: Optional[str] = Field(None, description="违规类别: general/medical")


class StreamSafetyResult(BaseModel):
    """流式安全检查结果"""
    should_abort: bool = Field(..., description="是否应中止流式输出")
    matched_keyword: Optional[str] = Field(None, description="匹配到的违禁词")
    category: Optional[str] = Field(None, description="违规类别: general/medical")
    fallback_message: Optional[str] = Field(None, description="兜底话术")


# ============ 健康档案数据模型 ============

class MemberProfile(BaseModel):
    """成员基础档案"""
    id: str = Field(..., description="成员唯一ID")
    user_id: str = Field(..., description="所属用户ID")
    name: str = Field(..., description="姓名")
    relationship: Relationship = Field(..., description="与本人关系")
    id_card_type: IdCardType = Field(IdCardType.ID_CARD, description="证件类型")
    id_card_number: Optional[str] = Field(None, description="证件号码")
    gender: Gender = Field(..., description="性别")
    birth_date: str = Field(..., description="出生日期 YYYY-MM-DD")
    phone: Optional[str] = Field(None, description="手机号")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class MemberCreateRequest(BaseModel):
    """创建成员请求"""
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
    relationship: Relationship = Field(..., description="与本人关系")
    gender: Gender = Field(..., description="性别")
    birth_date: str = Field(..., description="出生日期 YYYY-MM-DD")
    id_card_type: IdCardType = Field(IdCardType.ID_CARD, description="证件类型")
    id_card_number: Optional[str] = Field(None, description="证件号码")
    phone: Optional[str] = Field(None, description="手机号")
    avatar_url: Optional[str] = Field(None, description="头像URL")

    # 体征信息
    height_cm: Optional[float] = Field(None, description="身高(cm)")
    weight_kg: Optional[float] = Field(None, description="体重(kg)")
    blood_pressure_systolic: Optional[int] = Field(None, description="收缩压")
    blood_pressure_diastolic: Optional[int] = Field(None, description="舒张压")
    blood_sugar: Optional[float] = Field(None, description="血糖")
    blood_sugar_type: Optional[str] = Field(None, description="血糖类型")

    # 生活习惯
    diet_habit: Optional[DietHabit] = Field(None, description="饮食习惯")
    exercise_habit: Optional[ExerciseHabit] = Field(None, description="运动习惯")
    sleep_quality: Optional[SleepQuality] = Field(None, description="睡眠质量")
    smoking_drinking: Optional[SmokingDrinking] = Field(None, description="烟酒习惯")
    sedentary_habit: Optional[SedentaryHabit] = Field(None, description="久坐习惯")
    mental_status: Optional[MentalStatus] = Field(None, description="心理情绪")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """验证姓名不能为空字符串"""
        if not v or not v.strip():
            raise ValueError("姓名不能为空")
        return v.strip()

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v):
        """验证出生日期不能晚于今天"""
        try:
            birth = date.fromisoformat(v)
        except ValueError:
            raise ValueError("出生日期格式错误，应为 YYYY-MM-DD")
        if birth > date.today():
            raise ValueError("出生日期不能晚于今天")
        return v



class VitalSigns(BaseModel):
    """体征信息"""
    member_id: str = Field(..., description="关联成员ID")
    height_cm: float = Field(..., description="身高(cm)")
    weight_kg: float = Field(..., description="体重(kg)")
    bmi: Optional[float] = Field(None, description="BMI")
    bmi_status: Optional[BMIStatus] = Field(None, description="BMI状态")
    blood_pressure_systolic: Optional[int] = Field(None, description="收缩压")
    blood_pressure_diastolic: Optional[int] = Field(None, description="舒张压")
    blood_sugar: Optional[float] = Field(None, description="血糖")
    blood_sugar_type: Optional[str] = Field(None, description="血糖类型")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class HealthHabits(BaseModel):
    """生活习惯"""
    member_id: str = Field(..., description="关联成员ID")
    diet_habit: Optional[DietHabit] = Field(None, description="饮食习惯")
    exercise_habit: Optional[ExerciseHabit] = Field(None, description="运动习惯")
    sleep_quality: Optional[SleepQuality] = Field(None, description="睡眠质量")
    smoking_drinking: Optional[SmokingDrinking] = Field(None, description="烟酒习惯")
    sedentary_habit: Optional[SedentaryHabit] = Field(None, description="久坐习惯")
    mental_status: Optional[MentalStatus] = Field(None, description="心理情绪")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")


class AllergyRecordNew(BaseModel):
    """过敏史记录（新版）"""
    id: str = Field(..., description="记录ID")
    allergen: str = Field(..., description="过敏原")
    reaction: str = Field(..., description="过敏反应")
    severity: str = Field("mild", description="严重程度")
    confirmed: bool = Field(False, description="是否已确认")
    date: Optional[str] = Field(None, description="发现日期")


class MedicalHistoryRecord(BaseModel):
    """既往病史记录"""
    id: str = Field(..., description="记录ID")
    condition: str = Field(..., description="疾病名称")
    diagnosis_date: Optional[str] = Field(None, description="诊断日期")
    treatment: Optional[str] = Field(None, description="治疗方式")
    status: str = Field("ongoing", description="状态")
    hospital: Optional[str] = Field(None, description="就诊医院")
    confirmed: bool = Field(False, description="是否已确认")


class FamilyHistoryRecord(BaseModel):
    """家族病史记录"""
    id: str = Field(..., description="记录ID")
    condition: str = Field(..., description="疾病名称")
    relative: str = Field(..., description="亲属关系")
    confirmed: bool = Field(False, description="是否已确认")


class MedicationHistoryRecord(BaseModel):
    """用药史记录"""
    id: str = Field(..., description="记录ID")
    drug_name: str = Field(..., description="药品名称")
    dosage: Optional[str] = Field(None, description="剂量")
    frequency: Optional[str] = Field(None, description="用药频率")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")
    reason: Optional[str] = Field(None, description="用药原因")
    confirmed: bool = Field(False, description="是否已确认")


class HealthHistoryFull(BaseModel):
    """完整健康史"""
    member_id: str = Field(..., description="成员ID")
    allergy_history: List[AllergyRecordNew] = Field(default_factory=list, description="过敏史")
    medical_history: List[MedicalHistoryRecord] = Field(default_factory=list, description="既往病史")
    family_history: List[FamilyHistoryRecord] = Field(default_factory=list, description="家族病史")
    medication_history: List[MedicationHistoryRecord] = Field(default_factory=list, description="用药史")


class ProfileConfirmRequest(BaseModel):
    """档案确认请求"""
    confirm: List[Dict[str, Any]] = Field(default_factory=list, description="确认列表")
    reject: List[Dict[str, Any]] = Field(default_factory=list, description="拒绝列表")
