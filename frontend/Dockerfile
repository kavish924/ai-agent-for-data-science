# Spec 11 FR-DP-02: frontend image. Build context: the repo root (it copies samples/).
FROM node:22.12.0-bookworm-slim AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM deps AS build
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/ ./
RUN npm run build

FROM node:22.12.0-bookworm-slim AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    SAMPLES_DIR=/app/samples
# The standalone server, its static assets and the sample datasets (FR-DP-03).
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --chown=node:node samples ./samples
USER node
EXPOSE 3000
# FR-DP-25: Render's $PORT, else 3000. HOSTNAME is set here, not inherited, so the server
# always listens on every interface.
CMD ["sh", "-c", "HOSTNAME=0.0.0.0 PORT=${PORT:-3000} exec node server.js"]
