import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd, checksum, requirements

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Obtain stocks of user
    stocks = db.execute("SELECT * FROM stocks WHERE user_id = ?", session["user_id"])
    for stock in stocks:
        stock["price"] = usd(stock["price"])
        stock["total"] = usd(stock["total"])
    user_cash = db.execute("SELECT cash, total FROM users WHERE id = ?", session["user_id"])
    user_cash[0]["cash"] = usd(user_cash[0]["cash"])
    user_cash[0]["total"] = usd(user_cash[0]["total"])
    return render_template("index.html", stocks=stocks, user_cash=user_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # Display form to buy stocks
    if request.method == "GET":
        return render_template("buy.html")
    # Validate and purchase stocks
    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Ensure that all fields have been filled up
        if not shares or not symbol:
            return apology("Missing Details", 400)

        # Ensure input is valid
        stock = lookup(symbol)
        if not stock:
            return apology("Invalid Symbol", 400)
        for character in shares:
            if character.isdigit() == False:
                return apology("Number of Shares must be an integer", 400)
        if "." in shares or int(shares) < 1:
            return apology("Number of Shares must be at least 1", 400)

        # Ensure user has sufficient cash
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        if float(rows[0]["cash"]) - (int(shares) * float(stock["price"])) < 0:
            return apology("Insufficient Cash", 400)

        # Buy stock for user if there are no errors and insert into transactions table
        time = datetime.now()
        price = int(shares) * float(stock["price"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transacted) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], stock["symbol"], shares, price, time)

        # Update cash for user
        remaining_cash = float(rows[0]["cash"]) - (int(shares) * float(stock["price"]))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remaining_cash, session["user_id"])

        # Update stocks database
        rows = db.execute("SELECT symbol FROM stocks WHERE user_id = ? AND symbol = ?", session["user_id"], stock["symbol"])
        # If user is buying a stock for the first time
        if not rows:
            # Add entry for stock into database
            db.execute("INSERT INTO stocks (user_id, symbol, name, shares, price, total) VALUES (?, ?, ?, ?, ?, ?)",
                       session["user_id"], stock["symbol"], stock["name"], shares, float(stock["price"]), price)
        # Else if user has already owned the stock
        else:
            old = db.execute("SELECT shares, price, total FROM stocks WHERE user_id = ? AND symbol = ?",
                             session["user_id"], stock["symbol"])
            new_shares = int(shares) + int(old[0]["shares"])
            new_total = new_shares * float(price)
            # Update database
            db.execute("UPDATE stocks SET shares = ?, total = ? WHERE user_id = ? AND symbol = ?",
                       new_shares, new_total, session["user_id"], stock["symbol"])

        # Redirect back to homepage
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Get user's transactions
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    for transaction in transactions:
        transaction["price"] = usd(transaction["price"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # Display form is request method is GET
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        # Invalid symbol
        if not stock:
            return apology("Invalid Symbol", 400)
        # Else redirect and provide information about that stock
        else:
            stock["price"] = usd(stock["price"])
            return render_template("quoted.html", stock=stock)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Load page if request is GET
    if request.method == "GET":
        return render_template("register.html")
    # Else when form is submitted via POST, check for errors
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure fields are not left blank
        if not password or not username or not confirmation:
            return apology("One or more fields left blank", 400)

        # Ensure password and confirmation is the same
        if not password == confirmation:
            return apology("Passwords do not match", 400)

        # Ensure password meets requirements
        if len(password) < 8:
            return apology("Password Must Have At Least 8 Characters", 400)
        if requirements(password) == False:
            return apology("Password Must Have At At Least 1 Alphabetical, Numerical And Special Character", 400)

        # Ensure username is not already taken
        users = db.execute("SELECT * FROM users")
        for user in users:
            if user["username"] == username:
                return apology("Username already taken", 400)

        # Add to database
        hashed_password = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed_password)

        # Log user in and redirect him to home page
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Get the user's stocks
    mystocks = db.execute("SELECT symbol FROM stocks WHERE user_id = ?", session["user_id"])
    # Load form if request method is GET
    if request.method == "GET":
        return render_template("sell.html", mystocks=mystocks)
    # Verify and sell stock when form is submitted through POST
    else:
        # Ensure that user owns that particular stock
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Missing Stock", 400)
        stock = lookup(symbol)
        rows = db.execute("SELECT * FROM stocks WHERE symbol = ? AND user_id = ?", stock["symbol"], session["user_id"])
        if not rows:
            return apology("Invalid Stock", 400)

        # Ensure user has typed in valid number of stocks
        shares = request.form.get("shares")
        for character in shares:
            if character.isdigit() == False:
                return apology("Number of Shares must be an integer", 400)
        if "." in shares or int(shares) < 1:
            return apology("Invalid Number Of Shares", 400)
        if int(shares) > int(rows[0]["shares"]):
            return apology("Too Many Shares", 400)

        # If no errors, sell stock and and update transactions table
        time = datetime.now()
        price = int(shares) * float(stock["price"])
        sold_shares = -1 * int(shares)
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, transacted) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], stock["symbol"], sold_shares, price, time)

        # Update user cash
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        updated_cash = float(user_cash[0]["cash"]) + (int(shares) * float(stock["price"]))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, session["user_id"])

        # Update stocks database
        rows = db.execute("SELECT shares, total FROM stocks WHERE user_id = ? AND symbol = ?", session["user_id"], stock["symbol"])
        new_shares = int(rows[0]["shares"]) - int(shares)
        new_total = int(new_shares) * float(stock["price"])
        # If all shares are not sold
        if new_shares > 0:
            db.execute("UPDATE stocks SET shares = ?, total = ? WHERE user_id = ? AND symbol = ?",
                       new_shares, new_total, session["user_id"], stock["symbol"])
        # Else if all the stocks have been sold
        else:
            db.execute("DELETE FROM stocks WHERE user_id = ? AND symbol = ?", session["user_id"], stock["symbol"])

        # Redirect to home page
        return redirect("/")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    # Load page if request method is GET
    if request.method == "GET":
        return render_template("change_password.html")
    # Else when form is submitted through POST, verify and change password if there are no errors
    else:
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm = request.form.get("confirm")

        # Verify that user has filled up all fields
        if not new_password or not old_password or not confirm:
            return apology("Please Fill Up All Fields", 400)

        # Verify that old password is correct
        hashed = generate_password_hash(old_password)
        rows = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        if not check_password_hash(rows[0]["hash"], old_password):
            return apology("Incorrect Password", 400)

        # Ensure that passwords match
        if not new_password == confirm:
            return apology("Passwords do not match", 400)

        # Ensure password meets requirements
        if len(new_password) < 8:
            return apology("Password Must Have At Least 8 Characters", 400)
        if requirements(new_password) == False:
            return apology("Password Must Have At At Least 1 Alphabetical, Numerical And Special Character", 400)

        # Update database with new information
        new_hashed = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", new_hashed, session["user_id"])

        # Inform user that password has been changed
        return render_template("changed.html")


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    # Load page when request method is GET
    if request.method == "GET":
        return render_template("add_cash.html")
    # Verify and add cash if there are no errors
    else:
        # Obtain inputs
        amount = request.form.get("amount")
        card_no = request.form.get("card_no")
        code = request.form.get("code")

        # Ensure that inputs have been filled up
        if not amount or not card_no or not code:
            return apology("Please Fill Up All Fields", 400)

        # Ensure that amount is valid
        counter = 0
        for character in amount:
            if character > "9" or (character < "0" and character != "."):
                return apology("Please Enter A Valid Amount", 400)
            if character == ".":
                counter += 1
        if counter > 1:
            return apology("Please Enter A Valid Amount", 400)

        # Ensure card number is valid
        for character in card_no:
            if character.isdigit() == False:
                return apology("Invalid Card Number", 400)
        sum = checksum(card_no)
        if not sum % 10 == 0:
            return apology("Invalid Card Number", 400)

        # Ensure security code is valid
        for character in code:
            if character.isdigit() == False:
                return apology("Invalid Security Code", 400)
        if len(code) < 3 or len(code) > 4:
            return apology("Invalid Security Code", 400)

        # Update user's cash if there are no errors
        rows = db.execute("SELECT cash, total FROM users WHERE id = ?", session["user_id"])
        new_cash = float(rows[0]["cash"]) + float(amount)
        new_total = float(rows[0]["total"]) + float(amount)
        db.execute("UPDATE users SET cash = ?, total = ? WHERE id = ?", new_cash, new_total, session["user_id"])

        # Redirect user back to homepage
        return redirect("/")
