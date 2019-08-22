FROM python:3-alpine
LABEL maintainer="Andrey Andreev <andyceo@yandex.ru> (@andyceo)"
LABEL run="docker run --rm -p 8130:8130 -v /data/stacks:/data/stacks -v /path/to/config.json:/app/config.json andyceo/dockerhub-webhooks"
COPY ./app.py /app/app.py
WORKDIR /app
EXPOSE 8130
ENTRYPOINT ["/app/app.py"]
