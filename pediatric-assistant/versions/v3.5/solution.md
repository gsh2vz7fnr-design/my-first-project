# 版本 v3.5 解决方案文档

> **版本**: v3.5
> **发布日期**: 2026-02-13
> **状态**: 开发中

---

## 一、技术方案概述

### 1.1 架构设计

v3.5 版本采用**前后端分离架构**，通过 RESTful API 实现用户认证和对话归档功能:

```
┌─────────────────────────────────────────────────────────────┐
│                         前端 (H5)                            │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────┐│
│  │  登录遮罩层    │  │  归档模态框    │  │  对话侧边栏       ││
│  │ (Login Modal) │  │ (Archive Modal)│  │ (Conversation    ││
│  │               │  │               │  │  Sidebar)        ││
│  └───────────────┘  └───────────────┘  └──────────────────┘│
│  ┌──────────────────────────────────────────────────────────┤
│  │  app.js: 认证逻辑 + 归档流程 + 计时器管理                 │
│  │  components.js: UI 组件                                  │
│  └──────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
                            ↕ REST API
┌─────────────────────────────────────────────────────────────┐
│                         后端 (FastAPI)                        │
│  ┌──────────────────────────────────────────────────────────┤
│  │  /api/v1/auth/register     - 用户注册/登录               │
│  │  /api/v1/auth/user/{id}    - 用户验证                    │
│  │  /api/v1/conversations/{id}/members - 查询对话成员        │
│  │  /api/v1/conversations/{id}/archive - 归档对话           │
│  └──────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┤
│  │  ConversationService: 对话管理 + 归档逻辑                │
│  │  UserService: 用户管理（新增）                           │
│  └──────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┤
│  │  SQLite: users 表 + conversations 表（新增 archived 字段）│
│  └──────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
```

---

## 二、前端实现方案

### 2.1 登录功能实现

#### 2.1.1 登录遮罩层

**文件**: `frontend/index.html`

**实现**:
- 使用现有的 `#login-modal` (lines 126-138)
- 添加 CSS 样式（已在 index.html 中定义）

**关键代码**:
```html
<div id="login-modal">
  <div id="login-card">
    <h1 id="login-title">👶 欢迎来到智能儿科助手</h1>
    <p id="login-subtitle">请输入您的邮箱或昵称...</p>
    <input type="text" id="login-input" />
    <button id="login-button">开始问诊</button>
  </div>
</div>
```

#### 2.1.2 登录逻辑

**文件**: `frontend/app.js` (lines 1373-1424)

**实现流程**:
1. 用户输入邮箱/昵称
2. 前端清理输入: `user_id = "user_" + sanitized_input`
3. 调用 `POST /api/v1/auth/register` 注册用户
4. 保存 `user_id` 到 `localStorage`
5. 隐藏登录遮罩层，加载对话列表

**关键代码**:
```javascript
async function handleLoginSubmit() {
  const userId = loginInput.value.trim();
  const cleanedUserId = userId.toLowerCase().replace(/\s+/g, '');
  const generatedUserId = 'user_' + cleanedUserId.replace(/[^a-z0-9]/g, '');

  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: generatedUserId,
        display_name: userId.trim()
      })
    });

    if (response.ok) {
      const data = await response.json();
      const validatedUserId = data.data?.user_id || generatedUserId;
      localStorage.setItem('pediatric_user_id', validatedUserId);
      CURRENT_USER_ID = validatedUserId;
    } else {
      // Fallback: 使用本地存储
      localStorage.setItem('pediatric_user_id', generatedUserId);
      CURRENT_USER_ID = generatedUserId;
    }
  } catch (error) {
    // Fallback
    localStorage.setItem('pediatric_user_id', generatedUserId);
    CURRENT_USER_ID = generatedUserId;
  }

  await loadConversations();
}
```

#### 2.1.3 用户验证

**文件**: `frontend/app.js` (lines 512-575)

**实现流程**:
1. 从 `localStorage` 读取 `user_id`
2. 调用 `GET /api/v1/auth/user/{user_id}` 验证
3. 如果验证失败，清除 `localStorage` 并显示登录遮罩层
4. 如果验证成功，加载对话列表

