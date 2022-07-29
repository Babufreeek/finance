import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps
from re import compile


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


# Calculate checksum for credit card number
def checksum(card):
    sum = 0
    for i in range(len(card)):
        digit = int(card[len(card) - 1 - i])
        if (i + 1) % 2 == 0:
            digit *= 2
        if digit >= 10:
            sum += digit % 10 + 1
        else:
            sum += digit
    return sum


# Password requirements: At least 8 characters, 1 alphabet character, 1 Number, 1 Special character
def requirements(password):
    alphabet = 0
    digits = 0
    special = 0

    # Calculate number of required characters
    regex = compile("[@_!#$%^&*()<>?/\|}'{~:]")
    for character in password:
        # Alphabet
        if character.isalpha() == True:
            alphabet += 1
        # Digits
        if character.isdigit() == True:
            digits += 1
        # Special Character
        if not regex.search(character) == None:
            special += 1
    if alphabet > 0 and digits > 0 and special > 0:
        return True
    else:
        return False