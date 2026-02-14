// Note: components.js is loaded as a regular script, so all functions are global
const API_BASE = "http://localhost:8000";

// Global user ID - can be updated via soft login
let CURRENT_USER_ID = "test_user_001";
const LAST_ACTIVE_MEMBER_KEY = "last_active_member_id";
let currentMemberId = null;
let currentMemberName = "默认成员";
let cachedMembers = [];
let conversationMemberMap = {};

// Helper function to get current user ID
function getUserId() {
  return localStorage.getItem('pediatric_user_id') || CURRENT_USER_ID;
}

function getMemberStorageKey() {
  return `${LAST_ACTIVE_MEMBER_KEY}:${getUserId() || "anonymous"}`;
}

function persistActiveMember(memberId) {
  const key = getMemberStorageKey();
  if (memberId) {
    localStorage.setItem(key, memberId);
  } else {
    localStorage.removeItem(key);
  }
}

function updateComposerMemberUI() {
  if (!composer?.refs?.memberPill) return;
  const label = currentMemberName || "默认成员";
  composer.refs.memberPill.innerHTML = `为${label}咨询 <span aria-hidden="true">⇅</span>`;
}

function syncMemberUIEverywhere() {
  updateComposerMemberUI();
  if (currentTab === "health" && cachedMembers.length > 0 && typeof renderHealthMemberSwitcher === "function") {
    renderHealthMemberSwitcher(cachedMembers, currentMemberId);
  }
}

