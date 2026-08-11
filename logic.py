# -*- coding: utf-8 -*-
"""
منطق اصلی برنامه: دیتابیس، محاسبات قیمت، مدیریت فروش
این فایل هیچ وابستگی به رابط کاربری ندارد (نه Tkinter، نه Flet)
پس دقیقاً همان چیزی است که در برنامه اصلی شما وجود داشت، بدون تغییر.
"""

import os
import sqlite3
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "restaurant_v2.db")


# ============================================================ دیتابیس ====
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        unit TEXT NOT NULL DEFAULT 'کیلوگرم',
        price REAL NOT NULL,
        stock REAL NOT NULL DEFAULT 0,
        min_stock REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingredient_id INTEGER NOT NULL,
        price REAL NOT NULL,
        changed_at TEXT NOT NULL,
        FOREIGN KEY(ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS dishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL DEFAULT 'غذای اصلی',
        profit_percent REAL NOT NULL DEFAULT 0,
        overhead_percent REAL NOT NULL DEFAULT 0,
        packaging_cost REAL NOT NULL DEFAULT 0,
        market_price REAL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS dish_ingredients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dish_id INTEGER NOT NULL,
        ingredient_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY(dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
        FOREIGN KEY(ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dish_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        is_takeout INTEGER NOT NULL DEFAULT 0,
        total_price REAL NOT NULL,
        sold_at TEXT NOT NULL,
        FOREIGN KEY(dish_id) REFERENCES dishes(id) ON DELETE CASCADE
    )""")

    conn.commit()
    conn.close()


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


# ---- توابع کالا و انبار ----
def add_or_update_ingredient(name, unit, price, stock, min_stock, ingredient_id=None):
    """
    ذخیره یا ویرایش کالا.
    اگر ingredient_id داده شود، همان رکورد (با هر نامی، حتی نام جدید) آپدیت می‌شود [ویرایش واقعی/rename].
    اگر ingredient_id داده نشود، طبق رفتار قبلی بر اساس نام یکتا درج/به‌روزرسانی می‌شود.
    خروجی: (True, "") در صورت موفقیت یا (False, "پیام خطا") در صورت تکراری بودن نام.
    """
    conn = get_conn()
    c = conn.cursor()
    ts = now_str()
    try:
        if ingredient_id:
            c.execute("SELECT price FROM ingredients WHERE id=?", (ingredient_id,))
            row = c.fetchone()
            if not row:
                conn.close()
                return False, "کالای مورد نظر برای ویرایش پیدا نشد."
            old_price = row[0]
            c.execute("""UPDATE ingredients SET name=?, unit=?, price=?, stock=?, min_stock=?, updated_at=?
                         WHERE id=?""", (name, unit, price, stock, min_stock, ts, ingredient_id))
            if float(old_price) != float(price):
                c.execute("INSERT INTO price_history (ingredient_id, price, changed_at) VALUES (?,?,?)",
                           (ingredient_id, price, ts))
        else:
            c.execute("SELECT id, price FROM ingredients WHERE name=?", (name,))
            row = c.fetchone()
            if row:
                ing_id, old_price = row
                c.execute("""UPDATE ingredients SET unit=?, price=?, stock=?, min_stock=?, updated_at=?
                             WHERE id=?""", (unit, price, stock, min_stock, ts, ing_id))
                if float(old_price) != float(price):
                    c.execute("INSERT INTO price_history (ingredient_id, price, changed_at) VALUES (?,?,?)",
                               (ing_id, price, ts))
            else:
                c.execute("""INSERT INTO ingredients (name, unit, price, stock, min_stock, updated_at)
                             VALUES (?,?,?,?,?,?)""", (name, unit, price, stock, min_stock, ts))
                ing_id = c.lastrowid
                c.execute("INSERT INTO price_history (ingredient_id, price, changed_at) VALUES (?,?,?)",
                           (ing_id, price, ts))
        conn.commit()
        conn.close()
        return True, ""
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"کالایی با نام «{name}» از قبل وجود دارد."


def get_all_ingredients():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, unit, price, stock, min_stock, updated_at FROM ingredients ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows


def get_ingredient_map():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT name, id, unit, price, stock FROM ingredients")
    rows = c.fetchall()
    conn.close()
    return {r[0]: {"id": r[1], "unit": r[2], "price": r[3], "stock": r[4]} for r in rows}


def delete_ingredient(ingredient_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM dish_ingredients WHERE ingredient_id=?", (ingredient_id,))
    used = c.fetchone()[0]
    if used > 0:
        conn.close()
        return False, f"این کالا در {used} غذا استفاده شده است."
    c.execute("DELETE FROM ingredients WHERE id=?", (ingredient_id,))
    conn.commit()
    conn.close()
    return True, ""


# ---- توابع غذا و منو ----
def save_dish(name, category, profit_percent, overhead_percent, packaging_cost, market_price, ingredient_rows, dish_id=None):
    """
    ذخیره یا ویرایش غذا.
    اگر dish_id داده شود، همان رکورد (با هر نامی، حتی نام جدید) آپدیت می‌شود [ویرایش واقعی/rename].
    اگر dish_id داده نشود، طبق رفتار قبلی بر اساس نام یکتا درج/به‌روزرسانی می‌شود.
    خروجی: (dish_id, "") در صورت موفقیت یا (None, "پیام خطا") در صورت تکراری بودن نام.
    """
    conn = get_conn()
    c = conn.cursor()
    try:
        if dish_id:
            c.execute("SELECT id FROM dishes WHERE id=?", (dish_id,))
            if not c.fetchone():
                conn.close()
                return None, "غذای مورد نظر برای ویرایش پیدا نشد."
            c.execute("""UPDATE dishes SET name=?, category=?, profit_percent=?, overhead_percent=?,
                         packaging_cost=?, market_price=? WHERE id=?""",
                       (name, category, profit_percent, overhead_percent, packaging_cost, market_price, dish_id))
            c.execute("DELETE FROM dish_ingredients WHERE dish_id=?", (dish_id,))
        else:
            c.execute("SELECT id FROM dishes WHERE name=?", (name,))
            row = c.fetchone()
            if row:
                dish_id = row[0]
                c.execute("""UPDATE dishes SET category=?, profit_percent=?, overhead_percent=?,
                             packaging_cost=?, market_price=? WHERE id=?""",
                           (category, profit_percent, overhead_percent, packaging_cost, market_price, dish_id))
                c.execute("DELETE FROM dish_ingredients WHERE dish_id=?", (dish_id,))
            else:
                c.execute("""INSERT INTO dishes (name, category, profit_percent, overhead_percent, packaging_cost, market_price)
                             VALUES (?,?,?,?,?,?)""",
                           (name, category, profit_percent, overhead_percent, packaging_cost, market_price))
                dish_id = c.lastrowid
        for ing_id, amount in ingredient_rows:
            c.execute("INSERT INTO dish_ingredients (dish_id, ingredient_id, amount) VALUES (?,?,?)",
                       (dish_id, ing_id, amount))
        conn.commit()
        conn.close()
        return dish_id, ""
    except sqlite3.IntegrityError:
        conn.close()
        return None, f"غذایی با نام «{name}» از قبل وجود دارد."


def update_dish_market_price(dish_id, new_price):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE dishes SET market_price=? WHERE id=?", (new_price, dish_id))
    conn.commit()
    conn.close()


def get_all_dishes():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, category, profit_percent, overhead_percent, packaging_cost, market_price FROM dishes ORDER BY category, name")
    rows = c.fetchall()
    conn.close()
    return rows


def get_dish_full(dish_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, category, profit_percent, overhead_percent, packaging_cost, market_price FROM dishes WHERE id=?", (dish_id,))
    dish = c.fetchone()
    c.execute("""SELECT i.id, i.name, i.unit, i.price, di.amount
                 FROM dish_ingredients di JOIN ingredients i ON i.id = di.ingredient_id
                 WHERE di.dish_id=?""", (dish_id,))
    ingredients = c.fetchall()
    conn.close()
    return dish, ingredients


def delete_dish(dish_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM dishes WHERE id=?", (dish_id,))
    conn.commit()
    conn.close()


# ---- توابع فروش و انبارداری ----
def process_sale(dish_id, qty, is_takeout):
    conn = get_conn()
    c = conn.cursor()
    dish, ingredients = get_dish_full(dish_id)

    insufficient = []
    for ing_id, name, unit, price, amount in ingredients:
        required = amount * qty
        c.execute("SELECT stock FROM ingredients WHERE id=?", (ing_id,))
        curr_stock = c.fetchone()[0]
        if curr_stock < required:
            insufficient.append(f"{name} (نیاز: {required} {unit} | موجودی: {curr_stock} {unit})")

    if insufficient:
        conn.close()
        return False, "موجودی انبار کافی نیست:\n" + "\n".join(insufficient)

    for ing_id, name, unit, price, amount in ingredients:
        required = amount * qty
        c.execute("UPDATE ingredients SET stock = stock - ? WHERE id=?", (required, ing_id))

    costs = [price * amount for _, _, _, price, amount in ingredients]
    mat_cost = sum(costs)
    overhead = mat_cost * dish[4] / 100.0
    pack = dish[5] if is_takeout else 0
    total_cost = mat_cost + overhead + pack

    base_unit_price = dish[6] if (dish[6] and dish[6] > 0) else total_cost * (1 + dish[3] / 100.0)
    final_price = base_unit_price * qty

    c.execute("INSERT INTO sales (dish_id, quantity, is_takeout, total_price, sold_at) VALUES (?,?,?,?,?)",
              (dish_id, qty, 1 if is_takeout else 0, final_price, now_str()))

    conn.commit()
    conn.close()
    return True, "فروش با موفقیت ثبت شد و انبار به‌روزرسانی گردید."


# ============================================================ ابزارهای محاسباتی ====
def fmt(n):
    """قالب‌بندی عدد با جداکننده هزارگان، مثلاً 12000 -> 12,000"""
    try:
        return f"{n:,.0f}"
    except Exception:
        return str(n)


def to_float(s, default=0.0):
    """تبدیل امن رشته به عدد اعشاری (برای ورودی‌های فرم)"""
    try:
        return float(str(s).replace(",", "").strip() or default)
    except Exception:
        return default


def compute_dish_cost(overhead_pct, profit_pct, pack_cost, is_takeout, ing_costs_sum):
    """
    محاسبه بهای تمام‌شده و قیمت فروش پیشنهادی یک غذا.
    خروجی: (هزینه مواد, مبلغ سربار, هزینه بسته‌بندی, بهای تمام‌شده کل, مبلغ سود, قیمت فروش نهایی)
    """
    overhead_amount = ing_costs_sum * overhead_pct / 100.0
    packaging = pack_cost if is_takeout else 0.0
    total_cost = ing_costs_sum + overhead_amount + packaging
    final_price = total_cost * (1 + profit_pct / 100.0)
    profit_amount = final_price - total_cost
    return ing_costs_sum, overhead_amount, packaging, total_cost, profit_amount, final_price