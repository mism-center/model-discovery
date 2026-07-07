FROM node:22-alpine AS deps
COPY package.json package-lock.json /app/
WORKDIR /app
RUN npm ci

FROM node:22-alpine AS production-deps
COPY package.json package-lock.json /app/
WORKDIR /app
RUN npm ci --omit=dev --ignore-scripts

FROM node:22-alpine AS build
COPY . /app/
COPY --from=deps /app/node_modules /app/node_modules
WORKDIR /app
RUN npm run build

FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app

RUN addgroup -S app && adduser -S app -G app

COPY --from=production-deps /app/node_modules /app/node_modules
COPY --from=build /app/build /app/build
COPY package.json package-lock.json /app/

USER app
EXPOSE 3000

CMD ["npm", "run", "start"]
