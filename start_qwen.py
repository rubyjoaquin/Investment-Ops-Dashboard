#!/usr/bin/env python3
"""
start_qwen.py - launch your local Qwen GGUF with llama.cpp's llama-server,
tuned to this machine's GPU (VRAM) and system RAM. No third-party packages needed.

Usage examples
  python start_qwen.py                          # auto-find model + llama-server, auto GPU/RAM fit
  python start_qwen.py --model "D:\\models\\Qwen3-8B-Q4_K_M.gguf"
  python start_qwen.py --ctx 16384              # longer context (uses more memory)
  python start_qwen.py --gpu-layers 20          # force N layers on GPU, rest in system RAM
  python start_qwen.py --cpu-only               # no GPU at all
  python start_qwen.py --monitor 10             # print GPU/RAM usage every 10 seconds
  python start_qwen.py --info                   # just show hardware + plan, don't start
Then open Investment_Ops_Dashboard_AI.html in your browser (double-click it).
"""
import argparse, ctypes, glob, os, platform, shutil, subprocess, sys, threading, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
GB = 1024 ** 3


# ---------------------------------------------------------------- hardware
def run(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=8).strip()
    except Exception:
        return ""


def ram():
    """(total_bytes, available_bytes) or (None, None)"""
    try:
        import psutil  # optional
        m = psutil.virtual_memory()
        return m.total, m.available
    except Exception:
        pass
    s = platform.system()
    try:
        if s == "Windows":
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tot", ctypes.c_ulonglong),
                            ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = MS(); m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.tot, m.avail
        if s == "Linux":
            d = {}
            for line in open("/proc/meminfo"):
                k, v = line.split(":", 1); d[k] = int(v.split()[0]) * 1024
            return d["MemTotal"], d.get("MemAvailable", d["MemFree"])
        if s == "Darwin":
            tot = int(run(["sysctl", "-n", "hw.memsize"]) or 0)
            return (tot or None), None
    except Exception:
        pass
    return None, None


def gpus():
    """NVIDIA GPUs via nvidia-smi -> list of dicts (MiB). Empty if none."""
    out = run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free",
               "--format=csv,noheader,nounits"])
    res = []
    for line in out.splitlines():
        p = [x.strip() for x in line.split(",")]
        if len(p) == 4 and p[1].isdigit():
            res.append({"name": p[0], "total": int(p[1]), "used": int(p[2]), "free": int(p[3])})
    return res


def fmt_gb(b):
    return "?" if b is None else f"{b / GB:.1f} GB"


# ---------------------------------------------------------------- discovery
def find_model(arg):
    if arg:
        if os.path.isfile(arg):
            return arg
        sys.exit(f"Model file not found: {arg}")
    env = os.environ.get("QWEN_GGUF")
    if env and os.path.isfile(env):
        return env
    roots = [HERE, os.path.join(HERE, "models"), os.path.join(HOME, "models"), os.path.join(HOME, "Downloads"),
             os.path.join(HOME, "Documents"), os.path.join(HOME, ".cache", "huggingface"),
             os.path.join(HOME, ".cache", "lm-studio", "models"), os.path.join(HOME, ".lmstudio", "models"),
             os.path.join(HOME, "AppData", "Local", "nomic.ai", "GPT4All"), "C:\\models", "D:\\models", "/models"]
    found = []
    for r in roots:
        if os.path.isdir(r):
            for f in glob.glob(os.path.join(r, "**", "*.gguf"), recursive=True):
                n = os.path.basename(f).lower()
                if "qwen" in n and "mmproj" not in n:
                    found.append(f)
    if not found:
        sys.exit("Couldn't find a Qwen .gguf automatically. Re-run with --model \"path\\to\\your-model.gguf\"")
    found.sort(key=lambda f: ("q4_k_m" not in f.lower(), -os.path.getmtime(f)))
    if len(found) > 1:
        print("Several Qwen GGUF files found; using the first. Use --model to pick another:")
        for f in found[:6]:
            print("   ", f)
    return found[0]


def find_server(arg):
    cands = [arg] if arg else []
    exe = "llama-server.exe" if platform.system() == "Windows" else "llama-server"
    w = shutil.which("llama-server")
    if w:
        cands.append(w)
    cands += [os.path.join(HERE, exe), os.path.join(HERE, "llama.cpp", "build", "bin", exe),
              os.path.join(HOME, "llama.cpp", "build", "bin", exe), os.path.join(HOME, "llama.cpp", exe),
              os.path.join(HOME, "AppData", "Local", "Microsoft", "WinGet", "Links", exe)]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    hits = glob.glob(os.path.join(HERE, "**", exe), recursive=True)   # e.g. .\llama_cpp\llama-server.exe
    if hits:
        return hits[0]
    sys.exit("Couldn't find llama-server. Install llama.cpp first (see the install commands), "
             "or pass --server \"path\\to\\llama-server\".")


