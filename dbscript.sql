/*------------------------ 1. ГОСТИ ------------------------*/
CREATE TABLE guest (
    guest_id     SERIAL PRIMARY KEY,
    full_name    TEXT NOT NULL,
    birth_date   DATE NOT NULL,
    sex          CHAR(1) CHECK (sex IN ('M','F')),
    passport_num VARCHAR(20) UNIQUE,
    phone        VARCHAR(20),
    email        TEXT
);

/*------------------------ 2. КОМНАТЫ -----------------------*/
CREATE TABLE room (
    room_id    SERIAL PRIMARY KEY,
    number     TEXT NOT NULL UNIQUE,
    building   TEXT NOT NULL,
    floor      INT,
    capacity   INT          NOT NULL CHECK (capacity > 0),
    daily_cost NUMERIC(10,2) NOT NULL CHECK (daily_cost >= 0)
);

/*------------------------ 3. ПУТЁВКИ -----------------------*/
CREATE TABLE stay (
    stay_id        SERIAL PRIMARY KEY,
    room_id        INT NOT NULL REFERENCES room,
    primary_guest   INT NOT NULL REFERENCES guest,
    check_in_date  DATE NOT NULL,
    check_out_date DATE NOT NULL,
    CHECK (check_out_date >= check_in_date)
);

/*--------------------- 4. ГОСТИ-В-ПУТЁВКЕ ------------------*/
CREATE TABLE stay_guest (
    stay_guest_id SERIAL PRIMARY KEY,
    stay_id       INT NOT NULL REFERENCES stay ON DELETE CASCADE,
    guest_id      INT NOT NULL REFERENCES guest,
    relation      TEXT                             -- «гость», «ребёнок»…
);

--/*---------------- Ограничение вместимости комнаты ----------*/
--CREATE OR REPLACE FUNCTION check_room_capacity() RETURNS TRIGGER AS $$
--DECLARE
--    v_room_id      INT;
--    v_capacity     INT;
--    v_current_load INT;
--BEGIN
--    /* номер комнаты текущей путёвки */
--    SELECT room_id INTO v_room_id FROM stay WHERE stay_id = NEW.stay_id;
--
--    /* её вместимость */
--    SELECT capacity INTO v_capacity FROM room WHERE room_id = v_room_id;
--
--    /* сколько уже постояльцев (с учётом NEW) пересекаются по датам */
--    SELECT COUNT(*) INTO v_current_load
--    FROM stay_guest sg
--    JOIN stay s ON s.stay_id = sg.stay_id
--    WHERE s.room_id = v_room_id
--      AND s.check_in_date <= (SELECT check_out_date FROM stay WHERE stay_id = NEW.stay_id)
--      AND s.check_out_date >= (SELECT check_in_date  FROM stay WHERE stay_id = NEW.stay_id);
--
--    IF v_current_load > v_capacity THEN
--        RAISE EXCEPTION 'Room capacity exceeded (allowed %, got %)', v_capacity, v_current_load;
--    END IF;
--    RETURN NEW;
--END;
--$$ LANGUAGE plpgsql;

--CREATE TRIGGER trg_room_capacity
--    BEFORE INSERT OR UPDATE ON stay_guest
--    FOR EACH ROW EXECUTE FUNCTION check_room_capacity();

/*---------------------- 5. ВРАЧИ ---------------------------*/
CREATE TABLE doctor (
    doctor_id  SERIAL PRIMARY KEY,
    full_name  TEXT NOT NULL,
    specialty  TEXT NOT NULL,
    phone      TEXT
);

/*------------------- 6. ТИПЫ ПРОЦЕДУР ----------------------*/
CREATE TABLE treatment_type (
    treatment_type_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    base_price  NUMERIC(10,2) NOT NULL CHECK (base_price >= 0)
);

/*------------------- 7. КУРСЫ ЛЕЧЕНИЯ ----------------------*/
CREATE TABLE treatment_course (
    course_id         SERIAL PRIMARY KEY,
    guest_id          INT NOT NULL REFERENCES guest,
    doctor_id         INT NOT NULL REFERENCES doctor,
    treatment_type_id INT NOT NULL REFERENCES treatment_type,
    created_at        TIMESTAMP DEFAULT now()
);

/*------------------- 8. СЕАНСЫ ЛЕЧЕНИЯ ---------------------*/
CREATE TABLE treatment_session (
    session_id  SERIAL PRIMARY KEY,
    course_id   INT NOT NULL REFERENCES treatment_course ON DELETE CASCADE,
    start_ts    TIMESTAMP NOT NULL,
    status      TEXT CHECK (status IN ('planned','done','cancelled')),
    result_notes TEXT
);

/*---------------------- 9. СЧЕТА ---------------------------*/
CREATE TABLE invoice (
    invoice_id  SERIAL PRIMARY KEY,
    stay_id     INT NOT NULL REFERENCES stay,
    issue_date  DATE NOT NULL,
    total_sum   NUMERIC(12,2) NOT NULL CHECK (total_sum >= 0),
    status      TEXT CHECK (status IN ('unpaid','partly','paid'))
);

/*--------------------- 10. ПЛАТЕЖИ -------------------------*/
CREATE TABLE payment (
    payment_id SERIAL PRIMARY KEY,
    invoice_id INT NOT NULL REFERENCES invoice,
    pay_ts     TIMESTAMP NOT NULL,
    amount     NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    method     TEXT
);

/*------------------ 11. VIEW со статусом -------------------*/
-- текущий статус путёвки вычисляем динамически
CREATE VIEW stay_status_vw AS
SELECT s.*,
       CASE
           WHEN CURRENT_DATE <  s.check_in_date                       THEN 'planned'
           WHEN CURRENT_DATE BETWEEN s.check_in_date AND s.check_out_date THEN 'ongoing'
           ELSE 'closed'
       END AS status
FROM stay s;
