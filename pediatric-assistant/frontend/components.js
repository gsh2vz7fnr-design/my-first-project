/**
 * Create archive confirmation modal
 * @param {Object} options - Configuration options
 * @param {boolean} options.multiMember - Whether conversation has multiple members
 * @param {Array} options.members - List of members (if multiMember is true)
 * @param {Function} options.onConfirm - Callback when archive is confirmed
 * @param {Function} options.onCancel - Callback when cancelled
 * @returns {Object} - Modal element with show/hide methods
 */
function createArchiveConfirmModal(options = {}) {
  const { multiMember = false, members = [], onConfirm, onCancel } = options;

  const overlay = document.createElement("div");
  overlay.className = "archive-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "archive-modal-title");

  const modal = document.createElement("div");
  modal.className = "archive-modal";

  if (multiMember && members.length > 0) {
    // Multi-member selector
    modal.innerHTML = `
      <div class="archive-modal__header">
        <h2 id="archive-modal-title" class="archive-modal__title">选择归档成员</h2>
        <button class="archive-modal__close" aria-label="关闭">×</button>
      </div>
      <div class="archive-modal__body">
        <p class="archive-modal__description">
          本次对话涉及多位成员，请选择归档到哪个成员的健康档案：
        </p>
        <div class="member-selector" id="member-selector">
          ${members.map((member, index) => `
            <label class="member-option">
              <input type="radio" name="selected-member" value="${member.id}" ${index === 0 ? 'checked' : ''} />
              <span class="member-option__label">
                <span class="member-option__name">${member.name || '未命名成员'}</span>
                <span class="member-option__meta">${member.relationship || ''} · ${member.age || ''}</span>
              </span>
            </label>
          `).join('')}
        </div>
      </div>
      <div class="archive-modal__actions">
        <button class="archive-modal__button archive-modal__button--cancel" type="button">取消</button>
        <button class="archive-modal__button archive-modal__button--confirm" type="button">确认归档</button>
      </div>
    `;
  } else {
    // Single member or auto-archive confirmation
    modal.innerHTML = `
      <div class="archive-modal__header">
        <h2 id="archive-modal-title" class="archive-modal__title">归档对话</h2>
        <button class="archive-modal__close" aria-label="关闭">×</button>
      </div>
      <div class="archive-modal__body">
        <div class="archive-modal__icon">📁</div>
        <p class="archive-modal__description">
          确认将本次对话归档到健康档案吗？归档后对话将保存为只读记录。
        </p>
      </div>
      <div class="archive-modal__actions">
        <button class="archive-modal__button archive-modal__button--cancel" type="button">取消</button>
        <button class="archive-modal__button archive-modal__button--confirm" type="button">确认归档</button>
      </div>
    `;
  }

  overlay.appendChild(modal);

  const closeBtn = modal.querySelector(".archive-modal__close");
  const cancelBtn = modal.querySelector(".archive-modal__button--cancel");
  const confirmBtn = modal.querySelector(".archive-modal__button--confirm");

  const close = () => {
    overlay.classList.remove("archive-modal-overlay--visible");
    setTimeout(() => {
      overlay.remove();
    }, 300);
    if (onCancel) onCancel();
  };

  const confirm = () => {
    let selectedMemberId = null;
    if (multiMember && members.length > 0) {
      const selectedRadio = modal.querySelector('input[name="selected-member"]:checked');
      selectedMemberId = selectedRadio ? selectedRadio.value : members[0].id;
    }

    overlay.classList.remove("archive-modal-overlay--visible");
    setTimeout(() => {
      overlay.remove();
    }, 300);

    if (onConfirm) onConfirm(selectedMemberId);
  };

  closeBtn.addEventListener("click", close);
  cancelBtn.addEventListener("click", close);
  confirmBtn.addEventListener("click", confirm);

  // Close on overlay click
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      close();
    }
  });

  return {
    element: overlay,
    show() {
      document.body.appendChild(overlay);
      overlay.offsetHeight; // Trigger reflow
      overlay.classList.add("archive-modal-overlay--visible");
      confirmBtn.focus();
    },
    hide: close,
  };
}

/**
 * Create a disclaimer modal for first-time users
 * @returns {Object} - Modal element with show/hide methods
 */
function createDisclaimerModal() {
  const overlay = document.createElement("div");
  overlay.className = "disclaimer-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "disclaimer-title");
  overlay.setAttribute("aria-describedby", "disclaimer-content");

  const modal = document.createElement("div");
  modal.className = "disclaimer-modal";

  modal.innerHTML = `
    <div class="disclaimer-modal__header">
      <div class="disclaimer-modal__icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2L2 7V12C2 17.52 6.37 22.75 12 24C17.63 22.75 22 17.52 22 12V7L12 2Z" stroke="currentColor" stroke-width="2" fill="var(--primary-50)"/>
          <path d="M12 8V12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <circle cx="12" cy="16" r="1" fill="currentColor"/>
        </svg>
      </div>
      <h1 id="disclaimer-title" class="disclaimer-modal__title">
        使用须知
      </h1>
    </div>

    <div class="disclaimer-modal__body">
      <p id="disclaimer-content" class="disclaimer-modal__content">
        欢迎使用智能儿科分诊与护理助手！
      </p>
      <div class="disclaimer-modal__list">
        <div class="disclaimer-item">
          <span class="disclaimer-icon">1</span>
          <span>本助手仅提供健康咨询参考，不能替代专业医疗诊断</span>
        </div>
        <div class="disclaimer-item">
          <span class="disclaimer-icon">2</span>
          <span>所有建议均基于权威医学指南，但不构成医疗处方</span>
        </div>
        <div class="disclaimer-item">
          <span class="disclaimer-icon">3</span>
          <span>如遇紧急情况，请立即拨打120或前往医院急诊</span>
        </div>
        <div class="disclaimer-item">
          <span class="disclaimer-icon">4</span>
          <span>本助手不会开具处方药，如需用药请咨询医生</span>
        </div>
      </div>
      <p class="disclaimer-modal__footer-text">
        您的使用即表示同意以上条款。
      </p>
    </div>

    <div class="disclaimer-modal__actions">
      <button class="disclaimer-modal__button" type="button" id="disclaimer-accept">
        我已知晓，开始使用
      </button>
    </div>
  `;

  overlay.appendChild(modal);

  const acceptBtn = modal.querySelector("#disclaimer-accept");

  return {
    element: overlay,
    show() {
      overlay.style.display = "flex";
      // Trigger reflow
      overlay.offsetHeight;
      overlay.classList.add("disclaimer-overlay--visible");
      acceptBtn.focus();
    },
    hide() {
      overlay.classList.remove("disclaimer-overlay--visible");
      setTimeout(() => {
        overlay.style.display = "none";
      }, 300);
    },
    onAccept(callback) {
      acceptBtn.addEventListener("click", () => {
        this.hide();
        if (callback) callback();
      });
    },
  };
}

