const commands = [
  './scripts/run.sh init --lang zh-CN --user-name "你的名字"',
  './scripts/run.sh boot --mode auto',
  './scripts/run.sh sync deep',
  './scripts/run.sh review --from-log --interactive yes --min-score 0.45',
  './scripts/run.sh graduate --threshold 3',
  './scripts/run.sh archive --week 2026-W09',
  './scripts/run.sh check --strict',
  './scripts/run.sh test',
];

const phases = [
  {
    name: '周一启动',
    focus: '口述目标，建立本周任务清单。',
    action: 'run.sh init / boot',
  },
  {
    name: '周中推进',
    focus: '产出文档后同步，保持周文件自动更新。',
    action: 'run.sh sync light|deep',
  },
  {
    name: '周末复盘',
    focus: '批量确认记忆候选，做毕业与归档。',
    action: 'run.sh review / graduate / archive',
  },
];

const files = [
  '/Users/zhang/Desktop/Claude/memory-work-codex/00 专注区/_本周.md',
  '/Users/zhang/Desktop/Claude/memory-work-codex/MEMORY.md',
  '/Users/zhang/Desktop/Claude/memory-work-codex/USER.md',
  '/Users/zhang/Desktop/Claude/memory-work-codex/scenarios/acceptance.md',
  '/Users/zhang/Desktop/Claude/memory-work-codex/sample_week/README.md',
];

function copyText(text) {
  navigator.clipboard.writeText(text).catch(() => {});
}

function renderCommands() {
  const root = document.getElementById('cmdList');
  commands.forEach((cmd) => {
    const row = document.createElement('div');
    row.className = 'cmd';
    row.innerHTML = `<code>${cmd}</code>`;

    const btn = document.createElement('button');
    btn.textContent = '复制';
    btn.addEventListener('click', () => {
      copyText(cmd);
      btn.textContent = '已复制';
      setTimeout(() => (btn.textContent = '复制'), 1000);
    });

    row.appendChild(btn);
    root.appendChild(row);
  });
}

function renderPhases() {
  const tabs = document.getElementById('phaseTabs');
  const panel = document.getElementById('phasePanel');

  const setActive = (idx) => {
    [...tabs.children].forEach((node, i) => node.classList.toggle('active', i === idx));
    panel.innerHTML = `
      <h3>${phases[idx].name}</h3>
      <p>${phases[idx].focus}</p>
      <p><strong>命令：</strong><code>${phases[idx].action}</code></p>
    `;
  };

  phases.forEach((phase, idx) => {
    const button = document.createElement('button');
    button.className = 'tab';
    button.textContent = phase.name;
    button.addEventListener('click', () => setActive(idx));
    tabs.appendChild(button);
  });

  setActive(0);
}

function renderFiles() {
  const list = document.getElementById('fileList');
  files.forEach((path) => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = path;
    a.textContent = path;
    li.appendChild(a);
    list.appendChild(li);
  });
}

function bindStarterCopy() {
  const btn = document.getElementById('copyStarter');
  const block = [
    'cd /Users/zhang/Desktop/Claude/memory-work-codex',
    './scripts/run.sh demo',
    './scripts/run.sh init --lang zh-CN --user-name "你的名字"',
    './scripts/run.sh boot --mode auto',
  ].join('\n');

  btn.addEventListener('click', () => {
    copyText(block);
    btn.textContent = '已复制';
    setTimeout(() => (btn.textContent = '复制完整体验命令'), 1200);
  });
}

renderCommands();
renderPhases();
renderFiles();
bindStarterCopy();
