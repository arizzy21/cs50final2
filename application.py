from cs50 import SQL, eprint
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from operator import attrgetter

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///list.db")

# Shortcut for users to search or view saved lists
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        page = request.form.get("page")
        if page == "search":
            return redirect("/search")
        if page == "saved":
            return redirect("/saved")
    else:
        return render_template("index.html")

# Explains website and its purpose
@app.route("/about", methods=["GET", "POST"])
def about():
    if request.method == "POST":
        page = request.form.get("page")
        if page == "register":
            return redirect("/register")
        if page == "login":
            return redirect("/login")
    else:
        return render_template("index.html")

#allows users to view or delete their saved lists of contacts
@app.route("/saved", methods=["GET", "POST"])
@login_required
def saved():
    if request.method == "POST":
        listname = request.form.get("listname")
        delete = request.form.get("deleteList")
        if listname:
            session['title']  = listname
            return redirect(url_for('.results', title=listname))
        elif delete:
            num = db.execute("SELECT list_id FROM SavedList WHERE user_id=:id AND title=:delete", id=session["user_id"], delete=delete)
            db.execute("DELETE FROM SavedList WHERE user_id=:id AND title=:delete", id=session["user_id"], delete=delete)
            db.execute("DELETE FROM ListContent WHERE user_id=:id AND list_id=:list_id", id=session["user_id"], list_id=num[0]['list_id'])
            return redirect("/saved")
    else:
        saved = db.execute("SELECT title, time FROM SavedList WHERE user_id=:id", id=session["user_id"])
        if saved:
            return render_template("saved.html", lists=saved, preexisting=True)
        else:
            return render_template("saved.html", preexisting=False)

# Shows user their chosen list and allows them to mark people as contacted if they're already reached out to them
@app.route("/results", methods=["GET", "POST"])
@login_required
def results():
    if request.method == "POST":
        change = request.form.get('change')
        person = request.form.get('person')
        title = request.form.get('title')
        if change == 'changeyes':
            db.execute("UPDATE ListContent SET Contacted = 'Yes' WHERE user_id=:user_id AND mentor_id=:mentor_id",
                        user_id=session["user_id"], mentor_id=person)
        if change == 'changeno':
            db.execute("UPDATE ListContent SET Contacted = 'No' WHERE user_id=:user_id AND mentor_id=:mentor_id",
                        user_id=session["user_id"], mentor_id=person)
        students = db.execute("SELECT m.Student, m.Email, m.Employer, m.Industry, m.Function, m.Major, m.Class, lc.Contacted, lc.mentor_id FROM mentors m, SavedList sl, ListContent lc WHERE sl.user_id = :id AND sl.title = :title AND sl.list_id=lc.list_id AND lc.mentor_id=m.mentor_id", id=session["user_id"], title=title)
        return render_template("results.html", students=students, title=title, edit=True)
    else:
        title = session['title']
        students = db.execute("SELECT m.Student, m.Email, m.Employer, m.Industry, m.Function, m.Major, m.Class, lc.Contacted, lc.mentor_id FROM mentors m, SavedList sl, ListContent lc WHERE sl.user_id = :id AND sl.title = :title AND sl.list_id=lc.list_id AND lc.mentor_id=m.mentor_id", id=session["user_id"], title=title)
        return render_template("results.html", students=students, title=title, edit=True)

# Uses company, indsutry and academic major preferences to search db and output a list of previous graduates
@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if request.method == "POST":
        # Get values from form
        method = request.form.get("method")
        company = request.form.get("employer")
        industry = request.form.get("industry")
        major = request.form.get("major")
        title = request.form.get("title")
        session['title'] = title

        # Get names of mentors to be printed
        students = db.execute("SELECT * FROM mentors WHERE (:major is null or Major LIKE '%' || :major || '%') AND (:company is null or Employer = :company) AND (:industry is null or Industry = :industry)",
                              major=major, company=company, industry=industry)
        # Save list if user entered a title and produce names, else produce names
        if method == 'save':
            existing = db.execute("SELECT title FROM SavedList WHERE user_id = :user_id AND title = :title",
                       user_id=session["user_id"], title=title)

            # Add list to sql if unique name else return apology
            if not existing:
                data = db.execute("INSERT INTO SavedList (user_id, title) VALUES(:user_id, :title)", user_id=session["user_id"], title=title)
                for student in students:
                    db.execute("INSERT INTO ListContent (user_id, list_id, mentor_id) VALUES (:user_id, :list_id, :mentor_id)",
                                user_id=session["user_id"], list_id=data, mentor_id=student["mentor_id"])
                    contact = db.execute("SELECT Contacted FROM ListContent WHERE user_id=:user_id AND mentor_id=:mentor_id AND Contacted='Yes'", user_id=session["user_id"], mentor_id=student["mentor_id"])
                    if contact:
                         db.execute("UPDATE ListContent SET Contacted = 'Yes' WHERE user_id=:user_id AND mentor_id=:mentor_id",
                                     user_id=session["user_id"], mentor_id=student["mentor_id"])
                return redirect(url_for('.results', title=title))
            else:
                return apology("List name must be unique.")
        else:
            return render_template("results.html", students=students, title=title, contacted=students, edit=False)
    else:
        # Generate sorted list of employers
        employers = db.execute("SELECT Employer FROM mentors")
        companiesRandom = []
        for employer in employers:
            name = employer["Employer"]
            if name not in companiesRandom and name != "-":
                companiesRandom.append(str(name))
        companies = sorted(companiesRandom, key=str.lower)

        #Generate sorted list of industries
        fields = db.execute("SELECT Industry FROM mentors")
        industriesRandom = []
        for industries in fields:
            name = str(industries["Industry"])
            if name not in industriesRandom and name != "-":
                industriesRandom.append(name)
        industries = sorted(industriesRandom, key=str.lower)

        #Generate sorted list of majors
        majors = db.execute("SELECT Name FROM majors")

        return render_template("search.html", companies=companies, industries=industries, majors=majors)

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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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

@app.route("/register", methods=["GET", "POST"])
def register():

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Ensures that there is a confirmation
        elif not request.form.get("confirmation"):
            return apology("must confirm password")

        # Ensures that passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match")

        # Ensures that user does not already exist in database and then adds to database else returns apology
        name = request.form.get("username")
        existing = db.execute(
            "SELECT username FROM users WHERE username = :username", username=name)
        if not existing:
            key = generate_password_hash(request.form.get("password"))
            result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                                username=request.form.get("username"), hash=key)
            session['user_id'] = result
            return render_template("index.html")
        else:
            return apology("This username already exists.")

    else:
        return render_template("register.html")

def errorhandler(e):
     """Handle error"""
     return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
     app.errorhandler(code)(errorhandler)
