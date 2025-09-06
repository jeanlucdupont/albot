#!/usr/bin/env python3

"""
It is BOUNCY!

"""

import argparse
import math
import re
import numpy as np
import random
import textwrap
import matplotlib.pyplot as plt
from matplotlib import animation

#m               = 0.5
g               = 9.81
drag            = 0.4
k_ground        = 7000.0
c_ground        = 55.0
mu_ground       = 0.6
dt              = 0.0025
y0              = 2.0
T               = 10.0
sample_every    = 20
SHAPE           = "square"
GROUND          = "flat"       
OBSTACLES       = ""        

def make_square(israndom=False):
    s = 1.0
    if israndom:
        X = np.array([[-s/2,  y0 + random.uniform(0, s)],
                      [ s/2,  y0 + random.uniform(0, s)],
                      [ s/2,  y0 - random.uniform(0, s)],
                      [-s/2,  y0 - random.uniform(0, s)]], dtype=float)        
    else:
        X = np.array([[-s/2,  y0 + s/2],
                      [ s/2,  y0 + s/2],
                      [ s/2,  y0 - s/2],
                      [-s/2,  y0 - s/2]], dtype=float)
    edges = [(0,1),(1,2),(2,3),(3,0),(0,2),(1,3)]
    return X, edges

def make_diamond(israndom=False):
    s = 1.0
    if israndom:
        X = np.array([[ 0.0, y0 + random.uniform(0, s)],
                      [ random.uniform(0, s),   y0     ],
                      [ 0.0, y0 - random.uniform(0, s)],
                      [-random.uniform(0, s),   y0     ]], dtype=float)
    else:
        X = np.array([[ 0.0, y0 + s],
                      [ s,   y0     ],
                      [ 0.0, y0 - s],
                      [-s,   y0     ]], dtype=float)
    edges = [(0,1),(1,2),(2,3),(3,0),(0,2),(1,3)]
    return X, edges

def make_rectangle(w=1.6, h=1.0, israndom=False):
    if israndom:
        X = np.array([[-w/2,  y0 + random.uniform(0, h)],
                      [ w/2,  y0 + random.uniform(0, h)],
                      [ w/2,  y0 - random.uniform(0, h)],
                      [-w/2,  y0 - random.uniform(0, h)]], dtype=float)      
    else:
        X = np.array([[-w/2,  y0 + h/2],
                      [ w/2,  y0 + h/2],
                      [ w/2,  y0 - h/2],
                      [-w/2,  y0 - h/2]], dtype=float)
    edges = [(0,1),(1,2),(2,3),(3,0),(0,2),(1,3)]
    return X, edges

def make_polygon(n=6, R=1.0):
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    X = np.c_[R*np.cos(angles), R*np.sin(angles)+y0].astype(float)
    edges = []
    for i in range(n):
        edges.append((i, (i+1) % n))
    if n >= 5:
        for i in range(n):
            edges.append((i, (i+2) % n))
    return X, edges

def make_grid(rows=4, cols=4, spacing=0.7):
    X = []
    for i in range(rows):
        for j in range(cols):
            X.append([j*spacing - (cols-1)*spacing/2, y0 + (rows-1-i)*spacing])
    X = np.array(X, dtype=float)
    edges = []
    def idx(i,j): return i*cols + j
    for i in range(rows):
        for j in range(cols):
            p = idx(i,j)
            if j < cols-1:
                edges.append((p, idx(i, j+1)))
            if i < rows-1:
                edges.append((p, idx(i+1, j)))
            if i < rows-1 and j < cols-1:
                edges.append((p, idx(i+1, j+1)))
                edges.append((idx(i, j+1), idx(i+1, j)))
    return X, edges

