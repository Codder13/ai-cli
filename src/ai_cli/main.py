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
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

__version__ = "0.8.0"
CONFIG_DIR = Path.home() / ".config" / "ai"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_MAX_MESSAGES = 20

def get_session_file() -> Path:
    """Return session history file path for the parent shell PID."""
    ppid = os.getppid()
    return Path(f"/tmp/ai_session_{ppid}.json")

def load_session_history() -> list:
    """Load conversation messages from current terminal session."""
    session_file = get_session_file()
    if session_file.is_file():
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                return history[-SESSION_MAX_MESSAGES:]
        except Exception:
            pass
    return []

def save_session_history(messages: list) -> None:
    """Save conversation messages to current terminal session."""
    session_file = get_session_file()
    try:
        with open(session_file, "w", encoding="utf-8") as f:
            # Persist user and assistant messages only to keep context clean
            filtered = [
                m for m in messages
                if m.get("role") in ("user", "assistant") and m.get("content")
            ]
            json.dump(filtered[-SESSION_MAX_MESSAGES:], f)
    except Exception:
        pass

def clear_session_history() -> None:
    """Clear conversation history for the current terminal session."""
    session_file = get_session_file()
    if session_file.is_file():
        try:
            session_file.unlink(missing_ok=True)
        except Exception:
            pass
def format_session_for_handoff() -> str:
    """Format conversation messages from current shell session into a unified context prompt."""
    history = load_session_history()
    if not history:
        return ""
    formatted = ["=== Conversation Context from ai-cli Terminal Session ==="]
    for msg in history:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "").strip()
        formatted.append(f"\n[{role}]:\n{content}")
    formatted.append("\n=== End Context ===\nPlease continue and solve the task based on the context above.")
    return "\n".join(formatted)

def execute_handoff(target_harness: str = "omp", extra_instruction: str = "") -> None:
    """Handoff session context and launch the target agent harness (omp, claude, codex, pi)."""
    import shutil

    context = format_session_for_handoff()
    full_prompt = context
    if extra_instruction:
        full_prompt = f"{context}\n\nAdditional Instruction: {extra_instruction}" if context else extra_instruction

    harness = (target_harness or "omp").lower().strip()

    # Find executable binary
    bin_name = harness
    if harness in ("omp", "hermes"):
        bin_path = shutil.which("omp") or shutil.which("hermes")
        label = "Oh My Pi (OMP)"
    elif harness in ("claude", "claude-code"):
        bin_path = shutil.which("claude")
        label = "Claude Code"
    elif harness in ("codex",):
        bin_path = shutil.which("codex")
        label = "Codex"
    elif harness in ("pi",):
        bin_path = shutil.which("pi")
        label = "Pi"
    else:
        bin_path = shutil.which(harness)
        label = harness

    if not bin_path:
        print(f"\033[31mError:\033[0m Harness binary for '{harness}' not found in PATH.", file=sys.stderr)
        print("Supported harnesses: omp, claude, codex, pi", file=sys.stderr)
        sys.exit(1)

    print(f"\033[1;35m🚀 Handing off session to {label} ({bin_path})...\033[0m")
    if full_prompt:
        os.execvp(bin_path, [bin_path, full_prompt])
    else:
        os.execvp(bin_path, [bin_path])

def print_markdown(text: str) -> None:
    """Render markdown using rich into clean terminal output, or plain text if piped."""
    if not sys.stdout.isatty():
        print(text)
        return
    try:
        from rich.console import Console
        from rich.markdown import Markdown
        console = Console()
        console.print(Markdown(text))
    except Exception:
        print(text)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a local shell command (e.g. tests, git, compilers, local processes). Do NOT use bash to curl or scrape the web unless the user explicitly requests a curl/shell command.",
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
            "description": "Search the web for information, documentation, or news. Always use this tool when web information is needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_web_page",
            "description": "Fetch and read the text content of a web page URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The HTTP or HTTPS URL to read"},
                    "max_chars": {"type": "integer", "description": "Maximum characters to return (default: 4000)"},
                },
                "required": ["url"],
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


