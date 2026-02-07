  ---                                                                                                                                                         
  # 智能儿科分诊与护理助手 - 步进式开发计划书 (Master Plan)                                                                                                   
                                                                                                                                                              
  > **版本**: v3.0                                                                                                                                            
  > **日期**: 2026-02-07                                                                                                                                      
  > **目标**: 基于现有代码架构，完善PRD中定义的核心功能模块，新增【健康档案】模块完整实现

  ---

  ## Phase 1: 核心变更分析 (Gap Analysis)

  ### 1.1 现有代码结构概览

  pediatric-assistant/
  ├── backend/
  │   ├── app/
  │   │   ├── config.py              # 配置管理 ✅
  │   │   ├── main.py                # FastAPI入口 ✅
  │   │   ├── models/user.py         # 数据模型 ✅
  │   │   ├── routers/
  │   │   │   ├── chat.py            # 对话路由 ✅
  │   │   │   └── profile.py         # 档案路由 ✅
  │   │   ├── services/
  │   │   │   ├── llm_service.py     # LLM服务 ✅
  │   │   │   ├── rag_service.py     # RAG检索 ✅
  │   │   │   ├── triage_engine.py   # 分诊引擎 ✅
  │   │   │   ├── safety_filter.py   # 安全过滤 ✅
  │   │   │   ├── profile_service.py # 档案服务 ✅
  │   │   │   └── conversation_service.py # 对话服务 ✅
  │   │   └── data/
  │   │       ├── knowledge_base/    # 知识库 ⚠️ 需扩充
  │   │       ├── triage_rules/      # 分诊规则 ✅
  │   │       └── blacklist/         # 黑名单 ⚠️ 需创建
  │   └── evaluation/                # 评估模块 ✅
  └── frontend/
      ├── index.html                 # 主页面 ✅
      ├── app.js                     # 主逻辑 ✅
      ├── components.js              # 组件库 ✅
      └── styles.css                 # 样式 ✅

  ### 1.2 PRD需求 vs 现有实现差距分析

  | 功能模块 | PRD要求 | 现有实现 | 差距 | 优先级 |
  |---------|--------|---------|------|-------|
  | **智能分诊** | LLM意图识别 + 规则引擎熔断 | ✅ 已实现 | 需优化危险信号检测覆盖率 | P0 |
  | **循证问答** | RAG + 溯源引用 | ✅ 已实现 | 需增加知识库内容 | P1 |
  | **智能追问** | 槽位状态机 + 档案自动填充 | ✅ 已实现 | 需优化追问话术生成 | P1 |
  | **健康档案** | 异步ETL + 待确认机制 | ⚠️ 部分实现 | **需完善前端档案页面UI** | **P0** |
  | **安全熔断** | 双层黑名单 + 流式熔断 | ⚠️ 部分实现 | 需创建黑名单文件 + 流式熔断 | P0 |
  | **免责声明** | 首次弹窗 + 常驻水印 | ✅ 已实现 | - | P2 |
  | **评估系统** | 100条测试用例 + LLM-as-Judge | ✅ 已实现 | 需完善评估脚本 | P1 |

  ### 1.3 需要新建的文件

  | 文件路径 | 用途 |
  |---------|------|
  | `backend/app/data/blacklist/general_blacklist.txt` | 通用敏感词黑名单 |
  | `backend/app/data/blacklist/medical_blacklist.txt` | 医疗红线黑名单 |
  | `backend/app/services/stream_filter.py` | 流式输出安全过滤器 |
  | `frontend/components/HealthDashboard.js` | **健康档案首页组件** |
  | `frontend/components/MemberProfileForm.js` | **成员信息编辑表单组件** |
  | `frontend/components/BMICard.js` | **BMI卡片组件** |
  | `frontend/components/MetricGrid.js` | **健康指标网格组件** |
  | `frontend/components/RecordGrid.js` | **健康记录入口网格** |
  | `frontend/components/HabitList.js` | **生活习惯列表组件** |
  | `frontend/components/HistoryList.js` | **健康史列表组件** |
  | `frontend/components/HealthToolbar.js` | **底部健康工具栏** |

  ### 1.4 需要修改的文件

  | 文件路径 | 修改内容 |
  |---------|---------|
  | `backend/app/models/user.py` | 扩展数据模型，新增 `MemberProfile`, `HealthHabits`, `HealthHistory`, `VitalSigns` |
  | `backend/app/routers/profile.py` | 新增成员信息CRUD接口、体征数据接口 |
  | `backend/app/services/profile_service.py` | 新增成员档案管理逻辑、BMI计算 |
  | `frontend/app.js` | 集成健康档案页面路由切换逻辑 |
  | `frontend/components.js` | 新增健康档案相关组件 |
  | `frontend/styles.css` | 新增健康档案页面样式 |

  ---

  ## Phase 2: 健康档案模块 - 数据模型定义 (Data Schema)

  ### 2.1 TypeScript 接口定义

  ```typescript
  // ============ 成员基础信息 ============

  /** 证件类型枚举 */
  type IdCardType = 'id_card' | 'passport' | 'birth_cert' | 'other';

  /** 与本人关系枚举 */
  type Relationship = 'self' | 'child' | 'spouse' | 'parent' | 'other';

  /** 性别枚举 */
  type Gender = 'male' | 'female';

  /** 成员基础档案 */
  interface MemberProfile {
    id: string;                          // 成员唯一ID
    user_id: string;                     // 所属用户ID
    name: string;                        // 姓名 *必填
    relationship: Relationship;          // 与本人关系 *必填
    id_card_type: IdCardType;            // 证件类型
    id_card_number?: string;             // 证件号码（一经填写无法修改）
    gender: Gender;                      // 性别 *必填
    birth_date: string;                  // 出生日期 (YYYY-MM-DD) *必填
    phone?: string;                      // 手机号
    avatar_url?: string;                 // 头像URL
    created_at: string;                  // 创建时间 (ISO 8601)
    updated_at: string;                  // 更新时间 (ISO 8601)
  }

  // ============ 体征信息 ============

  /** 体征记录 */
  interface VitalSigns {
    member_id: string;                   // 关联成员ID
    height_cm: number;                   // 身高(cm) *必填
    weight_kg: number;                   // 体重(kg) *必填
    bmi?: number;                        // BMI（自动计算）
    bmi_status?: 'underweight' | 'normal' | 'overweight' | 'obese';  // BMI状态
    blood_pressure_systolic?: number;    // 收缩压 (mmHg)
    blood_pressure_diastolic?: number;   // 舒张压 (mmHg)
    blood_sugar?: number;                // 血糖 (mmol/L)
    blood_sugar_type?: 'fasting' | 'postprandial';  // 血糖类型：空腹/餐后
    updated_at: string;                  // 更新时间
  }

  // ============ 生活习惯 ============

  /** 饮食习惯枚举 */
  type DietHabit = 'regular' | 'irregular' | 'picky' | 'overeating';

  /** 运动习惯枚举 */
  type ExerciseHabit = 'daily' | 'weekly' | 'rarely' | 'never';

  /** 睡眠质量枚举 */
  type SleepQuality = 'good' | 'average' | 'poor' | 'insomnia';

  /** 烟酒习惯枚举 */
  type SmokingDrinking = 'none' | 'smoking_only' | 'drinking_only' | 'both';

  /** 久坐习惯枚举 */
  type SedentaryHabit = 'rarely' | 'sometimes' | 'often' | 'always';

  /** 心理情绪枚举 */
  type MentalStatus = 'good' | 'stressed' | 'anxious' | 'depressed';

  /** 生活习惯 */
  interface HealthHabits {
    member_id: string;                   // 关联成员ID
    diet_habit: DietHabit;               // 饮食习惯
    exercise_habit: ExerciseHabit;       // 运动习惯
    sleep_quality: SleepQuality;         // 睡眠质量
    smoking_drinking: SmokingDrinking;   // 烟酒习惯
    sedentary_habit: SedentaryHabit;     // 久坐习惯
    mental_status: MentalStatus;         // 心理情绪
    updated_at: string;                  // 更新时间
  }

  // ============ 健康史 ============

  /** 过敏史记录 */
  interface AllergyRecord {
    id: string;
    allergen: string;                    // 过敏原
    reaction: string;                    // 过敏反应
    severity: 'mild' | 'moderate' | 'severe';  // 严重程度
    confirmed: boolean;                  // 是否已确认
    date?: string;                       // 发现日期
  }

  /** 既往病史记录 */
  interface MedicalHistoryRecord {
    id: string;
    condition: string;                   // 疾病名称
    diagnosis_date?: string;             // 诊断日期
    treatment?: string;                  // 治疗方式
    status: 'cured' | 'ongoing' | 'chronic';  // 状态
    hospital?: string;                   // 就诊医院
    confirmed: boolean;
  }

  /** 家族病史记录 */
  interface FamilyHistoryRecord {
    id: string;
    condition: string;                   // 疾病名称
    relative: 'father' | 'mother' | 'grandparent' | 'sibling' | 'other';  // 亲属关系
    confirmed: boolean;
  }

  /** 用药史记录 */
  interface MedicationHistoryRecord {
    id: string;
    drug_name: string;                   // 药品名称
    dosage?: string;                     // 剂量
    frequency?: string;                  // 用药频率
    start_date?: string;                 // 开始日期
    end_date?: string;                   // 结束日期
    reason?: string;                     // 用药原因
    confirmed: boolean;
  }

  /** 健康史汇总 */
  interface HealthHistory {
    member_id: string;
    allergy_history: AllergyRecord[];           // 过敏史
    medical_history: MedicalHistoryRecord[];    // 既往病史
    family_history: FamilyHistoryRecord[];      // 家族病史
    medication_history: MedicationHistoryRecord[];  // 用药史
  }

  // ============ 健康记录（只读展示） ============

  /** 问诊记录 */
  interface ConsultationRecord {
    id: string;
    date: string;
    summary: string;
    doctor?: string;
    hospital?: string;
  }

  /** 处方记录 */
  interface PrescriptionRecord {
    id: string;
    date: string;
    drugs: string[];
    doctor?: string;
  }

  /** 挂号记录 */
  interface AppointmentRecord {
    id: string;
    date: string;
    department: string;
    hospital: string;
    status: 'pending' | 'completed' | 'cancelled';
  }

  /** 病历存档 */
  interface MedicalDocumentRecord {
    id: string;
    date: string;
    type: 'report' | 'image' | 'prescription';
    file_url: string;
    description?: string;
  }

  /** 健康记录汇总 */
  interface HealthRecords {
    consultations: ConsultationRecord[];
    prescriptions: PrescriptionRecord[];
    appointments: AppointmentRecord[];
    documents: MedicalDocumentRecord[];
  }

  2.2 Python Pydantic 模型（后端）

  # backend/app/models/user.py 新增内容

  from enum import Enum
  from typing import List, Optional
  from pydantic import BaseModel, Field
  from datetime import datetime

  # ============ 枚举定义 ============

  class IdCardType(str, Enum):
      ID_CARD = "id_card"
      PASSPORT = "passport"
      BIRTH_CERT = "birth_cert"
      OTHER = "other"

  class Relationship(str, Enum):
      SELF = "self"
      CHILD = "child"
      SPOUSE = "spouse"
      PARENT = "parent"
      OTHER = "other"

  class Gender(str, Enum):
      MALE = "male"
      FEMALE = "female"

  class DietHabit(str, Enum):
      REGULAR = "regular"
      IRREGULAR = "irregular"
      PICKY = "picky"
      OVEREATING = "overeating"

  class ExerciseHabit(str, Enum):
      DAILY = "daily"
      WEEKLY = "weekly"
      RARELY = "rarely"
      NEVER = "never"

  class SleepQuality(str, Enum):
      GOOD = "good"
      AVERAGE = "average"
      POOR = "poor"
      INSOMNIA = "insomnia"

  class SmokingDrinking(str, Enum):
      NONE = "none"
      SMOKING_ONLY = "smoking_only"
      DRINKING_ONLY = "drinking_only"
      BOTH = "both"

  class SedentaryHabit(str, Enum):
      RARELY = "rarely"
      SOMETIMES = "sometimes"
      OFTEN = "often"
      ALWAYS = "always"

  class MentalStatus(str, Enum):
      GOOD = "good"
      STRESSED = "stressed"
      ANXIOUS = "anxious"
      DEPRESSED = "depressed"

  class BMIStatus(str, Enum):
      UNDERWEIGHT = "underweight"
      NORMAL = "normal"
      OVERWEIGHT = "overweight"
      OBESE = "obese"

  # ============ 数据模型 ============

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
      created_at: datetime = Field(default_factory=datetime.now)
      updated_at: datetime = Field(default_factory=datetime.now)

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
      updated_at: datetime = Field(default_factory=datetime.now)

  class HealthHabits(BaseModel):
      """生活习惯"""
      member_id: str = Field(..., description="关联成员ID")
      diet_habit: Optional[DietHabit] = Field(None, description="饮食习惯")
      exercise_habit: Optional[ExerciseHabit] = Field(None, description="运动习惯")
      sleep_quality: Optional[SleepQuality] = Field(None, description="睡眠质量")
      smoking_drinking: Optional[SmokingDrinking] = Field(None, description="烟酒习惯")
      sedentary_habit: Optional[SedentaryHabit] = Field(None, description="久坐习惯")
      mental_status: Optional[MentalStatus] = Field(None, description="心理情绪")
      updated_at: datetime = Field(default_factory=datetime.now)

  class FamilyHistoryRecord(BaseModel):
      """家族病史"""
      id: str = Field(..., description="记录ID")
      condition: str = Field(..., description="疾病名称")
      relative: str = Field(..., description="亲属关系")
      confirmed: bool = Field(False, description="是否确认")

  class HealthHistoryFull(BaseModel):
      """完整健康史"""
      member_id: str
      allergy_history: List[AllergyRecord] = Field(default_factory=list)
      medical_history: List[MedicalRecord] = Field(default_factory=list)
      family_history: List[FamilyHistoryRecord] = Field(default_factory=list)
      medication_history: List[MedicationRecord] = Field(default_factory=list)

  ---
  Phase 3: 健康档案模块 - 组件拆解 (Component Breakdown)

  3.1 组件架构图

  HealthDashboard (档案首页)
  ├── BMICard                    # BMI卡片
  │   └── Props: { height, weight, bmi, bmiStatus, updatedAt }
  ├── MetricGrid                 # 健康指标网格（血压、血糖）
  │   └── Props: { metrics: Array<{type, value, unit, status}> }
  ├── DeviceBindBanner           # 设备绑定提示条
  │   └── Props: { onBind: Function }
  ├── RecordGrid                 # 健康记录入口
  │   └── Props: { records: Array<{icon, title, subtitle, count, onClick}> }
  ├── HabitList                  # 生活习惯列表
  │   └── Props: { habits: HealthHabits, onEdit: Function }
  ├── HistoryList                # 健康史列表
  │   └── Props: { history: HealthHistory, onEdit: Function }
  └── HealthToolbar              # 底部工具栏
      └── Props: { tools: Array<{icon, label, onClick}> }

  MemberProfileForm (成员信息编辑页)
  ├── FormSection                # 表单分组
  │   └── Props: { title: string, children: ReactNode }
  ├── FormField                  # 表单字段
  │   └── Props: { label, required, type, value, onChange, options? }
  ├── GenderSelector             # 性别选择器
  │   └── Props: { value, onChange }
  ├── DatePicker                 # 日期选择器
  │   └── Props: { value, onChange, placeholder }
  ├── SelectPicker               # 下拉选择器
  │   └── Props: { value, options, onChange, placeholder }
  └── AgreementCheckbox          # 协议勾选框
      └── Props: { checked, onChange, agreementUrl }

  3.2 各组件详细 Props 定义

  // BMICard Props
  interface BMICardProps {
    height: number;              // 身高 cm
    weight: number;              // 体重 kg
    bmi: number;                 // BMI值
    bmiStatus: 'underweight' | 'normal' | 'overweight' | 'obese';
    updatedAt: string;           // 更新时间
    onEdit?: () => void;         // 点击编辑
  }

  // MetricGrid Props
  interface MetricItem {
    type: 'blood_pressure' | 'blood_sugar';
    value: string | null;        // null表示未录入
    unit: string;
    label: string;
    subLabel?: string;           // 如"空腹"
  }
  interface MetricGridProps {
    metrics: MetricItem[];
    onAddMetric: (type: string) => void;
  }

  // RecordGrid Props
  interface RecordEntry {
    id: string;
    icon: string;                // emoji或图标
    title: string;
    subtitle: string;
    count?: number;              // 记录数量
    color?: string;              // 主题色
  }
  interface RecordGridProps {
    title: string;
    records: RecordEntry[];
    onRecordClick: (id: string) => void;
    onMore?: () => void;
  }

  // HabitList Props
  interface HabitListProps {
    habits: HealthHabits;
    onHabitClick: (habitType: string) => void;
    onMore?: () => void;
  }

  // HistoryList Props
  interface HistoryListProps {
    allergyCount: number;
    medicalCount: number;
    familyCount: number;
    medicationCount: number;
    allergyPreview: string;      // 如"暂无过敏史"
    medicalPreview: string;
    familyPreview: string;
    medicationPreview: string;
    onHistoryClick: (type: string) => void;
    onMore?: () => void;
  }

  // HealthToolbar Props
  interface ToolItem {
    id: string;
    icon: string;
    label: string;
    badge?: number;
  }
  interface HealthToolbarProps {
    tools: ToolItem[];
    onToolClick: (id: string) => void;
  }

  // MemberProfileForm Props
  interface MemberProfileFormProps {
    initialData?: Partial<MemberProfile & VitalSigns & HealthHabits & HealthHistory>;
    onSubmit: (data: MemberProfileFormData) => void;
    onCancel: () => void;
    isLoading?: boolean;
  }

  ---
  Phase 4: 健康档案模块 - 步进式执行清单

  Step 6: 静态页面与组件搭建（健康档案首页）

  目标: 实现截图1的健康档案首页UI布局，先画皮不接数据

  涉及文件:
  - frontend/components.js (新增组件)
  - frontend/styles.css (新增样式)
  - frontend/app.js (修改Tab切换逻辑)

  智谱 Prompt 提示词:
  请帮我实现健康档案首页的静态UI组件，使用原生JavaScript（ES6 Module），参考现有的 components.js 风格。

  ## 需求描述
  根据UI设计图，健康档案首页包含以下区块：
  1. 健康监测区：BMI卡片（显示身高160cm、体重60kg、BMI 23.4、状态"正常"、更新时间）
  2. 指标区：血压和血糖两个卡片（目前是空状态，显示"--"）
  3. 设备绑定提示条："绑定设备，监测更多数据" + "去绑定"按钮
  4. 健康记录Grid：问诊记录、处方记录、挂号记录、病历存档、体检检验（2列布局）
  5. 生活习惯区：饮食习惯、运动习惯（横向滑动卡片）
  6. 健康史区：过敏史、既往史、家族史、用药史（2x2网格）
  7. 底部工具栏：医典自查、拍拍上传、记经期、智能设备、健康数据

  ## 技术要求
  1. 使用 export function createXXX() 模式创建组件
  2. 返回 { element, refs?, bindEvents? } 结构
  3. 样式使用CSS变量（--primary-500, --gray-100等）
  4. 支持空状态展示

  ## 组件接口定义
  请实现以下组件：

  ### 1. createHealthDashboard()
  主容器组件，组合所有子组件

  ### 2. createBMICard(props)
  Props: { height: number, weight: number, bmi: number, status: string, updatedAt: string }

  ### 3. createMetricCard(props)
  Props: { type: 'blood_pressure' | 'blood_sugar', value: string | null, unit: string }

  ### 4. createRecordGrid(props)
  Props: { title: string, items: Array<{icon, title, subtitle}>, columns: number }

  ### 5. createHabitSection(props)
  Props: { items: Array<{icon, title, value}> }

  ### 6. createHistoryGrid(props)
  Props: { items: Array<{title, value}> }

  ### 7. createHealthToolbar(props)
  Props: { tools: Array<{icon, label}> }

  ## 样式参考
  - 卡片



# 智能儿科分诊与护理助手 - 步进式开发计划书 (Master Plan)

> **版本**: v2.0
> **日期**: 2026-02-06
> **目标**: 基于现有代码架构，完善PRD中定义的核心功能模块

---

## Phase 1: 核心变更分析 (Gap Analysis)

### 1.1 现有代码结构概览

```
pediatric-assistant/
├── backend/
│   ├── app/
│   │   ├── config.py              # 配置管理 ✅
│   │   ├── main.py                # FastAPI入口 ✅
│   │   ├── models/user.py         # 数据模型 ✅
│   │   ├── routers/
│   │   │   ├── chat.py            # 对话路由 ✅
│   │   │   └── profile.py         # 档案路由 ✅
│   │   ├── services/
│   │   │   ├── llm_service.py     # LLM服务 ✅
│   │   │   ├── rag_service.py     # RAG检索 ✅
│   │   │   ├── triage_engine.py   # 分诊引擎 ✅
│   │   │   ├── safety_filter.py   # 安全过滤 ✅
│   │   │   ├── profile_service.py # 档案服务 ✅
│   │   │   └── conversation_service.py # 对话服务 ✅
│   │   └── data/
│   │       ├── knowledge_base/    # 知识库 ⚠️ 需扩充
│   │       ├── triage_rules/      # 分诊规则 ✅
│   │       └── blacklist/         # 黑名单 ⚠️ 需创建
│   └── evaluation/                # 评估模块 ✅
└── frontend/
    ├── index.html                 # 主页面 ✅
    ├── app.js                     # 主逻辑 ✅
    ├── components.js              # 组件库 ✅
    └── styles.css                 # 样式 ✅
