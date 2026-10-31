FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY index.html vite.config.ts tsconfig.json tailwind.config.js postcss.config.js ./
COPY src ./src
COPY public ./public
RUN pnpm build

FROM python:3.12-slim-bookworm AS runtime
ENV PORT=3000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY smartattend_ml /app/smartattend_ml
COPY --from=frontend-build /app/dist /app/dist
EXPOSE 3000
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-3000} --workers 2 --threads 4 --timeout 90 --access-logfile - --error-logfile - backend.wsgi:app"]
