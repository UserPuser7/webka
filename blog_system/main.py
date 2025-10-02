from fastapi import FastAPI, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from typing import List, Dict
import json
import os
from models import User, UserCreate, Post, PostCreate


app = FastAPI(title="Blog System", version="1.0.0")
templates = Jinja2Templates(directory="templates")

users_db: Dict[int, User] = {}
posts_db: Dict[int, Post] = {}
user_id_counter = 1
post_id_counter = 1

DATA_FILE = "data.json"

def save_data():
    data = {
        "users": {uid: {
            "id": user.id,
            "email": user.email,
            "login": user.login,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat()
        } for uid, user in users_db.items()},
        "posts": {pid: {
            "id": post.id,
            "author_id": post.author_id,
            "title": post.title,
            "content": post.content,
            "created_at": post.created_at.isoformat(),
            "updated_at": post.updated_at.isoformat()
        } for pid, post in posts_db.items()},
        "counters": {
            "user_id": user_id_counter,
            "post_id": post_id_counter
        }
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    global users_db, posts_db, user_id_counter, post_id_counter
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for uid, user_data in data.get("users", {}).items():
            users_db[int(uid)] = User(
                id=user_data["id"],
                email=user_data["email"],
                login=user_data["login"],
                created_at=datetime.fromisoformat(user_data["created_at"]),
                updated_at=datetime.fromisoformat(user_data["updated_at"])
            )
        for pid, post_data in data.get("posts", {}).items():
            posts_db[int(pid)] = Post(
                id=post_data["id"],
                author_id=post_data["author_id"],
                title=post_data["title"],
                content=post_data["content"],
                created_at=datetime.fromisoformat(post_data["created_at"]),
                updated_at=datetime.fromisoformat(post_data["updated_at"])
            )
        counters = data.get("counters", {})
        user_id_counter = counters.get("user_id", 1)
        post_id_counter = counters.get("post_id", 1)
    except Exception as e:
        print(f"Error loading data: {e}")

load_data()

@app.post("/users/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    global user_id_counter
    if "@" not in user.email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    for existing in users_db.values():
        if existing.email == user.email:
            raise HTTPException(status_code=400, detail="Email already exists")
        if existing.login == user.login:
            raise HTTPException(status_code=400, detail="Login already exists")
    new_user = User(
        id=user_id_counter,
        email=user.email,
        login=user.login,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    users_db[user_id_counter] = new_user
    user_id_counter += 1
    save_data()
    return new_user

@app.get("/users/", response_model=List[User])
async def get_users():
    return list(users_db.values())

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]

@app.put("/users/{user_id}", response_model=User)
async def update_user(user_id: int, user: UserCreate):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    if "@" not in user.email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    for uid, existing in users_db.items():
        if uid != user_id:
            if existing.email == user.email:
                raise HTTPException(status_code=400, detail="Email already exists")
            if existing.login == user.login:
                raise HTTPException(status_code=400, detail="Login already exists")
    updated_user = User(
        id=user_id,
        email=user.email,
        login=user.login,
        created_at=users_db[user_id].created_at,
        updated_at=datetime.now()
    )
    users_db[user_id] = updated_user
    save_data()
    return updated_user

@app.delete("/users/{user_id}")
async def delete_user(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    posts_to_delete = [pid for pid, post in posts_db.items() if post.author_id == user_id]
    for pid in posts_to_delete:
        del posts_db[pid]
    del users_db[user_id]
    save_data()
    return {"message": "User deleted"}

@app.post("/posts/", response_model=Post, status_code=status.HTTP_201_CREATED)
async def create_post(post: PostCreate, author_id: int):
    global post_id_counter
    if author_id not in users_db:
        raise HTTPException(status_code=404, detail="Author not found")
    if not post.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    if not post.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    if len(post.title) > 100:
        raise HTTPException(status_code=400, detail="Title too long")
    new_post = Post(
        id=post_id_counter,
        author_id=author_id,
        title=post.title.strip(),
        content=post.content.strip(),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    posts_db[post_id_counter] = new_post
    post_id_counter += 1
    save_data()
    return new_post

@app.get("/posts/", response_model=List[Post])
async def get_posts():
    return list(posts_db.values())

@app.get("/posts/{post_id}", response_class=HTMLResponse)
async def view_post_page(request: Request, post_id: int):
    if post_id not in posts_db:
        raise HTTPException(status_code=404, detail="Post not found")
    post = posts_db[post_id]
    author = users_db.get(post.author_id)
    if author is None:
        return templates.TemplateResponse("error.html", {"request": request, "error": "Author not found"})
    return templates.TemplateResponse("view_post.html", {
        "request": request,
        "post": post,
        "author": author
    })

@app.get("/posts/create", response_class=HTMLResponse)
async def create_post_page(request: Request):
    if not users_db:
        return templates.TemplateResponse("error.html", {"request": request, "error": "No users available. Please create a user first."})
    return templates.TemplateResponse("create_post.html", {"request": request, "users": list(users_db.values())})

@app.post("/posts/create")
async def handle_create_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    author_id: int = Form(...)
):
    try:
        post_data = PostCreate(title=title, content=content)
        new_post = await create_post(post_data, author_id)
        return RedirectResponse(url=f"/posts/{new_post.id}", status_code=303)
    except HTTPException as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": e.detail})

@app.get("/posts/{post_id}/edit", response_class=HTMLResponse)
async def edit_post_page(request: Request, post_id: int):
    if post_id not in posts_db:
        raise HTTPException(status_code=404, detail="Post not found")
    post = posts_db[post_id]
    return templates.TemplateResponse("edit_post.html", {"request": request, "post": post})

@app.post("/posts/{post_id}/edit")
async def handle_edit_post(
    request: Request,
    post_id: int,
    title: str = Form(...),
    content: str = Form(...)
):
    if post_id not in posts_db:
        return templates.TemplateResponse("error.html", {"request": request, "error": "Post not found"})
    try:
        post_data = PostCreate(title=title, content=content)
        updated_post = await update_post(post_id, post_data)
        return RedirectResponse(url=f"/posts/{updated_post.id}", status_code=303)
    except HTTPException as e:
        return templates.TemplateResponse("error.html", {"request": request, "error": e.detail})

async def update_post(post_id: int, post: PostCreate):
    if post_id not in posts_db:
        raise HTTPException(status_code=404, detail="Post not found")
    if not post.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    if not post.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    if len(post.title) > 100:
        raise HTTPException(status_code=400, detail="Title too long")
    old_post = posts_db[post_id]
    updated_post = Post(
        id=post_id,
        author_id=old_post.author_id,
        title=post.title.strip(),
        content=post.content.strip(),
        created_at=old_post.created_at,
        updated_at=datetime.now()
    )
    posts_db[post_id] = updated_post
    save_data()
    return updated_post

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
