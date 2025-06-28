from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from sqlalchemy import func, and_, or_

db = SQLAlchemy()

class Guest(db.Model):
    __tablename__ = 'guest'
    
    guest_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.Text, nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    sex = db.Column(db.String(1))
    passport_num = db.Column(db.String(20), unique=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.Text)
    
    # Отношения
    stays_as_primary = db.relationship('Stay', backref='primary_guest_obj', foreign_keys='Stay.primary_guest')
    stay_guests = db.relationship('StayGuest', backref='guest_obj')
    treatment_courses = db.relationship('TreatmentCourse', backref='guest_obj')
    
    __table_args__ = (
        db.CheckConstraint("sex IN ('M','F')"),
    )
    
    @property
    def age(self):
        if self.birth_date:
            today = date.today()
            return today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return None

class Room(db.Model):
    __tablename__ = 'room'
    
    room_id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Text, nullable=False, unique=True)
    building = db.Column(db.Text, nullable=False)
    floor = db.Column(db.Integer)
    capacity = db.Column(db.Integer, nullable=False)
    daily_cost = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Отношения
    stays = db.relationship('Stay', backref='room_obj')
    
    __table_args__ = (
        db.CheckConstraint("capacity > 0"),
        db.CheckConstraint("daily_cost >= 0"),
    )
    
    @property
    def status(self):
        """Статус комнаты: занята или свободна"""
        current_date = date.today()
        active_stay = Stay.query.filter(
            and_(
                Stay.room_id == self.room_id,
                Stay.check_in_date <= current_date,
                Stay.check_out_date >= current_date
            )
        ).first()
        return 'occupied' if active_stay else 'available'

class Stay(db.Model):
    __tablename__ = 'stay'
    
    stay_id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.room_id'), nullable=False)
    primary_guest = db.Column(db.Integer, db.ForeignKey('guest.guest_id'), nullable=False)
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)
    
    # Отношения
    stay_guests = db.relationship('StayGuest', backref='stay_obj', cascade='all, delete-orphan')
    invoices = db.relationship('Invoice', backref='stay_obj')
    
    __table_args__ = (
        db.CheckConstraint("check_out_date >= check_in_date"),
    )
    
    @property
    def status(self):
        """Статус путёвки: planned, ongoing, closed"""
        current_date = date.today()
        if current_date < self.check_in_date:
            return 'planned'
        elif current_date <= self.check_out_date:
            return 'ongoing'
        else:
            return 'closed'
    
    @property
    def duration(self):
        """Длительность путёвки в днях"""
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return None

class StayGuest(db.Model):
    __tablename__ = 'stay_guest'
    
    stay_guest_id = db.Column(db.Integer, primary_key=True)
    stay_id = db.Column(db.Integer, db.ForeignKey('stay.stay_id', ondelete='CASCADE'), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.guest_id'), nullable=False)

class Doctor(db.Model):
    __tablename__ = 'doctor'
    
    doctor_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.Text, nullable=False)
    specialty = db.Column(db.Text, nullable=False)
    phone = db.Column(db.Text)
    
    # Отношения
    treatment_courses = db.relationship('TreatmentCourse', backref='doctor_obj')

class TreatmentType(db.Model):
    __tablename__ = 'treatment_type'
    
    treatment_type_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Отношения
    treatment_courses = db.relationship('TreatmentCourse', backref='treatment_type_obj')
    
    __table_args__ = (
        db.CheckConstraint("base_price >= 0"),
    )

class TreatmentCourse(db.Model):
    __tablename__ = 'treatment_course'
    
    course_id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.guest_id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.doctor_id'), nullable=False)
    treatment_type_id = db.Column(db.Integer, db.ForeignKey('treatment_type.treatment_type_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Отношения
    treatment_sessions = db.relationship('TreatmentSession', backref='course_obj', cascade='all, delete-orphan')

class TreatmentSession(db.Model):
    __tablename__ = 'treatment_session'
    
    session_id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('treatment_course.course_id', ondelete='CASCADE'), nullable=False)
    start_ts = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20))
    result_notes = db.Column(db.Text)
    
    __table_args__ = (
        db.CheckConstraint("status IN ('planned','done','cancelled')"),
    )

class Invoice(db.Model):
    __tablename__ = 'invoice'
    
    invoice_id = db.Column(db.Integer, primary_key=True)
    stay_id = db.Column(db.Integer, db.ForeignKey('stay.stay_id'), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    total_sum = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20))
    
    # Отношения
    payments = db.relationship('Payment', backref='invoice_obj')
    
    __table_args__ = (
        db.CheckConstraint("total_sum >= 0"),
        db.CheckConstraint("status IN ('unpaid','partly','paid')"),
    )

class Payment(db.Model):
    __tablename__ = 'payment'
    
    payment_id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.invoice_id'), nullable=False)
    pay_ts = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    method = db.Column(db.Text)
    
    __table_args__ = (
        db.CheckConstraint("amount > 0"),
    ) 