def execute_bash(command: str, max_chars: int = 12000, sandbox: bool = True) -> str:
    """Execute command in bash (optionally sandboxed via bwrap) and return combined stdout/stderr."""
    bwrap_path = shutil.which("bwrap")
    use_sandbox = sandbox and bool(bwrap_path)

    if use_sandbox:
        pwd = os.getcwd()
        home = os.path.expanduser("~")
        cmd_args = [
            bwrap_path,
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", f"{home}/.ssh",
            "--tmpfs", f"{home}/.gnupg",
            "--bind", pwd, pwd,
            "--share-net",
            "--",
            "/bin/bash", "-c", command,
        ]
    else:
        cmd_args = ["/bin/bash", "-c", command]

    try:
        res = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=60,
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


def execute_web_search(query: str, max_results: int = 8) -> str:
    """Search the web with automatic multi-engine fallbacks (Startpage, DuckDuckGo, Bing)."""
    # 1. Primary Engine: Startpage (Google-powered, unblocked, fast)
    try:
        url = "https://www.startpage.com/sp/search"
        data = urllib.parse.urlencode({"query": query}).encode("utf-8")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            page = resp.read().decode("utf-8", errors="ignore")

        results = []
        for m in re.finditer(
            r"<a[^>]*class=[\x27\"][^\x27\"]*result-title[^\x27\"]*[\x27\"][^>]*href=[\x27\"]([^\x27\"]+)[\x27\"][^>]*>(.*?)</a>",
            page,
        ):
            link = m.group(1)
            raw_title = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)).strip())
            # Strip inline CSS if injected
            title = re.sub(r"^[^{]+\{[^}]+\}", "", raw_title).strip()
            if not title:
                title = raw_title
            results.append(f"- **Title:** {title}\n  **URL:** {link}")
            if len(results) >= max_results:
                break
        if results:
            return "\n\n".join(results)
    except Exception:
        pass

    # 2. Secondary Engine: DuckDuckGo HTML POST
    try:
        url = "https://html.duckduckgo.com/html/"
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://html.duckduckgo.com/",
            "Origin": "https://html.duckduckgo.com",
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            page = resp.read().decode("utf-8", errors="ignore")

        results = []
        for m in re.finditer(
            r"<a[^>]*class=\"result__snippet[^\"]*\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
            page,
            re.DOTALL,
        ):
            raw_url = m.group(1)
            u_match = re.search(r"uddg=([^&]+)", raw_url)
            link = urllib.parse.unquote(u_match.group(1)) if u_match else raw_url
            snippet = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)).strip())
            results.append(f"- **URL:** {link}\n  **Snippet:** {snippet}")
            if len(results) >= max_results:
                break
        if results:
            return "\n\n".join(results)
    except Exception:
        pass

    return "No results found."

def execute_fetch_web_page(url_str: str, max_chars: int = 4000) -> str:
    """Fetch clean, readable text from a web page URL."""
    if not url_str.startswith("http://") and not url_str.startswith("https://"):
        url_str = "https://" + url_str
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url_str, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
        # Strip scripts, styles, and tags
        clean = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = html.unescape(clean)
        clean = " ".join(clean.split())
        if len(clean) > max_chars:
            clean = clean[:max_chars] + f"\n... [Truncated to {max_chars} chars]"
        return clean if clean.strip() else "[Web page contained no readable text]"
    except Exception as e:
        return f"[Error fetching web page: {e}]"


