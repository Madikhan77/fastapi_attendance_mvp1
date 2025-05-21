from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    records = relationship('Attendance', back_populates='user')
    taught_lessons = relationship('Lesson', back_populates='teacher')
    lesson_enrollments = relationship('StudentLessonEnrollment', back_populates='student', cascade="all, delete-orphan")

class Lesson(Base):
    __tablename__ = 'lessons'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    teacher_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    teacher = relationship('User', back_populates='taught_lessons')
    files = relationship('LessonFile', back_populates='lesson', cascade="all, delete-orphan")
    enrollments = relationship('StudentLessonEnrollment', back_populates='lesson', cascade="all, delete-orphan")

class LessonFile(Base):
    __tablename__ = 'lesson_files'
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    lesson_id = Column(Integer, ForeignKey('lessons.id'), nullable=False)
    lesson = relationship('Lesson', back_populates='files')

class StudentLessonEnrollment(Base):
    __tablename__ = 'student_lesson_enrollments'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    lesson_id = Column(Integer, ForeignKey('lessons.id'), primary_key=True)
    student = relationship('User', back_populates='lesson_enrollments')
    lesson = relationship('Lesson', back_populates='enrollments')

class Attendance(Base):
    __tablename__ = 'attendance'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    lesson_id = Column(Integer, nullable=False)
    similarity = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship('User', back_populates='records')