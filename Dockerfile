FROM ubuntu:14.04

RUN \
   apt-get -y update && apt-get -y install python-pip python-dev

RUN \
   apt-get -y install postgresql libpq-dev  && \
   apt-get -y install gcc python-dev python-pip ipython graphviz && \
   apt-get -y install apache2 apache2-mpm-prefork apache2-utils libexpat1 ssl-cert && \
   apt-get -y install libapache2-mod-uwsgi php5 libapache2-mod-wsgi vim && \
   apt-get -y install libreadline-dev libxml2-dev libxslt1-dev sp xsltproc

ADD pip_list.txt /tmp/pip_list.txt
RUN \
   pip install -r /tmp/pip_list.txt && \
   pip install pydot

ADD . /src

WORKDIR /src
RUN chmod 600 mpo*key

EXPOSE 8443
EXPOSE 9443
ENTRYPOINT [ "./entrypoint.sh" ]

CMD [ ]
