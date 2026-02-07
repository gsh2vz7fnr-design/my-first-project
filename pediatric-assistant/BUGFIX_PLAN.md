# Phase 1.5: 问题分级与修复计划 (Triage & Fix Strategy)

> **版本**: v2.0
> **日期**: 2026-02-08
> **基于**: Phase 1 测试报告 (53 tests passed, 68% coverage) + 代码审查

---

## Part 1: 测试结果分析与问题分级

### 测试执行摘要

| 指标 | 结果 |
|------|------|
| **总测试用例** | 53 |
| **通过** | 53 (100%) |
| **代码覆盖率** | 68% (目标 85%) |
| **未覆盖关键路径** | 4 个 |
| **发现的代码缺陷** | 7 个 |

### 问题分级总览

| 编号 | 严重程度 | 类别 | 问题描述 | 影响范围 |
|------|---------|------|---------|---------|
| BUG-001 | Critical | 数据验证 | `MemberCreateRequest.name` 允许空字符串 | 可创建无名成员 |
| BUG-002 | Critical | 业务规则 | 身份证号不可变规则未实现 | 身份证号可被随意修改 |
| BUG-003 | Critical | 数据验证 | 出生日期允许未来日期 | 数据不合理 |
| BUG-004 | Major | 功能缺失 | `profile.py` 缺少 `datetime` 导入 | 问诊/处方/病历记录接口 500 |
| BUG-005 | Major | 覆盖率 | `update_member`/`delete_member` 无测试 | 48% service 覆盖率 |
| BUG-006 | Major | 覆盖率 | `HealthRecordsService` 完全未测试 | 健康记录功能无保障 |
| BUG-007 | Minor | 代码质量 | `rag_service.py` 裸 except 语句 | 调试困难 |

---

## Part 1.1: 逐项根因分析 (Root Cause Analysis)

### BUG-001: 姓名字段允许空字符串 (Critical)

**现象**: `MemberCreateRequest(name="", ...)` 不会抛出 `ValidationError`

**Root Cause**: `models/user.py:264` 中 `name` 字段使用 `Field(...)` 仅标记为必填，但未设置 `min_length` 约束。Pydantic v2 的 `str` 类型默认允许空字符串。

**Fix Approach**: 在 `MemberCreateRequest.name` 字段添加 `min_length=1` 约束。

```python
# models/user.py:264
# Before:
name: str = Field(..., description="姓名")
# After:
name: str = Field(..., min_length=1, max_length=50, description="姓名")
```

---

### BUG-002: 身份证号不可变规则未实现 (Critical)

**现象**: 已设置身份证号的成员，调用 `update_member` 可以修改身份证号。

**Root Cause**: `profile_service.py:537-557` 的 `update_member` 方法直接执行 SQL UPDATE，没有检查 `id_card_number` 是否已存在。

**Fix Approach**: 在 `update_member` 方法中添加前置检查：如果数据库中已有 `id_card_number` 且新值不同，则拒绝修改。

```python
# profile_service.py: update_member()
def update_member(self, member_id: str, member: MemberProfile) -> bool:
    # 检查身份证号不可变规则
    existing = self.get_member(member_id)
    if existing and existing.get("id_card_number"):
        if member.id_card_number and member.id_card_number != existing["id_card_number"]:
            raise ValueError("身份证号一经设置不可修改")
    # ... 继续更新
```

---

### BUG-003: 出生日期允许未来日期 (Critical)

**现象**: `birth_date="2030-01-01"` 可以通过验证并保存。

**Root Cause**: `MemberCreateRequest` 和 `MemberProfile` 的 `birth_date` 字段类型为 `str`，没有自定义 validator 检查日期合理性。

**Fix Approach**: 添加 Pydantic `field_validator` 校验出生日期不能晚于今天。

```python
# models/user.py: MemberCreateRequest
from pydantic import field_validator
from datetime import date

@field_validator("birth_date")
@classmethod
def validate_birth_date(cls, v):
    birth = date.fromisoformat(v)
    if birth > date.today():
        raise ValueError("出生日期不能晚于今天")
    return v
```

---

### BUG-004: profile.py 缺少 datetime 导入 (Major)

**现象**: 调用 `add_consultation_record`、`add_prescription_record`、`add_document_record`、`add_checkup_record` 时，如果请求体中没有 `date` 字段，会触发 `NameError: name 'datetime' is not defined`。

**Root Cause**: `routers/profile.py` 文件头部没有 `from datetime import datetime` 导入，但第 560、583、625、649 行使用了 `datetime.now().strftime("%Y-%m-%d")` 作为默认值。

**Fix Approach**: 在 `profile.py` 头部添加 `from datetime import datetime`。

```python
# routers/profile.py:1-5
from fastapi import APIRouter, HTTPException
from loguru import logger
from typing import List, Dict, Any
from datetime import datetime  # 添加此行
```

---

### BUG-005: 成员更新/删除无测试覆盖 (Major)