function createHeader() {
  const header = document.createElement("header");
  header.className = "app-header";

  header.innerHTML = `
    <div class="header-top">
      <!-- 左侧：汉堡菜单 + 品牌名称 -->
      <div class="header-left">
        <button class="header-menu-btn" aria-label="菜单">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <h1 class="header-brand">智能儿科助手</h1>
      </div>

      <!-- 右侧：操作按钮 -->
      <div class="header-right">
        <button class="header-icon-btn" aria-label="归档对话" id="archive-conversation-btn">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 8v13H3V8"></path>
            <path d="M1 3h22v5H1z"></path>
            <line x1="10" y1="12" x2="14" y2="12"></line>
          </svg>
        </button>
      </div>
    </div>

    <!-- 底部：标签切换 -->
    <div class="header-bottom">
      <nav class="header-tabs">
        <button class="header-tab active" data-tab="chat">
          <span class="tab-icon">💬</span>
          <span class="tab-label">对话</span>
        </button>
        <button class="header-tab" data-tab="health">
          <span class="tab-icon">🩺</span>
          <span class="tab-label">健康</span>
        </button>
      </nav>
    </div>
  `;

  // Setup tab click handlers
  const tabButtons = header.querySelectorAll(".header-tab");
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const tabName = button.dataset.tab;

      // Update active state
      tabButtons.forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");

      // Dispatch custom event for tab change
      header.dispatchEvent(new CustomEvent("tabchange", { detail: tabName }));
    });
  });

  // Setup menu button handler
  const menuBtn = header.querySelector(".header-menu-btn");
  menuBtn.addEventListener("click", () => {
    header.dispatchEvent(new CustomEvent("menu-toggle", { bubbles: true }));
  });

  // Setup archive button handler
  const archiveBtn = header.querySelector("#archive-conversation-btn");
  archiveBtn.addEventListener("click", () => {
    header.dispatchEvent(new CustomEvent("archive-conversation", { bubbles: true }));
  });

  return header;
}

function createTabs(onTabChange) {
  // This function now just sets up the event listener
  // Actual tabs are in the header
  return {
    element: document.createElement("div"), // Empty element (tabs are in header)
    onTabChange,
  };
}

function createChat() {
  const main = document.createElement("main");
  main.className = "chat";
  main.setAttribute("role", "log");
  main.setAttribute("aria-live", "polite");
  main.setAttribute("aria-label", "对话区域");

  // Add welcome screen with suggestions
  const welcome = createWelcomeScreen();
  main.appendChild(welcome);

  const empty = document.createElement("div");
  empty.className = "chat-empty";
  empty.textContent = "暂无对话，请描述宝宝的症状或用药问题。";
  empty.setAttribute("aria-hidden", "true");
  main.appendChild(empty);

  const banner = document.createElement("div");
  banner.className = "chat-banner";
  banner.textContent = "";
  banner.dataset.visible = "false";
  banner.setAttribute("role", "status");
  banner.setAttribute("aria-live", "polite");
  main.appendChild(banner);
  return main;
}

/**
 * Create improved welcome screen with quick suggestions
 * @returns {HTMLElement} Welcome screen element
 */
function createWelcomeScreen() {
  const welcome = document.createElement("div");
  welcome.className = "chat-welcome";
  welcome.setAttribute("role", "complementary");
  welcome.setAttribute("aria-label", "使用指南");

  // Define quick suggestion cards
  const suggestions = [
    {
      icon: "🌡️",
      title: "发烧咨询",
      example: "宝宝8个月，发烧38.5度，精神不好",
      intent: "fever",
      color: "var(--emergency-500)",
      bg: "var(--emergency-50)",
    },
    {
      icon: "💊",
      title: "用药问题",
      example: "泰诺林怎么给1岁宝宝吃？",
      intent: "medication",
      color: "var(--primary-500)",
      bg: "var(--primary-50)",
    },
    {
      icon: "🤢",
      title: "症状描述",
      example: "宝宝拉肚子，一天5次，稀水样",
      intent: "symptom",
      color: "var(--warning-500)",
      bg: "var(--warning-50)",
    },
    {
      icon: "🏥",
      title: "是否就医",
      example: "需要去医院还是在家观察？",
      intent: "triage",
      color: "var(--success-500)",
      bg: "var(--success-50)",
    },
  ];

  welcome.innerHTML = `
    <div class="chat-welcome-suggestions" style="margin-top: 20px;">
      <h2 class="suggestions-title" style="text-align: left; margin-left: 0;">您可以这样问我：</h2>
      <div class="suggestion-grid" role="list" aria-label="快捷问题">
        ${suggestions
          .map(
            (s, index) => `
          <button
            class="suggestion-card"
            data-example="${s.example}"
            data-intent="${s.intent}"
            type="button"
            role="listitem"
            aria-label="${s.title}：${s.example}"
            style="--card-color: ${s.color}; --card-bg: ${s.bg};"
          >
            <div class="suggestion-card__content">
              <div class="suggestion-card__title">${s.title}</div>
              <div class="suggestion-card__example">${s.example}</div>
            </div>
            <span class="suggestion-card__arrow" aria-hidden="true">→</span>
          </button>
        `
          )
          .join("")}
      </div>
    </div>
  `;

  // Add click handlers for suggestion cards
  welcome.querySelectorAll(".suggestion-card").forEach((card) => {
    card.addEventListener("click", () => {
      const example = card.dataset.example;
      // Dispatch custom event for app.js to handle
      welcome.dispatchEvent(
        new CustomEvent("suggestion-selected", {
          detail: { example, intent: card.dataset.intent },
          bubbles: true,
        })
      );
    });

    // Add keyboard support
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        card.click();
      }
    });
  });

  return welcome;
}

function createChatBubble({ role, html }) {
  const section = document.createElement("section");
  section.className = `message ${role}`;
  section.setAttribute("role", "article");
  section.setAttribute("aria-label", role === "user" ? "您的消息" : "助手回复");

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.setAttribute("tabindex", "0");
  bubble.innerHTML = html;
  section.appendChild(bubble);
  return section;
}

function createComposer() {
  const footer = document.createElement("footer");
  footer.className = "composer";
  footer.setAttribute("role", "form");
  footer.setAttribute("aria-label", "消息输入框");

  // Input wrapper for layout
  const inputWrapper = document.createElement("div");
  inputWrapper.className = "composer-input-wrapper";

  inputWrapper.innerHTML = `
    <input
      class="composer-input"
      type="text"
      placeholder="请描述症状..."
      aria-label="输入您的消息"
      aria-describedby="composer-hint"
    />
    <button class="composer-send" aria-label="发送消息" type="submit">
      发送
    </button>
  `;

  const hint = document.createElement("div");
  hint.className = "composer-hint";
  hint.id = "composer-hint";
  hint.textContent = "提示：可直接输入「发烧39度，精神蔫」，系统会引导补全信息。";
  hint.setAttribute("aria-live", "polite");

  footer.appendChild(inputWrapper);
  footer.appendChild(hint);

  return {
    el: footer,
    refs: {
      input: footer.querySelector(".composer-input"),
      button: footer.querySelector(".composer-send"),
    },
  };
}

function createSourceSheet() {
  const backdrop = document.createElement("div");
  backdrop.className = "sheet-backdrop";
  backdrop.dataset.sheetClose = "true";

  const sheet = document.createElement("aside");
  sheet.className = "sheet";
  sheet.innerHTML = `
    <div class="sheet-handle"></div>
    <div class="sheet-header">
      <div class="sheet-title">来源原文</div>
      <button class="sheet-close" data-sheet-close="true">关闭</button>
    </div>
    <div class="sheet-body">
      <div class="sheet-meta">
        <div class="meta-label">来源</div>
        <div class="meta-value" id="source-name">-</div>
      </div>
      <div class="sheet-meta">
        <div class="meta-label">标题</div>
        <div class="meta-value" id="source-title">-</div>
      </div>
      <div class="sheet-content" id="source-content">
        点击来源角标后，将展示原文片段。
      </div>
    </div>
  `;

  return {
    backdrop,
    sheet,
    refs: {
      sourceName: sheet.querySelector("#source-name"),
      sourceTitle: sheet.querySelector("#source-title"),
      sourceContent: sheet.querySelector("#source-content"),
    },
  };
}

