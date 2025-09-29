# routes_partybags.py
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, jsonify, abort, current_app
)
from sqlalchemy import desc, func
from werkzeug.utils import secure_filename
from decimal import Decimal
import os
import re

from models import db, Product, Admin, Orders
from services import (
    init_stripe, send_email, generate_order_id,
    money_to_pence, pence_to_gbp
)

bp = Blueprint("partybags", __name__)

# ---------- Public pages ----------

@bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email_addr = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email_addr or not message:
            flash('Please fill out all required fields.', 'error')
            return redirect(url_for('partybags.contact'))

        subject = 'New Contact Form Submission'
        body = f'Name: {name}\nEmail: {email_addr}\nPhone: {phone}\nSubject: {subject}\nMessage: {message}'
        send_email(subject, body)

        flash('Your message has been sent!', 'success')
        return redirect(url_for('partybags.contact'))

    return render_template('PartyBag/contact.html')


@bp.route("/")
def homepage():
    categories = ['Birthdays', 'Seasonal', 'Event', 'NSFW', 'Custom']
    category_products = {}
    for category in categories:
        if category != 'NSFW':
            products = (
                Product.query.filter_by(category=category)
                .order_by(func.random()).limit(3).all()
            )
        else:
            products = []
        category_products[category] = products

    order_id = session.pop('last_order_id', None)
    return render_template("PartyBag/home.html", category_products=category_products, order_id=order_id)


@bp.route("/category/<name>")
def category(name):
    route_map = {
        "Birthdays": "partybags.birthday",
        "Seasonal": "partybags.seasonal",
        "Event": "partybags.event",
        "Extras": "partybags.extras",
        "NSFW": "partybags.nsfw",
    }
    endpoint = route_map.get(name)
    if not endpoint:
        abort(404)
    return redirect(url_for(endpoint))


@bp.route("/extras")
def extras():
    extras_products = (
        Product.query
        .filter_by(category="Extras")
        .order_by(Product.name)
        .all()
    )
    return render_template("PartyBag/categories/extras.html", products=extras_products)


@bp.route("/birthday")
def birthday():
    birthday_products = Product.query.filter_by(category="Birthdays")
    return render_template("PartyBag/categories/birthday.html", products=birthday_products)


@bp.route("/event")
def event():
    event_products = Product.query.filter_by(category="Event")
    return render_template("PartyBag/categories/event.html", products=event_products)


@bp.route("/seasonal")
def seasonal():
    seasonal_products = Product.query.filter_by(category="Seasonal")
    return render_template("PartyBag/categories/seasonal.html", products=seasonal_products)


@bp.route("/nsfw")
def nsfw():
    nsfw_products = Product.query.filter_by(category="NSFW").order_by(Product.name).all()
    show_age_gate = not session.get("adult_verified", False)
    return render_template(
        "PartyBag/categories/nsfw.html", products=nsfw_products, show_age_gate=show_age_gate
    )


@bp.route("/product/<int:product_id>")
def product(product_id):
    product = Product.query.get_or_404(product_id)

    category_display = {
        'Birthdays': 'Birthday Bags',
        'Seasonal': 'Seasonal Bags',
        'Event': 'Event Bags',
        'Extras': 'Extras',
        'NSFW': 'NSFW'
    }
    category_routes = {
        'Birthdays': 'partybags.birthday',
        'Seasonal': 'partybags.seasonal',
        'Event': 'partybags.event',
        'Extras': 'partybags.extras',
        'NSFW': 'partybags.nsfw'
    }

    custom_breadcrumbs = [
        {'name': 'MadCakes', 'url': url_for('madcakes.index')},
        {'name': 'PartyBags', 'url': url_for('partybags.homepage')},
        {
            'name': category_display.get(product.category, product.category),
            'url': url_for(category_routes.get(product.category, 'partybags.homepage'))
        },
        {'name': product.name, 'url': request.path}
    ]

    recommendations = Product.query.filter(
        Product.category == product.category,
        Product.id != product.id
    ).order_by(func.random()).limit(4).all()

    extras_suggestions = (
        Product.query
        .filter(Product.category == "Extras")
        .order_by(func.random())
        .limit(4)
        .all()
    )

    return render_template("PartyBag/product.html",
                           product=product,
                           custom_breadcrumbs=custom_breadcrumbs,
                           recommendations=recommendations,
                           extras_suggestions=extras_suggestions)

# ---------- Cart ----------

