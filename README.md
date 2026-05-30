# Multiple-Ai-Cooperating-Operation-System
A LangGraph-based multi-agent autonomous work system with browser automation, MCP integration, and One-API model routing.

# 多 Agent 自主工作系统

一个基于 **LangGraph** 的多 Agent 自主工作系统，使用 **One-API** 统一路由模型，默认接入 **DeepSeek** 作为推理核心，结合 **Browser-Use** 完成浏览器自动化，并通过 **MCP** 接入本地文件系统与工具能力。

> 目标：让模型不只是“回答问题”，而是能够“拆解任务、调用工具、执行操作、输出结果”。

---

## 核心能力

- **任务编排 (workflow orchestration)**：基于 LangGraph 构建监督式工作流。
- **模型路由 (model routing)**：通过 One-API 统一管理后端模型。
- **浏览器自动化 (browser automation)**：使用 Browser-Use 执行网页搜索、页面浏览与结果总结。
- **本地工具接入 (tool integration)**：通过 MCP 接入文件系统等本地能力。
- **自主任务循环 (agent loop)**：Supervisor 决定下一步交给哪个 Agent 执行，直到任务完成。
- **可扩展架构 (extensible architecture)**：后续可继续接入代码执行、持久记忆、更多工具与更复杂的 Agent。

---

## 系统架构

本项目采用“监督节点 + 执行节点”的方式：

```mermaid
graph TD
    U[用户输入] --> S[Supervisor]
    S -->|联网搜索 / 网页操作| B[BrowserAgent]
    S -->|文件操作 / 本地任务| M[MCPAgent]
    B --> S
    M --> S
    S --> E[结束]



##节点说明

Supervisor：解析用户任务，判断下一步应该调用哪个 Agent。
BrowserAgent：负责联网搜索、浏览网页、提取摘要。
MCPAgent：负责本地文件读写与工具调用。
END：任务完成后结束当前轮执行。
技术栈
Python
LangGraph
LangChain
DeepSeek
One-API
Browser-Use
MCP (Model Context Protocol)
Windows
（可选）ChromaDB：持久记忆
（可选）代码执行模块：安全执行本地代码任务
目录结构
.
├─ main.py
├─ .env
├─ API.txt
├─ one-api.db
├─ one-api.exe
├─ start.ps1
├─ test_mcp.py
├─ workspace/
├─ Python/
├─ venv/
└─ logs/
功能演示
1. 联网搜索

输入类似下面的任务：

搜索 DeepSeek 最新进展并总结 3 条核心信息

系统会自动调用浏览器能力进行检索，并返回中文摘要。

2. 文件操作

输入类似下面的任务：

把今天的任务整理成报告并保存到本地

系统会通过 MCP 写入本地工作区文件。

环境要求
Python 3.10+
Node.js
可用的 npx
Windows 环境（当前版本针对 Windows 做了适配）
一个可用的 One-API 服务地址与 Key
可访问浏览器自动化所需的 Chrome 环境
安装
1. 克隆仓库
git clone https://github.com/你的用户名/你的仓库名.git
cd 你的仓库名
2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate
3. 安装依赖
pip install -r requirements.txt
4. 安装 Node 依赖 / MCP 组件

确保 npx 可用，并能正常执行：

npx -v
配置

创建 .env 文件：

ONE_API_BASE=https://你的-one-api地址/v1
ONE_API_KEY=你的key
CLAUDE_MODEL=deepseek-chat
WORKSPACE_DIR=D:\MultiAgentSystem\workspace
参数说明
变量名	说明
ONE_API_BASE	One-API 接口地址
ONE_API_KEY	One-API 密钥
CLAUDE_MODEL	实际调用的模型名，默认可设为 deepseek-chat
WORKSPACE_DIR	工作区目录，用于本地文件读写
运行
python main.py

启动后可以直接输入自然语言任务，例如：

搜索 DeepSeek 最新进展并保存报告

退出方式：

exit
quit
退出
实现细节
Supervisor 任务分发

系统会让 Supervisor 先判断任务类型，并输出标准 JSON：

{
  "next": "BrowserAgent",
  "instruction": "具体搜索关键词"
}

可选值：

BrowserAgent
MCPAgent
FINISH
浏览器失败兜底

Browser-Use 失败时，系统会自动切换到 HTTP 兜底方案，尽量保证任务能继续执行。

Windows 兼容处理

项目在 Windows 下显式设置了事件循环策略，并在结束时清理 Chrome 进程，减少残留。

已知限制
当前实现偏向 Windows 环境。
搜索结果质量受网页结构与网络环境影响。
浏览器自动化依赖目标网站页面结构，网站改版后可能需要调整。
当前 Supervisor 使用 JSON 输出约束，若模型输出格式不稳定，可能需要进一步加固解析逻辑。
若要上生产级，建议补充：
更强的错误重试机制
统一日志系统
记忆层
代码执行沙箱
任务队列 / 并发控制
后续计划
 接入 ChromaDB 持久记忆
 接入代码执行工具
 增加更多 Agent（如数据分析、文档生成、邮件处理）
 增加任务可视化界面
 增加多轮任务规划与中间态保存
 增加更稳健的浏览器策略与重试机制
免责声明

本项目用于学习、研究与自动化工作流探索。请在合法合规范围内使用浏览器自动化、本地文件访问与工具调用能力。

致谢
LangGraph
LangChain
Browser-Use
MCP
One-API
DeepSeek
