from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_

from ..extensions import db
from ..models import ClassSession, Staff, StaffSubjectAssignment, Student, User


def student_profile_for(user: User) -> Student | None:
    return Student.query.filter_by(user_id=user.id, status="active").one_or_none()


def staff_profile_for(user: User) -> Staff | None:
    return Staff.query.filter_by(user_id=user.id, status="active").one_or_none()


def staff_assignment_query(staff_id, on_date: date | None = None):
    query = StaffSubjectAssignment.query.filter_by(staff_id=staff_id)
    if on_date is not None:
        query = query.filter(or_(StaffSubjectAssignment.valid_from.is_(None), StaffSubjectAssignment.valid_from <= on_date))
        query = query.filter(or_(StaffSubjectAssignment.valid_to.is_(None), StaffSubjectAssignment.valid_to >= on_date))
    return query


def staff_can_access_session(user: User, session: ClassSession) -> bool:
    if user.role == "Admin":
        return True
    staff = staff_profile_for(user)
    if not staff:
        return False
    session_day = session.starts_at.date()
    return staff_assignment_query(staff.id, session_day).filter_by(subject_id=session.subject_id, section_id=session.section_id).first() is not None


def student_can_access_session(user: User, session: ClassSession) -> bool:
    if user.role == "Admin":
        return True
    student = student_profile_for(user)
    return bool(student and student.section_id == session.section_id)


def scoped_student_query(user: User):
    query = Student.query.filter_by(status="active")
    if user.role == "Admin":
        return query
    if user.role == "Student":
        profile = student_profile_for(user)
        return query.filter_by(id=profile.id) if profile else query.filter(db.false())
    staff = staff_profile_for(user)
    if staff is None:
        return query.filter(db.false())
    assignment_sections = staff_assignment_query(staff.id, date.today()).with_entities(StaffSubjectAssignment.section_id)
    return query.filter(Student.section_id.in_(assignment_sections)).distinct()


def scoped_session_query(user: User):
    query = ClassSession.query
    if user.role == "Admin":
        return query
    if user.role == "Student":
        profile = student_profile_for(user)
        return query.filter_by(section_id=profile.section_id) if profile else query.filter(db.false())
    staff = staff_profile_for(user)
    if staff is None:
        return query.filter(db.false())
    session_day = func.date(ClassSession.starts_at)
    pairs = db.session.query(StaffSubjectAssignment.subject_id, StaffSubjectAssignment.section_id).filter_by(staff_id=staff.id)
    pairs = pairs.filter(or_(StaffSubjectAssignment.valid_from.is_(None), StaffSubjectAssignment.valid_from <= session_day))
    pairs = pairs.filter(or_(StaffSubjectAssignment.valid_to.is_(None), StaffSubjectAssignment.valid_to >= session_day))
    return query.filter(db.tuple_(ClassSession.subject_id, ClassSession.section_id).in_(pairs))