**关键代码**:
```javascript
async function loadConversations() {
  const userId = localStorage.getItem('pediatric_user_id');

  if (!userId) {
    // 显示登录遮罩层
    const loginModal = document.getElementById('login-modal');
    loginModal.classList.add('show');
    return;
  }

  try {
    const validateResponse = await fetch(`${API_BASE}/api/v1/auth/user/${userId}`);
    if (!validateResponse.ok) {
      localStorage.removeItem('pediatric_user_id');
      const loginModal = document.getElementById('login-modal');
      loginModal.classList.add('show');
      return;
    }

    const validateData = await validateResponse.json();
    if (!validateData.data?.valid) {
      localStorage.removeItem('pediatric_user_id');
      const loginModal = document.getElementById('login-modal');
      loginModal.classList.add('show');
      return;
    }
  } catch (error) {
    // Fallback: 使用本地验证
    console.warn('[LOGIN] Backend validation unavailable');
  }

  // 加载对话列表
  const response = await fetch(`${API_BASE}/api/v1/chat/conversations/${userId}`);
  // ...
}
```

---

### 2.2 归档功能实现

#### 2.2.1 归档按钮

**文件**: `frontend/components.js` (lines 111-118)

**修改**: 将"清除对话"按钮改为"归档对话"按钮

**关键代码**:
```javascript
<!-- 右侧：操作按钮 -->
<div class="header-right">
  <button class="header-icon-btn" aria-label="归档对话" id="archive-conversation-btn">
    <svg width="20" height="20" viewBox="0 0 24 24">
      <!-- 文件夹图标 -->
      <path d="M21 8v13H3V8"></path>
      <path d="M1 3h22v5H1z"></path>
      <line x1="10" y1="12" x2="14" y2="12"></line>
    </svg>
  </button>
</div>
```

#### 2.2.2 归档确认模态框

**文件**: `frontend/components.js` (新增函数)

**功能**:
- 单成员: 显示确认对话框
- 多成员: 显示成员选择器

**关键代码**:
```javascript
function createArchiveConfirmModal(options = {}) {
  const { multiMember = false, members = [], onConfirm, onCancel } = options;

  if (multiMember && members.length > 0) {
    // 多成员选择器
    modal.innerHTML = `
      <div class="member-selector">
        ${members.map((member, index) => `
          <label class="member-option">
            <input type="radio" name="selected-member" value="${member.id}" />
            <span>${member.name} (${member.relationship} · ${member.age})</span>
          </label>
        `).join('')}
      </div>
    `;
  } else {
    // 单成员确认
    modal.innerHTML = `
      <p>确认将本次对话归档到健康档案吗？</p>
    `;
  }

  return {
    element: overlay,
    show() { /* ... */ },
    hide() { /* ... */ }
  };
}
```

#### 2.2.3 归档流程

**文件**: `frontend/app.js` (lines 1241-1314)

**实现流程**:
1. 用户点击"归档"按钮
2. 查询对话涉及的成员
3. 根据成员数量显示不同 UI
4. 调用归档 API
5. 清空当前对话，重新加载对话列表

**关键代码**:
```javascript
header.addEventListener("archive-conversation", async () => {
  if (!conversationId) return;

  try {
    // 查询成员
    const membersResponse = await fetch(
      `${API_BASE}/api/v1/conversations/${conversationId}/members`
    );

    if (!membersResponse.ok) {
      // Fallback: 直接归档
      await performArchive(conversationId, null);
      return;
    }

    const membersData = await membersResponse.json();
    const members = membersData.data?.members || [];

    if (members.length === 0) {
      await performArchive(conversationId, null);
    } else if (members.length === 1) {
      // 单成员: 显示确认对话框
      const archiveModal = createArchiveConfirmModal({
        multiMember: false,
        onConfirm: async () => {
          await performArchive(conversationId, members[0].id);
        }
      });
      archiveModal.show();
    } else {
      // 多成员: 显示选择器
      const archiveModal = createArchiveConfirmModal({
        multiMember: true,
        members: members,
        onConfirm: async (selectedMemberId) => {
          await performArchive(conversationId, selectedMemberId);
        }
      });
      archiveModal.show();
    }
  } catch (error) {
    await performArchive(conversationId, null);
  }
});

async function performArchive(convId, memberId) {
  const archiveResponse = await fetch(
    `${API_BASE}/api/v1/conversations/${convId}/archive`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        member_id: memberId,
        user_id: CURRENT_USER_ID
      })
    }
  );

  if (!archiveResponse.ok) throw new Error('归档失败');

  showBanner("对话已归档到健康档案", "info");
  conversationId = null;
  chat.innerHTML = "";
  await loadConversations();
}
```

