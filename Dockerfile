FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8773

CMD ["python", "-m", "shika", "serve", "--host", "0.0.0.0"]
