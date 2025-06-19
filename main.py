from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from uuid import uuid4
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# Load Environment Variables

load_dotenv()
SUPABASE_URL = "https://rxxamqqktpbxtknrzvua.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ4eGFtcXFrdHBieHRrbnJ6dnVhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTAzMzg2NzUsImV4cCI6MjA2NTkxNDY3NX0.k_MI5-TaPhF8s3n6VZywANqX_vvKiCIQglty2loyUCw"
SUPABASE_BUCKET = "post-images"
DATABASE_URL = "postgresql://postgres:nJh8xnMR3JnE!*r@db.rxxamqqktpbxtknrzvua.supabase.co:5432/postgres"

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# SQLAlchemy Setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, authflush=False)

app = FastAPI(title="Supabase Blogger API")

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === SQLAlchemyModels ==
class PostDB(Base):
    __tablename__ = "posts"
    id = Column(String, primary_key=True, index=True)
    title = Column(String)
    content = Column(Text)
    image_url = Column(String, default="")
    inserted_at = Column(DateTime, default=datetime.utcnow)

    comments = relationship("CommentDB", back_populates="post", cascade="all, delete")

class CommentDB(Base):
    __tablename__ = "comments"
    id = Column(String, primary_key=True, index=True)
    post_id = Column(String, ForeignKey("post.id"))
    author = Column(String)
    content = Column(Text)
    inserted_at = Column(DateTime, default=datetime.utcnow)

    post = relationship("PostDb", back_populates="comments")

Base.metadata.create_all(bind=engine)

# === Pydantic Schemas===
class Comment(BaseModel):
    id: str
    post_id: str
    author: str
    content: str

class CommentCreate(BaseModel):
    author: str
    content: str

class Post(BaseModel):
    id: str
    title: str
    content: str
    image_url: str = ""
    comments: List[Comment] = []

class PostCreate(BaseModel):
    title: str
    content: str


# API Routes
@app.post("/posts/", response_model=Post)
async def create_post(
        title: str = Form(...),
        content: str = Form(...),
        image: UploadFile = File(None),
):
    db = SessionLocal
    post_id = str(uuid4())
    image_url = ""

    if image:
        filename = f"{post_id}.{image.filename.split('.')[-1]}"
        path = os.path.join("uploads",filename)
        with open(path, "wb") as f:
            f.write(await image.read())
        image_url = f"/uploads/{filename}"

    new_post = PostDB(id=post_id, title=title, content=content, image_url=image_url)
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return Post(
        id=new_post.id,
        title=new_post.title,
        content=new_post.content,
        image_url=new_post.image_url,
        comments=[],
    )

@app.get("/posts/", response_model=List[Post])
def get_all_posts():
    db = SessionLocal()
    posts = db.query(PostDB).all()
    results = []
    for post in posts:
        results.append(Post(
            id=post.id,
            title=post.title,
            content=post.content,
            image_url=post.image_url,
            comments=[
                Comment(id=c.id, post_id=c.post_id, author=c.author, content=c.content)
                for c in post.comments
            ]
        ))
        return results

@app.post("/post/{post_id}/comments/", response_model=Comment)
def add_comment(post_id: str, comment: CommentCreate):
    db = SessionLocal()
    post = db.query(PostDB).filter(PostDB.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not Found")

    comment_id = str(uuid4())
    new_comment = CommentDB(
        id=comment_id,
        post_id=post_id,
        author=comment.author,
        content=comment.content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return Comment(id=new_comment.id, post_id=post_id, author=new_comment.author, content=new_comment.content)

@app.delete("/posts/{post_id}")
def delete_post(post_id: str):
    db = SessionLocal()
    post = db.query(PostDB).filter(PostDB.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"message": "Post deleted"}

@app.delete("/post/{post_id}/comments/{comment_id}")
def delete_comment(post_id: str, comment_id: str):
    db = SessionLocal()
    comment = db.query(CommentDB).filter(CommentDB.id == comment_id, CommentDB.post_id == post_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
        db.delete(comment)
        db.commit()
        return {"message": "Comment deleted"}