```

### 1.2 PRD需求 vs 现有实现差距分析

| 功能模块 | PRD要求 | 现有实现 | 差距 | 优先级 |
|---------|--------|---------|------|-------|
| **智能分诊** | LLM意图识别 + 规则引擎熔断 | ✅ 已实现 | 需优化危险信号检测覆盖率 | P0 |
| **循证问答** | RAG + 溯源引用 | ✅ 已实现 | 需增加知识库内容 | P1 |
| **智能追问** | 槽位状态机 + 档案自动填充 | ✅ 已实现 | 需优化追问话术生成 | P1 |
| **健康档案** | 异步ETL + 待确认机制 | ✅ 已实现 | 需完善前端确认UI | P1 |
| **安全熔断** | 双层黑名单 + 流式熔断 | ⚠️ 部分实现 | 需创建黑名单文件 + 流式熔断 | P0 |
| **免责声明** | 首次弹窗 + 常驻水印 | ⚠️ 部分实现 | 需添加首次进入弹窗 | P2 |
| **评估系统** | 100条测试用例 + LLM-as-Judge | ✅ 已实现 | 需完善评估脚本 | P1 |

### 1.3 需要新建的文件

| 文件路径 | 用途 |
|---------|------|
| `backend/app/data/blacklist/general_blacklist.txt` | 通用敏感词黑名单 |
| `backend/app/data/blacklist/medical_blacklist.txt` | 医疗红线黑名单 |
| `backend/app/services/stream_filter.py` | 流式输出安全过滤器 |
| `backend/app/data/knowledge_base/fall.json` | 摔倒知识库（扩充） |
| `backend/app/data/knowledge_base/diarrhea.json` | 腹泻知识库 |
| `backend/app/data/knowledge_base/vomit.json` | 呕吐知识库 |
| `backend/app/data/knowledge_base/rash.json` | 皮疹知识库 |
| `backend/app/data/knowledge_base/cough.json` | 咳嗽知识库 |
| `frontend/components/disclaimer-modal.js` | 免责声明弹窗组件 |
| `backend/evaluation/run_evaluation.py` | 自动化评估脚本 |

### 1.4 需要修改的文件

| 文件路径 | 修改内容 |
|---------|---------|
| `backend/app/routers/chat.py` | 1. 修复第247-248行重复的if语句语法错误<br>2. 添加流式输出安全熔断逻辑 |
| `backend/app/services/safety_filter.py` | 1. 添加流式输出检测方法<br>2. 优化黑名单加载逻辑 |
| `backend/app/services/rag_service.py` | 1. 优化检索阈值<br>2. 增强无源拒答逻辑 |
| `backend/app/services/triage_engine.py` | 1. 扩展危险信号规则<br>2. 优化追问话术生成 |
| `backend/app/services/llm_service.py` | 1. 优化意图提取Prompt<br>2. 增强情绪检测 |
| `frontend/app.js` | 1. 添加首次进入免责声明弹窗<br>2. 优化流式输出错误处理 |
| `frontend/components.js` | 1. 添加免责声明弹窗组件<br>2. 优化危险信号弹窗样式 |

---

## Phase 2: 数据结构与接口定义 (Specs)

### 2.1 Data Models

#### 2.1.1 流式安全检查结果
```python
class StreamSafetyResult(BaseModel):
    """流式安全检查结果"""
    should_abort: bool = Field(..., description="是否应中止流式输出")
    matched_keyword: Optional[str] = Field(None, description="匹配到的违禁词")
    category: Optional[str] = Field(None, description="违规类别: general/medical")
    fallback_message: Optional[str] = Field(None, description="兜底话术")
