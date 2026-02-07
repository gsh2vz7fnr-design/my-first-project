// Note: components.js is loaded as a regular script, so all functions are global
const API_BASE = "http://localhost:8000";

let conversationId = null;
let currentTab = "chat"; // Track current tab

// Tab change handler
function handleTabChange(tabName) {
  currentTab = tabName;

  if (tabName === "chat") {
    // Show chat, hide profile and health
    pendingPanel.el.style.display = "none";
    healthDashboard.element.style.display = "none";
    chat.style.display = "flex";
    composer.el.style.display = "flex";
  } else if (tabName === "profile") {
    // Show profile panel, hide chat and health
    pendingPanel.el.style.display = "block";
    healthDashboard.element.style.display = "none";
    chat.style.display = "none";
    composer.el.style.display = "none";
  } else if (tabName === "health") {
    // Show health dashboard, hide chat and profile
    healthDashboard.element.style.display = "block";
    pendingPanel.el.style.display = "none";
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
const pendingPanel = createPendingPanel();
const chat = createChat();
const composer = createComposer();
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
app.appendChild(pendingPanel.el);
app.appendChild(chat);
app.appendChild(healthDashboard.element);
app.appendChild(composer.el);
root.appendChild(app);

// Initialize: hide profile and health panels by default
pendingPanel.el.style.display = "none";
healthDashboard.element.style.display = "none";

// Listen for tab change events from header
header.addEventListener("tabchange", (e) => {
  handleTabChange(e.detail);
});

// Initialize: hide profile panel by default
pendingPanel.el.style.display = "none";

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
  let safe = escapeHtml(text);
  safe = safe.replace(/\n/g, "<br />");
  safe = safe.replace(/【来源:([^】]+)】/g, (match, id) => {
    return `<span class="citation">【来源:${id}】</span>`;
  });
  return safe;
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
  const empty = chat.querySelector(".chat-empty");
  if (empty) {
    empty.remove();
  }
  chat.appendChild(bubble);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
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
  const userId = pendingPanel.refs.userIdInput.value.trim() || "test_user_001";
  try {
    const response = await fetch(`${API_BASE}/api/v1/conversations/${userId}`);
    if (!response.ok) throw new Error("请求失败");
    const data = await response.json();
    conversationSidebar.renderConversations(data.data.conversations || []);

    // Set active conversation
    if (conversationId) {
      conversationSidebar.setActive(conversationId);
    }
  } catch (err) {
    console.error("加载对话列表失败:", err);
    conversationSidebar.renderConversations([]);
  }
}

async function handleNewConversation() {
  const userId = pendingPanel.refs.userIdInput.value.trim() || "test_user_001";
  try {
    const response = await fetch(`${API_BASE}/api/v1/conversations/${userId}`, {
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

  const userId = pendingPanel.refs.userIdInput.value.trim() || "test_user_001";
  try {
    const response = await fetch(`${API_BASE}/api/v1/conversations/${userId}/${convId}`, {
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
  const banner = chat.querySelector(".chat-banner");
  if (!banner) return;
  banner.textContent = message;
  banner.classList.remove("info", "warn");
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

function renderPending(items) {
  const pendingList = pendingPanel.refs.pendingList;
  pendingList.innerHTML = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "panel-empty";
    empty.textContent = "暂无待确认内容";
    pendingList.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "pending-item";

    const meta = document.createElement("div");
    meta.className = "pending-meta";

    const type = document.createElement("div");
    type.className = "pending-type";
    type.textContent = item.type || "unknown";

    const record = document.createElement("div");
    record.className = "pending-record";
    record.textContent = JSON.stringify(item.record || {}, null, 0);

    meta.appendChild(type);
    meta.appendChild(record);

    const actions = document.createElement("div");
    actions.className = "pending-actions";

    const confirmBtn = document.createElement("button");
    confirmBtn.className = "pending-confirm";
    confirmBtn.textContent = "确认";
    confirmBtn.addEventListener("click", () => updatePending(item, true));

    const rejectBtn = document.createElement("button");
    rejectBtn.className = "pending-reject";
    rejectBtn.textContent = "拒绝";
    rejectBtn.addEventListener("click", () => updatePending(item, false));

    actions.appendChild(confirmBtn);
    actions.appendChild(rejectBtn);

    card.appendChild(meta);
    card.appendChild(actions);
    pendingList.appendChild(card);
  });
}

async function fetchPending() {
  const userId = pendingPanel.refs.userIdInput.value.trim();
  if (!userId) return;

  pendingPanel.refs.pendingList.innerHTML = "<div class='panel-empty'>加载中...</div>";
  try {
    const response = await fetch(`${API_BASE}/api/v1/profile/${userId}/pending`);
    if (!response.ok) throw new Error("请求失败");
    const data = await response.json();
    renderPending(data.data.pending_confirmations || []);
  } catch (err) {
    pendingPanel.refs.pendingList.innerHTML = "<div class='panel-empty'>无法获取待确认内容</div>";
  }
}

/**
 * Send message with streaming output
 * @param {string} text - User message
 * @param {number} retryCount - Current retry attempt
 */
async function sendMessageStream(text, retryCount = 0) {
  const MAX_RETRIES = 3;
  const startTime = performance.now();
  let firstTokenTime = null;
  let streamBubble = null;
  let metadata = null;

  try {
    const response = await fetch(`${API_BASE}/api/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: pendingPanel.refs.userIdInput.value.trim() || "test_user_001",
        conversation_id: conversationId,
        message: text,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    // Remove empty state
    const empty = chat.querySelector(".chat-empty");
    if (empty) {
      empty.remove();
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

              // Handle follow-up needed
              if (metadata.need_follow_up && metadata.missing_slots) {
                showBanner("提示：需要补充关键信息后才能给出更准确建议。", "info");

                // Create follow-up form
                const form = createFollowUpForm(metadata.missing_slots, (values) => {
                  // Send form data as a follow-up message
                  const followUpMessage = Object.entries(values)
                    .map(([key, value]) => {
                      if (Array.isArray(value)) {
                        return `${key}: ${value.join(", ")}`;
                      }
                      return `${key}: ${value}`;
                    })
                    .join("\n");

                  appendMessage("user", followUpMessage);
                  form.element.remove();

                  // Send the follow-up data to backend
                  sendMessageStream(followUpMessage);
                });

                chat.appendChild(form.element);
                chat.scrollTop = chat.scrollHeight;
              }

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
            }

            // Handle content chunks
            if (data.type === "content" && data.content) {
              // Create stream bubble if it doesn't exist
              if (!streamBubble) {
                streamBubble = createStreamBubble({ role: "assistant", initialText: "" });
                chat.appendChild(streamBubble.element);
              }

              streamBubble.appendText(data.content);
              chat.scrollTop = chat.scrollHeight;
            } else if (data.type === "abort" && data.content) {
              // Handle safety abort
              if (streamBubble) {
                streamBubble.bubble.classList.add("stream-error");
                streamBubble.bubble.innerHTML = formatMessage(data.content);
                streamBubble.cursor.remove();
              } else {
                // Create error bubble if stream hasn't started
                const errorBubble = createStreamBubble({ role: "assistant", initialText: "" });
                errorBubble.bubble.classList.add("stream-error");
                errorBubble.bubble.innerHTML = formatMessage(data.content);
                errorBubble.cursor.remove();
                chat.appendChild(errorBubble.element);
              }
              showBanner("⚠️ 安全警示：该回复已被系统拦截。", "warn");
            } else if (data.type === "done") {
              // Complete streaming
              if (streamBubble) {
                streamBubble.complete();

                // Add triage card if needed
                if (metadata && metadata.triage_level && metadata.intent === "triage") {
                  const triageCard = createTriageResultCard({
                    level: metadata.triage_level,
                    reason: "根据症状分析",
                    action: streamBubble.bubble.textContent,
                  });
                  streamBubble.bubble.innerHTML = "";
                  streamBubble.bubble.appendChild(triageCard);
                }
              }

              // Check if overall latency was acceptable
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

    // Clean up
    if (streamBubble) {
      streamBubble.complete();
    }

    // Reload conversation list to update metadata
    await loadConversations();

  } catch (err) {
    console.error("Streaming error:", err);

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
    showBanner("连接失败，请检查网络或稍后重试。", "info");
  }
}

async function updatePending(item, confirm) {
  const userId = pendingPanel.refs.userIdInput.value.trim();
  if (!userId) return;

  const payload = confirm
    ? { confirm: [item], reject: [] }
    : { confirm: [], reject: [item] };

  try {
    const response = await fetch(`${API_BASE}/api/v1/profile/${userId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("请求失败");
    await fetchPending();
  } catch (err) {
    pendingPanel.refs.pendingList.innerHTML = "<div class='panel-empty'>更新失败，请重试</div>";
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

pendingPanel.refs.refreshButton.addEventListener("click", fetchPending);
fetchPending();

// Load conversations on startup
loadConversations();

async function sendMessage() {
  const text = composer.refs.input.value.trim();
  if (!text) return;

  hideBanner();
  appendMessage("user", text);
  composer.refs.input.value = "";
  composer.refs.input.focus();

  // Use streaming for better user experience
  await sendMessageStream(text);
}

composer.refs.button.addEventListener("click", sendMessage);
composer.refs.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    sendMessage();
  }
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

async function loadHealthData() {
  const userId = pendingPanel.refs.userIdInput.value.trim() || "test_user_001";

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
      // 获取第一个成员的详细数据
      const firstMember = membersData.data.members[0];

      // 重建健康仪表板内容
      rebuildHealthDashboard();
      await loadMemberDetail(firstMember.id);
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
      const userId = pendingPanel.refs.userIdInput.value.trim() || "test_user_001";

      try {
        // 创建成员
        const memberResponse = await fetch(`${API_BASE}/api/v1/profile/${userId}/members`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });

        if (memberResponse.ok) {
          // 创建体征记录
          const memberResult = await memberResponse.json();
          const memberId = memberResult.data.member_id;

          await fetch(`${API_BASE}/api/v1/profile/members/${memberId}/vital-signs`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              member_id: memberId,
              height_cm: data.height_cm,
              weight_kg: data.weight_kg,
              blood_pressure_systolic: data.blood_pressure_systolic,
              blood_pressure_diastolic: data.blood_pressure_diastolic,
              blood_sugar: data.blood_sugar,
              blood_sugar_type: data.blood_sugar_type,
            }),
          });

          // 创建生活习惯记录
          await fetch(`${API_BASE}/api/v1/profile/members/${memberId}/habits`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              member_id: memberId,
              diet_habit: data.diet_habit,
              exercise_habit: data.exercise_habit,
              sleep_quality: data.sleep_quality,
            }),
          });

          // 重新加载数据
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
