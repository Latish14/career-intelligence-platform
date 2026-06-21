# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration if needed, otherwise use default
# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
