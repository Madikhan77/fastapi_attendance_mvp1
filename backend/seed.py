from sqlalchemy.orm import Session
from fastapi_attendance_mvp.backend.database import SessionLocal, engine, Base
import models
from passlib.context import CryptContext

# Инициализация схемы
Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed():
    db: Session = SessionLocal()
    users = [
        {"username": "student1", "password": "password123", "role": "student"},
        {"username": "teacher1", "password": "password123", "role": "teacher"},
    ]
    for u in users:
        hashed = pwd_context.hash(u["password"])
        db_user = models.User(username=u["username"], password=hashed, role=u["role"])
        db.add(db_user)
    db.commit()
    db.close()

if __name__ == '__main__':
    seed()
    print("Users seeded: student1/teacher1, password: password123")