@bp.route('/cart')
def view_cart():
    if 'cart' not in session:
        session['cart'] = {}

    cart_items = []
    for product_id, quantity in session['cart'].items():
        product = Product.query.get(int(product_id))
        if product:
            cart_items.append({'product': product, 'quantity': quantity})

    total = sum(item['product'].price * item['quantity'] for item in cart_items)
    return render_template('PartyBag/cart.html', cart_items=cart_items, total=total)


@bp.route('/cart/add/<int:product_id>', methods=['POST', 'GET'])
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = {}

    product = Product.query.get_or_404(product_id)
    product_id_str = str(product.id)

    quantity = request.form.get('quantity', '1')
    quantity = int(quantity) if quantity.isdigit() else 1

    if product_id_str in session['cart']:
        session['cart'][product_id_str] += quantity
    else:
        session['cart'][product_id_str] = quantity

    session.modified = True
    flash(f"Added {product.name} (x{quantity}) to cart!", "success")
    return redirect(url_for('partybags.view_cart'))


@bp.route('/cart/update', methods=['POST'])
def update_cart():
    if 'cart' not in session:
        session['cart'] = {}

    for field_name in request.form:
        if field_name.startswith("quantity[") and field_name.endswith("]"):
            product_id = field_name[9:-1]
            try:
                session['cart'][product_id] = int(request.form[field_name])
            except ValueError:
                continue

    session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_items = []
        total = 0.0
        for pid, quantity in session['cart'].items():
            product = Product.query.get(int(pid))
            if product:
                subtotal = float(product.price) * quantity
                cart_items.append({'product_id': product.id, 'subtotal': subtotal})
                total += subtotal
        return jsonify({'cart_items': cart_items, 'total': total})
    else:
        flash("Cart updated!", "success")
        return redirect(url_for('partybags.view_cart'))


@bp.route('/cart/remove/<int:product_id>', methods=['POST', 'GET'])
def remove_from_cart(product_id):
    product_id_str = str(product_id)
    if 'cart' in session and product_id_str in session['cart']:
        session['cart'].pop(product_id_str)
        session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_items = []
        total = 0.0
        for pid, quantity in session.get('cart', {}).items():
            product = Product.query.get(int(pid))
            if product:
                subtotal = float(product.price) * quantity
                cart_items.append({'product_id': product.id, 'subtotal': subtotal})
                total += subtotal
        return jsonify({'cart_items': cart_items, 'total': total, 'cart_empty': total == 0})
    else:
        return redirect(url_for('partybags.view_cart'))

# ---------- Checkout / Stripe ----------

@bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    stripe = init_stripe()
    try:
        if 'cart' not in session or not session['cart']:
            flash("Your cart is empty!", "error")
            return redirect(url_for('partybags.view_cart'))

        has_regular_item = False
        for product_id_str in session['cart']:
            product = Product.query.get(int(product_id_str))
            if product and product.category != "Extras":
                has_regular_item = True
                break
        if not has_regular_item:
            flash("You must have at least one regular item (not just Extras) to checkout.", "error")
            return redirect(url_for('partybags.view_cart'))

        # stock check
        for product_id, quantity in session['cart'].items():
            product = Product.query.get_or_404(product_id)
            if quantity > product.stock:
                flash(
                    f"Not enough stock for {product.name}. Available: {product.stock}, Requested: {quantity}.",
                    "error"
                )
                return redirect(url_for('partybags.view_cart'))

        line_items = []
        order_snapshot = []
        for product_id, quantity in session['cart'].items():
            product = Product.query.get_or_404(product_id)
            line_items.append({
                'price_data': {
                    'currency': 'gbp',
                    'unit_amount': money_to_pence(product.price),
                    'product_data': {
                        'name': product.name,
                        'description': product.description,
                        'metadata': {'product_id': str(product.id)}
                    },
                },
                'quantity': quantity,
            })
            order_snapshot.append({
                "name": product.name,
                "qty": int(quantity),
                "unit_amount_pence": money_to_pence(product.price),
                "subtotal_pence": money_to_pence(product.price) * int(quantity),
                "product_id": product.id,
            })

        # delivery fee
        delivery_fee_pence = 399
        line_items.append({
            'price_data': {
                'currency': 'gbp',
                'unit_amount': delivery_fee_pence,
                'product_data': {'name': 'Delivery Fee', 'description': 'Flat delivery fee'},
            },
            'quantity': 1,
        })

        order_id = generate_order_id()
        new_order = Orders(order_id=order_id, email="", status="pending", items=order_snapshot)
        db.session.add(new_order)
        db.session.commit()

        success_url = url_for('partybags.success', _external=True) + \
                      f'?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}'
        cancel_url = url_for('partybags.homepage', _external=True)

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            billing_address_collection='required',
            shipping_address_collection={'allowed_countries': ['GB']},
            metadata={"order_id": order_id},
            payment_intent_data={
                "description": f"Order {order_id}",
                "metadata": {"order_id": order_id}
            }
        )
        return redirect(checkout_session.url, code=303)

    except Exception as e:
        current_app.logger.exception(e)
        return str(e), 500


