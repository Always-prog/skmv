from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, date
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # В продакшене используйте безопасный ключ

# Конфигурация базы данных
DB_CONFIG = {
    'host': 'localhost', #os.getenv('DB_HOST', 'localhost'),
    'database': 'sanatori', #os.getenv('DB_NAME', 'sanatori'),
    'user': 'kazah', #os.getenv('DB_USER', 'kazah'),
    'password': 'kazah', #os.getenv('DB_PASSWORD', 'kazah'),
    'port': '5432' #os.getenv('DB_PORT', '5432')
}

def get_db_connection():
    """Создает соединение с базой данных"""
    return psycopg2.connect(**DB_CONFIG)

def execute_query(query, params=None, fetch=True):
    """Выполняет SQL запрос и возвращает результат"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
                return [dict(row) for row in result]
            else:
                conn.commit()
                return cur.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@app.route('/')
def index():
    """Главная страница с обзором санатория"""
    try:
        # Статистика
        stats = {}
        
        # Общее количество гостей
        result = execute_query("SELECT COUNT(*) as count FROM guest")
        stats['total_guests'] = result[0]['count'] if result else 0
        
        # Текущие постояльцы
        result = execute_query("""
            SELECT COUNT(DISTINCT guest_id) as count 
            FROM (
                SELECT s.primary_guest as guest_id
                FROM stay s 
                WHERE CURRENT_DATE BETWEEN s.check_in_date AND s.check_out_date
                UNION
                SELECT sg.guest_id
                FROM stay_guest sg 
                JOIN stay s ON s.stay_id = sg.stay_id 
                WHERE CURRENT_DATE BETWEEN s.check_in_date AND s.check_out_date
            ) all_guests
        """)
        stats['current_guests'] = result[0]['count'] if result else 0
        
        # Свободные комнаты
        result = execute_query("""
            SELECT COUNT(*) as count FROM room r 
            WHERE r.room_id NOT IN (
                SELECT DISTINCT s.room_id FROM stay s 
                WHERE CURRENT_DATE BETWEEN s.check_in_date AND s.check_out_date
            )
        """)
        stats['available_rooms'] = result[0]['count'] if result else 0
        
        # Неоплаченные счета
        result = execute_query("""
            SELECT COUNT(*) as count FROM invoice 
            WHERE status IN ('unpaid', 'partly')
        """)
        stats['unpaid_invoices'] = result[0]['count'] if result else 0
        
        # Текущие путёвки
        current_stays = execute_query("""
            SELECT s.*, r.number as room_number, r.building, g.full_name as guest_name
            FROM stay s
            JOIN room r ON r.room_id = s.room_id
            JOIN guest g ON g.guest_id = s.primary_guest
            WHERE CURRENT_DATE BETWEEN s.check_in_date AND s.check_out_date
            ORDER BY s.check_in_date
        """)
        
        return render_template('index.html', stats=stats, current_stays=current_stays)
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'error')
        return render_template('index.html', stats={}, current_stays=[])

# Роуты для гостей
@app.route('/guests')
def guests():
    """Список всех гостей"""
    try:
        guests = execute_query("""
            SELECT *, 
                   EXTRACT(YEAR FROM AGE(birth_date)) as age
            FROM guest 
            ORDER BY full_name
        """)
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
            execute_query("""
                INSERT INTO guest (full_name, birth_date, sex, passport_num, phone, email)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (data['full_name'], data['birth_date'], data['sex'], 
                  data['passport_num'], data['phone'], data['email']), fetch=False)
            flash('Гость успешно добавлен!', 'success')
            return redirect(url_for('guests'))
        except Exception as e:
            flash(f'Ошибка при добавлении гостя: {str(e)}', 'error')
    
    return render_template('guest_form.html', guest=None)

