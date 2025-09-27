#!/usr/bin/env python3

import argparse
import psutil
import re
import html
import shutil
import subprocess
from typing import Dict, List, Tuple, Optional, Set

def f_getprocesses() -> Dict[int, psutil.Process]:
    procs                   = {}
    i                       = 1
    for p in psutil.process_iter(attrs=[], ad_value=None):
        print(f"     \r{i} ", end='', flush=True)
        i                   += 1
        try:
            procs[p.pid] = p
        except psutil.NoSuchProcess:
            pass
    return procs

def f_mapchild(index: Dict[int, psutil.Process]) -> Dict[int, List[int]]:
    cm: Dict[int, List[int]] = {}
    for pid, p in index.items():
        try:
            ppid = p.ppid()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        cm.setdefault(ppid, []).append(pid)
    for k in cm:
        cm[k].sort()
    return cm

def f_getroots(index: Dict[int, psutil.Process]) -> List[int]:
    rs = []
    for pid, p in index.items():
        try:
            ppid = p.ppid()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            ppid = -1
        if ppid not in index:
            rs.append(pid)
    return sorted(rs)

def f_label2k10(p: psutil.Process) -> str:
    try:
        name = p.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass   
    name = f'<font color="#c53335">{name}</font>&nbsp;<font size=-2 color="#666666">[{p.pid}]</font>'
    try:
        exe = p.exe()
        if exe:
            name = f'{name}\n<font size=-1 color="#0099e7">{exe}</font>'
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    return name



def f_walk(index, cmap, roots_list, mdepth, mnode):
    """Return nodes and edges for the filtered tree."""
    nodes: Set[int] = set()
    edges: List[Tuple[int, int]] = []
    seen: Set[int] = set()
    stack: List[Tuple[int, int, Optional[int]]] = [(r, 0, None) for r in roots_list]

    while stack and len(nodes) < mnode:
        pid, depth, parent = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        p = index.get(pid)
        if not p:
            continue
        nodes.add(pid)
        if parent is not None and parent in nodes:
            edges.append((parent, pid))
        if depth >= mdepth:
            continue
        for cpid in reversed(cmap.get(pid, [])):
            if cpid in index:
                stack.append((cpid, depth + 1, pid))
        if len(nodes) >= mnode:
            break
    return nodes, edges

def f_dohtml(index, nodes: Set[int], cmap: Dict[int, List[int]], roots_list: List[int]) -> str:
    kept_children           = {pid: [c for c in cmap.get(pid, []) if c in nodes] for pid in nodes}
    kept_roots              = [r for r in roots_list if r in nodes]

    def label(pid: int) -> str:
        p                   = index.get(pid)
        if not p: 
            return f"[{pid}]"
        s                   = f_label2k10(p).replace("\\n", " — ")
        return s

    def render(pid: int) -> str:
        kids                = kept_children.get(pid, [])
        if not kids:
            return f'<li><span class="leaf">{label(pid)}</span></li>'
        inner               = "\n".join(render(c) for c in kids)
        return f'<li><details open><summary>{label(pid)}</summary><ul>\n{inner}\n</ul></details></li>'

    body                    = "\n".join(render(r) for r in kept_roots)
    return f"""<!doctype html>
        <html>
            <head>
                <meta charset="utf-8"/>
                <title>Windows Process Tree</title>
                <style>
                     body {{ font-family: Consolas, monospace; }}
                     ul {{ list-style-type: none; padding-left: 1rem; }}
                     summary {{ cursor: pointer; }}
                     .leaf {{ margin-left: 0.2rem; }}
                </style>
            </head>
            <body>
            <h2>MS Windows processes</h2>
                <ul>
                    {body}
                </ul>
            </body>
        </html>
    """


def main():
    ap                  = argparse.ArgumentParser(description="Export MS Windows process tree to HTML")
    ap.add_argument("-o","--output", default="pyproc.html", help="Name of the html file")
    ap.add_argument("--depth", type=int, default=30, help="Max depth")
    ap.add_argument("--node", type=int, default=96000, help="Max nodes")
    args                = ap.parse_args()
    index               = f_getprocesses()
    cmap                = f_mapchild(index)
    rts                 = f_getroots(index)
    kept_nodes, edges   = f_walk(index, cmap, rts, args.depth, args.node)
    out                 = str(args.output) 
    html_text           = f_dohtml(index, kept_nodes, cmap, rts)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_text)
    print(f"\nWrote HTML: {out}")

if __name__ == "__main__":
    main()