async function loadMembersForCurrentUser() {
  const userId = getUserId();
  if (!userId) return [];
  try {
    const response = await fetch(`${API_BASE}/api/v1/profile/${userId}/members`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.data?.members || [];
  } catch (error) {
    console.warn("[MEMBER] Failed to load members:", error);
    return [];
  }
}

async function syncActiveMember() {
  cachedMembers = await loadMembersForCurrentUser();
  const restored = localStorage.getItem(getMemberStorageKey());
  const found = restored ? cachedMembers.find((m) => m.id === restored) : null;

  if (found) {
    currentMemberId = found.id;
    currentMemberName = found.name || "默认成员";
  } else if (cachedMembers.length > 0) {
    currentMemberId = cachedMembers[0].id;
    currentMemberName = cachedMembers[0].name || "默认成员";
  } else {
    currentMemberId = null;
    currentMemberName = "默认成员";
  }

  persistActiveMember(currentMemberId);
  syncMemberUIEverywhere();
}

function resetChatToWelcome() {
  conversationId = null;
  chat.innerHTML = "";
  const welcome = createWelcomeScreen();
  chat.appendChild(welcome);
}

async function switchActiveMember(memberId, memberName) {
  if (!memberId || memberId === currentMemberId) return;
  if (conversationId) {
    const ok = confirm("切换就诊人将开启新会话并清空当前上下文，是否继续？");
    if (!ok) return;
  }
  currentMemberId = memberId;
  currentMemberName = memberName || "默认成员";
  persistActiveMember(currentMemberId);
  syncMemberUIEverywhere();

  // 关键隔离：切换成员后强制开启新会话上下文
  resetChatToWelcome();
  conversationSidebar.setActive("");
  showBanner(`已切换就诊人：${currentMemberName}，已开启新会话`, "info");
  await loadConversations();
}

async function showConsultMemberSelector() {
  cachedMembers = await loadMembersForCurrentUser();
  if (cachedMembers.length === 0) {
    showBanner("请先创建就诊人后再问诊。", "warn");
    const shouldCreate = confirm("当前还没有就诊人档案，是否现在创建？");
    if (shouldCreate) {
      showCreateMemberForm();
    }
    return;
  }
  const modal = createMemberSelectorModal({
    members: cachedMembers,
    activeMemberId: currentMemberId,
    onConfirm: async (selectedMemberId) => {
      const selected = cachedMembers.find((m) => m.id === selectedMemberId);
      await switchActiveMember(selectedMemberId, selected?.name);
    },
    onCancel: () => {}
  });
  modal.show();
}

let conversationId = null;
let currentTab = "chat"; // Track current tab
let isInitialLoad = true; // Track initial page load

// ============ 自动滚动管理 ============
let userScrolledUp = false; // 用户是否手动向上翻阅
let scrollTimeout = null;   // 滚动防抖定时器

/**
 * 检查是否应该自动滚动到底部
 * @returns {boolean} - 是否应该自动滚动
 */
function shouldAutoScroll() {
  // 如果用户没有向上翻阅，总是自动滚动
  if (!userScrolledUp) return true;

  // 检查是否接近底部（距离底部 150px 以内视为"接近"）
  const threshold = 150;
  const distanceFromBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight;
  return distanceFromBottom <= threshold;
}

/**
 * 滚动到底部
 * @param {boolean} smooth - 是否使用平滑滚动，默认 true
 */
function scrollToBottom(smooth = true) {
  if (!chat) return;

  // 使用 requestAnimationFrame 确保 DOM 更新后再滚动
  requestAnimationFrame(() => {
    if (smooth) {
      chat.scrollTo({
        top: chat.scrollHeight,
        behavior: 'smooth'
      });
    } else {
      chat.scrollTop = chat.scrollHeight;
    }
  });
}

/**
 * 强制滚动到底部（忽略用户翻阅状态）
 * 用于用户发送消息等关键场景
 */
function forceScrollToBottom() {
  userScrolledUp = false;
  scrollToBottom(true);
}

/**
 * 处理聊天区域滚动事件
 * 检测用户是否在查看历史消息
 */
function handleChatScroll() {
  // 清除之前的定时器
  if (scrollTimeout) clearTimeout(scrollTimeout);

  // 防抖：滚动停止后检测
  scrollTimeout = setTimeout(() => {
    const distanceFromBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight;

    // 如果距离底部超过 150px，认为用户在查看历史
    userScrolledUp = distanceFromBottom > 150;
  }, 100);
}

/**
 * 监听消息内容高度变化（处理 Markdown 渲染等动态内容）
 */
function setupResizeObserver() {
  if (typeof ResizeObserver === 'undefined') return;

  const resizeObserver = new ResizeObserver(() => {
    // 如果应该自动滚动，则在内容高度变化时滚动
    if (shouldAutoScroll()) {
      scrollToBottom(false); // 频繁触发时不用平滑滚动，避免卡顿
    }
  });

  // 监听聊天区域内的所有消息
  return resizeObserver;
}

let chatResizeObserver = null;

// Tab change handler
function handleTabChange(tabName) {
  currentTab = tabName;

  if (tabName === "chat") {
    // Show chat, hide health
    healthDashboard.element.style.display = "none";
    chat.style.display = "flex";
    composer.el.style.display = "flex";
  } else if (tabName === "health") {
    // Show health dashboard, hide chat
    healthDashboard.element.style.display = "block";
    chat.style.display = "none";
    composer.el.style.display = "none";

    // Load health data when switching to health tab
    loadHealthData();
  }
}

const root = document.getElementById("root");
const app = document.createElement("div");
app.className = "app";

// Check if disclaimer has been accepted
const DISCLAIMER_KEY = "disclaimer_accepted";
const disclaimerAccepted = localStorage.getItem(DISCLAIMER_KEY) === "true";

// Create disclaimer modal
const disclaimerModal = createDisclaimerModal();
document.body.appendChild(disclaimerModal.element);

// Show disclaimer if not accepted yet
if (!disclaimerAccepted) {
  // Disable input while disclaimer is shown
  const composerInput = document.querySelector(".composer-input");
  if (composerInput) {
    composerInput.disabled = true;
  }

  disclaimerModal.onAccept(() => {
    // Store acceptance
    localStorage.setItem(DISCLAIMER_KEY, "true");

    // Enable input
    const composerInput = document.querySelector(".composer-input");
    if (composerInput) {
      composerInput.disabled = false;
    }
  });

  // Show modal after a short delay
  setTimeout(() => {
    disclaimerModal.show();
  }, 100);
}

const header = createHeader();
const tabs = createTabs(handleTabChange);
const chat = createChat();
const composer = createComposer();
updateComposerMemberUI();

// Add progress container to composer
const progressContainer = document.createElement("div");
progressContainer.className = "composer-progress-container";
composer.el.insertBefore(progressContainer, composer.el.firstChild);
composer.refs.progress = progressContainer;

const sourceSheet = createSourceSheet();
const healthDashboard = createHealthDashboard();

// Listen for quick suggestion clicks from welcome screen
chat.addEventListener("suggestion-selected", (e) => {
  const { example } = e.detail;
  if (example) {
    composer.refs.input.value = example;
    composer.refs.input.focus();
    hideBanner();
  }
});

// Create conversation sidebar
const conversationSidebar = createConversationSidebar({
  onNewConversation: handleNewConversation,
  onSelectConversation: handleSwitchConversation,
  onDeleteConversation: handleDeleteConversation,
});

// Create sidebar backdrop for mobile
const sidebarBackdrop = document.createElement("div");
sidebarBackdrop.className = "sidebar-backdrop";
sidebarBackdrop.addEventListener("click", () => {
  conversationSidebar.element.classList.remove("open");
  sidebarBackdrop.classList.remove("open");
});

// Add sidebar toggle button to header
const sidebarToggle = document.createElement("button");
sidebarToggle.className = "sidebar-toggle";
sidebarToggle.innerHTML = "☰";
sidebarToggle.addEventListener("click", () => {
  conversationSidebar.element.classList.add("open");
  sidebarBackdrop.classList.add("open");
});

app.appendChild(header);
app.appendChild(chat);
app.appendChild(healthDashboard.element);
app.appendChild(composer.el);
root.appendChild(app);

// Initialize: hide health panel by default
healthDashboard.element.style.display = "none";

// ============ 设置自动滚动监听 ============
// 监听用户滚动行为
chat.addEventListener('scroll', handleChatScroll);

// 设置 ResizeObserver 监听内容高度变化
chatResizeObserver = setupResizeObserver();

// Listen for tab change events from header
header.addEventListener("tabchange", (e) => {
  handleTabChange(e.detail);
});

composer.refs.memberPill?.addEventListener("click", () => {
  showConsultMemberSelector();
});

composer.refs.profileLink?.addEventListener("click", async () => {
  const healthTab = header.querySelector('[data-tab="health"]');
  if (healthTab) healthTab.click();
});

// Add sidebar toggle button to header
const sidebarToggleWrapper = header.querySelector(".sidebar-toggle-wrapper");
if (sidebarToggleWrapper) {
  sidebarToggleWrapper.insertBefore(sidebarToggle, sidebarToggleWrapper.firstChild);
}

// Add sidebar and backdrop to body
document.body.appendChild(conversationSidebar.element);
document.body.appendChild(sidebarBackdrop);
document.body.appendChild(sourceSheet.backdrop);
document.body.appendChild(sourceSheet.sheet);

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatMessage(text) {
  if (!text) return "";

  // 先清理来源标记
  let clean = text.replace(/【来源:[^】]+】/g, "");

  // 提取代码块，用占位符替换（避免内部被转义）
  const codeBlocks = [];
  clean = clean.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push({ lang, code: code.trim() });
    return `\n__CODE_BLOCK_${idx}__\n`;
  });

  // 转义 HTML
  let html = escapeHtml(clean);

  // 处理 Markdown 格式
  // 1. 标题 (### / ## / #)
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");

  // 2. 加粗 **text**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // 3. 斜体 *text* (不匹配已处理的加粗)
  html = html.replace(/(?<!\*)\*([^*]+?)\*(?!\*)/g, "<em>$1</em>");

  // 4. 行内代码 `code`
  html = html.replace(/`([^`]+?)`/g, "<code class='inline-code'>$1</code>");

  // 5. 链接 [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="md-link">$1</a>');

  // 6. 引用块 > text（注意 > 已被转义为 &gt;）
  html = html.replace(/^&gt; (.*?)$/gm, "<blockquote>$1</blockquote>");
  html = html.replace(/^&gt;\s*$/gm, "");
  html = html.replace(/<\/blockquote>\n<blockquote>/g, "<br>");

  // 7. 水平线
  html = html.replace(/^---+$/gm, "<hr>");

  // 8. 处理列表和段落（逐行解析）
  const lines = html.split("\n");
  let result = [];
  let inUl = false;
  let inOl = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 跳过已经是 HTML 标签的行
    if (line.startsWith("<h") || line.startsWith("<blockquote>") || line.startsWith("<hr")) {
      if (inUl) { result.push("</ul>"); inUl = false; }
      if (inOl) { result.push("</ol>"); inOl = false; }
      result.push(line);
      continue;
    }

    // 代码块占位符还原
    const codeMatch = line.trim().match(/^__CODE_BLOCK_(\d+)__$/);
    if (codeMatch) {
      if (inUl) { result.push("</ul>"); inUl = false; }
      if (inOl) { result.push("</ol>"); inOl = false; }
      const block = codeBlocks[parseInt(codeMatch[1])];
      const langClass = block.lang ? ` class="lang-${block.lang}"` : "";
      result.push(`<pre class="code-block"><code${langClass}>${escapeHtml(block.code)}</code></pre>`);
      continue;
    }

    const ulMatch = line.match(/^[ \t]*[-*] (.+)/);
    const olMatch = line.match(/^[ \t]*(\d+)\. (.+)/);

    if (ulMatch) {
      if (!inUl) {
        if (inOl) { result.push("</ol>"); inOl = false; }
        result.push("<ul class='message-list'>");
        inUl = true;
      }
      result.push(`<li>${ulMatch[1]}</li>`);
    } else if (olMatch) {
      if (!inOl) {
        if (inUl) { result.push("</ul>"); inUl = false; }
        result.push("<ol class='message-list'>");
        inOl = true;
      }
      result.push(`<li>${olMatch[2]}</li>`);
    } else {
      if (inUl) { result.push("</ul>"); inUl = false; }
      if (inOl) { result.push("</ol>"); inOl = false; }
      if (line.trim()) {
        result.push(`<p>${line}</p>`);
      }
    }
  }

  if (inUl) result.push("</ul>");
  if (inOl) result.push("</ol>");

  return result.join("");
}

function appendMessage(role, text, options = {}) {
  const html = options.html ? options.html : formatMessage(text);
  const bubble = createChatBubble({ role, html });
  if (options.loading) {
    bubble.querySelector(".bubble").classList.add("loading");
  }
  if (options.emergency) {
    bubble.querySelector(".bubble").classList.add("emergency");
  }

  // 添加来源折叠组件
  if (options.sources && options.sources.length > 0) {
    const sourceToggle = createSourceToggle(options.sources);
    bubble.querySelector(".bubble").appendChild(sourceToggle);
  }

  // Check if bubble has content before removing empty state
  const empty = chat.querySelector(".chat-empty");
  if (empty) {
    empty.remove();
  }
  chat.appendChild(bubble);

  // 自动滚动到底部（用户发送消息时强制滚动）
  if (role === 'user') {
    forceScrollToBottom();
  } else {
    scrollToBottom(true);
  }

  // 监听消息高度变化（处理 Markdown 渲染后高度变化）
  if (chatResizeObserver) {
    chatResizeObserver.observe(bubble);
  }

  return bubble;
}

// 创建来源折叠组件
function createSourceToggle(sources) {
  const container = document.createElement("div");
  container.className = "source-toggle-container";

  const toggleBtn = document.createElement("button");
  toggleBtn.className = "source-toggle-button";
  toggleBtn.innerHTML = `<span class="source-icon">📚</span> 查看知识来源 (${sources.length})`;
  toggleBtn.setAttribute("aria-expanded", "false");
  toggleBtn.setAttribute("type", "button");

  const sourceList = document.createElement("div");
  sourceList.className = "source-list";
  sourceList.setAttribute("role", "list");
  sourceList.style.display = "none";

  sources.forEach((source, index) => {
    const sourceItem = document.createElement("div");
    sourceItem.className = "source-item";
    sourceItem.setAttribute("role", "listitem");
    sourceItem.innerHTML = `
      <span class="source-index">${index + 1}</span>
      <div class="source-info">
        <div class="source-title">${source.title || "未知来源"}</div>
        <div class="source-ref">${source.source || ""}</div>
      </div>
    `;
    sourceList.appendChild(sourceItem);
  });

  toggleBtn.addEventListener("click", () => {
    const isExpanded = toggleBtn.getAttribute("aria-expanded") === "true";
    toggleBtn.setAttribute("aria-expanded", !isExpanded);
    sourceList.style.display = isExpanded ? "none" : "block";
    toggleBtn.querySelector(".source-icon").textContent = isExpanded ? "📚" : "📖";
  });

  container.appendChild(toggleBtn);
  container.appendChild(sourceList);
  return container;
}

// Quick Reply configuration - 槽位填充快捷选项
const QUICK_REPLIES_MAP = {
  // 主要症状（后端 key: symptom/symptoms）
  'symptom': ['发烧', '咳嗽', '流鼻涕', '呕吐', '腹泻', '皮疹', '哭闹不安', '其他'],
  'symptoms': ['发烧', '咳嗽', '流鼻涕', '呕吐', '腹泻', '皮疹', '哭闹不安', '其他'],
  '主要症状': ['发烧', '咳嗽', '流鼻涕', '呕吐', '腹泻', '皮疹', '哭闹不安', '其他'],

  // 持续时间（后端 key: duration）
  'duration': ['刚刚发现', '半天', '1天', '2天', '3天', '一周以上'],
  '发烧持续时间': ['刚刚发现', '半天', '1天', '2天', '3天', '一周以上'],
  '持续时间': ['刚刚发现', '半天', '1天', '2天', '3天', '一周以上'],

  // 体温（后端 key: temperature）
  'temperature': ['37.5℃', '38.0℃', '38.5℃', '39.0℃', '39.5℃', '40.0℃', '不确定'],
  '体温': ['37.5℃', '38.0℃', '38.5℃', '39.0℃', '39.5℃', '40.0℃', '不确定'],

  // 精神状态（后端 key: mental_state）
  'mental_state': ['正常玩耍', '精神差/蔫', '嗜睡', '烦躁不安'],
  '精神状态': ['正常玩耍', '精神差/蔫', '嗜睡', '烦躁不安'],

  // 食欲（后端 key: appetite）
  'appetite': ['正常进食', '食欲减退', '拒食', '呕吐'],
  '食欲': ['正常进食', '食欲减退', '拒食', '呕吐'],
  '进食情况': ['正常进食', '食欲减退', '拒食', '呕吐'],

  // 进食情况（后端 key: food_intake）
  'food_intake': ['正常进食', '进食减少', '拒食', '呕吐'],

  // 尿量（后端 key: urine_output）
  'urine_output': ['正常', '偏少', '明显减少', '无尿'],
  '尿量': ['正常', '偏少', '明显减少', '无尿'],

  // 伴随症状（后端 key: accompanying_symptoms）
  'accompanying_symptoms': ['无', '咳嗽', '呕吐', '腹泻', '皮疹', '呼吸急促'],
  '伴随症状': ['无', '咳嗽', '呕吐', '腹泻', '皮疹', '呼吸急促'],

  // 咳嗽类型（后端 key: cough_type）
  'cough_type': ['干咳', '有痰咳', '犬吠样咳嗽', '痉挛性咳嗽'],
  '咳嗽类型': ['干咳', '有痰咳', '犬吠样咳嗽', '痉挛性咳嗽'],

  // 大便性状（后端 key: stool_character）
  'stool_character': ['水样便', '糊状便', '黏液便', '脓血便'],
  '大便性状': ['水样便', '糊状便', '黏液便', '脓血便'],

  // 呼吸
  '呼吸': ['平稳', '急促', '困难', '有异响'],

  // 活动力
  '活动力': ['正常', '减弱', '不愿动']
};

// Global reference for slot tracker components
let activeSlotTracker = null;
let activeQuickReplies = null;

// Listen for form cancellation
window.addEventListener("form-cancelled", () => {
  clearComposerProgress();
});

function clearComposerProgress() {
  if (composer.refs.progress) {
    composer.refs.progress.innerHTML = "";
  }
  activeSlotTracker = null;
  activeQuickReplies = null;
}

async function loadHistory() {
  if (!conversationId) return;
  try {
    const response = await fetch(`${API_BASE}/api/v1/chat/history/${conversationId}`);
    if (!response.ok) throw new Error("请求失败");
    const data = await response.json();
    const messages = data.data.messages || [];
    chat.innerHTML = "";
    messages.forEach((item) => {
      appendMessage(item.role, item.content);
    });
  } catch (err) {
    showBanner("历史记录加载失败。", "info");
  }
}

async function loadConversations() {
  // 🎨 软登录检查：优先检查 localStorage 中的用户 ID
  const userId = localStorage.getItem('pediatric_user_id');

  if (!userId) {
    // 没有用户 ID，显示登录遮罩层
    const loginModal = document.getElementById('login-modal');
    loginModal.classList.add('show');

    // 暂停其他初始化，等待用户登录
    console.log('[LOGIN] No user ID found, showing login modal');
    return;
  }

  // 🎨 验证用户 ID（调用后端 API）
  try {
    const validateResponse = await fetch(`${API_BASE}/api/v1/auth/user/${userId}`);
    if (!validateResponse.ok) {
      // 后端验证失败，清除本地数据，重新登录
      console.warn('[LOGIN] User validation failed, clearing local data');
      localStorage.removeItem('pediatric_user_id');
      const loginModal = document.getElementById('login-modal');
      loginModal.classList.add('show');
      return;
    }
    const validateData = await validateResponse.json();
    if (!validateData.data?.valid) {
      // 用户 ID 无效
      console.warn('[LOGIN] User ID invalid');
      localStorage.removeItem('pediatric_user_id');
      const loginModal = document.getElementById('login-modal');
      loginModal.classList.add('show');
      return;
    }
  } catch (error) {
    // 后端 API 不可用，使用本地验证 fallback
    console.warn('[LOGIN] Backend validation unavailable, using local fallback:', error);
  }

  // 验证并使用用户 ID
  if (userId !== CURRENT_USER_ID) {
    console.warn('[LOGIN] User ID mismatch, updating:', userId);
    CURRENT_USER_ID = userId;
  }

  console.log('[LOGIN] User authenticated:', CURRENT_USER_ID);

  // 隐藏登录 Modal（如果存在）
  const loginModal = document.getElementById('login-modal');
  if (loginModal) {
    loginModal.classList.remove('show');
  }

  try {
    await syncActiveMember();

    const response = await fetch(`${API_BASE}/api/v1/chat/conversations/${userId}`);
    if (!response.ok) throw new Error("请求失败");
    const data = await response.json();
    const conversations = data.data.conversations || [];
    conversationMemberMap = {};
    conversations.forEach((c) => {
      conversationMemberMap[c.conversation_id] = c.member_id || null;
    });
    conversationSidebar.renderConversations(conversations);

    // 页面刷新后，自动加载最近对话（恢复上下文）
    // 只在初始加载时执行，避免清除后重新加载
    if (isInitialLoad && !conversationId && conversations.length > 0) {
      const latestId = conversationSidebar.getLatestConversationId();
      if (latestId) {
        console.log(`[REFRESH] Auto-loading latest conversation: ${latestId}`);
        const latestMemberId = conversationMemberMap[latestId];
        if (latestMemberId && latestMemberId !== currentMemberId) {
          const member = cachedMembers.find((m) => m.id === latestMemberId);
          currentMemberId = latestMemberId;
          currentMemberName = member?.name || "默认成员";
          persistActiveMember(currentMemberId);
          syncMemberUIEverywhere();
        }
        conversationId = latestId;
        conversationSidebar.setActive(latestId);
        await loadHistory();
      }
    } else if (conversationId) {
      // 如果已有 conversationId，设置活跃状态
      conversationSidebar.setActive(conversationId);
    }

    isInitialLoad = false;
  } catch (err) {
    console.error("加载对话列表失败:", err);
    conversationSidebar.renderConversations([]);
  }
}

async function handleNewConversation() {
  const userId = CURRENT_USER_ID;
  try {
    const response = await fetch(`${API_BASE}/api/v1/chat/conversations/${userId}`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("请求失败");
    const data = await response.json();

    // Clear current chat
    conversationId = data.data.conversation_id;
    chat.innerHTML = "";
    appendMessage("assistant", "已创建新对话，请描述宝宝的症状或用药问题。");

    // Reload conversation list
    await loadConversations();

    // Close sidebar on mobile
    conversationSidebar.element.classList.remove("open");
    sidebarBackdrop.classList.remove("open");

    showBanner("已创建新对话", "info");
  } catch (err) {
    console.error("创建对话失败:", err);
    showBanner("创建对话失败，请重试。", "info");
  }
}

async function handleSwitchConversation(convId) {
  const boundMemberId = conversationMemberMap[convId];
  if (boundMemberId && boundMemberId !== currentMemberId) {
    const member = cachedMembers.find((m) => m.id === boundMemberId);
    currentMemberId = boundMemberId;
    currentMemberName = member?.name || "默认成员";
    persistActiveMember(currentMemberId);
    syncMemberUIEverywhere();
  }
  conversationId = convId;

  // Load messages
  await loadHistory();

  // Update active state
  conversationSidebar.setActive(convId);

  // Close sidebar on mobile
  conversationSidebar.element.classList.remove("open");
  sidebarBackdrop.classList.remove("open");
}

async function handleDeleteConversation(convId) {
  if (!confirm("确定要删除这个对话吗？")) {
    return;
  }

  const userId = CURRENT_USER_ID;
  try {
    const response = await fetch(`${API_BASE}/api/v1/chat/conversations/${userId}/${convId}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error("请求失败");

    // If deleted conversation was current, clear chat
    if (conversationId === convId) {
      conversationId = null;
      chat.innerHTML = "";
    }

    // Reload conversation list
    await loadConversations();

    showBanner("对话已删除", "info");
  } catch (err) {
    console.error("删除对话失败:", err);
    showBanner("删除对话失败，请重试。", "info");
  }
}

