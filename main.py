"""
多 Agent 自主系统 - main.py（v5 最终修正版）

v5 修正点：
  [G] AIMessage 猴子补丁（monkey patch）：在模块级别给 AIMessage.__init__ 打补丁，
      确保所有 AIMessage 实例（包括 LangChain 内部创建的）都有 .usage 属性，
      彻底解决 'AIMessage' object has no attribute 'usage' 问题
  [H] HTTP 兜底函数改为纯同步函数，用 run_in_executor 正确调用，
      消除 asyncio.run() 嵌套导致的兜底方案静默失败问题
"""

# =====================================================================
# 0. Windows 事件循环策略 —— 必须在所有 import 之前
# =====================================================================
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# =====================================================================
# 1. import
# =====================================================================
import asyncio
import datetime
import html
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from typing import Annotated, Sequence, TypedDict

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from browser_use import Agent as BrowserUseAgent, Browser

# =====================================================================
# 2. [修正 G] AIMessage 猴子补丁
#    必须在所有其他代码之前执行。
#    LangChain 内部创建 AIMessage 时不带 .usage，
#    browser-use 访问该属性时崩溃。
#    通过包装 __init__ 确保每个实例都有 .usage = None。
# =====================================================================
_original_ai_message_init = AIMessage.__init__

def _patched_ai_message_init(self, *args, **kwargs):
    _original_ai_message_init(self, *args, **kwargs)
    if not hasattr(self, "usage"):
        self.usage = None

AIMessage.__init__ = _patched_ai_message_init

# =====================================================================
# 3. 环境变量
# =====================================================================
load_dotenv()

ONE_API_BASE  = os.environ["ONE_API_BASE"]
ONE_API_KEY   = os.environ["ONE_API_KEY"]
CLAUDE_MODEL  = os.environ.get("CLAUDE_MODEL", "deepseek-chat")
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", r"D:\MultiAgentSystem\workspace")

# =====================================================================
# 4. LLM
# =====================================================================
raw_llm = ChatOpenAI(
    model=CLAUDE_MODEL,
    openai_api_key=ONE_API_KEY,
    openai_api_base=ONE_API_BASE,
    temperature=0.0,
)

class LLMProxy:
    def __init__(self, llm):
        self._llm       = llm
        self.provider   = "openai"
        self.model_name = CLAUDE_MODEL

    def __getattr__(self, name):
        return getattr(self._llm, name)

    async def ainvoke(self, messages, config=None, **kwargs):
        if config is not None:
            return await self._llm.ainvoke(messages, config, **kwargs)
        return await self._llm.ainvoke(messages, **kwargs)

    def invoke(self, messages, config=None, **kwargs):
        if config is not None:
            return self._llm.invoke(messages, config, **kwargs)
        return self._llm.invoke(messages, **kwargs)

llm = LLMProxy(raw_llm)

# =====================================================================
# 5. 工具函数
# =====================================================================
def kill_chrome_processes():
    if sys.platform == "win32":
        subprocess.run("taskkill /f /im chrome.exe >nul 2>&1",      shell=True)
        subprocess.run("taskkill /f /im chromedriver.exe >nul 2>&1", shell=True)


def extract_browser_result(result) -> str:
    if hasattr(result, "final_result"):
        val = result.final_result
        if callable(val):
            return str(val())
        if val is not None:
            return str(val)
    if hasattr(result, "history") and result.history:
        return str(result.history[-1])
    return str(result)


# [修正 H] 纯同步函数，正确放入 run_in_executor
def fetch_baidu_snippets_sync(keyword: str) -> str:
    """
    同步 HTTP 请求百度搜索，解析摘要文本。
    不依赖 browser-use，不受 DeepSeek 模型能力限制。
    """
    url = "https://www.baidu.com/s?wd=" + urllib.parse.quote(keyword)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")

    # 尝试多种摘要选择器
    # Baidu class 名高度混淆，不依赖 class 匹配；
    # 直接去掉所有标签后提取长度 > 40 的文本块
    # 先移除 script / style / noscript 块，减少噪音
    raw_clean = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', '', raw, flags=re.S|re.I)
    all_texts = re.findall(r'>([^<]{40,})<', raw_clean)

    cleaned = []
    skip_keywords = ["百度", "搜索", "登录", "注册", "cookie", "Copyright", "©", "javascript"]
    for t in all_texts:
        text = html.unescape(t).strip()
        text = re.sub(r'\s+', ' ', text)
        if any(kw.lower() in text.lower() for kw in skip_keywords):
            continue
        if len(text) > 40:
            cleaned.append(text)

    # 去重（保序）
    seen, deduped = set(), []
    for t in cleaned:
        key = t[:30]
        if key not in seen:
            seen.add(key)
            deduped.append(t)

    return "\n\n".join(deduped[:5]) if deduped else ""