def run_agent_loop(
    base_url: str,
    api_key: str,
    model: str,
    user_content: str,
    system_prompt: str = None,
    temperature: float = None,
    max_turns: int = 15,
    auto_approve: bool = False,
    sandbox: bool = True,
) -> None:
    """Run an agentic loop with bash, read_file, write_file, search_web, and fetch_web_page tools."""
    base_instructions = (
        "You are a fast, lightweight terminal assistant. "
        "Your primary job is to resolve simple requests quickly, accurately, and concisely.\n\n"
        "Tool Usage Policy:\n"
        "- Efficiency & Quality: Use the minimum number of tool calls needed, but NEVER sacrifice answer quality, accuracy, or completeness. Always be confident that you have fully answered the user's intent with grounded facts before finishing.\n"
        "- Internet Requests: When searching or retrieving information from the internet, ALWAYS use `search_web` (and `fetch_web_page` to read specific URLs).\n"
        "- Shell & Commands: Only use `bash` to fetch web content if the user explicitly asks to run a curl/bash/script command. Use `bash` for local system tasks.\n"
        "- Directness: Provide direct, clear answers without unnecessary fluff or excessive commentary."
    )
    history = load_session_history()
    messages = []
    sys_content = f"{base_instructions}\n\n{system_prompt}" if system_prompt else base_instructions
    messages.append({"role": "system", "content": sys_content})
    if history:
        messages.extend(history)
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
                print_markdown(content)
                # Persist updated session history
                updated_history = list(history)
                updated_history.append({"role": "user", "content": user_content})
                updated_history.append({"role": "assistant", "content": content})
                save_session_history(updated_history)
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
                output = execute_bash(cmd, sandbox=sandbox)
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
                if output.startswith("[Web Search Error") or output == "No results found.":
                    print(f"  \033[31m✗ {output}\033[0m")
                else:
                    # Count found results
                    items = [line for line in output.split("\n\n") if line.strip().startswith("- **")]
                    count = len(items) if items else 1
                    print(f"  \033[32m✓ Found {count} result{'s' if count != 1 else ''}\033[0m")
                    for item in items[:3]:
                        first_line = item.strip().split("\n")[0]
                        clean_first = first_line.replace("- **Title:**", "•").replace("- **URL:**", "•")
                        print(f"    \033[90m{clean_first[:85]}\033[0m")
                    if len(items) > 3:
                        print(f"    \033[90m... and {len(items)-3} more\033[0m")
                messages.append({"role": "tool", "tool_call_id": tool_id, "content": output})

            elif fname in ("fetch_web_page", "read_url", "fetch_url"):
                u = args.get("url") or args.get("link") or ""
                mc = args.get("max_chars", 4000)
                print(f"\033[1;35m📄 Fetch Page:\033[0m \033[36m{u}\033[0m")
                output = execute_fetch_web_page(u, max_chars=mc)
                if output.startswith("[Error"):
                    print(f"  \033[31m✗ {output}\033[0m")
                else:
                    print(f"  \033[32m✓ Fetched {len(output)} chars\033[0m")
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
    history = load_session_history()
    messages = []
    default_no_tool_system = (
        "You are a fast, lightweight terminal assistant. "
        "Your job is to resolve simple requests quickly, accurately, and concisely."
    )
    sys_content = f"{default_no_tool_system}\n\n{system_prompt}" if system_prompt else default_no_tool_system
    messages.append({"role": "system", "content": sys_content})
    if history:
        messages.extend(history)
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

    full_response = []
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
                            full_response.append(content)
                    except json.JSONDecodeError:
                        continue
        print_markdown("".join(full_response))
        if full_response:
            updated_history = list(history)
            updated_history.append({"role": "user", "content": user_content})
            updated_history.append({"role": "assistant", "content": "".join(full_response)})
            save_session_history(updated_history)
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
            "  ai search the latest zig release and summarize changes\n"
            "  git diff | ai summarize changes in 3 bullets\n"
            "  ai inspect package.json and run the test script\n"
            "  ai -n 'Reply in haiku' explain rust (pure prompt mode, no tools)\n"
            "  ai -m claude-3-5-sonnet 'explain quantum entanglement'"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", nargs="*", help="User prompt or instruction")
    parser.add_argument(
        "-n",
        "--no-tools",
        "--no-agent",
        action="store_true",
        help="Disable tools and run in fast direct streaming completion mode",
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
        "-s",
        "--no-sandbox",
        action="store_true",
        help="Disable Bubblewrap sandbox and run commands directly on the host",
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
    parser.add_argument(
        "-C",
        "--clear",
        action="store_true",
        help="Clear conversation memory for the current terminal session",
    )
    parser.add_argument(
        "-H",
        "--handoff",
        nargs="?",
        const="omp",
        default=None,
        metavar="HARNESS",
        help="Handoff session context and launch a heavy agent harness (omp, claude, codex, pi; default: omp)",
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
    if args.clear:
        clear_session_history()
        print("✨ Cleared conversation session memory.")
        sys.exit(0)
    if args.handoff is not None:
        extra_inst = " ".join(args.prompt).strip()
        execute_handoff(args.handoff, extra_inst)
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

    # Resolve approval preference
    require_approval = config.get("require_approval", False)
    auto_approve = True
    if args.confirm:
        auto_approve = False
    elif args.yes:
        auto_approve = True
    elif require_approval:
        auto_approve = False
    if args.no_tools:
        run_stream_completion(
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            user_content=user_content,
            system_prompt=args.system,
            temperature=args.temperature,
        )
    else:
        use_sandbox = not args.no_sandbox and config.get("sandbox", True)
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
                sandbox=use_sandbox,
            )
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(130)

if __name__ == "__main__":
    main()
