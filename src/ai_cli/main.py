#!/usr/bin/env python3
"""
ai-cli: Zero-dependency, ultra-fast streaming AI CLI for Unix pipelines & agentic task solving.
Compatible with any OpenAI-compatible endpoint (OpenAI, Groq, Ollama, vLLM, OpenRouter, Together, AGM).
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

__version__ = "0.2.0"
CONFIG_DIR = Path.home() / ".config" / "ai"
CONFIG_FILE = CONFIG_DIR / "config.json"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "limit": {"type": "integer", "description": "Max number of lines to read"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite file contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information, documentation, or news.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
]


def load_config() -> dict:
    """Load configuration from ~/.config/ai/config.json with fallback to ~/.omp/agent/models.yml if present."""
    config = {}

    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    # Fallback to OMP models.yml if available
    if not config.get("base_url") or not config.get("api_key"):
        omp_models = Path.home() / ".omp" / "agent" / "models.yml"
        if omp_models.is_file():
            try:
                text = omp_models.read_text(encoding="utf-8")
                agm_match = re.search(r"agm:\s*\n((?:\s+.*\n)+)", text)
                section = agm_match.group(1) if agm_match else text
                b = re.search(r'(?:baseUrl|base_url):\s*["\']?([^"\'\s\n]+)', section)
                k = re.search(r'(?:apiKey|api_key):\s*["\']?([^"\'\s\n]+)', section)
                if b and not config.get("base_url"):
                    config["base_url"] = b.group(1)
                if k and not config.get("api_key"):
                    config["api_key"] = k.group(1)
                if not config.get("model"):
                    config["model"] = "gemini-3.7-flash-high"
            except Exception:
                pass

    return config


def execute_bash(command: str, max_chars: int = 12000) -> str:
    """Execute command in bash and return combined stdout/stderr."""
    try:
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            executable="/bin/bash",
        )
        out = res.stdout + res.stderr
        if not out.strip():
            out = f"[Command exited with status {res.returncode} and produced no output]"
        if len(out) > max_chars:
            out = out[:max_chars] + f"\n... [Output truncated to {max_chars} characters]"
        return out
    except subprocess.TimeoutExpired:
        return "[Error: Command timed out after 60 seconds]"
    except Exception as e:
        return f"[Execution Error: {e}]"


def execute_read_file(path_str: str, limit: int = None) -> str:
    """Read file content safely."""
    path = Path(path_str).expanduser()
    if not path.is_file():
        return f"[Error: File not found at '{path_str}']"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            if limit and limit > 0:
                lines = [f.readline() for _ in range(limit)]
                return "".join(lines)
            return f.read()
    except Exception as e:
        return f"[Error reading file: {e}]"


def execute_write_file(path_str: str, content: str) -> str:
    """Write file content safely."""
    path = Path(path_str).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[Successfully wrote {len(content.encode('utf-8'))} bytes to '{path_str}']"
    except Exception as e:
        return f"[Error writing file: {e}]"


def execute_web_search(query: str, max_results: int = 5) -> str:
    """Search DuckDuckGo HTML without external dependencies or API keys."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://duckduckgo.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            page = resp.read().decode("utf-8", errors="ignore")

        results = []
        for m in re.finditer(
            r'<a class="result__snippet[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            page,
            re.DOTALL,
        ):
            url_match = re.search(r"uddg=([^&]+)", m.group(1))
            link = urllib.parse.unquote(url_match.group(1)) if url_match else m.group(1)
            snippet = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)).strip())
            results.append(f"- URL: {link}\n  Snippet: {snippet}")
            if len(results) >= max_results:
                break

        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"[Web Search Error: {e}]"


