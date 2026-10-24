"""Draw splits/pro-pool.json from the gold-checked SWE-bench Pro candidates.

  python splits/pro_pool.py

A seeded shuffle within each language picks the held-out repos, so no one picks them by hand.
Tasks that an agent already ran (any job under runs/results/) never go to held-out.
"""

import json
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 13
LANGS = {
    "python": ["ansible/ansible", "internetarchive/openlibrary", "qutebrowser/qutebrowser"],
    "go": ["flipt-io/flipt", "gravitational/teleport", "future-architect/vuls", "navidrome/navidrome"],
}
HELD_OUT_REPOS = {"python": 1, "go": 2}
ALPINE_IMAGE_SUFFIX = "-vee9b09fb20c43af7e520f57e9239bbcf46b7113d"


def repo_of(instance_id):
    owner, rest = instance_id.removeprefix("instance_").split("__", 1)
    return f"{owner}/{rest.split('-')[0]}"


def main():
    checked = json.loads((ROOT / "splits" / "pro-gold-check.json").read_text())
    ok = [c["instance_id"] for c in checked if c["gold_reward"] == 1 and c["empty_reward"] == 0
          and not c["instance_id"].endswith(ALPINE_IMAGE_SUFFIX)]
    ran = {json.loads(p.read_text())["task_id"] for p in (ROOT / "runs" / "results").glob("*/*.json")}

    held_repos = []
    for lang, repos in LANGS.items():
        shuffled = sorted(repos)
        random.Random(f"{SEED}/{lang}").shuffle(shuffled)
        held_repos += shuffled[:HELD_OUT_REPOS[lang]]

    by_repo = {repo: [i for i in ok if repo_of(i) == repo] for repos in LANGS.values() for repo in repos}
    assert sum(map(len, by_repo.values())) == len(ok), "an instance id did not map to a repo"
    dev = [i for repo, ids in by_repo.items() if repo not in held_repos for i in ids]
    held_out = [i for repo in held_repos for i in by_repo[repo] if i not in ran]

    out = {
        "drawn": date.today().isoformat(),
        "seed": SEED,
        "source": "ScaleAI/SWE-bench_Pro (default config, V2). Tasks from splits/pro-candidates.json that pass "
                  "the gold patch and fail the empty patch (splits/pro-gold-check.json). Held-out repos come from "
                  "a seeded shuffle within each language. Tasks an agent already ran are left out of held-out. Tasks whose "
                  "image is Alpine are left out because the glibc Droid binary does not run there.",
        "held_out_repos": held_repos,
        "dev": dev,
        "held_out": held_out,
    }
    (ROOT / "splits" / "pro-pool.json").write_text(json.dumps(out, indent=2) + "\n", newline="\n")
    print(f"held-out repos {held_repos}; dev {len(dev)}, held_out {len(held_out)}")


if __name__ == "__main__":
    main()