/**
 * Create a streaming chat bubble with typewriter effect
 * @param {Object} options - Configuration options
 * @param {string} options.role - Message role ('user' or 'assistant')
 * @param {string} options.initialText - Initial text to display
 * @returns {Object} - Bubble element and control methods
 */
function createStreamBubble({ role, initialText = "" }) {
  const section = document.createElement("section");
  section.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble bubble-stream";
  bubble.innerHTML = initialText;

  // Add blinking cursor
  const cursor = document.createElement("span");
  cursor.className = "stream-cursor";
  cursor.textContent = "▋";
  bubble.appendChild(cursor);

  section.appendChild(bubble);

  return {
    element: section,
    bubble,
    cursor,
    /**
     * Append text content to the bubble
     * @param {string} text - Text to append
     */
    appendText(text) {
      // Insert before cursor
      const textNode = document.createTextNode(text);
      bubble.insertBefore(textNode, cursor);
    },

    /**
     * Complete streaming and remove cursor
     */
    complete() {
      cursor.remove();
      bubble.classList.remove("bubble-stream");
    },

    /**
     * Update bubble HTML directly (for formatting)
     * @param {string} html - HTML content
     */
    updateHTML(html) {
      bubble.innerHTML = html;
      if (!bubble.querySelector(".stream-cursor")) {
        bubble.appendChild(cursor);
      }
    },
  };
}

/**
 * Create a triage result card with visual indicators
 * @param {Object} triageData - Triage information
 * @param {string} triageData.level - Triage level: 'emergency' | 'observation' | 'consultation'
 * @param {string} triageData.reason - Reason for triage decision
 * @param {string} triageData.action - Recommended action
 * @param {Array<string>} triageData.dangerSignals - List of danger signals (if any)
 * @returns {HTMLElement} - Triage card element
 */
function createTriageResultCard(triageData) {
  const { level, reason, action, dangerSignals = [] } = triageData;

  const card = document.createElement("div");
  card.className = `triage-card triage-${level}`;

  // Map levels to display info
  const levelConfig = {
    emergency: {
      icon: "⚠️",
      label: "紧急",
      gradient: "linear-gradient(135deg, #ff6b6b, #c0392b)",
    },
    observation: {
      icon: "👁️",
      label: "观察",
      gradient: "linear-gradient(135deg, #4ecdc4, #2196f3)",
    },
    consultation: {
      icon: "💬",
      label: "在线咨询",
      gradient: "linear-gradient(135deg, #3498db, #1976d2)",
    },
  };

  const config = levelConfig[level] || levelConfig.consultation;

  card.innerHTML = `
    <div class="triage-header" style="background: ${config.gradient}">
      <span class="triage-icon">${config.icon}</span>
      <span class="triage-level">${config.label}</span>
    </div>
    <div class="triage-body">
      <div class="triage-reason">
        <strong>分诊依据：</strong>${reason}
      </div>
      <div class="triage-action">
        <strong>建议行动：</strong>${action}
      </div>
      ${
        level === "emergency"
          ? `
      <div class="triage-actions">
        <a href="tel:120" class="triage-btn triage-btn-emergency">
          📞 拨打120
        </a>
        <button class="triage-btn triage-btn-hospital" onclick="alert('地图功能开发中，请使用地图APP搜索最近医院')">
          🏥 查找最近医院
        </button>
      </div>
      `
          : ""
      }
    </div>
  `;

  return card;
}

/**
 * Create an enhanced danger signal modal with haptic feedback
 * @param {Array<string>} dangerSignals - List of danger signals
 * @returns {Object} - Modal element with show/hide methods
 */
function createDangerSignalModal(dangerSignals = []) {
  const overlay = document.createElement("div");
  overlay.className = "emergency-overlay";
  overlay.setAttribute("role", "alertdialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "emergency-title");
  overlay.setAttribute("aria-describedby", "emergency-description");

  const modal = document.createElement("div");
  modal.className = "emergency-modal";

  modal.innerHTML = `
    <div class="emergency-modal__header">
      <div class="emergency-modal__icon" aria-hidden="true">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 9V13" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
          <circle cx="12" cy="17" r="1" fill="currentColor"/>
          <path d="M12 2L2 7V12C2 17.52 6.37 22.75 12 24C17.63 22.75 22 17.52 22 12V7L12 2Z" stroke="currentColor" stroke-width="2"/>
        </svg>
      </div>
      <h1 id="emergency-title" class="emergency-modal__title">
        ⚠️ 紧急警告
      </h1>
    </div>

    <div class="emergency-modal__body">
      <p id="emergency-description" class="emergency-modal__description">
        检测到以下危险信号，建议立即就医：
      </p>
      <ul class="emergency-modal__signals" role="list">
        ${dangerSignals.map((signal) => `<li>${signal}</li>`).join("")}
      </ul>
    </div>

    <div class="emergency-modal__actions">
      <a href="tel:120" class="emergency-btn emergency-btn--call" role="button">
        <span class="emergency-btn__icon" aria-hidden="true">📞</span>
        <div class="emergency-btn__content">
          <span class="emergency-btn__title">立即拨打120</span>
          <span class="emergency-btn__subtitle">紧急医疗救助</span>
        </div>
      </a>

      <button class="emergency-btn emergency-btn--hospital" type="button">
        <span class="emergency-btn__icon" aria-hidden="true">🏥</span>
        <div class="emergency-btn__content">
          <span class="emergency-btn__title">查找最近医院</span>
          <span class="emergency-btn__subtitle">地图导航</span>
        </div>
      </button>
    </div>

    <div class="emergency-modal__footer">
      <p class="emergency-modal__note">
        如不确定是否紧急，建议宁可就医确诊，不要延误病情
      </p>
      <button
        class="emergency-modal__acknowledge"
        type="button"
        aria-label="我已了解风险，继续咨询"
      >
        我已了解，继续咨询
      </button>
    </div>
  `;

  overlay.appendChild(modal);

  // Trigger haptic feedback
  const triggerHaptic = () => {
    if ("vibrate" in navigator) {
      // Pattern: vibrate 200ms, pause 100ms, vibrate 200ms
      navigator.vibrate([200, 100, 200]);
    }
  };

  // Close handlers
  const close = () => {
    overlay.classList.remove("emergency-overlay--visible");
    setTimeout(() => {
      overlay.style.display = "none";
      // Show persistent banner
      showPersistentEmergencyBanner();
    }, 300);
  };

  const acknowledgeBtn = modal.querySelector(".emergency-modal__acknowledge");
  acknowledgeBtn.addEventListener("click", close);

  // Trap focus for accessibility
  const focusableElements = modal.querySelectorAll(
    'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  modal.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }
    // Close on Escape
    if (e.key === "Escape") {
      // Don't close on Escape for emergency - require explicit acknowledge
      // Just shake the modal to indicate it can't be dismissed
      modal.classList.add("emergency-modal--shake");
      setTimeout(() => modal.classList.remove("emergency-modal--shake"), 500);
    }
  });

  return {
    element: overlay,
    show() {
      overlay.style.display = "flex";
      triggerHaptic();
      // Trigger reflow
      overlay.offsetHeight;
      overlay.classList.add("emergency-overlay--visible");
      // Set focus
      setTimeout(() => firstElement.focus(), 100);
    },
    close,
  };
}

