"""Flask application entry-point."""
from app import app


if __name__ == "__main__":
    # 开发模式：python app_flask.py
    # 生产建议：gunicorn -w 2 -b 0.0.0.0:8000 app_flask:app
    app.run(host="0.0.0.0", port=8000, debug=True)