**现象**: `update_member()` 和 `delete_member()` 方法完全没有测试用例。

**Root Cause**: 测试文件中缺少 `TestMemberUpdate` 和 `TestMemberDeletion` 测试类。

**Fix Approach**: 补充测试用例，覆盖正常更新、身份证号不可变、级联删除等场景。

---

### BUG-006: HealthRecordsService 完全未测试 (Major)

**现象**: `HealthRecordsService` 类（问诊/处方/挂号/病历/体检记录）0% 覆盖率。

**Root Cause**: 测试计划中未包含此服务的测试用例。

**Fix Approach**: 补充 `test_health_records.py` 测试文件。

---

### BUG-007: 裸 except 语句 (Minor)

**现象**: `rag_service.py` 第192行使用 `except:` 吞掉所有异常。

**Root Cause**: 开发时为快速实现使用了裸 except。

**Fix Approach**: 改为 `except (ValueError, IndexError):`。

---

## Part 2: Phase 1.5 执行计划 (Fix & Polish)

### Step 1: 紧急修复 - 数据验证与业务规则 (Critical Fixes)

**目标**: 修复 BUG-001 ~ BUG-004，确保数据完整性和接口可用性

**涉及文件**:
- `backend/app/models/user.py`
- `backend/app/services/profile_service.py`
- `backend/app/routers/profile.py`

**Copilot Prompt**:

```
你是一个资深 Python 后端工程师。请帮我修复以下 4 个 Bug：

## Bug 1: 姓名字段允许空字符串
文件: `backend/app/models/user.py`
位置: `MemberCreateRequest` 类

当前代码:
```python
class MemberCreateRequest(BaseModel):
    name: str = Field(..., description="姓名")
```

修改为:
```python
class MemberCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
```

## Bug 2: 身份证号不可变规则未实现
文件: `backend/app/services/profile_service.py`
位置: `MemberProfileService.update_member()` 方法（约第537行）

在 UPDATE 执行前添加检查逻辑:
```python
def update_member(self, member_id: str, member: MemberProfile) -> bool:
    # 新增：检查身份证号不可变规则
    existing = self.get_member(member_id)
    if existing and existing.get("id_card_number"):
        if member.id_card_number and member.id_card_number != existing["id_card_number"]:
            raise ValueError("身份证号一经设置不可修改")

    member.updated_at = datetime.now()
    # ... 后续 SQL UPDATE 逻辑不变
