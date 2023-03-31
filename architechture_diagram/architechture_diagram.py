from diagrams import Cluster, Diagram, Edge
from diagrams.aws.storage import S3
from diagrams.custom import Custom
from diagrams.onprem.client import User
from diagrams.onprem.workflow import Airflow
from diagrams.programming.language import Python

graph_attr = {
    "splines": "ortho",
    "overlap": "false",
    "nodesep": "1.0",
    "ranksep": "1.5",
    "fontsize": "12",
    "fontname": "Verdana",
}

with Diagram("MP3 Transcript Workflow", show=False, graph_attr=graph_attr):
    user = User("Streamlit User")

    with Cluster("Streamlit App"):
        streamlit_app = Custom("Streamlit App", "architechture_diagram\streamlit.png")
        upload_mp3 = Python("Upload MP3")
        select_question = Python("Select Default Question")
        custom_question = Python("Ask Custom Question")

    with Cluster("Airflow"):
        airflow_trigger_dag = Airflow("Trigger DAG")
        airflow_cron_dag = Airflow("Cron DAG")
        with Cluster("Open AI"):
            whisper_api = Custom("Whisper API", "architechture_diagram\openai.png")
            openai_api = Custom("OpenAI API", "architechture_diagram\openai.png")

    with Cluster("S3 Bucket"):
        main_bucket = S3("damg7245-team4-assignment-4")
        to_be_processed = Custom(
            "to_be_processed", "architechture_diagram\directory.png"
        )
        archived = Custom("archived", "architechture_diagram\directory.png")
        transcripts = Custom("transcripts", "architechture_diagram\directory.png")
        default_qna = Custom("default_qna", "architechture_diagram\directory.png")

    ########################################################################################################
    ### Workflow connections
    ########################################################################################################

    ## MP3 Upload Flow
    user >> streamlit_app >> upload_mp3 >> to_be_processed
    ## Adhoc Flow
    (
        user
        >> streamlit_app
        >> airflow_trigger_dag
        >> to_be_processed
        >> whisper_api
        >> transcripts
    )

    ## Batch Flow
    airflow_cron_dag >> to_be_processed >> whisper_api >> transcripts

    ## Generic Q&A Flow
    airflow_trigger_dag >> openai_api >> default_qna
    airflow_cron_dag >> openai_api >> default_qna

    ## Questionnarire
    user >> streamlit_app >> default_qna >> select_question >> default_qna
    user << streamlit_app << default_qna

    user >> streamlit_app >> custom_question >> openai_api
    user << streamlit_app << openai_api

    ## Genral Process
    to_be_processed >> archived
