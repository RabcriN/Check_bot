import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telegram import Bot, TelegramError

from exceptions import SendMessageError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    handlers=[logging.FileHandler('homework.log', 'w', 'utf-8')],
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    datefmt='%y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляем сообщение в телеграм чат."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, message)
    except TelegramError:
        raise SendMessageError


def get_api_answer(current_timestamp):
    """Получаем ответ от API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        raise Exception(f'Ошибка при запросе к API: {error}')
    if response.status_code != 200:
        status_code = response.status_code
        raise Exception(
            f'homework_statuses.status_code expected 200, but got '
            f'{status_code}'
        )
    response = response.json()
    return response


def check_response(response):
    """Проверяем полученный ответ."""
    if not isinstance(response, dict):
        raise TypeError(
            f'type of response is not a dict, but {type(response)}'
        )
    try:
        homework_list = response['homeworks']
    except KeyError:
        raise KeyError('key "homeworks" is missing')
    if not isinstance(homework_list, list):
        raise TypeError(
            f'type of homework_list is not a list, but {type(homework_list)}'
        )
    if not homework_list:
        return None
    homework = homework_list[0]
    return homework


def parse_status(homework):
    """Извлекаем из информации о домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        raise KeyError('key "homework_name" is missing')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('key "status" is missing')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError('key {homework_status} not in HOMEWORK_STATUSES')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем корректнось токенов."""
    keys = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for key, value in keys.items():
        if value is None:
            logger.critical(f'{key} is missing')
    return bool(PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)


def main():
    """Основная логика работы бота."""
    logger.debug('main function is started')
    check_dict = {
        'homework_name': '',
        'status': ''
    }
    last_error = 'no errors'
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    logger.debug(f'current_timestamp is {current_timestamp}')
    logger.debug('check_tokens function is started')
    if not check_tokens():
        logger.critical('Critical error. No ".env" data. Shutdown')
        sys.exit()
    while True:
        try:
            logger.debug('get_api_answer function is started')
            response = get_api_answer(current_timestamp)
            logger.debug(f'response is {response}')
            logger.debug('check_response function is started')
            homework = check_response(response)
            logger.debug('checking for homework')
            logger.debug(f'homework is {homework}')
            if homework:
                logger.debug('parse_status function is started')
                message = parse_status(homework)
                logger.debug('checking homework updates')
                logger.debug(f'old homework is {check_dict}')
                current_homework = {
                    'homework_name': homework['homework_name'],
                    'status': homework['status']
                }
                logger.debug(f'new_homework is {current_homework}')
                logger.debug(
                    f'homework != check_dict: {homework != check_dict}'
                )
                if current_homework != check_dict:
                    check_dict = current_homework
                    logger.debug(f'homework updated and now is {check_dict}')
                    logger.debug('send_message function is started')
                    send_message(bot, message)
                    logger.info(f'Bot just sent a message: {message}')
            current_timestamp = (
                response.get('current_date', default=current_timestamp)
            )
            logger.debug(f'current_timestamp = {response.get("current_date")}')
        except SendMessageError:
            logger.error(
                "Can't send a message. An error in the send_message function"
            )
        except Exception as error:
            message = f'an error in the program: {error}'
            logger.error(message)
            if error != last_error:
                send_message(bot, message)
                last_error = error
                logger.debug(f'{last_error}, {error}')
        finally:
            logger.debug(f'go to sleep for {RETRY_TIME}s')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
