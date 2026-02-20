# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Learn Claude Code** - an educational project that teaches how modern AI agents work through 11 progressive sessions, from a simple loop to full autonomous teams. It contains Python reference implementations and an interactive Next.js web platform for visualization.

## Commands

### Python Agents

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env    # Configure ANTHROPIC_API_KEY

# Run any session (each is self-contained)
python agents/s01_agent_loop.py        # Basic agent loop
python agents/s02_tool_use.py          # + Read/Write/Edit tools
python agents/s11_autonomous_agents.py # Full autonomous team
python agents/s_full.py                # Combined reference
```

### Web Platform

```bash
cd web
npm install
npm run dev      # Development server (http://localhost:3000)
npm run build    # Production build
```

### CI/Type Checking

```bash
# Web type check
cd web && npx tsc --noEmit
```

## Architecture

### Core Pattern (The Agent Loop)

Every agent is built on this fundamental pattern:

```python
def agent_loop(messages):
    while True:
        response = client.messages.create(model=MODEL, messages=messages, tools=TOOLS)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return
        results = [execute_tool(block) for block in response.content if block.type == "tool_use"]
        messages.append({"role": "user", "content": results})
```

Each session (s01-s11) adds ONE mechanism on top of this loop.

### Session Progression

| Phase | Sessions | Key Mechanisms |
|-------|----------|----------------|
| 1. THE LOOP | s01-s02 | while loop + tools (Bash, Read, Write, Edit) |
| 2. PLANNING | s03-s06 | TodoWrite, Subagents (fresh context), Skills (SKILL.md), Compact |
| 3. PERSISTENCE | s07-s08 | Tasks CRUD + dependencies, Background threads |
| 4. TEAMS | s09-s11 | Teammates + mailboxes, Protocols, Autonomous agents |

### Directory Structure

- `agents/` - Python reference implementations (s01-s11 + s_full)
- `docs/` - Mental-model-first documentation with ASCII diagrams (EN/ZH/JA)
- `web/` - Next.js 16 interactive learning platform
- `skills/` - SKILL.md files for skill-loading mechanism

### Key Files

- `agents/s_full.py` - Combined reference with all mechanisms
- `web/src/components/simulator/` - Agent loop step-through visualization
- `web/src/components/visualizations/` - Per-session architecture diagrams
- `skills/agent-builder/SKILL.md` - Philosophy and patterns for building agents

## Supported Providers

The agents support Anthropic-compatible providers via environment variables:

```bash
ANTHROPIC_API_KEY=your-key
ANTHROPIC_BASE_URL=https://api.anthropic.com  # or other provider
MODEL_ID=claude-sonnet-4-6  # or glm-5, kimi-k2.5, deepseek-chat, MiniMax-M2.5
```

See `.env.example` for regional endpoints (GLM, Kimi, DeepSeek, MiniMax).
