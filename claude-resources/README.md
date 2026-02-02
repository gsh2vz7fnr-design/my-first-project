# Claude 资源目录说明

这个目录包含了Claude Code相关的技能和工作流资源。

## 📁 目录结构

```
claude-resources/
├── official-skills/          # 官方技能仓库
│   └── anthropic-skills/     # Anthropic官方技能集合
│       ├── skills/           # 各种示例技能
│       ├── spec/             # Agent Skills规范
│       └── template/         # 技能模板
│
├── workflows/                # 工作流系统
│   └── superpowers/          # Obra的Superpowers开发工作流
│       ├── skills/           # 工作流相关技能
│       ├── agents/           # 代理配置
│       ├── commands/         # 命令定义
│       └── hooks/            # 钩子脚本
│
└── downloaded-skills/        # 下载的第三方技能
    └── ui-ux-pro-max-skill/  # UI/UX设计智能技能
        ├── src/              # 源代码
        ├── cli/              # CLI工具
        └── .claude/          # Claude配置
```

## 🎯 实际使用的技能位置

Claude Code实际加载技能的位置：
```
~/.config/claude-code/skills/
└── ui-ux-pro-max/            # 已安装的UI/UX技能
```

## 📦 技能管理

### 安装新技能到Claude Code

1. **从本地安装**：
   ```bash
   cp -r claude-resources/downloaded-skills/ui-ux-pro-max-skill/.claude/skills/ui-ux-pro-max ~/.config/claude-code/skills/
   ```

2. **从GitHub安装**：
   ```bash
   cd claude-resources/downloaded-skills/
   git clone https://github.com/username/skill-name.git
   cp -r skill-name/.claude/skills/skill-name ~/.config/claude-code/skills/
   ```

### 查看已安装的技能

```bash
ls -la ~/.config/claude-code/skills/
```

### 卸载技能

```bash
rm -rf ~/.config/claude-code/skills/skill-name
```

## 🔧 Superpowers工作流

Superpowers是一个完整的软件开发工作流系统，包含：

- **brainstorming** - 头脑风暴
- **writing-plans** - 编写计划
- **executing-plans** - 执行计划
- **test-driven-development** - 测试驱动开发
- **systematic-debugging** - 系统化调试
- **requesting-code-review** - 请求代码审查
- **receiving-code-review** - 接收代码审查
- **finishing-a-development-branch** - 完成开发分支

### 安装Superpowers到Claude Code

```bash
# 方法1：通过插件市场（推荐）
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace

# 方法2：手动安装
cp -r claude-resources/workflows/superpowers/skills/* ~/.config/claude-code/skills/
```

## 📚 官方技能仓库

Anthropic官方技能仓库包含多个示例技能：

### 创意与设计
- algorithmic-art - 算法艺术
- canvas-design - 画布设计
- frontend-design - 前端设计

### 开发与技术
- mcp-builder - MCP服务器构建
- test-driven-development - 测试驱动开发

### 企业与沟通
- brand-guidelines - 品牌指南
- internal-comms - 内部沟通
- competitive-analysis - 竞争分析

### 文档技能
- docx - Word文档处理
- pdf - PDF文档处理
- pptx - PowerPoint处理
- xlsx - Excel处理

### 安装官方技能

```bash
# 通过插件市场
/plugin marketplace add anthropics/skills
/plugin install document-skills@anthropic-agent-skills
/plugin install example-skills@anthropic-agent-skills
```

## 🎨 UI/UX Pro Max 技能

已安装的UI/UX设计智能技能，提供：

- **67种UI样式** - Glassmorphism、Minimalism、Brutalism等
- **96种调色板** - 行业特定配色方案
- **57种字体配对** - 精选字体组合
- **25种图表类型** - 数据可视化建议
- **13种技术栈** - React、Vue、Next.js、SwiftUI等
- **99条UX指南** - 最佳实践和反模式
- **100条推理规则** - 行业特定设计系统生成

### 使用方法

技能会在UI/UX相关请求时自动激活，触发关键词：
- 动作：build, create, design, implement, review, fix, improve
- 项目：website, landing page, dashboard, e-commerce, SaaS
- 元素：button, modal, navbar, sidebar, card, form
- 样式：glassmorphism, minimalism, dark mode, responsive

### 手动调用

```bash
# 生成设计系统
python3 ~/.config/claude-code/skills/ui-ux-pro-max/scripts/search.py "healthcare medical" --design-system

# 搜索特定领域
python3 ~/.config/claude-code/skills/ui-ux-pro-max/scripts/search.py "glassmorphism" --domain style

# 获取技术栈指南
python3 ~/.config/claude-code/skills/ui-ux-pro-max/scripts/search.py "responsive" --stack html-tailwind
```

## 🔄 更新技能

### 更新UI/UX Pro Max

```bash
cd claude-resources/downloaded-skills/ui-ux-pro-max-skill
git pull origin main
cp -r .claude/skills/ui-ux-pro-max ~/.config/claude-code/skills/
```

### 更新Superpowers

```bash
cd claude-resources/workflows/superpowers
git pull origin main
# 然后重新安装需要的技能
```

### 更新官方技能

```bash
cd claude-resources/official-skills/anthropic-skills
git pull origin main
# 然后重新安装需要的技能
```

## 📝 创建自定义技能

1. 使用官方模板：
   ```bash
   cp -r claude-resources/official-skills/anthropic-skills/template my-custom-skill
   cd my-custom-skill
   # 编辑 SKILL.md
   ```

2. 安装到Claude Code：
   ```bash
   cp -r my-custom-skill ~/.config/claude-code/skills/
   ```

## 🔗 相关链接

- [Agent Skills 官方文档](https://support.claude.com/en/articles/12512176-what-are-skills)
- [Agent Skills 规范](http://agentskills.io)
- [Anthropic Skills 仓库](https://github.com/anthropics/skills)
- [Superpowers 仓库](https://github.com/obra/superpowers)
- [UI/UX Pro Max 仓库](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)

## 📊 当前状态

- ✅ UI/UX Pro Max 已安装并可用
- ⏳ Superpowers 工作流已下载，待安装
- ⏳ 官方技能仓库已下载，可按需安装

---

**最后更新**: 2024-01-28
**维护者**: Zhang