@app.route('/guests/<int:guest_id>/edit', methods=['GET', 'POST'])
def edit_guest(guest_id):
    """Редактирование гостя"""
    if request.method == 'POST':
        try:
            data = request.form
            execute_query("""
                UPDATE guest 
                SET full_name = %s, birth_date = %s, sex = %s, 
                    passport_num = %s, phone = %s, email = %s
                WHERE guest_id = %s
            """, (data['full_name'], data['birth_date'], data['sex'],
                  data['passport_num'], data['phone'], data['email'], guest_id), fetch=False)
            flash('Данные гостя обновлены!', 'success')
            return redirect(url_for('guests'))
        except Exception as e:
            flash(f'Ошибка при обновлении: {str(e)}', 'error')
    
    guest = execute_query("SELECT * FROM guest WHERE guest_id = %s", (guest_id,))
    if not guest:
        flash('Гость не найден', 'error')
        return redirect(url_for('guests'))
    
    return render_template('guest_form.html', guest=guest[0])

# Роуты для комнат
@app.route('/rooms')
def rooms():
    """Список всех комнат"""
    try:
        rooms = execute_query("""
            SELECT r.*, 
                   CASE 
                       WHEN s.stay_id IS NOT NULL THEN 'occupied'
                       ELSE 'available'
                   END as status
            FROM room r
            LEFT JOIN (
                SELECT DISTINCT room_id, stay_id 
                FROM stay 
                WHERE CURRENT_DATE BETWEEN check_in_date AND check_out_date
            ) s ON r.room_id = s.room_id
            ORDER BY r.building, r.number
        """)
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
            execute_query("""
                INSERT INTO room (number, building, floor, capacity, daily_cost)
                VALUES (%s, %s, %s, %s, %s)
            """, (data['number'], data['building'], data['floor'], 
                  data['capacity'], data['daily_cost']), fetch=False)
            flash('Комната успешно добавлена!', 'success')
            return redirect(url_for('rooms'))
        except Exception as e:
            flash(f'Ошибка при добавлении комнаты: {str(e)}', 'error')
    
    return render_template('room_form.html', room=None)

# Роуты для путёвок
@app.route('/stays')
def stays():
    """Список всех путёвок"""
    try:
        stays = execute_query("""
            SELECT s.*, r.number as room_number, r.building, g.full_name as guest_name,
                   CASE
                       WHEN CURRENT_DATE < s.check_in_date THEN 'planned'
                       WHEN CURRENT_DATE BETWEEN s.check_in_date AND s.check_out_date THEN 'ongoing'
                       ELSE 'closed'
                   END as status
            FROM stay s
            JOIN room r ON r.room_id = s.room_id
            JOIN guest g ON g.guest_id = s.primary_guest
            ORDER BY s.check_in_date DESC
        """)
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
            execute_query("""
                INSERT INTO stay (room_id, primary_guest, check_in_date, check_out_date)
                VALUES (%s, %s, %s, %s)
            """, (data['room_id'], data['primary_guest'], 
                  data['check_in_date'], data['check_out_date']), fetch=False)
            flash('Путёвка успешно создана!', 'success')
            return redirect(url_for('stays'))
        except Exception as e:
            flash(f'Ошибка при создании путёвки: {str(e)}', 'error')
    
    rooms = execute_query("SELECT * FROM room ORDER BY building, number")
    guests = execute_query("SELECT * FROM guest ORDER BY full_name")
    return render_template('stay_form.html', rooms=rooms, guests=guests, stay=None)

# Роуты для счетов
@app.route('/invoices')
def invoices():
    """Список всех счетов"""
    try:
        invoices = execute_query("""
            SELECT i.*, s.check_in_date, s.check_out_date, g.full_name as guest_name
            FROM invoice i
            JOIN stay s ON s.stay_id = i.stay_id
            JOIN guest g ON g.guest_id = s.primary_guest
            ORDER BY i.issue_date DESC
        """)
        return render_template('invoices.html', invoices=invoices)
    except Exception as e:
        flash(f'Ошибка при загрузке счетов: {str(e)}', 'error')
        return render_template('invoices.html', invoices=[])

# API для получения данных
@app.route('/api/guests')
def api_guests():
    """API для получения списка гостей"""
    try:
        guests = execute_query("SELECT guest_id, full_name FROM guest ORDER BY full_name")
        return jsonify(guests)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms')
def api_rooms():
    """API для получения списка комнат"""
    try:
        rooms = execute_query("SELECT room_id, number, building FROM room ORDER BY building, number")
        return jsonify(rooms)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 