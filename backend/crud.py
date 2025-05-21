from sqlalchemy.orm import Session
import models, schemas
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Users

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed = pwd_context.hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed, role=user.role)
    db.add(db_user); db.commit(); db.refresh(db_user)
    return db_user

# Attendance

def create_attendance(db: Session, user_id: int, att: schemas.AttendanceCreate):
    db_att = models.Attendance(user_id=user_id, lesson_id=att.lesson_id, similarity=att.similarity)
    db.add(db_att); db.commit(); db.refresh(db_att)
    return db_att

def get_attendance(db: Session):
    return db.query(models.Attendance).all()


# Lesson CRUD Operations

def create_lesson(db: Session, lesson: schemas.LessonCreate, teacher_id: int) -> models.Lesson:
    db_lesson = models.Lesson(**lesson.model_dump(), teacher_id=teacher_id)
    db.add(db_lesson)
    db.commit()
    db.refresh(db_lesson)
    return db_lesson

def get_lesson(db: Session, lesson_id: int) -> models.Lesson | None:
    return db.query(models.Lesson).filter(models.Lesson.id == lesson_id).first()

def get_lessons_by_teacher(db: Session, teacher_id: int, skip: int = 0, limit: int = 100) -> list[models.Lesson]:
    return db.query(models.Lesson).filter(models.Lesson.teacher_id == teacher_id).offset(skip).limit(limit).all()

def get_lessons_for_student(db: Session, student_id: int, skip: int = 0, limit: int = 100) -> list[models.Lesson]:
    return db.query(models.Lesson)\
        .join(models.StudentLessonEnrollment, models.StudentLessonEnrollment.lesson_id == models.Lesson.id)\
        .filter(models.StudentLessonEnrollment.user_id == student_id)\
        .offset(skip).limit(limit).all()

def update_lesson(db: Session, lesson_id: int, lesson_update: schemas.LessonCreate) -> models.Lesson | None:
    db_lesson = get_lesson(db, lesson_id)
    if db_lesson:
        db_lesson.title = lesson_update.title
        db_lesson.description = lesson_update.description
        db.commit()
        db.refresh(db_lesson)
    return db_lesson

def delete_lesson(db: Session, lesson_id: int) -> models.Lesson | None:
    db_lesson = get_lesson(db, lesson_id)
    if db_lesson:
        db.delete(db_lesson)
        db.commit()
    return db_lesson

# LessonFile CRUD Operations

def create_lesson_file(db: Session, file_name: str, file_path: str, lesson_id: int) -> models.LessonFile:
    db_lesson_file = models.LessonFile(filename=file_name, file_path=file_path, lesson_id=lesson_id)
    db.add(db_lesson_file)
    db.commit()
    db.refresh(db_lesson_file)
    return db_lesson_file

def get_lesson_files(db: Session, lesson_id: int) -> list[models.LessonFile]:
    return db.query(models.LessonFile).filter(models.LessonFile.lesson_id == lesson_id).all()

def get_lesson_file(db: Session, file_id: int) -> models.LessonFile | None:
    return db.query(models.LessonFile).filter(models.LessonFile.id == file_id).first()

def delete_lesson_file(db: Session, file_id: int) -> models.LessonFile | None:
    db_lesson_file = get_lesson_file(db, file_id)
    if db_lesson_file:
        db.delete(db_lesson_file)
        db.commit()
    return db_lesson_file

# StudentLessonEnrollment CRUD Operations

def enroll_student(db: Session, enrollment: schemas.StudentLessonEnrollmentCreate) -> models.StudentLessonEnrollment:
    # Check if enrollment already exists
    existing_enrollment = get_enrollment(db, student_id=enrollment.user_id, lesson_id=enrollment.lesson_id)
    if existing_enrollment:
        return existing_enrollment # Or raise an exception, depending on desired behavior
    
    db_enrollment = models.StudentLessonEnrollment(**enrollment.model_dump())
    db.add(db_enrollment)
    db.commit()
    db.refresh(db_enrollment)
    return db_enrollment

def unenroll_student(db: Session, student_id: int, lesson_id: int) -> models.StudentLessonEnrollment | None:
    db_enrollment = get_enrollment(db, student_id, lesson_id)
    if db_enrollment:
        db.delete(db_enrollment)
        db.commit()
    return db_enrollment

def get_enrollments_for_lesson(db: Session, lesson_id: int) -> list[models.StudentLessonEnrollment]:
    return db.query(models.StudentLessonEnrollment).filter(models.StudentLessonEnrollment.lesson_id == lesson_id).all()

def get_enrollment(db: Session, student_id: int, lesson_id: int) -> models.StudentLessonEnrollment | None:
    return db.query(models.StudentLessonEnrollment)\
        .filter(models.StudentLessonEnrollment.user_id == student_id, models.StudentLessonEnrollment.lesson_id == lesson_id)\
        .first()