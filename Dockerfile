# Use python 3.6 
FROM python:3.6-slim

# setup the working directory
RUN mkdir /code && \
    mkdir /code/KPF-Pipeline && \
    apt-get --yes update && \
    apt install build-essential -y --no-install-recommends && \
    apt-get install --yes git && \
    cd /code && \
    # Clone the KeckDRPFramework repository 
    git clone https://github.com/Keck-DataReductionPipelines/KeckDRPFramework.git

# Set the working directory to KPF-Pipeline
WORKDIR /code/KPF-Pipeline
ADD requirements.txt /code/KPF-Pipeline/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip3 install --trusted-host pypi.python.org -r requirements.txt

ADD . /code/KPF-Pipeline

# Run app.py when the container launches
CMD make init && \
    make test