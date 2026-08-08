FROM node:22-alpine AS build
ARG API_INTERNAL_URL=http://api:8000/api
ENV API_INTERNAL_URL=$API_INTERNAL_URL
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app .
EXPOSE 3000
CMD ["npm","start"]
