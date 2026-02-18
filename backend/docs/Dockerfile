FROM swaggerapi/swagger-ui

# Копируем openapi.yaml в контейнер
COPY openapi.yaml /usr/share/nginx/html/openapi.yaml

# Настраиваем переменные окружения для Swagger UI
ENV URL=/openapi.yaml