function showBanner(message, tone = "info") {
  let banner = chat.querySelector(".chat-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.className = "chat-banner";
    banner.setAttribute("role", "status");
    banner.setAttribute("aria-live", "polite");
    chat.appendChild(banner);
  }
  banner.textContent = message;
  banner.classList.remove("info", "warn", "success");
  banner.classList.add(tone);
  banner.dataset.visible = "true";
}

function hideBanner() {
  const banner = chat.querySelector(".chat-banner");
  if (!banner) return;
  banner.dataset.visible = "false";
}

function openSheet() {
  sourceSheet.sheet.classList.add("open");
  sourceSheet.backdrop.classList.add("open");
}

function closeSheet() {
  sourceSheet.sheet.classList.remove("open");
  sourceSheet.backdrop.classList.remove("open");
}

async function fetchSource(entryId) {
  sourceSheet.refs.sourceName.textContent = "加载中...";
  sourceSheet.refs.sourceTitle.textContent = "-";
  sourceSheet.refs.sourceContent.textContent = "正在获取原文片段...";
  openSheet();

  try {
    const response = await fetch(`${API_BASE}/api/v1/chat/source/${entryId}`);
    if (!response.ok) {
      throw new Error("请求失败");
    }
    const data = await response.json();
    sourceSheet.refs.sourceName.textContent = data.data.source || "-";
    sourceSheet.refs.sourceTitle.textContent = data.data.title || "-";
    sourceSheet.refs.sourceContent.textContent = data.data.content || "暂无内容";
  } catch (err) {
    sourceSheet.refs.sourceName.textContent = "未知来源";
    sourceSheet.refs.sourceTitle.textContent = "未获取到内容";
    sourceSheet.refs.sourceContent.textContent = "当前无法获取原文片段，请稍后重试。";
  }
}