# =====================================================================
# 6. 全局浏览器单例
# =====================================================================
class GlobalBrowser:
    _instance = None

    @classmethod
    def get_browser(cls) -> Browser:
        if cls._instance is None:
            cls._instance = Browser()
        return cls._instance

    @classmethod
    async def shutdown(cls):
        if cls._instance is not None:
            try:
                await cls._instance.close()
            except Exception:
                pass
            cls._instance = None

# =====================================================================
# 7. Agent 状态
# =====================================================================
class AgentState(TypedDict):
    messages:    Annotated[Sequence[BaseMessage], add_messages]
    next:        str
    instruction: str

# =====================================================================
# 8. Supervisor 节点
# =====================================================================
async def supervisor_node(state: AgentState) -> dict:
    system_msg = SystemMessage(content="""你是一个任务主管（Supervisor）。
根据用户请求，决定下一步由哪个 Agent 执行：

- 如果需要搜索实时网络信息 → 输出 {"next": "BrowserAgent", "instruction": "具体搜索关键词"}
- 如果需要读写文件或本地操作 → 输出 {"next": "MCPAgent",     "instruction": "文件操作细节"}
- 如果任务已完成或无法继续  → 输出 {"next": "FINISH",        "instruction": "完成摘要"}

规则：只输出纯 JSON，不加任何前缀、后缀或 markdown 代码块。
""")

    try:
        response = await llm.ainvoke([system_msg] + list(state["messages"]))
        content  = response.content.strip()
        content  = content.replace("```json", "").replace("```", "").strip()
        data     = json.loads(content)

        next_node   = data.get("next", "FINISH")
        instruction = data.get("instruction", "任务完成")

        if next_node not in ("BrowserAgent", "MCPAgent", "FINISH"):
            next_node = "FINISH"

        return {"next": next_node, "instruction": instruction}

    except json.JSONDecodeError as e:
        print(f"⚠️  Supervisor JSON 解析失败: {e}")
        return {"next": "FINISH", "instruction": "JSON 解析失败，终止。"}
    except Exception as e:
        print(f"❌ Supervisor 异常: {e}")
        return {"next": "FINISH", "instruction": f"Supervisor 错误: {e}"}

# =====================================================================
# 9. Browser Agent 节点
# =====================================================================
async def browser_node(state: AgentState) -> dict:
    instruction = state.get("instruction", "")
    print(f"\n🌐 [BrowserAgent] 执行: {instruction}")

    summary = ""

    # --- 主路径：browser-use ---
    task = (
        f"打开百度 https://www.baidu.com，"
        f"如果出现 Cookie 同意弹窗，点击'接受'或'同意'按钮关闭它，"
        f"然后在搜索框搜索「{instruction}」，"
        f"浏览搜索结果，用中文总结3条核心内容并返回。"
    )
    try:
        # 不传 browser= 参数，让 browser-use 自己管理浏览器生命周期
        # GlobalBrowser 单例在多次运行后状态会损坏，导致 BrowserStateRequestEvent -> {}
        agent  = BrowserUseAgent(
            task=task,
            llm=llm,
        )
        result  = await agent.run(max_steps=15)
        raw_sum = extract_browser_result(result)
        if raw_sum and raw_sum != "None":
            summary = raw_sum
    except Exception as e:
        print(f"⚠️  browser-use 失败（{e}），切换到 HTTP 兜底方案…")

    # --- 兜底路径：同步 HTTP 请求放入线程池 ---
    # [修正 H] fetch_baidu_snippets_sync 是纯同步函数，
    #           用 run_in_executor 正确执行，不嵌套 asyncio.run()
    if not summary:
        try:
            print("🔄 正在用 HTTP 方式抓取百度搜索结果…")
            loop    = asyncio.get_event_loop()
            summary = await loop.run_in_executor(
                None, fetch_baidu_snippets_sync, instruction
            )
        except Exception as e2:
            print(f"❌ HTTP 兜底也失败: {e2}")

    if not summary:
        summary = f"搜索「{instruction}」未能获取结果，请检查网络连接。"

    print(f"✅ [BrowserAgent] 完成，结果长度: {len(summary)} 字符")
    return {"messages": [AIMessage(content=f"🌐 网络搜索结果:\n{summary}")]}

