# Frontend SPA — build with Vite, serve with `serve` (single-page mode).
# No reverse proxy config needed: the SPA calls the backend at
# VITE_API_BASE_URL (baked in at build time), so this container is pure static.
FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /web
RUN npm install -g serve@14
COPY --from=build /web/dist ./dist
# Dokploy sets PORT; serve honors it. -s = SPA fallback for client-side routes.
ENV PORT=3000
EXPOSE 3000
CMD ["sh", "-c", "serve -s dist -l ${PORT:-3000}"]
