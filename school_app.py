"""برنامه اصلی «مدیریت هوشمند مدرسه سرچهان».

سرور داخلی و رابط کاربری را با هم اجرا می‌کند، پس روی هر سیستم فقط یک
برنامه لازم است. همین فایل ورودی ساخت فایل exe است.

اجرای آزمایشی بدون ساخت exe:   python school_app.py
بازنشانی رمز مدیر:             python school_app.py --reset-admin
"""
import os
import socket
import sqlite3
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

APP_NAME = "مدیریت هوشمند مدرسه سرچهان"
FROZEN = getattr(sys, "frozen", False)
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))

if not FROZEN:
    # در حالت آزمایشی، فایل سرور داخل پوشه‌ی school_server است
    sys.path.insert(0, os.path.join(BASE_DIR, "school_server"))
    sys.path.insert(0, BASE_DIR)


def data_dir():
    """پوشه‌ای که دیتابیس و تنظیمات در آن ذخیره می‌شود (قابل نوشتن برای همه)."""
    candidates = [os.environ.get("SCHOOL_DATA_DIR")]
    if os.environ.get("PROGRAMDATA"):
        candidates.append(os.path.join(os.environ["PROGRAMDATA"], "SarchahanSchool"))
    candidates.append(
        os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SarchahanSchool")
    )

    for path in candidates:
        if not path:
            continue
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".write_test")
            with open(probe, "w") as handle:
                handle.write("ok")
            os.remove(probe)
            return path
        except OSError:
            continue
    return BASE_DIR


def users_exist(db_path):
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def ask_new_password(parent):
    """از کاربر یک رمز (حداقل ۸ نویسه) می‌گیرد؛ با انصراف None برمی‌گرداند."""
    while True:
        first = simpledialog.askstring(
            APP_NAME, "یک رمز عبور برای حساب مدیر (admin) انتخاب کنید.\n(حداقل ۸ نویسه)",
            show="*", parent=parent
        )
        if first is None:
            return None
        if len(first) < 8:
            messagebox.showwarning(APP_NAME, "رمز عبور باید حداقل ۸ نویسه باشد.", parent=parent)
            continue

        again = simpledialog.askstring(APP_NAME, "رمز عبور را دوباره وارد کنید:",
                                       show="*", parent=parent)
        if again is None:
            return None
        if again != first:
            messagebox.showwarning(APP_NAME, "دو رمز یکسان نیستند. دوباره تلاش کنید.", parent=parent)
            continue
        return first


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(port):
    # این importها برای ساخت exe لازم‌اند (uvicorn آن‌ها را پویا بارگذاری می‌کند)
    import uvicorn
    import uvicorn.lifespan.off  # noqa: F401
    import uvicorn.loops.asyncio  # noqa: F401
    import uvicorn.protocols.http.h11_impl  # noqa: F401
    import main as school_server

    config = uvicorn.Config(
        school_server.app, host="127.0.0.1", port=port, log_config=None,
        loop="asyncio", http="h11", ws="none", lifespan="off",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 20
    while time.time() < deadline:
        if server.started:
            return server
        if not thread.is_alive():
            break
        time.sleep(0.1)
    raise RuntimeError("سرور داخلی برنامه اجرا نشد.")


def reset_admin_flow():
    root = tk.Tk()
    root.withdraw()
    try:
        if not messagebox.askyesno(
            APP_NAME, "رمز عبور حساب مدیر (admin) بازنشانی شود؟", parent=root
        ):
            return
        password = ask_new_password(root)
        if password is None:
            return

        import main as school_server
        school_server.set_admin_password(password)
        messagebox.showinfo(
            APP_NAME, "رمز تغییر کرد. با نام کاربری admin و رمز جدید وارد شوید.", parent=root
        )
    finally:
        root.destroy()


def main():
    folder = data_dir()
    db_path = os.path.join(folder, "school.db")
    os.environ["SCHOOL_DATA_DIR"] = folder
    os.environ["SCHOOL_DB_PATH"] = db_path

    if "--reset-admin" in sys.argv:
        reset_admin_flow()
        return

    # اولین اجرا: رمز مدیر را خود کاربر انتخاب می‌کند
    if not users_exist(db_path):
        root = tk.Tk()
        root.withdraw()
        password = ask_new_password(root)
        root.destroy()
        if password is None:
            return
        os.environ["SCHOOL_ADMIN_PASSWORD"] = password

    port = free_port()
    os.environ["SCHOOL_API_URL"] = "http://127.0.0.1:%d" % port

    try:
        server = start_server(port)
    except Exception as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, "اجرای برنامه ممکن نشد:\n%s" % error, parent=root)
        root.destroy()
        return

    try:
        import desktop_fixed  # noqa: F401  (رابط کاربری تا بسته شدن پنجره اجرا می‌شود)
    finally:
        server.should_exit = True
        time.sleep(0.3)


if __name__ == "__main__":
    main()
