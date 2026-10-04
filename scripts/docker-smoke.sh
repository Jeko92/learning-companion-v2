#!/usr/bin/env bash
# Builds the image, runs it and checks that it serves the app in production
# mode. Needs Docker and network access (the build downloads Tailwind).
# Every container, the volume and the image tag it creates are removed again.
#
#   scripts/docker-smoke.sh
#
# Prints PASS/FAIL per check and exits non-zero at the first failure.
set -euo pipefail

cd "$(dirname "$0")/.."

ID="learning-companion-smoke-$$"
IMAGE="learning-companion:smoke-$$"
VOLUME="$ID-data"
KEYS=(-e SECRET_KEY=smoke-test-secret-key -e OPENAI_API_KEY=sk-smoke-dummy)
USERNAME="smoke"
PASSWORD="Smoke-Test-Pass-123!"
WORK="$(mktemp -d)"

cleanup() {
  docker rm -f "$ID-first" "$ID-second" >/dev/null 2>&1 || true
  docker volume rm -f "$VOLUME" >/dev/null 2>&1 || true
  docker image rm -f "$IMAGE" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

check() {
  local name="$1"
  shift
  if "$@"; then
    echo "PASS $name"
  else
    echo "FAIL $name"
    exit 1
  fi
}

build_image() {
  docker build --quiet --tag "$IMAGE" . >/dev/null
}

missing_secret_key_fails() {
  local output status=0
  output="$(docker run --rm -e OPENAI_API_KEY=sk-smoke-dummy "$IMAGE" 2>&1)" || status=$?
  [ "$status" -ne 0 ] && grep -q "SECRET_KEY" <<<"$output"
}

image_has_no_env_file_or_tailwind_binary() {
  docker run --rm --entrypoint sh "$IMAGE" -c '
    test ! -e /app/.env &&
    test ! -e /app/src/.django_tailwind_cli &&
    test -z "$(find /app /opt -name "tailwindcss-*" -type f)"
  '
}

# Starts a container on the shared volume and waits until its HEALTHCHECK
# passes (migrations applied, gunicorn answering). Sets BASE to its URL.
start() {
  local name="$1"
  docker run --detach --name "$name" "${KEYS[@]}" \
    --volume "$VOLUME:/app/data" --publish 127.0.0.1::8000 "$IMAGE" >/dev/null
  for _ in $(seq 1 60); do
    case "$(docker inspect --format '{{.State.Health.Status}}' "$name")" in
      healthy)
        BASE="http://$(docker port "$name" 8000/tcp | head -n 1)"
        return 0
        ;;
      unhealthy) break ;;
    esac
    [ "$(docker inspect --format '{{.State.Running}}' "$name")" = true ] || break
    sleep 2
  done
  docker logs "$name"
  return 1
}

runs_as_non_root() {
  [ "$(docker exec "$ID-first" id -u)" != 0 ]
}

home_page_is_served() {
  curl -fsS "$BASE/" | grep -q "Learning Companion"
}

stylesheet_is_served() {
  curl -fsS -D "$WORK/headers" -o "$WORK/tailwind.css" "$BASE/static/css/tailwind.css" &&
    grep -qi '^content-type: text/css' "$WORK/headers" &&
    grep -q '\.btn' "$WORK/tailwind.css"
}

stylesheet_is_served_gzipped() {
  curl -fsS -H 'Accept-Encoding: gzip' -D "$WORK/headers" -o /dev/null \
    "$BASE/static/css/tailwind.css" &&
    grep -qi '^content-encoding: gzip' "$WORK/headers"
}

favicon_is_served() {
  curl -fsS -D "$WORK/headers" -o /dev/null "$BASE/favicon.ico" &&
    grep -Eqi '^content-type: image/(x-icon|vnd\.microsoft\.icon)' "$WORK/headers"
}

# POSTs a form with the CSRF token from its page; prints "<status> <redirect>".
post_form() {
  local path="$1"
  shift
  local jar="$WORK/cookies" token
  curl -fsS -c "$jar" -b "$jar" -o "$WORK/page.html" "$BASE$path"
  token="$(sed -n 's/.*name="csrfmiddlewaretoken" value="\([^"]*\)".*/\1/p' "$WORK/page.html" | head -n 1)"
  curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code} %{redirect_url}' \
    --data-urlencode "csrfmiddlewaretoken=$token" "$@" "$BASE$path"
}

sign_up_works() {
  rm -f "$WORK/cookies"
  [ "$(post_form /accounts/signup/ --data-urlencode "username=$USERNAME" \
    --data-urlencode "password1=$PASSWORD" --data-urlencode "password2=$PASSWORD")" \
    = "302 $BASE/dashboard/" ]
}

stops_cleanly() {
  docker stop --time 20 "$ID-first" >/dev/null &&
    [ "$(docker inspect --format '{{.State.ExitCode}}' "$ID-first")" = 0 ]
}

log_in_works_on_a_new_container() {
  rm -f "$WORK/cookies"
  [ "$(post_form /accounts/login/ --data-urlencode "username=$USERNAME" \
    --data-urlencode "password=$PASSWORD")" = "302 $BASE/dashboard/" ]
}

check "the image builds" build_image
check "without SECRET_KEY the container exits non-zero and names it" missing_secret_key_fails
check "the image has no .env and no Tailwind binary" image_has_no_env_file_or_tailwind_binary
check "the container becomes healthy (migrations applied, gunicorn answering)" start "$ID-first"
check "the app does not run as root" runs_as_non_root
check "GET / serves the home page" home_page_is_served
check "GET /static/css/tailwind.css serves the built stylesheet" stylesheet_is_served
check "the stylesheet is served gzipped when accepted" stylesheet_is_served_gzipped
check "GET /favicon.ico serves the icon" favicon_is_served
check "sign-up works through the form (CSRF and a database write)" sign_up_works
check "docker stop shuts gunicorn down cleanly" stops_cleanly
check "a new container on the same volume becomes healthy" start "$ID-second"
check "the account survives: log-in works on the new container" log_in_works_on_a_new_container

echo "All smoke checks passed."