/**
 * Create a "thinking" loading bubble
 * @returns {Object} - Element and remove method
 */
function createThinkingBubble() {
  const section = document.createElement("section");
  section.className = "message assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble bubble-thinking";
  bubble.innerHTML = `
    <div class="thinking-indicator">
      <div class="thinking-dots">
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
        <span class="thinking-dot"></span>
      </div>
      <span class="thinking-text">正在分析中...</span>
    </div>
  `;

  section.appendChild(bubble);

  return {
    element: section,
    remove() {
      section.classList.add("thinking-exit");
      setTimeout(() => section.remove(), 200);
    },
  };
}

/**
 * Render quick replies for slot filling
 * @param {Object} metadata - Metadata containing missing_slots
 */
function renderQuickReplies(metadata) {
  showBanner("提示：需要补充关键信息后才能给出更准确建议。", "info");
  clearComposerProgress();

  // 移除之前的 quick-replies（防止叠加）
  const prevQuickReplies = chat.querySelector(".inline-quick-replies");
  if (prevQuickReplies) {
    prevQuickReplies.remove();
  }

  // 解析 missing_slots - 兼容数组和对象两种格式
  let slotKeys = [];
  let slotDefs = {};

  const rawSlots = metadata.missing_slots;

  // 防御性检查：missing_slots 为 falsy / 数字 / 空
  if (!rawSlots || typeof rawSlots === 'number' || typeof rawSlots === 'string') {
    console.warn('[Slot Filling] missing_slots 无效:', rawSlots);
    return;
  }

  if (Array.isArray(rawSlots)) {
    // 数组格式: ["symptom", "duration"]
    slotKeys = rawSlots.filter(k => typeof k === 'string' && k.trim());
    slotKeys.forEach(key => {
      slotDefs[key] = { label: key, options: [] };
    });
  } else if (typeof rawSlots === 'object') {
    // 对象格式: {"symptom": {"label": "症状", "options": [...]}}
    slotKeys = Object.keys(rawSlots);
    slotDefs = rawSlots;
  }

  if (slotKeys.length === 0) {
    console.warn('[Slot Filling] missing_slots 为空');
    return;
  }

  const currentSlotKey = slotKeys[0];
  const currentSlotDef = slotDefs[currentSlotKey] || {};

  // 获取 label - 多重 fallback
  const SLOT_LABEL_MAP = {
    'symptom': '主要症状',
    'symptoms': '主要症状',
    'duration': '持续时间',
    'temperature': '体温',
    'mental_state': '精神状态',
    'appetite': '食欲情况',
    'urine_output': '尿量',
    'food_intake': '进食情况',
    'accompanying_symptoms': '伴随症状',
    'cough_type': '咳嗽类型',
    'stool_character': '大便性状',
  };
  const currentSlotLabel = currentSlotDef.label || SLOT_LABEL_MAP[currentSlotKey] || currentSlotKey || '信息';

  // 获取选项 - 优先后端 options，fallback 到前端预设
  let chips = [];
  if (currentSlotDef.options && Array.isArray(currentSlotDef.options) && currentSlotDef.options.length > 0) {
    chips = currentSlotDef.options.map(opt => {
      if (typeof opt === 'string') return opt;
      return opt.label || opt.value;
    });
  } else {
    chips = QUICK_REPLIES_MAP[currentSlotKey] || QUICK_REPLIES_MAP[currentSlotLabel] || [];
  }

  console.log('[Slot Filling] currentSlotKey:', currentSlotKey, 'label:', currentSlotLabel, 'chips:', chips);

  // 判断是否支持多选（symptom/symptoms/accompanying_symptoms 等支持多选）
  const MULTI_SELECT_SLOTS = ['symptom', 'symptoms', 'accompanying_symptoms', '伴随症状'];
  const allowMultiSelect = MULTI_SELECT_SLOTS.includes(currentSlotKey);

  // 创建 Quick Replies 容器
  const quickRepliesContainer = document.createElement("div");
  quickRepliesContainer.className = "inline-quick-replies";

  // 提示文字
  const promptText = document.createElement("div");
  promptText.className = "inline-quick-replies__prompt";
  if (chips.length === 0) {
    promptText.textContent = `请描述${currentSlotLabel}：`;
  } else if (allowMultiSelect) {
    promptText.textContent = `请选择${currentSlotLabel}（可多选）：`;
  } else {
    promptText.textContent = `请选择或描述${currentSlotLabel}：`;
  }
  quickRepliesContainer.appendChild(promptText);

  // 选中的值（多选模式用数组，单选模式用字符串）
  let selectedValues = [];

  // 快捷按钮
  if (chips && chips.length > 0) {
    const chipsWrapper = document.createElement("div");
    chipsWrapper.className = "inline-quick-replies__chips";

    chips.forEach(chip => {
      const btn = document.createElement("button");
      btn.className = "inline-reply-chip";
      btn.textContent = chip;
      btn.dataset.value = chip;
      btn.dataset.selected = "false";

      btn.addEventListener("click", () => {
        if (allowMultiSelect) {
          // 多选模式：切换选中状态
          const isSelected = btn.dataset.selected === "true";
          if (isSelected) {
            // 取消选中
            btn.dataset.selected = "false";
            btn.classList.remove("selected");
            selectedValues = selectedValues.filter(v => v !== chip);
          } else {
            // 选中
            btn.dataset.selected = "true";
            btn.classList.add("selected");
            selectedValues.push(chip);
          }
          // 更新确认按钮状态
          updateConfirmButtonState();
        } else {
          // 单选模式：直接发送
          appendMessage("user", chip);
          quickRepliesContainer.remove();
          clearComposerProgress();
          sendMessageStream(chip);
        }
      });

      chipsWrapper.appendChild(btn);
    });

    quickRepliesContainer.appendChild(chipsWrapper);
  }

  // 底部操作区（输入框 + 按钮）
  const actionWrapper = document.createElement("div");
  actionWrapper.className = "inline-quick-replies__action-wrapper";

  // 文本输入框（混合模式）
  const inputWrapper = document.createElement("div");
  inputWrapper.className = "inline-quick-replies__input-wrapper";

  const textInput = document.createElement("input");
  textInput.type = "text";
  textInput.className = "inline-quick-replies__input";
  textInput.placeholder = chips.length > 0 ? `或手动输入${currentSlotLabel}...` : `请输入${currentSlotLabel}...`;

  // 确认按钮（多选模式显示，或混合输入时使用）
  const confirmBtn = document.createElement("button");
  confirmBtn.className = "inline-quick-replies__confirm";
  confirmBtn.textContent = allowMultiSelect ? "选好了" : "发送";

  // 更新确认按钮状态
  function updateConfirmButtonState() {
    const hasInput = textInput.value.trim().length > 0;
    const hasSelection = selectedValues.length > 0;
    confirmBtn.disabled = !hasInput && !hasSelection;
    if (allowMultiSelect && hasSelection && selectedValues.length > 0) {
      confirmBtn.textContent = `确认提交 (${selectedValues.length}项)`;
    } else if (hasInput) {
      confirmBtn.textContent = "发送";
    } else {
      confirmBtn.textContent = allowMultiSelect ? "选好了" : "发送";
    }
  }

  textInput.addEventListener("input", updateConfirmButtonState);

  // 发送逻辑
  function sendValues() {
    const inputValue = textInput.value.trim();
    // 合并选中的 chips 和手动输入的内容
    let allValues = [...selectedValues];
    if (inputValue) {
      // 检查是否已包含该值
      if (!allValues.includes(inputValue)) {
        allValues.push(inputValue);
      }
    }

    if (allValues.length > 0) {
      const message = allValues.join("、");
      appendMessage("user", message);
      quickRepliesContainer.remove();
      clearComposerProgress();
      sendMessageStream(message);
    }
  }

  confirmBtn.addEventListener("click", sendValues);

  textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendValues();
    }
  });

  inputWrapper.appendChild(textInput);
  actionWrapper.appendChild(inputWrapper);
  actionWrapper.appendChild(confirmBtn);
  quickRepliesContainer.appendChild(actionWrapper);

  // 初始化确认按钮状态
  updateConfirmButtonState();

  // 添加到 chat 末尾（在 assistant 消息之后）
  chat.appendChild(quickRepliesContainer);
  forceScrollToBottom();
  textInput.focus();
}