@bp.route('/buy_now/<int:product_id>', methods=['POST'])
def buy_now(product_id):
    stripe = init_stripe()
    try:
        product = Product.query.get_or_404(product_id)
        quantity = int(request.form.get('quantity', '1'))

        if quantity > product.stock:
            flash(
                f"Not enough stock for {product.name}. Available: {product.stock}, Requested: {quantity}.",
                "error"
            )
            return redirect(url_for('partybags.product', product_id=product.id))

        line_items = [{
            'price_data': {
                'currency': 'gbp',
                'unit_amount': money_to_pence(product.price),
                'product_data': {
                    'name': product.name,
                    'description': product.description,
                    'metadata': {'product_id': str(product.id)}
                },
            },
            'quantity': quantity,
        }]
        order_snapshot = [{
            "name": product.name,
            "qty": int(quantity),
            "unit_amount_pence": money_to_pence(product.price),
            "subtotal_pence": money_to_pence(product.price) * int(quantity),
            "product_id": product.id,
        }]

        delivery_fee_pence = 399
        line_items.append({
            'price_data': {
                'currency': 'gbp',
                'unit_amount': delivery_fee_pence,
                'product_data': {'name': 'Delivery Fee', 'description': 'Flat delivery fee'},
            },
            'quantity': 1,
        })

        order_id = generate_order_id()
        new_order = Orders(order_id=order_id, email="", status="pending", items=order_snapshot)
        db.session.add(new_order)
        db.session.commit()

        success_url = url_for('partybags.success', _external=True) + \
                      f'?session_id={{CHECKOUT_SESSION_ID}}&order_id={order_id}'
        cancel_url = url_for('partybags.homepage', _external=True)

        checkout_session = init_stripe().checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            billing_address_collection='required',
            shipping_address_collection={'allowed_countries': ['GB']},
            metadata={"order_id": order_id},
            payment_intent_data={
                "description": f"Order {order_id}",
                "metadata": {"order_id": order_id}
            }
        )
        return redirect(checkout_session.url, code=303)

    except Exception as e:
        current_app.logger.exception(e)
        return str(e), 500


@bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    stripe = init_stripe()
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        order_id = session_data.get('metadata', {}).get('order_id')
        order = Orders.query.filter_by(order_id=order_id).first()

        if order:
            cust = session_data.get('customer_details', {}) or {}
            order.email = cust.get('email', 'No Email Provided')
            order.status = 'received'
            db.session.commit()

    return 'Success', 200


@bp.route('/success')
def success():
    stripe = init_stripe()
    session_id = request.args.get('session_id')
    order_id = request.args.get('order_id')
    if not session_id:
        return "Invalid session.", 400

    stripe_session = stripe.checkout.Session.retrieve(session_id)
    if not stripe_session or stripe_session.payment_status != 'paid':
        return "Payment not verified.", 400

    line_items = stripe.checkout.Session.list_line_items(
        session_id, expand=['data.price.product']
    )

    order = Orders.query.filter_by(order_id=order_id).first()
    if order:
        order.status = 'received'
        order.email = (stripe_session.customer_details.email or "")
        db.session.commit()

    # Deduct stock
    for item in line_items.data:
        if item.price.product and item.price.product.metadata:
            product_id = item.price.product.metadata.get('product_id')
            if product_id:
                product = Product.query.get(int(product_id))
                if product:
                    product.stock = max(0, product.stock - item.quantity)
    db.session.commit()

    cust = stripe_session.customer_details
    customer_name = cust.name or "Unknown Customer"
    customer_email = cust.email or "No Email Provided"
    address = cust.address
    customer_address = address.line1 if address and address.line1 else "No Address"
    customer_city = address.city if address and address.city else "N/A"
    customer_postal = address.postal_code if address and address.postal_code else "N/A"
    customer_country = address.country if address and address.country else "N/A"

    order_summary = ""
    for item in line_items.data:
        order_summary += f"- {item.description} (x{item.quantity}): £{item.amount_total/100:.2f}\n"

    subject = "New Order Received!"
    body = (
        f"{subject}\n\n"
        f"Order Details:\n{order_summary}\n"
        f"Customer Information:\n"
        f"Name: {customer_name}\n"
        f"Email: {customer_email}\n"
        f"Address: {customer_address}\n"
        f"City: {customer_city}\n"
        f"Postal Code: {customer_postal}\n"
        f"Country: {customer_country}\n"
    )
    send_email(subject, body)

    session['cart'] = {}
    session.modified = True
    session['last_order_id'] = order_id

    return redirect(url_for('partybags.homepage', _external=False) + "?success=true", code=302)