/**
 * Show persistent emergency banner after modal is closed
 */
function showPersistentEmergencyBanner() {
  const existing = document.querySelector(".persistent-emergency-banner");
  if (existing) return;

  const banner = document.createElement("div");
  banner.className = "persistent-emergency-banner";
  banner.setAttribute("role", "alert");
  banner.setAttribute("aria-live", "assertive");

  banner.innerHTML = `
    <div class="persistent-emergency-banner__content">
      <span class="persistent-emergency-banner__icon" aria-hidden="true">⚠️</span>
      <div class="persistent-emergency-banner__text">
        <strong>紧急警告</strong>
        <span>系统检测到危险信号，请密切观察宝宝状况</span>
      </div>
    </div>
    <a href="tel:120" class="persistent-emergency-banner__call">
      📞 拨打120
    </a>
  `;

  document.body.appendChild(banner);

  // Auto-remove after 5 minutes
  setTimeout(() => {
    banner.style.opacity = "0";
    setTimeout(() => banner.remove(), 300);
  }, 5 * 60 * 1000);
}

/**
 * Create a slot tracker (progress bar replacement)
 * @param {Array} slots - Array of slot objects { key, label, status, value }
 * @returns {Object} - Element and update method
 */
function createSlotTracker(slots) {
  const container = document.createElement("div");
  container.className = "slot-tracker";
  
  const render = (currentSlots) => {
    container.innerHTML = currentSlots.map(slot => {
      let statusClass = slot.status || "waiting";
      let icon = "";
      if (statusClass === "completed") icon = '<span class="slot-icon">✓</span>';
      
      return `
        <div class="slot-card ${statusClass}">
          <div class="slot-label">${icon}${slot.label}</div>
          <div class="slot-value">${slot.value || (statusClass === "waiting" ? "Waiting" : "Current")}</div>
        </div>
      `;
    }).join("");
  };

  render(slots);

  return {
    element: container,
    update: render
  };
}

/**
 * Create quick reply chips
 * @param {Array} chips - Array of strings
 * @param {Function} onSelect - Callback(chipValue)
 * @returns {Object} - Element and update method
 */
function createQuickReplies(chips, onSelect) {
  const container = document.createElement("div");
  container.className = "quick-replies";

  const render = (currentChips) => {
    container.innerHTML = "";
    if (!currentChips || currentChips.length === 0) {
      container.style.display = "none";
      return;
    }
    container.style.display = "flex";
    
    currentChips.forEach(chip => {
      const btn = document.createElement("button");
      btn.className = "reply-chip";
      btn.textContent = chip;
      btn.addEventListener("click", () => onSelect(chip));
      container.appendChild(btn);
    });
  };

  render(chips);

  return {
    element: container,
    update: render
  };
}

/**
 * Create a follow-up form for collecting missing information
 * @param {Object} missingSlots - Missing slot definitions
 * @param {Function} onSubmit - Callback when form is submitted
 * @returns {Object} - Form element and control methods
 */