# ---------------------------------------------------------------- monitor
def monitor(sec, stop):
    while not stop.wait(sec):
        t, a = ram()
        line = "[usage] "
        g = gpus()
        if g:
            line += " | ".join(f"GPU{i} {x['used']}/{x['total']} MiB" for i, x in enumerate(g)) + " | "
        if t:
            line += f"RAM used {fmt_gb(t - a) if a else '?'} of {fmt_gb(t)}"
        print(line, flush=True)


def wait_ready(url, stop):
    for _ in range(600):
        if stop.is_set():
            return
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as r:
                if r.status == 200:
                    print(f"\n>>> Qwen is READY at {url}\n>>> Open Investment_Ops_Dashboard_AI.html in your browser.\n", flush=True)
                    return
        except Exception:
            pass
        time.sleep(1)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Launch local Qwen for the SOP dashboard")
    ap.add_argument("--model"); ap.add_argument("--server")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--ctx", type=int, default=8192, help="context window in tokens (default 8192)")
    ap.add_argument("--gpu-layers", type=int, help="force this many layers onto the GPU (default: llama.cpp auto-fits)")
    ap.add_argument("--cpu-only", action="store_true")
    ap.add_argument("--threads", type=int, help="CPU threads (default: half of logical cores)")
    ap.add_argument("--kv-q8", action="store_true", help="8-bit KV cache: saves memory on long contexts")
    ap.add_argument("--mlock", action="store_true", help="pin the model in RAM so the OS can't swap it out")
    ap.add_argument("--monitor", type=int, default=0, metavar="SEC", help="print GPU/RAM usage every SEC seconds")
    ap.add_argument("--info", action="store_true", help="show hardware and plan, then exit")
    ap.add_argument("--extra", default="", help="extra raw llama-server flags, in quotes")
    a = ap.parse_args()

    model = find_model(a.model)
    server = find_server(a.server)
    msize = os.path.getsize(model)
    tot, avail = ram()
    g = gpus()

    print("=" * 64)
    print(f"Model : {model}  ({fmt_gb(msize)})")
    print(f"Server: {server}")
    print(f"CPU   : {os.cpu_count()} logical cores")
    print(f"RAM   : {fmt_gb(tot)} total, {fmt_gb(avail)} available")
    if g:
        for i, x in enumerate(g):
            print(f"GPU{i}  : {x['name']}  {x['total']} MiB total, {x['free']} MiB free")
    else:
        print("GPU   : no NVIDIA GPU detected via nvidia-smi (Apple Silicon/AMD/Vulkan builds can still use their GPU)")

    need = msize + 1.0 * GB + (a.ctx / 1024) * 0.15 * GB  # weights + overhead + rough KV cache (~0.15 GB per 1k tokens, 8B-class)
    if a.cpu_only:
        print(f"Plan  : CPU only. Needs about {fmt_gb(msize + 1 * GB)} of free RAM.")
    elif g:
        free = sum(x["free"] for x in g) * 1024 * 1024
        if free >= need:
            print(f"Plan  : whole model fits in VRAM (~{fmt_gb(need)} needed). Fastest option.")
        else:
            spill = max(0, need - free)
            print(f"Plan  : partial GPU offload. ~{fmt_gb(spill)} will live in system RAM (slower but works).")
            if avail and spill > avail:
                print("WARNING: not enough free RAM for the spill-over. Close apps, lower --ctx, or use a smaller quant.")
    elif tot and msize + 1 * GB > (avail or tot):
        print("WARNING: model may not fit in free RAM.")
    print("=" * 64)
    if a.info:
        return

    cmd = [server, "-m", model, "-c", str(a.ctx), "--host", "127.0.0.1", "--port", str(a.port),
           "-t", str(a.threads or max(1, (os.cpu_count() or 4) // 2)), "--jinja", "-np", "1"]
    if a.cpu_only:
        cmd += ["-ngl", "0"]
    elif a.gpu_layers is not None:
        cmd += ["-ngl", str(a.gpu_layers)]          # explicit value turns off auto-fit for layers
    # otherwise: llama.cpp's built-in --fit (on by default in current builds) picks layers/ctx to fit free memory
    if a.kv_q8:
        cmd += ["--cache-type-k", "q8_0", "--cache-type-v", "q8_0"]
    if a.mlock:
        cmd += ["--mlock"]
    if a.extra:
        cmd += a.extra.split()

    print("Starting:", " ".join(f'"{c}"' if " " in c else c for c in cmd), "\n"
          "(Watch the log below: lines mentioning 'offloaded N/M layers' show the real GPU use.)\n", flush=True)
    stop = threading.Event()
    url = f"http://127.0.0.1:{a.port}"
    threading.Thread(target=wait_ready, args=(url, stop), daemon=True).start()
    if a.monitor:
        threading.Thread(target=monitor, args=(a.monitor, stop), daemon=True).start()
    p = subprocess.Popen(cmd)
    try:
        sys.exit(p.wait())
    except KeyboardInterrupt:
        print("\nStopping Qwen...")
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
