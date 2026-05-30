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