function createFollowUpForm(missingSlots, onSubmit) {
  const form = document.createElement("div");
  form.className = "follow-up-form inline-form"; // Added inline-form class

  // Count total steps
  const slotKeys = Object.keys(missingSlots);
  
  // Build form fields
  const fieldsContainer = document.createElement("div");
  fieldsContainer.className = "form-fields";

  const fieldValues = {};

  slotKeys.forEach((slotKey) => {
    const slotDef = missingSlots[slotKey];
    const fieldWrapper = document.createElement("div");
    fieldWrapper.className = `form-field ${slotDef.required ? "required" : ""}`;

    const label = document.createElement("label");
    label.className = "form-label";
    label.textContent = slotDef.label || slotKey;
    if (slotDef.required) {
      label.innerHTML += ' <span class="required-indicator">*</span>';
    }
    fieldWrapper.appendChild(label);

    let input;

    // Create different input types based on slot definition
    switch (slotDef.type) {
      case "number":
        input = document.createElement("input");
        input.type = "number";
        input.className = "form-input";
        input.min = slotDef.min || 0;
        input.max = slotDef.max || 1000;
        input.step = slotDef.step || 1;
        input.placeholder = `请输入${slotDef.label || slotKey}`;
        input.addEventListener("input", () => {
          fieldValues[slotKey] = parseFloat(input.value);
          validateForm();
        });
        break;

      case "select":
        input = document.createElement("select");
        input.className = "form-select";
        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = `请选择${slotDef.label || slotKey}`;
        input.appendChild(defaultOption);

        (slotDef.options || []).forEach((opt) => {
          const option = document.createElement("option");
          option.value = typeof opt === "string" ? opt : opt.value;
          option.textContent = typeof opt === "string" ? opt : opt.label;
          input.appendChild(option);
        });

        input.addEventListener("change", () => {
          fieldValues[slotKey] = input.value;
          validateForm();
        });
        break;

      case "multiselect":
        input = document.createElement("div");
        input.className = "form-multiselect";

        (slotDef.options || []).forEach((opt) => {
          const checkboxWrapper = document.createElement("label");
          checkboxWrapper.className = "form-checkbox";

          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.value = typeof opt === "string" ? opt : opt.value;

          const checkboxLabel = document.createElement("span");
          checkboxLabel.textContent = typeof opt === "string" ? opt : opt.label;

          checkboxWrapper.appendChild(checkbox);
          checkboxWrapper.appendChild(checkboxLabel);

          checkbox.addEventListener("change", () => {
            if (!fieldValues[slotKey]) {
              fieldValues[slotKey] = [];
            }
            if (checkbox.checked) {
              fieldValues[slotKey].push(checkbox.value);
            } else {
              fieldValues[slotKey] = fieldValues[slotKey].filter((v) => v !== checkbox.value);
            }
            validateForm();
          });

          input.appendChild(checkboxWrapper);
        });
        break;

      default: // text
        input = document.createElement("input");
        input.type = "text";
        input.className = "form-input";
        input.placeholder = `请输入${slotDef.label || slotKey}`;
        input.addEventListener("input", () => {
          fieldValues[slotKey] = input.value;
          validateForm();
        });
    }

    fieldWrapper.appendChild(input);
    fieldsContainer.appendChild(fieldWrapper);
  });

  form.appendChild(fieldsContainer);

  // Build form actions
  const actions = document.createElement("div");
  actions.className = "form-actions";

  const submitBtn = document.createElement("button");
  submitBtn.className = "form-submit";
  submitBtn.textContent = "提交";
  submitBtn.disabled = true;
  submitBtn.addEventListener("click", () => {
    if (onSubmit) {
      onSubmit(fieldValues);
    }
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "form-cancel";
  cancelBtn.textContent = "取消";
  cancelBtn.addEventListener("click", () => {
    form.remove();
    // Dispatch event to clear progress bar
    window.dispatchEvent(new CustomEvent("form-cancelled"));
  });

  actions.appendChild(cancelBtn);
  actions.appendChild(submitBtn);
  form.appendChild(actions);

  // Validation function
  function validateForm() {
    let isValid = true;

    slotKeys.forEach((slotKey) => {
      const slotDef = missingSlots[slotKey];
      if (slotDef.required) {
        const value = fieldValues[slotKey];
        if (!value || (Array.isArray(value) && value.length === 0)) {
          isValid = false;
        }
      }
    });

    submitBtn.disabled = !isValid;
  }

  return {
    element: form,
    getValues() {
      return fieldValues;
    },
  };
}

/**
 * Create a conversation history sidebar
 * @param {Object} options - Configuration options
 * @param {Function} options.onNewConversation - Callback when new conversation is created
 * @param {Function} options.onSelectConversation - Callback when conversation is selected
 * @param {Function} options.onDeleteConversation - Callback when conversation is deleted
 * @returns {Object} - Sidebar element and control methods
 */
function createConversationSidebar({ onNewConversation, onSelectConversation, onDeleteConversation }) {
  const sidebar = document.createElement("aside");
  sidebar.className = "conversation-sidebar";

  sidebar.innerHTML = `
    <div class="sidebar-header">
      <h3 class="sidebar-title">对话历史</h3>
      <button class="sidebar-close" id="sidebar-close-btn">×</button>
    </div>
    <div class="sidebar-new-btn-wrapper">
      <button class="sidebar-new-btn" id="new-conv-btn">
        <span class="new-icon">+</span>
        <span>新建对话</span>
      </button>
    </div>
    <div class="sidebar-content" id="conv-list">
      <div class="sidebar-empty">加载中...</div>
    </div>
  `;

  const refs = {
    closeBtn: sidebar.querySelector("#sidebar-close-btn"),
    newBtn: sidebar.querySelector("#new-conv-btn"),
    list: sidebar.querySelector("#conv-list"),
  };

  // Event handlers
  refs.closeBtn.addEventListener("click", () => {
    sidebar.classList.remove("open");
  });

  refs.newBtn.addEventListener("click", () => {
    if (onNewConversation) {
      onNewConversation();
    }
  });

  let conversations = [];

  /**
   * Render conversation list
   * @param {Array} convs - List of conversations
   */
  function renderConversations(convs) {
    conversations = convs;
    refs.list.innerHTML = "";

    if (convs.length === 0) {
      refs.list.innerHTML = `<div class="sidebar-empty">暂无对话历史</div>`;
      return;
    }

    convs.forEach((conv) => {
      const item = document.createElement("div");
      item.className = "sidebar-item";
      item.dataset.conversationId = conv.conversation_id;

      // 添加已归档标记
      if (conv.archived) {
        item.classList.add("sidebar-item--archived");
      }

      const title = document.createElement("div");
      title.className = "sidebar-item-title";
      title.textContent = conv.title || "新对话";

      // 已归档添加图标
      if (conv.archived) {
        title.innerHTML = `📁 ${title.textContent}`;
      }

      const meta = document.createElement("div");
      meta.className = "sidebar-item-meta";

      const time = document.createElement("span");
      time.className = "sidebar-item-time";
      time.textContent = formatRelativeTime(conv.updated_at);

      const count = document.createElement("span");
      count.className = "sidebar-item-count";
      count.textContent = `${conv.message_count} 条消息`;

      meta.appendChild(time);
      meta.appendChild(count);

      const actions = document.createElement("div");
      actions.className = "sidebar-item-actions";

      // 已归档对话不显示删除按钮
      if (!conv.archived) {
        const deleteBtn = document.createElement("button");
        deleteBtn.className = "sidebar-item-delete";
        deleteBtn.innerHTML = "🗑";
        deleteBtn.title = "删除对话";
        deleteBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          if (onDeleteConversation) {
            onDeleteConversation(conv.conversation_id);
          }
        });
        actions.appendChild(deleteBtn);
      } else {
        // 已归档标签
        const archivedLabel = document.createElement("span");
        archivedLabel.className = "sidebar-item-archived-label";
        archivedLabel.textContent = "已归档";
        actions.appendChild(archivedLabel);
      }

      item.appendChild(title);
      item.appendChild(meta);
      item.appendChild(actions);

      item.addEventListener("click", () => {
        if (onSelectConversation) {
          onSelectConversation(conv.conversation_id);
        }
      });

      refs.list.appendChild(item);
    });
  }

  /**
   * Set active conversation
   * @param {string} conversationId - Conversation ID
   */
  function setActive(conversationId) {
    refs.list.querySelectorAll(".sidebar-item").forEach((item) => {
      if (item.dataset.conversationId === conversationId) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });
  }

  /**
   * Clear active conversation
   */
  function clearActive() {
    refs.list.querySelectorAll(".sidebar-item").forEach((item) => {
      item.classList.remove("active");
    });
  }

  /**
   * Get latest conversation ID
   * @returns {string|null} - Latest conversation ID or null
   */
  function getLatestConversationId() {
    const items = refs.list.querySelectorAll(".sidebar-item");
    if (items.length > 0) {
      return items[0].dataset.conversationId;
    }
    return null;
  }

  /**
   * Format relative time
   * @param {string} timestamp - ISO timestamp
   * @returns {string} - Formatted time
   */
  function formatRelativeTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000); // seconds

    if (diff < 60) {
      return "刚刚";
    } else if (diff < 3600) {
      return `${Math.floor(diff / 60)}分钟前`;
    } else if (diff < 86400) {
      return `${Math.floor(diff / 3600)}小时前`;
    } else if (diff < 604800) {
      return `${Math.floor(diff / 86400)}天前`;
    } else {
      return date.toLocaleDateString("zh-CN");
    }
  }

  return {
    element: sidebar,
    refs,
    renderConversations,
    setActive,
    clearActive,
    getLatestConversationId,
    conversations,
  };
}

/**
 * Create health dashboard component
 * @returns {Object} - Dashboard element with render method
 */
