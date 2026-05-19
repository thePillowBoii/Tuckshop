from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
app = Flask(__name__)
app.secret_key = 'tuckshop'


@app.route('/')
def home():
    if 'userID' not in session:
        return render_template('login.html', title='Log in')
    else:
        username = session['userID']
        return render_template('products.html', title='Menu', username=username)


@app.route('/login', methods=['POST', 'GET'])
def login():
    username = request.form['userID']
    password = request.form['password']

    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM User WHERE UserID = ? AND Password = ?', (username, password))
    data = cur.fetchone()
    con.close()

    if data is None:
        return render_template('login.html', title='Log in', error='Invalid UserID or Password')
    else:
        session['userID'] = username
        return redirect('/products')


@app.route('/products', methods=['POST', 'GET'])
def products():
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM Menu')
    data = cur.fetchall()
    con.close()
    return render_template('products.html', Menu=data, active_category=None, active_dietary=None)



@app.route('/search', methods=['POST', 'GET'])
def search():
    searchTerm = request.form['search_term']
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM Menu WHERE Name LIKE ?', ('%' + searchTerm + '%',))
    data = cur.fetchall()
    con.close()
    return render_template('products.html', Menu=data, active_category=None, active_dietary=None)



@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    try:
        data = request.get_json()
        item_id   = data.get('itemID')
        quantity  = data.get('quantity', 1)
        option_id = data.get('optionID', 0)

        con = sqlite3.connect("Tuckshop.db", timeout=10)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute('SELECT Price FROM Menu WHERE ItemID = ?', (item_id,))
        item = cur.fetchone()
        if item is None:
            con.close()
            return jsonify({'success': False, 'error': 'Item not found'}), 404

        item_price = item['Price']

        special_id = 0
        cur.execute('SELECT SpecialID FROM Specials WHERE ItemID = ?', (item_id,))
        special = cur.fetchone()
        if special:
            special_id = special['SpecialID']

        option_price = 0.0
        if option_id != 0:
            cur.execute('SELECT Price FROM Options WHERE OptionID = ?', (option_id,))
            option = cur.fetchone()
            if option:
                option_price = option['Price']

        total_price = round(item_price + option_price, 2)

        cur.execute('''
            INSERT INTO Cart (Item, Quantity, Specials, "Option", Price)
            VALUES (?, ?, ?, ?, ?)
        ''', (item_id, quantity, special_id, option_id, total_price))

        con.commit()
        con.close()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/cart')
def cart():
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('''
        SELECT Cart.rowid, Menu.Name, Cart.Quantity, Cart.Specials,
               Cart."Option", Cart.Price,
               Options.OptionName
        FROM Cart
        JOIN Menu ON Cart.Item = Menu.ItemID
        LEFT JOIN Options ON Cart."Option" = Options.OptionID
    ''')
    items = cur.fetchall()

    cur.execute('SELECT SUM(Price * Quantity) FROM Cart')
    total = cur.fetchone()[0] or 0.0
    con.close()

    return render_template('cart.html', items=items, total=round(total, 2))


@app.route('/remove_from_cart/<int:rowid>', methods=['POST'])
def remove_from_cart(rowid):
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    cur = con.cursor()
    cur.execute('DELETE FROM Cart WHERE rowid = ?', (rowid,))
    con.commit()
    con.close()
    return redirect('/cart')


@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    cur = con.cursor()
    cur.execute('DELETE FROM Cart')
    con.commit()
    con.close()
    return redirect('/cart')


@app.route('/category/<path:category>')
def category(category):
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM Menu WHERE Category = ?', (category,))
    data = cur.fetchall()
    con.close()
    return render_template('products.html', Menu=data, active_category=category, active_dietary=None)


@app.route('/get_categories')
def get_categories():
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT DISTINCT Category FROM Menu ORDER BY Category')
    data = [row['Category'] for row in cur.fetchall()]
    con.close()
    return jsonify(data)