---

### 2.3 归档提醒实现

#### 2.3.1 beforeunload 事件

**文件**: `frontend/app.js` (lines 1459-1471)

**实现**:
```javascript
window.addEventListener('beforeunload', (event) => {
  if (conversationId && conversationStartTime) {
    const duration = Date.now() - conversationStartTime;
    const fiveMinutes = 5 * 60 * 1000;

    if (duration > fiveMinutes) {
      const message = '您有未归档的对话，确定要离开吗？';
      event.preventDefault();
      event.returnValue = message;
      return message;
    }
  }
});
```

#### 2.3.2 30分钟计时器

**文件**: `frontend/app.js` (lines 1425-1457)

**实现**:
```javascript
let conversationStartTime = null;
let thirtyMinuteTimer = null;

function startThirtyMinuteTimer() {
  conversationStartTime = Date.now();
  clearTimeout(thirtyMinuteTimer);

  thirtyMinuteTimer = setTimeout(() => {
    if (conversationId) {
      showBanner("💡 提示：对话已持续30分钟，建议归档保存到健康档案", "info");
    }
  }, 30 * 60 * 1000);
}

// 创建新对话时启动计时器
const originalHandleNewConversation = handleNewConversation;
handleNewConversation = async function() {
  await originalHandleNewConversation();
  startThirtyMinuteTimer();
};

// 发送首条消息时启动计时器
const originalSendMessageStream = sendMessageStream;
sendMessageStream = async function(text, retryCount = 0) {
  if (!conversationStartTime && conversationId) {
    startThirtyMinuteTimer();
  }
  return await originalSendMessageStream(text, retryCount);
};
```

---

### 2.4 归档状态显示

**文件**: `frontend/components.js` (lines 983-1079)

**实现**: 修改 `renderConversations()` 函数，显示归档状态

**关键代码**:
```javascript
function renderConversations(convs) {
  convs.forEach((conv) => {
    const item = document.createElement("div");
    item.className = "sidebar-item";

    // 添加归档标记
    if (conv.archived) {
      item.classList.add("sidebar-item--archived");
    }

    const title = document.createElement("div");
    title.className = "sidebar-item-title";
    title.textContent = conv.title || "新对话";

    // 归档图标
    if (conv.archived) {
      title.innerHTML = `📁 ${title.textContent}`;
    }

    const actions = document.createElement("div");

    // 归档对话不显示删除按钮
    if (!conv.archived) {
      const deleteBtn = document.createElement("button");
      deleteBtn.innerHTML = "🗑";
      actions.appendChild(deleteBtn);
    } else {
      const archivedLabel = document.createElement("span");
      archivedLabel.className = "sidebar-item-archived-label";
      archivedLabel.textContent = "已归档";
      actions.appendChild(archivedLabel);
    }
  });
}
```

---

## 三、后端实现方案

### 3.1 数据库设计

#### 3.1.1 users 表（新增）

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    nickname TEXT,
    email TEXT,
    created_at TEXT NOT NULL,
    last_login TEXT NOT NULL
);
```

#### 3.1.2 conversations 表（新增字段）

```sql
ALTER TABLE conversations ADD COLUMN archived INTEGER DEFAULT 0;
ALTER TABLE conversations ADD COLUMN archived_to_member_id TEXT;
ALTER TABLE conversations ADD COLUMN archived_at TEXT;
```

---

### 3.2 API 实现

#### 3.2.1 用户注册/登录

**路由**: `POST /api/v1/auth/register`

**实现**:
```python
@router.post("/auth/register")
async def register_user(request: RegisterRequest):
    service = ConversationService()
    user = service.upsert_user(
        user_id=request.user_id,
        nickname=request.display_name,
        email=request.display_name if "@" in request.display_name else None
    )
    return {
        "status": "success",
        "data": {
            "user_id": user["user_id"],
            "created_at": user["created_at"],
            "last_login": user["last_login"]
        }
    }
