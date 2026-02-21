#!/usr/bin/env python3
"""
s08_background_tasks.py - Background Tasks

Run commands in background threads. A notification queue is drained
before each LLM call to deliver results.

    Main thread                Background thread
    +-----------------+        +-----------------+
    | agent loop      |        | task executes   |
    | ...             |        | ...             |
    | [LLM call] <---+------- | enqueue(result) |
    |  ^drain queue   |        +-----------------+
    +-----------------+

    Timeline:
    Agent ----[spawn A]----[spawn B]----[other work]----
                 |              |
                 v              v
              [A runs]      [B runs]        (parallel)
                 |              |
                 +-- notification queue --> [results injected]

Key insight: "Fire and forget -- the agent doesn't block while the command runs."
"""

import os
import subprocess
import threading
import uuid
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from logger import AgentLogger

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {WORKDIR}. Use background_run for long-running commands."

# 初始化日志器
logger = AgentLogger(verbose=True, show_raw=True)


# -- BackgroundManager: threaded execution + notification queue --
class BackgroundManager:
    def __init__(self):
        self.tasks = {}  # task_id -> {status, result, command}
        self._notification_queue = []  # completed task results
        self._lock = threading.Lock()

    def run(self, command: str) -> str:
        """Start a background thread, return task_id immediately."""
        task_id = str(uuid.uuid4())[:8]
        self.tasks[task_id] = {"status": "running", "result": None, "command": command}
        thread = threading.Thread(
            target=self._execute, args=(task_id, command), daemon=True
        )
        thread.start()

        # 日志：后台任务启动
        self._print_task_started(task_id, command)

        return f"Background task {task_id} started: {command[:80]}"

    def _execute(self, task_id: str, command: str):
        """Thread target: run subprocess, capture output, push to queue."""
        try:
            r = subprocess.run(
                command, shell=True, cwd=WORKDIR,
                capture_output=True, text=True, timeout=300
            )
            output = (r.stdout + r.stderr).strip()[:50000]
            status = "completed"
        except subprocess.TimeoutExpired:
            output = "Error: Timeout (300s)"
            status = "timeout"
        except Exception as e:
            output = f"Error: {e}"
            status = "error"
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = output or "(no output)"
        with self._lock:
            self._notification_queue.append({
                "task_id": task_id,
                "status": status,
                "command": command[:80],
                "result": (output or "(no output)")[:500],
            })

        # 日志：后台任务完成（在线程中打印，使用特殊标记）
        self._print_task_completed(task_id, status, output)

    def check(self, task_id: str = None) -> str:
        """Check status of one task or list all."""
        if task_id:
            t = self.tasks.get(task_id)
            if not t:
                return f"Error: Unknown task {task_id}"
            self._print_task_detail(task_id, t)
            return f"[{t['status']}] {t['command'][:60]}\n{t.get('result') or '(running)'}"

        # 列出所有任务
        self._print_task_list()
        lines = []
        for tid, t in self.tasks.items():
            lines.append(f"{tid}: [{t['status']}] {t['command'][:60]}")
        return "\n".join(lines) if lines else "No background tasks."

    def drain_notifications(self) -> list:
        """Return and clear all pending completion notifications."""
        with self._lock:
            notifs = list(self._notification_queue)
            self._notification_queue.clear()
        return notifs

    # -- 日志输出方法 --
    def _print_task_started(self, task_id: str, command: str):
        """打印后台任务启动日志"""
        print(logger._color(f"\n{'┌' + '─' * 78 + '┐'}", "magenta"))
        print(logger._color(f"│  🚀 BACKGROUND TASK STARTED" + " " * 50 + "│", "magenta"))
        print(logger._color(f"│  Task ID: {task_id}" + " " * (69 - len(task_id)) + "│", "magenta"))
        cmd_preview = command[:65] + "..." if len(command) > 65 else command
        print(logger._color(f"│  Command: {cmd_preview}" + " " * (69 - len(cmd_preview)) + "│", "dim"))
        print(logger._color(f"│  Status: 🔄 Running..." + " " * 55 + "│", "yellow"))
        print(logger._color(f"└" + "─" * 78 + "┘", "magenta"))

    def _print_task_completed(self, task_id: str, status: str, output: str):
        """打印后台任务完成日志（从线程中调用）"""
        status_icons = {"completed": "✅", "timeout": "⏱️", "error": "❌"}
        icon = status_icons.get(status, "❓")

        print(logger._color(f"\n{'┌' + '─' * 78 + '┐'}", "green" if status == "completed" else "red"))
        print(logger._color(f"│  {icon} BACKGROUND TASK COMPLETED" + " " * (48 if status == "completed" else 49) + "│",
                           "green" if status == "completed" else "red"))
        print(logger._color(f"│  Task ID: {task_id}" + " " * (69 - len(task_id)) + "│",
                           "green" if status == "completed" else "red"))
        print(logger._color(f"│  Status: {status}" + " " * (70 - len(status)) + "│", "dim"))
        output_preview = (output[:100] + "...") if len(output) > 100 else output
        output_line = output_preview.replace("\n", " ")[:68]
        print(logger._color(f"│  Output: {output_line}" + " " * (69 - len(output_line)) + "│", "dim"))
        print(logger._color(f"└" + "─" * 78 + "┘", "green" if status == "completed" else "red"))

    def _print_task_detail(self, task_id: str, task: dict):
        """打印单个任务详情"""
        status_icons = {"running": "🔄", "completed": "✅", "timeout": "⏱️", "error": "❌"}
        icon = status_icons.get(task["status"], "❓")

        print(logger._color(f"\n  📋 BACKGROUND TASK #{task_id}:", "cyan"))
        print(logger._color(f"      Status: {icon} {task['status']}", "dim"))
        print(logger._color(f"      Command: {task['command'][:70]}", "dim"))
        if task.get("result"):
            result_preview = task["result"][:200]
            print(logger._color(f"      Result: {result_preview[:70]}...", "dim"))

    def _print_task_list(self):
        """打印所有后台任务列表"""
        if not self.tasks:
            print(logger._color(f"\n  📋 No background tasks.", "dim"))
            return

        running = sum(1 for t in self.tasks.values() if t["status"] == "running")
        completed = sum(1 for t in self.tasks.values() if t["status"] == "completed")
        error = sum(1 for t in self.tasks.values() if t["status"] in ("error", "timeout"))

        print(logger._color(f"\n{'╔' + '═' * 78 + '╗'}", "cyan"))
        print(logger._color(f"║  📋 BACKGROUND TASKS" + " " * 57 + "║", "cyan"))
        print(logger._color(f"║  Total: {len(self.tasks)} | 🔄 Running: {running} | ✅ Completed: {completed} | ❌ Error: {error}" + " " * (78 - 75 - len(str([len(self.tasks), running, completed, error]))) + "║", "dim"))
        print(logger._color(f"╠" + "═" * 78 + "╣", "cyan"))

        for tid, t in self.tasks.items():
            status_icons = {"running": "🔄", "completed": "✅", "timeout": "⏱️", "error": "❌"}
            icon = status_icons.get(t["status"], "❓")
            line = f"  {icon} {tid}: {t['command'][:55]}"
            print(logger._color(f"║{line}" + " " * (78 - len(line) - 1) + "║", "dim"))

        print(logger._color(f"╚" + "═" * 78 + "╝", "cyan"))

    def print_notifications(self, notifs: list):
        """打印通知队列内容"""
        if not notifs:
            return

        print(logger._color(f"\n{'╔' + '═' * 78 + '╗'}", "yellow"))
        print(logger._color(f"║  📬 BACKGROUND NOTIFICATIONS ({len(notifs)} pending)" + " " * (31 - len(str(len(notifs)))) + "║", "yellow"))
        print(logger._color(f"╠" + "═" * 78 + "╣", "yellow"))

        for n in notifs:
            status_icons = {"completed": "✅", "timeout": "⏱️", "error": "❌"}
            icon = status_icons.get(n["status"], "❓")
            print(logger._color(f"║  {icon} [{n['task_id']}] {n['status']}", "yellow"))
            print(logger._color(f"║      Command: {n['command'][:65]}", "dim"))
            result_line = n["result"][:65].replace("\n", " ")
            print(logger._color(f"║      Result: {result_line}", "dim"))

        print(logger._color(f"╚" + "═" * 78 + "╝", "yellow"))

    def print_summary(self):
        """打印后台任务系统状态摘要"""
        running = sum(1 for t in self.tasks.values() if t["status"] == "running")
        print(logger._color(f"\n  📊 Background Task System:", "cyan"))
        print(logger._color(f"      Total tasks: {len(self.tasks)}", "dim"))
        print(logger._color(f"      Currently running: {running}", "dim"))
        print(logger._color(f"      Pending notifications: {len(self._notification_queue)}", "dim"))


