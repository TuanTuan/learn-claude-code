#!/usr/bin/env python3
"""
logger.py - 模块化的 Agent 日志系统

提供结构化的日志输出，用于追踪 Agent Loop 的每一步。
支持多种日志级别和格式化输出。

使用方法:
    from logger import AgentLogger

    logger = AgentLogger(verbose=True, show_raw=True)
    logger.request_raw(request_data)
    logger.response_raw(response_data)
"""

import json
from datetime import datetime
from typing import Any, Optional


class AgentLogger:
    """Agent 日志输出器，支持结构化日志和原始数据显示"""

    # ANSI 颜色代码
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "underline": "\033[4m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "bg_black": "\033[40m",
        "bg_red": "\033[41m",
        "bg_green": "\033[42m",
        "bg_yellow": "\033[43m",
        "bg_blue": "\033[44m",
        "bg_magenta": "\033[45m",
        "bg_cyan": "\033[46m",
    }

    def __init__(self, verbose: bool = True, show_raw: bool = True):
        """
        初始化日志器

        Args:
            verbose: 是否显示详细日志
            show_raw: 是否显示原始 API 数据
        """
        self.verbose = verbose
        self.show_raw = show_raw
        self._iteration = 0

    def _color(self, text: str, color: str) -> str:
        """添加颜色"""
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def _timestamp(self) -> str:
        """获取时间戳"""
        return self._color(datetime.now().strftime("%H:%M:%S.%f")[:-3], "dim")

    # =========================================================================
    # 基础输出方法
    # =========================================================================

    def separator(self, title: str = "", char: str = "─", width: int = 80):
        """打印分隔线"""
        if not self.verbose:
            return
        if title:
            line = char * 10 + f" {title} " + char * (width - 12 - len(title))
        else:
            line = char * width
        print(self._color(f"\n{line}", "dim"))

    def header(self, text: str, session_name: str = ""):
        """打印标题头"""
        print(self._color(f"\n{'═' * 80}", "cyan"))
        if session_name:
            print(self._color(f"  [{session_name}]", "dim"))
        print(self._color(f"  {text}", "bold"))
        print(self._color(f"{'═' * 80}", "cyan"))

    def section(self, text: str, icon: str = "▶"):
        """打印章节标题"""
        if not self.verbose:
            return
        print(self._color(f"\n{icon} {text}", "cyan"))

    def key_value(self, key: str, value: Any, indent: int = 2, color: str = "yellow"):
        """打印键值对"""
        spaces = " " * indent
        key_str = self._color(f"{key}:", color)
        print(f"{spaces}{key_str} {value}")

    def json_block(self, title: str, data: Any, indent: int = 2, color: str = "magenta"):
        """打印 JSON 格式的内容"""
        if not self.verbose:
            return
        spaces = " " * indent
        title_str = self._color(f"{title}:", color)
        print(f"{spaces}{title_str}")
        try:
            formatted = json.dumps(data, ensure_ascii=False, indent=indent + 2)
            for line in formatted.split("\n"):
                print(self._color(f"{spaces}  {line}", "dim"))
        except Exception:
            print(self._color(f"{spaces}  {data}", "dim"))

    # =========================================================================
    # 原始 API 数据显示 (核心功能)
    # =========================================================================

    def request_raw(self, model: str, system: str, messages: list, tools: list, max_tokens: int = 8000):
        """
        结构化显示原始 API 请求数据

        展示发送给 LLM API 的完整请求结构，帮助理解底层数据格式。
        """
        if not self.show_raw:
            return

        print(self._color("\n" + "┌" + "─" * 78 + "┐", "magenta"))
        print(self._color("│  📤 RAW API REQUEST" + " " * 57 + "│", "magenta"))
        print(self._color("└" + "─" * 78 + "┘", "magenta"))

        # 构建请求数据结构
        request_data = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system[:100] + "..." if len(system) > 100 else system,
            "tools": [{"name": t["name"], "description": t["description"][:50] + "..."} for t in tools],
            "messages": []
        }

        # 简化消息显示
        for i, msg in enumerate(messages):
            msg_entry = {"role": msg["role"]}
            content = msg.get("content", "")

            if isinstance(content, str):
                msg_entry["content"] = f"<text: {len(content)} chars>"
            elif isinstance(content, list):
                # 处理 content blocks
                blocks_summary = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type", "unknown")
                    else:
                        block_type = getattr(block, "type", "unknown")

                    if block_type == "tool_result":
                        tool_id = block.get("tool_use_id", "") if isinstance(block, dict) else getattr(block, "tool_use_id", "")
                        blocks_summary.append(f"tool_result(id={tool_id[:16]}...)")
                    elif block_type == "tool_use":
                        name = block.get("name", "") if isinstance(block, dict) else getattr(block, "name", "")
                        blocks_summary.append(f"tool_use(name={name})")
                    else:
                        blocks_summary.append(block_type)
                msg_entry["content"] = blocks_summary
            else:
                # Pydantic 对象列表
                blocks_summary = []
                for block in content:
                    block_type = getattr(block, "type", "unknown")
                    if block_type == "tool_result":
                        tool_id = getattr(block, "tool_use_id", "")
                        blocks_summary.append(f"tool_result(id={tool_id[:16]}...)")
                    elif block_type == "tool_use":
                        name = getattr(block, "name", "")
                        blocks_summary.append(f"tool_use(name={name})")
                    else:
                        blocks_summary.append(block_type)
                msg_entry["content"] = blocks_summary

            request_data["messages"].append(msg_entry)

        self._print_structured_json(request_data, "Request Structure")

        # 显示完整请求 JSON (可选)
        print(self._color("\n  📄 Full Request JSON (copy-paste ready):", "cyan"))
        full_request = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "tools": tools,
            "messages": self._serialize_messages(messages)
        }
        self._print_code_block(full_request)

    def response_raw(self, response):
        """
        结构化显示原始 API 响应数据

        展示从 LLM API 返回的完整响应结构，帮助理解底层数据格式。
        """
        if not self.show_raw:
            return

        print(self._color("\n" + "┌" + "─" * 78 + "┐", "blue"))
        print(self._color("│  📥 RAW API RESPONSE" + " " * 56 + "│", "blue"))
        print(self._color("└" + "─" * 78 + "┘", "blue"))

        # 构建响应数据结构
        response_data = {
            "id": response.id,
            "model": response.model,
            "role": response.role,
            "stop_reason": response.stop_reason,
            "stop_sequence": response.stop_sequence,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "content": []
        }

        # 解析 content blocks
        for block in response.content:
            block_type = getattr(block, "type", "unknown")
            block_entry = {"type": block_type}

            if block_type == "text":
                text = getattr(block, "text", "")
                block_entry["text"] = f"<{len(text)} chars>"
            elif block_type == "tool_use":
                block_entry["id"] = getattr(block, "id", "")
                block_entry["name"] = getattr(block, "name", "")
                block_entry["input"] = getattr(block, "input", {})

            response_data["content"].append(block_entry)

        self._print_structured_json(response_data, "Response Structure")

        # 显示完整响应 JSON
        print(self._color("\n  📄 Full Response JSON (copy-paste ready):", "cyan"))
        full_response = {
            "id": response.id,
            "model": response.model,
            "role": response.role,
            "stop_reason": response.stop_reason,
            "stop_sequence": response.stop_sequence,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "content": self._serialize_content(response.content)
        }
        self._print_code_block(full_response)

    def _serialize_messages(self, messages: list) -> list:
        """序列化消息列表为可 JSON 化的格式"""
        result = []
        for msg in messages:
            msg_dict = {"role": msg["role"]}
            content = msg.get("content", "")

            if isinstance(content, str):
                msg_dict["content"] = content
            elif isinstance(content, list):
                msg_dict["content"] = self._serialize_content(content)
            else:
                msg_dict["content"] = str(content)

            result.append(msg_dict)
        return result

    def _serialize_content(self, content) -> list:
        """序列化 content blocks 为可 JSON 化的格式"""
        result = []
        for block in content:
            if isinstance(block, dict):
                result.append(block)
            else:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    result.append({
                        "type": "text",
                        "text": getattr(block, "text", "")
                    })
                elif block_type == "tool_use":
                    result.append({
                        "type": "tool_use",
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "input": dict(getattr(block, "input", {}))
                    })
                else:
                    result.append({"type": str(block_type)})
        return result

    def _print_structured_json(self, data: dict, title: str):
        """打印结构化 JSON 数据"""
        print(self._color(f"\n  📊 {title}:", "cyan"))
        try:
            formatted = json.dumps(data, ensure_ascii=False, indent=4)
            for line in formatted.split("\n"):
                # 语法高亮：键名黄色，字符串绿色，数字蓝色
                if '":' in line:
                    print(self._color(f"    {line}", "dim"))
                else:
                    print(self._color(f"    {line}", "dim"))
        except Exception as e:
            print(self._color(f"    Error formatting: {e}", "red"))

    def _print_code_block(self, data: dict):
        """打印代码块格式的 JSON"""
        try:
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            print(self._color("  " + "┌" + "─" * 76 + "┐", "dim"))
            for line in formatted.split("\n"):
                # 截断过长的行
                if len(line) > 74:
                    line = line[:71] + "..."
                print(self._color(f"  │ {line:<74} │", "dim"))
            print(self._color("  " + "└" + "─" * 76 + "┘", "dim"))
        except Exception as e:
            print(self._color(f"    Error: {e}", "red"))

    # =========================================================================
    # 循环和消息追踪
    # =========================================================================

    def loop_iteration(self, iteration: int):
        """打印循环迭代"""
        if not self.verbose:
            return
        self._iteration = iteration
        print(self._color(f"\n{'┌' + '─' * 78 + '┐'}", "cyan"))
        print(self._color(f"│  🔄 LOOP ITERATION #{iteration:<62}│", "cyan"))
        print(self._color(f"{'└' + '─' * 78 + '┘'}", "cyan"))

    def messages_snapshot(self, messages: list, title: str = "MESSAGES SNAPSHOT"):
        """打印当前消息列表的快照"""
        if not self.verbose:
            return
        print(self._color(f"\n  📋 {title}", "blue"))
        print(self._color(f"  Total messages: {len(messages)}", "dim"))
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            role_color = "green" if role == "user" else "yellow" if role == "assistant" else "white"
            content = msg.get("content", "")

            # 简化 content 显示
            if isinstance(content, str):
                preview = content[:60] + ("..." if len(content) > 60 else "")
                print(f"    [{i}] {self._color(role, role_color)}: {self._color(preview, 'dim')}")
            elif isinstance(content, list):
                # 工具结果列表
                block_types = []
                for b in content:
                    if isinstance(b, dict):
                        block_types.append(b.get('type', 'unknown'))
                    else:
                        block_types.append(getattr(b, 'type', 'unknown'))
                print(f"    [{i}] {self._color(role, role_color)}: {self._color(str(block_types), 'dim')}")

    # =========================================================================
    # 工具调用显示
    # =========================================================================

    def tool_call(self, name: str, input_data: dict, tool_id: str = ""):
        """打印工具调用"""
        print(self._color(f"\n  ⚡ TOOL CALL", "green"))
        if tool_id:
            self.key_value("id", self._color(tool_id[:24] + "...", "dim"), indent=4, color="green")
        self.key_value("name", self._color(name, "green"), indent=4, color="green")
        self.key_value("input", "", indent=4, color="green")
        for k, v in input_data.items():
            v_str = str(v)
            if len(v_str) > 60:
                v_str = v_str[:60] + "..."
            print(self._color(f"      {k}: {v_str}", "dim"))

    def tool_result(self, tool_id: str, content: str, is_error: bool = False):
        """打印工具结果"""
        color = "red" if is_error else "blue"
        icon = "❌" if is_error else "✓"
        print(self._color(f"\n  {icon} TOOL RESULT", color))
        self.key_value("tool_use_id", tool_id[:24] + "...", indent=4, color=color)
        content_preview = content[:300] + ("..." if len(content) > 300 else "")
        self.key_value("content", self._color(f'"{content_preview}"', "dim"), indent=4, color=color)

    # =========================================================================
    # LLM 交互摘要
    # =========================================================================

    def llm_request_summary(self, model: str, messages_count: int, tools_count: int):
        """打印 LLM 请求摘要"""
        if not self.verbose:
            return
        print(self._color(f"\n  📤 LLM REQUEST SUMMARY", "magenta"))
        self.key_value("model", model, indent=4, color="magenta")
        self.key_value("messages_count", str(messages_count), indent=4, color="magenta")
        self.key_value("tools_count", str(tools_count), indent=4, color="magenta")
        self.key_value("timestamp", self._timestamp(), indent=4, color="magenta")

    def llm_response_summary(self, stop_reason: str, usage: dict, content_blocks: int):
        """打印 LLM 响应摘要"""
        if not self.verbose:
            return
        print(self._color(f"\n  📥 LLM RESPONSE SUMMARY", "magenta"))
        stop_color = "yellow" if stop_reason == "tool_use" else "green"
        self.key_value("stop_reason", self._color(stop_reason, stop_color), indent=4, color="magenta")
        self.key_value("content_blocks", str(content_blocks), indent=4, color="magenta")
        self.key_value("usage", f"input={usage.get('input_tokens', 0)}, output={usage.get('output_tokens', 0)}", indent=4, color="magenta")

    def response_content_blocks(self, content_blocks: list):
        """打印响应内容块详情"""
        if not self.verbose:
            return
        self.section("Response Content Blocks", "📦")
        for i, block in enumerate(content_blocks):
            block_type = getattr(block, "type", "unknown") if not isinstance(block, dict) else block.get("type", "unknown")
            if block_type == "text":
                text = getattr(block, "text", "") if not isinstance(block, dict) else block.get("text", "")
                text_preview = text[:100] + ("..." if len(text) > 100 else "")
                self.key_value(f"Block [{i}]", f'type={block_type}, text="{text_preview}"', indent=4)
            elif block_type == "tool_use":
                name = getattr(block, "name", "") if not isinstance(block, dict) else block.get("name", "")
                self.key_value(f"Block [{i}]", f"type={block_type}, name={name}", indent=4)

    def loop_end(self, reason: str):
        """打印循环结束"""
        self.section(f"🏁 LOOP END: {reason}", "🛑")

    def user_input(self, query: str):
        """打印用户输入"""
        self.separator("USER INPUT")
        print(f"  {query}")


# =============================================================================
# 便捷函数 - 用于向后兼容
# =============================================================================

# 默认全局实例
_default_logger = AgentLogger()


def get_logger(verbose: bool = True, show_raw: bool = True) -> AgentLogger:
    """获取日志器实例"""
    return AgentLogger(verbose=verbose, show_raw=show_raw)
