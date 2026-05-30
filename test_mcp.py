import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 显式修复 Windows 上的 Asyncio 事件循环冲突（勘误表核心痛点）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    print("🔄 正在尝试自动唤醒并连接 Filesystem MCP 服务器...")

    # 配置服务器启动参数：告诉 Python 运行时如何帮你拉起 npx 引擎
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@modelcontextprotocol/server-filesystem",
            # 填入你第一步创建的 workspace 绝对路径（使用 r 规避反斜杠转义）
            r"D:\Multiple Ai Cooperating Operation System\workspace"
        ]
    )

    # 建立 Stdio 管道连接
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # 初始化 MCP 会话 (Initialize Session)
                await session.initialize()
                print("✅ MCP 服务器初始化成功！")

                # 获取该服务向大模型开放的所有工具清单
                tools = await session.list_tools()

                print("\n🤖 成功为系统注入以下本地文件控制工具：")
                for tool in tools.tools:
                    print(f"- 【工具名】: {tool.name}")
                    print(f"  【功能描述】: {tool.description}\n")

    except Exception as e:
        print(f"❌ 连接失败，错误信息: {e}")


if __name__ == "__main__":
    asyncio.run(main())