function createHealthDashboard() {
  const dashboard = document.createElement("div");
  dashboard.className = "health-dashboard";

  // 创建健康监测区（BMI卡片）
  const bmiSection = document.createElement("section");
  bmiSection.className = "health-section";
  bmiSection.innerHTML = `
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
  `;

  // 创建指标区（血压、血糖）
  const metricsGrid = document.createElement("div");
  metricsGrid.className = "metrics-grid";
  metricsGrid.innerHTML = `
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
  `;

  // 创建设备绑定提示条
  const deviceBanner = document.createElement("div");
  deviceBanner.className = "device-banner";
  deviceBanner.innerHTML = `
    <div class="device-banner__content">
      <span class="device-banner__icon">📱</span>
      <span class="device-banner__text">绑定智能设备，自动监测更多健康数据</span>
    </div>
    <button class="device-banner__button">去绑定</button>
  `;

  // 创建健康记录网格
  const recordGrid = document.createElement("section");
  recordGrid.className = "health-section";
  recordGrid.innerHTML = `
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
  `;

  // 创建生活习惯区域
  const habitSection = document.createElement("section");
  habitSection.className = "health-section";
  habitSection.innerHTML = `
    <h2 class="health-section__title">
      生活习惯
      <button class="health-section__more">编辑</button>
    </h2>
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
  `;

  // 创建健康史网格
  const historySection = document.createElement("section");
  historySection.className = "health-section";
  historySection.innerHTML = `
    <h2 class="health-section__title">
      健康史
      <button class="health-section__more">编辑</button>
    </h2>
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
  `;

  dashboard.appendChild(bmiSection);
  dashboard.appendChild(metricsGrid);
  dashboard.appendChild(deviceBanner);
  dashboard.appendChild(recordGrid);
  dashboard.appendChild(habitSection);
  dashboard.appendChild(historySection);

  return {
    element: dashboard,
    refs: {
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
    },
    /**
     * Update BMI card with data
     * @param {Object} data - BMI data
     */
    updateBMI(data) {
      if (data.bmi) {
        this.refs.bmiValue.textContent = data.bmi;
      }
      if (data.bmi_status) {
        const statusMap = {
          underweight: "偏瘦",
          normal: "正常",
          overweight: "偏胖",
          obese: "肥胖",
        };
        this.refs.bmiStatus.textContent = statusMap[data.bmi_status] || "--";
      }
      if (data.height_cm) {
        this.refs.heightValue.textContent = `${data.height_cm} cm`;
      }
      if (data.weight_kg) {
        this.refs.weightValue.textContent = `${data.weight_kg} kg`;
      }
      if (data.updated_at) {
        const date = new Date(data.updated_at);
        this.refs.bmiUpdateTime.textContent = `更新于 ${date.toLocaleDateString()}`;
      }
    },
    /**
     * Update metrics with data
     * @param {Object} data - Metrics data
     */
    updateMetrics(data) {
      if (data.blood_pressure_systolic && data.blood_pressure_diastolic) {
        this.refs.bpValue.textContent = `${data.blood_pressure_systolic}/${data.blood_pressure_diastolic}`;
      }
      if (data.blood_sugar) {
        this.refs.sugarValue.textContent = data.blood_sugar;
      }
    },
    /**
     * Update habits with data
     * @param {Object} data - Habits data
     */
    updateHabits(data) {
      const dietMap = {
        regular: "规律",
        irregular: "不规律",
        picky: "偏食",
        overeating: "暴饮暴食",
      };
      const exerciseMap = {
        daily: "每天运动",
        weekly: "每周运动",
        rarely: "偶尔运动",
        never: "从不运动",
      };
      const sleepMap = {
        good: "良好",
        average: "一般",
        poor: "较差",
        insomnia: "失眠",
      };

      if (data.diet_habit && this.refs.habitCards.diet) {
        this.refs.habitCards.diet.textContent = dietMap[data.diet_habit] || "--";
      }
      if (data.exercise_habit && this.refs.habitCards.exercise) {
        this.refs.habitCards.exercise.textContent = exerciseMap[data.exercise_habit] || "--";
      }
      if (data.sleep_quality && this.refs.habitCards.sleep) {
        this.refs.habitCards.sleep.textContent = sleepMap[data.sleep_quality] || "--";
      }
    },
    /**
     * Update history counts
     * @param {Object} data - History counts
     */
    updateHistoryCounts(data) {
      if (this.refs.historyCounts.allergy) {
        this.refs.historyCounts.allergy.textContent = data.allergy_count || 0;
      }
      if (this.refs.historyCounts.medical) {
        this.refs.historyCounts.medical.textContent = data.medical_count || 0;
      }
      if (this.refs.historyCounts.family) {
        this.refs.historyCounts.family.textContent = data.family_count || 0;
      }
      if (this.refs.historyCounts.medication) {
        this.refs.historyCounts.medication.textContent = data.medication_count || 0;
      }
    },
    /**
     * Update health record counts
     * @param {Object} data - Record counts
     */
    updateRecordCounts(data) {
      if (this.refs.recordCounts.consultation) {
        this.refs.recordCounts.consultation.textContent = data.consultation_count || 0;
      }
      if (this.refs.recordCounts.prescription) {
        this.refs.recordCounts.prescription.textContent = data.prescription_count || 0;
      }
      if (this.refs.recordCounts.appointment) {
        this.refs.recordCounts.appointment.textContent = data.appointment_count || 0;
      }
      if (this.refs.recordCounts.document) {
        this.refs.recordCounts.document.textContent = data.document_count || 0;
      }
      if (this.refs.recordCounts.checkup) {
        this.refs.recordCounts.checkup.textContent = data.checkup_count || 0;
      }
    },
  };
}


/**
 * Create a weight trend chart component
 * @returns {Object} - Chart element and update method
 */
function createWeightTrendChart() {
  const chart = document.createElement("div");
  chart.className = "weight-trend-chart";

  chart.innerHTML = `
    <div class="trend-chart-header">
      <span class="trend-chart-title">体重趋势</span>
      <span class="trend-chart-unit">kg</span>
    </div>
    <div class="trend-chart-body" id="trend-chart-body">
      <div class="trend-chart-empty">暂无数据</div>
    </div>
  `;

  return {
    element: chart,
    refs: {
      body: chart.querySelector("#trend-chart-body"),
    },
    /**
     * Update chart with data
     * @param {Array} data - Array of {date, value} objects
     * @param {number} targetWeight - Target weight for reference line
     */
    updateData(data, targetWeight = null) {
      if (!data || data.length === 0) {
        this.refs.body.innerHTML = '<div class="trend-chart-empty">暂无数据</div>';
        return;
      }

      // 找出最大最小值用于计算比例
      const values = data.map(d => d.value);
      const minVal = Math.min(...values) * 0.95;
      const maxVal = Math.max(...values) * 1.05;
      const range = maxVal - minVal;

      // 生成柱状图HTML
      let html = '<div class="trend-chart-bars">';

      data.forEach((item, index) => {
        const heightPercent = ((item.value - minVal) / range) * 100;
        const isRecent = index === data.length - 1;

        html += `
          <div class="trend-bar-wrapper ${isRecent ? 'recent' : ''}">
            <div class="trend-bar" style="height: ${heightPercent}%;"></div>
            <div class="trend-label">${item.value}</div>
            <div class="trend-date">${item.date}</div>
          </div>
        `;
      });

      html += '</div>';

      // 添加目标线
      if (targetWeight && targetWeight >= minVal && targetWeight <= maxVal) {
        const targetPercent = ((targetWeight - minVal) / range) * 100;
        html += `
          <div class="trend-target-line" style="bottom: ${targetPercent}%;">
            <span class="trend-target-label">目标 ${targetWeight}</span>
          </div>
        `;
      }

      this.refs.body.innerHTML = html;
    },
  };
}


/**
 * Create a health metrics summary card
 * @returns {Object} - Card element and update method
 */
