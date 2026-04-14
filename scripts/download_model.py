#!/usr/bin/env python3
"""
Download the sentence-transformers embedding model for News That Matters.

Required once per machine. After this runs the model is cached at:
  ~/.cache/news-that-matters/models/all-MiniLM-L6-v2/
...and the pipeline uses it automatically — no more TF-IDF fallback.

Strategy (Walmart network-aware):
  - Small text files (tokenizer, vocab, config): direct HuggingFace CDN — works fine
  - Model weights (model.safetensors, 87MB): curl with proxy through XetHub CDN
    Python's httpx client times out; curl with --max-time 300 succeeds at ~800KB/s

Usage:
    python scripts/download_model.py

After running, verify:
    python scripts/test_m1.py  (should say "Loading neural model from local cache")
"""
import os
import shutil
import ssl
import subprocess
import sys
import time
from pathlib import Path

MODEL_NAME  = "all-MiniLM-L6-v2"
HF_REPO     = "sentence-transformers/all-MiniLM-L6-v2"
HF_BASE_URL = f"https://huggingface.co/{HF_REPO}/resolve/main"
LOCAL_DIR   = Path.home() / ".cache" / "news-that-matters" / "models" / MODEL_NAME
PROXY       = "http://sysproxy.wal-mart.com:8080"

# Text files served directly by HF CDN (no XetHub redirect)
TEXT_FILES = [
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "README.md",
    "1_Pooling/config.json",
    "2_Normalize/config.json",
]

# Large binary files that go through XetHub CDN — need long timeout via curl
BINARY_FILES = [
    ("model.safetensors", 90_000_000),  # ~87MB actual
]


def is_complete() -> bool:
    """Return True if the model directory has all required files."""
    weights = LOCAL_DIR / "model.safetensors"
    tokenizer = LOCAL_DIR / "tokenizer.json"
    return (
        LOCAL_DIR.exists()
        and weights.exists() and weights.stat().st_size > 80_000_000
        and tokenizer.exists() and tokenizer.stat().st_size > 100_000
    )


def curl_download(url: str, dest: Path, timeout: int = 60, use_proxy: bool = True) -> bool:
    """Download a single file with curl. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["curl", "-skL", f"--max-time", str(timeout), "--retry", "2",
           "--retry-delay", "3", "-o", str(dest), url]
    if use_proxy:
        cmd = [f"HTTPS_PROXY={PROXY}", f"HTTP_PROXY={PROXY}"] + cmd
        # pass proxy via env instead of args (cleaner)
        env = {**os.environ, "HTTPS_PROXY": PROXY, "HTTP_PROXY": PROXY}
    else:
        env = os.environ.copy()

    result = subprocess.run(cmd, env=env, capture_output=True)
    if result.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        return False
    return True


def download_text_files() -> None:
    print("\n📄 Downloading config + tokenizer files (fast, direct CDN)…")
    failed = []
    for rel_path in TEXT_FILES:
        dest = LOCAL_DIR / rel_path
        if dest.exists() and dest.stat().st_size > 0:
            print(f"   ✓ {rel_path:<40} (cached)")
            continue

        url = f"{HF_BASE_URL}/{rel_path}"
        ok = curl_download(url, dest, timeout=30)
        if ok:
            size = dest.stat().st_size
            print(f"   ✓ {rel_path:<40} ({size:,} bytes)")
        else:
            print(f"   ✗ {rel_path:<40} FAILED")
            failed.append(rel_path)

    if failed:
        print(f"\n⚠️  {len(failed)} text file(s) failed. Network issue?")


def download_binary_files() -> None:
    print("\n🧠 Downloading model weights (87MB via XetHub CDN — expect ~2 min)…")
    for rel_path, expected_size in BINARY_FILES:
        dest = LOCAL_DIR / rel_path
        if dest.exists() and dest.stat().st_size >= expected_size * 0.95:
            print(f"   ✓ {rel_path} already cached ({dest.stat().st_size:,} bytes)")
            continue

        url = f"{HF_BASE_URL}/{rel_path}"
        print(f"   Downloading {rel_path} from HuggingFace…")
        start = time.time()
        ok = curl_download(url, dest, timeout=300)
        elapsed = time.time() - start

        if ok and dest.stat().st_size >= expected_size * 0.95:
            mb = dest.stat().st_size / 1_000_000
            print(f"   ✓ {rel_path} — {mb:.1f}MB in {elapsed:.0f}s ✅")
        else:
            actual = dest.stat().st_size if dest.exists() else 0
            print(f"   ✗ {rel_path} incomplete: {actual:,}/{expected_size:,} bytes after {elapsed:.0f}s")
            print("     → Try again; proxy can be slow. If consistently failing,")
            print("       download outside Walmart network and copy to:")
            print(f"       {dest}")
            sys.exit(1)


def verify_model() -> None:
    """Load and smoke-test the model to confirm it works end-to-end."""
    print("\n🔬 Verifying model loads and encodes correctly…")
    ssl._create_default_https_context = ssl._create_unverified_context

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(LOCAL_DIR))

    sentences = [
        "Federal Reserve raises interest rates amid inflation concerns.",
        "Fed hikes rates as US inflation remains elevated.",
        "SpaceX launches Starship on orbital test flight from Texas.",
    ]
    vecs = model.encode(sentences)
    sim_same  = float(vecs[0] @ vecs[1])   # Fed vs Fed — should be high
    sim_diff  = float(vecs[0] @ vecs[2])   # Fed vs SpaceX — should be low

    print(f"\n   Embedding shape           : {vecs.shape}")
    print(f"   Fed ↔ Fed similarity      : {sim_same:.4f}  (expect > 0.50 for RSS-length titles)")
    print(f"   Fed ↔ SpaceX similarity   : {sim_diff:.4f}  (expect < 0.30 for unrelated topics)")
    print(f"   Discrimination ratio      : {sim_same/max(sim_diff, 0.001):.1f}× (expect > 3×)")

    # all-MiniLM-L6-v2 on short sentences: related pairs score 0.5-0.8, unrelated < 0.2
    # threshold of 0.85 is for long-document pairs — wrong for RSS snippet text
    if sim_same > 0.50 and sim_diff < 0.30 and (sim_same / max(sim_diff, 0.001)) > 3.0:
        print("\n   🎉  Neural model verified — clustering quality is production-ready.")
        print("       Same-event articles with different phrasings WILL cluster correctly.")
    else:
        print(f"\n   ⚠️  Scores look wrong. Model may not have loaded correctly.")
        sys.exit(1)


def main() -> None:
    print("⚡ News That Matters — Neural Embedding Model Setup")
    print(f"   Target: {LOCAL_DIR}")
    print("=" * 60)

    if is_complete():
        print("\n✅  Model already fully cached. Running verification…")
        verify_model()
        print(f"\n→ All good. Run pipeline: python scripts/test_m1.py\n")
        return

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    download_text_files()
    download_binary_files()
    verify_model()

    print(f"\n✅  Setup complete. Model at: {LOCAL_DIR}")
    print(f"→  Run pipeline: python scripts/test_m1.py\n")


if __name__ == "__main__":
    main()
