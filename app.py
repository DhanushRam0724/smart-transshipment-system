from flask import Flask, render_template
from solver.optimizer import solve_model

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/optimize")
def optimize():

    result = solve_model()

    return render_template(
        "result.html",
        result=result
    )


if __name__ == "__main__":
    app.run(debug=True)