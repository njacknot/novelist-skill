# 安装说明

`novelist` 是一个遵循 [Agent Skills 开放标准](https://github.com/obra/Skills) 的技能。本文件说明如何在 Codex CLI 和 Gemini CLI（以及其他兼容工具）中安装本技能。

---

## 一键安装（推荐）

```bash
git clone https://github.com/njacknot/novelist-skill.git
cd novelist-skill
./scripts/install.sh --tool codex
# 或
./scripts/install.sh --tool gemini
# 其他：claude-code / opencode / antigravity
```

脚本会把整个 skill 目录复制到对应工具的用户级 skills 目录下：

| 工具 | 默认安装目录 |
|------|--------------|
| Codex CLI | `~/.codex/skills/novelist/` |
| Gemini CLI | `~/.gemini/skills/novelist/` |
| Claude Code | `~/.claude/skills/novelist/` |
| OpenCode | `~/.opencode/skills/novelist/` |
| Antigravity | `~/.antigravity/skills/novelist/` |

加 `--force` 覆盖已有安装：

```bash
./scripts/install.sh --tool codex --force
```

---

## Codex CLI

### 全局（用户级）

```bash
git clone https://github.com/njacknot/novelist-skill.git ~/.codex/skills/novelist
```

### 项目级

```bash
cd /path/to/your/project
mkdir -p .codex/skills
git clone https://github.com/njacknot/novelist-skill.git .codex/skills/novelist
```

### 使用 `gh skill`（Github CLI v2.90+）

```bash
gh skill install njacknot/novelist-skill --agent codex --scope user
```

### 触发

在 Codex CLI 交互会话或 `codex exec` 命令中，只要你的请求和 `SKILL.md` 的 `description` 匹配（例如包含"写小说"、"创作故事"、"续写章节"等关键词），Codex 会自动激活本 skill。

也可以显式触发：

```
/learn novelist
用 novelist 帮我写一部悬疑小说
/一键开书
```

---

## Gemini CLI

### 工作区（workspace）

Gemini CLI 支持两个路径作为工作区 skill 目录，任选其一：

```bash
mkdir -p .gemini/skills
git clone https://github.com/njacknot/novelist-skill.git .gemini/skills/novelist
```

或使用别名（与其他 Agent 兼容）：

```bash
mkdir -p .agents/skills
git clone https://github.com/njacknot/novelist-skill.git .agents/skills/novelist
```

### 用户级（~）

```bash
mkdir -p ~/.gemini/skills
git clone https://github.com/njacknot/novelist-skill.git ~/.gemini/skills/novelist
```

### 验证

启动 Gemini CLI 后：

```
/skills list
```

应能看到 `novelist`。

### 触发

Gemini CLI 会根据 `SKILL.md` 的 `description` 自动决策何时激活本 skill。也可以显式说：

```
用 novelist 开始一部武侠小说
```

详见 [Gemini CLI Skills 文档](https://geminicli.com/docs/cli/skills/)。

---

## Claude Code / OpenCode / Antigravity

同样是把仓库克隆到对应工具的 skills 目录下：

```bash
git clone https://github.com/njacknot/novelist-skill.git ~/.claude/skills/novelist
git clone https://github.com/njacknot/novelist-skill.git ~/.opencode/skills/novelist
git clone https://github.com/njacknot/novelist-skill.git ~/.antigravity/skills/novelist
```

---

## 更新

进入 skill 目录拉最新代码即可：

```bash
cd ~/.codex/skills/novelist  # 或对应路径
git pull
```

---

## 卸载

```bash
rm -rf ~/.codex/skills/novelist    # Codex CLI
rm -rf ~/.gemini/skills/novelist   # Gemini CLI
# 其他工具同理
```

---

## 依赖

- **Python 3.8+**（仅用于 `scripts/check_chapter_wordcount.py` 字数检查脚本，零外部依赖）
- **Git**（安装方式）

其他机制（RAG 检索、知识图谱、大纲锚点等）都是通过 SKILL.md 指导 AI 自身执行，不需要外部服务。

---

## 常见问题

**Q: Codex CLI / Gemini CLI 没有自动触发这个 skill？**
A: 检查 `~/.codex/skills/` 或 `~/.gemini/skills/` 下的 `novelist/SKILL.md` 是否存在；重启 CLI；或显式说"用 novelist 写小说"。

**Q: 能同时给多个 CLI 安装吗？**
A: 能。用 `./scripts/install.sh --tool <name>` 分别安装即可。也可以用符号链接节省空间：
```bash
ln -sf /path/to/novelist-skill ~/.codex/skills/novelist
ln -sf /path/to/novelist-skill ~/.gemini/skills/novelist
```

**Q: 专业模式的 RAG / 知识图谱需要外部 API 吗？**
A: 不需要。所有检索、图谱构建、节奏审查都由 AI 自身执行（LLM 读正文+调用规范文档），零外部依赖。

**Q: 简易模式和专业模式如何切换？**
A: 在对话中说 `/专业模式` 或 `/简易模式` 即可。默认简易模式，首次开长篇（目标规模 100 万字以上）时建议切换到专业模式。