/**
 * Send message with streaming output
 * @param {string} text - User message
 * @param {number} retryCount - Current retry attempt
 */
async function sendMessageStream(text, retryCount = 0) {
  if (!currentMemberId) {
    showBanner("请先选择或创建就诊人后再问诊。", "warn");
    await showConsultMemberSelector();
    return;
  }
  const MAX_RETRIES = 3;
  const startTime = performance.now();
  let firstTokenTime = null;
  let streamBubble = null;
  let metadata = null;
  let streamDone = false;
  let accumulatedText = ""; // 累积原始文本，用于实时格式化
  let formatTimer = null;   // 防抖定时器

  // 显示 "思考中" 气泡
  const thinkingBubble = createThinkingBubble();
  const empty = chat.querySelector(".chat-empty");
  if (empty) empty.remove();
  chat.appendChild(thinkingBubble.element);
  forceScrollToBottom(); // 用户发送消息后强制滚动

  // ✅ 添加调试日志：显示发送时的 conversationId
  console.log(`[SEND] conversationId: ${conversationId}, message: ${text.substring(0, 30)}...`);
  console.log(`[SEND] Full payload:`, {
    conversation_id: conversationId,
    user_id: CURRENT_USER_ID,
    member_id: currentMemberId,
    message: text
  });

  // 实时格式化函数（防抖，避免频繁重渲染）
  function scheduleFormat() {
    if (formatTimer) clearTimeout(formatTimer);
    formatTimer = setTimeout(() => {
      if (streamBubble && accumulatedText) {
        const formatted = formatMessage(accumulatedText);
        streamBubble.bubble.innerHTML = formatted;
        // 重新添加光标
        const cursor = document.createElement("span");
        cursor.className = "stream-cursor";
        cursor.textContent = "▋";
        streamBubble.bubble.appendChild(cursor);
        streamBubble.cursor = cursor;
        // 流式输出时检查是否应该自动滚动
        if (shouldAutoScroll()) {
          scrollToBottom(false);
        }
      }
    }, 80);
  }

  try {
    const response = await fetch(`${API_BASE}/api/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: CURRENT_USER_ID,
        conversation_id: conversationId,
        member_id: currentMemberId,
        message: text,
      }),
    });

    if (!response.ok) {
      thinkingBubble.remove();
      const errorPayload = await response.json().catch(() => ({}));
      const detail = errorPayload.detail || {};
      if (detail.code === "need_member_creation") {
        showBanner("请先在健康档案创建就诊人后再开始问诊。", "warn");
        return;
      }
      if (detail.code === "need_member_selection") {
        showBanner("请先选择就诊人。", "warn");
        await showConsultMemberSelector();
        return;
      }
      if (detail.code === "member_mismatch") {
        showBanner("当前会话已绑定其他就诊人，请切换后新建会话。", "warn");
        return;
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    // Read the stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      // Decode chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const jsonStr = line.slice(6).trim();

          if (!jsonStr) continue;

          try {
            const data = JSON.parse(jsonStr);

            // Handle metadata chunks
            if (data.type === "metadata" && data.metadata) {
              metadata = data.metadata;

              if (metadata.error === "member_mismatch") {
                showBanner("当前会话已绑定其他就诊人，请先切换后开启新会话。", "warn");
              }
              if (metadata.error === "bad_request" && metadata.message) {
                showBanner(metadata.message, "warn");
              }

              // Handle danger signals - show modal
              if (metadata.danger_signal) {
                const dangerModal = createDangerSignalModal([
                  "检测到危险信号，请立即就医！",
                ]);
                document.body.appendChild(dangerModal.element);
                dangerModal.show();

                // Show warning banner
                showBanner("⚠️ 系统识别到急症风险，请立即就医或拨打 120。", "warn");
              }

              // Handle blocked content
              if (metadata.blocked) {
                showBanner("提示：该问题涉及安全红线，已触发系统拦截。", "warn");
              }

              // Note: follow-up quick replies 将在 done 事件后创建
              // 因为需要等 assistant 消息先渲染到 chat 中

              continue;
            }

            // Record first token latency
            if (firstTokenTime === null && data.type === "content") {
              firstTokenTime = performance.now();
              const latency = ((firstTokenTime - startTime) / 1000).toFixed(2);
              console.log(`⚡ First-token latency: ${latency}s`);

              if (parseFloat(latency) > 1.5) {
                console.warn(`⚠️ First-token latency exceeded 1.5s target`);
              }

              // 移除 thinking 气泡，创建 stream 气泡
              thinkingBubble.remove();
            }

            // Handle content chunks
            if (data.type === "content" && data.content) {
              // Create stream bubble if it doesn't exist
              if (!streamBubble) {
                streamBubble = createStreamBubble({ role: "assistant", initialText: "" });
                chat.appendChild(streamBubble.element);
                // 监听流式气泡的高度变化
                if (chatResizeObserver) {
                  chatResizeObserver.observe(streamBubble.element);
                }
              }

              accumulatedText += data.content;
              streamBubble.appendText(data.content);

              // 流式输出时检查是否应该自动滚动
              if (shouldAutoScroll()) {
                scrollToBottom(false);
              }

              // 触发实时格式化（防抖）
              scheduleFormat();
            } else if (data.type === "abort" && data.content) {
              thinkingBubble.remove();
              if (streamBubble) {
                streamBubble.bubble.classList.add("stream-error");
                streamBubble.bubble.innerHTML = formatMessage(data.content);
                streamBubble.cursor.remove();
              } else {
                const errorBubble = createStreamBubble({ role: "assistant", initialText: "" });
                errorBubble.bubble.classList.add("stream-error");
                errorBubble.bubble.innerHTML = formatMessage(data.content);
                errorBubble.cursor.remove();
                chat.appendChild(errorBubble.element);
              }
              // 错误消息强制滚动到底部
              forceScrollToBottom();
              showBanner("⚠️ 安全警示：该回复已被系统拦截。", "warn");
            } else if (data.type === "done") {
              // 清除防抖定时器
              if (formatTimer) clearTimeout(formatTimer);

              streamDone = true;
              thinkingBubble.remove();

              // 从 done 事件中提取 conversation_id 并更新本地变量
              if (data.conversation_id) {
                conversationId = data.conversation_id;
                console.log(`📋 更新 conversation_id: ${conversationId}`);
              }

              if (streamBubble) {
                // 最终格式化
                const formattedHTML = formatMessage(accumulatedText);
                if (streamBubble.cursor && streamBubble.cursor.parentNode) {
                  streamBubble.cursor.remove();
                }
                streamBubble.bubble.innerHTML = formattedHTML;
                streamBubble.bubble.classList.remove("bubble-stream");

                // Add triage card if needed
                if (metadata && metadata.triage_level && metadata.intent === "triage") {
                  const triageCard = createTriageResultCard({
                    level: metadata.triage_level,
                    reason: "根据症状分析",
                    action: accumulatedText,
                  });
                  streamBubble.bubble.innerHTML = "";
                  streamBubble.bubble.appendChild(triageCard);
                }

                // Add source toggle if sources exist
                if (metadata && metadata.sources && metadata.sources.length > 0) {
                  const sourceToggle = createSourceToggle(metadata.sources);
                  streamBubble.bubble.appendChild(sourceToggle);
                }
              }

              // ===== 在 done 后创建 Quick Replies（确保位置在 assistant 消息之后）=====
              const hasValidSlots = metadata
                && metadata.need_follow_up
                && metadata.missing_slots
                && typeof metadata.missing_slots === 'object'
                && (Array.isArray(metadata.missing_slots)
                  ? metadata.missing_slots.length > 0
                  : Object.keys(metadata.missing_slots).length > 0);

              if (hasValidSlots) {
                renderQuickReplies(metadata);
              } else {
                // 无 follow-up 时正常滚动
                forceScrollToBottom();
              }

              if (firstTokenTime) {
                const totalLatency = ((performance.now() - startTime) / 1000).toFixed(2);
                console.log(`✅ Streaming complete in ${totalLatency}s`);
              }
            }
          } catch (parseError) {
            console.error("Failed to parse SSE data:", jsonStr, parseError);
          }
        }
      }
    }

    // Clean up (only if "done" event was NOT already processed)
    if (formatTimer) clearTimeout(formatTimer);
    thinkingBubble.remove();

    if (streamBubble && !streamDone) {
      if (accumulatedText) {
        const formattedHTML = formatMessage(accumulatedText);
        if (streamBubble.cursor && streamBubble.cursor.parentNode) {
          streamBubble.cursor.remove();
        }
        streamBubble.bubble.innerHTML = formattedHTML;
        streamBubble.bubble.classList.remove("bubble-stream");
      } else {
        streamBubble.complete();
      }
      // 最终滚动到底部
      forceScrollToBottom();
    }

    // Reload conversation list to update metadata
    await loadConversations();

  } catch (err) {
    console.error("Streaming error:", err);
    if (formatTimer) clearTimeout(formatTimer);
    thinkingBubble.remove();

    // Retry logic
    if (retryCount < MAX_RETRIES) {
      console.log(`Retrying... (${retryCount + 1}/${MAX_RETRIES})`);
      await new Promise((resolve) => setTimeout(resolve, 1000 * (retryCount + 1)));
      return sendMessageStream(text, retryCount + 1);
    }

    // Show error in chat
    const errorBubble = createStreamBubble({ role: "assistant", initialText: "" });
    errorBubble.bubble.classList.add("stream-error");
    errorBubble.bubble.innerHTML = "连接失败，请稍后重试。";
    errorBubble.cursor.remove();
    chat.appendChild(errorBubble.element);
    // 错误消息强制滚动到底部
    forceScrollToBottom();
    showBanner("连接失败，请检查网络或稍后重试。", "info");
  }
}

chat.addEventListener("click", (event) => {
  const target = event.target;
  if (target.classList.contains("citation")) {
    const text = target.textContent || "";
    const match = text.match(/【来源:([^】]+)】/);
    if (match) {
      fetchSource(match[1]);
    }
  }
});

document.querySelectorAll("[data-sheet-close]").forEach((el) => {
  el.addEventListener("click", closeSheet);
});

// ============ 归档对话功能 ============
header.addEventListener("archive-conversation", async () => {
  if (!conversationId) {
    showBanner("当前没有活跃对话", "info");
    return;
  }

  // 优先使用当前就诊人，避免归档落到错误成员
  if (currentMemberId) {
    try {
      await performArchive(conversationId, currentMemberId);
    } catch (error) {
      if (error.code === "member_mismatch") {
        showBanner("当前会话已绑定其他就诊人，请切换后新建会话。", "warn");
      } else if (error.code === "need_member_creation") {
        showBanner("请先创建就诊人档案后再归档。", "warn");
      } else if (error.code === "need_member_selection") {
        await showMemberSelector(conversationId);
      } else {
        showBanner("归档失败，请重试。", "warn");
      }
    }
    return;
  }

  // 无当前成员时，保留旧兼容流程
  try {
    await performArchive(conversationId, null);
  } catch (error) {
    if (error.code === "need_member_selection" || error.status === 400) {
      await showMemberSelector(conversationId);
    } else if (error.code === "need_member_creation") {
      showBanner("请先创建就诊人档案后再归档。", "warn");
    } else {
      console.error('[ARCHIVE] Failed to archive:', error);
      showBanner("归档失败，请重试", "info");
    }
  }
});

/**
 * 显示成员选择器（当用户有多个成员时）
 * @param {string} convId - 对话 ID
 */
async function showMemberSelector(convId) {
  try {
    // 获取用户的所有成员
    const membersResponse = await fetch(`${API_BASE}/api/v1/profile/${CURRENT_USER_ID}/members`);

    if (!membersResponse.ok) {
      throw new Error('获取成员列表失败');
    }

    const membersData = await membersResponse.json();
    const members = membersData.data?.members || [];

    if (members.length === 0) {
      // 无成员，直接归档
      await performArchive(convId, null);
      return;
    }

    // 显示成员选择器
    const archiveModal = createArchiveConfirmModal({
      multiMember: true,
      members: members,
      onConfirm: async (selectedMemberId) => {
        await performArchive(convId, selectedMemberId);
      },
      onCancel: () => {
        console.log('[ARCHIVE] User cancelled archive');
      }
    });
    archiveModal.show();

  } catch (error) {
    console.error('[ARCHIVE] Failed to show member selector:', error);
    showBanner("获取成员列表失败，请重试", "info");
  }
}

/**
 * 执行归档操作
 * @param {string} convId - 对话 ID
 * @param {string|null} memberId - 成员 ID（可选）
 * @throws {Object} - 错误对象包含 status 和 message
 */
async function performArchive(convId, memberId) {
  const userId = getUserId();

  if (!userId) {
    console.error('[ARCHIVE] Missing user_id');
    showBanner("无法获取用户信息，请尝试重新登录", "warn");
    return;
  }

  // 禁用归档按钮 + 显示加载状态
  const archiveBtn = header.querySelector("#archive-conversation-btn");
  if (archiveBtn) {
    archiveBtn.disabled = true;
    archiveBtn.classList.add("loading");
  }
  showBanner("正在归档对话，请稍候…", "info");

  const payload = {
    user_id: userId
  };
  if (memberId) {
    payload.member_id = memberId;
  }

  console.log('[ARCHIVE] Sending archive request:', payload);

  try {
    const archiveResponse = await fetch(`${API_BASE}/api/v1/chat/conversations/${convId}/archive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!archiveResponse.ok) {
      const errorData = await archiveResponse.json().catch(() => ({}));
      const detail = errorData.detail || {};
      const error = new Error(
        typeof detail === "string" ? detail : (detail.message || '归档失败')
      );
      error.status = archiveResponse.status;
      error.code = detail.code;
      throw error;
    }

    const data = await archiveResponse.json();
    const summary = data.data?.summary || "对话已归档";
    const extraction = data.data?.health_extraction || {};

    // 构建成功提示信息
    let successMsg = `归档成功！${summary.substring(0, 40)}`;
    const extractionParts = [];
    if (extraction.consultation) extractionParts.push(`${extraction.consultation}条问诊记录`);
    if (extraction.allergy) extractionParts.push(`${extraction.allergy}条过敏记录`);
    if (extraction.medication) extractionParts.push(`${extraction.medication}条用药记录`);
    if (extraction.checkup) extractionParts.push(`${extraction.checkup}条体征记录`);
    if (extractionParts.length > 0) {
      successMsg += `（已提取${extractionParts.join("、")}）`;
    }

    showBanner(successMsg, "success");

    // 清空当前对话
    conversationId = null;
    chat.innerHTML = "";
    const welcome = createWelcomeScreen();
    chat.appendChild(welcome);

    // 重新加载对话列表
    await loadConversations();
  } finally {
    // 恢复归档按钮状态
    if (archiveBtn) {
      archiveBtn.disabled = false;
      archiveBtn.classList.remove("loading");
    }
  }
}

