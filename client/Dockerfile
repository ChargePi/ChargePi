#pull image
FROM python:3.7
RUN apt-get update && apt-get install -y \
    curl \
    git

#copy all client files
WORKDIR /ChargePi/client
COPY . .

#install libraries listed in requirements.txt
RUN sudo pip3 install -r requirements.txt

CMD ["sudo python3","ChargePi_client.py"]
