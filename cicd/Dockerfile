FROM apache/airflow:3.1.8-python3.11

COPY ./dags/ /opt/airflow/dags/

COPY ./requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt