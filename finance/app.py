from datetime import datetime
import os
#from subprocess import CREATE_BREAKAWAY_FROM_JOB

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, isfloat

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

    stocks_owned = db.execute("SELECT * FROM user_stocks WHERE user_stock_id = ?", session["user_id"])

    # list to add holdings
    total_holdings = []

    # Query for each stock owned
    for stock in stocks_owned:
        assets = lookup(stock["stock"])

        # Get worth of asset
        holdings = float(assets["price"] * stock["shares"])

        # add name, price and holdings' fields to stock owned
        stock["name"] = assets["name"]
        stock["price"] = usd(assets["price"])
        stock["holdings"] = usd(holdings)

        # append holdings to list
        total_holdings.append(holdings)

    # Query database for users information
    row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    # Get cash available from users
    cash = row[0]["cash"]

    # Grand total
    grand_total = cash + sum(total_holdings)

    # delete empty portfolios
    zero = 0
    db.execute("DELETE FROM user_stocks WHERE shares = ?", zero)
    # render users stock portfolio
    return render_template("index.html", stocks_owned=stocks_owned, grand_total=usd(grand_total), cash=usd(cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Ensure shares is a positive number
        shares = request.form.get("shares")
        if isfloat(shares) == False:
            return apology("shares must be an integer", 400)
        if "." in shares:
            return apology("shares must be an integer", 400)
        # convert string t int
        shares  = int(shares)
        # apologies if user doesn't input symbol or if symbol does not exist
        if not request.form.get("symbol") or lookup(request.form.get("symbol")) == None:
            return apology("symbol does not exits", 400)

        if not request.form.get("shares") or shares <= 0:
            return apology("shares cannot be empty/negative", 400)

        properties = db.execute("SELECT * FROM user_stocks")

        # lookup symbol to access dictionary
        stock = lookup(request.form.get("symbol"))

        # get available cash of user
        cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cash_row[0]["cash"]

        # set variable equal to stock holdings
        stock_cost = float(stock["price"] * shares)
        new_balance = cash - stock_cost

        # Check if user can afford stock
        if stock_cost > cash:
            return apology("Insufficient funds for current purchase", 400)
        else:
            # Get current date and time
            date = datetime.today()

            # add transaction to transaction history
            db.execute("INSERT INTO transactions(username, stock, shares, transaction_type, date) VALUES(?, ?, ?, ?, ?)",
            db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])[0]['username'], stock["symbol"],
            shares, 'buy', date.strftime("%d %m %Y"))

            # update users cash balance
            db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])

            # update users shares information if user already has stock
            for property in properties:
                if stock["symbol"] == property["stock"]:
                    old_shares = db.execute("SELECT shares FROM user_stocks WHERE user_stock_id = ?", session["user_id"])
                    shares = old_shares[0]["shares"] + shares
                    db.execute("UPDATE user_stocks SET shares = ?", shares)

                    # redirect user to index
                    return redirect("/")

            # add new stock information if stock not previously in Stock
            db.execute("INSERT INTO user_stocks(user_stock_id, stock, stock_price, shares) VALUES(?, ?, ?, ?)", \
            session["user_id"], stock["symbol"], stock["price"], shares)

            # redirect user to index
            return redirect("/")

    # if request method is GET
    else:
        return render_template("buy.html")


@app.route("/history", )
@login_required
def history():
    """Show history of transactions"""

    # Get rows of all transaction
    transactions = db.execute("SELECT * FROM transactions WHERE username = ?", db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])[0]['username'])

    for transaction in transactions:

        transaction["name"] = "Name"

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
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

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
    if request.method == "POST":
        """Get stock quote."""
        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Symbol not found", 400)

        return render_template("quoted.html", quote=quote)

    # If request method is GET
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
       # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Query database for if username already exist
        elif db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username")):
            return apology("username already exits", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure both passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password do not match confirmation password", 400)

        # add registrant to database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"),  generate_password_hash(request.form.get("password")))

        # redirect user to login
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # Gete varible type of shares
        sell_shares = request.form.get("shares")
        if isfloat(sell_shares) == False:
            return apology("shares must be an integer", 400)
        if "." in sell_shares:
            sell_shares = float(sell_shares)
        elif "." not in sell_shares:
            sell_shares  = int(sell_shares)
        # Ensure user selects an option
        if not request.form.get("symbol"):
            return apology("Select a valid Option", 400)

        # apologise if user does not own any shares of the stock
        elif not db.execute("SELECT stock FROM user_stocks WHERE stock = ?", request.form.get("symbol")):
            return apology("You can not sell shares you don't have!", 400)

        # Apologise if number of shares is not positive
        elif sell_shares <= 0 or isfloat(request.form.get("shares")) == False:
            return apology("Enter a valid number of shares", 400)

        # apologies if user does not have enogh shares
        elif sell_shares > db.execute("SELECT shares FROM user_stocks WHERE stock = ?", request.form.get("symbol"))[0]["shares"]:
            return apology("You don't have enough shares for this transaction", 400)

        # If everything checks out fine
        else:

            #lookup stock symbol
            sale = lookup(request.form.get("symbol"))

            #Get total profit from sale
            profit = float(sale["price"] * sell_shares)

            #update users cash balance
            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", profit, session["user_id"])

            #Get current date and time
            date = datetime.today()

            #delete users stock information if all shares sold
            if request.form.get("shares") == db.execute("SELECT shares FROM user_stocks WHERE stock = ?", request.form.get("symbol")):
                db.execute("DELETE FROM user_stocks WHERE stock = ?", request.form.get("symbol"))
            else:
                #update shares after sales
                db.execute("UPDATE user_stocks SET shares = shares - ? WHERE stock = ?", sell_shares, request.form.get("symbol"))

            #add transaction to transaction history
            db.execute("INSERT INTO transactions(username, stock, shares, transaction_type, date) VALUES(?, ?, ?, ?, ?)",
            db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])[0]['username'], sale["symbol"],
            sell_shares, 'sell', date.strftime("%d %m %Y"))

        #redirect user to index to see balance
        return redirect("/")

    else:
        user = db.execute("SELECT * FROM user_stocks")
        return render_template("sell.html", user=user)

