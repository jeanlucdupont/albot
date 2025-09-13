'''
   everything.exe (https://www.voidtools.com/) but rewritten in python.
   (displaying icons makes super and crash. working on this 20250913)
'''

import os
import sys
import time
import threading
import queue
import sqlite3
import fnmatch
import re
import ctypes
from ctypes import wintypes as wt
from PIL import Image, ImageTk
from datetime import datetime
import ctypes
from ctypes import wintypes as wt
from PIL import Image, ImageTk
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_NAME = "PyEverything"
DB_DIR = Path(os.getenv("LOCALAPPDATA") or Path.home() / ".local") / APP_NAME
DB_PATH = DB_DIR / "index.db"

DEFAULT_ROOTS = [str(Path.home())]  # change/add more roots if you want
RESULT_LIMIT = 5000                 # safety cap for UI
SEARCH_DEBOUNCE_MS = 120            # feel free to tweak
ENABLE_ICONS = True

# --- Win32 bits
SHGFI_ICON              = 0x000000100
SHGFI_USEFILEATTRIBUTES = 0x000000010
SHGFI_SMALLICON         = 0x000000001
FILE_ATTRIBUTE_NORMAL   = 0x80
DI_NORMAL               = 0x0003
BI_RGB                  = 0



class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon",      wt.BOOL),
        ("xHotspot",   wt.DWORD),
        ("yHotspot",   wt.DWORD),
        ("hbmMask",    wt.HANDLE),  # HBITMAP
        ("hbmColor",   wt.HANDLE),  # HBITMAP
    ]

class SHFILEINFO(ctypes.Structure):
    _fields_ = [
        ("hIcon",         wt.HICON),
        ("iIcon",         ctypes.c_int),
        ("dwAttributes",  wt.DWORD),
        ("szDisplayName", wt.WCHAR * 260),
        ("szTypeName",    wt.WCHAR * 80),
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize",          wt.DWORD),
        ("biWidth",         ctypes.c_long),
        ("biHeight",        ctypes.c_long),
        ("biPlanes",        wt.WORD),
        ("biBitCount",      wt.WORD),
        ("biCompression",   wt.DWORD),
        ("biSizeImage",     wt.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed",       wt.DWORD),
        ("biClrImportant",  wt.DWORD),
    ]
    
    
class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER)]    

