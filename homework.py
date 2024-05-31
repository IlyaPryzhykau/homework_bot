import logging
import os
import sys
import time

from http import HTTPStatus
from dotenv import load_dotenv
import requests
from telebot import TeleBot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
TWO_DAYS = 172000
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)

stream_handler = logging.StreamHandler(sys.stdout)
stream_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
stream_handler.setFormatter(stream_formatter)

logger.addHandler(stream_handler)


def check_tokens():
    """Проверяет наличие необходимых переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }

    missing_tokens = [name for name, token in tokens.items() if token is None]

    if missing_tokens:
        logger.critical(f"Отсутствуют обязательные переменные "
                        f"окружения: {', '.join(missing_tokens)}")
        return False

    return True


def send_message(bot, message):
    """Отправляет сообщение пользователю."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug(f'Отправлено: {message}')

    except Exception as error:
        logger.error(f'Сообщение не отправлено, причина: {error}')


def get_api_answer(timestamp):
    """Запрашивает статусы домашних работ с эндпоинта ЯндексПрактикума."""
    try:
        homework_status = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if homework_status.status_code == HTTPStatus.OK:
            return homework_status.json()
        else:
            raise AssertionError(
                logger.error(f"Ошибка при получении данных:"
                             f" {homework_status.status_code}"))

    except requests.exceptions.ConnectionError as error:
        logger.error(f"Недоступен эндпоинт: {error}")

    except requests.exceptions.RequestException as error:
        logger.error(f"Сбой при запросе к эндпоинту: {error}")

    return None


def check_response(response):
    """Проверка ожидаемых ключей в ответе API."""
    try:
        homeworks = response['homeworks']
        if isinstance(homeworks, list):
            if len(homeworks) == 0:
                return None
            return homeworks[0]
        else:
            logger.error("Неправильный тип значения для ключа 'homeworks'")
            raise TypeError("Неправильный тип значения для ключа 'homeworks'")
    except KeyError:
        logger.error("Отсутствует ключ 'homeworks' в ответе API")
        raise KeyError("Отсутствует ключ 'homeworks' в ответе API")


def parse_status(homework):
    """Подготавливает сообщение для отправки ботом."""
    if homework is not None:
        if 'lesson_name' not in homework:
            logger.debug('Ключ "lesson_name" отсутствует в ответе API')
            raise KeyError('Ключ "lesson_name" отсутствует в ответе API')

        homework_name = homework['homework_name']
        response_status = homework['status']

        if response_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS[response_status]
            return (f'Изменился статус проверки работы'
                    f' "{homework_name}". {verdict}')

        logger.error(f'Неожиданный статус домашней работы: {response_status}')
    else:
        logger.debug('Нет данных о статусе домашней работы.')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - TWO_DAYS  # Проверяем за последние 2-е суток
    error_message_sent = False

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            message = parse_status(homeworks)
            if message:
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if not error_message_sent:
                send_message(bot, message)
                error_message_sent = True

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