# =====================================================================
# 10. MCP Agent 节点工厂
# =====================================================================
def mcp_node_factory(session: ClientSession):
    async def mcp_node(state: AgentState) -> dict:
        instruction = state.get("instruction", "")
        print(f"\n📁 [MCPAgent] 执行: {instruction}")

        try:
            tools      = await session.list_tools()
            tool_names = [t.name for t in tools.tools] if hasattr(tools, "tools") else []
            print(f"   MCP 可用工具: {tool_names}")

            report_path    = os.path.join(WORKSPACE_DIR, "report.txt")
            report_content = (
                f"=== 任务报告 ===\n"
                f"指令: {instruction}\n"
                f"生成时间: {datetime.datetime.now().isoformat()}\n"
            )

            if "write_file" in tool_names:
                await session.call_tool(
                    "write_file",
                    {"path": report_path, "content": report_content},
                )
            else:
                os.makedirs(WORKSPACE_DIR, exist_ok=True)
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(report_content)

            print(f"✅ [MCPAgent] 文件已写入: {report_path}")
            return {"messages": [AIMessage(content=f"📁 report.txt 已更新，路径: {report_path}")]}

        except Exception as e:
            print(f"❌ [MCPAgent] 失败: {e}")
            return {"messages": [AIMessage(content=f"📁 文件操作失败: {e}")]}

    return mcp_node

# =====================================================================
# 11. 构建工作流
# =====================================================================
def build_workflow(mcp_node) -> StateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("Supervisor",   supervisor_node)
    workflow.add_node("BrowserAgent", browser_node)
    workflow.add_node("MCPAgent",     mcp_node)
    workflow.add_edge(START, "Supervisor")
    workflow.add_conditional_edges(
        "Supervisor",
        lambda state: state["next"],
        {"BrowserAgent": "BrowserAgent", "MCPAgent": "MCPAgent", "FINISH": END},
    )
    workflow.add_edge("BrowserAgent", "Supervisor")
    workflow.add_edge("MCPAgent",     "Supervisor")
    return workflow

# =====================================================================
# 12. 主程序
# =====================================================================
async def main():
    kill_chrome_processes()
    print("🔧 正在连接 MCP 文件服务器...")

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", WORKSPACE_DIR],
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ MCP 服务器连接成功")

                mcp_node = mcp_node_factory(session)
                app      = build_workflow(mcp_node).compile()

                print("\n✅ 系统就绪。输入指令开始执行，输入 exit 退出。")
                print("示例：搜索 DeepSeek 最新进展并保存报告")

                while True:
                    print()
                    try:
                        user_input = input(">>> 请输入指令：").strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\n👋 已退出")
                        break

                    if not user_input:
                        continue
                    if user_input.lower() in ("exit", "quit", "退出"):
                        print("👋 已退出")
                        break

                    print(f"\n🚀 开始执行: {user_input}\n{'─'*50}")
                    try:
                        async for chunk in app.astream(
                            {"messages": [HumanMessage(content=user_input)]}
                        ):
                            for node_name, node_output in chunk.items():
                                if node_name == "__end__":
                                    continue
                                msgs = node_output.get("messages", [])
                                for msg in msgs:
                                    if hasattr(msg, "content") and msg.content:
                                        print(f"[{node_name}] {msg.content[:300]}")
                        print(f"{'─'*50}\n✅ 执行完毕，可继续输入下一条指令")
                    except Exception as e:
                        print(f"❌ 执行出错: {e}，可继续输入下一条指令")

    except FileNotFoundError:
        print("❌ 找不到 npx 命令，请确认 Node.js 已安装且在 PATH 中")
    except KeyError as e:
        print(f"❌ 环境变量缺失: {e}，请检查 .env 文件")
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
        raise
    finally:
        await GlobalBrowser.shutdown()
        kill_chrome_processes()
        print("🔚 资源已清理")


if __name__ == "__main__":
    asyncio.run(main())