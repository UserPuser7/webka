from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime
import urllib.parse

# База данных в памяти
users = []
posts = []
user_id = 1
post_id = 1

# Тестовый пользователь
users.append({
    "id": 1,
    "email": "test@test.com",
    "login": "testuser",
    "password": "123456",
    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
})

class BlogHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        if self.path == '/':
            self.send_home_page()
        elif self.path == '/create':
            self.send_create_page()
        elif self.path.startswith('/view/'):
            try:
                post_id = int(self.path.split('/')[-1])
                self.send_view_page(post_id)
            except:
                self.send_error(404, "Post not found")
        elif self.path.startswith('/edit/'):
            try:
                post_id = int(self.path.split('/')[-1])
                self.send_edit_page(post_id)
            except:
                self.send_error(404, "Post not found")
        elif self.path == '/users':
            self.send_json_response([{"id": u["id"], "email": u["email"], "login": u["login"], 
                                    "created_at": u["created_at"]} for u in users])
        elif self.path == '/posts':
            self.send_json_response(posts)
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        if self.path == '/create':
            self.handle_create_post()
        elif self.path.startswith('/edit/'):
            try:
                post_id = int(self.path.split('/')[-1])
                self.handle_edit_post(post_id)
            except:
                self.send_error(404, "Post not found")
        elif self.path == '/users':
            self.handle_create_user()
        else:
            self.send_error(404, "Not Found")
    
    def do_PUT(self):
        if self.path.startswith('/users/'):
            try:
                user_id = int(self.path.split('/')[-1])
                self.handle_update_user(user_id)
            except:
                self.send_error(404, "User not found")
        elif self.path.startswith('/posts/'):
            try:
                post_id = int(self.path.split('/')[-1])
                self.handle_update_post(post_id)
            except:
                self.send_error(404, "Post not found")
    
    def do_DELETE(self):
        if self.path.startswith('/users/'):
            try:
                user_id = int(self.path.split('/')[-1])
                self.handle_delete_user(user_id)
            except:
                self.send_error(404, "User not found")
        elif self.path.startswith('/posts/'):
            try:
                post_id = int(self.path.split('/')[-1])
                self.handle_delete_post(post_id)
            except:
                self.send_error(404, "Post not found")
    
    def send_html_response(self, html_content, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False, default=str).encode('utf-8'))
    
    def send_home_page(self):
        html = '''<!DOCTYPE html>
<html>
<head>
    <title>Blog System</title>
    <style>
        body { font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }
        .post { border: 1px solid #ddd; padding: 15px; margin: 15px 0; border-radius: 5px; }
        .btn { background: #007cba; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; margin: 5px; display: inline-block; }
        .btn-success { background: #28a745; }
        .post-actions { margin-top: 10px; }
    </style>
</head>
<body>
    <h1>📝 Blog System</h1>
    
    <div>
        <a href="/create" class="btn btn-success">Create New Post</a>
        <a href="/users" class="btn">Users API</a>
        <a href="/posts" class="btn">Posts API</a>
    </div>

    <h2>All Posts</h2>'''
        
        if posts:
            for post in posts:
                html += f'''
                <div class="post">
                    <h3>{post["title"]}</h3>
                    <p><strong>Author:</strong> {post["author_name"]}</p>
                    <p><strong>Created:</strong> {post["created_at"]}</p>
                    <p>{post["content"][:100]}{"..." if len(post["content"]) > 100 else ""}</p>
                    <div class="post-actions">
                        <a href="/view/{post["id"]}" class="btn">View</a>
                        <a href="/edit/{post["id"]}" class="btn">Edit</a>
                    </div>
                </div>'''
        else:
            html += '<p>No posts yet. <a href="/create">Create your first post!</a></p>'
        
        html += '</body></html>'
        self.send_html_response(html)
    
    def send_create_page(self):
        html = '''<!DOCTYPE html>
<html>
<head>
    <title>Create Post</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }
        .form-group { margin: 15px 0; }
        input, textarea, select { width: 100%; padding: 8px; margin: 5px 0; }
        button { background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Create New Post</h1>
    <form method="post" action="/create">
        <div class="form-group">
            <label>Title:</label>
            <input type="text" name="title" required>
        </div>
        <div class="form-group">
            <label>Content:</label>
            <textarea name="content" rows="10" required></textarea>
        </div>
        <div class="form-group">
            <label>Author:</label>
            <select name="author_id" required>'''
        
        for user in users:
            html += f'<option value="{user["id"]}">{user["login"]}</option>'
        
        html += '''</select>
        </div>
        <button type="submit">Create Post</button>
    </form>
    <br>
    <a href="/">← Back to Home</a>
</body>
</html>'''
        self.send_html_response(html)
    
    def send_view_page(self, post_id):
        post = next((p for p in posts if p["id"] == post_id), None)
        if not post:
            self.send_error(404, "Post not found")
            return
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>{post["title"]}</title>
    <style>
        body {{ font-family: Arial; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .post-content {{ border: 1px solid #ddd; padding: 20px; margin: 15px 0; }}
    </style>
</head>
<body>
    <h1>{post["title"]}</h1>
    <p><strong>Author:</strong> {post["author_name"]}</p>
    <p><strong>Created:</strong> {post["created_at"]}</p>
    
    <div class="post-content">
        {post["content"]}
    </div>
    
    <br>
    <a href="/edit/{post["id"]}">Edit Post</a> | 
    <a href="/">Back to Home</a>
</body>
</html>'''
        self.send_html_response(html)
    
    def send_edit_page(self, post_id):
        post = next((p for p in posts if p["id"] == post_id), None)
        if not post:
            self.send_error(404, "Post not found")
            return
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Edit Post</title>
    <style>
        body {{ font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }}
        input, textarea {{ width: 100%; padding: 8px; margin: 5px 0; }}
        button {{ background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>Edit Post</h1>
    <form method="post" action="/edit/{post["id"]}">
        <div>
            <label>Title:</label>
            <input type="text" name="title" value="{post["title"]}" required>
        </div>
        <div>
            <label>Content:</label>
            <textarea name="content" rows="10" required>{post["content"]}</textarea>
        </div>
        <button type="submit">Update Post</button>
    </form>
    <br>
    <a href="/view/{post["id"]}">Cancel</a> | 
    <a href="/">Back to Home</a>
</body>
</html>'''
        self.send_html_response(html)
    
    def handle_create_post(self):
        global post_id
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)
        
        title = params.get('title', [''])[0]
        content = params.get('content', [''])[0]
        author_id = int(params.get('author_id', [1])[0])
        
        author = next((u for u in users if u["id"] == author_id), users[0])
        
        new_post = {
            "id": post_id,
            "title": title,
            "content": content,
            "author_id": author_id,
            "author_name": author["login"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        posts.append(new_post)
        post_id += 1
        
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()
    
    def handle_edit_post(self, post_id):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)
        
        title = params.get('title', [''])[0]
        content = params.get('content', [''])[0]
        
        post = next((p for p in posts if p["id"] == post_id), None)
        if post:
            post["title"] = title
            post["content"] = content
            post["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        self.send_response(303)
        self.send_header('Location', f'/view/{post_id}')
        self.end_headers()
    
    def handle_create_user(self):
        global user_id
        content_length = int(self.headers['Content-Length'])
        user_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        
        new_user = {
            "id": user_id,
            "email": user_data.get("email", ""),
            "login": user_data.get("login", ""),
            "password": user_data.get("password", ""),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        users.append(new_user)
        user_id += 1
        
        self.send_json_response(new_user, 201)
    
    def handle_update_user(self, user_id):
        content_length = int(self.headers['Content-Length'])
        user_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        
        user = next((u for u in users if u["id"] == user_id), None)
        if user:
            user.update({
                "email": user_data.get("email", user["email"]),
                "login": user_data.get("login", user["login"]),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.send_json_response(user)
        else:
            self.send_error(404, "User not found")
    
    def handle_delete_user(self, user_id):
        global users
        users = [u for u in users if u["id"] != user_id]
        self.send_json_response({"message": "User deleted"})
    
    def handle_update_post(self, post_id):
        content_length = int(self.headers['Content-Length'])
        post_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        
        post = next((p for p in posts if p["id"] == post_id), None)
        if post:
            post.update({
                "title": post_data.get("title", post["title"]),
                "content": post_data.get("content", post["content"]),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.send_json_response(post)
        else:
            self.send_error(404, "Post not found")
    
    def handle_delete_post(self, post_id):
        global posts
        posts = [p for p in posts if p["id"] != post_id]
        self.send_json_response({"message": "Post deleted"})

def run_server():
    server = HTTPServer(('localhost', 8000), BlogHandler)
    print("🚀 Server running at http://localhost:8000")
    print("📝 Open http://localhost:8000 in your browser")
    print("⏹️  Press Ctrl+C to stop")
    server.serve_forever()

if __name__ == '__main__':
    run_server()