# Learning Companion in production mode: gunicorn, DEBUG off, static files
# served by WhiteNoise, SQLite on a volume.
#
#   docker build -t learning-companion .
#   docker run --env-file .env -e DEBUG=False -p 127.0.0.1:8000:8000 \
#     -v learning-companion-data:/app/data learning-companion
#
# SECRET_KEY and OPENAI_API_KEY are required at run time and never baked in.
# A custom ALLOWED_HOSTS must keep 127.0.0.1 for the HEALTHCHECK, whose
# --start-interval needs Docker Engine 25 or newer.
# scripts/docker-smoke.sh builds, runs and checks the image.

# Build stage: the Linux Tailwind binary (about 80 MB, downloaded from GitHub)
# builds the CSS, and collectstatic gathers it with the other static files.
# Only the results go into the final image.
FROM python:3.14-slim AS build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
# Loading the settings needs both keys: build-only dummies, set for this RUN
# only, so they never end up in the image's configuration.
RUN export SECRET_KEY=build-only OPENAI_API_KEY=build-only \
    && python src/manage.py tailwind build \
    && python src/manage.py collectstatic --noinput

# Final stage: the app, its virtualenv and the collected static files.
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_URL=sqlite:////app/data/db.sqlite3
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home \
       --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY src/ src/
COPY --from=build /app/src/staticfiles src/staticfiles
COPY docker/entrypoint.sh docker/entrypoint.sh
# Owned by app before VOLUME, so a new named volume starts out writable.
RUN mkdir /app/data && chown app:app /app/data
VOLUME /app/data
USER app
EXPOSE 8000
# 127.0.0.1, not localhost: gunicorn listens on IPv4 only. No curl in slim.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=2s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/favicon.ico', timeout=5)"]
ENTRYPOINT ["/app/docker/entrypoint.sh"]
# Workers follow WEB_CONCURRENCY (default 1). The 90 s timeout outlasts the
# AI calls' 30 s network timeouts.
CMD ["gunicorn", "--chdir", "src", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", "--access-logfile", "-", \
     "--worker-tmp-dir", "/dev/shm", "--no-control-socket", "--timeout", "90"]
