# Build context MUST be the repo root, not apps/web-app - this app depends
# on shared-ui via an npm workspace (see root package.json's "workspaces"
# field), so `npm install` needs the whole apps/ tree to resolve it as a
# local symlink, not a registry package (there is no published "shared-ui"
# package - it only exists as a workspace member). See docker-compose.yml's
# web-app service: `build: { context: ., dockerfile: apps/web-app/Dockerfile }`.
#
# Two stages: build the static assets with Node, then serve them with
# nginx - a Node process running `vite preview` is a dev-mode server, not
# meant for real traffic. This mirrors the same "don't ship what you don't
# need to run in prod" reasoning as the backend Dockerfiles' single-stage
# builds, just applied to a static-asset frontend instead.

FROM node:20-slim AS build
WORKDIR /repo

COPY package.json package-lock.json ./
COPY apps/web-app/package.json apps/web-app/package.json
COPY apps/shared-ui/package.json apps/shared-ui/package.json
RUN npm install

COPY apps/web-app apps/web-app
COPY apps/shared-ui apps/shared-ui

# Build-time API URLs - Vite bakes these into the static bundle at build
# time (import.meta.env), not read at container start. Passed as build
# args so the same Dockerfile works for docker-compose (localhost ports)
# and a real deploy (real domain/gateway URL) without editing this file -
# see docker-compose.prod.yml and .env.prod.example for the production
# values.
ARG VITE_PLATFORM_SPINE_URL
ARG VITE_QUOTATION_URL
ARG VITE_RESOURCE_NETWORK_URL
ARG VITE_PAYMENTS_URL
ENV VITE_PLATFORM_SPINE_URL=${VITE_PLATFORM_SPINE_URL} \
    VITE_QUOTATION_URL=${VITE_QUOTATION_URL} \
    VITE_RESOURCE_NETWORK_URL=${VITE_RESOURCE_NETWORK_URL} \
    VITE_PAYMENTS_URL=${VITE_PAYMENTS_URL}

RUN npm run build --workspace=web-app

FROM nginx:1.27-alpine
COPY --from=build /repo/apps/web-app/dist /usr/share/nginx/html
COPY apps/web-app/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
