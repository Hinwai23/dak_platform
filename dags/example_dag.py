import time
import datetime
from airflow.sdk import DAG, task

with DAG(
    dag_id="example_dag",
    start_date=datetime.datetime(2021, 1, 1),
    schedule="@daily"
):
    
    @task
    def hello_world():
        time.sleep(5)
        print("Hello world, from Airflow!")
    
    @task
    def goodbye_world():
        time.sleep(5)
        print("Goodbye world, from Airflow!")


    @task
    def sleep_for_a_while():
        time.sleep(10)
        print("Slept for a while!")

    @task
    def add_numbers(x: int, y: int) -> int:
        time.sleep(5)
        result = x + y
        print(f"The sum of {x} and {y} is {result}")
        return result
    
    hello_world() >> goodbye_world()