# --- DLLs
user32  = ctypes.windll.user32
gdi32   = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent TEXT NOT NULL,
    size INTEGER,
    mtime REAL
);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(name);
CREATE INDEX IF NOT EXISTS idx_files_parent ON files(parent);
"""


def _hicon_to_pil(hicon, size=16):
    # Defensive: verify handle looks valid
    if not hicon:
        return None

    # Prepare a top-down 32-bpp DIB
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize        = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth       = size
    bmi.bmiHeader.biHeight      = -size  # top-down
    bmi.bmiHeader.biPlanes      = 1
    bmi.bmiHeader.biBitCount    = 32
    bmi.bmiHeader.biCompression = BI_RGB

    hdc = user32.GetDC(None)
    if not hdc:
        return None

    ppvBits = ctypes.c_void_p()
    hbitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(ppvBits), None, 0)
    if not hbitmap:
        user32.ReleaseDC(None, hdc)
        return None

    mdc = gdi32.CreateCompatibleDC(hdc)
    old = gdi32.SelectObject(mdc, hbitmap)

    try:
        # Draw the icon into the DIB
        user32.DrawIconEx(mdc, 0, 0, hicon, size, size, 0, None, DI_NORMAL)

        # Copy raw BGRA bytes
        buf_len = size * size * 4
        buf = (ctypes.c_ubyte * buf_len).from_address(ppvBits.value)
        data = bytes(buf)
    finally:
        # Cleanup GDI no matter what
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(None, hdc)
        gdi32.DeleteObject(hbitmap)
        user32.DestroyIcon(hicon)  # free the icon handle we received

    # Convert BGRA -> RGBA for PIL
    return Image.frombuffer("RGBA", (size, size), data, "raw", "BGRA", 0, 1)


_icon_cache = {}  # (path.lower(), size) -> Tk PhotoImage

def file_icon_photoimage(path, size=16):
    if not ENABLE_ICONS:
        return None
    key = (path.lower(), size)
    if key in _icon_cache:
        return _icon_cache[key]

    # Ask Windows for the associated icon by attributes (doesn't open the file)
    sfi = SHFILEINFO()
    flags = SHGFI_ICON | SHGFI_USEFILEATTRIBUTES | SHGFI_SMALLICON
    ok = shell32.SHGetFileInfoW(path, FILE_ATTRIBUTE_NORMAL,
                                ctypes.byref(sfi), ctypes.sizeof(sfi), flags)
    if not ok or not sfi.hIcon:
        return None

    pil_img = _hicon_to_pil(sfi.hIcon, size=size)
    if pil_img is None:
        return None

    tk_img = ImageTk.PhotoImage(pil_img)
    _icon_cache[key] = tk_img
    return tk_img


_icon_cache = {}  # (path.lower(), size) -> PhotoImage (kept alive)

def file_icon_photoimage(path, size=16):
    """Return a Tk PhotoImage for the file/folder icon (cached)."""
    key = (path.lower(), size)
    if key in _icon_cache:
        return _icon_cache[key]

    sfi = SHFILEINFO()
    flags = SHGFI_ICON | SHGFI_USEFILEATTRIBUTES | SHGFI_SMALLICON
    # We ask by attributes to avoid touching the actual file
    if not shell32.SHGetFileInfoW(path, FILE_ATTRIBUTE_NORMAL,
                                  ctypes.byref(sfi), ctypes.sizeof(sfi), flags):
        return None
    if not sfi.hIcon:
        return None

    pil_img = _hicon_to_pil(sfi.hIcon, size=size)
    if pil_img is None:
        return None
    tk_img = ImageTk.PhotoImage(pil_img)
    _icon_cache[key] = tk_img
    return tk_img

def treeview_sort_column(tree, col, reverse, is_numeric=False):
    """Sort Treeview by given column. If is_numeric, sort as int."""
    data = [
        (tree.set(k, col), k) 
        for k in tree.get_children("")
    ]
    if is_numeric:
        # Convert text to int safely (strip commas, KB, etc.)
        data = [(int(v.split()[0].replace(",", "")), k) for v, k in data]

    # Sort data
    data.sort(reverse=reverse)

    # Reorder rows in tree
    for idx, (val, k) in enumerate(data):
        tree.move(k, "", idx)

    # Toggle sort on next click
    tree.heading(col, command=lambda: treeview_sort_column(tree, col, not reverse, is_numeric=is_numeric))

def human_size(n):
    """Return size in KB with commas as thousand separators."""
    try:
        n = int(n)
    except Exception:
        return ""
    kb = max(1, n // 1024)  # round down to KB, but never 0
    return f"{kb:,} KB"

def init_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=MEMORY")
    for stmt in filter(None, SCHEMA.split(";")):
        con.execute(stmt)
    con.commit()
    return con

def scan_roots(roots, progress_cb=None, stop_flag=None):
    """Walk roots and (up)sert into DB. Runs in worker thread."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    total = 0
    t0 = time.time()
    for root in roots:
        root = os.path.abspath(root)
        for dirpath, dirnames, filenames in os.walk(root):
            if stop_flag and stop_flag.is_set():
                con.commit()
                con.close()
                return
            parent = dirpath
            rows = []
            # files
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                try:
                    st = os.stat(p, follow_symlinks=False)
                    rows.append((
                        p,
                        fn.lower(),
                        parent.lower(),
                        st.st_size,
                        st.st_mtime
                    ))
                except Exception:
                    continue
            # folders themselves (optional: include to find folders by name)
            for dn in dirnames:
                p = os.path.join(dirpath, dn)
                try:
                    st = os.stat(p, follow_symlinks=False)
                    rows.append((
                        p,
                        dn.lower(),
                        parent.lower(),
                        st.st_size if hasattr(st, "st_size") else 0,
                        st.st_mtime
                    ))
                except Exception:
                    continue

            if rows:
                cur.executemany("""
                INSERT INTO files(path, name, parent, size, mtime)
                VALUES(?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET
                    name=excluded.name,
                    parent=excluded.parent,
                    size=excluded.size,
                    mtime=excluded.mtime
                """, rows)
                total += len(rows)

            if total % 5000 == 0:
                con.commit()
                if progress_cb:
                    progress_cb(total)

    con.commit()
    con.close()
    if progress_cb:
        dt = time.time() - t0
        progress_cb(total, done=True, seconds=dt)

def wildcard_to_regex(pattern):
    # Convert * and ? to regex; allow plain substring if no wildcard
    if not pattern:
        return None
    # If user typed /regex/... allow true regex
    if len(pattern) >= 2 and pattern.startswith("/") and pattern.endswith("/"):
        try:
            return re.compile(pattern[1:-1], re.IGNORECASE)
        except re.error:
            return None
    # Else turn glob into regex
    rx = fnmatch.translate(pattern)
    return re.compile(rx, re.IGNORECASE)

