# Это телеграм бот аналог ГетКурса

# Установка
1. На сервере установить гит
~~~pycon
sudo apt update
apt install git
~~~
2. Создать папку проекта
~~~pycon
cd ../
mkdir -p opt/getcourse
cd opt/getcourse
~~~
3. Скачать проект с гитхаба
~~~pycon
/opt/getcourse# git clone https://github.com/MaksAnikeev/it_bot.git .
~~~
4. Скачать на сервер папку с медиа с локального компьютера (необязательно, для запуска пробного контента - запросить у разработчика)
Пример (указываете адрес папки на локале и название сервера):
~~~pycon
scp -r  /mnt/d/Программирование/Devman/it_bot/media getcourse:/opt/getcourse
~~~
5. Скачать на сервер недостающие файлы для работы ТГ бота (запросить у разработчика)
~~~pycon
scp -r  /mnt/d/Программирование/Devman/it_bot/telegram_code getcourse:/opt/getcourse
~~~
6. Скачать тестовую базу (необязательно, для демонстрации пробного контента)
~~~pycon
scp db_start.json getcourse:/opt/getcourse
~~~
7. Создать файл `.env` в корне проекта и прописать туда переменные окружения
TG_BOT_TOKEN - токен вашего бота, полученный у BotFather в ТГ
PAYMENT_UKASSA_TOKEN - токен юкассы, если будете получать платежи через юкассу

данные пустой БД в постгри, она создастся автоматически по указанным вами данным
POSTGRES_URL=postgres:
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=

переменные джанго
SECRET_KEY=ключ проекта
DJANGO_SUPERUSER_USERNAME= имя суперюзера для входа в админку
DJANGO_SUPERUSER_PASSWORD=пароль суперюзера для входа в админку
DJANGO_SUPERUSER_EMAIL=адрес электронной почты суперюзера
ALLOWED_HOSTS=доступные хосты, здесь указывается ip сервера
BASE_MEDIA_URL=http://nginx:80 нужно для раздачи статики для контейнера nginx

Пример
~~~pycon
TG_BOT_TOKEN=5012401124:AAFKCbhhGsDW3rh8mMQIJgcWOXEENU
PAYMENT_UKASSA_TOKEN=381764678:TEST:119110

POSTGRES_URL=postgres://max:Anykey@pgdb:5432/get_course_td_bot
POSTGRES_DB=get_course_td_bot
POSTGRES_USER=max
POSTGRES_PASSWORD=Anykey

SECRET_KEY='django-insecure-&3s652n^nn_l-6l_i&%mc(7$ypwcs))007q%czm48tmjif&12#'
DEBUG=False
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
ALLOWED_HOSTS=127.0.0.1,localhost,get_course_bot,nginx,84.38.180.226
BASE_MEDIA_URL=http://nginx:80
~~~
8. Установить `docker` и `docker compose`
Установка docker
~~~pycon
sudo apt update
sudo apt install apt-transport-https ca-certificates curl software-properties-common

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable"
sudo apt update

apt-cache policy docker-ce

sudo apt install docker-ce
~~~
При успешном запуске увидите:
~~~pycon
sudo systemctl status docker

● docker.service - Docker Application Container Engine
     Loaded: loaded (/lib/systemd/system/docker.service; enabled; vendor preset: enabled)
     Active: active (running) since Wed 2025-04-30 17:36:56 UTC; 22s ago
TriggeredBy: ● docker.socket
       Docs: https://docs.docker.com
   Main PID: 10629 (dockerd)
      Tasks: 7
     Memory: 43.9M
        CPU: 472ms
     CGroup: /system.slice/docker.service
             └─10629 /usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock
~~~
Установка docker compose
~~~pycon
apt  install docker-compose

sudo apt-get install docker-compose-plugin
~~~

9. Если вы копировали проект не в папку `/opt/getcourse`, то вам нужно в файле `docker-compose.yml` изменить адрес папки media
Это необходимо чтобы с сервера подгрузилась медиа в докер контейнер
~~~pycon
version: '3.8'

services:
  
  backend:
    volumes:
      - .:/app
      - collected_static:/app/collected_static
      - /opt/getcourse/media:/app/media  # Монтируем папку с сервера

  nginx:
    volumes:
      - ./hosts/get_course_bot_nginx.conf:/etc/nginx/conf.d/default.conf
      - collected_static:/static_bot/collected_static
      - /opt/getcourse/media:/app/media  # Монтируем папку с сервера
~~~

10. Теперь настройка сервера завершена и можно запускать установку проекта
~~~pycon
docker compose build
~~~
Итог
~~~pycon
[+] Building 2/2
 ✔ backend  Built                                                                                      0.0s
 ✔ bot      Built   
~~~

~~~pycon
docker compose up
~~~
Итог
Начнутся создаваться контейнеры `pgdb, nginx, django_backend, it_bot-bot`
При отсутствии ошибок в браузере вы сможете войти в админ панель
`http://ip вашего сервера/admin/` по логину и паролю, который вы указали в `.env`
а также запустить вашего бота по команде `/start`
