from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class UserBase(BaseModel):
    username: str
    role: str

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserRead(UserBase):
    id: int
    taught_lessons: list[LessonReadWithoutTeacher] = []
    lesson_enrollments: list[StudentLessonEnrollmentReadWithoutStudent] = []
    class Config:
        model_config = {"from_attributes": True}

# Helper Schemas to avoid circular dependencies

class UserReadWithoutDetails(BaseModel):
    id: int
    username: str
    role: str
    class Config:
        model_config = {"from_attributes": True}

class LessonReadWithoutDetails(BaseModel):
    id: int
    title: str
    class Config:
        model_config = {"from_attributes": True}

class LessonReadWithoutTeacher(BaseModel): # For UserRead
    id: int
    title: str # Added title based on common usage, can be adjusted
    description: str | None = None
    created_at: datetime
    # files and enrollments might be too much detail here, excluded for now
    class Config:
        model_config = {"from_attributes": True}

class LessonFileReadWithoutLesson(BaseModel): # For LessonRead
    id: int
    filename: str
    file_path: str
    uploaded_at: datetime
    class Config:
        model_config = {"from_attributes": True}

class StudentLessonEnrollmentReadWithoutLesson(BaseModel): # For LessonRead
    user_id: int
    student: UserReadWithoutDetails
    class Config:
        model_config = {"from_attributes": True}

class StudentLessonEnrollmentReadWithoutStudent(BaseModel): # For UserRead
    lesson_id: int
    lesson: LessonReadWithoutDetails
    class Config:
        model_config = {"from_attributes": True}


# Lesson Schemas
class LessonBase(BaseModel):
    title: str
    description: str | None = None

class LessonCreate(LessonBase):
    pass

class LessonRead(LessonBase):
    id: int
    teacher_id: int
    created_at: datetime
    files: list[LessonFileReadWithoutLesson] = []
    enrollments: list[StudentLessonEnrollmentReadWithoutLesson] = []
    class Config:
        model_config = {"from_attributes": True}

# LessonFile Schemas
class LessonFileBase(BaseModel):
    filename: str

class LessonFileCreate(LessonFileBase):
    pass

class LessonFileRead(LessonFileBase):
    id: int
    file_path: str
    uploaded_at: datetime
    lesson_id: int
    # lesson: LessonReadWithoutDetails # Optional: if you need basic lesson info here
    class Config:
        model_config = {"from_attributes": True}

# StudentLessonEnrollment Schemas
class StudentLessonEnrollmentBase(BaseModel):
    user_id: int
    lesson_id: int

class StudentLessonEnrollmentCreate(StudentLessonEnrollmentBase):
    pass

class StudentLessonEnrollmentRead(StudentLessonEnrollmentBase):
    student: UserReadWithoutDetails
    lesson: LessonReadWithoutDetails
    class Config:
        model_config = {"from_attributes": True}

class AttendanceBase(BaseModel):
    lesson_id: int

class AttendanceCreate(AttendanceBase):
    similarity: float

class AttendanceRead(AttendanceCreate):
    id: int
    user_id: int
    timestamp: datetime
    class Config:
        model_config = {"from_attributes": True}

# Generic Message Response
class MessageResponse(BaseModel):
    message: str