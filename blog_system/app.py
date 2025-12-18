from datetime import datetime
from typing import Optional

import markdown

import logging

logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


import sqlite3
import uvicorn
from fastapi import (
    FastAPI,
    Request,
    Form,
    HTTPException,
    Depends,
    status,
    Response,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ----------------------- НАСТРОЙКА ПРИЛОЖЕНИЯ -----------------------

app = FastAPI(title="Blog API", description="Simple blog system with DB")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_PATH = "blog.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    # Проверяем, есть ли админ
    cur = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    row = cur.fetchone()
    if row is None:
        now = datetime.now().isoformat(sep=" ", timespec="seconds")
        conn.execute(
            """
            INSERT INTO users (login, email, password, role, createdAt, updatedAt)
            VALUES (?, ?, ?, 'admin', ?, ?)
            """,
            ("admin", "admin@example.com", "admin", now, now),
        )
        print("Создан пользователь-админ: login=admin, password=admin")

    conn.execute("UPDATE users SET role = 'admin' WHERE login = 'wow'")

    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()


# ----------------------- АУТНТИФИКАЦИЯ  -----------------------------


def get_current_user_id(request: Request) -> Optional[int]:
    user_id = request.cookies.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except ValueError:
        return None


from fastapi import status
from fastapi.responses import RedirectResponse


def require_auth(request: Request) -> int:
    user_id = get_current_user_id(request)
    if not user_id:
        # если не залогинен – редирект на /login
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Not authenticated",
            headers={"Location": "/login"},
        )
    return user_id


def get_current_user(request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return None
    user = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return user


# ----------------------- УТИЛИТЫ ДЛЯ БД -----------------------------


def fetch_one(query: str, params=()):
    conn = get_db()
    cur = conn.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row


def fetch_all(query: str, params=()):
    conn = get_db()
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def execute(query: str, params=()):
    conn = get_db()
    cur = conn.execute(query, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


# ----------------------- РЕГИСТРАЦИЯ / ЛОГИН ------------------------


@app.get("/register", response_class=HTMLResponse)
async def show_register(request: Request):
    return templates.TemplateResponse(
        "register.html", {"request": request, "error": None}
    )


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    login: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if not login or not email or not password:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Все поля обязательны",
            },
        )

    existing_login = fetch_one("SELECT id FROM users WHERE login = ?", (login,))
    existing_email = fetch_one("SELECT id FROM users WHERE email = ?", (email,))
    if existing_login:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Логин уже занят",
            },
        )
    if existing_email:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Email уже используется",
            },
        )

    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    execute(
        """
        INSERT INTO users (login, email, password, role, createdAt, updatedAt)
        VALUES (?, ?, ?, 'user', ?, ?)
        """,
        (login, email, password, now, now),
    )

    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
async def show_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
):
    # Поискк пользователя по логину
    user = fetch_one(
        "SELECT id, password FROM users WHERE login = ?",
        (login,),
    )

    # Если не нашли
    if user is None or str(user["password"]) != password:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Неверный логин или пароль",
            },
        )

    resp = RedirectResponse(url="/", status_code=303)
    resp.set_cookie("user_id", str(user["id"]))
    logging.info(f"User {login} (ID: {user['id']}) logged in")
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("user_id")
    return resp


# ----------------------- ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ -----------------------


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    user_id = require_auth(request)
    user = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse(
        "profile.html", {"request": request, "user": user, "error": None}
    )


@app.post("/profile", response_class=HTMLResponse)
async def update_profile(
    request: Request,
    login: str = Form(...),
    email: str = Form(...),
):
    user_id = require_auth(request)
    if not login or not email:
        user = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "Все поля обязательны",
            },
        )

    existing_login = fetch_one(
        "SELECT id FROM users WHERE login = ? AND id != ?",
        (login, user_id),
    )
    existing_email = fetch_one(
        "SELECT id FROM users WHERE email = ? AND id != ?",
        (email, user_id),
    )
    if existing_login:
        user = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "Логин уже занят",
            },
        )
    if existing_email:
        user = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "user": user,
                "error": "Email уже используется",
            },
        )

    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    execute(
        "UPDATE users SET login = ?, email = ?, updatedAt = ? WHERE id = ?",
        (login, email, now, user_id),
    )

    user = fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "user": user, "error": "Профиль обновлён"},
    )


