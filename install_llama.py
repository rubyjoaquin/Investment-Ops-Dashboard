#!/usr/bin/env python3
"""
install_llama.py - download the llama.cpp engine (llama-server.exe) for Windows into
a "llama_cpp" folder next to this script. Python standard library only; no winget needed.

  python install_llama.py              # auto-pick: NVIDIA CUDA if you have it, else Vulkan, else CPU
  python install_llama.py --backend vulkan   # force one of: cuda, vulkan, cpu
  python install_llama.py --list       # show what the latest release offers, download nothing
"""
import argparse, io, json, os, re, shutil, subprocess, sys, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, "llama_cpp")
API = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=30"
UA = {"User-Agent": "install_llama.py"}


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if binary else json.loads(r.read().decode())


def download(url, label):
    req = urllib.request.Request(url, headers=UA)
    buf = io.BytesIO()
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            buf.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {label}: {done / 1e6:6.0f} / {total / 1e6:.0f} MB", end="", flush=True)
    print()
    buf.seek(0)
    return buf


def nvidia_cuda_version():
    """Return (major, minor) of the CUDA version your NVIDIA *driver* supports, or None."""
    try:
        out = subprocess.check_output(["nvidia-smi"], text=True, stderr=subprocess.DEVNULL, timeout=10)
        m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", out)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    except Exception:
        return None


def pick(assets, backend):
    """assets: dict name -> url. Returns list of (name, url) to download."""
    def find(pattern):
        hits = sorted((n for n in assets if re.fullmatch(pattern, n)), reverse=True)
        return hits
    if backend == "cuda":
        cv = nvidia_cuda_version() or (0, 0)
        want = []
        if cv[0] >= 13:
            want = [r"llama-.*-bin-win-cuda-13\.\d+-x64\.zip", r"llama-.*-bin-win-cuda-12\.4-x64\.zip"]
        elif cv >= (12, 4):
            want = [r"llama-.*-bin-win-cuda-12\.4-x64\.zip"]
        for pat in want:
            main = find(pat)
            if main:
                ver = re.search(r"cuda-([\d.]+)-x64", main[0]).group(1)
                rt = find(r"cudart-llama-bin-win-cuda-" + re.escape(ver) + r"-x64\.zip")
                return [(main[0], assets[main[0]])] + [(rt[0], assets[rt[0]])] * bool(rt)
        print("Your NVIDIA driver is too old for the CUDA builds (needs CUDA 12.4+). "
              "Update your NVIDIA driver, or use --backend vulkan.")
        return []
    pat = {"vulkan": r"llama-.*-bin-win-vulkan-x64\.zip", "cpu": r"llama-.*-bin-win-cpu-x64\.zip"}[backend]
    m = find(pat)
    return [(m[0], assets[m[0]])] if m else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["cuda", "vulkan", "cpu"])
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if os.name != "nt":
        print("This installer is for Windows. On Mac use: brew install llama.cpp")

    print("Asking GitHub for recent llama.cpp releases...")
    try:
        releases = get(API)
    except Exception as e:
        sys.exit(f"Couldn't reach GitHub ({e}).\nCheck your internet/firewall, or download the zips by hand from "
                 "https://github.com/ggml-org/llama.cpp/releases (see the manual steps in the instructions).")
    releases = [r for r in releases if not r.get("draft")]

    if a.list:
        for r in releases[:8]:
            names = sorted(x["name"] for x in r["assets"] if "win" in x["name"])
            print(f"\n{r['tag_name']}  ({len(r['assets'])} files, {len(names)} Windows)")
            for n in names:
                print("   ", n)
        return

    backend = a.backend
    if not backend:
        backend = "cuda" if nvidia_cuda_version() is not None else "vulkan"
        print(f"Auto-selected backend: {backend}" + ("  (NVIDIA GPU found)" if backend == "cuda" else "  (no NVIDIA GPU found)"))

    todo, tag = [], None
    for r in releases:
        assets = {x["name"]: x["browser_download_url"] for x in r["assets"]}
        todo = pick(assets, backend)
        if todo:
            tag = r["tag_name"]
            break
        if not any("bin-win" in n for n in assets):
            print(f"  skipping {r['tag_name']} (no Windows engine files in it)")
    if not todo:
        print("\nCouldn't find a matching download in the 30 most recent releases.")
        print("Run:  python install_llama.py --list   and send me the output.")
        print("Or download by hand: https://github.com/ggml-org/llama.cpp/releases")
        sys.exit(1)
    print("Using release:", tag)

    os.makedirs(DEST, exist_ok=True)
    for name, url in todo:
        print("Downloading", name)
        z = zipfile.ZipFile(download(url, name))
        z.extractall(DEST)
    # some releases unpack into a subfolder; make sure the exe + DLLs end up together and findable
    exe = None
    for root, _, files in os.walk(DEST):
        if "llama-server.exe" in files:
            exe = os.path.join(root, "llama-server.exe")
            break
    if not exe:
        sys.exit("Downloaded, but llama-server.exe wasn't in the archive. Run with --list and tell me the names.")
    print("\nInstalled:", exe)
    print("Next step:  python start_qwen.py")


if __name__ == "__main__":
    main()
