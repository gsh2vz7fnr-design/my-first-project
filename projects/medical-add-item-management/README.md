# 体检报告加项管理系统

一个基于 React + TypeScript + Ant Design 的 B 端后台管理页面，用于医生或运营人员为用户的体检报告添加额外检查项目。

## 功能特性

### 核心功能
- ✅ **用户选择**：搜索并选择需要加项的用户
- ✅ **多项目添加**：支持一次性添加多个检查项目
- ✅ **动态表单**：可动态增删加项项目
- ✅ **自动计算**：实时计算总价格
- ✅ **列表管理**：展示所有加项单记录

### 列表功能
- 🔍 **搜索**：支持按用户姓名、加项单编号、体检编号搜索
- 🎯 **筛选**：支持按状态、时间范围筛选
- 📄 **分页**：标准分页功能
- 👁️ **查看详情**：查看加项单完整信息
- ✏️ **编辑**：修改加项单信息
- 📤 **导出**：导出单条加项单为文本文件
- 🗑️ **删除**：删除加项单记录

### 状态管理
- 待支付（pending）
- 已支付（paid）
- 已完成（completed）

## 技术栈

- **前端框架**：React 18 + TypeScript
- **UI 组件库**：Ant Design 5.x
- **构建工具**：Vite
- **日期处理**：dayjs
- **状态管理**：React Hooks

## 快速开始

### 安装依赖
```bash
npm install
```

### 启动开发服务器
```bash
npm run dev
```

访问 http://localhost:5173/ 即可查看页面

### 构建生产版本
```bash
npm run build
```

### 预览生产版本
```bash
npm run preview
```

## 项目结构

```
src/
├── components/          # 组件目录
│   ├── AddItemModal.tsx        # 新增/编辑加项弹窗
│   └── OrderDetailModal.tsx    # 查看详情弹窗
├── pages/              # 页面目录
│   ├── AddItemManagement.tsx   # 主页面
│   └── AddItemManagement.css   # 页面样式