def fmt_mtime(v):
    """Accept float epoch, int, ISO string, or None -> 'YYYY-MM-DD HH:MM'."""
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v).isoformat(timespec="minutes").replace("T", " ")
        except Exception:
            return ""
    # assume string
    s = str(v)
    # tolerate '2025-09-12T21:01:55.123' or '...Z'
    s = s.replace("T", " ").replace("Z", "")
    return s[:16]

def query_db(pattern, in_path=False, limit=RESULT_LIMIT, parent_filter=None):
    """Search by wildcard/regex. SQLite used for coarse prefilter, Python for final match.
       Returns mtime in ISO 8601 format (e.g., 2025-09-12T21:15:30)."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Build coarse LIKE filter to avoid scanning entire table
    core = re.sub(r"[\*\?]", "", pattern).strip()
    like_token = f"%{core.lower()}%" if core else "%"
    base_sql = "SELECT path, name, parent, size, mtime FROM files"
    where = []
    params = []

    if parent_filter:
        where.append("parent LIKE ?")
        params.append(f"%{parent_filter.lower()}%")

    if in_path:
        where.append("path LIKE ?")
        params.append(like_token)
    else:
        where.append("name LIKE ?")
        params.append(like_token)

    sql = base_sql + " WHERE " + " AND ".join(where) + " LIMIT ?"
    params.append(limit * 4)  # fetch more for final regex filter

    cur.execute(sql, params)
    rows = cur.fetchall()
    con.close()

    rx = wildcard_to_regex(pattern)
    out = []
    for p, n, parent, size, mtime in rows:
        target = p if in_path else n
        if rx is None or rx.search(target):
            try:
                iso_mtime = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
            except Exception:
                iso_mtime = ""
            out.append((p, n, parent, size, iso_mtime))
            if len(out) >= limit:
                break
    return out
    
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} (Python)")
        self.geometry("1000x600")
        self.minsize(800, 400)

        self.search_var = tk.StringVar()
        self.in_path_var = tk.BooleanVar(value=False)
        self.parent_filter_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")
        self.roots = DEFAULT_ROOTS.copy()

        self._search_after = None
        self._work_q = queue.Queue()
        self._stop_index_flag = threading.Event()

        self._build_ui()
        self._ensure_db()
        self._bind_keys()

    def _build_ui(self):
        # Top frame: search
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Search:").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.search_var, width=40)
        entry.pack(side="left", padx=(4,8), fill="x", expand=True)
        entry.focus_set()

        ttk.Label(top, text=" In folder filter:").pack(side="left", padx=(12,2))
        ttk.Entry(top, textvariable=self.parent_filter_var, width=24).pack(side="left")

        ttk.Button(top, text="Reindex", command=self.reindex).pack(side="right")
        ttk.Button(top, text="Roots…", command=self.choose_roots).pack(side="right", padx=(0,6))


        cols = ("folder", "size", "modified", "fullpath")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", height=20)
        self.tree.heading("#0", text="Name")
        self.tree.column("#0", width=280)

        self.tree.heading("fullpath", text="Full Path")
        self.tree.column("fullpath", width=0, stretch=False)  # hide but keep data

        self.tree.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.tree.heading("folder", text="Path", command=lambda: treeview_sort_column(self.tree, "folder", False, is_numeric=False))
        self.tree.column("folder", width=320)
        
        self.tree.heading("size", text="Size", command=lambda: treeview_sort_column(self.tree, "size", False, is_numeric=True))
        self.tree.column("size", width=90, anchor="e")
        
        self.tree.heading("modified", text="Date Modified", command=lambda: treeview_sort_column(self.tree, "modified", False, is_numeric=False))
        self.tree.column("modified", width=160, anchor="e")
        
        # keep icon refs alive
        self._row_icons = {}



        # Status bar
        status = ttk.Frame(self)
        status.pack(fill="x", padx=8, pady=(0,8))
        self.progress = ttk.Progressbar(status, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(status, textvariable=self.status_var).pack(side="right")

        # Bind events
        self.search_var.trace_add("write", lambda *_: self._on_search_changed())
        self.in_path_var.trace_add("write", lambda *_: self._on_search_changed())
        self.parent_filter_var.trace_add("write", lambda *_: self._on_search_changed())
        self.tree.bind("<Return>", self._open_selected)
        self.tree.bind("<Double-1>", self._open_selected)



    def _bind_keys(self):
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Escape>", lambda e: self._clear_search())

    def _focus_search(self):
        for child in self.children.values():
            if isinstance(child, ttk.Frame):
                for w in child.winfo_children():
                    if isinstance(w, ttk.Entry):
                        w.focus_set()
                        return

    def _clear_search(self):
        self.search_var.set("")
        self.parent_filter_var.set("")

    def _ensure_db(self):
        init_db()
        # If DB is empty, prompt to index
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("SELECT COUNT(1) FROM files")
        n = cur.fetchone()[0]
        con.close()
        if n == 0:
            self.after(500, self.reindex)

    def choose_roots(self):
        roots = []
        messagebox.showinfo(APP_NAME, "Pick one or more folders. Click Cancel when done.")
        while True:
            folder = filedialog.askdirectory(title="Choose root folder to index")
            if not folder:
                break
            if folder and folder not in roots:
                roots.append(folder)
                if len(roots) >= 16:
                    break
        if roots:
            self.roots = roots
            self.status_var.set(f"Roots set: {', '.join(self.roots)}")
            self.reindex()

    def reindex(self):
        if hasattr(self, "_index_thread") and self._index_thread.is_alive():
            if messagebox.askyesno(APP_NAME, "Index is running. Stop and restart?"):
                self._stop_index_flag.set()
            else:
                return

        self._stop_index_flag.clear()
        self.progress.configure(mode="indeterminate")
        self.progress.start(50)
        self.status_var.set("Indexing…")
        self._index_thread = threading.Thread(
            target=scan_roots,
            args=(self.roots, self._on_progress,),
            kwargs={"stop_flag": self._stop_index_flag},
            daemon=True
        )
        self._index_thread.start()

    def _on_progress(self, count, done=False, seconds=None):
        if done:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0, maximum=100)
            msg = f"Indexed {count:,} entries"
            if seconds is not None and seconds > 0:
                msg += f" in {seconds:.1f}s"
            self.status_var.set(msg)
            # auto-run search to refresh results
            self._search_now()
        else:
            self.status_var.set(f"Indexed {count:,} entries…")

    def _on_search_changed(self):
        if self._search_after:
            self.after_cancel(self._search_after)
        self._search_after = self.after(SEARCH_DEBOUNCE_MS, self._search_now)

    def _search_now(self):
        pat = self.search_var.get().strip()
        in_path = self.in_path_var.get()
        parent_f = self.parent_filter_var.get().strip()
        self.status_var.set("Searching…")
        self.tree.delete(*self.tree.get_children())

        def worker():
            try:
                rows = query_db(pat if pat else "%", in_path=in_path,
                                limit=RESULT_LIMIT,
                                parent_filter=parent_f if parent_f else None)
            except Exception as e:
                rows = []
                err = str(e)
                self.after(0, lambda: messagebox.showerror(APP_NAME, f"Query error:\n{err}"))
            self._work_q.put(rows)

        threading.Thread(target=worker, daemon=True).start()
        self.after(30, self._poll_results)

    def _poll_results(self):
        try:
            rows = self._work_q.get_nowait()
        except queue.Empty:
            self.after(30, self._poll_results)
            return

        for p, n, parent, size, iso_m in rows:
            mtime_disp = fmt_mtime(iso_m)
            icon = None
            try:
                icon = file_icon_photoimage(p, size=16)
            except Exception:
                icon = None
            if icon:
                self._row_icons[p] = icon

            display_name = os.path.basename(p)

            insert_kwargs = {"text": display_name}
            icon_obj = self._row_icons.get(p)
            if icon_obj is not None:  # ← only pass image if real
                insert_kwargs["image"] = icon_obj

            self.tree.insert(
                "", "end",
                values=(parent, human_size(size), mtime_disp, p),
                **insert_kwargs
            )

    def _open_selected(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if not vals or len(vals) < 4:
            return
        fullpath = vals[3]  # not [4]
        try:
            os.startfile(fullpath)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Failed to open:\n{fullpath}\n\n{e}")

if __name__ == "__main__":
    def _excepthook(exc_type, exc, tb):
        import traceback
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            # Show a dialog if Tk is up; fall back to stderr
            messagebox.showerror(APP_NAME, msg)
        except Exception:
            sys.stderr.write(msg)
    sys.excepthook = _excepthook
    try:
        App().mainloop()
    except KeyboardInterrupt:
        pass
