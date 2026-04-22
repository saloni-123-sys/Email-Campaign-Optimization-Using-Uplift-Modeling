@app.route("/logout")
def logout():
    session.clear()
    return render_template("logout.html") 