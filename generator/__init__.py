import re
import sqlite3
import random
import datetime
import flask
from flask import Flask, render_template, g
from flask_bootstrap import Bootstrap
from wtforms import Form, TextAreaField


DBPATH = "lists.db"
listnamere = "[\w\-]+"

app = Flask(__name__)
app.secret_key = "code names are soooo 2016"
Bootstrap(app)

@app.route("/")
def main():
    cur = db().cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    cur.close()
    return render_template("index.html", title="Welcome!", listitems=[(r[0], flask.url_for("next", listname=r[0])) for r in tables])

@app.route("/del/<listname>")
def delete(listname):
    if not re.fullmatch(listnamere, listname):
        # Show error
        flask.flash("List name must match re {:s}".format(listnamere), "danger")
        return flask.redirect(flask.url_for("main"))
    cur = db().cursor()
    listname = listname.lower()
    table = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=(?)", (listname,)).fetchone()
    if not table:
        flask.flash("{:s}? There is no such list.".format(listname), "danger")
        return flask.redirect(flask.url_for("main"))
    else:
        res = cur.execute("DROP TABLE [{:s}]".format(listname))
        flask.flash("List {:s} deleted.".format(listname), "success")
        return flask.redirect(flask.url_for("main"))

@app.route("/load/<listname>", methods=["GET", "POST"])
def load(listname):
    if not re.fullmatch(listnamere, listname):
        # Show error
        flask.flash("List name must match re {:s}".format(listnamere), "danger")
        return flask.redirect(flask.url_for("main"))

    cur = db().cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    listname = listname.lower()

    if flask.request.method == "POST":
        if listname in [row[0] for row in tables]:
            # Show error
            flask.flash("That list ({:s}) allready exists".format(listname), "error")
            return flask.redirect(flask.url_for("main"))

        llform = LoadListForm(flask.request.form)
        listitems = process_text(llform.freetext.data)[:10000]
        random.shuffle(listitems)
        cur.execute("CREATE TABLE [{:s}] (item text, picked datetime)".format(listname))
        cur.executemany("INSERT INTO [{:s}](item) VALUES (?)".format(listname), [(li,) for li in listitems])
        commit()
        cur.close()
        flask.flash("List {:s} loaded with {:d} items.".format(listname, len(listitems)), "success")
        return flask.redirect(flask.url_for("main"))
    else:
        if listname in [row[0] for row in tables]:
            results = cur.execute("SELECT item FROM [{:s}]".format(listname)).fetchall()
            listitems = [r[0] for r in results]
        else:
            listitems = None
        llform = LoadListForm()
        if listitems:
            llform.freetext.data = "\n".join(listitems)
        return render_template("load.html", form=llform, listname=listname, posturl=flask.url_for("load", listname=listname))


@app.route("/nextfrom/<listname>", methods=["GET", "POST"])
def next(listname):
    if not checkflash_listname(listname):
        return flask.redirect(flask.url_for("main"))

    cur = db().cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    listname = listname.lower()
    if listname not in [row[0] for row in tables]:
        flask.flash("{:s}? There is no such list.".format(listname), "danger")
        return flask.redirect(flask.url_for("main"))
    if flask.request.method == "POST":
        res = cur.execute("UPDATE [{:s}] SET picked = (?) WHERE item = (?)".format(listname), (datetime.datetime.now(), flask.request.form["listitem"]))
        commit()
        if res.rowcount > 0:
            flask.flash("You picked {:s}. This item is now in use.".format(flask.request.form["listitem"]), "success")
        else:
            flask.flash("Uh nothing updated...whatever that means...you know", "warning")
    result = cur.execute("SELECT * FROM [{:s}] WHERE picked IS NULL".format(listname)).fetchone()
    if not result:
        item = None
    else:
        item = result[0]
    return render_template("next.html", listname=listname, listitem=item, posturl=flask.url_for("next", listname=listname))

def process_text(rawtxt):
    items = re.split("[,\t\r\n]+",rawtxt, flags=re.IGNORECASE)
    return [re.sub("[^\w\-\ \']", "_", item, flags=re.IGNORECASE) for item in items]

def checkflash_listname(rawname):
    if not re.fullmatch(listnamere, rawname):
        flask.flash("This is an invalid listname, dummy! Should comply to re {:s}".format(listnamere), "danger")
        return False
    else:
        return True

def db():
    dbo = getattr(g, '_database', None)
    if dbo is None:
        dbo = g._database = connect_to_database()
    return dbo

def commit():
    dbo = getattr(g, '_database', None)
    if dbo is None:
        dbo = g._database = connect_to_database()
    dbo.commit()
    return True

def connect_to_database():
    return sqlite3.connect(DBPATH)


@app.teardown_appcontext
def close_connection(exception):
    dbo = getattr(g, '_database', None)
    if dbo is not None:
        dbo.close()

class LoadListForm(Form):
    freetext = TextAreaField(label="List items", description="Paste your items in here")

if __name__ == "__main__":
    app.run()