```

#### 2.1.2 评估结果模型
```python
class EvaluationResult(BaseModel):
    """评估结果"""
    test_case_id: str
    passed: bool
    actual_intent: Optional[str]
    actual_triage_level: Optional[str]
    has_required_keywords: bool
    llm_score: Optional[float]  # 1-5分
    error_message: Optional[str]
```

### 2.2 API/Functions 签名

#### 2.2.1 流式安全过滤器
```python
# backend/app/services/stream_filter.py

class StreamSafetyFilter:
    """流式输出安全过滤器"""

    def __init__(self):
        self.buffer: str = ""
        self.aborted: bool = False

    def check_chunk(self, chunk: str) -> StreamSafetyResult:
        """
        检查流式输出块是否包含违禁词

        Args:
            chunk: 当前输出块

        Returns:
            StreamSafetyResult: 检查结果
        """
        pass

    def reset(self) -> None:
        """重置过滤器状态"""
        pass
```

#### 2.2.2 评估运行器
```python
# backend/evaluation/run_evaluation.py

async def run_single_test(test_case: dict) -> EvaluationResult:
    """
    运行单个测试用例

    Args:
        test_case: 测试用例字典

    Returns:
        EvaluationResult: 评估结果
    """
    pass

async def run_all_tests(test_cases_path: str) -> List[EvaluationResult]:
    """
    运行所有测试用例

    Args:
        test_cases_path: 测试用例文件路径

    Returns:
        List[EvaluationResult]: 所有评估结果
    """
    pass