```

同时修改 `routers/profile.py` 的 `update_member` 路由，捕获 ValueError:
```python
@router.put("/members/{member_id}")
async def update_member(member_id: str, member: MemberProfile):
    try:
        success = member_profile_service.update_member(member_id, member)
        if not success:
            raise HTTPException(status_code=404, detail="成员不存在")
        return {"code": 0, "message": "更新成功", "data": member.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新成员失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

## Bug 3: 出生日期允许未来日期
文件: `backend/app/models/user.py`
位置: `MemberCreateRequest` 类

添加 field_validator:
```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date

class MemberCreateRequest(BaseModel):
    # ... 现有字段 ...

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v):
        try:
            birth = date.fromisoformat(v)
        except ValueError:
            raise ValueError("出生日期格式错误，应为 YYYY-MM-DD")
        if birth > date.today():
            raise ValueError("出生日期不能晚于今天")
        return v
```

## Bug 4: profile.py 缺少 datetime 导入
文件: `backend/app/routers/profile.py`
位置: 文件头部

在 import 区域添加:
```python
from datetime import datetime
```

## 验证方法
修复完成后，运行以下命令验证:
```bash
cd pediatric-assistant/backend
python -m pytest tests/ -v
python -c "from app.routers.profile import router; print('✅ profile.py 语法正确')"
```
```

---

### Step 2: 补充测试覆盖率 (Coverage Improvement)

**目标**: 将覆盖率从 68% 提升到 85%+，修复 BUG-005 和 BUG-006

**涉及文件**:
- `backend/tests/test_member_profile.py` (扩充)
- `backend/tests/test_health_records.py` (新建)

**Copilot Prompt**:

```
你是一个资深 Python 测试工程师。请帮我补充以下测试用例，提升代码覆盖率。

## 1. 补充成员更新/删除测试
文件: `backend/tests/test_member_profile.py`

请在现有测试文件中添加以下测试类:

### TestMemberUpdate 类
- test_update_member_name: 修改姓名后验证更新成功
- test_update_member_gender: 修改性别后验证更新成功
- test_id_card_number_immutable: 已设置身份证号后尝试修改，应抛出 ValueError
- test_id_card_number_first_set: 首次设置身份证号应成功
- test_update_nonexistent_member: 更新不存在的成员应返回 False

### TestMemberDeletion 类
- test_delete_member: 删除成员后验证成员不存在
- test_delete_nonexistent_member: 删除不存在的成员应返回 False
- test_delete_cascades_vital_signs: 删除成员后体征数据也应被删除
- test_delete_cascades_health_habits: 删除成员后生活习惯数据也应被删除

### TestHealthHabitsOperations 类
- test_create_health_habits: 创建生活习惯记录
- test_update_health_habits: 更新生活习惯记录
- test_get_member_with_habits: 获取成员详情应包含生活习惯

## 2. 新建健康记录测试
文件: `backend/tests/test_health_records.py`

### TestHealthRecordsService 类
- test_add_consultation_record: 添加问诊记录
- test_add_prescription_record: 添加处方记录
- test_add_appointment_record: 添加挂号记录
- test_add_document_record: 添加病历存档
- test_add_checkup_record: 添加体检记录
- test_get_records_summary: 获取记录摘要，验证各类计数正确
- test_empty_records_summary: 无记录时摘要应全为 0

## 技术要求
- 使用 conftest.py 中已有的 fixture
- 每个测试函数有清晰的中文注释
- 使用 assert 验证预期结果
- 测试数据使用有意义的中文内容

## 验证方法
```bash
python -m pytest tests/ -v --cov=app.services.profile_service --cov=app.models.user --cov-report=term-missing
# 预期覆盖率 >= 85%
```
```

---

### Step 3: 代码质量修复 (Code Quality)

**目标**: 修复 BUG-007 及其他代码质量问题

**涉及文件**:
- `backend/app/services/rag_service.py`

**Copilot Prompt**:

```
请帮我修复以下代码质量问题:

## 1. 修复裸 except 语句
文件: `backend/app/services/rag_service.py`
位置: 约第192行

将:
```python
except:
    pass
```

修改为:
```python
except (ValueError, IndexError):
    pass
```

## 验证方法
```bash
python -c "from app.services.rag_service import rag_service; print('✅ RAG服务加载成功')"
```
```

---

### Step 4: 回归测试 (Regression Check)

**验证标准**:

完成所有修复后，执行以下回归测试:

```bash
# 1. 运行全量单元测试
cd pediatric-assistant/backend
python -m pytest tests/ -v

# 预期: 所有测试通过（含新增测试用例）

# 2. 覆盖率检查
python -m pytest tests/ --cov=app.services.profile_service --cov=app.models.user --cov-report=term-missing

# 预期: 覆盖率 >= 85%

# 3. 验证数据验证修复
python -c "
from app.models.user import MemberCreateRequest, Relationship, Gender
try:
    MemberCreateRequest(name='', relationship='child', gender='male', birth_date='2025-06-15')
    print('❌ 空姓名应被拒绝')
except Exception as e:
    print(f'✅ 空姓名被拒绝: {e}')

try:
    MemberCreateRequest(name='小明', relationship='child', gender='male', birth_date='2030-01-01')
    print('❌ 未来日期应被拒绝')
except Exception as e:
    print(f'✅ 未来日期被拒绝: {e}')
"

# 4. 验证 profile.py 导入修复
python -c "from app.routers.profile import router; print('✅ profile.py 语法正确')"

# 5. 启动后端服务验证
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 3

# 测试创建成员接口
curl -s -X POST http://localhost:8000/api/v1/profile/test_user_001/members \
  -H "Content-Type: application/json" \
  -d '{"name":"小明","relationship":"child","gender":"male","birth_date":"2025-06-15","height_cm":75,"weight_kg":9.5}' | python -m json.tool

# 测试空姓名被拒绝
curl -s -X POST http://localhost:8000/api/v1/profile/test_user_001/members \
  -H "Content-Type: application/json" \
  -d '{"name":"","relationship":"child","gender":"male","birth_date":"2025-06-15"}' | python -m json.tool
# 预期: 返回 422 Validation Error
```

---

### 回归测试检查清单

| # | 检查项 | 预期结果 | 状态 |
|---|--------|---------|------|
| 1 | 全量单元测试通过 | 所有测试 PASS | ⬜ |
| 2 | 覆盖率 >= 85% | term-missing 报告确认 | ⬜ |
| 3 | 空姓名被拒绝 | ValidationError | ⬜ |
| 4 | 未来出生日期被拒绝 | ValidationError | ⬜ |
| 5 | 身份证号不可变 | ValueError / 400 | ⬜ |
| 6 | profile.py 无导入错误 | 正常加载 | ⬜ |
| 7 | BMI 计算正确 (75cm, 9.5kg → 16.9) | 16.9, underweight | ⬜ |
| 8 | 创建成员接口正常 | 200 + member_id | ⬜ |
| 9 | 健康记录接口正常 | 200 + record_id | ⬜ |
| 10 | 前端健康档案页加载正常 | 无 JS 错误 | ⬜ |

---

## 执行优先级

```
Step 1 (Critical Fixes)  ──→  Step 2 (Coverage)  ──→  Step 3 (Quality)  ──→  Step 4 (Regression)
     [30 min]                    [45 min]                [10 min]                [15 min]
```

**总计**: 约 1.5 小时