# ----------------------- ГЛАВНАЯ И ПОИСК ----------------------------


POSTS_PER_PAGE = 5
# Ограничение количества постов на странице (по красоте штобы)


@app.get("/", response_class=HTMLResponse)
async def main_page(
    request: Request,
    q: str | None = None,
    page: int = 1,
):
    user_id = get_current_user_id(request)

    if page < 1:
        page = 1

    offset = (page - 1) * POSTS_PER_PAGE

    params = []
    where = ""
    if q:
        like = f"%{q}%"
        where = "WHERE p.title LIKE ? OR p.content LIKE ?"
        params.extend([like, like])

    # Подсчет кол-ва постов на странице
    count_row = fetch_one(
        f"""
        SELECT COUNT(* ) as cnt
        FROM posts p
        {where}
        """,
        tuple(params),
    )
    total = count_row["cnt"] if count_row else 0

    # Получаем конкретную страницу
    posts = fetch_all(
        f"""
        SELECT p.*, u.login AS authorName
        FROM posts p
        JOIN users u ON p.authorId = u.id
        {where}
        ORDER BY p.createdAt DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [POSTS_PER_PAGE, offset]),
    )

    has_prev = page > 1
    has_next = offset + POSTS_PER_PAGE < total

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "posts": posts,
            "current_user_id": user_id,
            "query": q,
            "page": page,
            "has_prev": has_prev,
            "has_next": has_next,
        },
    )


@app.get("/users", response_class=HTMLResponse)
async def search_users(request: Request, q: str | None = None):
    if q:
        like = f"%{q}%"
        users = fetch_all(
            "SELECT * FROM users WHERE login LIKE ? OR email LIKE ? ORDER BY createdAt DESC",
            (like, like),
        )
    else:
        users = fetch_all("SELECT * FROM users ORDER BY createdAt DESC")

    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users, "query": q},
    )


# ----------------------- ПОСТЫ --------------------------------------


@app.get("/create-post", response_class=HTMLResponse)
async def show_create_post_form(request: Request):
    user_id = require_auth(request)

    # Автор может только сам себя выбрать
    user = fetch_one("SELECT id, login, email FROM users WHERE id = ?", (user_id,))
    users = [user] if user else []

    return templates.TemplateResponse(
        "create_post.html", {"request": request, "users": users, "error": None}
    )


@app.post("/create-post", response_class=HTMLResponse)
async def create_post_html(
    request: Request,
    authorId: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
):
    user_id = require_auth(request)

    if user_id != authorId:
        raise HTTPException(
            status_code=403, detail="Можно создавать посты только от себя"
        )

    if not title or not content:
        user = fetch_one("SELECT id, login, email FROM users WHERE id = ?", (user_id,))
        return templates.TemplateResponse(
            "create_post.html",
            {
                "request": request,
                "users": [user],
                "error": "Заполните все поля",
            },
        )

    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    execute(
        """
        INSERT INTO posts (authorId, title, content, createdAt, updatedAt)
        VALUES (?, ?, ?, ?, ?)
        """,
        (authorId, title, content, now, now),
    )

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/post/{post_id}", response_class=HTMLResponse)
async def view_post(request: Request, post_id: int):
    user_id = get_current_user_id(request)

    post = fetch_one(
        """
        SELECT p.*, u.login AS authorName
        FROM posts p
        JOIN users u ON p.authorId = u.id
        WHERE p.id = ?
        """,
        (post_id,),
    )
    if not post:
        execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))
        raise HTTPException(status_code=404, detail="Post not found")

    comments = fetch_all(
        """
        SELECT c.*, u.login AS authorName
        FROM comments c
        JOIN users u ON c.userId = u.id
        WHERE c.postId = ?
        ORDER BY c.createdAt ASC
        """,
        (post_id,),
    )

    saved = False
    if user_id:
        row = fetch_one(
            "SELECT 1 FROM saved_posts WHERE userId = ? AND postId = ?",
            (user_id, post_id),
        )
        saved = bool(row)

    role = None
    if user_id:
        row = fetch_one("SELECT role FROM users WHERE id = ?", (user_id,))
        role = row["role"] if row else None

    post_content = markdown.markdown(post["content"])

    collections = (
        fetch_all("SELECT * FROM collections WHERE userId = ?", (user_id,))
        if user_id
        else []
    )
    return templates.TemplateResponse(
        "post.html",
        {
            "request": request,
            "post": post,
            "post_content": post_content,
            "comments": comments,
            "current_user_id": user_id,
            "is_saved": saved,
            "current_user_role": role,
            "collections": collections,
        },
    )


@app.get("/edit-post/{post_id}", response_class=HTMLResponse)
async def show_edit_post_form(request: Request, post_id: int):
    user_id = require_auth(request)

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    current_user = fetch_one("SELECT role FROM users WHERE id = ?", (user_id,))
    role = current_user["role"] if current_user else "user"

    if post["authorId"] != user_id and role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Можно редактировать только свои посты (кроме админа)",
        )

    user = fetch_one("SELECT id, login, email FROM users WHERE id = ?", (user_id,))
    return templates.TemplateResponse(
        "edit_post.html",
        {"request": request, "post": post, "users": [user], "error": None},
    )


@app.post("/edit-post/{post_id}", response_class=HTMLResponse)
async def edit_post_html(
    request: Request,
    post_id: int,
    authorId: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
):
    user_id = require_auth(request)

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    current_user = fetch_one("SELECT role FROM users WHERE id = ?", (user_id,))
    role = current_user["role"] if current_user else "user"

    if post["authorId"] != user_id and role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Можно редактировать только свои посты (кроме админа)",
        )

    if not title or not content:
        user = fetch_one("SELECT id, login, email FROM users WHERE id = ?", (user_id,))
        return templates.TemplateResponse(
            "edit_post.html",
            {
                "request": request,
                "post": post,
                "users": [user],
                "error": "Заполните все поля",
            },
        )

    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    execute(
        "UPDATE posts SET title = ?, content = ?, updatedAt = ?, authorId = ? WHERE id = ?",
        (title, content, now, authorId, post_id),
    )

    return RedirectResponse(
        url=f"/post/{post_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/post/{post_id}/delete")
async def delete_post(request: Request, post_id: int):
    user_id = require_auth(request)

    post = fetch_one("SELECT * FROM posts WHERE id = ?", (post_id,))
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    current_user = fetch_one("SELECT role FROM users WHERE id = ?", (user_id,))
    role = current_user["role"] if current_user else "user"

    if post["authorId"] != user_id and role != "admin":
        raise HTTPException(
            status_code=403, detail="Можно удалять только свои посты (кроме админа)"
        )

    execute("DELETE FROM posts WHERE id = ?", (post_id,))
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ----------------------- КОММЕНТАРИИ И ИЗБРАННОЕ --------------------


@app.get("/collections", response_class=HTMLResponse)
async def collections_page(request: Request):
    user_id = require_auth(request)
    collections = fetch_all(
        """
                            SELECT c.*,
                            (SELECT COUNT(*) FROM post_collections pc WHERE pc.collectionId = c.id) as post_count
                            FROM collections c
                            WHERE c.userId = ?
                            """,
        (user_id,),
    )

    return templates.TemplateResponse(
        "collections.html", {"request": request, "collections": collections}
    )


@app.post("/collections", response_class=HTMLResponse)
async def create_collection(request: Request, name: str = Form(...)):
    user_id = require_auth(request)
    execute("INSERT INTO collections (userId, name) VALUES (?, ?)", (user_id, name))
    return RedirectResponse(url="/collections", status_code=303)


@app.post("/post/{post_id}/comment")
async def add_comment(
    request: Request,
    post_id: int,
    content: str = Form(...),
):
    user_id = require_auth(request)

    if not content.strip():
        return RedirectResponse(
            url=f"/post/{post_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    execute(
        """
        INSERT INTO comments (postId, userId, content, createdAt, updatedAt)
        VALUES (?, ?, ?, ?, ?)
        """,
        (post_id, user_id, content, now, now),
    )

    return RedirectResponse(
        url=f"/post/{post_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/post/{post_id}/save")
async def save_post(request: Request, post_id: int):
    user_id = require_auth(request)

    row = fetch_one(
        "SELECT 1 FROM saved_posts WHERE userId = ? AND postId = ?",
        (user_id, post_id),
    )
    if not row:
        execute(
            "INSERT INTO saved_posts (userId, postId) VALUES (?, ?)",
            (user_id, post_id),
        )

    return RedirectResponse(
        url=f"/post/{post_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/post/{post_id}/unsave")
async def unsave_post(request: Request, post_id: int):
    user_id = require_auth(request)

    execute(
        "DELETE FROM saved_posts WHERE userId = ? AND postId = ?",
        (user_id, post_id),
    )
    return RedirectResponse(
        url=f"/post/{post_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@app.get("/saved", response_class=HTMLResponse)
async def saved_posts_page(request: Request):
    user_id = require_auth(request)

    posts = fetch_all(
        """
        SELECT p.*, u.login AS authorName
        FROM saved_posts s
        JOIN posts p ON s.postId = p.id
        JOIN users u ON p.authorId = u.id
        WHERE s.userId = ?
        ORDER BY s.savedAt DESC
        """,
        (user_id,),
    )

    return templates.TemplateResponse(
        "saved.html",
        {"request": request, "posts": posts},
    )


@app.post("/post/{post_id}/add-to-collection")
async def add_to_collection(
    request: Request,
    post_id: int,
    collection_id: int = Form(...),
):
    user_id = require_auth(request)
    # Проверка что подборка принадлежит пользователю
    collection = fetch_one(
        "SELECT id FROM collections WHERE id = ? AND userId = ?",
        (collection_id, user_id),
    )
    if not collection:
        raise HTTPException(
            status_code=403, detail="Подборка не найдена или недоступна"
        )
    # Добавление поста в подборку
    execute(
        "INSERT OR IGNORE INTO post_collections (postId, collectionId) VALUES (?, ?)",
        (post_id, collection_id),
    )
    return RedirectResponse(url=f"/post/{post_id}", status_code=303)


# ----------------------- API --------------------------------


@app.get("/api/posts")
async def api_get_posts():
    rows = fetch_all("SELECT * FROM posts ORDER BY createdAt DESC")
    return [dict(r) for r in rows]


@app.get("/api/users")
async def api_get_users():
    rows = fetch_all("SELECT * FROM users ORDER BY createdAt DESC")
    return [dict(r) for r in rows]


@app.get("/collections/{collection_id}", response_class=HTMLResponse)
async def view_collection(request: Request, collection_id: int):
    user_id = require_auth(request)
    collection = fetch_one(
        "SELECT * FROM collections WHERE id = ? AND userId = ?",
        (collection_id, user_id),
    )
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    posts = fetch_all(
        """
        SELECT p.*, u.login AS authorName
        FROM post_collections pc
        JOIN posts p ON pc.postId = p.id
        JOIN users u ON p.authorId = u.id
        WHERE pc.collectionId = ?
    """,
        (collection_id,),
    )
    return templates.TemplateResponse(
        "collection.html",
        {"request": request, "collection": collection, "posts": posts},
    )


@app.post("/collection/{collection_id}/remove-post")
async def remove_from_collection(
    request: Request,
    collection_id: int,
    post_id: int = Form(...),
):
    user_id = require_auth(request)
    collection = fetch_one(
        "SELECT id FROM collections WHERE id = ? AND userId = ?",
        (collection_id, user_id),
    )
    if not collection:
        raise HTTPException(
            status_code=403, detail="Подборка не найдена или недоступна"
        )
    execute(
        "DELETE FROM post_collections WHERE postId = ? AND collectionId = ?",
        (post_id, collection_id),
    )
    return RedirectResponse(url=f"/collections/{collection_id}", status_code=303)


@app.post("/collections/{collection_id}/delete")
async def delete_collection(
    request: Request,
    collection_id: int,
):
    user_id = require_auth(request)
    collection = fetch_one(
        "SELECT id FROM collections WHERE id = ? AND userId = ?",
        (collection_id, user_id),
    )
    if not collection:
        raise HTTPException(
            status_code=403, detail="Подборка не найдена или недоступна"
        )
    execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    return RedirectResponse(url="/collections", status_code=303)


# ----------------------- ЗАПУСК -------------------------------------


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