def parse_shape(spec, israndom):
    s = spec.strip().lower()
    if s == "square":
        return make_square(israndom)
    if s == "diamond":
        return make_diamond(israndom)

    m = re.match(r"rectangle\(\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
    if m:
        return make_rectangle(float(m.group(1)), float(m.group(2)), israndom)

    m = re.match(r"polygon\(\s*([0-9]+)\s*(?:,\s*([\-0-9]*\.?[0-9]+))?\s*\)", s)
    if m:
        n = max(3, int(m.group(1)))
        R = float(m.group(2)) if m.group(2) else 1.0
        return make_polygon(n, R)

    m = re.match(r"grid\(\s*([0-9]+)\s*,\s*([0-9]+)\s*(?:,\s*([\-0-9]*\.?[0-9]+))?\s*\)", s)
    if m:
        rows = max(2, int(m.group(1)))
        cols = max(2, int(m.group(2)))
        spacing = float(m.group(3)) if m.group(3) else 0.7
        return make_grid(rows, cols, spacing)

    return make_square()

def parse_ground(spec):
    s = spec.strip().lower()
    if s in ("none", "no", "off"):
        return []
    if s == "flat":
        return [{"type": "line", "a": 0.0, "b": 0.0}]
    m = re.match(r"slanted\(\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
    if m:
        theta = float(m.group(1)); b = float(m.group(2))
        a = math.tan(math.radians(theta))
        return [{"type": "line", "a": a, "b": b}]
    m = re.match(r"line\(\s*a\s*=\s*([\-0-9]*\.?[0-9]+)\s*,\s*b\s*=\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
    if m:
        a = float(m.group(1)); b = float(m.group(2))
        return [{"type": "line", "a": a, "b": b}]
    print(f"[warn] Unrecognized ground '{spec}', using flat.")
    return [{"type": "line", "a": 0.0, "b": 0.0}]

def parse_obstacles(spec):
    items = []
    if not spec or not spec.strip():
        return items
    for raw in spec.split(";"):
        s = raw.strip().lower()
        if not s:
            continue
        if s == "flat":
            items.append({"type": "line", "a": 0.0, "b": 0.0}); continue
        m = re.match(r"slanted\(\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
        if m:
            theta = float(m.group(1)); b = float(m.group(2))
            a = math.tan(math.radians(theta))
            items.append({"type": "line", "a": a, "b": b}); continue
        m = re.match(r"line\(\s*a\s*=\s*([\-0-9]*\.?[0-9]+)\s*,\s*b\s*=\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
        if m:
            a = float(m.group(1)); b = float(m.group(2))
            items.append({"type": "line", "a": a, "b": b}); continue
        m = re.match(r"segment\(\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
        if m:
            x0,y0,x1,y1 = map(float, m.groups())
            items.append({"type": "segment", "p0": np.array([x0,y0]), "p1": np.array([x1,y1])}); continue
        m = re.match(r"circle\(\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
        if m:
            cx,cy,R = map(float, m.groups())
            items.append({"type": "circle", "c": np.array([cx,cy]), "R": R}); continue
        m = re.match(r"steps\(\s*([0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*,\s*([\-0-9]*\.?[0-9]+)\s*\)", s)
        if m:
            n, rise, run, x0, y0s = m.groups()
            n = int(n); rise = float(rise); run = float(run); x0 = float(x0); y0s = float(y0s)
            segs = []
            # Build axis-aligned steps: horizontal tread then vertical riser
            curx, cury = x0, y0s
            for k in range(n):
                # tread: from (curx, cury) to (curx+run, cury)
                segs.append({"type": "segment", "p0": np.array([curx, cury]), "p1": np.array([curx+run, cury])})
                # riser: from (curx+run, cury) to (curx+run, cury+rise)
                segs.append({"type": "segment", "p0": np.array([curx+run, cury]), "p1": np.array([curx+run, cury+rise])})
                curx += run; cury += rise
            items.append({"type": "steps", "segs": segs}); continue
        print(f"[warn] Unrecognized obstacle '{s}' (skipped).")
    return items

def build_springs(X, edges):
    rest = []
    for i, j in edges:
        rest.append(np.linalg.norm(X[j]-X[i]))
    return np.array(rest, dtype=float)

def springforce_matrix(X, V, edges, rest, springforce, c_spring):
    F = np.zeros_like(X)
    eps = 1e-12
    for idx, (i, j) in enumerate(edges):
        xi, xj = X[i], X[j]
        vi, vj = V[i], V[j]
        d = xj - xi
        L = math.sqrt(d[0]*d[0] + d[1]*d[1]) + eps
        dirx, diry = d[0]/L, d[1]/L
        Fs = springforce * (L - rest[idx])
        vrelx, vrely = vj[0]-vi[0], vj[1]-vi[1]
        v_rel_along = vrelx*dirx + vrely*diry
        Fd = c_spring * v_rel_along
        Fx = (Fs + Fd) * dirx
        Fy = (Fs + Fd) * diry
        F[i,0] +=  Fx; F[i,1] +=  Fy
        F[j,0] += -Fx; F[j,1] += -Fy
    return F

def contact_line_infinite(xi, vi, a, b):
    denom = math.sqrt(1.0 + a*a)
    nx, ny = -a/denom, 1.0/denom
    c = b/denom
    d = nx*xi[0] + ny*xi[1] - c
    vn = nx*vi[0] + ny*vi[1]
    tx, ty = ny, -nx
    vt = tx*vi[0] + ty*vi[1]
    n = np.array([nx, ny]); t = np.array([tx, ty])
    return d, vn, vt, n, t

def contact_segment(xi, vi, p0, p1):
    seg = p1 - p0
    seg_len2 = float(seg[0]*seg[0] + seg[1]*seg[1]) + 1e-12
    t = ((xi[0]-p0[0])*seg[0] + (xi[1]-p0[1])*seg[1]) / seg_len2
    if t < 0.0 or t > 1.0:
        return None  
    cpt = p0 + t*seg
    tx, ty = seg / math.sqrt(seg_len2)
    nx, ny =  ty, -tx
    if ny < 0.0:
        nx, ny = -nx, -ny
    dvec = xi - cpt
    d = nx*dvec[0] + ny*dvec[1]
    vn = nx*vi[0] + ny*vi[1]
    vt = tx*vi[0] + ty*vi[1]
    n = np.array([nx, ny]); tvec = np.array([tx, ty])
    return d, vn, vt, n, tvec

def contact_circle(xi, vi, c, R):
    dx, dy = xi[0]-c[0], xi[1]-c[1]
    dist = math.sqrt(dx*dx + dy*dy) + 1e-12
    nx, ny = dx/dist, dy/dist  
    d = dist - R  
    vn = nx*vi[0] + ny*vi[1]
    tx, ty = ny, -nx
    vt = tx*vi[0] + ty*vi[1]
    n = np.array([nx, ny]); t = np.array([tx, ty])
    return d, vn, vt, n, t

def ground_forces_multi(X, V, primitives):
    F = np.zeros_like(X)
    eps = 1e-12
    for i in range(X.shape[0]):
        xi = X[i]; vi = V[i]
        total_F = np.array([0.0, 0.0])
        for prim in primitives:
            if prim["type"] == "line":
                d, vn, vt, n, t = contact_line_infinite(xi, vi, prim["a"], prim["b"])
            elif prim["type"] == "segment":
                out = contact_segment(xi, vi, prim["p0"], prim["p1"])
                if out is None:
                    continue
                d, vn, vt, n, t = out
            elif prim["type"] == "circle":
                d, vn, vt, n, t = contact_circle(xi, vi, prim["c"], prim["R"])
            elif prim["type"] == "steps":
                # expand into segments
                for seg in prim["segs"]:
                    out = contact_segment(xi, vi, seg["p0"], seg["p1"])
                    if out is None:
                        continue
                    d, vn, vt, n, t = out
                    if d < 0.0:
                        Fn = -k_ground * d - c_ground * min(vn, 0.0)
                        Ft = -mu_ground * Fn * (vt / (math.sqrt(vt*vt) + eps))
                        total_F += Fn*n + Ft*t
                continue
            else:
                continue

            if d < 0.0:
                Fn = -k_ground * d - c_ground * min(vn, 0.0)
                Ft = -mu_ground * Fn * (vt / (math.sqrt(vt*vt) + eps))
                total_F += Fn*n + Ft*t
        F[i] += total_F
    return F

def simulate(X, edges, primitives, springforce, stiffness, mass):
    V = np.zeros_like(X)
    rest = build_springs(X, edges)
    c_spring = stiffness * 2.0 * math.sqrt(springforce * (mass/2.0))
    n_steps = int(T / dt)
    frames = []
    for t in range(n_steps):
        F = np.zeros_like(X)
        F[:,1] -= mass * g
        F -= drag * V
        F += springforce_matrix(X, V, edges, rest, springforce, c_spring)
        F += ground_forces_multi(X, V, primitives)
        A = F / mass
        V += A * dt
        X += V * dt
        if t % sample_every == 0:
            frames.append(X.copy())
    return np.array(frames)

def draw_obstacles(ax, primitives, xmin, xmax, ymin, ymax):
    for prim in primitives:
        if prim["type"] == "line":
            a, b = prim["a"], prim["b"]
            xs = np.linspace(xmin-2, xmax+2, 200)
            ys = a*xs + b
            ax.plot(xs, ys, linewidth=2)
        elif prim["type"] == "segment":
            p0, p1 = prim["p0"], prim["p1"]
            ax.plot([p0[0], p1[0]], [p0[1], p1[1]], linewidth=2)
        elif prim["type"] == "steps":
            for seg in prim["segs"]:
                p0, p1 = seg["p0"], seg["p1"]
                ax.plot([p0[0], p1[0]], [p0[1], p1[1]], linewidth=2)
        elif prim["type"] == "circle":
            theta = np.linspace(0, 2*np.pi, 200)
            cx, cy = prim["c"]
            R = prim["R"]
            ax.plot(cx + R*np.cos(theta), cy + R*np.sin(theta), linewidth=2)


def animate_frames(frames, edges, primitives, title):
    fig, ax = plt.subplots(figsize=(6,6))
    ax.set_aspect('equal', adjustable='box')
    xmin = np.min(frames[:,:,0]) - 1.0; xmax = np.max(frames[:,:,0]) + 1.0
    ymin = np.min(frames[:,:,1]) - 1.0; ymax = np.max(frames[:,:,1]) + 1.0
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    ax.set_title(title)

    draw_obstacles(ax, primitives, xmin, xmax, ymin, ymax)

    pts = ax.scatter(frames[0,:,0], frames[0,:,1], s=60)
    spring_lines = []
    for (i,j) in edges:
        (line,) = ax.plot([frames[0,i,0], frames[0,j,0]],
                          [frames[0,i,1], frames[0,j,1]], linewidth=1.3)
        spring_lines.append(line)
    time_text = ax.text(0.02, 0.95, "t = 0.00 s", transform=ax.transAxes)

    def init():
        pts.set_offsets(frames[0])
        for line, (i,j) in zip(spring_lines, edges):
            line.set_data([frames[0,i,0], frames[0,j,0]],
                          [frames[0,i,1], frames[0,j,1]])
        time_text.set_text("t = 0.00 s")
        return [pts, *spring_lines, time_text]

    def update(f):
        X = frames[f]
        pts.set_offsets(X)
        for line, (i,j) in zip(spring_lines, edges):
            line.set_data([X[i,0], X[j,0]], [X[i,1], X[j,1]])
        time_text.set_text(f"t = {f*sample_every*dt:.2f} s")
        return [pts, *spring_lines, time_text]

    anim = animation.FuncAnimation(fig, update, init_func=init,
                                   frames=len(frames), interval=33, blit=True)
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="2D mass-spring with multiple obstacles")
    parser.add_argument("--shape", type=str, default=SHAPE,
                        help="square | diamond | rectangle(w,h) | polygon(n[,R]) | grid(rows,cols[,spacing])")
    parser.add_argument("--ground", type=str, default=GROUND,
                        help="none | flat | slanted(theta,b) | line(a=...,b=...)")
    parser.add_argument("--obstacles", type=str, default=OBSTACLES,
                        help="Semicolon-separated: flat | slanted(theta,b) | line(a=...,b=...) | segment(x0,y0,x1,y1) | steps(n,rise,run,x0,y0) | circle(cx,cy,R)")
    parser.add_argument("--random", type=bool, default=False, help="Distort square, diamond, rectangle")
    parser.add_argument("--springforce", type=float, default=800.0, help="Spring Force")
    parser.add_argument("--stiffness", type=float, default=0.18, help="The higher, the stiffer")
    parser.add_argument("--mass", type=float, default=0.5, help="Mass in kg")

  
    args = parser.parse_args()
    args_dict = vars(args)
    params = " ".join(f"{k}={v}" for k, v in args_dict.items() if v is not None)
    params = textwrap.wrap(params, width=len(params)//3 + 1)
    params = "\n".join(params)    

    X, edges = parse_shape(args.shape, args.random)
    primitives = []
    primitives += parse_ground(args.ground)
    primitives += parse_obstacles(args.obstacles)
    frames = simulate(X, edges, primitives, args.springforce, args.stiffness, args.mass)
    animate_frames(frames, edges, primitives, params)

if __name__ == "__main__":
    main()