```

#### 3.2.2 用户验证

**路由**: `GET /api/v1/auth/user/{user_id}`

**实现**:
```python
@router.get("/auth/user/{user_id}")
async def validate_user(user_id: str):
    service = ConversationService()
    user = service.get_user(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 更新 last_login
    service.upsert_user(user_id)

    return {
        "status": "success",
        "data": {
            "valid": True,
            "user_id": user["user_id"],
            "nickname": user["nickname"],
            "last_login": user["last_login"]
        }
    }
```

#### 3.2.3 查询对话成员

**路由**: `GET /api/v1/conversations/{conversation_id}/members`

**实现**:
```python
@router.get("/conversations/{conversation_id}/members")
async def get_conversation_members(conversation_id: str):
    service = ConversationService()
    members = service.get_conversation_members(conversation_id)

    return {
        "status": "success",
        "data": {
            "members": members
        }
    }
```

#### 3.2.4 归档对话

**路由**: `POST /api/v1/conversations/{conversation_id}/archive`

**实现**:
```python
@router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: str,
    request: ArchiveRequest
):
    service = ConversationService()
    result = service.archive_conversation(
        conversation_id=conversation_id,
        member_id=request.member_id,
        user_id=request.user_id
    )

    if not result:
        raise HTTPException(status_code=400, detail="Archive failed")

    conv = service.get_conversation(conversation_id)

    return {
        "status": "success",
        "data": {
            "conversation_id": conversation_id,
            "archived": conv["archived"],
            "archived_to_member_id": conv["archived_to_member_id"],
            "archived_at": conv["archived_at"]
        }
    }
```

---

## 四、测试方案

### 4.1 E2E 测试

**文件**: `backend/tests/e2e/test_v35_integration.py`

**覆盖场景**:
1. TC-E2E-01: 首次登录创建用户
2. TC-E2E-02: 老用户重新登录
3. TC-E2E-03: 单成员对话归档
4. TC-E2E-04: 多成员对话选择归档
5. TC-E2E-05: beforeunload 提示归档
6. TC-E2E-06: 30分钟超时提醒
7. TC-E2E-07: 已归档对话只读
8. TC-E2E-08: 用户ID验证失败重新登录
9. TC-E2E-09: 跨会话数据持久化
10. TC-E2E-10: 完整用户流程

**运行命令**:
```bash
cd backend
pytest tests/e2e/test_v35_integration.py -v
```

---

## 五、部署方案

### 5.1 前端部署

**步骤**:
1. 更新 `frontend/app.js` 和 `frontend/components.js`
2. 更新 `frontend/styles.css`（归档模态框样式）
3. 测试登录流程和归档功能
4. 部署到静态服务器（Nginx/CDN）

### 5.2 后端部署

**步骤**:
1. 更新数据库 schema（添加 `users` 表和 `archived` 字段）
2. 部署新的 API 端点
3. 运行数据库迁移脚本
4. 重启 FastAPI 服务

**数据库迁移**:
```sql
-- 创建 users 表
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    nickname TEXT,
    email TEXT,
    created_at TEXT NOT NULL,
    last_login TEXT NOT NULL
);

-- 添加归档字段
ALTER TABLE conversations ADD COLUMN archived INTEGER DEFAULT 0;
ALTER TABLE conversations ADD COLUMN archived_to_member_id TEXT;
ALTER TABLE conversations ADD COLUMN archived_at TEXT;
```

---

## 六、回滚方案

### 6.1 前端回滚

- 恢复 `frontend/app.js` 和 `frontend/components.js` 到 v3.4 版本
- 移除归档相关 CSS 样式
- 恢复"清除对话"按钮

### 6.2 后端回滚

- 回滚 API 端点
- 保留数据库 schema（不删除 `users` 表和 `archived` 字段，避免数据丢失）
- 重启 FastAPI 服务

---

*最后更新: 2026-02-13 by Agent C*
