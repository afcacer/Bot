import librosa
import librosa.display
import numpy as np
import pydub as pdb
import soundfile as sf
import telebot
from telebot import types
import os

# Инициализация бота
TOKEN = '7897457139:AAFwnUYxO_fxneeHn9ooCiVk4b1znmXu_aU'
bot = telebot.TeleBot(TOKEN)

# Алфавит для шифрования
ALPHABET = '0123456789'

# Временные папки
WORKING_FILES = 'working_files'
GRIFFINLIM_FILES = 'griffinlim_files'
RESULT_FOLDER = 'result'
WORKING_FILES1 = 'working_files1'

# Создаем папки, если их нет
os.makedirs(WORKING_FILES, exist_ok=True)
os.makedirs(GRIFFINLIM_FILES, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)
os.makedirs(WORKING_FILES1, exist_ok=True)

# Глобальные переменные для хранения состояния
user_states = {}

def ALPH(symbol):
    return ALPHABET.find(symbol)

def ALPH_to_list(s):
    return [ALPH(i) for i in s]

def ALPH_to_str(a):
    return ''.join([ALPHABET[int(i)] for i in a])

def sum_of_all_values(sym, result):
    S = np.abs(librosa.stft(result))
    S_db = librosa.amplitude_to_db(S)
    S_db.astype('int32')
    if sum(S_db[4])//len(S_db[0]) != sym:
        return 1
    return 0

def encrypt_audio(file_path, message):
    a = ALPH_to_list(message)
    list_of_timestamps = list(range(1, len(a)+1))
    
    audio = pdb.AudioSegment.from_wav(file_path)
    start = 0
    count = 0
    
    for idx in range(len(list_of_timestamps)):
        end = list_of_timestamps[idx] * 1000
        audio_chunk = audio[start:end]
        audio_chunk.export(f"{WORKING_FILES}/audio_chunk_{count}.wav", format="wav")
        start = end
        count += 1

    k = 0
    for counter in range(count):
        y, sr = librosa.load(f"{WORKING_FILES}/audio_chunk_{counter}.wav")
        S = np.abs(librosa.stft(y))
        S_db = librosa.amplitude_to_db(S)
        S = librosa.db_to_amplitude(S_db)
        result = librosa.griffinlim(S)
        
        if k < len(a):
            while sum_of_all_values(a[k], result):
                S = np.abs(librosa.stft(result))
                S_db = librosa.amplitude_to_db(S)
                for I in range(len(S_db[0])):
                    S_db[1][I] = a[k] + 1
                    S_db[4][I] = a[k]
                    S_db[3][I] = a[k] + 1
                S = librosa.db_to_amplitude(S_db)
                result = librosa.griffinlim(S)
        
        sf.write(f"{GRIFFINLIM_FILES}/audio_chunk_{counter}.wav", result, sr, subtype='PCM_24')
        k += 1
    
    combined_sounds = pdb.AudioSegment.from_wav(f"{GRIFFINLIM_FILES}/audio_chunk_0.wav")
    for i in range(1, k):
        combined_sounds += pdb.AudioSegment.from_wav(f"{GRIFFINLIM_FILES}/audio_chunk_{i}.wav")
    
    result_path = f"{RESULT_FOLDER}/result.wav"
    combined_sounds.export(result_path, format="wav")
    return result_path