# ---------- Order lookup ----------

@bp.route('/order', methods=['GET', 'POST'])
def order_lookup():
    preset_order_id = request.args.get('order_id', '').strip().upper()
    preset_email = request.args.get('email', '').strip().lower()

    if request.method == 'POST':
        order_id = (request.form.get('order_id') or '').strip().upper()
        email = (request.form.get('email') or '').strip().lower()

        if not order_id or not email:
            flash('Please enter both Order ID and Email.', 'error')
            return render_template('PartyBag/order_lookup.html',
                                   preset_order_id=order_id, preset_email=email)

        if not re.match(r'^[A-Z0-9]{8}$', order_id):
            flash('Order ID format looks wrong. It should be 8 characters (letters/numbers).', 'error')
            return render_template('PartyBag/order_lookup.html',
                                   preset_order_id=order_id, preset_email=email)

        order = Orders.query.filter(
            Orders.order_id == order_id,
            func.lower(Orders.email) == email
        ).first()

        if not order:
            flash('No order found for that Order ID and Email.', 'error')
            return render_template('PartyBag/order_lookup.html',
                                   preset_order_id=order_id, preset_email=email)

        items = order.items or []
        total_pence = 0
        normalized_items = []
        for it in items:
            qty = int(it.get('qty', 1))
            unit_p = int(it.get('unit_amount_pence', 0))
            subtotal_p = int(it.get('subtotal_pence', unit_p * qty))
            total_pence += subtotal_p
            normalized_items.append({
                'name': it.get('name', 'Item'),
                'qty': qty,
                'unit_amount_pence': unit_p,
                'unit_amount_gbp': pence_to_gbp(unit_p),
                'subtotal_pence': subtotal_p,
                'subtotal_gbp': pence_to_gbp(subtotal_p),
                'product_id': it.get('product_id')
            })

        result = {
            'order_id': order.order_id,
            'email': order.email,
            'status': order.status,
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'items': normalized_items,
            'total_pence': total_pence,
            'total_gbp': pence_to_gbp(total_pence),
        }

        wants_json = (request.args.get('format') == 'json') or \
                     ('application/json' in (request.headers.get('Accept') or ''))

        if wants_json:
            return jsonify(result)

        return render_template('PartyBag/order_lookup.html',
                               result=result,
                               preset_order_id=order_id,
                               preset_email=email)

    return render_template('PartyBag/order_lookup.html',
                           preset_order_id=preset_order_id,
                           preset_email=preset_email)

# ---------- Admin ----------

@bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('admin_password')

        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            if admin.first_login:
                return render_template('PartyBag/admin/admin_login.html',
                                       first_login=True, username=username)
            session['is_admin'] = True
            session['admin_username'] = admin.username
            return redirect(url_for('partybags.admin_dashboard'))

        flash('Incorrect username or password.', 'error')

    return render_template('PartyBag/admin/admin_login.html', first_login=False)


@bp.route('/admin/change_password', methods=['POST'])
def admin_change_password():
    username = request.form.get('username')
    admin = Admin.query.filter_by(username=username).first()

    if not admin:
        flash("Admin not found.", "error")
        return redirect(url_for('partybags.admin_login'))

    old = request.form.get('old_password')
    new = request.form.get('new_password')
    confirm = request.form.get('confirm_password')

    if not admin.check_password(old):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('partybags.admin_login'))

    if not new or new != confirm:
        flash('New passwords must match and not be empty.', 'error')
        return redirect(url_for('partybags.admin_login'))

    admin.set_password(new)
    admin.first_login = False
    db.session.commit()

    session['is_admin'] = True
    session['admin_username'] = admin.username
    flash('Password updated! Welcome, admin.', 'success')
    return redirect(url_for('partybags.admin_dashboard'))


@bp.route('/admin/dashboard')
def admin_dashboard():
    if 'is_admin' not in session:
        return redirect(url_for('partybags.admin_login'))
    products = Product.query.all()
    return render_template('PartyBag/admin/admin_dashboard.html', products=products)


def _upload_folder():
    # static/PartyBag/product_imgs
    folder = os.path.join(current_app.static_folder, 'partybags', 'product_imgs')
    os.makedirs(folder, exist_ok=True)
    return folder


