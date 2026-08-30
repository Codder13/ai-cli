#!/usr/bin/env python3
"""
ai-cli: Zero-dependency, ultra-fast streaming AI CLI for Unix pipelines.
Compatible with any OpenAI-compatible endpoint (OpenAI, Groq, Ollama, vLLM, OpenRouter, Together, AGM).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

__version__ = "0.1.0"
CONFIG_DIR = Path.home() / ".config" / "ai"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Load configuration from ~/.config/ai/config.json with fallback to ~/.omp/agent/models.yml if present."""
    config = {}

    # 1. User config file
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    # 2. If base_url or api_key not set, fallback to OMP models.yml if available
    if not config.get("base_url") or not config.get("api_key"):
        omp_models = Path.home() / ".omp" / "agent" / "models.yml"
        if omp_models.is_file():
            try:
                import yaml  # optional check

                with open(omp_models, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    agm = data.get("providers", {}).get("agm", {})
                    if not config.get("base_url") and agm.get("baseUrl"):
                        config["base_url"] = agm["baseUrl"].rstrip("/")
                    if not config.get("api_key") and agm.get("apiKey"):
                        config["api_key"] = agm["apiKey"]
                    if not config.get("model") and agm.get("default"):
                        config["model"] = agm["default"]
            except Exception:
                # Basic non-yaml regex parse fallback so zero extra deps are required
                try:
                    text = omp_models.read_text(encoding="utf-8")
                    for line in text.splitlines():
                        if "baseUrl:" in line and not config.get("base_url"):
                            config["base_url"] = line.split("baseUrl:")[1].strip().strip('"').strip("'").rstrip("/")
                        elif "apiKey:" in line and not config.get("api_key"):
                            config["api_key"] = line.split("apiKey:")[1].strip().strip('"').strip("'")
                except Exception:
                    pass

    return config


def main() -> None:
    config = load_config()

    default_base_url = os.getenv("AI_BASE_URL", config.get("base_url", "https://api.openai.com/v1"))
    default_api_key = os.getenv("AI_API_KEY", config.get("api_key", "dummy"))
    default_model = os.getenv("AI_MODEL", config.get("model", "gemini-3.7-flash-high" if "basa-eagle" in default_base_url else "gpt-4o-mini"))
    default_system = os.getenv("AI_SYSTEM_PROMPT", config.get("system_prompt", ""))

    parser = argparse.ArgumentParser(
        prog="ai",
        description="⚡ Zero-dependency, ultra-fast streaming AI CLI for Unix pipelines.",
        epilog="""examples:
  ai what is the biggest thing on the moon
  git diff | ai summarize these changes in 3 bullet points
  ai -m gpt-4o -s "Reply only in valid JSON" generate 3 user profiles
  cat error.log | ai explain how to fix this
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "prompt",
        nargs="*",
        help="Prompt text or instruction to the model",
    )
    parser.add_argument(
        "-m", "--model",
        default=default_model,
        help=f"Model identifier (default: {default_model})",
    )
    parser.add_argument(
        "-u", "--base-url",
        default=default_base_url,
        help="OpenAI-compatible Base URL (env: AI_BASE_URL)",
    )
    parser.add_argument(
        "-k", "--api-key",
        default=default_api_key,
        help="API Key (env: AI_API_KEY)",
    )
    parser.add_argument(
        "-s", "--system",
        default=default_system,
        help="System instruction / persona prompt",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=config.get("temperature", 0.7),
        help="Sampling temperature (default: 0.7)",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create ~/.config/ai/config.json with interactive defaults",
    )
    parser.add_argument(
        "-v", "--version",
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
            "system_prompt": args.system or "",
            "temperature": args.temperature,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2)
        print(f"Created config file at {CONFIG_FILE}")
        return

    # Check for stdin (piped input)
    stdin_text = ""
    if not sys.stdin.isatty():
        try:
            stdin_text = sys.stdin.read().strip()
        except Exception:
            pass

    args_text = " ".join(args.prompt).strip()

    # Combine input
    if args_text and stdin_text:
        user_content = f"{args_text}\n\nContext / Input:\n```\n{stdin_text}\n```"
    elif args_text:
        user_content = args_text
    elif stdin_text:
        user_content = stdin_text
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)

    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": user_content})

    url = f"{args.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {args.api_key}",
    }
    payload = {
        "model": args.model,
        "messages": messages,
        "temperature": args.temperature,
        "stream": True,
    }

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
        # Graceful exit on Ctrl+C without Python traceback
        print()
        sys.exit(130)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print(f"\nAPI Error ({e.code}): {err_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