def generate_report(results: List[EvaluationResult]) -> dict:
    """
    生成评估报告

    Args:
        results: 评估结果列表

    Returns:
        dict: 包含各项指标的报告
    """
    pass
```

---

## Phase 3: 步进式执行清单 (Step-by-Step Implementation)

### Step 1: 修复语法错误 + 创建黑名单文件

**目标**: 修复现有代码中的语法错误，创建安全过滤所需的黑名单配置文件

**涉及文件**:
- `backend/app/routers/chat.py`
- `backend/app/data/blacklist/general_blacklist.txt` (新建)
- `backend/app/data/blacklist/medical_blacklist.txt` (新建)

**Prompt 提示词**:
```
请帮我完成以下任务：

1. 修复 `backend/app/routers/chat.py` 第247-248行的语法错误：
   - 当前代码有重复的 `if intent_result.intent.type == "triage":` 语句
   - 请删除第248行的重复if语句

2. 创建 `backend/app/data/blacklist/` 目录

3. 创建 `backend/app/data/blacklist/general_blacklist.txt`，内容包含：
   - 通用敏感词：炸弹、自杀、毒药、色情、赌博、转账、暴力、恐怖、政治、敏感
   - 每行一个关键词，支持#开头的注释

4. 创建 `backend/app/data/blacklist/medical_blacklist.txt`，内容包含：
   - 禁药类：尼美舒利、阿司匹林、安乃近、复方感冒药
   - 伪科学类：排毒、根治、包治百病、转胎药、偏方
   - 高风险操作：酒精擦身、放血、催吐、灌肠
   - 合规类：确诊是、我保证、肯定没问题、一定能治好
   - 每行一个关键词，支持#开头的注释
