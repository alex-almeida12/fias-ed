# Contexto de build: raiz do monorepo.
FROM node:24-alpine AS build
WORKDIR /build/fias-ed-web/frontend
COPY fias-ed-shared/design-tokens /build/fias-ed-shared/design-tokens
COPY fias-ed-shared/schemas /build/fias-ed-shared/schemas
COPY fias-ed-web/frontend/package.json fias-ed-web/frontend/package-lock.json ./
RUN npm ci
COPY fias-ed-web/frontend ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY fias-ed-web/deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/fias-ed-web/frontend/dist /usr/share/nginx/html
EXPOSE 8080
