from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_, or_, extract
from models import db, Guest, Room, Stay, StayGuest, Invoice, Payment, Doctor, TreatmentType, TreatmentCourse, TreatmentSession

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # В продакшене используйте безопасный ключ

# Конфигурация базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://kazah:kazah@localhost:5432/sanatori'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных
db.init_app(app)

@app.route('/')
def index():
    """Главная страница с обзором санатория"""
    try:
        # Статистика
        stats = {}
        
        # Общее количество гостей
        stats['total_guests'] = Guest.query.count()
        
        # Текущие постояльцы
        current_date = date.today()
        
        # Основные гости из активных путёвок
        primary_guests = db.session.query(Stay.primary_guest).filter(
            and_(
                Stay.check_in_date <= current_date,
                Stay.check_out_date >= current_date
            )
        )
        
        # Дополнительные гости из активных путёвок
        additional_guests = db.session.query(StayGuest.guest_id).join(Stay).filter(
            and_(
                Stay.check_in_date <= current_date,
                Stay.check_out_date >= current_date
            )
        )
        
        # Объединяем и считаем уникальных гостей
        all_guest_ids = set()
        for guest_id in primary_guests:
            all_guest_ids.add(guest_id[0])
        for guest_id in additional_guests:
            all_guest_ids.add(guest_id[0])
        
        stats['current_guests'] = len(all_guest_ids)
        
        # Свободные комнаты
        occupied_rooms = db.session.query(Stay.room_id).filter(
            and_(
                Stay.check_in_date <= current_date,
                Stay.check_out_date >= current_date
            )
        ).distinct()
        
        occupied_room_ids = [room[0] for room in occupied_rooms]
        
        stats['available_rooms'] = Room.query.filter(
            ~Room.room_id.in_(occupied_room_ids)
        ).count()
        
        # Неоплаченные счета
        stats['unpaid_invoices'] = Invoice.query.filter(
            Invoice.status.in_(['unpaid', 'partly'])
        ).count()
        
        # Активные курсы лечения
        stats['active_courses'] = TreatmentCourse.query.count()
        
        # Сеансы на сегодня
        today_start = datetime.combine(current_date, datetime.min.time())
        today_end = datetime.combine(current_date, datetime.max.time())
        stats['today_sessions'] = TreatmentSession.query.filter(
            and_(
                TreatmentSession.start_ts >= today_start,
                TreatmentSession.start_ts <= today_end
            )
        ).count()
        
        # Текущие путёвки
        current_stays = Stay.query.join(Room).join(Guest, Stay.primary_guest == Guest.guest_id).filter(
            and_(
                Stay.check_in_date <= current_date,
                Stay.check_out_date >= current_date
            )
        ).order_by(Stay.check_in_date).all()
        
        return render_template('index.html', stats=stats, current_stays=current_stays)
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'error')
        return render_template('index.html', stats={}, current_stays=[])

# Роуты для гостей
@app.route('/guests')
def guests():
    """Список всех гостей"""
    try:
        guests = Guest.query.order_by(Guest.full_name).all()
        return render_template('guests.html', guests=guests)
    except Exception as e:
        flash(f'Ошибка при загрузке гостей: {str(e)}', 'error')
        return render_template('guests.html', guests=[])