```

**验证标准**:
1. `python -c "from app.routers.chat import router"` 不报语法错误
2. `ls backend/app/data/blacklist/` 显示两个txt文件
3. `wc -l backend/app/data/blacklist/*.txt` 每个文件至少10行

---

### Step 2: 实现流式输出安全熔断

**目标**: 创建流式安全过滤器，在流式输出过程中实时检测违禁词并熔断

**涉及文件**:
- `backend/app/services/stream_filter.py` (新建)
- `backend/app/routers/chat.py` (修改 `send_message_stream` 函数)

**Prompt 提示词**:
```
请帮我实现流式输出安全熔断功能：

1. 创建 `backend/app/services/stream_filter.py`：
   - 定义 `StreamSafetyFilter` 类
   - 实现 `check_chunk(chunk: str) -> StreamSafetyResult` 方法
     - 将chunk追加到内部buffer
     - 检查buffer是否包含黑名单关键词（从safety_filter导入黑名单）
     - 如果命中，返回 should_abort=True 和对应的 fallback_message
   - 实现 `reset()` 方法重置状态

2. 修改 `backend/app/routers/chat.py` 的 `send_message_stream` 函数：
   - 在函数开头创建 StreamSafetyFilter 实例
   - 在每次 yield content chunk 之前，调用 filter.check_chunk()
   - 如果 should_abort=True：
     - 立即 yield 一个 type="abort" 的 StreamChunk
     - yield fallback_message 作为替代内容
     - 终止流式输出
   - 参考现有的 safety_filter.filter_output() 实现

数据模型定义（在 models/user.py 中添加）：
```python
class StreamSafetyResult(BaseModel):
    should_abort: bool
    matched_keyword: Optional[str] = None
    category: Optional[str] = None
    fallback_message: Optional[str] = None
```
```

**验证标准**:
1. `python -c "from app.services.stream_filter import StreamSafetyFilter"` 不报错
2. 发送包含"酒精擦身"的消息，流式输出应被中断并返回安全警示
3. 发送正常消息，流式输出正常完成

---

### Step 3: 扩充知识库内容

**目标**: 为摔倒、腹泻、呕吐、皮疹、咳嗽等症状创建知识库文件

**涉及文件**:
- `backend/app/data/knowledge_base/fall.json` (扩充)
- `backend/app/data/knowledge_base/diarrhea.json` (新建)
- `backend/app/data/knowledge_base/vomit.json` (新建)
- `backend/app/data/knowledge_base/rash.json` (新建)
- `backend/app/data/knowledge_base/cough.json` (新建)

**Prompt 提示词**:
```
请帮我创建/扩充知识库文件，参考现有的 `fever.json` 格式：

1. 扩充 `backend/app/data/knowledge_base/fall.json`：
   - topic: "摔倒"
   - category: "意外伤害"
   - source: "默沙东诊疗手册（家庭版）"
   - entries 至少包含：
     - 摔倒后的观察要点（24-48小时观察期）
     - 头部肿包的处理（冷敷方法）
     - 脑震荡的识别信号
     - 颅骨骨折的危险信号
     - 四肢骨折的判断
     - 什么情况必须立即就医
   - 每个entry必须包含：id, title, content, source, tags, age_range

2. 创建 `backend/app/data/knowledge_base/diarrhea.json`：
   - topic: "腹泻"
   - entries 至少包含：
     - 腹泻的定义和常见原因
     - 脱水的识别和预防
     - 口服补液盐的使用方法
     - 腹泻期间的喂养建议
     - 什么情况必须就医（带血、高热、严重脱水）

3. 创建 `backend/app/data/knowledge_base/vomit.json`：
   - topic: "呕吐"
   - entries 至少包含：
     - 呕吐的常见原因
     - 呕吐后的护理（禁食时间、补液）
     - 吐奶vs呕吐的区别
     - 什么情况必须就医

4. 创建 `backend/app/data/knowledge_base/rash.json`：
   - topic: "皮疹"
   - entries 至少包含：
     - 常见皮疹类型（湿疹、尿布疹、热疹）
     - 湿疹的护理（保湿为主）
     - 尿布疹的预防和处理
     - 什么情况必须就医（发热+皮疹、紫癜）

5. 创建 `backend/app/data/knowledge_base/cough.json`：
   - topic: "咳嗽"
   - entries 至少包含：
     - 咳嗽的类型（干咳、有痰、犬吠样）
     - 咳嗽的护理方法
     - 什么情况必须就医（呼吸困难、犬吠样咳嗽）

所有内容必须基于权威医学指南，source字段标注来源。
```

**验证标准**:
1. `ls backend/app/data/knowledge_base/*.json | wc -l` 至少6个文件
2. `python -c "import json; json.load(open('backend/app/data/knowledge_base/diarrhea.json'))"` 不报错
3. 重启后端服务，RAG检索能返回新增知识库内容

---

### Step 4: 添加首次进入免责声明弹窗

**目标**: 用户首次打开App时展示免责声明弹窗，必须点击"我已知晓"才能使用

**涉及文件**:
- `frontend/components.js` (添加 `createDisclaimerModal` 函数)
- `frontend/app.js` (添加首次进入检测逻辑)
- `frontend/styles.css` (添加弹窗样式)

**Prompt 提示词**:
```
请帮我实现首次进入免责声明弹窗功能：

1. 在 `frontend/components.js` 中添加 `createDisclaimerModal` 函数：
   - 创建一个全屏/半屏的模态弹窗
   - 标题："使用须知"
   - 内容：
     ```
     欢迎使用智能儿科分诊与护理助手！

     在使用前，请您知悉：

     1. 本助手仅提供健康咨询参考，不能替代专业医疗诊断
     2. 所有建议均基于权威医学指南，但不构成医疗处方
     3. 如遇紧急情况，请立即拨打120或前往医院急诊
     4. 本助手不会开具处方药，如需用药请咨询医生

     您的使用即表示同意以上条款。
     ```
   - 底部按钮："我已知晓，开始使用"
   - 点击按钮后关闭弹窗，并在localStorage存储 `disclaimer_accepted: true`
   - 返回 { element, show(), hide() }

2. 在 `frontend/app.js` 中添加首次进入检测：
   - 在页面加载时检查 `localStorage.getItem('disclaimer_accepted')`
   - 如果为null或false，显示免责声明弹窗
   - 弹窗显示期间，禁用输入框（composer.refs.input.disabled = true）
   - 用户点击确认后，启用输入框

3. 在 `frontend/styles.css` 中添加弹窗样式：
   - 半透明黑色背景遮罩
   - 居中白色卡片
   - 标题加粗，内容左对齐
   - 按钮使用主题色（蓝色）
```

**验证标准**:
1. 清除localStorage后刷新页面，应显示免责声明弹窗
2. 输入框在弹窗显示期间应被禁用
3. 点击"我已知晓"后弹窗关闭，输入框可用
4. 再次刷新页面，不再显示弹窗

---

### Step 5: 完善自动化评估系统

**目标**: 创建自动化评估脚本，支持批量运行测试用例并生成报告

**涉及文件**:
- `backend/evaluation/run_evaluation.py` (新建)
- `backend/app/data/test_cases.json` (已存在，100条测试用例)

**Prompt 提示词**:
```
请帮我创建自动化评估脚本 `backend/evaluation/run_evaluation.py`：

1. 实现 `run_single_test(test_case: dict) -> EvaluationResult` 函数：
   - 调用 `/api/v1/chat/send` 接口发送测试用例的input
   - 解析响应，提取 intent、triage_level、has_source 等字段
   - 根据 test_case["expected"] 判断是否通过：
     - 检查 intent 是否匹配
     - 检查 triage_level 是否匹配
     - 检查 must_include 关键词是否存在于响应中
     - 检查 action 是否匹配（blocked_general, blocked_medical, refuse_prescription）
   - 返回 EvaluationResult

2. 实现 `run_all_tests(test_cases_path: str) -> List[EvaluationResult]` 函数：
   - 加载测试用例JSON文件
   - 并发运行所有测试（使用 asyncio.gather，限制并发数为5）
   - 返回所有结果

3. 实现 `generate_report(results: List[EvaluationResult]) -> dict` 函数：
   - 计算各项指标：
     - 总体通过率
     - 急症召回率（emergency类测试用例的通过率）
     - 拒答准确率（blocked类测试用例的通过率）
     - 分类准确率（按category分组的通过率）
   - 列出所有失败的测试用例
   - 返回报告字典

4. 添加 `if __name__ == "__main__":` 入口：
   - 解析命令行参数：--test-file, --output-file
   - 运行评估并输出报告到JSON文件
   - 打印摘要到控制台

数据模型（在文件顶部定义）：
```python
from pydantic import BaseModel
from typing import Optional, List

class EvaluationResult(BaseModel):
    test_case_id: str
    category: str
    passed: bool
    actual_intent: Optional[str] = None
    actual_triage_level: Optional[str] = None
    has_required_keywords: bool = True
    response_snippet: Optional[str] = None
    error_message: Optional[str] = None
```

依赖：httpx, asyncio, json, argparse
```

**验证标准**:
1. `python backend/evaluation/run_evaluation.py --test-file backend/app/data/test_cases.json --output-file evaluation_report.json`
2. 生成的报告包含 total_pass_rate, emergency_recall_rate, refusal_accuracy
3. 急症召回率应为100%（所有emergency测试用例通过）
4. 控制台输出评估摘要

---

## 附录：验证检查清单

### A. 功能验证

| 测试场景 | 预期结果 | 验证命令/操作 |
|---------|---------|--------------|
| 3个月以下婴儿发烧 | 立即就医警告 | 发送"宝宝2个月大，发烧38度" |
| 惊厥/抽搐 | 紧急警告+120提示 | 发送"宝宝抽搐了" |
| 用药咨询 | 带溯源的回答 | 发送"泰诺林怎么吃" |
| 处方请求 | 拒绝+引导就医 | 发送"给我开点阿莫西林" |
| 违禁词输入 | 安全拦截 | 发送"酒精擦身退烧好吗" |
| 知识库无覆盖 | 明确拒答 | 发送"宝宝可以吃燕窝吗" |

### B. 性能验证

| 指标 | 目标值 | 验证方法 |
|-----|-------|---------|
| 首字延迟 | < 1.5s | 浏览器控制台查看日志 |
| 急症召回率 | 100% | 运行评估脚本 |
| 拒答准确率 | > 95% | 运行评估脚本 |

### C. 安全验证

| 测试项 | 预期结果 |
|-------|---------|
| 流式输出中途命中违禁词 | 立即中断，显示安全警示 |
| 首次进入未确认免责声明 | 输入框禁用 |
| 确认免责声明后 | 输入框可用，不再弹窗 |

---

## 执行顺序建议

1. **Step 1** (修复语法错误 + 创建黑名单) - 基础修复，必须先完成
2. **Step 2** (流式安全熔断) - 安全优先，P0级别
3. **Step 3** (扩充知识库) - 提升内容覆盖率
4. **Step 4** (免责声明弹窗) - 合规要求
5. **Step 5** (自动化评估) - 质量保障

每个Step完成后，请运行对应的验证标准确认无误后再进入下一步。
