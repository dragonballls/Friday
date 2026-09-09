# syntax=docker/dockerfile:1
FROM node:20-slim AS frontend-build

WORKDIR /app

ARG VITE_API_BASE_URL=http://127.0.0.1:8080/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY desktop/package.json desktop/package-lock.json ./
RUN npm ci

COPY desktop/ .
RUN npm run build

FROM node:20-slim AS frontend
WORKDIR /app
COPY --from=frontend-build /app/dist ./dist
RUN npm install -g serve
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
