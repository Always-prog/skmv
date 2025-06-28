from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from datetime import datetime, date
from sqlalchemy import func, and_, or_, extract
from models import db, Guest, Room, Stay, StayGuest, Invoice, Payment

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

# Роуты для счетов
@app.route('/invoices')
def invoices():
    """Список всех счетов"""
    try:
        invoices = Invoice.query.join(Stay).join(Guest, Stay.primary_guest == Guest.guest_id).order_by(Invoice.issue_date.desc()).all()
        return render_template('invoices.html', invoices=invoices)
    except Exception as e:
        flash(f'Ошибка при загрузке счетов: {str(e)}', 'error')
        return render_template('invoices.html', invoices=[])

# API для получения данных
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создаем таблицы, если их нет
    app.run(debug=True, host='0.0.0.0', port=5000) 