BG = BackgroundManager()


# -- Tool implementations --
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        c = fp.read_text()
        if old_text not in c:
            return f"Error: Text not found in {path}"
        fp.write_text(c.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


TOOL_HANDLERS = {
    "bash":             lambda **kw: run_bash(kw["command"]),
    "read_file":        lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file":       lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":        lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "background_run":   lambda **kw: BG.run(kw["command"]),
    "check_background": lambda **kw: BG.check(kw.get("task_id")),
}

TOOLS = [
    {"name": "bash", "description": "Run a shell command (blocking).",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "background_run", "description": "Run command in background thread. Returns task_id immediately.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "check_background", "description": "Check background task status. Omit task_id to list all.",
     "input_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}}},
]


def agent_loop(messages: list):
    """Agent 循环"""
    iteration = 0

    while True:
        iteration += 1
        logger.loop_iteration(iteration)

        # Drain background notifications and inject as system message before LLM call
        notifs = BG.drain_notifications()
        if notifs and messages:
            BG.print_notifications(notifs)
            notif_text = "\n".join(
                f"[bg:{n['task_id']}] {n['status']}: {n['result']}" for n in notifs
            )
            messages.append({"role": "user", "content": f"<background-results>\n{notif_text}\n</background-results>"})
            messages.append({"role": "assistant", "content": "Noted background results."})
            logger.messages_snapshot(messages, "AFTER INJECT NOTIFICATIONS")

        logger.messages_snapshot(messages, "BEFORE LLM CALL")

        # 显示原始请求
        logger.request_raw(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000
        )

        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )

        # 显示原始响应
        logger.response_raw(response)

        # 显示响应摘要
        usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
        logger.llm_response_summary(response.stop_reason, usage, len(response.content))
        logger.response_content_blocks(response.content)

        messages.append({"role": "assistant", "content": response.content})
        logger.messages_snapshot(messages, "AFTER APPEND ASSISTANT")

        if response.stop_reason != "tool_use":
            logger.loop_end(f"stop_reason = '{response.stop_reason}'")
            return

        # 执行工具调用
        logger.section("Executing Tool Calls", "🔧")
        results = []
        for block in response.content:
            if block.type == "tool_use":
                input_data = dict(block.input)
                logger.tool_call(block.name, input_data, block.id)

                handler = TOOL_HANDLERS.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as e:
                    output = f"Error: {e}"

                is_error = str(output).startswith("Error:")
                logger.tool_result(block.id, str(output), is_error=is_error)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(output)})

        messages.append({"role": "user", "content": results})
        logger.messages_snapshot(messages, "AFTER APPEND TOOL RESULTS")
        logger.separator(f"END OF ITERATION {iteration}")


if __name__ == "__main__":
    logger.header("s08 Background Tasks - Interactive Mode", "s08")

    # 显示后台任务系统状态
    BG.print_summary()

    history = []
    while True:
        try:
            query = input("\033[36ms08 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        logger.user_input(query)
        history.append({"role": "user", "content": query})
        agent_loop(history)

        logger.separator("FINAL RESPONSE")
        for block in history[-1]["content"] if isinstance(history[-1]["content"], list) else []:
            if hasattr(block, "text"):
                print(block.text)
        print()