// Load conversations on startup
loadConversations();

async function sendMessage() {
  const text = composer.refs.input.value.trim();
  if (!text) return;
  if (!currentMemberId) {
    showBanner("请先选择或创建就诊人后再问诊。", "warn");
    await showConsultMemberSelector();
    return;
  }

  hideBanner();
  appendMessage("user", text);
  composer.refs.input.value = "";

  // 禁用输入，防止重复发送
  composer.refs.button.disabled = true;
  composer.refs.input.disabled = true;

  try {
    await sendMessageStream(text);
  } finally {
    composer.refs.button.disabled = false;
    composer.refs.input.disabled = false;
    composer.refs.input.focus();
  }
}

composer.refs.button.addEventListener("click", () => {
  showBanner("更多功能入口开发中，可直接按 Enter 发送消息。", "info");
});
composer.refs.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    sendMessage();
  }
});

composer.refs.voiceToggle?.addEventListener("click", () => {
  showBanner("语音输入功能开发中，暂可使用文字输入。", "info");
});

// ============ 健康档案数据加载 ============

// 显示加载状态
function showHealthLoading(show = true) {
  const dashboard = healthDashboard.element;
  if (show) {
    dashboard.classList.add("loading");
    // 添加加载遮罩
    if (!dashboard.querySelector(".health-loading-overlay")) {
      const overlay = document.createElement("div");
      overlay.className = "health-loading-overlay";
      overlay.innerHTML = `
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      `;
      dashboard.appendChild(overlay);
    }
  } else {
    dashboard.classList.remove("loading");
    const overlay = dashboard.querySelector(".health-loading-overlay");
    if (overlay) overlay.remove();
  }
}

// 显示错误状态
function showHealthError(message) {
  const dashboard = healthDashboard.element;
  // 移除加载遮罩
  const overlay = dashboard.querySelector(".health-loading-overlay");
  if (overlay) overlay.remove();

  // 显示错误提示
  const errorBanner = dashboard.querySelector(".health-error-banner") || document.createElement("div");
  errorBanner.className = "health-error-banner";
  errorBanner.innerHTML = `
    <span class="health-error-banner__icon">⚠️</span>
    <span class="health-error-banner__text">${message}</span>
    <button class="health-error-banner__retry">重试</button>
  `;

  const existing = dashboard.querySelector(".health-error-banner");
  if (!existing) {
    dashboard.insertBefore(errorBanner, dashboard.firstChild);
  }

  const retryBtn = errorBanner.querySelector(".health-error-banner__retry");
  if (retryBtn) {
    retryBtn.addEventListener("click", loadHealthData);
  }
}

// ============ 🎨 软登录功能 ============

/**
 * 初始化登录功能
 */
function initLoginFeature() {
  const loginInput = document.getElementById('login-input');
  const loginButton = document.getElementById('login-button');

  // 登录按钮点击事件
  loginButton.addEventListener('click', handleLoginSubmit);

  // 输入框回车事件
  loginInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      handleLoginSubmit();
    }
  });

  // 输入框输入事件（实时清理）
  loginInput.addEventListener('input', (event) => {
    const value = event.target.value.trim();
    // 移除空格和特殊字符，只保留字母、数字、下划线
    const cleaned = value.replace(/[^a-zA-Z0-9\-]/g, '');
    event.target.value = cleaned;
  });
}