function createHealthMetricsSummary() {
  const summary = document.createElement("div");
  summary.className = "health-metrics-summary";

  summary.innerHTML = `
    <h3 class="metrics-summary-title">健康概览</h3>
    <div class="metrics-summary-grid">
      <div class="metric-summary-card" id="bmi-summary">
        <span class="metric-summary-icon">⚖️</span>
        <div class="metric-summary-content">
          <div class="metric-summary-label">BMI</div>
          <div class="metric-summary-value">--</div>
          <div class="metric-summary-status">--</div>
        </div>
      </div>
      <div class="metric-summary-card" id="bp-summary">
        <span class="metric-summary-icon">❤️</span>
        <div class="metric-summary-content">
          <div class="metric-summary-label">血压</div>
          <div class="metric-summary-value">--/--</div>
          <div class="metric-summary-status">--</div>
        </div>
      </div>
      <div class="metric-summary-card" id="sugar-summary">
        <span class="metric-summary-icon">🩸</span>
        <div class="metric-summary-content">
          <div class="metric-summary-label">血糖</div>
          <div class="metric-summary-value">--</div>
          <div class="metric-summary-status">--</div>
        </div>
      </div>
      <div class="metric-summary-card" id="habits-score">
        <span class="metric-summary-icon">⭐</span>
        <div class="metric-summary-content">
          <div class="metric-summary-label">健康评分</div>
          <div class="metric-summary-value">--</div>
          <div class="metric-summary-status">--</div>
        </div>
      </div>
    </div>
  `;

  return {
    element: summary,
    refs: {
      bmi: {
        value: summary.querySelector("#bmi-summary .metric-summary-value"),
        status: summary.querySelector("#bmi-summary .metric-summary-status"),
      },
      bp: {
        value: summary.querySelector("#bp-summary .metric-summary-value"),
        status: summary.querySelector("#bp-summary .metric-summary-status"),
      },
      sugar: {
        value: summary.querySelector("#sugar-summary .metric-summary-value"),
        status: summary.querySelector("#sugar-summary .metric-summary-status"),
      },
      score: {
        value: summary.querySelector("#habits-score .metric-summary-value"),
        status: summary.querySelector("#habits-score .metric-summary-status"),
      },
    },
    /**
     * Update BMI summary
     * @param {number} bmi - BMI value
     * @param {string} status - BMI status
     */
    updateBMI(bmi, status) {
      if (this.refs.bmi.value) {
        this.refs.bmi.value.textContent = bmi.toFixed(1);
      }
      if (this.refs.bmi.status) {
        const statusMap = {
          underweight: "偏瘦",
          normal: "正常",
          overweight: "偏胖",
          obese: "肥胖",
        };
        const statusClassMap = {
          underweight: "warning",
          normal: "success",
          overweight: "warning",
          obese: "danger",
        };
        this.refs.bmi.status.textContent = statusMap[status] || "--";
        this.refs.bmi.status.className = `metric-summary-status ${statusClassMap[status] || ''}`;
      }
    },
    /**
     * Update blood pressure summary
     * @param {number} systolic - 收缩压
     * @param {number} diastolic - 舒张压
     */
    updateBP(systolic, diastolic) {
      if (this.refs.bp.value) {
        this.refs.bp.value.textContent = `${systolic}/${diastolic}`;
      }
      if (this.refs.bp.status) {
        let status = "正常";
        let statusClass = "success";

        if (systolic >= 140 || diastolic >= 90) {
          status = "偏高";
          statusClass = "warning";
        }
        if (systolic >= 160 || diastolic >= 100) {
          status = "高血压";
          statusClass = "danger";
        }

        this.refs.bp.status.textContent = status;
        this.refs.bp.status.className = `metric-summary-status ${statusClass}`;
      }
    },
    /**
     * Update blood sugar summary
     * @param {number} sugar - 血糖值
     * @param {string} type - 血糖类型 (fasting/postprandial)
     */
    updateSugar(sugar, type = "fasting") {
      if (this.refs.sugar.value) {
        this.refs.sugar.value.textContent = sugar.toFixed(1);
      }
      if (this.refs.sugar.status) {
        let status = "正常";
        let statusClass = "success";
        const threshold = type === "fasting" ? 6.1 : 7.8;

        if (sugar >= threshold) {
          status = "偏高";
          statusClass = "warning";
        }
        if (sugar >= threshold + 2) {
          status = "过高";
          statusClass = "danger";
        }

        this.refs.sugar.status.textContent = status;
        this.refs.sugar.status.className = `metric-summary-status ${statusClass}`;
      }
    },
    /**
     * Update health score (基于生活习惯计算)
     * @param {Object} habits - 生活习惯数据
     */
    updateHealthScore(habits) {
      if (!this.refs.score.value) return;

      // 计算健康评分
      let score = 60; // 基础分

      if (habits.diet_habit === "regular") score += 10;
      else if (habits.diet_habit === "irregular") score += 5;

      if (habits.exercise_habit === "daily") score += 15;
      else if (habits.exercise_habit === "weekly") score += 10;
      else if (habits.exercise_habit === "rarely") score += 5;

      if (habits.sleep_quality === "good") score += 10;
      else if (habits.sleep_quality === "average") score += 5;

      if (habits.smoking_drinking === "none") score += 5;

      score = Math.min(100, Math.max(0, score));

      this.refs.score.value.textContent = score.toString();

      let status = "良好";
      let statusClass = "success";
      if (score < 60) {
        status = "需改善";
        statusClass = "danger";
      } else if (score < 80) {
        status = "一般";
        statusClass = "warning";
      }

      if (this.refs.score.status) {
        this.refs.score.status.textContent = status;
        this.refs.score.status.className = `metric-summary-status ${statusClass}`;
      }
    },
  };
}


/**
 * Create a member profile form for editing member information
 * @returns {Object} - Form element with control methods
 */
