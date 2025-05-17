import telebot
import soundfile as sf
import numpy as np
import os
import logging
from telebot import types

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot("7897457139:AAFwnUYxO_fxneeHn9ooCiVk4b1znmXu_aU")

# Создаем временную директорию
TEMP_DIR = "temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

def save_audio(message):
    """Сохраняет присланное аудио во временный файл."""
    try:
        file_info = bot.get_file(message.audio.file_id if message.audio else message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        file_ext = os.path.splitext(file_info.file_path)[1].lower()
        if file_ext != '.wav':
            raise ValueError("Поддерживаются только WAV-файлы")
            
        file_path = os.path.join(TEMP_DIR, "audio.wav")
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)
            
        return file_path
    except Exception as e:
        logger.error(f"Ошибка сохранения аудио: {e}")
        raise

def encode_lsb(audio_path, message):
    """Кодирует сообщение в LSB аудиофайла."""
    try:
        # Читаем аудиофайл как 16-битные целые числа
        audio, sr = sf.read(audio_path, dtype='int16')
        if len(audio.shape) > 1:
            audio = audio[:, 0]  # Берем первый канал для стерео

        # Добавляем маркер конца сообщения
        message += "§"
        binary_msg = ''.join([format(ord(c), '08b') for c in message])
        
        if len(binary_msg) > len(audio):
            raise ValueError(f"Сообщение слишком длинное. Максимум: {len(audio)//8} символов")
        
        # Кодируем сообщение в LSB
        for i in range(len(binary_msg)):
            audio[i] = (audio[i] & 0xFFFE) | int(binary_msg[i])
        
        # Сохраняем результат
        output_path = os.path.join(TEMP_DIR, "encoded.wav")
        sf.write(output_path, audio, sr, subtype='PCM_16')
        return output_path
    except Exception as e:
        logger.error(f"Ошибка кодирования: {e}")
        raise

def decode_lsb(audio_path):
    """Декодирует сообщение из LSB аудиофайла."""
    try:
        # Читаем аудиофайл как 16-битные целые числа
        audio, _ = sf.read(audio_path, dtype='int16')
        if len(audio.shape) > 1:
            audio = audio[:, 0]  # Берем первый канал для стерео

        # Извлекаем LSB каждого сэмпла
        binary_msg = ''.join([str(sample & 1) for sample in audio])
        
        # Преобразуем биты в текст
        message = ""
        for i in range(0, len(binary_msg), 8):
            byte = binary_msg[i:i+8]
            if len(byte) < 8:
                break
            char = chr(int(byte, 2))
            if char == "§":
                break
            message += char
        
        return message if message else "Сообщение не найдено"
    except Exception as e:
        logger.error(f"Ошибка декодирования: {e}")
        raise

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_encode = types.KeyboardButton("🔒 Зашифровать")
    btn_decode = types.KeyboardButton("🔓 Расшифровать")
    markup.add(btn_encode, btn_decode)
    bot.send_message(
        message.chat.id,
        "Привет! Я бот для LSB-стеганографии в WAV-аудио.\n"
        "Выбери действие:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "🔒 Зашифровать")
def handle_encode(message):
    bot.send_message(
        message.chat.id,
        "Отправь WAV-аудиофайл для кодирования сообщения",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_audio_for_encoding)

def process_audio_for_encoding(message):
    try:
        if not (message.audio or message.document):
            raise ValueError("Нужно отправить аудиофайл")
            
        audio_path = save_audio(message)
        bot.send_message(message.chat.id, "Теперь отправь текст для кодирования:")
        bot.register_next_step_handler(message, lambda m: process_text_for_encoding(m, audio_path))
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

def process_text_for_encoding(message, audio_path):
    try:
        if not message.text:
            raise ValueError("Нужно отправить текстовое сообщение")
            
        encoded_path = encode_lsb(audio_path, message.text)
        with open(encoded_path, 'rb') as f:
            bot.send_audio(
                message.chat.id,
                f,
                caption="Сообщение успешно закодировано!",
                title="encoded_audio"
            )
    except Exception as e:
        bot.reply_to(message, f"Ошибка кодирования: {e}")

@bot.message_handler(func=lambda m: m.text == "🔓 Расшифровать")
def handle_decode(message):
    bot.send_message(
        message.chat.id,
        "Отправь WAV-аудиофайл с закодированным сообщением",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, process_audio_for_decoding)

def process_audio_for_decoding(message):
    try:
        if not (message.audio or message.document):
            raise ValueError("Нужно отправить аудиофайл")
            
        audio_path = save_audio(message)
        decoded = decode_lsb(audio_path)
        bot.reply_to(message, f"Расшифрованное сообщение:\n{decoded}")
    except Exception as e:
        bot.reply_to(message, f"Ошибка декодирования: {e}")

if __name__ == "__main__":
    logger.info("Бот запущен")
    bot.infinity_polling()
