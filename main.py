import ast
import json
import math
import operator
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI


# 加载当前目录下的 .env 文件
load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
NOTES_FILE = DATA_DIR / "notes.json"


# ============================================================
# 本地笔记存储
# ============================================================


def ensure_notes_file() -> None:
    """确保笔记目录和文件存在。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not NOTES_FILE.exists():
        NOTES_FILE.write_text("[]", encoding="utf-8")


def load_notes() -> list[dict[str, Any]]:
    """读取本地笔记。"""
    ensure_notes_file()

    try:
        data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_notes(notes: list[dict[str, Any]]) -> None:
    """保存本地笔记。"""
    ensure_notes_file()
    NOTES_FILE.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ============================================================
# 工具一：安全计算器
# ============================================================


_ALLOWED_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> int | float:
    """只执行受限的数学表达式，避免直接使用 eval。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise ValueError("不支持布尔值")

        if isinstance(node.value, (int, float)):
            return node.value

        raise ValueError("只支持整数和小数")

    if isinstance(node, ast.UnaryOp):
        function = _ALLOWED_UNARY_OPERATORS.get(type(node.op))
        if function is None:
            raise ValueError("不支持该一元运算符")
        return function(_safe_eval(node.operand))

    if isinstance(node, ast.BinOp):
        function = _ALLOWED_BINARY_OPERATORS.get(type(node.op))
        if function is None:
            raise ValueError("不支持该二元运算符")

        left = _safe_eval(node.left)
        right = _safe_eval(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > 20:
            raise ValueError("幂运算指数不能超过 20")

        result = function(left, right)

        if isinstance(result, int) and result.bit_length() > 256:
            raise ValueError("计算结果过大")

        if isinstance(result, float) and not math.isfinite(result):
            raise ValueError("计算结果不是有限数字")

        return result

    raise ValueError("表达式中包含不支持的内容")


@tool
def calculate(expression: str) -> str:
    """计算数学表达式，例如 12 * (3 + 4)、100 / 4、2 ** 10。"""
    expression = expression.strip()

    if not expression:
        return "计算表达式不能为空"

    if len(expression) > 200:
        return "计算表达式太长，最多支持 200 个字符"

    try:
        parsed_expression = ast.parse(expression, mode="eval")
        return str(_safe_eval(parsed_expression))
    except ZeroDivisionError:
        return "计算失败：不能除以零"
    except SyntaxError:
        return "计算失败：表达式语法不正确"
    except ValueError as error:
        return f"计算失败：{error}"
    except Exception as error:
        return f"计算失败：{error}"


# ============================================================
# 工具二：查询时间
# ============================================================


@tool
def get_current_time(timezone_name: str = "Asia/Shanghai") -> str:
    """获取指定时区的当前时间，例如 Asia/Shanghai、Asia/Tokyo 或 UTC。"""
    timezone_name = timezone_name.strip() or "Asia/Shanghai"

    try:
        target_timezone = ZoneInfo(timezone_name)
        current_time = datetime.now(target_timezone)
        return current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    except ZoneInfoNotFoundError:
        return f"不支持的时区：{timezone_name}"


# ============================================================
# 工具三：保存笔记
# ============================================================


@tool
def save_note(title: str, content: str) -> str:
    """保存一条本地笔记，只有用户明确要求保存或记录时才调用。"""
    title = title.strip()
    content = content.strip()

    if not title:
        return "保存失败：笔记标题不能为空"

    if not content:
        return "保存失败：笔记内容不能为空"

    notes = load_notes()
    new_note = {
        "id": len(notes) + 1,
        "title": title,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    notes.append(new_note)
    save_notes(notes)
    return f"笔记保存成功，编号为 {new_note['id']}，标题为《{title}》"


# ============================================================
# 工具四：搜索笔记
# ============================================================


@tool
def search_notes(keyword: str) -> str:
    """根据关键词搜索本地笔记的标题和内容。"""
    keyword = keyword.strip()

    if not keyword:
        return "搜索关键词不能为空"

    keyword_lower = keyword.casefold()
    matched_notes = [
        note
        for note in load_notes()
        if keyword_lower in note["title"].casefold()
        or keyword_lower in note["content"].casefold()
    ][:10]

    if not matched_notes:
        return f"没有找到包含“{keyword}”的笔记"

    lines = [f"找到 {len(matched_notes)} 条相关笔记："]
    for note in matched_notes:
        lines.append(
            f"\n编号：{note['id']}"
            f"\n标题：{note['title']}"
            f"\n内容：{note['content']}"
            f"\n创建时间：{note['created_at']}"
        )

    return "\n".join(lines)


# ============================================================
# 创建 Agent
# ============================================================


SYSTEM_PROMPT = """
你是一个中文智能助手。

你可以使用以下工具：

1. calculate：计算数学表达式。只要用户提出数学计算，就优先使用这个工具。
2. get_current_time：查询当前时间。没有指定时区时，默认使用 Asia/Shanghai。
3. save_note：保存本地笔记。只有用户明确要求保存、记录或记住时才调用。
4. search_notes：搜索已经保存的本地笔记。

使用工具后，必须根据工具返回的真实结果回答用户，不要编造工具调用结果。
普通聊天不需要调用工具。
回答使用简体中文，尽量清晰、简洁。
"""


def create_chat_agent():
    """使用网关提供的 OpenAI 兼容接口创建 LangChain Agent。"""
    # 优先使用通用变量，兼容之前使用的 CLAUDE_* 变量名。
    api_key = os.getenv("LLM_API_KEY") or os.getenv("CLAUDE_API_KEY")
    model_name = os.getenv("LLM_MODEL") or os.getenv(
        "CLAUDE_MODEL",
        "gpt-6.1-sol",
    )
    base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("CLAUDE_BASE_URL")
        or "https://your-llm-gateway.example.com"
    ).rstrip("/")

    if not api_key:
        raise RuntimeError(
            "没有找到 LLM_API_KEY，请在 .env 文件中填写 API Key"
        )

    # OpenAI 兼容接口通常使用 /v1 作为 API 根路径。
    # 如果环境变量已经包含 /v1，则不重复添加。
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        # 当前模型不支持 temperature 参数，因此不传入。
        # 带工具调用时使用 Responses API。
        use_responses_api=True,
        output_version="responses/v1",
    )

    return create_agent(
        model=model,
        tools=[calculate, get_current_time, save_note, search_notes],
        system_prompt=SYSTEM_PROMPT,
    )


def content_to_text(content: Any) -> str:
    """将模型返回的消息内容转换为可显示文本。"""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)

    return str(content)


def run_chat() -> None:
    """启动命令行聊天程序。"""
    print("正在创建 Claude LangChain Agent……")

    try:
        agent = create_chat_agent()
    except Exception as error:
        print(f"Agent 创建失败：{error}")
        return

    messages: list[Any] = []

    print("\nAgent 已启动。输入 exit、quit 或 q 退出。")
    print("可以尝试：")
    print("  计算 (123.45 + 67.8) * 2")
    print("  现在上海几点？")
    print("  记住：我的项目名称是智能客服系统")
    print("  搜索关于项目的笔记\n")

    while True:
        try:
            user_input = input("你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n程序已退出。")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "q"}:
            print("程序已退出。")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            result = agent.invoke({"messages": messages})
            messages = result["messages"]
            print(f"\n助手：{content_to_text(messages[-1].content)}\n")
        except Exception as error:
            if messages:
                messages.pop()
            print(f"\n调用 Agent 失败：{error}\n")


if __name__ == "__main__":
    run_chat()