function createMemberProfileForm() {
  const form = document.createElement("div");
  form.className = "member-profile-form";

  form.innerHTML = `
    <div class="form-header">
      <h3 class="form-title">成员信息</h3>
      <button class="form-close" id="close-form">×</button>
    </div>

    <div class="form-body">
      <!-- 基础信息 -->
      <div class="form-section">
        <h4 class="form-section-title">基础信息</h4>

        <div class="form-field">
          <label class="form-label">姓名 <span class="required">*</span></label>
          <input type="text" class="form-input" id="member-name" placeholder="请输入姓名" required />
        </div>

        <div class="form-field">
          <label class="form-label">与本人关系 <span class="required">*</span></label>
          <select class="form-select" id="member-relationship" required>
            <option value="">请选择</option>
            <option value="self">本人</option>
            <option value="child">子女</option>
            <option value="spouse">配偶</option>
            <option value="parent">父母</option>
            <option value="other">其他</option>
          </select>
        </div>

        <div class="form-row">
          <div class="form-field">
            <label class="form-label">性别 <span class="required">*</span></label>
            <div class="gender-selector" id="gender-selector">
              <button class="gender-option" value="male">男</button>
              <button class="gender-option" value="female">女</button>
            </div>
            <input type="hidden" id="member-gender" />
          </div>

          <div class="form-field">
            <label class="form-label">出生日期 <span class="required">*</span></label>
            <input type="date" class="form-input" id="member-birth-date" required />
          </div>
        </div>
      </div>

      <!-- 体征信息 -->
      <div class="form-section">
        <h4 class="form-section-title">体征信息</h4>

        <div class="form-row">
          <div class="form-field">
            <label class="form-label">身高 (cm) <span class="required">*</span></label>
            <input type="number" class="form-input" id="member-height" placeholder="160" min="30" max="250" required />
          </div>

          <div class="form-field">
            <label class="form-label">体重 (kg) <span class="required">*</span></label>
            <input type="number" class="form-input" id="member-weight" placeholder="60" min="2" max="300" step="0.1" required />
          </div>
        </div>

        <div class="form-row">
          <div class="form-field">
            <label class="form-label">收缩压 (mmHg)</label>
            <input type="number" class="form-input" id="member-bp-systolic" placeholder="120" min="60" max="250" />
          </div>

          <div class="form-field">
            <label class="form-label">舒张压 (mmHg)</label>
            <input type="number" class="form-input" id="member-bp-diastolic" placeholder="80" min="40" max="150" />
          </div>
        </div>

        <div class="form-field">
          <label class="form-label">血糖 (mmol/L)</label>
          <div class="form-row">
            <input type="number" class="form-input" id="member-sugar" placeholder="5.5" min="1" max="30" step="0.1" />
            <select class="form-select" id="member-sugar-type" style="width: 120px;">
              <option value="fasting">空腹</option>
              <option value="postprandial">餐后</option>
            </select>
          </div>
        </div>
      </div>

      <!-- 生活习惯 -->
      <div class="form-section">
        <h4 class="form-section-title">生活习惯</h4>

        <div class="form-field">
          <label class="form-label">饮食习惯</label>
          <select class="form-select" id="member-diet">
            <option value="">请选择</option>
            <option value="regular">规律饮食</option>
            <option value="irregular">不规律</option>
            <option value="picky">偏食</option>
            <option value="overeating">暴饮暴食</option>
          </select>
        </div>

        <div class="form-field">
          <label class="form-label">运动习惯</label>
          <select class="form-select" id="member-exercise">
            <option value="">请选择</option>
            <option value="daily">每天运动</option>
            <option value="weekly">每周运动</option>
            <option value="rarely">偶尔运动</option>
            <option value="never">从不运动</option>
          </select>
        </div>

        <div class="form-field">
          <label class="form-label">睡眠质量</label>
          <select class="form-select" id="member-sleep">
            <option value="">请选择</option>
            <option value="good">良好</option>
            <option value="average">一般</option>
            <option value="poor">较差</option>
            <option value="insomnia">失眠</option>
          </select>
        </div>
      </div>
    </div>

    <div class="form-actions">
      <button class="form-btn form-btn--cancel" id="cancel-btn">取消</button>
      <button class="form-btn form-btn--submit" id="submit-btn">保存</button>
    </div>
  `;

  // Setup gender selector
  const genderOptions = form.querySelectorAll(".gender-option");
  const genderInput = form.querySelector("#member-gender");

  genderOptions.forEach(option => {
    option.addEventListener("click", () => {
      genderOptions.forEach(btn => btn.classList.remove("active"));
      option.classList.add("active");
      genderInput.value = option.value;
    });
  });

  return {
    element: form,
    refs: {
      name: form.querySelector("#member-name"),
      relationship: form.querySelector("#member-relationship"),
      gender: form.querySelector("#member-gender"),
      birthDate: form.querySelector("#member-birth-date"),
      height: form.querySelector("#member-height"),
      weight: form.querySelector("#member-weight"),
      bpSystolic: form.querySelector("#member-bp-systolic"),
      bpDiastolic: form.querySelector("#member-bp-diastolic"),
      sugar: form.querySelector("#member-sugar"),
      sugarType: form.querySelector("#member-sugar-type"),
      diet: form.querySelector("#member-diet"),
      exercise: form.querySelector("#member-exercise"),
      sleep: form.querySelector("#member-sleep"),
      closeBtn: form.querySelector("#close-form"),
      cancelBtn: form.querySelector("#cancel-btn"),
      submitBtn: form.querySelector("#submit-btn"),
    },
    /**
     * Set form data
     * @param {Object} data - Form data
     */
    setData(data) {
      if (data.name) this.refs.name.value = data.name;
      if (data.relationship) this.refs.relationship.value = data.relationship;
      if (data.gender) {
        this.refs.gender.value = data.gender;
        const genderBtn = form.querySelector(`.gender-option[value="${data.gender}"]`);
        if (genderBtn) genderBtn.classList.add("active");
      }
      if (data.birth_date) this.refs.birthDate.value = data.birth_date;
      if (data.height_cm) this.refs.height.value = data.height_cm;
      if (data.weight_kg) this.refs.weight.value = data.weight_kg;
      if (data.blood_pressure_systolic) this.refs.bpSystolic.value = data.blood_pressure_systolic;
      if (data.blood_pressure_diastolic) this.refs.bpDiastolic.value = data.blood_pressure_diastolic;
      if (data.blood_sugar) this.refs.sugar.value = data.blood_sugar;
      if (data.blood_sugar_type) this.refs.sugarType.value = data.blood_sugar_type;
      if (data.diet_habit) this.refs.diet.value = data.diet_habit;
      if (data.exercise_habit) this.refs.exercise.value = data.exercise_habit;
      if (data.sleep_quality) this.refs.sleep.value = data.sleep_quality;
    },
    /**
     * Get form data
     * @returns {Object} - Form data
     */
    getData() {
      return {
        name: this.refs.name.value,
        relationship: this.refs.relationship.value,
        gender: this.refs.gender.value,
        birth_date: this.refs.birthDate.value,
        height_cm: parseFloat(this.refs.height.value),
        weight_kg: parseFloat(this.refs.weight.value),
        blood_pressure_systolic: this.refs.bpSystolic.value ? parseInt(this.refs.bpSystolic.value) : null,
        blood_pressure_diastolic: this.refs.bpDiastolic.value ? parseInt(this.refs.bpDiastolic.value) : null,
        blood_sugar: this.refs.sugar.value ? parseFloat(this.refs.sugar.value) : null,
        blood_sugar_type: this.refs.sugarType.value || null,
        diet_habit: this.refs.diet.value || null,
        exercise_habit: this.refs.exercise.value || null,
        sleep_quality: this.refs.sleep.value || null,
      };
    },
    /**
     * Validate form
     * @returns {Object} - Validation result
     */
    validate() {
      const data = this.getData();
      const errors = [];

      if (!data.name) errors.push("请输入姓名");
      if (!data.relationship) errors.push("请选择与本人关系");
      if (!data.gender) errors.push("请选择性别");
      if (!data.birth_date) errors.push("请选择出生日期");
      if (!data.height_cm || data.height_cm < 30 || data.height_cm > 250) {
        errors.push("请输入正确的身高");
      }
      if (!data.weight_kg || data.weight_kg < 2 || data.weight_kg > 300) {
        errors.push("请输入正确的体重");
      }

      return {
        valid: errors.length === 0,
        errors,
      };
    },
    /**
     * Setup event listeners
     * @param {Object} handlers - Event handlers
     */
    bindEvents(handlers) {
      if (handlers.onClose) {
        this.refs.closeBtn.addEventListener("click", handlers.onClose);
        this.refs.cancelBtn.addEventListener("click", handlers.onClose);
      }
      if (handlers.onSubmit) {
        this.refs.submitBtn.addEventListener("click", handlers.onSubmit);
      }
    },
  };
}

// Export all functions to global scope for use in app.js
window.createArchiveConfirmModal = createArchiveConfirmModal;
window.createDisclaimerModal = createDisclaimerModal;
window.createHeader = createHeader;
window.createTabs = createTabs;
window.createChat = createChat;
window.createWelcomeScreen = createWelcomeScreen;
window.createChatBubble = createChatBubble;
window.createComposer = createComposer;
window.createSourceSheet = createSourceSheet;
window.createStreamBubble = createStreamBubble;
window.createTriageResultCard = createTriageResultCard;
window.createDangerSignalModal = createDangerSignalModal;
window.createSlotTracker = createSlotTracker;
window.createQuickReplies = createQuickReplies;
window.createFollowUpForm = createFollowUpForm;
window.createConversationSidebar = createConversationSidebar;
window.createHealthDashboard = createHealthDashboard;
window.createMemberProfileForm = createMemberProfileForm;
window.createWeightTrendChart = createWeightTrendChart;
window.createHealthMetricsSummary = createHealthMetricsSummary;
window.showPersistentEmergencyBanner = showPersistentEmergencyBanner;
