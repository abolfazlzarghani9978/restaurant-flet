# -*- coding: utf-8 -*-
"""
سیستم جامع مدیریت مالی، انبارداری، قیمت‌گذاری و پیشنهاد هوشمند قیمت رستوران
نسخه اندرویدی / دسکتاپ / وب - ساخته‌شده با Flet
شامل ۷ بخش: ثبت فروش، محاسبه غذا، کالاها و انبار، قیمت‌گذاری هوشمند، گزارش منو، داشبورد، ترازنامه مالی
"""
import flet as ft
import logic

# رنگ‌های اصلی برنامه (هماهنگ با نسخه دسکتاپ قبلی)
ACCENT = ft.Colors.ORANGE_700
ACCENT_DARK = ft.Colors.ORANGE_900
DANGER = ft.Colors.RED_600
SUCCESS = ft.Colors.GREEN_700
DARK_BG = "#1e293b"
CARD_BORDER = ft.Colors.GREY_300


def card(content, expand=False):
    return ft.Container(
        content=content,
        padding=16,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, CARD_BORDER),
        border_radius=12,
        expand=expand,
    )


def section_title(text):
    return ft.Text(text, size=16, weight=ft.FontWeight.BOLD, color="#0f172a")


def main(page: ft.Page):
    page.title = "مدیریت مالی و انبار رستوران"
    page.rtl = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = "#f1f5f9"
    page.theme = ft.Theme(color_scheme_seed=ACCENT)

    logic.init_db()

    # لیست توابع رفرش هر تب - بعد از هر تغییر داده (فروش، ذخیره غذا، ذخیره کالا و ...) همه به‌روز می‌شوند
    refreshers = []

    def refresh_all():
        for f in refreshers:
            f()
        page.update()

    # ============================================================
    # تب ۱: ثبت فروش
    # ============================================================
    def build_sales_tab():
        dish_map = {}
        dish_dropdown = ft.Dropdown(label="انتخاب غذا", width=320, options=[])
        qty_field = ft.TextField(label="تعداد", width=320, value="1", keyboard_type=ft.KeyboardType.NUMBER)
        takeout_switch = ft.Switch(label="سفارش بیرون‌بر (محاسبه هزینه بسته‌بندی)", value=False)
        status_text = ft.Text("", size=13)

        def refresh():
            dish_map.clear()
            dish_map.update({f"{d[2]} - {d[1]}": d[0] for d in logic.get_all_dishes()})
            dish_dropdown.options = [ft.dropdown.Option(k) for k in dish_map.keys()]
            if dish_dropdown.value not in dish_map:
                dish_dropdown.value = None

        def submit_sale(e):
            dish_id = dish_map.get(dish_dropdown.value)
            qty = int(logic.to_float(qty_field.value))
            if not dish_id or qty <= 0:
                status_text.value = "⚠️ لطفاً غذا و تعداد معتبر انتخاب کنید."
                status_text.color = DANGER
                page.update()
                return

            ok, msg = logic.process_sale(dish_id, qty, takeout_switch.value)
            status_text.value = ("✅ " if ok else "❌ ") + msg
            status_text.color = SUCCESS if ok else DANGER
            if ok:
                qty_field.value = "1"
                takeout_switch.value = False
            refresh_all()

        refreshers.append(refresh)

        content = ft.Column([
            card(ft.Column([
                section_title("🛒 ثبت فروش و کسر خودکار از انبار"),
                ft.Divider(),
                dish_dropdown,
                qty_field,
                takeout_switch,
                ft.ElevatedButton("🛍️ ثبت نهایی فروش", on_click=submit_sale,
                                   bgcolor=ACCENT, color=ft.Colors.WHITE, width=320,
                                   style=ft.ButtonStyle(padding=18)),
                status_text,
            ], spacing=14)),
        ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

        refresh()
        return content

    # ============================================================
    # تب ۲: کالاها و انبار
    # ============================================================
    ingredient_options_refreshers = []  # وقتی کالا اضافه شد، دراپ‌داون‌های تب رسپی به‌روز شوند

    def build_ingredients_tab():
        name_field = ft.TextField(label="نام کالا", width=280)
        unit_field = ft.Dropdown(
            label="واحد سنجش", width=280, value="کیلوگرم",
            options=[ft.dropdown.Option(u) for u in
                     ["کیلوگرم", "گرم", "لیتر", "میلی‌لیتر", "عدد", "بسته"]],
        )
        price_field = ft.TextField(label="قیمت واحد (تومان)", width=280, keyboard_type=ft.KeyboardType.NUMBER)
        stock_field = ft.TextField(label="موجودی اولیه", width=280, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        min_stock_field = ft.TextField(label="نقطه سفارش (هشدار)", width=280, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        search_field = ft.TextField(label="🔍 جستجوی کالا", width=280)
        status_text = ft.Text("", size=13)

        data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("نام کالا")),
                ft.DataColumn(ft.Text("واحد")),
                ft.DataColumn(ft.Text("قیمت")),
                ft.DataColumn(ft.Text("موجودی")),
                ft.DataColumn(ft.Text("نقطه سفارش")),
                ft.DataColumn(ft.Text("عملیات")),
            ],
            rows=[],
        )
        raw_data = []

        def edit_ingredient_click(item):
            ing_id, name, unit, price, stock, min_stock, updated = item
            editing_ingredient_id[0] = ing_id
            name_field.value = name
            unit_field.value = unit
            price_field.value = str(price)
            stock_field.value = str(stock)
            min_stock_field.value = str(min_stock)
            status_text.value = f"✏️ در حال ویرایش «{name}» — می‌توانید نام را هم تغییر دهید. پس از اعمال تغییرات، «ذخیره کالا» را بزنید."
            status_text.color = ACCENT_DARK
            page.update()

        def delete_ingredient_click(item):
            ing_id, name = item[0], item[1]
            if editing_ingredient_id[0] == ing_id:
                clear_form()
            ok, msg = logic.delete_ingredient(ing_id)
            status_text.value = ("✅ " if ok else "❌ ") + (msg if msg else f"کالای «{name}» حذف شد.")
            status_text.color = SUCCESS if ok else DANGER
            refresh_all()

        def render_table():
            data_table.rows.clear()
            query = (search_field.value or "").strip().lower()
            for item in raw_data:
                ing_id, name, unit, price, stock, min_stock, updated = item
                if query and query not in name.lower():
                    continue
                low_stock = stock <= min_stock
                data_table.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(name)),
                        ft.DataCell(ft.Text(unit)),
                        ft.DataCell(ft.Text(logic.fmt(price))),
                        ft.DataCell(ft.Text(str(stock), color=DANGER if low_stock else None,
                                             weight=ft.FontWeight.BOLD if low_stock else None)),
                        ft.DataCell(ft.Text(str(min_stock))),
                        ft.DataCell(ft.Row([
                            ft.IconButton(icon=ft.Icons.EDIT, icon_color=ACCENT,
                                          tooltip="ویرایش",
                                          on_click=lambda e, it=item: edit_ingredient_click(it)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_color=DANGER,
                                          tooltip="حذف",
                                          on_click=lambda e, it=item: delete_ingredient_click(it)),
                        ], spacing=0)),
                    ])
                )
            page.update()

        def refresh():
            raw_data.clear()
            raw_data.extend(logic.get_all_ingredients())
            render_table()
            for f in ingredient_options_refreshers:
                f()

        search_field.on_change = lambda e: render_table()

        editing_ingredient_id = [None]  # وقتی مقدار دارد یعنی در حالت ویرایش (رکورد قبلی حتی با نام جدید آپدیت می‌شود)

        def clear_form():
            name_field.value = ""
            price_field.value = ""
            stock_field.value = "0"
            min_stock_field.value = "0"
            status_text.value = ""
            editing_ingredient_id[0] = None

        def save_ingredient(e):
            name = (name_field.value or "").strip()
            price = logic.to_float(price_field.value)
            stock = logic.to_float(stock_field.value)
            min_stock = logic.to_float(min_stock_field.value)
            if not name or price <= 0:
                status_text.value = "⚠️ لطفاً نام کالا و قیمت معتبر وارد کنید."
                status_text.color = DANGER
                page.update()
                return
            ok, msg = logic.add_or_update_ingredient(
                name, unit_field.value, price, stock, min_stock, editing_ingredient_id[0]
            )
            if not ok:
                status_text.value = "❌ " + msg
                status_text.color = DANGER
                page.update()
                return
            was_edit = editing_ingredient_id[0] is not None
            clear_form()
            status_text.value = f"✅ کالای «{name}» با موفقیت {'ویرایش' if was_edit else 'ذخیره'} شد."
            status_text.color = SUCCESS
            refresh_all()

        refreshers.append(refresh)

        form = card(ft.Column([
            section_title("➕ افزودن / ویرایش کالا"),
            ft.Divider(),
            name_field, unit_field, price_field, stock_field, min_stock_field,
            ft.Row([
                ft.ElevatedButton("💾 ذخیره کالا", on_click=save_ingredient,
                                   bgcolor=ACCENT, color=ft.Colors.WHITE),
                ft.OutlinedButton("پاک کردن فرم", on_click=lambda e: (clear_form(), page.update())),
            ]),
            status_text,
        ], spacing=10))

        table_section = card(ft.Column([
            ft.Row([section_title("📦 لیست کالاها و موجودی انبار"), search_field], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),
            ft.Row([data_table], scroll=ft.ScrollMode.AUTO),
        ], spacing=10), expand=True)

        refresh()
        return ft.Column([form, table_section], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    # ============================================================
    # تب ۳: محاسبه غذا / رسپی
    # ============================================================
    def build_dish_tab():
        dish_name_field = ft.TextField(label="نام غذا", width=280)
        dish_category_field = ft.Dropdown(
            label="دسته‌بندی", width=280, value="غذای اصلی",
            options=[ft.dropdown.Option(c) for c in
                     ["غذای اصلی", "پیش‌غذا", "نوشیدنی", "دسر", "سالاد"]],
        )
        profit_field = ft.TextField(label="درصد سود (%)", width=280, value="30", keyboard_type=ft.KeyboardType.NUMBER)
        overhead_field = ft.TextField(label="درصد سربار (%)", width=280, value="10", keyboard_type=ft.KeyboardType.NUMBER)
        packaging_field = ft.TextField(label="هزینه بسته‌بندی (بیرون‌بر)", width=280, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        market_price_field = ft.TextField(label="قیمت فروش دستی (اختیاری)", width=280, keyboard_type=ft.KeyboardType.NUMBER)

        ingredient_rows_column = ft.Column(spacing=6)
        ingredient_rows = []
        summary_text = ft.Text("", size=13, weight=ft.FontWeight.BOLD)
        dish_status_text = ft.Text("", size=13)

        def get_ingredient_options():
            ing_map = logic.get_ingredient_map()
            return list(ing_map.keys()), ing_map

        def recalc_summary():
            ing_map = logic.get_ingredient_map()
            total_mat_cost = 0.0
            for row in ingredient_rows:
                name = row["dropdown"].value
                amount = logic.to_float(row["amount"].value)
                info = ing_map.get(name)
                if info and amount > 0:
                    cost = info["price"] * amount
                    row["cost_text"].value = logic.fmt(cost)
                    total_mat_cost += cost
                else:
                    row["cost_text"].value = "0"

            overhead_pct = logic.to_float(overhead_field.value)
            profit_pct = logic.to_float(profit_field.value)
            pack_cost = logic.to_float(packaging_field.value)

            mat, overhead_amt, pack, total, profit_amt, final = logic.compute_dish_cost(
                overhead_pct, profit_pct, pack_cost, True, total_mat_cost
            )
            summary_text.value = (
                f"هزینه مواد: {logic.fmt(mat)}   |   سربار: {logic.fmt(overhead_amt)}   |   "
                f"بسته‌بندی: {logic.fmt(pack)} تومان\n"
                f"💰 بهای تمام‌شده: {logic.fmt(total)} تومان   |   سود: {logic.fmt(profit_amt)}   |   "
                f"قیمت فروش پیشنهادی: {logic.fmt(final)} تومان"
            )
            page.update()

        def remove_ingredient_row(row):
            ingredient_rows.remove(row)
            ingredient_rows_column.controls.remove(row["container"])
            recalc_summary()

        def add_ingredient_row(e=None):
            names, _ = get_ingredient_options()
            dropdown = ft.Dropdown(width=170, options=[ft.dropdown.Option(n) for n in names])
            dropdown.on_change = lambda e: recalc_summary()
            amount_field = ft.TextField(width=80, value="0", keyboard_type=ft.KeyboardType.NUMBER)
            amount_field.on_change = lambda e: recalc_summary()
            cost_text = ft.Text("0", width=90)
            row = {"dropdown": dropdown, "amount": amount_field, "cost_text": cost_text}
            delete_btn = ft.IconButton(icon=ft.Icons.DELETE, icon_color=DANGER,
                                        on_click=lambda e: remove_ingredient_row(row))
            row_container = ft.Row([dropdown, amount_field, ft.Text("مقدار"), cost_text, ft.Text("تومان"), delete_btn], spacing=6)
            row["container"] = row_container
            ingredient_rows.append(row)
            ingredient_rows_column.controls.append(row_container)
            page.update()

        def refresh_ingredient_options():
            names, _ = get_ingredient_options()
            for row in ingredient_rows:
                row["dropdown"].options = [ft.dropdown.Option(n) for n in names]

        ingredient_options_refreshers.append(refresh_ingredient_options)

        editing_dish_id = [None]  # وقتی مقدار دارد یعنی در حالت ویرایش (رکورد قبلی حتی با نام جدید آپدیت می‌شود)

        def clear_dish_form():
            dish_name_field.value = ""
            profit_field.value = "30"
            overhead_field.value = "10"
            packaging_field.value = "0"
            market_price_field.value = ""
            ingredient_rows.clear()
            ingredient_rows_column.controls.clear()
            dish_status_text.value = ""
            summary_text.value = ""
            editing_dish_id[0] = None

        def save_dish_click(e):
            name = (dish_name_field.value or "").strip()
            if not name:
                dish_status_text.value = "⚠️ لطفاً نام غذا را وارد کنید."
                dish_status_text.color = DANGER
                page.update()
                return

            ing_map = logic.get_ingredient_map()
            ingredient_data = []
            for row in ingredient_rows:
                info = ing_map.get(row["dropdown"].value)
                amount = logic.to_float(row["amount"].value)
                if info and amount > 0:
                    ingredient_data.append((info["id"], amount))

            if not ingredient_data:
                dish_status_text.value = "⚠️ حداقل یک کالا با مقدار معتبر انتخاب کنید."
                dish_status_text.color = DANGER
                page.update()
                return

            market_price = logic.to_float(market_price_field.value) or None
            new_id, msg = logic.save_dish(
                name, dish_category_field.value,
                logic.to_float(profit_field.value),
                logic.to_float(overhead_field.value),
                logic.to_float(packaging_field.value),
                market_price,
                ingredient_data,
                editing_dish_id[0],
            )
            if new_id is None:
                dish_status_text.value = "❌ " + msg
                dish_status_text.color = DANGER
                page.update()
                return
            was_edit = editing_dish_id[0] is not None
            clear_dish_form()
            dish_status_text.value = f"✅ غذای «{name}» با موفقیت {'ویرایش' if was_edit else 'ذخیره'} شد."
            dish_status_text.color = SUCCESS
            refresh_all()

        dish_list_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("نام غذا")),
                ft.DataColumn(ft.Text("دسته")),
                ft.DataColumn(ft.Text("سود %")),
                ft.DataColumn(ft.Text("عملیات")),
            ],
            rows=[],
        )

        def edit_dish_click(d_id):
            dish, ingredients = logic.get_dish_full(d_id)
            if not dish:
                return
            _, name, cat, profit_p, overhead_p, pack_cost, market_price = dish

            editing_dish_id[0] = d_id
            dish_name_field.value = name
            dish_category_field.value = cat
            profit_field.value = str(profit_p)
            overhead_field.value = str(overhead_p)
            packaging_field.value = str(pack_cost)
            market_price_field.value = str(market_price) if market_price else ""

            ingredient_rows.clear()
            ingredient_rows_column.controls.clear()
            for ing_id, iname, unit, price, amount in ingredients:
                add_ingredient_row()
                new_row = ingredient_rows[-1]
                new_row["dropdown"].value = iname
                new_row["amount"].value = str(amount)

            dish_status_text.value = f"✏️ در حال ویرایش «{name}» — می‌توانید نام را هم تغییر دهید. پس از اعمال تغییرات، «ذخیره غذا» را بزنید."
            dish_status_text.color = ACCENT_DARK
            recalc_summary()

        def delete_dish_click(d_id, name):
            if editing_dish_id[0] == d_id:
                clear_dish_form()
            logic.delete_dish(d_id)
            dish_status_text.value = f"✅ غذای «{name}» حذف شد."
            dish_status_text.color = SUCCESS
            refresh_all()

        def refresh_dish_list():
            dish_list_table.rows.clear()
            for d in logic.get_all_dishes():
                d_id, name = d[0], d[1]
                dish_list_table.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(d[1])),
                    ft.DataCell(ft.Text(d[2])),
                    ft.DataCell(ft.Text(str(d[3]))),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.Icons.EDIT, icon_color=ACCENT,
                                      tooltip="ویرایش",
                                      on_click=lambda e, did=d_id: edit_dish_click(did)),
                        ft.IconButton(icon=ft.Icons.DELETE, icon_color=DANGER,
                                      tooltip="حذف",
                                      on_click=lambda e, did=d_id, dname=name: delete_dish_click(did, dname)),
                    ], spacing=0)),
                ]))

        refreshers.append(refresh_dish_list)

        left_form = card(ft.Column([
            section_title("🍳 محاسبه غذا / رسپی"),
            ft.Divider(),
            dish_name_field, dish_category_field,
            ft.Row([profit_field, overhead_field], wrap=True),
            ft.Row([packaging_field, market_price_field], wrap=True),
            ft.Divider(),
            ft.Text("کالاهای مصرفی:", weight=ft.FontWeight.BOLD),
            ingredient_rows_column,
            ft.ElevatedButton("➕ افزودن کالا به رسپی", on_click=add_ingredient_row),
            ft.Divider(),
            summary_text,
            ft.Row([
                ft.ElevatedButton("💾 ذخیره غذا", on_click=save_dish_click,
                                   bgcolor=ACCENT, color=ft.Colors.WHITE),
                ft.OutlinedButton("پاک کردن فرم", on_click=lambda e: (clear_dish_form(), page.update())),
            ]),
            dish_status_text,
        ], spacing=10, scroll=ft.ScrollMode.AUTO), expand=True)

        right_list = card(ft.Column([
            section_title("📋 غذاهای ثبت‌شده"),
            ft.Divider(),
            ft.Row([dish_list_table], scroll=ft.ScrollMode.AUTO),
        ], spacing=10), expand=True)

        refresh_dish_list()
        return ft.Column([left_form, right_list], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    # ============================================================
    # تب ۴: پیشنهاد هوشمند قیمت
    # ============================================================
    def build_smart_pricing_tab():
        search_field = ft.TextField(label="🔍 جستجوی غذا", width=280)
        info_text = ft.Text("", size=13)
        raw_data = []

        pricing_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("نام غذا")),
                ft.DataColumn(ft.Text("قیمت فعلی")),
                ft.DataColumn(ft.Text("بهای تمام‌شده جدید")),
                ft.DataColumn(ft.Text("قیمت پیشنهادی")),
                ft.DataColumn(ft.Text("تغییر")),
            ],
            rows=[],
        )

        def compute_data():
            raw_data.clear()
            for d in logic.get_all_dishes():
                d_id, name, cat, profit_p, overhead_p, pack_cost, curr_market_price = d
                _, ingredients = logic.get_dish_full(d_id)
                mat_cost = sum(price * amount for _, _, _, price, amount in ingredients)
                _, _, _, total_cost, _, rec_price = logic.compute_dish_cost(overhead_p, profit_p, pack_cost, False, mat_cost)
                curr_price = curr_market_price if (curr_market_price and curr_market_price > 0) else rec_price
                diff = rec_price - curr_price
                diff_pct = (diff / curr_price * 100) if curr_price > 0 else 0
                raw_data.append({
                    "id": d_id, "name": name, "curr_price": curr_price, "total_cost": total_cost,
                    "rec_price": rec_price, "diff": diff, "diff_pct": diff_pct,
                })

        def render_table():
            pricing_table.rows.clear()
            query = (search_field.value or "").strip().lower()
            for item in raw_data:
                if query and query not in item["name"].lower():
                    continue
                up = item["diff"] > 0
                sign = "+" if up else ""
                pricing_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(item["name"])),
                            ft.DataCell(ft.Text(logic.fmt(item["curr_price"]))),
                            ft.DataCell(ft.Text(logic.fmt(item["total_cost"]))),
                            ft.DataCell(ft.Text(logic.fmt(item["rec_price"]), weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.Text(f"{sign}{logic.fmt(item['diff'])} ({item['diff_pct']:+.1f}%)",
                                                 color=ft.Colors.AMBER_800 if up else SUCCESS)),
                        ],
                    )
                )
            page.update()

        search_field.on_change = lambda e: render_table()

        def refresh():
            compute_data()
            render_table()

        refreshers.append(refresh)

        def apply_all_prices(e):
            for item in raw_data:
                logic.update_dish_market_price(item["id"], item["rec_price"])
            info_text.value = f"✅ قیمت پیشنهادی برای {len(raw_data)} غذا روی منو اعمال شد."
            info_text.color = SUCCESS
            refresh_all()

        content = ft.Column([
            card(ft.Column([
                ft.Row([section_title("💡 سیستم پیشنهاد خودکار و هوشمند قیمت"), search_field],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),
                ft.Row([pricing_table], scroll=ft.ScrollMode.AUTO),
                ft.Divider(),
                ft.Row([
                    ft.ElevatedButton("✅ اعمال همه قیمت‌های پیشنهادی روی منو", on_click=apply_all_prices,
                                       bgcolor=ACCENT, color=ft.Colors.WHITE),
                ]),
                info_text,
            ], spacing=10), expand=True),
        ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

        refresh()
        return content

    # ============================================================
    # تب ۵: گزارش منو
    # ============================================================
    def build_report_tab():
        search_field = ft.TextField(label="🔍 جستجو (نام یا دسته)", width=280)
        raw_data = []

        report_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("دسته")),
                ft.DataColumn(ft.Text("نام غذا")),
                ft.DataColumn(ft.Text("هزینه مواد")),
                ft.DataColumn(ft.Text("سربار")),
                ft.DataColumn(ft.Text("بسته‌بندی")),
                ft.DataColumn(ft.Text("بهای تمام‌شده")),
                ft.DataColumn(ft.Text("قیمت فروش منو")),
            ],
            rows=[],
        )

        def compute_data():
            raw_data.clear()
            for d in logic.get_all_dishes():
                d_id, name, cat, profit_p, overhead_p, pack_cost, market_price = d
                _, ingredients = logic.get_dish_full(d_id)
                mat_cost = sum(price * amount for _, _, _, price, amount in ingredients)
                mat, ov, pack, total, profit, final_calc = logic.compute_dish_cost(overhead_p, profit_p, pack_cost, True, mat_cost)
                final_price = market_price if (market_price and market_price > 0) else final_calc
                raw_data.append((cat, name, mat, ov, pack, total, final_price))

        def render_table():
            report_table.rows.clear()
            query = (search_field.value or "").strip().lower()
            for cat, name, mat, ov, pack, total, final_price in raw_data:
                if query and query not in name.lower() and query not in cat.lower():
                    continue
                report_table.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(cat)),
                    ft.DataCell(ft.Text(name)),
                    ft.DataCell(ft.Text(logic.fmt(mat))),
                    ft.DataCell(ft.Text(logic.fmt(ov))),
                    ft.DataCell(ft.Text(logic.fmt(pack))),
                    ft.DataCell(ft.Text(logic.fmt(total))),
                    ft.DataCell(ft.Text(logic.fmt(final_price), weight=ft.FontWeight.BOLD)),
                ]))
            page.update()

        search_field.on_change = lambda e: render_table()

        def refresh():
            compute_data()
            render_table()

        refreshers.append(refresh)

        content = ft.Column([
            card(ft.Column([
                ft.Row([section_title("📊 گزارش منو و بهای تمام‌شده"), search_field],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),
                ft.Row([report_table], scroll=ft.ScrollMode.AUTO),
            ], spacing=10), expand=True),
        ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

        refresh()
        return content

    # ============================================================
    # تب ۶: داشبورد تحلیلی
    # ============================================================
    def build_analytics_tab():
        stats_row = ft.Row(spacing=12, wrap=True)
        low_stock_column = ft.Column(spacing=6)
        top_margin_column = ft.Column(spacing=6)

        def stat_card(title, value, color):
            return ft.Container(
                content=ft.Column([
                    ft.Text(title, size=12, color=ft.Colors.GREY_700),
                    ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=color),
                ], spacing=4),
                padding=16, bgcolor=ft.Colors.WHITE, border_radius=12,
                border=ft.Border.all(1, CARD_BORDER), width=200,
            )

        def refresh():
            ingredients = logic.get_all_ingredients()
            dishes = logic.get_all_dishes()

            low_stock_items = [i for i in ingredients if i[4] <= i[5]]

            margins = []
            for d in dishes:
                d_id, name, cat, profit_p, overhead_p, pack_cost, market_price = d
                _, ing_list = logic.get_dish_full(d_id)
                mat_cost = sum(price * amount for _, _, _, price, amount in ing_list)
                _, _, _, total_cost, profit_amt, final_price = logic.compute_dish_cost(overhead_p, profit_p, pack_cost, False, mat_cost)
                sell_price = market_price if (market_price and market_price > 0) else final_price
                margin_pct = ((sell_price - total_cost) / sell_price * 100) if sell_price > 0 else 0
                margins.append((name, margin_pct, sell_price, total_cost))
            margins.sort(key=lambda x: x[1], reverse=True)

            stats_row.controls = [
                stat_card("📦 تعداد کالاها", str(len(ingredients)), "#0f172a"),
                stat_card("🍽️ تعداد غذاها", str(len(dishes)), "#0f172a"),
                stat_card("⚠️ کالاهای رو به اتمام", str(len(low_stock_items)), DANGER),
            ]

            low_stock_column.controls = [ft.Text("همه کالاها موجودی کافی دارند ✅", color=SUCCESS)] if not low_stock_items else [
                ft.Row([
                    ft.Icon(ft.Icons.WARNING_AMBER, color=DANGER, size=18),
                    ft.Text(f"{name} — موجودی: {stock} {unit} (نقطه سفارش: {min_stock})", size=13),
                ]) for _, name, unit, price, stock, min_stock, updated in low_stock_items
            ]

            top_margin_column.controls = [
                ft.Row([
                    ft.Text(f"{idx+1}.", weight=ft.FontWeight.BOLD, width=24),
                    ft.Text(name, expand=True),
                    ft.Text(f"{margin_pct:.1f}٪ سود", color=SUCCESS if margin_pct >= 0 else DANGER, weight=ft.FontWeight.BOLD),
                ]) for idx, (name, margin_pct, sell_price, total_cost) in enumerate(margins[:8])
            ] or [ft.Text("هنوز غذایی ثبت نشده است.", color=ft.Colors.GREY_600)]

            page.update()

        refreshers.append(refresh)

        content = ft.Column([
            stats_row,
            ft.Row([
                card(ft.Column([
                    section_title("⚠️ هشدار موجودی انبار"),
                    ft.Divider(),
                    low_stock_column,
                ], spacing=8), expand=True),
                card(ft.Column([
                    section_title("🏆 پرسودترین غذاهای منو"),
                    ft.Divider(),
                    top_margin_column,
                ], spacing=8), expand=True),
            ], spacing=16, wrap=True),
        ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

        refresh()
        return content

    # ============================================================
    # تب ۷: ترازنامه مالی (فاکتور خرید / فروش + اقلام دستی)
    # ============================================================
    def build_balance_tab():
        editing_id = [None]  # وقتی مقدار دارد یعنی در حالت ویرایش یک ترازنامه قبلی هستیم

        # ---- تاریخ کلی ترازنامه ----
        sheet_date_field = ft.TextField(label="تاریخ کلی ترازنامه (مثلاً 1403/05/12)")

        # ---- فاکتور خرید ----
        purchase_date_field = ft.TextField(label="روز و تاریخ فاکتور خرید")
        purchase_item_name = ft.TextField(label="نوع کالا", col={"xs": 12, "sm": 6, "md": 4})
        purchase_qty = ft.TextField(label="وزن/تعداد", col={"xs": 12, "sm": 6, "md": 4}, keyboard_type=ft.KeyboardType.NUMBER)
        purchase_unit_price = ft.TextField(label="قیمت واحد", col={"xs": 12, "sm": 12, "md": 4}, keyboard_type=ft.KeyboardType.NUMBER)
        purchase_rows = []  # هر آیتم: {"name","qty","unit_price","total_price"}
        editing_purchase_idx = [None]  # اندیس ردیفی از فاکتور خرید که در حال ویرایش است (None یعنی حالت افزودن)
        purchase_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("نوع کالا")),
                ft.DataColumn(ft.Text("وزن/تعداد")),
                ft.DataColumn(ft.Text("قیمت واحد")),
                ft.DataColumn(ft.Text("قیمت کل")),
                ft.DataColumn(ft.Text("عملیات")),
            ],
            rows=[],
        )
        purchase_total_text = ft.Text("جمع فاکتور خرید: 0 تومان", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_DARK)

        # ---- فاکتور فروش ----
        sale_date_field = ft.TextField(label="روز و تاریخ فاکتور فروش")
        sale_item_name = ft.TextField(label="نوع کالا", col={"xs": 12, "sm": 6, "md": 4})
        sale_qty = ft.TextField(label="وزن/تعداد", col={"xs": 12, "sm": 6, "md": 4}, keyboard_type=ft.KeyboardType.NUMBER)
        sale_unit_price = ft.TextField(label="قیمت واحد", col={"xs": 12, "sm": 12, "md": 4}, keyboard_type=ft.KeyboardType.NUMBER)
        sale_rows = []
        editing_sale_idx = [None]  # اندیس ردیفی از فاکتور فروش که در حال ویرایش است (None یعنی حالت افزودن)
        sale_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("نوع کالا")),
                ft.DataColumn(ft.Text("وزن/تعداد")),
                ft.DataColumn(ft.Text("قیمت واحد")),
                ft.DataColumn(ft.Text("قیمت کل")),
                ft.DataColumn(ft.Text("عملیات")),
            ],
            rows=[],
        )
        sale_total_text = ft.Text("جمع فاکتور فروش: 0 تومان", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_DARK)

        match_text = ft.Text("", size=13)

        # ---- اقلام دستی ----
        pos1_field = ft.TextField(label="جمع واریزی کارتخوان ۱", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        pos2_field = ft.TextField(label="جمع واریزی کارتخوان ۲", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        cash_field = ft.TextField(label="نقدی", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        card_to_card_field = ft.TextField(label="کارت به کارت", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        grand_total_field = ft.TextField(label="جمع کل", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        partners_field = ft.TextField(label="مبلغ پایا شده شرکا", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        municipality_field = ft.TextField(label="شهرداری", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        tax_field = ft.TextField(label="دارایی", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        electricity_field = ft.TextField(label="برق", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        gas_field = ft.TextField(label="گاز", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        water_field = ft.TextField(label="آب", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        custom_field = ft.TextField(label="مبلغ دلخواه", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        balance_field = ft.TextField(label="تراز مالی", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)
        shortage_field = ft.TextField(label="کسری اقلام", col={"xs": 12, "sm": 6, "md": 4}, value="0", keyboard_type=ft.KeyboardType.NUMBER)

        status_text = ft.Text("", size=13)

        # ---------------- محاسبات و رفرش جدول‌ها ----------------
        def calc_purchase_total():
            return sum(r["total_price"] for r in purchase_rows)

        def calc_sale_total():
            return sum(r["total_price"] for r in sale_rows)

        def update_match_text():
            p_total = calc_purchase_total()
            s_total = calc_sale_total()
            if p_total == 0 and s_total == 0:
                match_text.value = ""
                return
            diff = s_total - p_total
            if abs(diff) < 0.01:
                match_text.value = "✅ جمع فاکتور خرید و فروش با هم برابر است."
                match_text.color = SUCCESS
            else:
                match_text.value = f"⚠️ عدم تطابق: اختلاف {logic.fmt(abs(diff))} تومان بین جمع خرید و فروش وجود دارد."
                match_text.color = DANGER

        def refresh_purchase_table():
            purchase_table.rows.clear()
            for idx, r in enumerate(purchase_rows):
                is_editing_this = editing_purchase_idx[0] == idx
                purchase_table.rows.append(ft.DataRow(
                    color=ft.Colors.ORANGE_50 if is_editing_this else None,
                    cells=[
                        ft.DataCell(ft.Text(r["name"])),
                        ft.DataCell(ft.Text(logic.fmt(r["qty"]))),
                        ft.DataCell(ft.Text(logic.fmt(r["unit_price"]))),
                        ft.DataCell(ft.Text(logic.fmt(r["total_price"]))),
                        ft.DataCell(ft.Row([
                            ft.IconButton(icon=ft.Icons.EDIT, icon_color=ACCENT,
                                          tooltip="ویرایش این ردیف",
                                          on_click=lambda e, i=idx: edit_purchase_row_click(i)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_color=DANGER,
                                          tooltip="حذف این ردیف",
                                          on_click=lambda e, i=idx: remove_purchase_row(i)),
                        ], spacing=0)),
                    ]))
            purchase_total_text.value = f"جمع فاکتور خرید: {logic.fmt(calc_purchase_total())} تومان"
            update_match_text()
            page.update()

        def refresh_sale_table():
            sale_table.rows.clear()
            for idx, r in enumerate(sale_rows):
                is_editing_this = editing_sale_idx[0] == idx
                sale_table.rows.append(ft.DataRow(
                    color=ft.Colors.ORANGE_50 if is_editing_this else None,
                    cells=[
                        ft.DataCell(ft.Text(r["name"])),
                        ft.DataCell(ft.Text(logic.fmt(r["qty"]))),
                        ft.DataCell(ft.Text(logic.fmt(r["unit_price"]))),
                        ft.DataCell(ft.Text(logic.fmt(r["total_price"]))),
                        ft.DataCell(ft.Row([
                            ft.IconButton(icon=ft.Icons.EDIT, icon_color=ACCENT,
                                          tooltip="ویرایش این ردیف",
                                          on_click=lambda e, i=idx: edit_sale_row_click(i)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_color=DANGER,
                                          tooltip="حذف این ردیف",
                                          on_click=lambda e, i=idx: remove_sale_row(i)),
                        ], spacing=0)),
                    ]))
            sale_total_text.value = f"جمع فاکتور فروش: {logic.fmt(calc_sale_total())} تومان"
            update_match_text()
            page.update()

        # ---------------- افزودن/ویرایش/حذف ردیف فاکتور خرید ----------------
        def add_purchase_row(e):
            name = (purchase_item_name.value or "").strip()
            qty = logic.to_float(purchase_qty.value)
            unit_price = logic.to_float(purchase_unit_price.value)
            if not name or qty <= 0 or unit_price <= 0:
                status_text.value = "⚠️ لطفاً نوع کالا، وزن/تعداد و قیمت واحد معتبر برای فاکتور خرید وارد کنید."
                status_text.color = DANGER
                page.update()
                return

            if editing_purchase_idx[0] is not None:
                # حالت ویرایش: همان ردیف موجود به‌روزرسانی می‌شود
                idx = editing_purchase_idx[0]
                purchase_rows[idx] = {"name": name, "qty": qty, "unit_price": unit_price,
                                       "total_price": qty * unit_price}
                editing_purchase_idx[0] = None
                purchase_add_button.text = "➕ افزودن ردیف به فاکتور خرید"
                purchase_cancel_edit_button.visible = False
                status_text.value = "✅ ردیف فاکتور خرید به‌روزرسانی شد."
                status_text.color = SUCCESS
            else:
                # حالت افزودن ردیف جدید
                purchase_rows.append({"name": name, "qty": qty, "unit_price": unit_price,
                                       "total_price": qty * unit_price})
                status_text.value = ""

            purchase_item_name.value = ""
            purchase_qty.value = ""
            purchase_unit_price.value = ""
            refresh_purchase_table()

        def edit_purchase_row_click(idx):
            r = purchase_rows[idx]
            purchase_item_name.value = r["name"]
            purchase_qty.value = str(r["qty"])
            purchase_unit_price.value = str(r["unit_price"])
            editing_purchase_idx[0] = idx
            purchase_add_button.text = "✏️ به‌روزرسانی ردیف فاکتور خرید"
            purchase_cancel_edit_button.visible = True
            status_text.value = f"در حال ویرایش ردیف «{r['name']}» از فاکتور خرید هستید."
            status_text.color = ACCENT_DARK
            refresh_purchase_table()

        def cancel_purchase_edit(e):
            editing_purchase_idx[0] = None
            purchase_item_name.value = ""
            purchase_qty.value = ""
            purchase_unit_price.value = ""
            purchase_add_button.text = "➕ افزودن ردیف به فاکتور خرید"
            purchase_cancel_edit_button.visible = False
            status_text.value = ""
            refresh_purchase_table()

        def remove_purchase_row(idx):
            if editing_purchase_idx[0] == idx:
                cancel_purchase_edit(None)
            purchase_rows.pop(idx)
            refresh_purchase_table()

        # ---------------- افزودن/ویرایش/حذف ردیف فاکتور فروش ----------------
        def add_sale_row(e):
            name = (sale_item_name.value or "").strip()
            qty = logic.to_float(sale_qty.value)
            unit_price = logic.to_float(sale_unit_price.value)
            if not name or qty <= 0 or unit_price <= 0:
                status_text.value = "⚠️ لطفاً نوع کالا، وزن/تعداد و قیمت واحد معتبر برای فاکتور فروش وارد کنید."
                status_text.color = DANGER
                page.update()
                return

            if editing_sale_idx[0] is not None:
                # حالت ویرایش: همان ردیف موجود به‌روزرسانی می‌شود
                idx = editing_sale_idx[0]
                sale_rows[idx] = {"name": name, "qty": qty, "unit_price": unit_price,
                                   "total_price": qty * unit_price}
                editing_sale_idx[0] = None
                sale_add_button.text = "➕ افزودن ردیف به فاکتور فروش"
                sale_cancel_edit_button.visible = False
                status_text.value = "✅ ردیف فاکتور فروش به‌روزرسانی شد."
                status_text.color = SUCCESS
            else:
                # حالت افزودن ردیف جدید
                sale_rows.append({"name": name, "qty": qty, "unit_price": unit_price,
                                   "total_price": qty * unit_price})
                status_text.value = ""

            sale_item_name.value = ""
            sale_qty.value = ""
            sale_unit_price.value = ""
            refresh_sale_table()

        def edit_sale_row_click(idx):
            r = sale_rows[idx]
            sale_item_name.value = r["name"]
            sale_qty.value = str(r["qty"])
            sale_unit_price.value = str(r["unit_price"])
            editing_sale_idx[0] = idx
            sale_add_button.text = "✏️ به‌روزرسانی ردیف فاکتور فروش"
            sale_cancel_edit_button.visible = True
            status_text.value = f"در حال ویرایش ردیف «{r['name']}» از فاکتور فروش هستید."
            status_text.color = ACCENT_DARK
            refresh_sale_table()

        def cancel_sale_edit(e):
            editing_sale_idx[0] = None
            sale_item_name.value = ""
            sale_qty.value = ""
            sale_unit_price.value = ""
            sale_add_button.text = "➕ افزودن ردیف به فاکتور فروش"
            sale_cancel_edit_button.visible = False
            status_text.value = ""
            refresh_sale_table()

        def remove_sale_row(idx):
            if editing_sale_idx[0] == idx:
                cancel_sale_edit(None)
            sale_rows.pop(idx)
            refresh_sale_table()

        # ---------------- پاک کردن فرم / ترازنامه جدید ----------------
        def clear_form():
            editing_id[0] = None
            editing_purchase_idx[0] = None
            editing_sale_idx[0] = None
            purchase_add_button.text = "➕ افزودن ردیف به فاکتور خرید"
            sale_add_button.text = "➕ افزودن ردیف به فاکتور فروش"
            purchase_cancel_edit_button.visible = False
            sale_cancel_edit_button.visible = False
            purchase_item_name.value = ""
            purchase_qty.value = ""
            purchase_unit_price.value = ""
            sale_item_name.value = ""
            sale_qty.value = ""
            sale_unit_price.value = ""
            sheet_date_field.value = ""
            purchase_date_field.value = ""
            sale_date_field.value = ""
            purchase_rows.clear()
            sale_rows.clear()
            for f in (pos1_field, pos2_field, cash_field, card_to_card_field, grand_total_field,
                      partners_field, municipality_field, tax_field, electricity_field,
                      gas_field, water_field, custom_field, balance_field, shortage_field):
                f.value = "0"
            status_text.value = ""
            refresh_purchase_table()
            refresh_sale_table()

        # ---------------- ذخیره ترازنامه ----------------
        def save_click(e):
            sheet_date = (sheet_date_field.value or "").strip()
            if not sheet_date:
                status_text.value = "⚠️ لطفاً تاریخ کلی ترازنامه را وارد کنید."
                status_text.color = DANGER
                page.update()
                return
            if not purchase_rows and not sale_rows:
                status_text.value = "⚠️ حداقل یک ردیف در فاکتور خرید یا فروش وارد کنید."
                status_text.color = DANGER
                page.update()
                return

            purchase_items = [(r["name"], r["qty"], r["unit_price"], r["total_price"]) for r in purchase_rows]
            sale_items = [(r["name"], r["qty"], r["unit_price"], r["total_price"]) for r in sale_rows]
            manual = {
                "pos1": logic.to_float(pos1_field.value),
                "pos2": logic.to_float(pos2_field.value),
                "cash": logic.to_float(cash_field.value),
                "card_to_card": logic.to_float(card_to_card_field.value),
                "grand_total": logic.to_float(grand_total_field.value),
                "partners_amount": logic.to_float(partners_field.value),
                "municipality": logic.to_float(municipality_field.value),
                "tax": logic.to_float(tax_field.value),
                "electricity": logic.to_float(electricity_field.value),
                "gas": logic.to_float(gas_field.value),
                "water": logic.to_float(water_field.value),
                "custom_amount": logic.to_float(custom_field.value),
                "balance": logic.to_float(balance_field.value),
                "shortage": logic.to_float(shortage_field.value),
            }
            new_id = logic.save_balance_sheet(
                sheet_date, purchase_date_field.value or "", sale_date_field.value or "",
                purchase_items, sale_items, manual, editing_id[0]
            )
            editing_id[0] = new_id
            was_edit = editing_id[0] is not None
            status_text.value = f"✅ ترازنامه مالی با موفقیت ذخیره شد (شماره {new_id})."
            status_text.color = SUCCESS
            refresh_all()
            page.update()

        # ---------------- تاریخچه ترازنامه‌ها ----------------
        history_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("تاریخ")),
                ft.DataColumn(ft.Text("جمع خرید")),
                ft.DataColumn(ft.Text("جمع فروش")),
                ft.DataColumn(ft.Text("جمع کل")),
                ft.DataColumn(ft.Text("تراز مالی")),
                ft.DataColumn(ft.Text("کسری اقلام")),
                ft.DataColumn(ft.Text("عملیات")),
            ],
            rows=[],
        )

        def load_sheet(sheet_id):
            header, p_items, s_items = logic.get_balance_sheet_full(sheet_id)
            if not header:
                return
            (h_id, sheet_date, purchase_date, sale_date, pos1, pos2, cash, card_to_card,
             grand_total, partners_amount, municipality, tax, electricity, gas, water,
             custom_amount, balance, shortage, purchase_total, sale_total, created_at) = header

            editing_id[0] = h_id
            editing_purchase_idx[0] = None
            editing_sale_idx[0] = None
            purchase_add_button.text = "➕ افزودن ردیف به فاکتور خرید"
            sale_add_button.text = "➕ افزودن ردیف به فاکتور فروش"
            purchase_cancel_edit_button.visible = False
            sale_cancel_edit_button.visible = False
            sheet_date_field.value = sheet_date
            purchase_date_field.value = purchase_date
            sale_date_field.value = sale_date

            purchase_rows.clear()
            for _, name, qty, unit_price, total_price in p_items:
                purchase_rows.append({"name": name, "qty": qty, "unit_price": unit_price, "total_price": total_price})

            sale_rows.clear()
            for _, name, qty, unit_price, total_price in s_items:
                sale_rows.append({"name": name, "qty": qty, "unit_price": unit_price, "total_price": total_price})

            pos1_field.value = str(pos1)
            pos2_field.value = str(pos2)
            cash_field.value = str(cash)
            card_to_card_field.value = str(card_to_card)
            grand_total_field.value = str(grand_total)
            partners_field.value = str(partners_amount)
            municipality_field.value = str(municipality)
            tax_field.value = str(tax)
            electricity_field.value = str(electricity)
            gas_field.value = str(gas)
            water_field.value = str(water)
            custom_field.value = str(custom_amount)
            balance_field.value = str(balance)
            shortage_field.value = str(shortage)

            status_text.value = f"✏️ در حال ویرایش ترازنامه شماره {h_id}. پس از تغییرات، «ذخیره ترازنامه» را بزنید."
            status_text.color = ACCENT_DARK
            refresh_purchase_table()
            refresh_sale_table()
            page.update()

        def delete_sheet_click(sheet_id):
            if editing_id[0] == sheet_id:
                clear_form()
            logic.delete_balance_sheet(sheet_id)
            status_text.value = f"✅ ترازنامه شماره {sheet_id} حذف شد."
            status_text.color = SUCCESS
            refresh_all()
            page.update()

        def refresh_history():
            history_table.rows.clear()
            for row in logic.get_all_balance_sheets():
                (h_id, sheet_date, purchase_date, sale_date, purchase_total, sale_total,
                 grand_total, balance, shortage, created_at) = row
                history_table.rows.append(ft.DataRow(cells=[
                    ft.DataCell(ft.Text(sheet_date)),
                    ft.DataCell(ft.Text(logic.fmt(purchase_total))),
                    ft.DataCell(ft.Text(logic.fmt(sale_total))),
                    ft.DataCell(ft.Text(logic.fmt(grand_total))),
                    ft.DataCell(ft.Text(logic.fmt(balance))),
                    ft.DataCell(ft.Text(logic.fmt(shortage))),
                    ft.DataCell(ft.Row([
                        ft.IconButton(icon=ft.Icons.EDIT, icon_color=ACCENT, tooltip="بازکردن/ویرایش",
                                      on_click=lambda e, sid=h_id: load_sheet(sid)),
                        ft.IconButton(icon=ft.Icons.DELETE, icon_color=DANGER, tooltip="حذف",
                                      on_click=lambda e, sid=h_id: delete_sheet_click(sid)),
                    ], spacing=0)),
                ]))

        refreshers.append(refresh_history)

        # ---------------- چیدمان نهایی ----------------
        purchase_add_button = ft.ElevatedButton("➕ افزودن ردیف به فاکتور خرید", on_click=add_purchase_row,
                                                 bgcolor=ACCENT, color=ft.Colors.WHITE)
        purchase_cancel_edit_button = ft.OutlinedButton("✖️ لغو ویرایش ردیف", on_click=cancel_purchase_edit,
                                                         visible=False)

        sale_add_button = ft.ElevatedButton("➕ افزودن ردیف به فاکتور فروش", on_click=add_sale_row,
                                             bgcolor=ACCENT, color=ft.Colors.WHITE)
        sale_cancel_edit_button = ft.OutlinedButton("✖️ لغو ویرایش ردیف", on_click=cancel_sale_edit,
                                                     visible=False)

        purchase_card = card(ft.Column([
            section_title("🧾 فاکتور خرید"),
            ft.Divider(),
            purchase_date_field,
            ft.ResponsiveRow([purchase_item_name, purchase_qty, purchase_unit_price]),
            ft.Row([purchase_add_button, purchase_cancel_edit_button], wrap=True),
            ft.Row([purchase_table], scroll=ft.ScrollMode.AUTO),
            purchase_total_text,
        ], spacing=10))

        sale_card = card(ft.Column([
            section_title("🧾 فاکتور فروش"),
            ft.Divider(),
            sale_date_field,
            ft.ResponsiveRow([sale_item_name, sale_qty, sale_unit_price]),
            ft.Row([sale_add_button, sale_cancel_edit_button], wrap=True),
            ft.Row([sale_table], scroll=ft.ScrollMode.AUTO),
            sale_total_text,
        ], spacing=10))

        manual_card = card(ft.Column([
            section_title("✍️ اقلام دستی ترازنامه"),
            ft.Divider(),
            ft.ResponsiveRow([
                pos1_field, pos2_field, cash_field, card_to_card_field, grand_total_field,
                partners_field, municipality_field, tax_field, electricity_field,
                gas_field, water_field, custom_field, balance_field, shortage_field,
            ]),
        ], spacing=10))

        save_card = card(ft.Column([
            section_title("🧮 ترازنامه مالی"),
            ft.Divider(),
            sheet_date_field,
            match_text,
            ft.Row([
                ft.ElevatedButton("💾 ذخیره ترازنامه", on_click=save_click,
                                   bgcolor=ACCENT, color=ft.Colors.WHITE),
                ft.OutlinedButton("🆕 ترازنامه جدید / پاک کردن فرم",
                                   on_click=lambda e: (clear_form(), page.update())),
            ]),
            status_text,
        ], spacing=10))

        history_card = card(ft.Column([
            section_title("📜 تاریخچه ترازنامه‌های ثبت‌شده"),
            ft.Divider(),
            ft.Row([history_table], scroll=ft.ScrollMode.AUTO),
        ], spacing=10))

        refresh_history()
        refresh_purchase_table()
        refresh_sale_table()

        return ft.Column([
            save_card,
            purchase_card,
            sale_card,
            manual_card,
            history_card,
        ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    # ============================================================
    # ساخت تب‌ها و چیدمان نهایی صفحه
    # ============================================================
    tab_labels = [
        "🛒 فروش", "📦 انبار", "🍳 رسپی", "💡 قیمت‌گذاری", "📊 گزارش", "📈 داشبورد", "🧮 ترازنامه مالی",
    ]
    tab_builders = [
        build_sales_tab, build_ingredients_tab, build_dish_tab,
        build_smart_pricing_tab, build_report_tab, build_analytics_tab, build_balance_tab,
    ]

    tabs = ft.Tabs(
        length=len(tab_labels),
        selected_index=0,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tab_alignment=ft.TabAlignment.CENTER,
                    tabs=[ft.Tab(label=ft.Text(t)) for t in tab_labels],
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[ft.Container(builder(), padding=14) for builder in tab_builders],
                ),
            ],
        ),
    )

    header = ft.Container(
        content=ft.Text("🍽️ مدیریت مالی و انبار رستوران", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor=DARK_BG, padding=16,
    )

    page.add(ft.Column([header, tabs], spacing=0, expand=True))

    
ft.app(target=main)