# Временное решение для Python 3.13
import sys
import os

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(__file__))

try:
    from main import app
    import uvicorn
    
    if __name__ == "__main__":
        print("🚀 Server starting at http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
except Exception as e:
    print(f"Error: {e}")
    print("Trying alternative approach...")
    
    # Альтернативный запуск
    from fastapi import FastAPI, HTTPException, Request, Form
    from fastapi.responses import HTMLResponse, RedirectResponse
    from fastapi.templating import Jinja2Templates
    from datetime import datetime
    import json
    
    app = FastAPI()
    templates = Jinja2Templates(directory="templates")
    
    # Простой функционал для демонстрации
    @app.get("/")
    async def home():
        return {"message": "Blog System is working!"}
    
    @app.get("/test")
    async def test():
        return HTMLResponse("<h1>Blog System</h1><p>Server is running!</p>")
    
    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)