@bp.route('/admin/product/new', methods=['GET', 'POST'])
def admin_new_product():
    if 'is_admin' not in session:
        return redirect(url_for('partybags.admin_login'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        category = request.form.get("category")
        subcategory = request.form.get("subcategory")
        image_file = request.files.get('image')

        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(_upload_folder(), filename)
            image_file.save(save_path)
            image_path = f"PartyBag/product_imgs/{filename}"  # relative to /static
        else:
            image_path = None

        price_str = request.form.get('price', '0.0')
        price = float(price_str) if price_str else 0.0

        stock_str = request.form.get('stock', '0')
        try:
            stock = int(stock_str)
        except ValueError:
            stock = 0

        new_product = Product(
            name=name,
            description=description,
            category=category,
            subcategory=subcategory,
            image=image_path,
            price=price,
            stock=stock
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('partybags.admin_dashboard'))

    return render_template('PartyBag/admin/admin_edit_product.html', product=None)


@bp.route('/admin/product/<int:product_id>/edit', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    if 'is_admin' not in session:
        return redirect(url_for('partybags.admin_login'))

    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.category = request.form.get('category')
        product.subcategory = request.form.get('subcategory')

        image_file = request.files.get('image')
        if image_file and image_file.filename.strip():
            filename = secure_filename(image_file.filename)
            save_path = os.path.join(_upload_folder(), filename)
            image_file.save(save_path)
            product.image = f"PartyBag/product_imgs/{filename}"

        price_str = request.form.get('price', '0.0')
        product.price = float(price_str) if price_str else 0.0

        stock_str = request.form.get('stock', '0')
        try:
            product.stock = int(stock_str)
        except ValueError:
            product.stock = 0

        db.session.commit()
        return redirect(url_for('partybags.admin_dashboard'))

    return render_template('PartyBag/admin/admin_edit_product.html', product=product)


@bp.route('/admin/product/<int:product_id>/delete', methods=['POST'])
def admin_delete_product(product_id):
    if 'is_admin' not in session:
        return redirect(url_for('partybags.admin_login'))
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('partybags.admin_dashboard'))


@bp.route('/admin/orders')
def admin_orders():
    if 'is_admin' not in session:
        return redirect(url_for('partybags.admin_login'))

    orders = Orders.query.order_by(desc(Orders.created_at)).all()
    STATUS_OPTIONS = ["processing", "shipped", "completed"]

    return render_template(
        'PartyBag/admin/admin_orders.html',
        orders=orders,
        STATUS_OPTIONS=STATUS_OPTIONS
    )


@bp.route('/admin/orders/update/<string:order_id>', methods=['POST'])
def admin_update_order(order_id):
    if 'is_admin' not in session:
        return redirect(url_for('partybags.admin_login'))

    new_status = (request.form.get('status') or '').strip().lower()
    STATUS_OPTIONS = ["processing", "shipped", "completed"]
    TERMINAL_STATUSES = {"completed"}

    order = Orders.query.filter_by(order_id=order_id).first()
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('partybags.admin_orders'))

    if new_status not in STATUS_OPTIONS:
        flash('Invalid status selected.', 'error')
        return redirect(url_for('partybags.admin_orders'))

    if new_status in TERMINAL_STATUSES:
        try:
            db.session.delete(order)
            db.session.commit()
            flash(f'Order {order_id} set to "{new_status}" and removed.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to delete order: {e}', 'error')
        return redirect(url_for('partybags.admin_orders'))

    try:
        order.status = new_status
        db.session.commit()
        flash(f'Order {order_id} status updated to "{new_status}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to update order: {e}', 'error')

    return redirect(url_for('partybags.admin_orders'))

# ---------- Template helpers ----------

@bp.app_context_processor
def inject_breadcrumbs():
    def generate_breadcrumbs(path):
        # Always start with MadCakes root
        crumbs = [{'name': 'MadCakes', 'url': url_for('madcakes.index')}]

        segments = [seg for seg in path.strip('/').split('/') if seg]

        if not segments:
            return crumbs

        accumulated = ''
        for i, seg in enumerate(segments):
            accumulated += f'/{seg}'

            # Special case: insert "PartyBags" as a top-level label
            if i == 0 and seg == 'party-bags':
                crumbs.append({'name': 'PartyBags', 'url': url_for('partybags.homepage')})
                continue

            # Default formatting
            name = seg.replace('-', ' ').title()
            crumbs.append({'name': name, 'url': accumulated})

        return crumbs

    return dict(breadcrumbs=generate_breadcrumbs(request.path))
