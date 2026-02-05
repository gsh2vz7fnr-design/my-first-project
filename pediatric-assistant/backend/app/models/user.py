"""
数据模型定义
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
    type: str = Field(..., description="类型: emotion/content/citation/done")
    content: Optional[str] = Field(None, description="内容")
    source: Optional[str] = Field(None, description="来源")


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
