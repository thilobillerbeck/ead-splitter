FROM node:24 AS frontend
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app
COPY frontend /app
RUN pnpm install
RUN pnpm run build

FROM ghcr.io/astral-sh/uv:python3.13-alpine
WORKDIR /app
ADD backend /app
COPY --from=frontend /app/dist /app/app/frontend
RUN uv sync --frozen --compile-bytecode --no-install-project --no-editable
CMD uv run fastapi run app/main.py --port 80