@app.route('/get_options/<int:item_id>')
def get_options(item_id):
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT OptionID, OptionName, Price, OptionType FROM Options WHERE ItemID = ?', (item_id,))
    rows = cur.fetchall()
    con.close()

    grouped = {}
    for row in rows:
        t = row['OptionType']
        if t not in grouped:
            grouped[t] = []
        grouped[t].append({
            'OptionID': row['OptionID'],
            'OptionName': row['OptionName'],
            'Price': row['Price']
        })
    return jsonify(grouped)


@app.route('/signout', methods=['POST', 'GET'])
def signout():
    session.pop('userID', None)
    return redirect('/')


@app.route('/checkout', methods=['POST'])
def checkout():
    order_date = request.form.get('orderDate')
    order_type = request.form.get('orderType')
    user_id = session.get('userID')

    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute('SELECT Item, Quantity, Price FROM Cart')
    cart_items = cur.fetchall()

    cur.execute('SELECT MAX(OrderID) FROM Orders')
    result = cur.fetchone()[0]
    next_order_id = (result + 1) if result else 1

    for item in cart_items:
        cur.execute('''
            INSERT INTO Orders (OrderID, User, Date, Price, Item, Quantity, ItemPrice, OrderType)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            next_order_id,
            user_id,
            order_date,
            round(item['Price'] * item['Quantity'], 2),
            item['Item'],
            item['Quantity'],
            item['Price'],
            order_type
        ))

    cur.execute('DELETE FROM Cart')
    con.commit()
    con.close()

    return redirect('/orders')


@app.route('/orders')
def orders():
    user_id = session.get('userID')
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('''
        SELECT Orders.OrderID, Orders.Date, Orders.OrderType, Orders.Quantity,
               Orders.ItemPrice, Orders.Price, Menu.Name
        FROM Orders
        JOIN Menu ON Orders.Item = Menu.ItemID
        WHERE Orders.User = ?
        ORDER BY Orders.OrderID DESC, Menu.Name
    ''', (user_id,))
    rows = cur.fetchall()
    con.close()

    orders_dict = {}
    for row in rows:
        oid = row['OrderID']
        if oid not in orders_dict:
            orders_dict[oid] = {
                'date': row['Date'],
                'order_type': row['OrderType'],
                'items': [],
                'total': 0.0
            }
        orders_dict[oid]['items'].append({
            'name': row['Name'],
            'quantity': row['Quantity'],
            'item_price': float(row['ItemPrice']),
            'line_total': float(row['Price'])
        })
        orders_dict[oid]['total'] = round(orders_dict[oid]['total'] + float(row['Price']), 2)

    return render_template('orders.html', orders=orders_dict)

@app.route('/get_dietaries')
def get_dietaries():
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM Dietaries')
    rows = cur.fetchall()
    con.close()
    result = {}
    for row in rows:
        result[row['ItemID']] = {
            'Vegan': row['Vegan'],
            'Vegetarian': row['Vegetarian'],
            'GlutenFree': row['GlutenFree'],
            'NutFree': row['NutFree'],
            'DairyFree': row['DairyFree']
        }
    return jsonify(result)

@app.route('/dietary/<filter>')
def dietary(filter):
    valid = ['Vegan', 'Vegetarian', 'GlutenFree', 'NutFree', 'DairyFree']
    if filter not in valid:
        return redirect('/products')
    con = sqlite3.connect("Tuckshop.db", timeout=10)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(f'''
        SELECT Menu.* FROM Menu
        JOIN Dietaries ON Menu.ItemID = Dietaries.ItemID
        WHERE Dietaries.{filter} = 1
    ''')
    data = cur.fetchall()
    con.close()
    return render_template('products.html', Menu=data, active_category=None, active_dietary=filter)

@app.route('/register')
def register():
    return render_template('register.html', title='Register')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)