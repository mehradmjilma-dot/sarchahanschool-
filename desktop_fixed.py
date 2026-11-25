import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import urllib.request
import urllib.error
import urllib.parse
import json
import re
import datetime
import os
import tempfile
import webbrowser
from pathlib import Path
from html import escape as esc

# -------------------------------
# تنظیمات اصلی
# -------------------------------

API_URL = os.environ.get("SCHOOL_API_URL", "http://127.0.0.1:8000")
BG = "#F1F5F9"
BLUE = "#1565C0"
APP_NAME = "مدیریت هوشمند مدرسه سرچهان"

window = tk.Tk()
window.title(APP_NAME)
window.configure(bg=BG)


def fit_window_to_screen():
    """اندازه‌ی پنجره را با صفحه‌نمایش (حتی کوچک) هماهنگ می‌کند."""
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    width = min(1150, screen_w - 40)
    height = min(750, screen_h - 90)          # جا برای نوار وظیفه ویندوز
    x = max((screen_w - width) // 2, 0)
    y = max((screen_h - height) // 2 - 15, 0)
    window.geometry("%dx%d+%d+%d" % (width, height, x, y))
    window.minsize(min(820, width), min(520, height))


fit_window_to_screen()

# وضعیت کاربر واردشده
auth = {"token": None, "role": None, "name": None, "username": None}

student_table = None
entry_first = None
entry_last = None
entry_code = None
entry_phone = None
search_entry = None


# -------------------------------
# ارتباط با سرور
# -------------------------------

def api_request(path, method="GET", data=None):
    url = API_URL + path
    headers = {"Content-Type": "application/json"}
    if auth["token"]:
        headers["Authorization"] = "Bearer " + auth["token"]

    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 401 and auth["token"]:
            window.after(0, force_logout)   # نشست منقضی شده
        raise


def error_text(error):
    """متن خطای قابل‌فهم از روی استثنا می‌سازد."""
    if isinstance(error, urllib.error.HTTPError):
        try:
            detail = json.loads(error.read().decode("utf-8"))
            return str(detail.get("detail") or detail.get("message") or error)
        except Exception:
            return "خطای سرور (%s)" % error.code
    if isinstance(error, urllib.error.URLError):
        return "ارتباط با سرور برقرار نشد.\nآدرس: %s\nعلت فنی: %s" % (API_URL, error.reason)
    return str(error)


# -------------------------------
# پاک کردن صفحه
# -------------------------------

def clear_content():
    for widget in content.winfo_children():
        widget.destroy()

    if "content_canvas" in globals():
        content_canvas.yview_moveto(0)


def clear_form():
    for entry in (entry_first, entry_last, entry_code, entry_phone):
        entry.delete(0, tk.END)


# -------------------------------
# داشبورد
# -------------------------------

def show_dashboard():
    clear_content()

    tk.Label(
        content, text="داشبورد مدیریت مدرسه",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=35)

    try:
        data = api_request("/students")
        count_text = str(len(data["students"]))
    except Exception:
        count_text = "عدم ارتباط با سرور"

    card = tk.Frame(content, bg="white", padx=40, pady=30)
    card.pack(pady=25)

    tk.Label(
        card, text="تعداد دانش‌آموزان ثبت‌شده",
        font=("Tahoma", 14), bg="white"
    ).pack(pady=10)

    tk.Label(
        card, text=count_text,
        font=("Tahoma", 30, "bold"), fg=BLUE, bg="white"
    ).pack(pady=10)

    tk.Label(
        content, text="%s عزیز، به سامانه %s خوش آمدید" % (auth["name"] or "", APP_NAME),
        font=("Tahoma", 13), bg=BG
    ).pack(pady=20)


# -------------------------------
# ثبت دانش‌آموز
# -------------------------------

def register_student():
    first = entry_first.get().strip()
    last = entry_last.get().strip()
    code = entry_code.get().strip()
    phone = entry_phone.get().strip()

    if not first or not last or not code:
        messagebox.showwarning(
            "خطا", "نام، نام خانوادگی و کد دانش‌آموزی الزامی است"
        )
        return

    student = {
        "first_name": first,
        "last_name": last,
        "student_code": code,
        "phone": phone,
    }

    try:
        result = api_request("/students", method="POST", data=student)
        messagebox.showinfo("موفقیت", result["message"])
        clear_form()
        load_students()

    except urllib.error.HTTPError as error:
        if error.code in (409, 500):
            messagebox.showerror("خطا", "این کد دانش‌آموزی قبلاً ثبت شده است.")
        else:
            messagebox.showerror("خطا", "خطا در ثبت اطلاعات: " + error_text(error))

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


# -------------------------------
# بارگذاری و جست‌وجوی دانش‌آموزان
# -------------------------------

def load_students(keyword=""):
    if student_table is None:
        return

    for item in student_table.get_children():
        student_table.delete(item)

    try:
        data = api_request("/students")
        keyword = keyword.strip()

        for student in data["students"]:
            first = str(student["first_name"])
            last = str(student["last_name"])
            code = str(student["student_code"])
            phone = str(student["phone"])

            full_name = first + " " + last

            if keyword == "" or keyword in full_name or keyword in code:
                student_table.insert(
                    "", tk.END, values=(first, last, code, phone)
                )

    except Exception as error:
        messagebox.showerror(
            "خطا", "خطا در دریافت فهرست دانش‌آموزان:\n" + error_text(error)
        )


# -------------------------------
# انتخاب دانش‌آموز از جدول
# -------------------------------

def select_student(event=None):
    if student_table is None:
        return

    selected = student_table.selection()
    if not selected:
        return

    # جدول فقط ۴ ستون دارد: اندیس ۰ تا ۳
    values = student_table.item(selected[0], "values")

    clear_form()
    entry_first.insert(0, values[0])
    entry_last.insert(0, values[1])
    entry_code.insert(0, values[2])
    entry_phone.insert(0, values[3])


# -------------------------------
# ویرایش دانش‌آموز
# -------------------------------

def update_student():
    code = entry_code.get().strip()

    if not code:
        messagebox.showwarning("خطا", "ابتدا یک دانش‌آموز را انتخاب کنید.")
        return

    student = {
        "first_name": entry_first.get().strip(),
        "last_name": entry_last.get().strip(),
        "student_code": code,
        "phone": entry_phone.get().strip(),
    }

    if not student["first_name"] or not student["last_name"]:
        messagebox.showwarning("خطا", "نام و نام خانوادگی را وارد کنید.")
        return

    try:
        result = api_request(
            "/students/" + urllib.parse.quote(code, safe=""),
            method="PUT", data=student
        )
        messagebox.showinfo("نتیجه", result["message"])
        load_students()

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


# -------------------------------
# حذف دانش‌آموز
# -------------------------------

def delete_student():
    code = entry_code.get().strip()

    if not code:
        messagebox.showwarning("خطا", "ابتدا یک دانش‌آموز را انتخاب کنید.")
        return

    if not messagebox.askyesno(
        "تأیید حذف", "آیا از حذف این دانش‌آموز مطمئن هستید؟"
    ):
        return

    try:
        result = api_request(
            "/students/" + urllib.parse.quote(code, safe=""),
            method="DELETE"
        )
        messagebox.showinfo("نتیجه", result["message"])
        clear_form()
        load_students()

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


# -------------------------------
# صفحه مدیریت دانش‌آموزان
# -------------------------------

def make_field(form, label, row):
    tk.Label(
        form, text=label, bg=BG, font=("Tahoma", 11)
    ).grid(row=row, column=0, padx=10, pady=7)

    entry = tk.Entry(form, font=("Tahoma", 11), width=25)
    entry.grid(row=row, column=1, padx=10, pady=7)
    return entry


def action_button(parent, text, command, color):
    tk.Button(
        parent, text=text, command=command,
        bg=color, fg="white", activeforeground="white",
        font=("Tahoma", 10, "bold"), width=15,
        relief="flat", cursor="hand2"
    ).pack(side="right", padx=5)


def show_students():
    global student_table, entry_first, entry_last
    global entry_code, entry_phone, search_entry

    clear_content()

    tk.Label(
        content, text="مدیریت دانش‌آموزان",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=15)

    # فرم اطلاعات دانش‌آموز
    form = tk.Frame(content, bg=BG)
    form.pack(pady=5)

    entry_first = make_field(form, "نام:", 0)
    entry_last = make_field(form, "نام خانوادگی:", 1)
    entry_code = make_field(form, "کد دانش‌آموزی:", 2)
    entry_phone = make_field(form, "شماره تلفن:", 3)

    # دکمه‌های عملیات
    buttons = tk.Frame(content, bg=BG)
    buttons.pack(pady=10)

    action_button(buttons, "ثبت دانش‌آموز", register_student, BLUE)
    action_button(buttons, "ویرایش اطلاعات", update_student, "#00897B")
    action_button(buttons, "حذف دانش‌آموز", delete_student, "#C62828")

    # بخش جست‌وجو
    search_frame = tk.Frame(content, bg=BG)
    search_frame.pack(pady=10)

    search_entry = tk.Entry(search_frame, font=("Tahoma", 11), width=25)
    search_entry.pack(side="right", padx=5)
    search_entry.bind("<Return>", lambda e: load_students(search_entry.get()))

    ttk.Button(
        search_frame, text="جست‌وجو",
        command=lambda: load_students(search_entry.get())
    ).pack(side="right", padx=5)

    ttk.Button(
        search_frame, text="نمایش همه",
        command=lambda: (search_entry.delete(0, tk.END), load_students())
    ).pack(side="right", padx=5)

    # جدول دانش‌آموزان
    columns = ("first", "last", "code", "phone")

    student_table = ttk.Treeview(
        content, columns=columns, show="headings", height=10
    )

    headings = {
        "first": ("نام", 130),
        "last": ("نام خانوادگی", 150),
        "code": ("کد دانش‌آموزی", 130),
        "phone": ("شماره تلفن", 150),
    }
    for key, (text, width) in headings.items():
        student_table.heading(key, text=text)
        student_table.column(key, width=width, anchor="center")

    student_table.pack(fill="both", expand=True, padx=20, pady=10)
    student_table.bind("<<TreeviewSelect>>", select_student)

    load_students()


# -------------------------------
# مدیریت صفحات
# -------------------------------

# -------------------------------
# تاریخ شمسی (بدون نیاز به کتابخانه)
# -------------------------------

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + g_d_m[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def today_jalali():
    now = datetime.date.today()
    return "%04d-%02d-%02d" % gregorian_to_jalali(now.year, now.month, now.day)


# -------------------------------
# صفحه حضور و غیاب
# -------------------------------

STATUS_LABELS = {
    "present": "حاضر",
    "absent": "غایب",
    "late": "تأخیر",
    "excused": "موجه",
}
STATUS_COLORS = {
    "present": "#E8F5E9",
    "absent": "#FFCDD2",
    "late": "#FFF9C4",
    "excused": "#E3F2FD",
}

att_classes = {}     # نام کلاس -> شناسه
att_students = []    # دانش‌آموزان کلاس انتخاب‌شده
att_status = {}      # کد دانش‌آموز -> وضعیت
att_loaded = {"class_id": None, "date": None}
att_table = None
att_class_box = None
att_date_entry = None
att_summary = None


def refresh_attendance_table():
    if att_table is None:
        return

    for item in att_table.get_children():
        att_table.delete(item)

    counts = dict.fromkeys(STATUS_LABELS, 0)

    for st in att_students:
        code = st["student_code"]
        status = att_status.get(code, "present")
        counts[status] += 1
        att_table.insert(
            "", tk.END, iid=code, tags=(status,),
            values=(
                st["first_name"] + " " + st["last_name"],
                code,
                STATUS_LABELS[status],
            )
        )

    att_summary.config(
        text=" | ".join(
            "%s: %d" % (STATUS_LABELS[k], counts[k]) for k in STATUS_LABELS
        )
    )


def load_attendance():
    name = att_class_box.get()
    date = att_date_entry.get().strip()

    if name not in att_classes:
        messagebox.showwarning("خطا", "ابتدا یک کلاس انتخاب کنید.")
        return

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        messagebox.showwarning("خطا", "تاریخ را به شکل 1405-08-28 وارد کنید.")
        return

    class_id = att_classes[name]

    try:
        students = api_request("/classes/%d/students" % class_id)["students"]
        query = urllib.parse.urlencode({"class_id": class_id, "date": date})
        saved = api_request("/attendance?" + query)["records"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    att_students.clear()
    att_students.extend(students)

    # پیش‌فرض همه حاضر؛ اگر قبلاً ثبت شده، همان وضعیت‌ها
    att_status.clear()
    for st in students:
        att_status[st["student_code"]] = "present"
    for record in saved:
        att_status[record["student_code"]] = record["status"]

    att_loaded["class_id"] = class_id
    att_loaded["date"] = date

    refresh_attendance_table()

    if not students:
        messagebox.showinfo("توجه", "این کلاس هنوز دانش‌آموزی ندارد.")


def set_attendance_status(status, everyone=False):
    if everyone:
        codes = [st["student_code"] for st in att_students]
    else:
        codes = list(att_table.selection())
        if not codes:
            messagebox.showwarning("خطا", "ابتدا یک یا چند دانش‌آموز را انتخاب کنید.")
            return

    for code in codes:
        att_status[code] = status

    refresh_attendance_table()


def save_attendance():
    if att_loaded["class_id"] is None or not att_students:
        messagebox.showwarning("خطا", "ابتدا لیست کلاس را بارگذاری کنید.")
        return

    payload = {
        "class_id": att_loaded["class_id"],
        "date": att_loaded["date"],
        "records": [
            {
                "student_code": st["student_code"],
                "status": att_status.get(st["student_code"], "present"),
            }
            for st in att_students
        ],
    }

    try:
        result = api_request("/attendance", method="POST", data=payload)
        messagebox.showinfo("موفقیت", result["message"])
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def show_attendance():
    global att_table, att_class_box, att_date_entry, att_summary

    clear_content()
    att_students.clear()
    att_status.clear()
    att_loaded["class_id"] = None
    att_loaded["date"] = None

    tk.Label(
        content, text="حضور و غیاب",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=15)

    # دریافت فهرست کلاس‌ها
    att_classes.clear()
    try:
        for c in api_request("/classes")["classes"]:
            att_classes[c["name"]] = c["id"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))

    # انتخاب کلاس و تاریخ
    top = tk.Frame(content, bg=BG)
    top.pack(pady=5)

    tk.Label(top, text="کلاس:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=5)
    att_class_box = ttk.Combobox(
        top, values=list(att_classes), state="readonly",
        font=("Tahoma", 11), width=18
    )
    att_class_box.pack(side="right", padx=5)

    tk.Label(top, text="تاریخ:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=5)
    att_date_entry = tk.Entry(top, font=("Tahoma", 11), width=12, justify="center")
    att_date_entry.insert(0, today_jalali())
    att_date_entry.pack(side="right", padx=5)

    action_button(top, "بارگذاری لیست", load_attendance, BLUE)

    if not att_classes:
        tk.Label(
            content,
            text="هنوز کلاسی برای شما تعریف نشده است. مدیر باید کلاس را بسازد و دبیر را به آن اختصاص دهد.",
            font=("Tahoma", 11), bg=BG, fg="#C62828"
        ).pack(pady=5)

    # دکمه‌های تعیین وضعیت
    status_bar = tk.Frame(content, bg=BG)
    status_bar.pack(pady=10)

    for key, color in (("excused", "#1976D2"), ("late", "#F9A825"),
                       ("absent", "#C62828"), ("present", "#2E7D32")):
        tk.Button(
            status_bar, text=STATUS_LABELS[key],
            command=lambda k=key: set_attendance_status(k),
            bg=color, fg="white", activeforeground="white",
            font=("Tahoma", 10, "bold"), width=10,
            relief="flat", cursor="hand2"
        ).pack(side="right", padx=4)

    tk.Button(
        status_bar, text="همه حاضر",
        command=lambda: set_attendance_status("present", everyone=True),
        font=("Tahoma", 10), relief="groove", cursor="hand2"
    ).pack(side="right", padx=14)

    # جدول
    att_table = ttk.Treeview(
        content, columns=("name", "code", "status"),
        show="headings", height=12, selectmode="extended"
    )
    for key, text, width in (("name", "نام و نام خانوادگی", 220),
                             ("code", "کد دانش‌آموزی", 130),
                             ("status", "وضعیت", 100)):
        att_table.heading(key, text=text)
        att_table.column(key, width=width, anchor="center")

    for status, color in STATUS_COLORS.items():
        att_table.tag_configure(status, background=color)

    att_table.pack(fill="both", expand=True, padx=20, pady=5)

    att_summary = tk.Label(content, text="", bg=BG, font=("Tahoma", 11))
    att_summary.pack(pady=5)

    save_frame = tk.Frame(content, bg=BG)
    save_frame.pack(pady=10)
    action_button(save_frame, "ثبت حضور و غیاب", save_attendance, "#00897B")


# -------------------------------
# صفحه کلاس‌ها
# -------------------------------

cls_table = None
cls_members = None
cls_name = None
cls_grade = None
cls_teacher = None
cls_student_box = None
cls_teachers = {}       # متن نمایشی دبیر -> شناسه
cls_all_students = {}   # متن نمایشی دانش‌آموز -> کد


def selected_class_id():
    if cls_table is None:
        return None
    selected = cls_table.selection()
    return int(selected[0]) if selected else None


def load_classes(keep_selection=True):
    previous = selected_class_id() if keep_selection else None

    for item in cls_table.get_children():
        cls_table.delete(item)

    try:
        classes = api_request("/classes")["classes"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    for c in classes:
        cls_table.insert(
            "", tk.END, iid=str(c["id"]),
            values=(
                c["name"],
                c["grade"] or "-",
                c["teacher_name"] or "-",
                c["student_count"],
            )
        )

    if previous is not None and cls_table.exists(str(previous)):
        cls_table.selection_set(str(previous))
    else:
        load_class_members()


def load_class_members(event=None):
    for item in cls_members.get_children():
        cls_members.delete(item)

    class_id = selected_class_id()
    if class_id is None:
        return

    try:
        students = api_request("/classes/%d/students" % class_id)["students"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    for st in students:
        cls_members.insert(
            "", tk.END, iid=st["student_code"],
            values=(
                st["first_name"] + " " + st["last_name"],
                st["student_code"],
                st["phone"],
            )
        )


def create_class_action():
    name = cls_name.get().strip()

    if not name:
        messagebox.showwarning("خطا", "نام کلاس الزامی است.")
        return

    data = {
        "name": name,
        "grade": cls_grade.get().strip(),
        "teacher_id": cls_teachers.get(cls_teacher.get()),
    }

    try:
        result = api_request("/classes", method="POST", data=data)
        messagebox.showinfo("موفقیت", result["message"])
        cls_name.delete(0, tk.END)
        cls_grade.delete(0, tk.END)
        cls_teacher.set("")
        load_classes()

    except urllib.error.HTTPError as error:
        if error.code == 409:
            messagebox.showerror("خطا", "کلاسی با این نام قبلاً ساخته شده است.")
        else:
            messagebox.showerror("خطا", error_text(error))

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def delete_class_action():
    class_id = selected_class_id()

    if class_id is None:
        messagebox.showwarning("خطا", "ابتدا یک کلاس را انتخاب کنید.")
        return

    if not messagebox.askyesno(
        "تأیید حذف",
        "با حذف کلاس، حضور و غیاب ثبت‌شده‌ی آن هم پاک می‌شود. ادامه می‌دهید؟"
    ):
        return

    try:
        result = api_request("/classes/%d" % class_id, method="DELETE")
        messagebox.showinfo("نتیجه", result["message"])
        load_classes(keep_selection=False)
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def add_member_action():
    class_id = selected_class_id()

    if class_id is None:
        messagebox.showwarning("خطا", "ابتدا یک کلاس را انتخاب کنید.")
        return

    code = cls_all_students.get(cls_student_box.get())
    if code is None:
        messagebox.showwarning("خطا", "یک دانش‌آموز از فهرست انتخاب کنید.")
        return

    try:
        api_request(
            "/classes/%d/students/%s" % (class_id, urllib.parse.quote(code, safe="")),
            method="POST"
        )
        cls_student_box.set("")
        load_classes()
        load_class_members()

    except urllib.error.HTTPError as error:
        if error.code == 409:
            messagebox.showinfo("توجه", "این دانش‌آموز قبلاً عضو این کلاس است.")
        else:
            messagebox.showerror("خطا", error_text(error))

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def remove_member_action():
    class_id = selected_class_id()
    selected = cls_members.selection()

    if class_id is None or not selected:
        messagebox.showwarning("خطا", "یک دانش‌آموز از جدول پایین انتخاب کنید.")
        return

    try:
        for code in selected:
            api_request(
                "/classes/%d/students/%s" % (class_id, urllib.parse.quote(code, safe="")),
                method="DELETE"
            )
        load_classes()
        load_class_members()
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def make_table(parent, columns, height):
    """columns: لیست (کلید، عنوان، عرض)"""
    table = ttk.Treeview(
        parent, columns=[c[0] for c in columns],
        show="headings", height=height, selectmode="extended"
    )
    for key, text, width in columns:
        table.heading(key, text=text)
        table.column(key, width=width, anchor="center")
    table.pack(fill="both", expand=True, padx=20, pady=5)
    return table


def show_classes():
    global cls_table, cls_members, cls_name, cls_grade
    global cls_teacher, cls_student_box

    clear_content()

    tk.Label(
        content, text="مدیریت کلاس‌ها",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=10)

    # داده‌های لازم برای لیست‌های کشویی
    cls_teachers.clear()
    cls_all_students.clear()
    try:
        for t in api_request("/teachers")["teachers"]:
            label = "%s %s (%s)" % (t["first_name"], t["last_name"], t["teacher_code"])
            cls_teachers[label] = t["id"]
        for st in api_request("/students")["students"]:
            label = "%s %s (%s)" % (st["first_name"], st["last_name"], st["student_code"])
            cls_all_students[label] = st["student_code"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))

    # فرم ساخت کلاس
    form = tk.Frame(content, bg=BG)
    form.pack(pady=5)

    tk.Label(form, text="نام کلاس:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    cls_name = tk.Entry(form, font=("Tahoma", 11), width=14)
    cls_name.pack(side="right", padx=4)

    tk.Label(form, text="پایه:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    cls_grade = tk.Entry(form, font=("Tahoma", 11), width=10)
    cls_grade.pack(side="right", padx=4)

    tk.Label(form, text="دبیر:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    cls_teacher = ttk.Combobox(
        form, values=list(cls_teachers), state="readonly",
        font=("Tahoma", 11), width=22
    )
    cls_teacher.pack(side="right", padx=4)

    buttons = tk.Frame(content, bg=BG)
    buttons.pack(pady=8)
    action_button(buttons, "ساخت کلاس", create_class_action, BLUE)
    action_button(buttons, "حذف کلاس", delete_class_action, "#C62828")

    # جدول کلاس‌ها
    cls_table = make_table(content, [
        ("name", "نام کلاس", 160),
        ("grade", "پایه", 100),
        ("teacher", "دبیر", 200),
        ("count", "تعداد دانش‌آموز", 120),
    ], height=6)
    cls_table.config(selectmode="browse")
    cls_table.bind("<<TreeviewSelect>>", load_class_members)

    # دانش‌آموزان کلاس انتخاب‌شده
    tk.Label(
        content, text="دانش‌آموزان کلاس انتخاب‌شده",
        font=("Tahoma", 13, "bold"), bg=BG
    ).pack(pady=(10, 2))

    add_frame = tk.Frame(content, bg=BG)
    add_frame.pack(pady=5)

    cls_student_box = ttk.Combobox(
        add_frame, values=list(cls_all_students),
        font=("Tahoma", 11), width=34
    )
    cls_student_box.pack(side="right", padx=5)

    action_button(add_frame, "افزودن به کلاس", add_member_action, "#00897B")
    action_button(add_frame, "حذف از کلاس", remove_member_action, "#C62828")

    cls_members = make_table(content, [
        ("name", "نام و نام خانوادگی", 220),
        ("code", "کد دانش‌آموزی", 130),
        ("phone", "شماره تلفن", 150),
    ], height=6)

    load_classes(keep_selection=False)


# -------------------------------
# صفحه نمرات و کارنامه
# -------------------------------

gr_students = {}        # متن نمایشی دانش‌آموز -> کد
gr_student_box = None
gr_term_box = None
gr_subject = None
gr_score = None
gr_table = None
gr_report = None
gr_overall = None
gr_attendance = None

DIGITS_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫/،", "0123456789" * 2 + "...")


def parse_score(text):
    """عدد را از ورودی می‌خواند (ارقام فارسی و ممیز فارسی هم قبول)."""
    try:
        return float(text.strip().translate(DIGITS_FA))
    except ValueError:
        return None


def current_grade_student():
    if gr_student_box is None:
        return None
    return gr_students.get(gr_student_box.get())


def load_grades_report(event=None):
    for table in (gr_table, gr_report):
        for item in table.get_children():
            table.delete(item)

    gr_overall.config(text="معدل کل: -", fg="black")
    gr_attendance.config(text="")

    code = current_grade_student()
    if code is None:
        return

    quoted = urllib.parse.quote(code, safe="")

    try:
        grades = api_request("/students/%s/grades" % quoted)["grades"]
        report = api_request("/students/%s/report" % quoted)
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    for g in grades:
        gr_table.insert(
            "", tk.END, iid=str(g["id"]),
            values=(g["subject"], g["term"], g["score"], g["class_name"] or "-")
        )

    for r in report["subjects"]:
        gr_report.insert(
            "", tk.END,
            values=(r["subject"], r["term"], r["average"]),
            tags=("low",) if r["average"] < 10 else ()
        )

    overall = report["overall_average"]
    if overall is not None:
        gr_overall.config(
            text="معدل کل: %s" % overall,
            fg="#C62828" if overall < 10 else "#2E7D32"
        )

    if report["attendance"]:
        gr_attendance.config(
            text="حضور و غیاب: " + " | ".join(
                "%s: %d" % (STATUS_LABELS.get(a["status"], a["status"]), a["count"])
                for a in report["attendance"]
            )
        )


def add_grade_action(event=None):
    code = current_grade_student()
    subject = gr_subject.get().strip()
    term = gr_term_box.get().strip()
    score = parse_score(gr_score.get())

    if code is None:
        messagebox.showwarning("خطا", "ابتدا یک دانش‌آموز را انتخاب کنید.")
        return

    if not subject or not term:
        messagebox.showwarning("خطا", "نام درس و نیم‌سال را وارد کنید.")
        return

    if score is None or not 0 <= score <= 20:
        messagebox.showwarning("خطا", "نمره باید عددی بین ۰ تا ۲۰ باشد.")
        return

    try:
        api_request("/grades", method="POST", data={
            "student_code": code,
            "subject": subject,
            "term": term,
            "score": score,
        })
        # درس و نیم‌سال می‌مانند تا ثبت نمره دانش‌آموز بعدی سریع باشد
        gr_score.delete(0, tk.END)
        gr_score.focus()
        load_grades_report()

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def delete_grade_action():
    selected = gr_table.selection()

    if not selected:
        messagebox.showwarning("خطا", "یک نمره را از جدول بالا انتخاب کنید.")
        return

    if not messagebox.askyesno("تأیید حذف", "نمره انتخاب‌شده حذف شود؟"):
        return

    try:
        for grade_id in selected:
            api_request("/grades/%s" % grade_id, method="DELETE")
        load_grades_report()
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def show_grades():
    global gr_student_box, gr_term_box, gr_subject, gr_score
    global gr_table, gr_report, gr_overall, gr_attendance

    clear_content()

    tk.Label(
        content, text="نمرات و کارنامه",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=10)

    gr_students.clear()
    subject_names = []
    try:
        for st in api_request("/students")["students"]:
            label = "%s %s (%s)" % (st["first_name"], st["last_name"], st["student_code"])
            gr_students[label] = st["student_code"]
        subject_names = [x["name"] for x in api_request("/subjects")["subjects"]]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))

    # انتخاب دانش‌آموز
    top = tk.Frame(content, bg=BG)
    top.pack(pady=4)

    tk.Label(top, text="دانش‌آموز:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    gr_student_box = ttk.Combobox(
        top, values=list(gr_students), state="readonly",
        font=("Tahoma", 11), width=36
    )
    gr_student_box.pack(side="right", padx=4)
    gr_student_box.bind("<<ComboboxSelected>>", load_grades_report)

    # فرم ثبت نمره
    form = tk.Frame(content, bg=BG)
    form.pack(pady=4)

    tk.Label(form, text="درس:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    gr_subject = ttk.Combobox(
        form, values=subject_names, state="readonly",
        font=("Tahoma", 11), width=14
    )
    gr_subject.pack(side="right", padx=4)

    tk.Label(form, text="نیم‌سال:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    gr_term_box = ttk.Combobox(
        form, values=sorted(set(["نیم‌سال اول", "نیم‌سال دوم"] + existing_terms())),
        font=("Tahoma", 11), width=12
    )
    gr_term_box.set("نیم‌سال اول")
    gr_term_box.pack(side="right", padx=4)

    tk.Label(form, text="نمره (۰ تا ۲۰):", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    gr_score = tk.Entry(form, font=("Tahoma", 11), width=7, justify="center")
    gr_score.pack(side="right", padx=4)
    gr_score.bind("<Return>", add_grade_action)

    if not subject_names:
        tk.Label(
            content, text="هنوز درسی تعریف نشده است. ابتدا از منوی «درس ها» درس اضافه کنید.",
            font=("Tahoma", 11), bg=BG, fg="#C62828"
        ).pack()

    buttons = tk.Frame(content, bg=BG)
    buttons.pack(pady=6)
    action_button(buttons, "ثبت نمره", add_grade_action, BLUE)
    action_button(buttons, "حذف نمره انتخاب‌شده", delete_grade_action, "#C62828")

    # نمره‌های ثبت‌شده
    tk.Label(
        content, text="نمره‌های ثبت‌شده",
        font=("Tahoma", 12, "bold"), bg=BG
    ).pack(pady=(6, 0))

    gr_table = make_table(content, [
        ("subject", "درس", 160),
        ("term", "نیم‌سال", 120),
        ("score", "نمره", 80),
        ("class", "کلاس", 120),
    ], height=5)

    # کارنامه
    tk.Label(
        content, text="کارنامه (میانگین هر درس)",
        font=("Tahoma", 12, "bold"), bg=BG
    ).pack(pady=(6, 0))

    gr_report = make_table(content, [
        ("subject", "درس", 160),
        ("term", "نیم‌سال", 120),
        ("average", "میانگین", 80),
    ], height=5)
    gr_report.tag_configure("low", background="#FFCDD2")

    gr_overall = tk.Label(
        content, text="معدل کل: -",
        font=("Tahoma", 14, "bold"), bg=BG
    )
    gr_overall.pack(pady=(4, 0))

    gr_attendance = tk.Label(content, text="", font=("Tahoma", 11), bg=BG)
    gr_attendance.pack(pady=(0, 6))


# -------------------------------
# صفحه درس‌ها
# -------------------------------

sb_table = None
sb_name = None
sb_grade = None


def selected_subject_id():
    selected = sb_table.selection() if sb_table is not None else ()
    return int(selected[0]) if selected else None


def load_subjects():
    for item in sb_table.get_children():
        sb_table.delete(item)

    try:
        subjects = api_request("/subjects")["subjects"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    for sub in subjects:
        sb_table.insert(
            "", tk.END, iid=str(sub["id"]),
            values=(sub["name"], sub["grade"] or "-")
        )


def select_subject(event=None):
    selected = sb_table.selection()
    if not selected:
        return

    name, grade = sb_table.item(selected[0], "values")
    sb_name.delete(0, tk.END)
    sb_name.insert(0, name)
    sb_grade.delete(0, tk.END)
    sb_grade.insert(0, "" if grade == "-" else grade)


def add_subject_action():
    name = sb_name.get().strip()

    if not name:
        messagebox.showwarning("خطا", "نام درس الزامی است.")
        return

    try:
        api_request("/subjects", method="POST",
                    data={"name": name, "grade": sb_grade.get().strip()})
        sb_name.delete(0, tk.END)
        sb_grade.delete(0, tk.END)
        load_subjects()

    except urllib.error.HTTPError as error:
        if error.code == 409:
            messagebox.showerror("خطا", "این درس قبلاً تعریف شده است.")
        else:
            messagebox.showerror("خطا", error_text(error))

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def update_subject_action():
    subject_id = selected_subject_id()
    name = sb_name.get().strip()

    if subject_id is None:
        messagebox.showwarning("خطا", "ابتدا یک درس را از جدول انتخاب کنید.")
        return

    if not name:
        messagebox.showwarning("خطا", "نام درس الزامی است.")
        return

    try:
        api_request("/subjects/%d" % subject_id, method="PUT",
                    data={"name": name, "grade": sb_grade.get().strip()})
        load_subjects()
        messagebox.showinfo("نتیجه", "درس ویرایش شد (نمره‌های قبلی هم به‌روز شدند).")

    except urllib.error.HTTPError as error:
        if error.code == 409:
            messagebox.showerror("خطا", "درسی با این نام وجود دارد.")
        else:
            messagebox.showerror("خطا", error_text(error))

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def delete_subject_action():
    subject_id = selected_subject_id()

    if subject_id is None:
        messagebox.showwarning("خطا", "ابتدا یک درس را از جدول انتخاب کنید.")
        return

    if not messagebox.askyesno("تأیید حذف", "این درس حذف شود؟"):
        return

    try:
        api_request("/subjects/%d" % subject_id, method="DELETE")
        sb_name.delete(0, tk.END)
        sb_grade.delete(0, tk.END)
        load_subjects()
    except Exception as error:
        # اگر برای درس نمره ثبت شده باشد، سرور دلیل را برمی‌گرداند
        messagebox.showerror("خطا", error_text(error))


def show_subjects():
    global sb_table, sb_name, sb_grade

    clear_content()

    tk.Label(
        content, text="مدیریت درس‌ها",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=15)

    form = tk.Frame(content, bg=BG)
    form.pack(pady=5)

    sb_name = make_field(form, "نام درس:", 0)
    sb_grade = make_field(form, "پایه (اختیاری):", 1)

    buttons = tk.Frame(content, bg=BG)
    buttons.pack(pady=10)
    action_button(buttons, "افزودن درس", add_subject_action, BLUE)
    action_button(buttons, "ویرایش درس", update_subject_action, "#00897B")
    action_button(buttons, "حذف درس", delete_subject_action, "#C62828")

    sb_table = make_table(content, [
        ("name", "نام درس", 220),
        ("grade", "پایه", 120),
    ], height=12)
    sb_table.config(selectmode="browse")
    sb_table.bind("<<TreeviewSelect>>", select_subject)

    load_subjects()


# -------------------------------
# صفحه مدیریت دبیران
# -------------------------------

tch_table = None
tch_first = None
tch_last = None
tch_code = None
tch_phone = None
tch_subject = None
tch_search = None
tch_selected = {"code": None}   # کد دبیری که برای ویرایش/حذف انتخاب شده


def clear_teacher_form():
    tch_code.config(state="normal")
    for entry in (tch_first, tch_last, tch_code, tch_phone):
        entry.delete(0, tk.END)
    tch_subject.set("")
    tch_selected["code"] = None
    tch_table.selection_remove(tch_table.selection())


def load_teachers(keyword=""):
    for item in tch_table.get_children():
        tch_table.delete(item)

    try:
        teachers = api_request("/teachers")["teachers"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    keyword = keyword.strip()

    for t in teachers:
        text = " ".join([
            t["first_name"], t["last_name"], t["teacher_code"], t["subject"] or ""
        ])
        if keyword and keyword not in text:
            continue

        tch_table.insert(
            "", tk.END, iid=t["teacher_code"],
            values=(
                t["first_name"], t["last_name"], t["teacher_code"],
                t["subject"] or "-", t["phone"] or "-"
            )
        )


def select_teacher(event=None):
    selected = tch_table.selection()
    if not selected:
        return

    first, last, code, subject, phone = tch_table.item(selected[0], "values")

    tch_code.config(state="normal")
    for entry in (tch_first, tch_last, tch_code, tch_phone):
        entry.delete(0, tk.END)

    tch_first.insert(0, first)
    tch_last.insert(0, last)
    tch_code.insert(0, code)
    tch_phone.insert(0, "" if phone == "-" else phone)
    tch_subject.set("" if subject == "-" else subject)

    # کد دبیر هنگام ویرایش قابل تغییر نیست
    tch_code.config(state="readonly")
    tch_selected["code"] = code


def teacher_form_data():
    return {
        "first_name": tch_first.get().strip(),
        "last_name": tch_last.get().strip(),
        "teacher_code": tch_code.get().strip(),
        "phone": tch_phone.get().strip(),
        "subject": tch_subject.get().strip(),
    }


def register_teacher():
    if tch_selected["code"] is not None:
        messagebox.showwarning(
            "توجه", "یک دبیر انتخاب شده است. برای ثبت دبیر جدید، ابتدا «فرم جدید» را بزنید."
        )
        return

    data = teacher_form_data()

    if not data["first_name"] or not data["last_name"] or not data["teacher_code"]:
        messagebox.showwarning("خطا", "نام، نام خانوادگی و کد دبیر الزامی است.")
        return

    try:
        result = api_request("/teachers", method="POST", data=data)
        messagebox.showinfo("موفقیت", result["message"])
        clear_teacher_form()
        load_teachers()

    except urllib.error.HTTPError as error:
        if error.code == 409:
            messagebox.showerror("خطا", "این کد دبیر قبلاً ثبت شده است.")
        else:
            messagebox.showerror("خطا", error_text(error))

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def update_teacher_action():
    code = tch_selected["code"]

    if code is None:
        messagebox.showwarning("خطا", "ابتدا یک دبیر را از جدول انتخاب کنید.")
        return

    data = teacher_form_data()

    if not data["first_name"] or not data["last_name"]:
        messagebox.showwarning("خطا", "نام و نام خانوادگی را وارد کنید.")
        return

    try:
        result = api_request(
            "/teachers/" + urllib.parse.quote(code, safe=""),
            method="PUT", data=data
        )
        messagebox.showinfo("نتیجه", result["message"])
        load_teachers(tch_search.get())

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def delete_teacher_action():
    code = tch_selected["code"]

    if code is None:
        messagebox.showwarning("خطا", "ابتدا یک دبیر را از جدول انتخاب کنید.")
        return

    if not messagebox.askyesno(
        "تأیید حذف",
        "دبیر حذف شود؟ کلاس‌های او حذف نمی‌شوند، ولی بدون دبیر می‌مانند."
    ):
        return

    try:
        result = api_request(
            "/teachers/" + urllib.parse.quote(code, safe=""),
            method="DELETE"
        )
        messagebox.showinfo("نتیجه", result["message"])
        clear_teacher_form()
        load_teachers(tch_search.get())

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def show_teachers():
    global tch_table, tch_first, tch_last, tch_code
    global tch_phone, tch_subject, tch_search

    clear_content()
    tch_selected["code"] = None

    tk.Label(
        content, text="مدیریت دبیران",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=15)

    subject_names = []
    try:
        subject_names = [s["name"] for s in api_request("/subjects")["subjects"]]
    except Exception:
        pass   # فهرست درس‌ها اختیاری است؛ دبیر می‌تواند درس را تایپ کند

    form = tk.Frame(content, bg=BG)
    form.pack(pady=5)

    tch_first = make_field(form, "نام:", 0)
    tch_last = make_field(form, "نام خانوادگی:", 1)
    tch_code = make_field(form, "کد دبیر:", 2)
    tch_phone = make_field(form, "شماره تلفن:", 3)

    tk.Label(
        form, text="درس تخصصی:", bg=BG, font=("Tahoma", 11)
    ).grid(row=4, column=0, padx=10, pady=7)

    tch_subject = ttk.Combobox(
        form, values=subject_names, font=("Tahoma", 11), width=23
    )
    tch_subject.grid(row=4, column=1, padx=10, pady=7)

    buttons = tk.Frame(content, bg=BG)
    buttons.pack(pady=10)

    action_button(buttons, "ثبت دبیر", register_teacher, BLUE)
    action_button(buttons, "ویرایش اطلاعات", update_teacher_action, "#00897B")
    action_button(buttons, "حذف دبیر", delete_teacher_action, "#C62828")
    action_button(buttons, "فرم جدید", clear_teacher_form, "#546E7A")

    search_frame = tk.Frame(content, bg=BG)
    search_frame.pack(pady=5)

    tch_search = tk.Entry(search_frame, font=("Tahoma", 11), width=25)
    tch_search.pack(side="right", padx=5)
    tch_search.bind("<Return>", lambda e: load_teachers(tch_search.get()))

    ttk.Button(
        search_frame, text="جست‌وجو",
        command=lambda: load_teachers(tch_search.get())
    ).pack(side="right", padx=5)

    ttk.Button(
        search_frame, text="نمایش همه",
        command=lambda: (tch_search.delete(0, tk.END), load_teachers())
    ).pack(side="right", padx=5)

    tch_table = make_table(content, [
        ("first", "نام", 110),
        ("last", "نام خانوادگی", 140),
        ("code", "کد دبیر", 100),
        ("subject", "درس تخصصی", 140),
        ("phone", "شماره تلفن", 130),
    ], height=9)
    tch_table.config(selectmode="browse")
    tch_table.bind("<<TreeviewSelect>>", select_teacher)

    load_teachers()


# -------------------------------
# صفحه مدیریت کاربران (فقط مدیر)
# -------------------------------

ROLE_LABELS = {"admin": "مدیر", "teacher": "دبیر"}
ROLE_FROM_LABEL = {label: key for key, label in ROLE_LABELS.items()}

usr_table = None
usr_username = None
usr_fullname = None
usr_password = None
usr_role = None
usr_teacher = None
usr_active = tk.BooleanVar(value=True)
usr_data = {}            # شناسه کاربر -> اطلاعات کامل
usr_teachers = {}        # متن نمایشی دبیر -> کد
usr_selected = {"id": None}


def clear_user_form():
    usr_username.config(state="normal")
    for entry in (usr_username, usr_fullname, usr_password):
        entry.delete(0, tk.END)
    usr_role.set(ROLE_LABELS["teacher"])
    usr_teacher.set("")
    usr_active.set(True)
    usr_selected["id"] = None
    usr_table.selection_remove(usr_table.selection())


def load_users():
    for item in usr_table.get_children():
        usr_table.delete(item)
    usr_data.clear()

    try:
        users = api_request("/users")["users"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    for u in users:
        usr_data[str(u["id"])] = u
        usr_table.insert(
            "", tk.END, iid=str(u["id"]),
            values=(
                u["username"], u["full_name"] or "-",
                ROLE_LABELS.get(u["role"], u["role"]),
                u["teacher_name"] or "-",
                "فعال" if u["active"] else "غیرفعال",
            ),
            tags=() if u["active"] else ("inactive",)
        )


def select_user(event=None):
    selected = usr_table.selection()
    if not selected:
        return

    u = usr_data.get(selected[0])
    if u is None:
        return

    usr_username.config(state="normal")
    for entry in (usr_username, usr_fullname, usr_password):
        entry.delete(0, tk.END)

    usr_username.insert(0, u["username"])
    usr_username.config(state="readonly")   # نام کاربری قابل تغییر نیست
    usr_fullname.insert(0, u["full_name"] or "")
    usr_role.set(ROLE_LABELS.get(u["role"], ""))
    usr_active.set(bool(u["active"]))

    label = ""
    for text, code in usr_teachers.items():
        if code == u["teacher_code"]:
            label = text
    usr_teacher.set(label)
    usr_selected["id"] = u["id"]


def confirm_teacher_link(role, teacher_code):
    """دبیرِ بدون اتصال به پرونده دبیری نمی‌تواند حضور و غیاب ثبت کند."""
    if role == "teacher" and not teacher_code:
        return messagebox.askyesno(
            "توجه",
            "این کاربر به هیچ دبیری متصل نشده و نمی‌تواند حضور و غیاب ثبت کند. ادامه می‌دهید؟"
        )
    return True


def add_user_action():
    if usr_selected["id"] is not None:
        messagebox.showwarning(
            "توجه", "یک کاربر انتخاب شده است. برای ساخت کاربر جدید ابتدا «فرم جدید» را بزنید."
        )
        return

    username = usr_username.get().strip()
    password = usr_password.get()
    role = ROLE_FROM_LABEL.get(usr_role.get())
    teacher_code = usr_teachers.get(usr_teacher.get())

    if len(username) < 3:
        messagebox.showwarning("خطا", "نام کاربری حداقل ۳ نویسه باشد.")
        return

    if len(password) < 8:
        messagebox.showwarning("خطا", "رمز عبور حداقل ۸ نویسه باشد.")
        return

    if role is None:
        messagebox.showwarning("خطا", "نقش کاربر را انتخاب کنید.")
        return

    if not confirm_teacher_link(role, teacher_code):
        return

    try:
        api_request("/users", method="POST", data={
            "username": username,
            "password": password,
            "full_name": usr_fullname.get().strip(),
            "role": role,
            "teacher_code": teacher_code,
        })
        clear_user_form()
        load_users()

    except urllib.error.HTTPError as error:
        if error.code == 409:
            messagebox.showerror("خطا", "این نام کاربری قبلاً استفاده شده است.")
        else:
            messagebox.showerror("خطا", error_text(error))

    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def update_user_action():
    user_id = usr_selected["id"]

    if user_id is None:
        messagebox.showwarning("خطا", "ابتدا یک کاربر را از جدول انتخاب کنید.")
        return

    role = ROLE_FROM_LABEL.get(usr_role.get())
    teacher_code = usr_teachers.get(usr_teacher.get())

    if role is None:
        messagebox.showwarning("خطا", "نقش کاربر را انتخاب کنید.")
        return

    if not confirm_teacher_link(role, teacher_code):
        return

    try:
        api_request("/users/%d" % user_id, method="PUT", data={
            "full_name": usr_fullname.get().strip(),
            "role": role,
            "active": bool(usr_active.get()),
            "teacher_code": teacher_code,
        })
        messagebox.showinfo("نتیجه", "تغییرات ذخیره شد.")
        load_users()
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def reset_user_password_action():
    user_id = usr_selected["id"]
    password = usr_password.get()

    if user_id is None:
        messagebox.showwarning("خطا", "ابتدا یک کاربر را از جدول انتخاب کنید.")
        return

    if len(password) < 8:
        messagebox.showwarning("خطا", "رمز جدید را (حداقل ۸ نویسه) در فیلد رمز عبور بنویسید.")
        return

    try:
        api_request("/users/%d/password" % user_id, method="PUT",
                    data={"password": password})
        usr_password.delete(0, tk.END)
        messagebox.showinfo("نتیجه", "رمز عبور تغییر کرد و کاربر از همه دستگاه‌ها خارج شد.")
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def delete_user_action():
    user_id = usr_selected["id"]

    if user_id is None:
        messagebox.showwarning("خطا", "ابتدا یک کاربر را از جدول انتخاب کنید.")
        return

    if not messagebox.askyesno("تأیید حذف", "این کاربر حذف شود؟"):
        return

    try:
        api_request("/users/%d" % user_id, method="DELETE")
        clear_user_form()
        load_users()
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


def show_users():
    global usr_table, usr_username, usr_fullname, usr_password
    global usr_role, usr_teacher

    clear_content()
    usr_selected["id"] = None

    tk.Label(
        content, text="مدیریت کاربران",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=12)

    usr_teachers.clear()
    try:
        for t in api_request("/teachers")["teachers"]:
            label = "%s %s (%s)" % (t["first_name"], t["last_name"], t["teacher_code"])
            usr_teachers[label] = t["teacher_code"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))

    form = tk.Frame(content, bg=BG)
    form.pack(pady=4)

    usr_username = make_field(form, "نام کاربری:", 0)
    usr_fullname = make_field(form, "نام نمایشی:", 1)

    tk.Label(
        form, text="رمز عبور (حداقل ۸ نویسه):", bg=BG, font=("Tahoma", 11)
    ).grid(row=2, column=0, padx=10, pady=5)
    usr_password = tk.Entry(form, font=("Tahoma", 11), width=25, show="*")
    usr_password.grid(row=2, column=1, padx=10, pady=5)

    tk.Label(
        form, text="نقش:", bg=BG, font=("Tahoma", 11)
    ).grid(row=3, column=0, padx=10, pady=5)
    usr_role = ttk.Combobox(
        form, values=list(ROLE_LABELS.values()), state="readonly",
        font=("Tahoma", 11), width=23
    )
    usr_role.set(ROLE_LABELS["teacher"])
    usr_role.grid(row=3, column=1, padx=10, pady=5)

    tk.Label(
        form, text="متصل به دبیر:", bg=BG, font=("Tahoma", 11)
    ).grid(row=4, column=0, padx=10, pady=5)
    usr_teacher = ttk.Combobox(
        form, values=list(usr_teachers), state="readonly",
        font=("Tahoma", 11), width=23
    )
    usr_teacher.grid(row=4, column=1, padx=10, pady=5)

    tk.Checkbutton(
        form, text="حساب فعال است", variable=usr_active,
        bg=BG, font=("Tahoma", 11)
    ).grid(row=5, column=0, columnspan=2, pady=3)
    usr_active.set(True)

    buttons = tk.Frame(content, bg=BG)
    buttons.pack(pady=8)
    action_button(buttons, "افزودن کاربر", add_user_action, BLUE)
    action_button(buttons, "ذخیره تغییرات", update_user_action, "#00897B")
    action_button(buttons, "بازنشانی رمز", reset_user_password_action, "#F9A825")
    action_button(buttons, "حذف کاربر", delete_user_action, "#C62828")
    action_button(buttons, "فرم جدید", clear_user_form, "#546E7A")

    usr_table = make_table(content, [
        ("username", "نام کاربری", 120),
        ("name", "نام نمایشی", 150),
        ("role", "نقش", 80),
        ("teacher", "دبیر متصل", 160),
        ("status", "وضعیت", 80),
    ], height=8)
    usr_table.config(selectmode="browse")
    usr_table.tag_configure("inactive", foreground="#9E9E9E")
    usr_table.bind("<<TreeviewSelect>>", select_user)

    load_users()


# -------------------------------
# کارنامه چاپی (صفحه HTML + نمودار SVG)
# -------------------------------

PASS_SCORE = 10                      # حداقل نمره‌ی قبولی
DEFAULT_SCHOOL_NAME = "مدرسه سرچهان"    # در صفحه گزارش‌گیری هم قابل تغییر است
SETTINGS_FILE = os.path.join(
    os.environ.get("SCHOOL_DATA_DIR") or os.path.dirname(os.path.abspath(__file__)),
    "report_settings.json"
)
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

REPORT_CSS = """
body{font-family:Tahoma,Arial,sans-serif;margin:0;background:#f1f5f9;color:#222;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.toolbar{padding:10px 20px;background:#1565C0;color:#fff;font-size:13px}
.toolbar button{font-size:15px;padding:6px 20px;margin-left:14px;cursor:pointer}
.card{background:#fff;width:190mm;margin:14px auto;padding:10mm;box-sizing:border-box;
border:1px solid #cfd8dc}
.head{text-align:center;border-bottom:2px solid #1565C0;padding-bottom:6px;margin-bottom:10px}
.head h1{margin:0;font-size:22px;color:#1565C0}
.head h2{margin:4px 0 0;font-size:15px;font-weight:normal}
h3{font-size:14px;margin:14px 0 6px;color:#1565C0}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{border:1px solid #90a4ae;padding:5px 8px;text-align:right}
th{background:#e3f2fd}
.num{text-align:center}
.ok{color:#2e7d32;font-weight:bold;text-align:center}
.bad{color:#c62828;font-weight:bold;text-align:center}
.summary{margin-top:10px}
.summary td{width:25%;text-align:center;font-size:13px;padding:6px}
.summary b{display:block;font-size:18px;margin-top:2px}
.chart{text-align:center}
.sign{margin-top:28px}
.sign td{border:none;font-size:13px;padding:0}
.sign td+td{text-align:left}
.foot{margin-top:14px;font-size:11px;color:#666}
@page{size:A4;margin:8mm}
@media print{body{background:#fff}.no-print{display:none}
.card{margin:0;border:none;width:auto;padding:0}
.card+.card{page-break-before:always}}
"""


def fa(value):
    """ارقام انگلیسی را فارسی می‌کند."""
    return str(value).translate(FA_DIGITS)


def fmt_score(value):
    return ("%.2f" % value).rstrip("0").rstrip(".")


def school_year_default():
    year, month, _ = [int(x) for x in today_jalali().split("-")]
    return "%d-%d" % ((year, year + 1) if month >= 7 else (year - 1, year))


def load_report_settings():
    settings = {"school_name": DEFAULT_SCHOOL_NAME, "school_year": school_year_default()}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            settings.update(json.load(f))
    except Exception:
        pass
    return settings


def save_report_settings(school_name, school_year):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"school_name": school_name, "school_year": school_year},
                      f, ensure_ascii=False)
    except Exception:
        pass   # ذخیره‌نشدن تنظیمات مانع چاپ نمی‌شود


def short_label(text, limit=13):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def build_chart_svg(rows):
    """نمودار میله‌ای: rows = [(درس، میانگین دانش‌آموز، میانگین کلاس یا None)]"""
    if not rows:
        return ""

    count = len(rows)
    width = max(560, 95 * count + 70)
    height = 320
    left, right, top, bottom = 38, 14, 34, 62
    plot_w = width - left - right
    plot_h = height - top - bottom
    group_w = plot_w / float(count)
    has_class = any(r[2] is not None for r in rows)
    bar_w = min(30.0, group_w / (3.0 if has_class else 2.0))

    def y_of(value):
        return top + plot_h * (1 - value / 20.0)

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
        'style="width:100%%;max-width:%dpx;height:auto" direction="ltr" '
        'font-family="Tahoma, Arial, sans-serif">' % (width, height, width)
    ]

    # خطوط راهنما
    for v in (0, 5, 10, 15, 20):
        y = y_of(v)
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#E0E0E0"/>'
                   % (left, y, width - right, y))
        out.append('<text x="%d" y="%.1f" font-size="11" fill="#666" '
                   'text-anchor="end">%s</text>' % (left - 6, y + 4, fa(v)))

    # خط حد قبولی
    y = y_of(PASS_SCORE)
    out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#C62828" '
               'stroke-width="1.5" stroke-dasharray="6 4"/>'
               % (left, y, width - right, y))

    def bar(x, value, color):
        h = plot_h * value / 20.0
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                   % (x, top + plot_h - h, bar_w, h, color))
        out.append('<text x="%.1f" y="%.1f" font-size="11" fill="#333" '
                   'text-anchor="middle">%s</text>'
                   % (x + bar_w / 2, top + plot_h - h - 4, fa(fmt_score(value))))

    for i, (name, own, cls) in enumerate(rows):
        # راست‌به‌چپ: درس اول سمت راست قرار می‌گیرد
        center = width - right - (i + 0.5) * group_w
        if has_class:
            bar(center, own, "#1565C0")                 # دانش‌آموز
            if cls is not None:
                bar(center - bar_w, cls, "#9E9E9E")     # میانگین کلاس
        else:
            bar(center - bar_w / 2, own, "#1565C0")
        out.append('<text x="%.1f" y="%d" font-size="12" text-anchor="middle">%s</text>'
                   % (center, height - bottom + 18, esc(short_label(name))))

    # راهنما
    x0 = width - right - 12
    out.append('<rect x="%d" y="9" width="12" height="12" fill="#1565C0"/>' % x0)
    out.append('<text x="%d" y="19" font-size="12" text-anchor="end">دانش‌آموز</text>' % (x0 - 6))
    if has_class:
        x1 = x0 - 100
        out.append('<rect x="%d" y="9" width="12" height="12" fill="#9E9E9E"/>' % x1)
        out.append('<text x="%d" y="19" font-size="12" text-anchor="end">میانگین کلاس</text>' % (x1 - 6))
        x0 = x1 - 20
    x2 = x0 - 100
    out.append('<line x1="%d" y1="15" x2="%d" y2="15" stroke="#C62828" '
               'stroke-width="2" stroke-dasharray="4 3"/>' % (x2 - 6, x2 + 12))
    out.append('<text x="%d" y="19" font-size="12" text-anchor="end">حد قبولی</text>' % (x2 - 12))

    out.append("</svg>")
    return "".join(out)


def build_card_html(r, school, year, term):
    """کارنامه‌ی یک دانش‌آموز (یک صفحه A4)."""
    st = r["student"]
    full_name = "%s %s" % (st["first_name"], st["last_name"])
    class_avg = dict((x["subject"], x["average"]) for x in r["class_averages"])

    table_rows = []
    chart_rows = []
    for sub in r["subjects"]:
        own = sub["average"]
        cls = class_avg.get(sub["subject"])
        passed = own >= PASS_SCORE
        table_rows.append(
            "<tr><td>%s</td><td class='num'>%s</td><td class='num'>%s</td>"
            "<td class='%s'>%s</td></tr>" % (
                esc(sub["subject"]),
                fa(fmt_score(own)),
                fa(fmt_score(cls)) if cls is not None else "-",
                "ok" if passed else "bad",
                "قبول" if passed else "مردود",
            )
        )
        chart_rows.append((sub["subject"], own, cls))

    counts = dict((a["status"], a["count"]) for a in r["attendance"])
    overall = r["overall_average"]
    overall_ok = overall is not None and overall >= PASS_SCORE

    return (
        "<section class='card'>"
        "<div class='head'><h1>%s</h1><h2>کارنامه %s — سال تحصیلی %s</h2></div>"
        "<table><tr><th>نام و نام خانوادگی</th><td>%s</td>"
        "<th>کد دانش‌آموزی</th><td>%s</td><th>کلاس</th><td>%s</td></tr></table>"
        "<h3>نمرات دروس</h3>"
        "<table><tr><th>درس</th><th>نمره</th><th>میانگین کلاس</th><th>وضعیت</th></tr>%s</table>"
        "<table class='summary'><tr>"
        "<td>معدل کل<b style='color:%s'>%s</b></td>"
        "<td>غایب<b>%s</b></td>"
        "<td>تأخیر<b>%s</b></td>"
        "<td>غیبت موجه<b>%s</b></td></tr></table>"
        "<h3>نمودار نمرات</h3><div class='chart'>%s</div>"
        "<table class='sign'><tr><td>امضای ولی: ..............</td>"
        "<td>مهر و امضای مدیر: ..............</td></tr></table>"
        "<div class='foot'>تاریخ صدور: %s — تعداد غیبت و تأخیر از ابتدای ثبت تا امروز است.</div>"
        "</section>"
    ) % (
        esc(school), esc(term), fa(esc(year)),
        esc(full_name), fa(esc(st["student_code"])),
        esc("، ".join(r["classes"]) or "-"),
        "".join(table_rows),
        "#2e7d32" if overall_ok else "#c62828",
        fa(fmt_score(overall)) if overall is not None else "-",
        fa(counts.get("absent", 0)), fa(counts.get("late", 0)),
        fa(counts.get("excused", 0)),
        build_chart_svg(chart_rows),
        fa(today_jalali()),
    )


def open_report_page(cards_html, title):
    page = (
        "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        "<title>%s</title><style>%s</style></head><body>"
        "<div class='no-print toolbar'><button onclick='window.print()'>چاپ</button>"
        "برای ذخیره به‌صورت PDF، در پنجره چاپ مقصد را «Save as PDF» بگذارید."
        "</div>%s</body></html>"
    ) % (esc(title), REPORT_CSS, cards_html)

    handle, path = tempfile.mkstemp(prefix="karname_", suffix=".html")
    with os.fdopen(handle, "w", encoding="utf-8") as f:
        f.write(page)

    webbrowser.open(Path(path).as_uri())


def fetch_report(code, term):
    query = urllib.parse.urlencode({"term": term})
    return api_request(
        "/students/%s/report?%s" % (urllib.parse.quote(code, safe=""), query)
    )


# -------------------------------
# صفحه گزارش‌گیری
# -------------------------------

rp_school = None
rp_year = None
rp_term = None
rp_student_box = None
rp_class_box = None
rp_students = {}     # متن نمایشی دانش‌آموز -> کد
rp_classes = {}      # نام کلاس -> شناسه


def existing_terms(code=None):
    """نیم‌سال‌هایی که واقعاً نمره دارند (برای یک دانش‌آموز، یا کل مدرسه)."""
    try:
        if code:
            grades = api_request(
                "/students/%s/grades" % urllib.parse.quote(code, safe="")
            )["grades"]
            return sorted(set(g["term"] for g in grades))
        return api_request("/terms")["terms"]
    except Exception:
        return []


def terms_hint(terms):
    if not terms:
        return "هنوز هیچ نمره‌ای ثبت نشده است."
    return "نیم‌سال‌های دارای نمره: " + "، ".join(terms)


def refresh_terms_for_student(event=None):
    code = rp_students.get(rp_student_box.get())
    if code is None:
        return

    terms = existing_terms(code)
    if terms:
        rp_term.config(values=terms)
        if rp_term.get() not in terms:
            rp_term.set(terms[0])


def report_inputs():
    school = rp_school.get().strip() or DEFAULT_SCHOOL_NAME
    year = rp_year.get().strip()
    term = rp_term.get().strip()

    if not term:
        messagebox.showwarning("خطا", "نیم‌سال را وارد کنید.")
        return None

    save_report_settings(school, year)
    return school, year, term


def print_student_report():
    inputs = report_inputs()
    if inputs is None:
        return
    school, year, term = inputs

    code = rp_students.get(rp_student_box.get())
    if code is None:
        messagebox.showwarning("خطا", "یک دانش‌آموز را انتخاب کنید.")
        return

    try:
        report = fetch_report(code, term)

        if "student" not in report:
            messagebox.showerror(
                "خطا",
                "سرور قدیمی است. فایل main.py جدید را جایگزین کنید و سرور را دوباره اجرا کنید."
            )
            return

        if not report["subjects"]:
            messagebox.showinfo(
                "نمره‌ای پیدا نشد",
                "برای این دانش‌آموز در «%s» نمره‌ای ثبت نشده است.\n\n%s\n"
                "نیم‌سال را از لیست کشویی انتخاب کنید." % (term, terms_hint(existing_terms(code)))
            )
            return

        name = "%s %s" % (report["student"]["first_name"], report["student"]["last_name"])
        open_report_page(build_card_html(report, school, year, term), "کارنامه " + name)

    except Exception as error:
        messagebox.showerror("خطا در ساخت کارنامه", error_text(error))


def print_class_reports():
    inputs = report_inputs()
    if inputs is None:
        return
    school, year, term = inputs

    class_id = rp_classes.get(rp_class_box.get())
    if class_id is None:
        messagebox.showwarning("خطا", "یک کلاس را انتخاب کنید.")
        return

    try:
        students = api_request("/classes/%d/students" % class_id)["students"]
        cards = []
        skipped = 0
        for st in students:
            report = fetch_report(st["student_code"], term)
            if report["subjects"]:
                cards.append(build_card_html(report, school, year, term))
            else:
                skipped += 1
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))
        return

    if not cards:
        messagebox.showinfo(
            "نمره‌ای پیدا نشد",
            "برای این کلاس در «%s» نمره‌ای ثبت نشده است.\n\n%s" % (term, terms_hint(existing_terms()))
        )
        return

    open_report_page("".join(cards), "کارنامه‌های کلاس " + rp_class_box.get())

    if skipped:
        messagebox.showinfo(
            "توجه", "%d دانش‌آموز نمره‌ای در این نیم‌سال نداشتند و کارنامه‌شان ساخته نشد." % skipped
        )


def show_reports():
    global rp_school, rp_year, rp_term, rp_student_box, rp_class_box

    clear_content()

    tk.Label(
        content, text="گزارش‌گیری و چاپ کارنامه",
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=12)

    rp_students.clear()
    rp_classes.clear()
    try:
        for st in api_request("/students")["students"]:
            label = "%s %s (%s)" % (st["first_name"], st["last_name"], st["student_code"])
            rp_students[label] = st["student_code"]
        for cl in api_request("/classes")["classes"]:
            rp_classes[cl["name"]] = cl["id"]
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))

    saved = load_report_settings()

    # تنظیمات عمومی کارنامه
    box = tk.LabelFrame(content, text=" مشخصات کارنامه ", bg=BG,
                        font=("Tahoma", 11, "bold"), padx=15, pady=8)
    box.pack(fill="x", padx=40, pady=6)

    row = tk.Frame(box, bg=BG)
    row.pack()

    tk.Label(row, text="نام مدرسه:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    rp_school = tk.Entry(row, font=("Tahoma", 11), width=22)
    rp_school.insert(0, saved["school_name"])
    rp_school.pack(side="right", padx=4)

    tk.Label(row, text="سال تحصیلی:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    rp_year = tk.Entry(row, font=("Tahoma", 11), width=10, justify="center")
    rp_year.insert(0, saved["school_year"])
    rp_year.pack(side="right", padx=4)

    tk.Label(row, text="نیم‌سال:", bg=BG, font=("Tahoma", 11)).pack(side="right", padx=4)
    known_terms = existing_terms()
    rp_term = ttk.Combobox(row, values=known_terms or ["نیم‌سال اول", "نیم‌سال دوم"],
                           font=("Tahoma", 11), width=12)
    rp_term.set(known_terms[0] if known_terms else "نیم‌سال اول")
    rp_term.pack(side="right", padx=4)

    # یک دانش‌آموز
    one = tk.LabelFrame(content, text=" کارنامه‌ی یک دانش‌آموز ", bg=BG,
                        font=("Tahoma", 11, "bold"), padx=15, pady=10)
    one.pack(fill="x", padx=40, pady=6)

    one_row = tk.Frame(one, bg=BG)
    one_row.pack()

    rp_student_box = ttk.Combobox(one_row, values=list(rp_students),
                                  state="readonly", font=("Tahoma", 11), width=36)
    rp_student_box.pack(side="right", padx=5)
    rp_student_box.bind("<<ComboboxSelected>>", refresh_terms_for_student)
    action_button(one_row, "نمایش و چاپ کارنامه", print_student_report, BLUE)

    # یک کلاس
    many = tk.LabelFrame(content, text=" کارنامه‌ی همه‌ی دانش‌آموزان یک کلاس ", bg=BG,
                         font=("Tahoma", 11, "bold"), padx=15, pady=10)
    many.pack(fill="x", padx=40, pady=6)

    many_row = tk.Frame(many, bg=BG)
    many_row.pack()

    rp_class_box = ttk.Combobox(many_row, values=list(rp_classes),
                                state="readonly", font=("Tahoma", 11), width=22)
    rp_class_box.pack(side="right", padx=5)
    action_button(many_row, "ساخت کارنامه‌های کلاس", print_class_reports, "#00897B")

    tk.Label(
        content,
        text="کارنامه در مرورگر باز می‌شود. دکمه «چاپ» بالای صفحه را بزنید،\n"
             "یا برای ذخیره به‌صورت PDF مقصد چاپ را «Save as PDF» بگذارید.\n"
             "در حالت کلاس، هر دانش‌آموز در یک صفحه‌ی جدا چاپ می‌شود.",
        font=("Tahoma", 10), bg=BG, fg="#546E7A", justify="center"
    ).pack(pady=14)


def show_placeholder(page):
    clear_content()

    tk.Label(
        content, text=page,
        font=("Tahoma", 22, "bold"), bg=BG, fg=BLUE
    ).pack(pady=40)

    tk.Label(
        content, text="این بخش در مراحل بعدی تکمیل خواهد شد.",
        font=("Tahoma", 13), bg=BG
    ).pack(pady=10)


PAGES = {
    "داشبورد": show_dashboard,
    "مدیریت دانش آموزان": show_students,
    "کلاس ها": show_classes,
    "حضور و غیاب": show_attendance,
    "نمرات و کارنامه": show_grades,
    "درس ها": show_subjects,
    "مدیریت دبیران": show_teachers,
    "کاربران": show_users,
    "گزارش گیری": show_reports,
}


def show_page(page):
    handler = PAGES.get(page)
    if handler:
        handler()
    else:
        show_placeholder(page)

    refresh_scroll_areas()


# -------------------------------
# سربرگ برنامه
# -------------------------------

header = tk.Frame(window, bg=BLUE, height=75)
header.pack(fill="x")

tk.Label(
    header, text=APP_NAME,
    font=("Tahoma", 20, "bold"), bg=BLUE, fg="white"
).pack(pady=18)


# -------------------------------
# ناحیه‌ی قابل پیمایش (نوار پیمایش فقط وقتی لازم باشد ظاهر می‌شود)
# -------------------------------

def make_scrollable(parent, bg):
    """خروجی: (قاب بیرونی، بوم، قاب داخلی برای ویجت‌ها، تابع به‌روزرسانی)"""
    outer = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(
        outer, bg=bg, highlightthickness=0, bd=0,
        width=1, height=1, yscrollincrement=20
    )
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    inner = tk.Frame(canvas, bg=bg)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.pack(side="right", fill="both", expand=True)

    state = {"bar": False}

    def refresh(event=None):
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        needed = inner.winfo_reqheight()
        total = max(needed, height)

        canvas.itemconfigure(window_id, width=width, height=total)
        canvas.configure(scrollregion=(0, 0, width, total))

        need_bar = needed > height + 1
        if need_bar and not state["bar"]:
            scrollbar.pack(side="left", fill="y", before=canvas)
            state["bar"] = True
        elif not need_bar and state["bar"]:
            scrollbar.pack_forget()
            state["bar"] = False
            canvas.yview_moveto(0)

    canvas.bind("<Configure>", refresh)
    inner.bind("<Configure>", refresh)
    return outer, canvas, inner, refresh


# -------------------------------
# منوی کناری
# -------------------------------

sidebar = tk.Frame(window, bg="#123B67", width=230)
sidebar.pack(side="right", fill="y")
sidebar.pack_propagate(False)

tk.Label(
    sidebar, text="منوی اصلی",
    font=("Tahoma", 16, "bold"), bg="#123B67", fg="white"
).pack(pady=(14, 8))


# -------------------------------
# فضای نمایش صفحات
# -------------------------------

content_scroll_outer, content_canvas, content, content_refresh = make_scrollable(window, BG)
content_scroll_outer.pack(side="right", fill="both", expand=True)


# -------------------------------
# منو بر اساس نقش کاربر
# -------------------------------

ADMIN_MENUS = [
    "داشبورد",
    "مدیریت دانش آموزان",
    "مدیریت دبیران",
    "کلاس ها",
    "درس ها",
    "نمرات و کارنامه",
    "حضور و غیاب",
    "کاربران",
    "گزارش گیری",
]

TEACHER_MENUS = [
    "داشبورد",
    "حضور و غیاب",
    "نمرات و کارنامه",
    "گزارش گیری",
]

SIDEBAR_BG = "#123B67"

# نوار پایین منو: نام کاربر، تغییر رمز و خروج
bottom_bar = tk.Frame(sidebar, bg=SIDEBAR_BG)
bottom_bar.pack(side="bottom", fill="x", pady=10)

user_label = tk.Label(
    bottom_bar, text="", font=("Tahoma", 10),
    bg=SIDEBAR_BG, fg="#BBDEFB", wraplength=200
)
user_label.pack(pady=5)

menu_scroll_outer, menu_canvas, menu_frame, menu_refresh = make_scrollable(sidebar, SIDEBAR_BG)
menu_scroll_outer.pack(fill="both", expand=True)


def refresh_scroll_areas():
    """بعد از ساخت صفحه یا منو، اندازه‌ی ناحیه‌های پیمایش را دوباره حساب می‌کند."""
    window.after_idle(menu_refresh)
    window.after_idle(content_refresh)


def on_mousewheel(event):
    """چرخ ماوس: منو یا صفحه‌ی زیر اشاره‌گر را پیمایش می‌کند."""
    try:
        widget = window.winfo_containing(event.x_root, event.y_root)
    except Exception:
        return

    target = None
    while widget is not None:
        # جدول‌ها و لیست‌ها پیمایش مخصوص خودشان را دارند
        if widget.winfo_class() in ("Treeview", "Listbox", "Text"):
            return
        if widget is menu_scroll_outer:
            target = menu_canvas
            break
        if widget is content_scroll_outer:
            target = content_canvas
            break
        widget = widget.master

    if target is None:
        return

    first, last = target.yview()
    if first <= 0.0 and last >= 1.0:
        return   # همه‌چیز دیده می‌شود؛ نیازی به پیمایش نیست

    if getattr(event, "num", 0) == 4:
        step = -1
    elif getattr(event, "num", 0) == 5:
        step = 1
    else:
        step = -1 if event.delta > 0 else 1

    target.yview_scroll(step * 3, "units")


def combobox_wheel(event):
    """چرخ ماوس روی لیست‌های کشویی، مقدارشان را عوض نمی‌کند و صفحه را می‌لغزاند."""
    on_mousewheel(event)
    return "break"


window.bind_all("<MouseWheel>", on_mousewheel)
window.bind_all("<Button-4>", on_mousewheel)
window.bind_all("<Button-5>", on_mousewheel)
window.bind_class("TCombobox", "<MouseWheel>", combobox_wheel)


def build_menu():
    for widget in menu_frame.winfo_children():
        widget.destroy()

    items = ADMIN_MENUS if auth["role"] == "admin" else TEACHER_MENUS

    for item in items:
        tk.Button(
            menu_frame, text=item, font=("Tahoma", 11),
            bg=SIDEBAR_BG, fg="white",
            activebackground="#1976D2", activeforeground="white",
            relief="flat", cursor="hand2",
            command=lambda name=item: show_page(name)
        ).pack(fill="x", padx=10, pady=4, ipady=7)

    refresh_scroll_areas()


def change_password_action():
    old = simpledialog.askstring("تغییر رمز", "رمز فعلی:", show="*", parent=window)
    if not old:
        return

    new = simpledialog.askstring(
        "تغییر رمز", "رمز جدید (حداقل ۸ نویسه):", show="*", parent=window
    )
    if not new:
        return

    if len(new) < 8:
        messagebox.showwarning("خطا", "رمز جدید حداقل ۸ نویسه باشد.")
        return

    again = simpledialog.askstring("تغییر رمز", "تکرار رمز جدید:", show="*", parent=window)
    if new != again:
        messagebox.showwarning("خطا", "تکرار رمز با رمز جدید یکسان نیست.")
        return

    try:
        result = api_request(
            "/auth/change-password", method="POST",
            data={"old_password": old, "new_password": new}
        )
        messagebox.showinfo("نتیجه", result["message"])
    except Exception as error:
        messagebox.showerror("خطا", error_text(error))


tk.Button(
    bottom_bar, text="تغییر رمز عبور", font=("Tahoma", 10),
    bg="#1E5A94", fg="white", activebackground="#1976D2",
    activeforeground="white", relief="flat", cursor="hand2",
    command=change_password_action
).pack(fill="x", padx=10, pady=3, ipady=4)

tk.Button(
    bottom_bar, text="خروج از حساب", font=("Tahoma", 10),
    bg="#8E2A2A", fg="white", activebackground="#C62828",
    activeforeground="white", relief="flat", cursor="hand2",
    command=lambda: logout_action()
).pack(fill="x", padx=10, pady=3, ipady=4)


# -------------------------------
# صفحه ورود
# -------------------------------

login_frame = tk.Frame(window, bg=BG)

login_card = tk.Frame(login_frame, bg="white", padx=45, pady=35)
login_card.place(relx=0.5, rely=0.42, anchor="center")

tk.Label(
    login_card, text=APP_NAME,
    font=("Tahoma", 18, "bold"), bg="white", fg=BLUE
).pack(pady=(0, 4))

tk.Label(
    login_card, text="ورود به سامانه",
    font=("Tahoma", 12), bg="white", fg="#546E7A"
).pack(pady=(0, 18))

tk.Label(login_card, text="نام کاربری", bg="white", font=("Tahoma", 11)).pack(anchor="e")
login_username = tk.Entry(login_card, font=("Tahoma", 12), width=26, justify="center")
login_username.pack(pady=(2, 12), ipady=3)

tk.Label(login_card, text="رمز عبور", bg="white", font=("Tahoma", 11)).pack(anchor="e")
login_password = tk.Entry(login_card, font=("Tahoma", 12), width=26, show="*", justify="center")
login_password.pack(pady=(2, 8), ipady=3)

login_error = tk.Label(
    login_card, text="", bg="white", fg="#C62828",
    font=("Tahoma", 10), wraplength=300
)
login_error.pack(pady=4)


def show_login(message=""):
    clear_content()

    for widget in menu_frame.winfo_children():
        widget.destroy()

    user_label.config(text="")
    login_password.delete(0, tk.END)
    login_error.config(text=message)

    login_frame.place(x=0, y=0, relwidth=1, relheight=1)
    login_frame.lift()
    login_username.focus_set()


def do_login(event=None):
    username = login_username.get().strip()
    password = login_password.get()

    if not username or not password:
        login_error.config(text="نام کاربری و رمز عبور را وارد کنید.")
        return

    try:
        result = api_request(
            "/auth/login", method="POST",
            data={"username": username, "password": password}
        )
    except Exception as error:
        login_error.config(text=error_text(error))
        return

    auth.update(
        token=result["token"], role=result["role"],
        name=result["full_name"], username=result["username"]
    )

    login_password.delete(0, tk.END)
    login_error.config(text="")
    login_frame.place_forget()

    user_label.config(
        text="%s (%s)" % (auth["name"], ROLE_LABELS.get(auth["role"], ""))
    )
    build_menu()
    show_page("داشبورد")


def reset_auth():
    auth.update(token=None, role=None, name=None, username=None)


def logout_action():
    try:
        api_request("/auth/logout", method="POST")
    except Exception:
        pass   # حتی اگر سرور در دسترس نباشد، خروج محلی انجام می‌شود

    reset_auth()
    show_login()


def force_logout():
    """وقتی سرور نشست را نپذیرد (منقضی یا غیرفعال) صدا زده می‌شود."""
    if auth["token"] is None:
        return

    reset_auth()
    show_login("نشست شما به پایان رسید. دوباره وارد شوید.")


tk.Button(
    login_card, text="ورود", font=("Tahoma", 12, "bold"),
    bg=BLUE, fg="white", activebackground="#1976D2",
    activeforeground="white", relief="flat", cursor="hand2",
    command=do_login
).pack(fill="x", pady=(10, 0), ipady=5)

login_username.bind("<Return>", lambda e: login_password.focus_set())
login_password.bind("<Return>", do_login)


# -------------------------------
# شروع برنامه
# -------------------------------

show_login()

window.mainloop()
