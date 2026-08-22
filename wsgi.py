from smartpricing.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(__import__("os").getenv("PORT", "5000")))
