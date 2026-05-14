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

    con = sqlite3.connect("Tuckshop.db")
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
    con = sqlite3.connect("Tuckshop.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM Menu')
    data = cur.fetchall()
    con.close()
    return render_template('products.html', Menu=data, active_category=None)


@app.route('/search', methods=['POST', 'GET'])
def search():
    searchTerm = request.form['search_term']
    con = sqlite3.connect("Tuckshop.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM Menu WHERE Name LIKE ?', ('%' + searchTerm + '%',))
    data = cur.fetchall()
    con.close()
    return render_template('products.html', Menu=data, active_category=None)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    item_id   = data.get('itemID')
    quantity  = data.get('quantity', 1)
    option_id = data.get('optionID', 0)

    con = sqlite3.connect("Tuckshop.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Get item price
    cur.execute('SELECT Price FROM Menu WHERE ItemID = ?', (item_id,))
    item = cur.fetchone()
    if item is None:
        con.close()
        return jsonify({'success': False, 'error': 'Item not found'}), 404

    item_price = item['Price']

    # Get special ID if one exists for this item
    special_id = 0
    cur.execute('SELECT SpecialID FROM Specials WHERE ItemID = ?', (item_id,))
    special = cur.fetchone()
    if special:
        special_id = special['SpecialID']

    # Get option price if option selected
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


@app.route('/cart')
def cart():
    con = sqlite3.connect("Tuckshop.db")
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
    con = sqlite3.connect("Tuckshop.db")
    cur = con.cursor()
    cur.execute('DELETE FROM Cart WHERE rowid = ?', (rowid,))
    con.commit()
    con.close()
    return redirect('/cart')

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    con = sqlite3.connect("Tuckshop.db")
    cur = con.cursor()
    cur.execute('DELETE FROM Cart')
    con.commit()
    con.close()
    return redirect('/cart')

@app.route('/category/<path:category>')
def category(category):
    con = sqlite3.connect("Tuckshop.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT * FROM Menu WHERE Category = ?', (category,))
    data = cur.fetchall()
    con.close()
    return render_template('products.html', Menu=data, active_category=category)


@app.route('/get_categories')
def get_categories():
    con = sqlite3.connect("Tuckshop.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT DISTINCT Category FROM Menu ORDER BY Category')
    data = [row['Category'] for row in cur.fetchall()]
    con.close()
    from flask import jsonify
    return jsonify(data)


@app.route('/get_options/<int:item_id>')
def get_options(item_id):
    con = sqlite3.connect("Tuckshop.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute('SELECT OptionID, OptionName, Price, OptionType FROM Options WHERE ItemID = ?', (item_id,))
    rows = cur.fetchall()
    con.close()

    # Group by OptionType
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


@app.route('/register')
def register():
    return render_template('register.html', title='Register')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)