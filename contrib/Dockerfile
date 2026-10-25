FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    ESTOFEX_STATE_FILE=/data/estofex_state.json

RUN useradd --create-home --uid 1000 bot && mkdir /data && chown bot /data
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY estofex_warning_bot.py .

USER bot
VOLUME /data
CMD ["python", "estofex_warning_bot.py"]
