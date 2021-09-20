# inherit python image
FROM python:3.6

WORKDIR /app

COPY . /app

# copy python dependencies and instlall
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# copy the rest of the application
COPY . .

EXPOSE 8001
STOPSIGNAL SIGINT

ENTRYPOINT ["python"]
CMD ["app.py"]