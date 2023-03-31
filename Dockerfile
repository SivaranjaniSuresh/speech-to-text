FROM python:3.10.6

RUN pip install --upgrade pip

WORKDIR /app

ADD userinterface.py requirements.txt /app/

RUN pip install -r requirements.txt

RUN apt-get update && \
    apt-get install -y ffmpeg

ADD helper_functions /app/helper_functions/
ADD helper_functions/__init__.py /app/helper_functions/
ADD helper_functions/core_helpers.py /app/helper_functions/
ADD navigation /app/navigation/
ADD navigation/adhoc.py /app/navigation/
ADD navigation/mp3_uploader.py /app/navigation/
ADD navigation/questionnaire.py /app/navigation/
ADD navigation/config.toml /app/navigation/

EXPOSE 8080

CMD ["streamlit", "run", "userinterface.py", "--server.port", "8080"]