/**
 * 处理登录提交
 */
async function handleLoginSubmit() {
  const loginInput = document.getElementById('login-input');
  const userId = loginInput.value.trim();

  if (!userId) {
    alert('请输入邮箱或昵称');
    return;
  }

  // 简单清理（去除首尾空格、转小写）
  let cleanedUserId = userId.trim().toLowerCase().replace(/\s+/g, '');

  // 生成简单的用户ID（可以根据需要改为 UUID）
  const generatedUserId = 'user_' + cleanedUserId.replace(/[^a-z0-9]/g, '');

  try {
    // 🎨 调用后端 API 注册/验证用户
    const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: generatedUserId,
        display_name: userId.trim()
      })
    });

    if (!response.ok) {
      // Fallback: 如果后端未实现，使用前端本地存储
      console.warn('[LOGIN] Backend register not available, using local storage');
      localStorage.setItem('pediatric_user_id', generatedUserId);
      CURRENT_USER_ID = generatedUserId;
    } else {
      const data = await response.json();
      // 使用后端返回的 user_id
      const validatedUserId = data.data?.user_id || generatedUserId;
      localStorage.setItem('pediatric_user_id', validatedUserId);
      CURRENT_USER_ID = validatedUserId;
      console.log('[LOGIN] User registered via backend:', validatedUserId);
    }

  } catch (error) {
    // 网络错误或后端未实现，使用本地存储 fallback
    console.warn('[LOGIN] Backend call failed, using local storage:', error);
    localStorage.setItem('pediatric_user_id', generatedUserId);
    CURRENT_USER_ID = generatedUserId;
  }

  console.log('[LOGIN] User logged in:', CURRENT_USER_ID);

  // 隐藏登录 Modal
  const loginModal = document.getElementById('login-modal');
  loginModal.classList.remove('show');

  // 重新加载对话列表（使用新的 user_id）
  await loadConversations();

  // 显示成功提示（根据时间显示问候语）
  const hour = new Date().getHours();
  let greeting;
  if (hour >= 6 && hour < 12) {
    greeting = '上午好';
  } else if (hour >= 12 && hour < 14) {
    greeting = '中午好';
  } else if (hour >= 14 && hour < 19) {
    greeting = '下午好';
  } else {
    greeting = '晚上好';
  }
  showBanner(`${greeting}，${cleanedUserId}！`, 'success');
}

// 页面加载时初始化登录功能
document.addEventListener('DOMContentLoaded', () => {
  // 延迟执行，确保 DOM 已完全加载
  setTimeout(() => {
    initLoginFeature();
  }, 100);
});

// ============ 🎨 软登录功能 ============

// ============ 归档提示功能 ============

// 30分钟计时器
let conversationStartTime = null;
let thirtyMinuteTimer = null;

// 启动30分钟计时器
function startThirtyMinuteTimer() {
  conversationStartTime = Date.now();
  clearTimeout(thirtyMinuteTimer);

  thirtyMinuteTimer = setTimeout(() => {
    if (conversationId) {
      showBanner("💡 提示：对话已持续30分钟，建议归档保存到健康档案", "info");
    }
  }, 30 * 60 * 1000); // 30分钟
}

// 重置计时器（当创建新对话或发送消息时）
function resetThirtyMinuteTimer() {
  if (conversationId) {
    startThirtyMinuteTimer();
  }
}

// 监听新对话创建
const originalHandleNewConversation = handleNewConversation;
handleNewConversation = async function() {
  await originalHandleNewConversation();
  startThirtyMinuteTimer();
};

// 监听消息发送（首条消息时启动计时器）
const originalSendMessageStream = sendMessageStream;
sendMessageStream = async function(text, retryCount = 0) {
  if (!conversationStartTime && conversationId) {
    startThirtyMinuteTimer();
  }
  return await originalSendMessageStream(text, retryCount);
};

// beforeunload 事件：页面关闭前提示归档
window.addEventListener('beforeunload', (event) => {
  // 仅当有活跃对话且对话时长超过5分钟时提示
  if (conversationId && conversationStartTime) {
    const duration = Date.now() - conversationStartTime;
    const fiveMinutes = 5 * 60 * 1000;

    if (duration > fiveMinutes) {
      const message = '您有未归档的对话，确定要离开吗？';
      event.preventDefault(); // 标准写法
      event.returnValue = message; // Chrome 需要
      return message; // 旧版浏览器
    }
  }
});

// 显示空状态（无成员）
function showEmptyMemberState() {
  const dashboard = healthDashboard.element;
  dashboard.innerHTML = `
    <div class="health-empty-state">
      <div class="health-empty-state__icon">👶</div>
      <div class="health-empty-state__title">还没有健康档案</div>
      <div class="health-empty-state__text">
        创建健康档案，记录宝宝的健康数据，方便随时查看
      </div>
      <button class="health-empty-state__button" id="create-first-member">
        + 创建健康档案
      </button>
    </div>
  `;

  const createBtn = dashboard.querySelector("#create-first-member");
  if (createBtn) {
    createBtn.addEventListener("click", showCreateMemberForm);
  }
}

function renderHealthMemberSwitcher(members, activeMemberId) {
  const dashboard = healthDashboard.element;
  const existing = dashboard.querySelector(".health-member-switcher");
  if (existing) existing.remove();
  if (!members || members.length === 0) return;

  const wrap = document.createElement("div");
  wrap.className = "health-member-switcher";
  const active = members.find((m) => m.id === activeMemberId) || members[0];
  wrap.innerHTML = `
    <span class="health-member-switcher__label">当前就诊人</span>
    <button class="health-member-switcher__button" type="button">
      ${active?.name || "默认成员"} <span aria-hidden="true">⇅</span>
    </button>
  `;

  const button = wrap.querySelector(".health-member-switcher__button");
  button.addEventListener("click", () => {
    const modal = createMemberSelectorModal({
      members,
      activeMemberId,
      onConfirm: async (selectedMemberId) => {
        const member = members.find((m) => m.id === selectedMemberId);
        await switchActiveMember(selectedMemberId, member?.name);
        await loadHealthData();
      },
      onCancel: () => {}
    });
    modal.show();
  });

  dashboard.prepend(wrap);
}

async function loadHealthData() {
  const userId = CURRENT_USER_ID;

  // 移除错误提示
  const errorBanner = healthDashboard.element.querySelector(".health-error-banner");
  if (errorBanner) errorBanner.remove();

  // 显示加载状态
  showHealthLoading(true);

  try {
    // 加载成员列表
    const membersResponse = await fetch(`${API_BASE}/api/v1/profile/${userId}/members`);

    if (!membersResponse.ok) {
      throw new Error("获取成员列表失败");
    }

    const membersData = await membersResponse.json();

    if (membersData.data && membersData.data.members && membersData.data.members.length > 0) {
      const members = membersData.data.members;
      const selectedMember =
        members.find((m) => m.id === currentMemberId) ||
        members[0];
      currentMemberId = selectedMember.id;
      currentMemberName = selectedMember.name || "默认成员";
      persistActiveMember(currentMemberId);
      syncMemberUIEverywhere();

      // 重建健康仪表板内容
      rebuildHealthDashboard();
      renderHealthMemberSwitcher(members, selectedMember.id);
      await loadMemberDetail(selectedMember.id);
    } else {
      // 没有成员，显示空状态
      showEmptyMemberState();
    }
  } catch (err) {
    console.error("加载健康数据失败:", err);
    showHealthError("加载失败，请检查网络或稍后重试");
  } finally {
    showHealthLoading(false);
  }
}

