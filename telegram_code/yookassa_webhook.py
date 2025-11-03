# telegram_code/yookassa_webhook.py
from flask import Flask, request, jsonify
import os
import logging
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
BASE_MEDIA_URL = os.getenv("BASE_MEDIA_URL", "http://backend:8080")


if not TG_BOT_TOKEN:
    logger.error("TG_BOT_TOKEN НЕ НАЙДЕН! Проверь .env")
    exit(1)

logger.info(f"TG_BOT_TOKEN: {TG_BOT_TOKEN[:10]}...")


@app.route('/yookassa/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"Вебхук получен: {data.get('event')}")

        if data.get('event') != 'payment.succeeded':
            logger.info(f"Игнорируем событие: {data.get('event')}")
            return jsonify({"status": "ignored"}), 200

        obj = data.get('object', {})
        metadata = obj.get('metadata', {})
        chat_id = metadata.get('chat_id')
        user_id = metadata.get('user_id')
        tariff = metadata.get('tariff')
        amount = obj.get('amount', {}).get('value', '0')

        if not chat_id or not user_id:
            logger.error(f"Нет chat_id/user_id: {metadata}")
            return jsonify({"error": "no chat_id/user_id"}), 400

        logger.info(f"Обрабатываем: chat_id={chat_id}, user_id={user_id}, tariff={tariff}")

        # === ЛОГИКА successful_payment ===
        today = datetime.now().date()
        one_month_later = today + timedelta(days=30)

        full_payload = {
            'amount': float(amount),
            'user': int(user_id),
            'access_date_start': str(today),
            'access_date_finish': str(one_month_later),
            'tariff': tariff,
            'status': "completed",
            'service_description': f"Оплата тарифа {tariff}"
        }

        # API: payment/add
        response = requests.post(f"{BASE_MEDIA_URL}/bot/payment/add/", json=full_payload)
        if not response.ok:
            logger.error(f"Payment add error: {response.status_code} {response.text}")
        else:
            logger.info("Payment added OK")

        # API: start_content/add
        content_payload = {'user': int(user_id), 'tariff': tariff}
        response_content = requests.post(f"{BASE_MEDIA_URL}/bot/start_content/add/", json=content_payload)
        if not response_content.ok:
            logger.error(f"Content add error: {response_content.status_code} {response_content.text}")
        else:
            logger.info("Content added OK")

        # === СООБЩЕНИЕ + КНОПКА ===
        text = 'Оплата успешно произведена, можете приступать к прохождению курса'
        keyboard = [[{"text": "📖 Главное меню", "callback_data": "main_menu"}]]
        reply_markup = {"inline_keyboard": keyboard}

        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup
        }
        r = requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage", json=payload)
        if r.ok:
            logger.info(f"Сообщение отправлено: {chat_id}")
        else:
            logger.error(f"Telegram error: {r.text}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500


# ← ВАЖНО: Запуск Flask
if __name__ == "__main__":
    logger.info("Yookassa webhook запущен на :8443")
    app.run(host='0.0.0.0', port=8443, debug=False)
