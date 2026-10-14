FROM node:20-slim

WORKDIR /app

# Dependencies are installed first so that a source change does not invalidate
# the cached install layer.
COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