def decrypt_audio(file_path, key):
    k = int(key)
    list_of_timestamps = list(range(1, k+1))
    
    audio = pdb.AudioSegment.from_wav(file_path)
    start = 0
    count = 0
    
    for idx in range(len(list_of_timestamps)):
        end = list_of_timestamps[idx] * 1000
        audio_chunk = audio[start:end]
        audio_chunk.export(f"{WORKING_FILES1}/new_chunk{count}.wav", format="wav")
        start = end
        count += 1

    x = []
    for counter in range(count):
        y, sr = librosa.load(f"{WORKING_FILES1}/new_chunk{counter}.wav")
        S = np.abs(librosa.stft(y))
        S_db = librosa.amplitude_to_db(S)
        S_db.astype('int32')
        x.append(int(sum(S_db[3])//len(S_db[0])))
    
    return ALPH_to_str(x)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Шифрование')
    btn2 = types.KeyboardButton('Дешифрование')
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, 
                    "Привет! Это бот для шифрования сообщений в аудиофайлы.\n"
                    "Выберите режим работы:",
                    reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == 'Шифрование')
def start_encryption(message):
    user_states[message.chat.id] = {'mode': 'encrypt', 'step': 0}
    bot.send_message(message.chat.id, 
                    "Выбран режим шифрования.\n"
                    "Пожалуйста, отправьте аудиофайл в формате WAV.")

@bot.message_handler(func=lambda message: message.text == 'Дешифрование')
def start_decryption(message):
    user_states[message.chat.id] = {'mode': 'decrypt', 'step': 0}
    bot.send_message(message.chat.id, 
                    "Выбран режим дешифрования.\n"
                    "Пожалуйста, отправьте зашифрованный аудиофайл.")

@bot.message_handler(content_types=['audio', 'voice', 'document'])
def handle_audio(message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        bot.send_message(chat_id, "Пожалуйста, сначала выберите режим работы (/start)")
        return
    
    mode = user_states[chat_id]['mode']
    
    try:
        if message.audio:
            file_info = bot.get_file(message.audio.file_id)
        elif message.voice:
            file_info = bot.get_file(message.voice.file_id)
        elif message.document:
            file_info = bot.get_file(message.document.file_id)
        else:
            bot.send_message(chat_id, "Пожалуйста, отправьте аудиофайл.")
            return
        
        downloaded_file = bot.download_file(file_info.file_path)
        file_path = f"{WORKING_FILES}/temp_audio.wav"
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # Конвертируем в WAV если нужно
        if not file_path.endswith('.wav'):
            audio = pdb.AudioSegment.from_file(file_path)
            file_path = file_path.split('.')[0] + '.wav'
            audio.export(file_path, format='wav')
        
        user_states[chat_id]['file_path'] = file_path
        user_states[chat_id]['step'] = 1
        
        if mode == 'encrypt':
            bot.send_message(chat_id, "Аудиофайл получен. Теперь введите сообщение для шифрования (только цифры):")
        else:
            bot.send_message(chat_id, "Аудиофайл получен. Теперь введите ключ (количество символов в сообщении):")
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обработке аудиофайла: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    if chat_id not in user_states or user_states[chat_id]['step'] != 1:
        return
    
    mode = user_states[chat_id]['mode']
    file_path = user_states[chat_id]['file_path']
    text = message.text
    
    try:
        if mode == 'encrypt':
            # Проверяем, что сообщение состоит только из цифр
            if not text.isdigit():
                bot.send_message(chat_id, "Сообщение должно содержать только цифры (0-9). Пожалуйста, попробуйте еще раз.")
                return
            
            bot.send_message(chat_id, "Идет процесс шифрования...")
            result_path = encrypt_audio(file_path, text)
            
            with open(result_path, 'rb') as audio_file:
                bot.send_audio(chat_id, audio_file, caption="Ваш зашифрованный аудиофайл")
            
            bot.send_message(chat_id, "Шифрование завершено!")
        
        else:  # decrypt
            if not text.isdigit():
                bot.send_message(chat_id, "Ключ должен быть числом. Пожалуйста, попробуйте еще раз.")
                return
            
            bot.send_message(chat_id, "Идет процесс дешифрования...")
            decrypted_message = decrypt_audio(file_path, text)
            
            bot.send_message(chat_id, f"Дешифрование завершено. Сообщение:\n{decrypted_message}")
        
        # Очищаем состояние пользователя
        del user_states[chat_id]
    
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")
        if chat_id in user_states:
            del user_states[chat_id]

if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