// 重建健康仪表板（在空状态后）
function rebuildHealthDashboard() {
  const dashboard = healthDashboard.element;
  const wasEmpty = dashboard.querySelector(".health-empty-state");

  if (wasEmpty) {
    // 恢复原始内容
    const originalContent = `
      <section class="health-section">
        <h2 class="health-section__title">健康监测</h2>
        <div class="bmi-card" id="bmi-card">
          <div class="bmi-card__header">
            <span class="bmi-card__label">BMI指数</span>
            <button class="bmi-card__edit" id="edit-bmi-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </button>
          </div>
          <div class="bmi-card__body">
            <div class="bmi-card__value">--</div>
            <div class="bmi-card__status">--</div>
          </div>
          <div class="bmi-card__metrics">
            <div class="bmi-card__metric">
              <span class="bmi-card__metric-label">身高</span>
              <span class="bmi-card__metric-value" id="height-value">-- cm</span>
            </div>
            <div class="bmi-card__metric">
              <span class="bmi-card__metric-label">体重</span>
              <span class="bmi-card__metric-value" id="weight-value">-- kg</span>
            </div>
          </div>
          <div class="bmi-card__footer">
            <span class="bmi-card__update-time" id="bmi-update-time">--</span>
          </div>
        </div>
      </section>

      <div class="metrics-grid">
        <div class="metric-card" id="bp-card">
          <div class="metric-card__icon">🩺</div>
          <div class="metric-card__content">
            <div class="metric-card__label">血压</div>
            <div class="metric-card__value" id="bp-value">--</div>
            <div class="metric-card__unit">mmHg</div>
          </div>
          <button class="metric-card__add" data-metric="blood-pressure">+</button>
        </div>
        <div class="metric-card" id="sugar-card">
          <div class="metric-card__icon">🩸</div>
          <div class="metric-card__content">
            <div class="metric-card__label">血糖</div>
            <div class="metric-card__value" id="sugar-value">--</div>
            <div class="metric-card__unit">mmol/L</div>
          </div>
          <button class="metric-card__add" data-metric="blood-sugar">+</button>
        </div>
      </div>

      <div class="device-banner">
        <div class="device-banner__content">
          <span class="device-banner__icon">📱</span>
          <span class="device-banner__text">绑定智能设备，自动监测更多健康数据</span>
        </div>
        <button class="device-banner__button">去绑定</button>
      </div>

      <section class="health-section">
        <h2 class="health-section__title">健康记录</h2>
        <div class="record-grid">
          <button class="record-card" data-record="consultation">
            <span class="record-card__icon">👨‍⚕️</span>
            <span class="record-card__title">问诊记录</span>
            <span class="record-card__count" id="consultation-count">0</span>
          </button>
          <button class="record-card" data-record="prescription">
            <span class="record-card__icon">💊</span>
            <span class="record-card__title">处方记录</span>
            <span class="record-card__count" id="prescription-count">0</span>
          </button>
          <button class="record-card" data-record="appointment">
            <span class="record-card__icon">📅</span>
            <span class="record-card__title">挂号记录</span>
            <span class="record-card__count" id="appointment-count">0</span>
          </button>
          <button class="record-card" data-record="document">
            <span class="record-card__icon">📄</span>
            <span class="record-card__title">病历存档</span>
            <span class="record-card__count" id="document-count">0</span>
          </button>
          <button class="record-card" data-record="checkup">
            <span class="record-card__icon">🔬</span>
            <span class="record-card__title">体检检验</span>
            <span class="record-card__count" id="checkup-count">0</span>
          </button>
          <button class="record-card" data-record="more">
            <span class="record-card__icon">···</span>
            <span class="record-card__title">更多</span>
          </button>
        </div>
      </section>

      <section class="health-section">
        <h2 class="health-section__title">生活习惯</h2>
        <div class="habit-list">
          <div class="habit-card" id="diet-habit">
            <span class="habit-card__icon">🍽️</span>
            <div class="habit-card__content">
              <div class="habit-card__label">饮食习惯</div>
              <div class="habit-card__value">--</div>
            </div>
          </div>
          <div class="habit-card" id="exercise-habit">
            <span class="habit-card__icon">🏃</span>
            <div class="habit-card__content">
              <div class="habit-card__label">运动习惯</div>
              <div class="habit-card__value">--</div>
            </div>
          </div>
          <div class="habit-card" id="sleep-habit">
            <span class="habit-card__icon">😴</span>
            <div class="habit-card__content">
              <div class="habit-card__label">睡眠质量</div>
              <div class="habit-card__value">--</div>
            </div>
          </div>
        </div>
      </section>

      <section class="health-section">
        <h2 class="health-section__title">健康史</h2>
        <div class="history-grid">
          <button class="history-card" data-history="allergy">
            <span class="history-card__icon">⚠️</span>
            <span class="history-card__label">过敏史</span>
            <span class="history-card__count" id="allergy-count">0</span>
          </button>
          <button class="history-card" data-history="medical">
            <span class="history-card__icon">🏥</span>
            <span class="history-card__label">既往史</span>
            <span class="history-card__count" id="medical-count">0</span>
          </button>
          <button class="history-card" data-history="family">
            <span class="history-card__icon">👨‍👩‍👧‍👦</span>
            <span class="history-card__label">家族史</span>
            <span class="history-card__count" id="family-count">0</span>
          </button>
          <button class="history-card" data-history="medication">
            <span class="history-card__icon">💊</span>
            <span class="history-card__label">用药史</span>
            <span class="history-card__count" id="medication-count">0</span>
          </button>
        </div>
      </section>

      <div class="health-toolbar">
        <button class="health-tool" data-tool="medical-search">
          <span class="health-tool__icon">📚</span>
          <span class="health-tool__label">医典自查</span>
        </button>
        <button class="health-tool" data-tool="photo-upload">
          <span class="health-tool__icon">📷</span>
          <span class="health-tool__label">拍拍上传</span>
        </button>
        <button class="health-tool" data-tool="period-tracker">
          <span class="health-tool__icon">📅</span>
          <span class="health-tool__label">记经期</span>
        </button>
        <button class="health-tool" data-tool="smart-device">
          <span class="health-tool__icon">⌚</span>
          <span class="health-tool__label">智能设备</span>
        </button>
        <button class="health-tool" data-tool="health-data">
          <span class="health-tool__icon">📊</span>
          <span class="health-tool__label">健康数据</span>
        </button>
      </div>
    `;

    dashboard.innerHTML = originalContent;

    // 更新 refs
    healthDashboard.refs = {
      bmiCard: dashboard.querySelector("#bmi-card"),
      bmiValue: dashboard.querySelector(".bmi-card__value"),
      bmiStatus: dashboard.querySelector(".bmi-card__status"),
      heightValue: dashboard.querySelector("#height-value"),
      weightValue: dashboard.querySelector("#weight-value"),
      bmiUpdateTime: dashboard.querySelector("#bmi-update-time"),
      bpValue: dashboard.querySelector("#bp-value"),
      sugarValue: dashboard.querySelector("#sugar-value"),
      habitCards: {
        diet: dashboard.querySelector("#diet-habit .habit-card__value"),
        exercise: dashboard.querySelector("#exercise-habit .habit-card__value"),
        sleep: dashboard.querySelector("#sleep-habit .habit-card__value"),
      },
      historyCounts: {
        allergy: dashboard.querySelector("#allergy-count"),
        medical: dashboard.querySelector("#medical-count"),
        family: dashboard.querySelector("#family-count"),
        medication: dashboard.querySelector("#medication-count"),
      },
      recordCounts: {
        consultation: dashboard.querySelector("#consultation-count"),
        prescription: dashboard.querySelector("#prescription-count"),
        appointment: dashboard.querySelector("#appointment-count"),
        document: dashboard.querySelector("#document-count"),
        checkup: dashboard.querySelector("#checkup-count"),
      },
    };
  }
}

async function loadMemberDetail(memberId) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/profile/members/${memberId}`);
    if (response.ok) {
      const data = await response.json();

      if (data.data) {
        // 更新 BMI 卡片
        if (data.data.vital_signs) {
          healthDashboard.updateBMI(data.data.vital_signs);
          healthDashboard.updateMetrics(data.data.vital_signs);
        }

        // 更新生活习惯
        if (data.data.health_habits) {
          healthDashboard.updateHabits(data.data.health_habits);
        }

        // 加载健康史摘要
        const historyResponse = await fetch(`${API_BASE}/api/v1/profile/members/${memberId}/history`);
        if (historyResponse.ok) {
          const historyData = await historyResponse.json();
          if (historyData.data) {
            healthDashboard.updateHistoryCounts(historyData.data);
          }
        }

        // 加载健康记录摘要
        const recordsResponse = await fetch(`${API_BASE}/api/v1/profile/members/${memberId}/records/summary`);
        if (recordsResponse.ok) {
          const recordsData = await recordsResponse.json();
          if (recordsData.data) {
            healthDashboard.updateRecordCounts(recordsData.data);
          }
        }
      }
    }
  } catch (err) {
    console.error("加载成员详情失败:", err);
  }
}

function showCreateMemberForm() {
  const form = createMemberProfileForm();
  document.body.appendChild(form.element);

  // 设置表单事件
  form.bindEvents({
    onClose: () => {
      form.element.remove();
    },
    onSubmit: async () => {
      const validation = form.validate();
      if (!validation.valid) {
        alert(validation.errors.join("\n"));
        return;
      }

      const data = form.getData();
      const userId = CURRENT_USER_ID;

      try {
        // 创建成员
        const memberResponse = await fetch(`${API_BASE}/api/v1/profile/${userId}/members`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });

        if (memberResponse.ok) {
          const memberResult = await memberResponse.json();
          const memberId = memberResult.data.member_id;
          const memberName = memberResult.data.name || data.name || "默认成员";

          // 创建后自动切到新成员，避免后续问诊写到旧上下文
          currentMemberId = memberId;
          currentMemberName = memberName;
          persistActiveMember(currentMemberId);
          syncMemberUIEverywhere();
          showBanner(`已创建并切换到就诊人：${memberName}`, "success");

          // 重新加载数据（后端 create_member 已处理体征和习惯）
          form.element.remove();
          await loadHealthData();
        } else {
          alert("创建成员失败，请重试");
        }
      } catch (err) {
        console.error("创建成员失败:", err);
        alert("创建成员失败，请重试");
      }
    },
  });
}