@app.route('/guests/new', methods=['GET', 'POST'])
def new_guest():
    """Добавление нового гостя"""
    if request.method == 'POST':
        try:
            data = request.form
            guest = Guest(
                full_name=data['full_name'],
                birth_date=datetime.strptime(data['birth_date'], '%Y-%m-%d').date(),
                sex=data['sex'],
                passport_num=data['passport_num'] or None,
                phone=data['phone'] or None,
                email=data['email'] or None
            )
            db.session.add(guest)
            db.session.commit()
            flash('Гость успешно добавлен!', 'success')
            return redirect(url_for('guests'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении гостя: {str(e)}', 'error')
    
    return render_template('guest_form.html', guest=None)

@app.route('/guests/<int:guest_id>/edit', methods=['GET', 'POST'])
def edit_guest(guest_id):
    """Редактирование гостя"""
    guest = Guest.query.get_or_404(guest_id)
    
    if request.method == 'POST':
        try:
            data = request.form
            guest.full_name = data['full_name']
            guest.birth_date = datetime.strptime(data['birth_date'], '%Y-%m-%d').date()
            guest.sex = data['sex']
            guest.passport_num = data['passport_num'] or None
            guest.phone = data['phone'] or None
            guest.email = data['email'] or None
            
            db.session.commit()
            flash('Данные гостя обновлены!', 'success')
            return redirect(url_for('guests'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении: {str(e)}', 'error')
    
    return render_template('guest_form.html', guest=guest)

@app.route('/guests/<int:guest_id>/delete', methods=['POST'])
def delete_guest(guest_id):
    """Удаление гостя"""
    guest = Guest.query.get_or_404(guest_id)
    
    # Проверяем, есть ли курсы лечения с этим гостем
    existing_courses = TreatmentCourse.query.filter_by(guest_id=guest_id).count()
    
    # Проверяем, есть ли путёвки с этим гостем
    existing_stays = Stay.query.filter_by(primary_guest=guest_id).count()
    existing_stay_guests = StayGuest.query.filter_by(guest_id=guest_id).count()
    
    if existing_courses > 0 or existing_stays > 0 or existing_stay_guests > 0:
        flash(f'Невозможно удалить гостя "{guest.full_name}". Существуют связанные записи: {existing_courses} курс(ов) лечения, {existing_stays} путёвка(и), {existing_stay_guests} записей в путёвках. Сначала удалите или измените эти записи.', 'error')
        return redirect(url_for('guests'))
    
    try:
        db.session.delete(guest)
        db.session.commit()
        flash('Гость успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении гостя: {str(e)}', 'error')
    return redirect(url_for('guests'))

# Роуты для комнат
@app.route('/rooms')
def rooms():
    """Список всех комнат"""
    try:
        rooms = Room.query.order_by(Room.building, Room.number).all()
        return render_template('rooms.html', rooms=rooms)
    except Exception as e:
        flash(f'Ошибка при загрузке комнат: {str(e)}', 'error')
        return render_template('rooms.html', rooms=[])

@app.route('/rooms/new', methods=['GET', 'POST'])
def new_room():
    """Добавление новой комнаты"""
    if request.method == 'POST':
        try:
            data = request.form
            room = Room(
                number=data['number'],
                building=data['building'],
                floor=int(data['floor']) if data['floor'] else None,
                capacity=int(data['capacity']),
                daily_cost=float(data['daily_cost'])
            )
            db.session.add(room)
            db.session.commit()
            flash('Комната успешно добавлена!', 'success')
            return redirect(url_for('rooms'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении комнаты: {str(e)}', 'error')
    
    return render_template('room_form.html', room=None)

@app.route('/rooms/<int:room_id>/edit', methods=['GET', 'POST'])
def edit_room(room_id):
    """Редактирование комнаты"""
    room = Room.query.get_or_404(room_id)
    
    if request.method == 'POST':
        try:
            data = request.form
            room.number = data['number']
            room.building = data['building']
            room.floor = int(data['floor']) if data['floor'] else None
            room.capacity = int(data['capacity'])
            room.daily_cost = float(data['daily_cost'])
            
            db.session.commit()
            flash('Комната успешно обновлена!', 'success')
            return redirect(url_for('rooms'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении комнаты: {str(e)}', 'error')
    
    return render_template('room_form.html', room=room)

@app.route('/rooms/<int:room_id>/delete', methods=['POST'])
def delete_room(room_id):
    """Удаление комнаты"""
    room = Room.query.get_or_404(room_id)
    
    try:
        # Проверяем, есть ли активные путёвки в этой комнате
        active_stays = Stay.query.filter_by(room_id=room_id).filter(
            Stay.status.in_(['planned', 'ongoing'])
        ).count()
        
        if active_stays > 0:
            flash(f'Нельзя удалить комнату, в которой есть активные путёвки ({active_stays} шт.)', 'error')
            return redirect(url_for('rooms'))
        
        db.session.delete(room)
        db.session.commit()
        flash(f'Комната {room.building} - {room.number} успешно удалена!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении комнаты: {str(e)}', 'error')
    
    return redirect(url_for('rooms'))

# Роуты для путёвок
@app.route('/stays')
def stays():
    """Список всех путёвок"""
    try:
        stays = Stay.query.join(Room).join(Guest, Stay.primary_guest == Guest.guest_id).order_by(Stay.check_in_date.desc()).all()
        return render_template('stays.html', stays=stays)
    except Exception as e:
        flash(f'Ошибка при загрузке путёвок: {str(e)}', 'error')
        return render_template('stays.html', stays=[])

@app.route('/stays/new', methods=['GET', 'POST'])
def new_stay():
    """Создание новой путёвки"""
    if request.method == 'POST':
        try:
            data = request.form
            stay = Stay(
                room_id=int(data['room_id']),
                primary_guest=int(data['primary_guest']),
                check_in_date=datetime.strptime(data['check_in_date'], '%Y-%m-%d').date(),
                check_out_date=datetime.strptime(data['check_out_date'], '%Y-%m-%d').date()
            )
            db.session.add(stay)
            db.session.commit()
            flash('Путёвка успешно создана!', 'success')
            return redirect(url_for('stays'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании путёвки: {str(e)}', 'error')
    
    rooms = Room.query.order_by(Room.building, Room.number).all()
    guests = Guest.query.order_by(Guest.full_name).all()
    return render_template('stay_form.html', rooms=rooms, guests=guests, stay=None)

@app.route('/stays/<int:stay_id>/edit', methods=['GET', 'POST'])
def edit_stay(stay_id):
    """Редактирование путёвки"""
    stay = Stay.query.get_or_404(stay_id)
    
    if request.method == 'POST':
        try:
            data = request.form
            stay.room_id = int(data['room_id'])
            stay.primary_guest = int(data['primary_guest'])
            stay.check_in_date = datetime.strptime(data['check_in_date'], '%Y-%m-%d').date()
            stay.check_out_date = datetime.strptime(data['check_out_date'], '%Y-%m-%d').date()
            
            db.session.commit()
            flash('Путёвка успешно обновлена!', 'success')
            return redirect(url_for('stays'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении путёвки: {str(e)}', 'error')
    
    rooms = Room.query.order_by(Room.building, Room.number).all()
    guests = Guest.query.order_by(Guest.full_name).all()
    return render_template('stay_form.html', rooms=rooms, guests=guests, stay=stay)

@app.route('/stays/<int:stay_id>/delete', methods=['POST'])
def delete_stay(stay_id):
    """Удаление путёвки"""
    stay = Stay.query.get_or_404(stay_id)
    
    try:
        # Проверяем, есть ли связанные счета
        invoices_count = Invoice.query.filter_by(stay_id=stay_id).count()
        if invoices_count > 0:
            flash(f'Нельзя удалить путёвку, к которой привязаны счета ({invoices_count} шт.)', 'error')
            return redirect(url_for('stays'))
        
        # Удаляем связанных гостей
        StayGuest.query.filter_by(stay_id=stay_id).delete()
        
        db.session.delete(stay)
        db.session.commit()
        flash('Путёвка успешно удалена!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении путёвки: {str(e)}', 'error')
    
    return redirect(url_for('stays'))

@app.route('/stays/<int:stay_id>/guests')
def stay_guests(stay_id):
    """Просмотр гостей путёвки"""
    stay = Stay.query.get_or_404(stay_id)
    
    # Получаем основного гостя
    primary_guest = Guest.query.get(stay.primary_guest)
    
    # Получаем дополнительных гостей
    additional_guests = db.session.query(Guest).join(StayGuest).filter(
        StayGuest.stay_id == stay_id
    ).all()
    
    # Получаем всех гостей для выбора
    all_guests = Guest.query.order_by(Guest.full_name).all()
    
    return render_template('stay_guests.html', 
                         stay=stay, 
                         primary_guest=primary_guest, 
                         additional_guests=additional_guests,
                         all_guests=all_guests)

@app.route('/stays/<int:stay_id>/guests/add', methods=['POST'])
def add_stay_guest(stay_id):
    """Добавление дополнительного гостя в путёвку"""
    stay = Stay.query.get_or_404(stay_id)
    
    try:
        data = request.form
        guest_id = int(data['guest_id'])
        
        # Проверяем, что гость не является основным
        if guest_id == stay.primary_guest:
            flash('Этот гость уже является основным в данной путёвке', 'error')
            return redirect(url_for('stay_guests', stay_id=stay_id))
        
        # Проверяем, что гость еще не добавлен
        existing_guest = StayGuest.query.filter_by(
            stay_id=stay_id, 
            guest_id=guest_id
        ).first()
        
        if existing_guest:
            flash('Этот гость уже добавлен в данную путёвку', 'error')
            return redirect(url_for('stay_guests', stay_id=stay_id))
        
        # Проверяем вместимость комнаты
        current_guests_count = StayGuest.query.filter_by(stay_id=stay_id).count() + 1  # +1 для основного гостя
        if current_guests_count >= stay.room_obj.capacity:
            flash(f'Комната имеет вместимость {stay.room_obj.capacity} человек. Невозможно добавить еще одного гостя.', 'error')
            return redirect(url_for('stay_guests', stay_id=stay_id))
        
        # Добавляем гостя
        stay_guest = StayGuest(
            stay_id=stay_id,
            guest_id=guest_id
        )
        db.session.add(stay_guest)
        db.session.commit()
        
        guest_name = Guest.query.get(guest_id).full_name
        flash(f'Гость {guest_name} успешно добавлен в путёвку!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении гостя: {str(e)}', 'error')
    
    return redirect(url_for('stay_guests', stay_id=stay_id))

@app.route('/stays/<int:stay_id>/guests/<int:guest_id>/remove', methods=['POST'])
def remove_stay_guest(stay_id, guest_id):
    """Удаление дополнительного гостя из путёвки"""
    stay = Stay.query.get_or_404(stay_id)
    
    # Проверяем, что это не основной гость
    if guest_id == stay.primary_guest:
        flash('Нельзя удалить основного гостя из путёвки', 'error')
        return redirect(url_for('stay_guests', stay_id=stay_id))
    
    try:
        stay_guest = StayGuest.query.filter_by(
            stay_id=stay_id, 
            guest_id=guest_id
        ).first()
        
        if not stay_guest:
            flash('Гость не найден в данной путёвке', 'error')
            return redirect(url_for('stay_guests', stay_id=stay_id))
        
        guest_name = Guest.query.get(guest_id).full_name
        db.session.delete(stay_guest)
        db.session.commit()
        
        flash(f'Гость {guest_name} успешно удален из путёвки!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении гостя: {str(e)}', 'error')
    
    return redirect(url_for('stay_guests', stay_id=stay_id))

# Роуты для счетов
@app.route('/invoices')
def invoices():
    """Список всех счетов"""
    try:
        invoices = Invoice.query.join(Stay).join(Room).join(Guest, Stay.primary_guest == Guest.guest_id).order_by(Invoice.issue_date.desc()).all()
        return render_template('invoices.html', invoices=invoices)
    except Exception as e:
        flash(f'Ошибка при загрузке счетов: {str(e)}', 'error')
        return render_template('invoices.html', invoices=[])

@app.route('/invoices/new', methods=['GET', 'POST'])
def new_invoice():
    """Создание нового счета"""
    if request.method == 'POST':
        try:
            data = request.form
            invoice = Invoice(
                stay_id=int(data['stay_id']),
                issue_date=datetime.strptime(data['issue_date'], '%Y-%m-%d').date(),
                total_sum=float(data['total_sum']),
                status=data['status']
            )
            db.session.add(invoice)
            db.session.commit()
            flash('Счет успешно создан!', 'success')
            return redirect(url_for('invoices'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании счета: {str(e)}', 'error')
    
    stays = Stay.query.join(Room).join(Guest, Stay.primary_guest == Guest.guest_id).order_by(Stay.check_in_date.desc()).all()
    return render_template('invoice_form.html', stays=stays, invoice=None)

# Роуты для врачей
@app.route('/doctors')
def doctors():
    """Список всех врачей"""
    try:
        doctors = Doctor.query.order_by(Doctor.full_name).all()
        return render_template('doctors.html', doctors=doctors)
    except Exception as e:
        flash(f'Ошибка при загрузке врачей: {str(e)}', 'error')
        return render_template('doctors.html', doctors=[])

@app.route('/doctors/new', methods=['GET', 'POST'])
def new_doctor():
    """Добавление нового врача"""
    if request.method == 'POST':
        try:
            data = request.form
            doctor = Doctor(
                full_name=data['full_name'],
                specialty=data['specialty'],
                phone=data['phone'] or None
            )
            db.session.add(doctor)
            db.session.commit()
            flash('Врач успешно добавлен!', 'success')
            return redirect(url_for('doctors'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении врача: {str(e)}', 'error')
    
    return render_template('doctor_form.html', doctor=None)

@app.route('/doctors/<int:doctor_id>/edit', methods=['GET', 'POST'])
def edit_doctor(doctor_id):
    """Редактирование врача"""
    doctor = Doctor.query.get_or_404(doctor_id)
    if request.method == 'POST':
        try:
            data = request.form
            doctor.full_name = data['full_name']
            doctor.specialty = data['specialty']
            doctor.phone = data['phone'] or None
            db.session.commit()
            flash('Данные врача успешно обновлены!', 'success')
            return redirect(url_for('doctors'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении врача: {str(e)}', 'error')
    
    return render_template('doctor_form.html', doctor=doctor)

@app.route('/doctors/<int:doctor_id>/delete', methods=['POST'])
def delete_doctor(doctor_id):
    """Удаление врача"""
    doctor = Doctor.query.get_or_404(doctor_id)
    
    # Проверяем, есть ли курсы лечения с этим врачом
    existing_courses = TreatmentCourse.query.filter_by(doctor_id=doctor_id).count()
    
    if existing_courses > 0:
        flash(f'Невозможно удалить врача "{doctor.full_name}". Существует {existing_courses} курс(ов) лечения с этим врачом. Сначала удалите или измените эти курсы.', 'error')
        return redirect(url_for('doctors'))
    
    try:
        db.session.delete(doctor)
        db.session.commit()
        flash('Врач успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении врача: {str(e)}', 'error')
    return redirect(url_for('doctors'))

# Роуты для типов процедур
@app.route('/treatment-types')
def treatment_types():
    """Список всех типов процедур"""
    try:
        treatment_types = TreatmentType.query.order_by(TreatmentType.name).all()
        return render_template('treatment_types.html', treatment_types=treatment_types)
    except Exception as e:
        flash(f'Ошибка при загрузке типов процедур: {str(e)}', 'error')
        return render_template('treatment_types.html', treatment_types=[])

@app.route('/treatment-types/new', methods=['GET', 'POST'])
def new_treatment_type():
    """Добавление нового типа процедуры"""
    if request.method == 'POST':
        try:
            data = request.form
            description = data['description'].strip() if data['description'] else None
            treatment_type = TreatmentType(
                name=data['name'],
                description=description,
                base_price=float(data['base_price'])
            )
            db.session.add(treatment_type)
            db.session.commit()
            flash('Тип процедуры успешно добавлен!', 'success')
            return redirect(url_for('treatment_types'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении типа процедуры: {str(e)}', 'error')
    
    return render_template('treatment_type_form.html', treatment_type=None)

@app.route('/treatment-types/<int:treatment_type_id>/edit', methods=['GET', 'POST'])
def edit_treatment_type(treatment_type_id):
    """Редактирование типа процедуры"""
    treatment_type = TreatmentType.query.get_or_404(treatment_type_id)
    if request.method == 'POST':
        try:
            data = request.form
            description = data['description'].strip() if data['description'] else None
            treatment_type.name = data['name']
            treatment_type.description = description
            treatment_type.base_price = float(data['base_price'])
            db.session.commit()
            flash('Тип процедуры успешно обновлен!', 'success')
            return redirect(url_for('treatment_types'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении типа процедуры: {str(e)}', 'error')
    
    return render_template('treatment_type_form.html', treatment_type=treatment_type)

@app.route('/treatment-types/<int:treatment_type_id>/delete', methods=['POST'])
def delete_treatment_type(treatment_type_id):
    """Удаление типа процедуры"""
    treatment_type = TreatmentType.query.get_or_404(treatment_type_id)
    
    # Проверяем, есть ли курсы лечения с этим типом процедуры
    existing_courses = TreatmentCourse.query.filter_by(treatment_type_id=treatment_type_id).count()
    
    if existing_courses > 0:
        flash(f'Невозможно удалить тип процедуры "{treatment_type.name}". Существует {existing_courses} курс(ов) лечения с этим типом процедуры. Сначала удалите или измените эти курсы.', 'error')
        return redirect(url_for('treatment_types'))
    
    try:
        db.session.delete(treatment_type)
        db.session.commit()
        flash('Тип процедуры успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении типа процедуры: {str(e)}', 'error')
    return redirect(url_for('treatment_types'))

# Роуты для курсов лечения
@app.route('/treatment-courses')
def treatment_courses():
    """Список всех курсов лечения"""
    try:
        courses = TreatmentCourse.query.join(Guest).join(Doctor).join(TreatmentType).order_by(TreatmentCourse.created_at.desc()).all()
        return render_template('treatment_courses.html', courses=courses)
    except Exception as e:
        flash(f'Ошибка при загрузке курсов лечения: {str(e)}', 'error')
        return render_template('treatment_courses.html', courses=[])

@app.route('/treatment-courses/new', methods=['GET', 'POST'])
def new_treatment_course():
    """Создание нового курса лечения"""
    if request.method == 'POST':
        try:
            data = request.form
            
            # Создаем курс лечения
            course = TreatmentCourse(
                guest_id=int(data['guest_id']),
                doctor_id=int(data['doctor_id']),
                treatment_type_id=int(data['treatment_type_id'])
            )
            db.session.add(course)
            db.session.flush()  # Получаем ID курса
            
            # Создаем сеансы, если указаны параметры
            if data.get('session_count') and data.get('first_session_date') and data.get('session_time'):
                session_count = int(data['session_count'])
                session_interval = int(data.get('session_interval', 1))
                first_session_date = datetime.strptime(data['first_session_date'], '%Y-%m-%d').date()
                session_time = datetime.strptime(data['session_time'], '%H:%M').time()
                
                # Создаем сеансы
                for i in range(session_count):
                    session_date = first_session_date + timedelta(days=i * session_interval)
                    session_datetime = datetime.combine(session_date, session_time)
                    
                    session = TreatmentSession(
                        course_id=course.course_id,
                        start_ts=session_datetime,
                        status=None  # Не устанавливаем статус, пусть вычисляется автоматически
                    )
                    db.session.add(session)
            
            db.session.commit()
            flash('Курс лечения успешно создан!', 'success')
            return redirect(url_for('treatment_courses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании курса лечения: {str(e)}', 'error')
    
    guests = Guest.query.order_by(Guest.full_name).all()
    doctors = Doctor.query.order_by(Doctor.full_name).all()
    treatment_types = TreatmentType.query.order_by(TreatmentType.name).all()
    return render_template('treatment_course_form.html', guests=guests, doctors=doctors, treatment_types=treatment_types, course=None)

@app.route('/treatment-courses/<int:course_id>/edit', methods=['GET', 'POST'])
def edit_treatment_course(course_id):
    """Редактирование курса лечения"""
    course = TreatmentCourse.query.get_or_404(course_id)
    if request.method == 'POST':
        try:
            data = request.form
            course.guest_id = int(data['guest_id'])
            course.doctor_id = int(data['doctor_id'])
            course.treatment_type_id = int(data['treatment_type_id'])
            db.session.commit()
            flash('Курс лечения успешно обновлен!', 'success')
            return redirect(url_for('treatment_courses'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении курса лечения: {str(e)}', 'error')
    
    guests = Guest.query.order_by(Guest.full_name).all()
    doctors = Doctor.query.order_by(Doctor.full_name).all()
    treatment_types = TreatmentType.query.order_by(TreatmentType.name).all()
    return render_template('treatment_course_form.html', guests=guests, doctors=doctors, treatment_types=treatment_types, course=course)

@app.route('/treatment-courses/<int:course_id>/delete', methods=['POST'])
def delete_treatment_course(course_id):
    """Удаление курса лечения"""
    course = TreatmentCourse.query.get_or_404(course_id)
    try:
        db.session.delete(course)
        db.session.commit()
        flash('Курс лечения успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении курса лечения: {str(e)}', 'error')
    return redirect(url_for('treatment_courses'))

# Роуты для сеансов лечения
@app.route('/treatment-sessions')
def treatment_sessions():
    """Список всех сеансов лечения"""
    try:
        sessions = TreatmentSession.query.join(TreatmentCourse).join(Guest).join(Doctor).join(TreatmentType).order_by(TreatmentSession.start_ts.desc()).all()
        return render_template('treatment_sessions.html', sessions=sessions)
    except Exception as e:
        flash(f'Ошибка при загрузке сеансов лечения: {str(e)}', 'error')
        return render_template('treatment_sessions.html', sessions=[])

@app.route('/treatment-sessions/new', methods=['GET', 'POST'])
def new_treatment_session():
    """Создание нового сеанса лечения"""
    if request.method == 'POST':
        try:
            data = request.form
            session = TreatmentSession(
                course_id=int(data['course_id']),
                start_ts=datetime.strptime(data['start_ts'], '%Y-%m-%dT%H:%M'),
                status=None,  # Не устанавливаем статус, пусть вычисляется автоматически
                result_notes=data['result_notes'].strip() if data['result_notes'] else None
            )
            db.session.add(session)
            db.session.commit()
            flash('Сеанс лечения успешно создан!', 'success')
            return redirect(url_for('treatment_sessions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании сеанса лечения: {str(e)}', 'error')
    
    courses = TreatmentCourse.query.join(Guest).join(Doctor).join(TreatmentType).order_by(TreatmentCourse.created_at.desc()).all()
    return render_template('treatment_session_form.html', courses=courses, session=None)

@app.route('/treatment-sessions/<int:session_id>/edit', methods=['GET', 'POST'])
def edit_treatment_session(session_id):
    """Редактирование сеанса лечения"""
    session = TreatmentSession.query.get_or_404(session_id)
    if request.method == 'POST':
        try:
            data = request.form
            session.course_id = int(data['course_id'])
            session.start_ts = datetime.strptime(data['start_ts'], '%Y-%m-%dT%H:%M')
            session.result_notes = data['result_notes'].strip() if data['result_notes'] else None
            db.session.commit()
            flash('Сеанс лечения успешно обновлен!', 'success')
            return redirect(url_for('treatment_sessions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении сеанса лечения: {str(e)}', 'error')
    
    courses = TreatmentCourse.query.join(Guest).join(Doctor).join(TreatmentType).order_by(TreatmentCourse.created_at.desc()).all()
    return render_template('treatment_session_form.html', courses=courses, session=session)

@app.route('/treatment-sessions/<int:session_id>/delete', methods=['POST'])
def delete_treatment_session(session_id):
    """Удаление сеанса лечения"""
    session = TreatmentSession.query.get_or_404(session_id)
    try:
        db.session.delete(session)
        db.session.commit()
        flash('Сеанс лечения успешно удален!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении сеанса лечения: {str(e)}', 'error')
    return redirect(url_for('treatment_sessions'))

@app.route('/treatment-sessions/<int:session_id>/cancel', methods=['POST'])
def cancel_treatment_session(session_id):
    """Отмена сеанса лечения"""
    session = TreatmentSession.query.get_or_404(session_id)
    try:
        session.status = 'cancelled'
        db.session.commit()
        flash('Сеанс лечения успешно отменен!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при отмене сеанса: {str(e)}', 'error')
    return redirect(url_for('treatment_sessions'))

@app.route('/treatment-sessions/<int:session_id>/complete', methods=['POST'])
def complete_treatment_session(session_id):
    """Завершение сеанса лечения"""
    session = TreatmentSession.query.get_or_404(session_id)
    try:
        session.status = 'done'
        db.session.commit()
        flash('Сеанс лечения успешно завершен!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при завершении сеанса: {str(e)}', 'error')
    return redirect(url_for('treatment_sessions'))

# API роуты
@app.route('/api/guests')
def api_guests():
    """API для получения списка гостей"""
    try:
        guests = Guest.query.with_entities(Guest.guest_id, Guest.full_name).order_by(Guest.full_name).all()
        return jsonify([{'guest_id': g.guest_id, 'full_name': g.full_name} for g in guests])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms')
def api_rooms():
    """API для получения списка комнат"""
    try:
        rooms = Room.query.with_entities(Room.room_id, Room.number, Room.building).order_by(Room.building, Room.number).all()
        return jsonify([{'room_id': r.room_id, 'number': r.number, 'building': r.building} for r in rooms])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/doctors')
def api_doctors():
    """API для получения списка врачей"""
    try:
        doctors = Doctor.query.with_entities(Doctor.doctor_id, Doctor.full_name, Doctor.specialty).order_by(Doctor.full_name).all()
        return jsonify([{'doctor_id': d.doctor_id, 'full_name': d.full_name, 'specialty': d.specialty} for d in doctors])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/treatment-types')
def api_treatment_types():
    """API для получения списка типов процедур"""
    try:
        treatment_types = TreatmentType.query.with_entities(TreatmentType.treatment_type_id, TreatmentType.name, TreatmentType.base_price).order_by(TreatmentType.name).all()
        return jsonify([{'treatment_type_id': t.treatment_type_id, 'name': t.name, 'base_price': float(t.base_price)} for t in treatment_types])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаем таблицы, если их нет
    app.run(debug=True, host='0.0.0.0', port=5000) 