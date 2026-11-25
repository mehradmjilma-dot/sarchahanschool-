"""سرور مدیریت هوشمند مدرسه سرچهان (FastAPI + SQLite)

اجرا:
    pip install fastapi uvicorn
    python main.py                      (یا F5 در IDLE)
    python -m uvicorn main:app --port 8000
تعیین/بازنشانی رمز مدیر (رمز دلخواه):
    python main.py --reset-admin
    python main.py --reset-admin MyPassword123
مستندات خودکار: http://127.0.0.1:8000/docs
"""
import hashlib
import os
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("SCHOOL_DB_PATH", "school.db")
app = FastAPI(title="Sarchahan Smart School Management")

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    student_code TEXT NOT NULL UNIQUE,
    phone TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    teacher_code TEXT NOT NULL UNIQUE,
    phone TEXT DEFAULT '',
    subject TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    grade TEXT DEFAULT '',
    teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS class_students (
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    PRIMARY KEY (class_id, student_id)
);
CREATE TABLE IF NOT EXISTS attendance (
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present','absent','late','excused')),
    PRIMARY KEY (class_id, student_id, date)
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('admin','teacher')),
    teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    grade TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    subject TEXT NOT NULL,
    term TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 20)
);
"""


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        raise HTTPException(409, "داده تکراری است یا مرجع نامعتبر دارد") from error
    finally:
        conn.close()


with db() as _conn:
    _conn.executescript(SCHEMA)


# ---------- مدل‌ها ----------

class StudentIn(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    student_code: str = Field(min_length=1)
    phone: str = ""


class TeacherIn(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    teacher_code: str = Field(min_length=1)
    phone: str = ""
    subject: str = ""


class ClassIn(BaseModel):
    name: str = Field(min_length=1)
    grade: str = ""
    teacher_id: Optional[int] = None


class AttendanceRecord(BaseModel):
    student_code: str
    status: Literal["present", "absent", "late", "excused"]


class AttendanceIn(BaseModel):
    class_id: int
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")  # مثلاً 1405-08-28
    records: List[AttendanceRecord]


class SubjectIn(BaseModel):
    name: str = Field(min_length=1)
    grade: str = ""


class GradeIn(BaseModel):
    student_code: str
    class_id: Optional[int] = None
    subject: str = Field(min_length=1)
    term: str = Field(min_length=1)
    score: float = Field(ge=0, le=20)


# ---------- توابع کمکی ----------

def student_id(conn, code: str) -> int:
    row = conn.execute(
        "SELECT id FROM students WHERE student_code = ?", (code,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "دانش‌آموز پیدا نشد")
    return row["id"]


def normalize_name(text: str) -> str:
    """ی/ک عربی را فارسی می‌کند و فاصله‌های اضافه را برمی‌دارد."""
    text = text.replace("ي", "ی").replace("ك", "ک")
    return " ".join(text.split())


def rows(cursor) -> list:
    return [dict(r) for r in cursor.fetchall()]


# ---------- احراز هویت و نقش‌ها ----------

SESSION_SECONDS = 12 * 60 * 60
PBKDF2_ITERATIONS = 200000
FAILED_LOGINS = {}   # نام کاربری -> (تعداد خطا، زمان پایان قفل)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2$%d$%s$%s" % (PBKDF2_ITERATIONS, salt.hex(), digest.hex())


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "ابتدا وارد شوید")
    return authorization[7:].strip()


def current_user(authorization: Optional[str] = Header(None)) -> dict:
    digest = token_hash(bearer_token(authorization))
    with db() as conn:
        row = conn.execute(
            "SELECT u.id, u.username, u.full_name, u.role, u.teacher_id,"
            " u.active, s.expires_at FROM sessions s"
            " JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (digest,)).fetchone()
    if row is None or row["expires_at"] < time.time() or not row["active"]:
        raise HTTPException(401, "نشست شما منقضی شده است. دوباره وارد شوید")
    return dict(row)


def require_roles(*roles):
    def checker(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "شما اجازه انجام این کار را ندارید")
        return user
    return checker


ANY = Depends(current_user)                         # هر کاربر واردشده
STAFF = Depends(require_roles("admin", "teacher"))  # مدیر یا دبیر
ADMIN = Depends(require_roles("admin"))             # فقط مدیر


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class UserIn(BaseModel):
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)
    full_name: str = ""
    role: Literal["admin", "teacher"]
    teacher_code: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: str = ""
    role: Literal["admin", "teacher"]
    active: bool = True
    teacher_code: Optional[str] = None


class PasswordResetIn(BaseModel):
    password: str = Field(min_length=8)


@app.post("/auth/login")
def login(body: LoginIn):
    key = body.username.strip().lower()
    now = time.time()

    count, locked_until = FAILED_LOGINS.get(key, (0, 0))
    if locked_until > now:
        raise HTTPException(
            429, "تلاش‌های ناموفق زیاد بود. چند دقیقه بعد دوباره امتحان کنید")
    if locked_until and locked_until <= now:
        count = 0

    with db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (key,)).fetchone()
        ok = (user is not None and user["active"]
              and verify_password(body.password, user["password_hash"]))

        if not ok:
            count += 1
            FAILED_LOGINS[key] = (count, now + 300 if count >= 5 else 0)
            raise HTTPException(401, "نام کاربری یا رمز عبور اشتباه است")

        FAILED_LOGINS.pop(key, None)
        token = secrets.token_urlsafe(32)
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(now),))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at)"
            " VALUES (?, ?, ?)",
            (token_hash(token), user["id"], int(now) + SESSION_SECONDS))

    return {"token": token, "role": user["role"],
            "full_name": user["full_name"] or user["username"],
            "username": user["username"]}


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    digest = token_hash(bearer_token(authorization))
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))
    return {"message": "خروج انجام شد"}


@app.get("/auth/me")
def me(user: dict = ANY):
    return {"username": user["username"], "role": user["role"],
            "full_name": user["full_name"]}


@app.post("/auth/change-password")
def change_password(body: PasswordChangeIn,
                    authorization: Optional[str] = Header(None),
                    user: dict = ANY):
    with db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user["id"],)).fetchone()
        if not verify_password(body.old_password, row["password_hash"]):
            raise HTTPException(400, "رمز فعلی اشتباه است")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (hash_password(body.new_password), user["id"]))
        # بقیه نشست‌های این کاربر بسته می‌شود
        conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?",
            (user["id"], token_hash(bearer_token(authorization))))
    return {"message": "رمز عبور تغییر کرد"}


# ---------- مدیریت کاربران (فقط مدیر) ----------

def teacher_id_from_code(conn, code: Optional[str]) -> Optional[int]:
    if not code:
        return None
    row = conn.execute(
        "SELECT id FROM teachers WHERE teacher_code = ?", (code,)).fetchone()
    if row is None:
        raise HTTPException(404, "دبیر پیدا نشد")
    return row["id"]


def check_last_admin(conn, user_id: int):
    """حداقل یک مدیر فعال دیگر باید باقی بماند."""
    others = conn.execute(
        "SELECT COUNT(*) FROM users"
        " WHERE role = 'admin' AND active = 1 AND id != ?",
        (user_id,)).fetchone()[0]
    if others == 0:
        raise HTTPException(409, "حداقل یک مدیر فعال باید باقی بماند")


@app.get("/users")
def list_users(user: dict = ADMIN):
    with db() as conn:
        return {"users": rows(conn.execute("""
            SELECT u.id, u.username, u.full_name, u.role, u.active,
                   t.teacher_code,
                   t.first_name || ' ' || t.last_name AS teacher_name
            FROM users u LEFT JOIN teachers t ON t.id = u.teacher_id
            ORDER BY u.role, u.username"""))}


@app.post("/users", status_code=201)
def create_user(u: UserIn, user: dict = ADMIN):
    with db() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role,"
            " teacher_id) VALUES (?, ?, ?, ?, ?)",
            (u.username.strip().lower(), hash_password(u.password),
             normalize_name(u.full_name), u.role,
             teacher_id_from_code(conn, u.teacher_code)))
    return {"message": "کاربر ساخته شد"}


@app.put("/users/{user_id}")
def update_user(user_id: int, u: UserUpdate, user: dict = ADMIN):
    with db() as conn:
        target = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            raise HTTPException(404, "کاربر پیدا نشد")

        loses_admin = target["role"] == "admin" and target["active"] and (
            u.role != "admin" or not u.active)
        if loses_admin:
            if user_id == user["id"]:
                raise HTTPException(
                    409, "نمی‌توانید نقش یا وضعیت حساب خودتان را کاهش دهید")
            check_last_admin(conn, user_id)

        conn.execute(
            "UPDATE users SET full_name = ?, role = ?, active = ?,"
            " teacher_id = ? WHERE id = ?",
            (normalize_name(u.full_name), u.role, int(u.active),
             teacher_id_from_code(conn, u.teacher_code), user_id))
        if not u.active or u.role != target["role"]:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return {"message": "کاربر ویرایش شد"}


@app.put("/users/{user_id}/password")
def reset_user_password(user_id: int, body: PasswordResetIn,
                        user: dict = ADMIN):
    with db() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(body.password), user_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "کاربر پیدا نشد")
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return {"message": "رمز عبور کاربر تغییر کرد"}


@app.delete("/users/{user_id}")
def delete_user(user_id: int, user: dict = ADMIN):
    if user_id == user["id"]:
        raise HTTPException(409, "نمی‌توانید حساب خودتان را حذف کنید")
    with db() as conn:
        target = conn.execute(
            "SELECT role, active FROM users WHERE id = ?",
            (user_id,)).fetchone()
        if target is None:
            raise HTTPException(404, "کاربر پیدا نشد")
        if target["role"] == "admin" and target["active"]:
            check_last_admin(conn, user_id)
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"message": "کاربر حذف شد"}


def ensure_first_admin():
    """اگر هیچ کاربری نباشد، یک مدیر با رمز تصادفی ساخته می‌شود."""
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return
        # برنامه‌ی نصبی رمز را از کاربر می‌پرسد و از این راه می‌دهد
        chosen = os.environ.pop("SCHOOL_ADMIN_PASSWORD", None)
        password = chosen or secrets.token_urlsafe(9)
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role)"
            " VALUES ('admin', ?, 'مدیر سیستم', 'admin')",
            (hash_password(password),))
    if not chosen:
        print("=" * 56)
        print("FIRST RUN: admin account created")
        print("   username: admin")
        print("   password: %s" % password)
        print("Log in and change this password right away.")
        print("=" * 56)


ensure_first_admin()


def set_admin_password(new_password: str):
    """رمز حساب admin را تعیین می‌کند (و همه نشست‌های باز را می‌بندد)."""
    with db() as conn:
        conn.execute("DELETE FROM sessions")
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, active = 1"
            " WHERE username = 'admin'", (hash_password(new_password),))
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role)"
                " VALUES ('admin', ?, 'مدیر سیستم', 'admin')",
                (hash_password(new_password),))


# ---------- دانش‌آموزان ----------

@app.get("/students", dependencies=[ANY])
def list_students():
    with db() as conn:
        return {"students": rows(conn.execute(
            "SELECT * FROM students ORDER BY last_name, first_name"))}


@app.post("/students", status_code=201, dependencies=[ADMIN])
def create_student(s: StudentIn):
    with db() as conn:
        conn.execute(
            "INSERT INTO students (first_name, last_name, student_code, phone)"
            " VALUES (?, ?, ?, ?)",
            (s.first_name, s.last_name, s.student_code, s.phone))
    return {"message": "دانش‌آموز با موفقیت ثبت شد"}


@app.put("/students/{code}", dependencies=[ADMIN])
def update_student(code: str, s: StudentIn):
    with db() as conn:
        cur = conn.execute(
            "UPDATE students SET first_name=?, last_name=?, phone=?"
            " WHERE student_code=?",
            (s.first_name, s.last_name, s.phone, code))
        if cur.rowcount == 0:
            raise HTTPException(404, "دانش‌آموز پیدا نشد")
    return {"message": "اطلاعات دانش‌آموز ویرایش شد"}


@app.delete("/students/{code}", dependencies=[ADMIN])
def delete_student(code: str):
    with db() as conn:
        cur = conn.execute("DELETE FROM students WHERE student_code=?", (code,))
        if cur.rowcount == 0:
            raise HTTPException(404, "دانش‌آموز پیدا نشد")
    return {"message": "دانش‌آموز حذف شد"}


# ---------- دبیران ----------

@app.get("/teachers", dependencies=[ANY])
def list_teachers():
    with db() as conn:
        return {"teachers": rows(conn.execute(
            "SELECT * FROM teachers ORDER BY last_name, first_name"))}


@app.post("/teachers", status_code=201, dependencies=[ADMIN])
def create_teacher(t: TeacherIn):
    with db() as conn:
        conn.execute(
            "INSERT INTO teachers (first_name, last_name, teacher_code, phone, subject)"
            " VALUES (?, ?, ?, ?, ?)",
            (t.first_name, t.last_name, t.teacher_code, t.phone, t.subject))
    return {"message": "دبیر با موفقیت ثبت شد"}


@app.put("/teachers/{code}", dependencies=[ADMIN])
def update_teacher(code: str, t: TeacherIn):
    with db() as conn:
        cur = conn.execute(
            "UPDATE teachers SET first_name=?, last_name=?, phone=?, subject=?"
            " WHERE teacher_code=?",
            (t.first_name, t.last_name, t.phone, t.subject, code))
        if cur.rowcount == 0:
            raise HTTPException(404, "دبیر پیدا نشد")
    return {"message": "اطلاعات دبیر ویرایش شد"}


@app.delete("/teachers/{code}", dependencies=[ADMIN])
def delete_teacher(code: str):
    with db() as conn:
        cur = conn.execute("DELETE FROM teachers WHERE teacher_code=?", (code,))
        if cur.rowcount == 0:
            raise HTTPException(404, "دبیر پیدا نشد")
    return {"message": "دبیر حذف شد"}


# ---------- کلاس‌ها ----------

@app.get("/classes")
def list_classes(user: dict = ANY):
    """مدیر همه کلاس‌ها را می‌بیند؛ دبیر فقط کلاس‌های خودش را."""
    query = """
        SELECT c.id, c.name, c.grade, c.teacher_id,
               t.first_name || ' ' || t.last_name AS teacher_name,
               (SELECT COUNT(*) FROM class_students cs
                 WHERE cs.class_id = c.id) AS student_count
        FROM classes c LEFT JOIN teachers t ON t.id = c.teacher_id"""
    params: list = []
    if user["role"] == "teacher":
        query += " WHERE c.teacher_id = ?"
        params.append(user["teacher_id"])
    query += " ORDER BY c.name"
    with db() as conn:
        return {"classes": rows(conn.execute(query, params))}


@app.post("/classes", status_code=201, dependencies=[ADMIN])
def create_class(c: ClassIn):
    with db() as conn:
        conn.execute(
            "INSERT INTO classes (name, grade, teacher_id) VALUES (?, ?, ?)",
            (c.name, c.grade, c.teacher_id))
    return {"message": "کلاس با موفقیت ایجاد شد"}


@app.delete("/classes/{class_id}", dependencies=[ADMIN])
def delete_class(class_id: int):
    with db() as conn:
        cur = conn.execute("DELETE FROM classes WHERE id=?", (class_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "کلاس پیدا نشد")
    return {"message": "کلاس حذف شد"}


@app.get("/classes/{class_id}/students", dependencies=[ANY])
def class_students(class_id: int):
    with db() as conn:
        return {"students": rows(conn.execute("""
            SELECT s.* FROM students s
            JOIN class_students cs ON cs.student_id = s.id
            WHERE cs.class_id = ? ORDER BY s.last_name, s.first_name""",
            (class_id,)))}


@app.post("/classes/{class_id}/students/{code}", status_code=201, dependencies=[ADMIN])
def add_to_class(class_id: int, code: str):
    with db() as conn:
        conn.execute(
            "INSERT INTO class_students (class_id, student_id) VALUES (?, ?)",
            (class_id, student_id(conn, code)))
    return {"message": "دانش‌آموز به کلاس اضافه شد"}


@app.delete("/classes/{class_id}/students/{code}", dependencies=[ADMIN])
def remove_from_class(class_id: int, code: str):
    with db() as conn:
        conn.execute(
            "DELETE FROM class_students WHERE class_id=? AND student_id=?",
            (class_id, student_id(conn, code)))
    return {"message": "دانش‌آموز از کلاس حذف شد"}


# ---------- حضور و غیاب ----------

@app.post("/attendance")
def save_attendance(a: AttendanceIn, user: dict = STAFF):
    """ثبت یا بروزرسانی حضور و غیاب یک کلاس در یک روز."""
    with db() as conn:
        if user["role"] == "teacher":
            owner = conn.execute(
                "SELECT teacher_id FROM classes WHERE id = ?",
                (a.class_id,)).fetchone()
            if owner is None:
                raise HTTPException(404, "کلاس پیدا نشد")
            if user["teacher_id"] is None or owner["teacher_id"] != user["teacher_id"]:
                raise HTTPException(
                    403, "فقط برای کلاس‌های خودتان می‌توانید حضور و غیاب ثبت کنید")
        for r in a.records:
            conn.execute(
                "INSERT INTO attendance (class_id, student_id, date, status)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(class_id, student_id, date)"
                " DO UPDATE SET status = excluded.status",
                (a.class_id, student_id(conn, r.student_code), a.date, r.status))
    return {"message": "حضور و غیاب ثبت شد"}


@app.get("/attendance", dependencies=[ANY])
def get_attendance(class_id: int, date: str):
    with db() as conn:
        return {"records": rows(conn.execute("""
            SELECT s.student_code, s.first_name, s.last_name, a.status
            FROM attendance a JOIN students s ON s.id = a.student_id
            WHERE a.class_id = ? AND a.date = ?
            ORDER BY s.last_name""", (class_id, date)))}


# ---------- درس‌ها ----------

@app.get("/subjects", dependencies=[ANY])
def list_subjects():
    with db() as conn:
        return {"subjects": rows(conn.execute(
            "SELECT * FROM subjects ORDER BY grade, name"))}


@app.post("/subjects", status_code=201, dependencies=[ADMIN])
def create_subject(sub: SubjectIn):
    with db() as conn:
        conn.execute(
            "INSERT INTO subjects (name, grade) VALUES (?, ?)",
            (normalize_name(sub.name), normalize_name(sub.grade)))
    return {"message": "درس با موفقیت ثبت شد"}


@app.put("/subjects/{subject_id}", dependencies=[ADMIN])
def update_subject(subject_id: int, sub: SubjectIn):
    """با تغییر نام درس، نام آن در نمره‌های قبلی هم به‌روز می‌شود."""
    name = normalize_name(sub.name)
    with db() as conn:
        old = conn.execute(
            "SELECT name FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if old is None:
            raise HTTPException(404, "درس پیدا نشد")
        conn.execute(
            "UPDATE subjects SET name = ?, grade = ? WHERE id = ?",
            (name, normalize_name(sub.grade), subject_id))
        conn.execute(
            "UPDATE grades SET subject = ? WHERE subject = ?",
            (name, old["name"]))
    return {"message": "درس ویرایش شد"}


@app.delete("/subjects/{subject_id}", dependencies=[ADMIN])
def delete_subject(subject_id: int):
    with db() as conn:
        row = conn.execute(
            "SELECT name FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "درس پیدا نشد")
        used = conn.execute(
            "SELECT COUNT(*) FROM grades WHERE subject = ?",
            (row["name"],)).fetchone()[0]
        if used:
            raise HTTPException(
                409, "برای این درس %d نمره ثبت شده و حذف آن ممکن نیست" % used)
        conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    return {"message": "درس حذف شد"}


# ---------- نمرات و کارنامه ----------

@app.post("/grades", status_code=201, dependencies=[STAFF])
def add_grade(g: GradeIn):
    subject = normalize_name(g.subject)
    with db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM subjects WHERE name = ?", (subject,)).fetchone()
        if exists is None:
            raise HTTPException(400, "این درس تعریف نشده است")
        conn.execute(
            "INSERT INTO grades (student_id, class_id, subject, term, score)"
            " VALUES (?, ?, ?, ?, ?)",
            (student_id(conn, g.student_code), g.class_id,
             subject, normalize_name(g.term), g.score))
    return {"message": "نمره ثبت شد"}


@app.get("/students/{code}/report", dependencies=[ANY])
def report_card(code: str, term: Optional[str] = None):
    """کارنامه: میانگین نمره هر درس + خلاصه غیبت."""
    with db() as conn:
        sid = student_id(conn, code)
        student = dict(conn.execute(
            "SELECT first_name, last_name, student_code FROM students"
            " WHERE id = ?", (sid,)).fetchone())
        classes = [r["name"] for r in conn.execute(
            "SELECT c.name FROM classes c"
            " JOIN class_students cs ON cs.class_id = c.id"
            " WHERE cs.student_id = ? ORDER BY c.name", (sid,))]

        query = ("SELECT subject, term, ROUND(AVG(score), 2) AS average"
                 " FROM grades WHERE student_id = ?")
        params: list = [sid]
        if term:
            query += " AND term = ?"
            params.append(term)
        query += " GROUP BY subject, term ORDER BY term, subject"
        subjects = rows(conn.execute(query, params))

        # میانگین هر درس در بین همه‌ی هم‌کلاسی‌ها (برای مقایسه در نمودار)
        class_query = (
            "SELECT g.subject, g.term, ROUND(AVG(g.score), 2) AS average"
            " FROM grades g WHERE g.student_id IN ("
            "   SELECT DISTINCT cs2.student_id FROM class_students cs1"
            "   JOIN class_students cs2 ON cs2.class_id = cs1.class_id"
            "   WHERE cs1.student_id = ?)")
        class_params: list = [sid]
        if term:
            class_query += " AND g.term = ?"
            class_params.append(term)
        class_query += " GROUP BY g.subject, g.term"
        class_averages = rows(conn.execute(class_query, class_params))

        absences = rows(conn.execute(
            "SELECT status, COUNT(*) AS count FROM attendance"
            " WHERE student_id = ? GROUP BY status", (sid,)))

    overall = (round(sum(s["average"] for s in subjects) / len(subjects), 2)
               if subjects else None)
    return {"student": student, "classes": classes,
            "subjects": subjects, "class_averages": class_averages,
            "overall_average": overall, "attendance": absences}


@app.get("/terms", dependencies=[ANY])
def list_terms():
    """نیم‌سال‌هایی که تا حالا برایشان نمره ثبت شده است."""
    with db() as conn:
        return {"terms": [r["term"] for r in conn.execute(
            "SELECT DISTINCT term FROM grades ORDER BY term")]}


@app.get("/students/{code}/grades", dependencies=[ANY])
def list_grades(code: str, term: Optional[str] = None):
    """همه نمره‌های ثبت‌شده‌ی یک دانش‌آموز (با شناسه، برای حذف/ویرایش)."""
    with db() as conn:
        sid = student_id(conn, code)
        query = ("SELECT g.id, g.subject, g.term, g.score, c.name AS class_name"
                 " FROM grades g LEFT JOIN classes c ON c.id = g.class_id"
                 " WHERE g.student_id = ?")
        params: list = [sid]
        if term:
            query += " AND g.term = ?"
            params.append(term)
        query += " ORDER BY g.term, g.subject, g.id"
        return {"grades": rows(conn.execute(query, params))}


@app.delete("/grades/{grade_id}", dependencies=[STAFF])
def delete_grade(grade_id: int):
    with db() as conn:
        cur = conn.execute("DELETE FROM grades WHERE id = ?", (grade_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "نمره پیدا نشد")
    return {"message": "نمره حذف شد"}


# ---------- آمار داشبورد ----------

@app.get("/stats", dependencies=[ANY])
def stats():
    with db() as conn:
        one = lambda q: conn.execute(q).fetchone()[0]  # noqa: E731
        return {
            "students": one("SELECT COUNT(*) FROM students"),
            "teachers": one("SELECT COUNT(*) FROM teachers"),
            "classes": one("SELECT COUNT(*) FROM classes"),
        }


if __name__ == "__main__":
    import sys

    if "--reset-admin" in sys.argv:
        # رمز دلخواه: یا بعد از --reset-admin نوشته می‌شود یا از شما پرسیده می‌شود
        extra = [a for a in sys.argv[1:] if a != "--reset-admin"]
        if extra:
            new_password = extra[0]
        else:
            new_password = input(
                "Enter a new admin password (at least 8 characters): ").strip()

        if len(new_password) < 8:
            print("Password is too short (minimum 8 characters). Nothing changed.")
        else:
            set_admin_password(new_password)
            print("Done. Log in with username: admin and the password you chose.")
    else:
        # اجرای مستقیم (مثلاً با F5 در IDLE یا python main.py)
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=8000)
