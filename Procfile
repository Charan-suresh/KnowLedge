web: gunicorn knowledge.main:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:${PORT:-10000} --timeout 120 --log-level info
