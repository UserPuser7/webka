from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from datetime import datetime
from typing import List

# Создаем приложение FastAPI
app = FastAPI(
    title="Blog API", description="Simple blog system with REST API and HTML views"
)

# Подключаем шаблоны
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Временная "база данных" в памяти
users: List[dict] = []
posts: List[dict] = []


# Генератор ID
def get_next_id(collection):
    if not collection:
        return 1
    return max(item["id"] for item in collection) + 1


# Модели (просто словари)
class User:
    def __init__(self, login: str, email: str, password: str):
        self.id = get_next_id(users)
        self.login = login
        self.email = email
        self.password = password
        self.createdAt = datetime.now()
        self.updatedAt = datetime.now()


class Post:
    def __init__(self, authorId: int, title: str, content: str):
        self.id = get_next_id(posts)
        self.authorId = authorId
        self.title = title
        self.content = content
        self.createdAt = datetime.now()
        self.updatedAt = datetime.now()


# --- CRUD для User ---


@app.post("/api/users", response_model=dict)
async def create_user(
    login: str = Form(...), email: str = Form(...), password: str = Form(...)
):
    """Создать нового пользователя"""
    # Валидация
    if not login or not email or not password:
        raise HTTPException(status_code=400, detail="All fields are required")
    if any(u["login"] == login for u in users):
        raise HTTPException(status_code=400, detail="Login already exists")
    if any(u["email"] == email for u in users):
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(login, email, password)
    users.append(user.__dict__)
    return {"message": "User created", "user": user.__dict__}


@app.get("/api/users", response_model=List[dict])
async def get_users():
    """Получить всех пользователей"""
    return users


@app.get("/api/users/{user_id}", response_model=dict)
async def get_user(user_id: int):
    """Получить пользователя по ID"""
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/api/users/{user_id}", response_model=dict)
async def update_user(
    user_id: int,
    login: str = Form(None),
    email: str = Form(None),
    password: str = Form(None),
):
    """Обновить пользователя"""
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем поля, если они переданы
    if login is not None:
        if any(u["login"] == login and u["id"] != user_id for u in users):
            raise HTTPException(status_code=400, detail="Login already exists")
        user["login"] = login
    if email is not None:
        if any(u["email"] == email and u["id"] != user_id for u in users):
            raise HTTPException(status_code=400, detail="Email already exists")
        user["email"] = email
    if password is not None:
        user["password"] = password

    user["updatedAt"] = datetime.now()
    return {"message": "User updated", "user": user}


@app.delete("/api/users/{user_id}", response_model=dict)
async def delete_user(user_id: int):
    """Удалить пользователя"""
    global users
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    users = [u for u in users if u["id"] != user_id]
    return {"message": "User deleted"}


# --- CRUD для Post ---


@app.post("/api/posts", response_model=dict)
async def create_post(
    authorId: int = Form(...), title: str = Form(...), content: str = Form(...)
):
    """Создать новый пост"""
    # Валидация
    if not title or not content:
        raise HTTPException(status_code=400, detail="Title and content are required")
    if not any(u["id"] == authorId for u in users):
        raise HTTPException(status_code=400, detail="Author does not exist")

    post = Post(authorId, title, content)
    posts.append(post.__dict__)
    return {"message": "Post created", "post": post.__dict__}


@app.get("/api/posts", response_model=List[dict])
async def get_posts():
    """Получить все посты"""
    return posts


@app.get("/api/posts/{post_id}", response_model=dict)
async def get_post(post_id: int):
    """Получить пост по ID"""
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    # Добавляем имя автора для удобства
    author = next((u for u in users if u["id"] == post["authorId"]), None)
    post["authorName"] = author["login"] if author else "Unknown"
    return post


@app.put("/api/posts/{post_id}", response_model=dict)
async def update_post(post_id: int, title: str = Form(None), content: str = Form(None)):
    """Обновить пост"""
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if title is not None:
        post["title"] = title
    if content is not None:
        post["content"] = content

    post["updatedAt"] = datetime.now()
    return {"message": "Post updated", "post": post}


@app.delete("/api/posts/{post_id}", response_model=dict)
async def delete_post(post_id: int):
    """Удалить пост"""
    global posts
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    posts = [p for p in posts if p["id"] != post_id]
    return {"message": "Post deleted"}


# --- HTML Шаблоны (Дополнительно) ---


@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Главная страница со списком всех постов"""
    # Получаем все посты и добавляем имена авторов
    posts_with_authors = []
    for post in posts:
        author = next((u for u in users if u["id"] == post["authorId"]), None)
        post_copy = post.copy()
        post_copy["authorName"] = author["login"] if author else "Unknown"
        posts_with_authors.append(post_copy)
    return templates.TemplateResponse(
        "index.html", {"request": request, "posts": posts_with_authors}
    )


@app.get("/post/{post_id}", response_class=HTMLResponse)
async def view_post(request: Request, post_id: int):
    """Страница просмотра конкретного поста"""
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    author = next((u for u in users if u["id"] == post["authorId"]), None)
    post["authorName"] = author["login"] if author else "Unknown"
    return templates.TemplateResponse("post.html", {"request": request, "post": post})


@app.get("/create-post", response_class=HTMLResponse)
async def show_create_post_form(request: Request):
    """Страница создания поста"""
    return templates.TemplateResponse(
        "create_post.html", {"request": request, "users": users}
    )


@app.post("/create-post", response_class=HTMLResponse)
async def create_post_html(
    request: Request,
    authorId: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
):
    """Обработчик формы создания поста"""
    try:
        await create_post(authorId, title, content)
        return RedirectResponse(url="/", status_code=303)
    except HTTPException as e:
        return templates.TemplateResponse(
            "create_post.html", {"request": request, "users": users, "error": e.detail}
        )


@app.get("/edit-post/{post_id}", response_class=HTMLResponse)
async def show_edit_post_form(request: Request, post_id: int):
    """Страница редактирования поста"""
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return templates.TemplateResponse(
        "edit_post.html", {"request": request, "post": post, "users": users}
    )


@app.post("/edit-post/{post_id}", response_class=HTMLResponse)
async def edit_post_html(
    request: Request,
    post_id: int,
    authorId: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
):
    """Обработчик формы редактирования поста"""
    try:
        await update_post(post_id, title, content)
        # Также обновляем автора, если он изменился
        post = next((p for p in posts if p["id"] == post_id), None)
        if post:
            post["authorId"] = authorId
            post["updatedAt"] = datetime.now()
        return RedirectResponse(url=f"/post/{post_id}", status_code=303)
    except HTTPException as e:
        post = next((p for p in posts if p["id"] == post_id), None)
        return templates.TemplateResponse(
            "edit_post.html",
            {"request": request, "post": post, "users": users, "error": e.detail},
        )


# Запуск сервера (для локального тестирования)
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
