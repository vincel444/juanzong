# -*- coding: utf-8 -*-
"""Build pages into the deck with rotating filenames (engine keeps zombie handles
on names it has saved, so every page uses a fresh file name).

Flow per page n:
  copy <src> -> _w{n}.pptx
  edsdk open_file _w{n}.pptx (background), wait load
  slidep upsert --dsl-file slides/{n}.slide
     - ok  -> direct save worked; result file = _w{n}.pptx
     - 500 -> commit landed; edsdk save_file -> _w{n}_out.pptx; result = that
  close editors for both names (force)
Next page seeds from the result. Final result copied to the deck.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile

NODE = r"C:/Users/54780/.workbuddy/binaries/node/versions/22.22.2-3/node.exe"
SLIDEP = r"C:/Users/54780/.workbuddy/binaries/node/versions/22.22.2-3/node_modules/@tencent/slidep/dist/slidep.js"
EDSDK = r"F:/ai/WorkBuddy/resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/tencent-local-office-edit/edsdk.py"
FINAL = os.path.abspath("卷宗-初赛PPT.pptx")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def slidep(*args):
    return run([NODE, SLIDEP, *args])


def edsdk(*args):
    r = run([sys.executable, EDSDK, "call", *args])
    return r.stdout + "\n" + r.stderr


def close_all_for(*paths):
    out = edsdk("get_pool_status")
    try:
        pool = json.loads(out[: out.rfind("}") + 1])
    except Exception:
        return
    norms = [p.lower().replace("\\", "/") for p in paths]
    for ed in pool.get("open_editors", []):
        fp = ed.get("file_path", "").lower().replace("\\", "/")
        fid = ed.get("file_id", "").lower().replace("\\", "/")
        if any(n in fp or n in fid for n in norms):
            print("  close", ed["file_id"][:50])
            edsdk("close_file", f"file_id={ed['file_id']}", "force=true")
    time.sleep(2)


def slide_count(pptx):
    with zipfile.ZipFile(pptx) as z:
        return len([n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")])


def copy_retry(src, dst, tries=8):
    for i in range(tries):
        try:
            shutil.copyfile(src, dst)
            return True
        except Exception as e:
            print(f"  copy retry {i}: {e}")
            time.sleep(2)
    return False


def build_page(n, src):
    work = os.path.abspath(f"_w{n}.pptx")
    out = os.path.abspath(f"_w{n}_out.pptx")
    dsl = os.path.abspath(f"slides/{n:02d}.slide")
    print(f"== page {n:02d} (seed={os.path.basename(src)}) ==")
    assert slide_count(src) == n - 1, f"seed has {slide_count(src)} slides, expected {n-1}"
    assert copy_retry(src, work), "cannot seed work file"
    close_all_for(work, out)

    result = None
    for attempt in range(3):
        print("  open fresh session")
        print("  >", edsdk("open_file", f"file_path={work}").strip().splitlines()[0])
        time.sleep(6)
        r = slidep("upsert-dsl", work, "--dsl-file", dsl)
        line = next((l for l in r.stdout.splitlines() if l.startswith("{")), "")
        ok, err = False, ""
        if line:
            try:
                d = json.loads(line)
                ok, err = d.get("ok", False), str(d.get("error", ""))[:160]
            except Exception:
                err = line[:160]
        else:
            err = (r.stderr or r.stdout)[-160:]
        if ok:
            print("  upsert + direct save ok")
            result = work
            break
        if "localapi/save" in err and "10005" in err:
            print("  commit landed, save 500 -> save-as fallback")
            fid = None
            for _ in range(8):
                st = edsdk("get_pool_status")
                try:
                    pool = json.loads(st[: st.rfind("}") + 1])
                    dirty = [e for e in pool.get("open_editors", [])
                             if e.get("is_dirty") and work.lower().replace("\\", "/") in
                             (e.get("file_path", "").lower().replace("\\", "/") + e.get("file_id", "").lower().replace("\\", "/"))]
                    if dirty:
                        fid = dirty[0]["file_id"]
                        break
                except Exception:
                    pass
                time.sleep(1)
            if not fid:
                print("  no dirty instance; retry cycle")
                close_all_for(work, out)
                continue
            sv = edsdk("save_file", f"file_id={fid}", f"file_path={out}")
            if "File saved" not in sv:
                print("  save-as failed:", sv[-200:])
                close_all_for(work, out)
                continue
            if slide_count(out) != n:
                print(f"  save-as slides={slide_count(out)} != {n}; retry cycle")
                close_all_for(work, out)
                continue
            result = out
            break
        if "not open" in err or "keyframe" in err:
            print(f"  keyframe race (attempt {attempt+1}), cleanup + retry")
            close_all_for(work, out)
            continue
        print("  UNEXPECTED error:", err)
        close_all_for(work, out)
        continue

    if result is None:
        raise RuntimeError(f"page {n} failed")
    close_all_for(work, out)
    print(f"  page {n:02d} ok via {os.path.basename(result)}")
    return result


if __name__ == "__main__":
    seed = os.path.abspath("_build_next.pptx")  # 4 pages, recovered
    if len(sys.argv) > 2:
        seed = os.path.abspath(sys.argv[2])
    pages = [int(a) for a in sys.argv[1].split(",")] if len(sys.argv) > 1 else list(range(5, 13))
    for n in pages:
        seed = build_page(n, seed)
        shutil.copyfile(seed, FINAL)
        print(f"  synced final deck: {slide_count(FINAL)} slides")
    print("ALL DONE, final =", seed)