def run_agent_loop(
    base_url: str,
    api_key: str,
    model: str,
    user_content: str,
    system_prompt: str = None,
    temperature: float = None,
    max_turns: int = 15,
    auto_approve: bool = False,
) -> None:
    """Run an agentic loop with bash, read_file, write_file, and web_search tools."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    for turn in range(max_turns):
        payload = {
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
        }
        if temperature is not None:
            payload["temperature"] = temperature

        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"\n\033[31mAPI Error ({e.code}):\033[0m {e.read().decode('utf-8')}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n\033[31mError:\033[0m {e}", file=sys.stderr)
            sys.exit(1)

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            # Final output text from the model
            content = message.get("content", "")
            if content:
                print(content)
            break

        # Execute each requested tool call
        for tool in tool_calls:
            func = tool.get("function", {})
            fname = func.get("name")
            tool_id = tool.get("id")
            raw_args = func.get("arguments", "{}")

            try:
                args = json.loads(raw_args)
            except Exception:
                args = {}

            if fname == "bash":
                cmd = args.get("command", "")
                print(f"\033[1;33m⚡ Action (bash):\033[0m \033[36m{cmd}\033[0m")
                if not auto_approve:
                    try:
                        ans = input("  Execute? [Y/n/a(lways)] ").strip().lower()
                    except (KeyboardInterrupt, EOFError):
                        print("\nAborted.")
                        sys.exit(130)
                    if ans == "a":
                        auto_approve = True
                    elif ans == "n":
                        messages.append({"role": "tool", "tool_call_id": tool_id, "content": "[Command rejected by user]"})
                        continue
                output = execute_bash(cmd)
                lines = output.strip().split("\n")
                preview = "\n".join(lines[:6]) + (f"\n... ({len(lines)-6} more lines)" if len(lines) > 6 else "")
                print(f"\033[90m{preview}\033[0m")
                messages.append({"role": "tool", "tool_call_id": tool_id, "content": output})

            elif fname == "read_file":
                p = args.get("path", "")
                lim = args.get("limit")
                print(f"\033[1;34m📖 Read File:\033[0m \033[36m{p}\033[0m")
                output = execute_read_file(p, lim)
                messages.append({"role": "tool", "tool_call_id": tool_id, "content": output})

            elif fname == "write_file":
                p = args.get("path", "")
                c = args.get("content", "")
                print(f"\033[1;32m📝 Write File:\033[0m \033[36m{p}\033[0m ({len(c.encode('utf-8'))} bytes)")
                if not auto_approve:
                    try:
                        ans = input(f"  Write to '{p}'? [Y/n/a(lways)] ").strip().lower()
                    except (KeyboardInterrupt, EOFError):
                        print("\nAborted.")
                        sys.exit(130)
                    if ans == "a":
                        auto_approve = True
                    elif ans == "n":
                        messages.append({"role": "tool", "tool_call_id": tool_id, "content": "[File write rejected by user]"})
                        continue
                output = execute_write_file(p, c)
                print(f"\033[90m{output}\033[0m")
                messages.append({"role": "tool", "tool_call_id": tool_id, "content": output})

            elif fname in ("search_web", "web_search", "search", "internet_search"):
                q = args.get("query") or args.get("q") or args.get("search_terms") or ""
                print(f"\033[1;35m🌐 Search Web:\033[0m \033[36m{q}\033[0m")
                output = execute_web_search(q)
                messages.append({"role": "tool", "tool_call_id": tool_id, "content": output})
            else:
                messages.append({"role": "tool", "tool_call_id": tool_id, "content": f"[Unknown tool: {fname}]"})


def run_stream_completion(
    base_url: str,
    api_key: str,
    model: str,
    user_content: str,
    system_prompt: str = None,
    temperature: float = None,
) -> None:
    """Stream completions with sub-5ms latency and zero dependencies."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if temperature is not None:
        payload["temperature"] = temperature

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        continue
            print()
    except KeyboardInterrupt:
        sys.exit(130)
    except urllib.error.HTTPError as e:
        print(f"\n\033[31mAPI Error ({e.code}):\033[0m {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n\033[31mError:\033[0m {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    config = load_config()

    parser = argparse.ArgumentParser(
        prog="ai",
        description="Lightning-fast streaming AI CLI with zero external dependencies and agentic tool mode.",
        epilog=(
            "Examples:\n"
            "  ai what is the biggest thing on the moon\n"
            "  git diff | ai summarize changes in 3 bullets\n"
            "  ai -a 'inspect package.json and run the test script'\n"
            "  ai -a 'search latest zig 0.14 release notes and summarize key changes'\n"
            "  ai -s 'Reply in haiku' explain rust\n"
            "  ai -m claude-3-5-sonnet 'explain quantum entanglement'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", nargs="*", help="User prompt or instruction")
    parser.add_argument(
        "-a",
        "--agent",
        action="store_true",
        help="Enable autonomous agent mode with tools (bash, read_file, write_file, web_search)",
    )
    parser.add_argument(
        "-c",
        "--confirm",
        action="store_true",
        default=None,
        help="Require manual confirmation for each tool action (default: auto-executes unless set in config)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        default=None,
        help="Bypass confirmation and auto-approve all tool actions",
    )
    parser.add_argument(
        "-m",
        "--model",
        default=os.getenv("AI_MODEL", config.get("model", "gemini-3.7-flash-high")),
        help="Model identifier (default: gemini-3.7-flash-high or from config)",
    )
    parser.add_argument(
        "-u",
        "--base-url",
        default=os.getenv("AI_BASE_URL", config.get("base_url", "https://api.openai.com/v1")),
        help="OpenAI-compatible API base URL",
    )
    parser.add_argument(
        "-k",
        "--api-key",
        default=os.getenv("AI_API_KEY", config.get("api_key", "dummy")),
        help="API authorization key",
    )
    parser.add_argument(
        "-s",
        "--system",
        default=config.get("system_prompt"),
        help="Custom system prompt",
    )
    parser.add_argument(
        "-t",
        "--temperature",
        type=float,
        default=config.get("temperature"),
        help="Sampling temperature (0.0 - 2.0)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=25,
        help="Maximum tool execution turns in agent mode (default: 25)",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create a default config template at ~/.config/ai/config.json",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    if args.init_config:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        sample = {
            "base_url": args.base_url,
            "api_key": args.api_key,
            "model": args.model,
            "system_prompt": "You are a concise, helpful terminal assistant.",
            "temperature": 0.7,
            "require_approval": False,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2)
        print(f"Created configuration file at {CONFIG_FILE}")
        sys.exit(0)

    # Ingest stdin if piped
    stdin_text = ""
    if not sys.stdin.isatty():
        try:
            stdin_text = sys.stdin.read().strip()
        except Exception:
            pass

    args_text = " ".join(args.prompt).strip()

    if args_text and stdin_text:
        user_content = f"{args_text}\n\nInput Context:\n```\n{stdin_text}\n```"
    elif args_text:
        user_content = args_text
    elif stdin_text:
        user_content = stdin_text
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.agent:
        # Determine approval policy: CLI flag overrides config, default is False (auto-approve)
        require_approval = config.get("require_approval", False)
        if args.confirm is True:
            require_approval = True
        elif args.yes is True:
            require_approval = False

        auto_approve = not require_approval

    if args.agent:
        try:
            run_agent_loop(
                base_url=args.base_url,
                api_key=args.api_key,
                model=args.model,
                user_content=user_content,
                system_prompt=args.system,
                temperature=args.temperature,
                max_turns=args.max_turns,
                auto_approve=auto_approve,
            )
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(130)
    else:
        run_stream_completion(
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            user_content=user_content,
            system_prompt=args.system,
            temperature=args.temperature,
        )

if __name__ == "__main__":
    main()
