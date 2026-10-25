"""Write the arm B input: the pre-registered prompt with condensed derivation transcripts.

  python analysis/features/armb_inputs.py --out DIR [--sessions runs/private/sessions]

The transcripts are the derivation sessions whose hard signal holds (runs/diagnoses/),
so each one shows the target. A transcript keeps the task message (not Droid's system
reminders, which repeat in every session), the assistant's
text, each tool call's name and input, and the start of each tool result, cut short,
since the raw JSONL of 20 sessions is about 9 MB. Arm B sees nothing else: no
features, diagnoses, scores, or grader output.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT_CHARS = 160
INPUT_CHARS = 240
TEXT_CHARS = 600
PROBLEM = "the agent makes many tool calls (reads, searches, shell commands) before its first file edit"


def clip(s, n):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n] + " [...]"


def render(path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        m = o.get("message") or {}
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for b in content or []:
            kind = b.get("type")
            if kind == "text" and b.get("text", "").strip():
                if role == "user" and b["text"].lstrip().startswith("<system-reminder>"):
                    continue  # Droid's own context, the same in every session
                out.append(f"[{role}] {clip(b['text'], 4000 if role == 'user' else TEXT_CHARS)}")
            elif kind == "tool_use":
                out.append(f"[tool call] {b['name']} {clip(json.dumps(b.get('input', {})), INPUT_CHARS)}")
            elif kind == "tool_result":
                body = b.get("content")
                body = body if isinstance(body, str) else json.dumps(body)
                err = " (error)" if b.get("is_error") else ""
                out.append(f"[tool result{err}] {clip(body, RESULT_CHARS)}")
    return "\n".join(out)


def prompt():
    text = (ROOT / "reports" / "preregistration.md").read_text(encoding="utf-8")
    block = text.split("## Arm B prompt", 1)[1].split("```", 2)[1].strip("\n")
    return block.replace("<target>", PROBLEM)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--sessions", type=Path, default=ROOT / "runs" / "private" / "sessions")
    ap.add_argument("--diagnoses", type=Path, default=ROOT / "runs" / "diagnoses")
    args = ap.parse_args()

    ids = sorted(json.loads(p.read_text())["session_id"] for p in args.diagnoses.glob("*.json") if p.name != "summary.json")
    parts = []
    for k, sid in enumerate(ids, 1):
        jsonl = sorted((args.sessions / sid / "factory-sessions").glob("*/*.jsonl"))
        if not jsonl:
            raise SystemExit(f"no transcript for {sid}")
        parts.append(f"=== Session {k} ===\n{render(jsonl[0])}")
    args.out.mkdir(parents=True, exist_ok=True)
    full = prompt().replace("<transcripts>", "\n\n".join(parts))
    (args.out / "prompt.md").write_text(full, encoding="utf-8", newline="\n")
    print(f"{len(ids)} sessions, {len(full):,} characters (about {len(full) // 4:,} tokens)")


if __name__ == "__main__":
    main()
