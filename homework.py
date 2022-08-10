import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telegram import Bot, TelegramError

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
        raise TelegramError('an error in send_message function')


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
    if type(response) is not dict:
        raise TypeError(
            f'type of response is not a dict, but {type(response)}'
        )
    try:
        homework_list = response['homeworks']
    except KeyError:
        raise KeyError('key "homeworks" is missing')
    if type(homework_list) is not list:
        raise TypeError(
            f'type of homework_list is not a list, but {type(homework_list)}'
        )
    try:
        homework = homework_list[0]
    except IndexError:
        raise IndexError('homework list is empty')
    return homework


def parse_status(homework):
    """Проверяем изменение статуса проверки работы."""
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
    hw_status = None
    check_dict = {
        'homework_name': '',
        'status': '',
    }
    error_list = []
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
            logger.debug(f'homework is {homework}')
            logger.debug('checking for response updates')
            logger.debug(f'number of homeworks: {len(response["homeworks"])}')

            if len(response['homeworks']) != 0:
                logger.debug('parse_status function is started')
                message = parse_status(homework)
                logger.debug(f'message is {message}')
                logger.debug('checking for status updates')
                logger.debug(f'{hw_status} != {homework["status"]}')
                logger.debug(f'{hw_status != homework["status"]}')

                # Да, тут 2 ifа друг под другом, но их объединить не получится
                # (либо я не знаю, как это сделать). Потому что тесты не дают
                # вынести проверку на 'status' из функции parse_status (не
                # проходят иначе), а если её не запускать перед следующим ifом
                # то возникает шанс натолкнуться на KeyError

                if hw_status != homework['status']:
                    hw_status = homework['status']
                    logger.debug(f'hw_status now is {hw_status}')
                    logger.debug('send_message function is started')
                    send_message(bot, message)

                    logger.info(f'Bot just sent a message: {message}')
            logger.debug(f'go to sleep for {RETRY_TIME}s')
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time())
            logger.debug(f'Change current_timestamp to {current_timestamp}')

        except Exception as error:
            error_list.append(error)
            message = f'an error in the program: {error}'
            logger.error(message)
            if error != error_list[0]:
                send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            pass


if __name__ == '__main__':
    main()
